// Price maths for any shopping comparison. Shops and prices here are made up.

import { test } from "node:test";
import assert from "node:assert/strict";
import { compare, PriceError } from "../lib/prices.js";

const TODAY = "2026-11-17";
const lensNeed = { units: 1, days: 30, lines: 2 }; // one lens a month per eye, boxes per eye

test("per unit, per month and a six-month total with the free-shipping threshold", () => {
  const r = compare({
    todayDate: TODAY,
    need: lensNeed,
    offers: [
      { shop: "Shop A", packPrice: 29.9, unitsPerPack: 6, shipping: 3.9, freeShippingFrom: 50, checkedOn: TODAY },
      { shop: "Shop B", packPrice: 15.5, unitsPerPack: 3, shipping: 2.5, checkedOn: TODAY },
    ],
  });
  assert.equal(r.status, "ok");
  const a = r.ranked.find((x) => x.shop === "Shop A");
  assert.equal(a.per_unit, 4.9833);
  assert.equal(a.per_month, 9.97);
  assert.deepEqual(a.period, { days: 180, packs: 2, packs_per_line: 1, goods: 59.8, shipping: 0, total: 59.8, per_month_with_shipping: 9.97, lasts_days: 180 });
  const b = r.ranked.find((x) => x.shop === "Shop B");
  assert.equal(b.period.packs, 4);
  assert.equal(b.period.goods, 62);
  assert.equal(b.period.total, 64.5);
  assert.equal(a.rank, 1);
  assert.equal(b.rank, 2);
});

test("below the threshold, shipping is added and the gap to free shipping is shown", () => {
  const r = compare({ todayDate: TODAY, need: { units: 1, days: 30 }, periodDays: 90, offers: [{ shop: "C", packPrice: 19.99, unitsPerPack: 3, shipping: 4.5, freeShippingFrom: 40, checkedOn: TODAY }] });
  const c = r.ranked[0];
  assert.equal(c.period.total, 24.49);
  assert.equal(c.period.to_free_shipping, 20.01);
});

test("unknown stays unknown: no price is unranked, unknown shipping ranks after known totals", () => {
  const r = compare({
    todayDate: TODAY,
    need: lensNeed,
    offers: [
      { shop: "No price", packPrice: null, unitsPerPack: 6, checkedOn: TODAY },
      { shop: "Cheap, shipping unknown", packPrice: 10, unitsPerPack: 6, checkedOn: TODAY },
      { shop: "Dearer, shipping known", packPrice: 30, unitsPerPack: 6, shipping: 0, checkedOn: TODAY },
      { shop: "No date", packPrice: 20, unitsPerPack: 6 },
    ],
  });
  assert.deepEqual(r.ranked.map((x) => x.shop), ["Dearer, shipping known", "Cheap, shipping unknown"]);
  assert.equal(r.ranked[1].period.total, "unknown");
  assert.equal(r.ranked[1].shipping, "unknown");
  assert.deepEqual(r.unranked.map((x) => [x.shop, x.reason]), [["No price", "price unknown"], ["No date", "no date checked: a price needs the day it was seen"]]);
});

test("old prices are flagged; future dates refused", () => {
  const r = compare({ todayDate: TODAY, offers: [{ shop: "Old", packPrice: 5, unitsPerPack: 1, checkedOn: "2026-11-01" }, { shop: "Future", packPrice: 5, unitsPerPack: 1, checkedOn: "2026-11-20" }] });
  assert.match(r.ranked[0].stale, /16 days ago/);
  assert.equal(r.unranked[0].reason, "checked date is in the future");
  assert.match(r.basis, /per unit only/);
});

test("small unit prices keep their precision (grams of coffee)", () => {
  const r = compare({ todayDate: TODAY, need: { units: 250, days: 7 }, periodDays: 28, offers: [{ shop: "Roastery", packPrice: 19.9, unitsPerPack: 1000, shipping: 0, checkedOn: TODAY }] });
  assert.equal(r.ranked[0].per_unit, 0.0199);
  assert.equal(r.ranked[0].per_month, 21.32);
  assert.equal(r.ranked[0].period.packs, 1);
});

test("bad input is refused", () => {
  assert.throws(() => compare({ offers: [] }), PriceError);
  assert.throws(() => compare({ offers: [{ shop: "x" }], need: { units: 1, days: 0 } }), /need/);
  assert.throws(() => compare({ offers: [{ shop: "x" }], currency: "eur" }), /currency/);
});
