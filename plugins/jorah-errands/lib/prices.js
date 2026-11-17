// Price comparisons in code: per unit, per month at Adam's rate of use, and the total for a period
// with shipping and the free-shipping threshold. Pure and generic (lenses, vitamins, coffee, ink,
// a subscription). Money is worked in cents. A missing price or shipping cost stays "unknown" and is
// never filled in: an offer without a price is listed but not ranked, and one with unknown shipping
// is ranked after the ones whose total is known.

import { daysBetween, isDate } from "./dates.js";

export class PriceError extends Error {}

const clean = (s) => String(s ?? "").replace(/[\u0000-\u001f\u007f]+/g, " ").replace(/\s+/g, " ").trim();
const intIn = (v, lo, hi) => Number.isInteger(v) && v >= lo && v <= hi;
const money = (v) => typeof v === "number" && Number.isFinite(v) && v >= 0 && v <= 1000000;
const cents = (v) => Math.round(v * 100);
const eur = (c) => Math.round(c) / 100;

export const STALE_DAYS = 7;

/**
 * offers: [{ shop, product?, url?, packPrice, unitsPerPack, shipping?, freeShippingFrom?, checkedOn, note? }]
 * need:   { units, days, lines? }  how fast Adam uses units; lines = variants that each need their own
 *         packs (2 for two eyes with different powers), default 1
 * periodDays: the period to cover when need is given (default 180)
 */
export function compare({ offers, need, periodDays, currency = "EUR", todayDate }) {
  if (!Array.isArray(offers) || offers.length === 0 || offers.length > 20) throw new PriceError("offers: 1 to 20");
  if (!/^[A-Z]{3}$/.test(currency)) throw new PriceError("currency: three capital letters, e.g. EUR");
  let n = null;
  if (need !== undefined && need !== null) {
    const lines = need.lines ?? 1;
    if (!(typeof need.units === "number" && need.units > 0 && need.units <= 100000) || !intIn(need.days, 1, 3650) || !intIn(lines, 1, 20)) {
      throw new PriceError("need: { units, days, lines? }, e.g. 1 lens per 30 days, lines 2 for two eyes");
    }
    n = { units: need.units, days: need.days, lines };
  }
  const period = periodDays ?? (n ? 180 : null);
  if (period !== null && !intIn(period, 1, 3650)) throw new PriceError("periodDays: 1 to 3650");

  const rows = offers.map((o, i) => {
    const shop = clean(o?.shop).slice(0, 80) || `offer ${i + 1}`;
    const row = { shop, ...(o?.product ? { product: clean(o.product).slice(0, 120) } : {}), ...(o?.url ? { url: clean(o.url).slice(0, 300) } : {}) };
    if (!intIn(o?.unitsPerPack, 1, 100000)) return { ...row, status: "unranked", reason: "units per pack unknown" };
    row.units_per_pack = o.unitsPerPack;
    if (!isDate(o?.checkedOn)) return { ...row, status: "unranked", reason: "no date checked: a price needs the day it was seen" };
    row.checked_on = o.checkedOn;
    if (todayDate && o.checkedOn > todayDate) return { ...row, status: "unranked", reason: "checked date is in the future" };
    if (todayDate && daysBetween(o.checkedOn, todayDate) > STALE_DAYS) row.stale = `checked ${daysBetween(o.checkedOn, todayDate)} days ago: check again before buying`;
    if (!money(o?.packPrice)) return { ...row, status: "unranked", reason: "price unknown" };
    const pack = cents(o.packPrice);
    row.pack_price = eur(pack);
    row.per_unit = Math.round((pack / o.unitsPerPack) * 100) / 10000; // to a hundredth of a cent: grams of coffee cost less than a cent
    if (o.note) row.note = clean(o.note).slice(0, 200);
    const ship = money(o?.shipping) ? cents(o.shipping) : null;
    const free = money(o?.freeShippingFrom) ? cents(o.freeShippingFrom) : null;
    row.shipping = ship === null ? "unknown" : eur(ship);
    if (free !== null) row.free_shipping_from = eur(free);
    if (n) {
      // Per month: what the units Adam actually uses cost, without shipping (a month is 30 days).
      row.per_month = Math.round((pack / o.unitsPerPack) * (n.units / n.days) * 30 * n.lines) / 100;
      // The period: whole packs per line, each line bought separately.
      const unitsPerLine = (n.units * period) / n.days;
      const packsPerLine = Math.ceil(unitsPerLine / o.unitsPerPack - 1e-9);
      const packs = packsPerLine * n.lines;
      const goods = pack * packs;
      row.period = { days: period, packs, packs_per_line: packsPerLine, goods: eur(goods) };
      const shipping = free !== null && goods >= free ? 0 : ship;
      if (shipping === null) {
        row.period.shipping = "unknown";
        row.period.total = "unknown";
        row.status = "ranked, shipping unknown";
      } else {
        row.period.shipping = eur(shipping);
        row.period.total = eur(goods + shipping);
        row.period.per_month_with_shipping = Math.round(((goods + shipping) / period) * 30) / 100;
        row.period.lasts_days = Math.floor((packsPerLine * o.unitsPerPack * n.days) / n.units + 1e-9);
        if (free !== null && goods < free) row.period.to_free_shipping = eur(free - goods);
        row.status = "ranked";
      }
      row._key = shipping === null ? [1, goods] : [0, goods + shipping];
    } else {
      row._key = [0, pack / o.unitsPerPack];
      row.status = "ranked";
    }
    return row;
  });

  const ranked = rows.filter((r) => r._key).sort((a, b) => a._key[0] - b._key[0] || a._key[1] - b._key[1]);
  ranked.forEach((r, i) => { r.rank = i + 1; delete r._key; });
  const unranked = rows.filter((r) => !r.rank);
  return {
    status: "ok",
    currency,
    basis: n ? `${n.units} per ${n.days} days${n.lines > 1 ? ` on each of ${n.lines} lines, bought separately` : ""}; period ${period} days; a month is 30 days` : "price per unit only (no rate of use given)",
    ranked,
    ...(unranked.length ? { unranked } : {}),
    rule: "Only prices seen on a shop's page, with the date checked. Unknown stays unknown.",
  };
}
