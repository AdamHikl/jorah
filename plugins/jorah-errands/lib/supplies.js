// Things Adam buys again, and when each runs out, worked out in code. Pure: callers pass today's
// date in Adam's zone. Generic: contact lenses, vitamins, water filters, coffee, printer ink, a
// yearly renewal. A supply has one or more lines, each with its own stock (one per eye for lenses
// with different powers, one line for most things).
//
//   line.perPack     units in one pack (6 lenses in a box, 60 tablets in a bottle, 1000 g of coffee)
//   line.use         { units, days }: how fast Adam uses them (1 lens per 30 days per eye; 1 tablet
//                    per 1 day; 250 g per 7 days)
//   events           purchase { date, packs: { line: n } } adds stock; count { date, units: { line: n } }
//                    is what Adam says is left, unopened, and replaces what the record thought
//
// Cover per line, in date order: a purchase adds its days of use from the later of the day it was
// bought and the day the line would have run out; a count starts again from its date (the unit in
// use isn't counted, so the date errs early). Units that last part of a period count down, never up:
// 7 days of cover is never rounded to 8. The supply runs out on the earliest line's date. A line
// with no purchase or count is unknown, never zero.

import { addDays, daysBetween, isDate, longDate } from "./dates.js";
import { buildReminder, slug } from "./reminder.js";

export class SupplyError extends Error {}

export const LIMITS = { lines: 6, events: 200, name: 60, product: 80, unit: 20, label: 40, spec: 60, notes: 300, shop: 80, note: 200 };
const LINE_KEY = /^[a-z0-9][a-z0-9-]{0,19}$/;
const CURRENCY = /^[A-Z]{3}$/;

const clean = (s) => String(s ?? "").replace(/[\u0000-\u001f\u007f]+/g, " ").replace(/\s+/g, " ").trim();
const intIn = (v, lo, hi) => Number.isInteger(v) && v >= lo && v <= hi;
const numIn = (v, lo, hi) => typeof v === "number" && Number.isFinite(v) && v >= lo && v <= hi;

function text(v, max, what, { required = false } = {}) {
  if (v === undefined || v === null) {
    if (required) throw new SupplyError(`${what} is missing`);
    return undefined;
  }
  const t = clean(v);
  if (!t && required) throw new SupplyError(`${what} is empty`);
  if (t.length > max) throw new SupplyError(`${what} is longer than ${max} characters`);
  return t;
}

/** Days one purchase or count of `units` lasts on one line: whole days, rounded down. */
export function coverDays(units, use) {
  return Math.floor((units * use.days) / use.units + 1e-9);
}

/** Lead time when Adam set none: a third of the latest event's cover, at most 30 days, at least 1. */
export function autoLead(cover) {
  return Math.min(30, Math.max(1, Math.floor(cover / 3)));
}

function checkLine(l, existing) {
  if (!l || typeof l !== "object") throw new SupplyError("each line is an object");
  const key = clean(l.key ?? existing?.key ?? "").toLowerCase();
  if (!LINE_KEY.test(key)) throw new SupplyError("line key: a short lower-case word, e.g. right, left or main");
  const out = { ...(existing ?? {}), key };
  if (l.label !== undefined) out.label = text(l.label, LIMITS.label, "line label");
  if (l.spec !== undefined) out.spec = l.spec === null ? undefined : text(l.spec, LIMITS.spec, "line spec");
  if (l.perPack !== undefined) {
    if (!intIn(l.perPack, 1, 100000)) throw new SupplyError("perPack: a whole number of units in one pack, 1 or more");
    out.perPack = l.perPack;
  }
  if (l.use !== undefined) {
    if (!l.use || !numIn(l.use.units, 0.001, 100000) || !intIn(l.use.days, 1, 3650)) {
      throw new SupplyError("use: { units, days }, how many units Adam uses in how many days, e.g. { units: 1, days: 30 }");
    }
    out.use = { units: l.use.units, days: l.use.days };
  }
  if (!out.label) out.label = key;
  if (out.spec === undefined) delete out.spec;
  return out;
}

function checkEvent(e, lines, todayDate) {
  if (!e || typeof e !== "object") throw new SupplyError("event is an object");
  const date = e.date ?? todayDate;
  if (!isDate(date)) throw new SupplyError("event date must be YYYY-MM-DD");
  if (date > todayDate) throw new SupplyError("event date is in the future: record a purchase when it's made");
  const keys = new Set(lines.map((l) => l.key));
  const only = lines.length === 1 ? lines[0].key : null;
  const perLine = (obj, what, check) => {
    // A number on its own means "the only line" when there is just one.
    const o = typeof obj === "number" && only ? { [only]: obj } : obj;
    if (!o || typeof o !== "object" || Array.isArray(o)) throw new SupplyError(`${what}: { line: number }, e.g. { right: 1, left: 1 }`);
    const out = {};
    for (const [k, v] of Object.entries(o)) {
      if (!keys.has(k)) throw new SupplyError(`${what}: no line called ${clean(k).slice(0, 20)} (lines: ${[...keys].join(", ")})`);
      if (!check(v)) throw new SupplyError(`${what}.${k} isn't a sensible number`);
      out[k] = v;
    }
    if (Object.keys(out).length === 0) throw new SupplyError(`${what} names no line`);
    return out;
  };
  if (e.type === "purchase") {
    const out = { type: "purchase", date, packs: perLine(e.packs, "packs", (v) => intIn(v, 0, 1000)) };
    const shop = text(e.shop, LIMITS.shop, "shop");
    if (shop) out.shop = shop;
    if (e.price !== undefined && e.price !== null) {
      if (!numIn(e.price?.amount, 0, 1000000) || !CURRENCY.test(String(e.price?.currency ?? ""))) throw new SupplyError("price: { amount, currency: \"EUR\" }, what Adam paid in total");
      out.price = { amount: Math.round(e.price.amount * 100) / 100, currency: e.price.currency };
    }
    const note = text(e.note, LIMITS.note, "note");
    if (note) out.note = note;
    return out;
  }
  if (e.type === "count") {
    const out = { type: "count", date, units: perLine(e.units, "units", (v) => numIn(v, 0, 1000000)) };
    const note = text(e.note, LIMITS.note, "note");
    if (note) out.note = note;
    return out;
  }
  throw new SupplyError("event type is purchase or count");
}

/**
 * Applies supply_save's fields to `current` (or a new supply) and returns the new record. Throws
 * SupplyError with a reason Adam can act on. `todayDate` is Adam's local date.
 */
export function applySave(current, p, { todayDate, nowIso }) {
  const isNew = !current;
  const s = isNew ? { lines: [], events: [], created_at: nowIso } : structuredClone(current);
  if (isNew) {
    s.name = text(p.name, LIMITS.name, "name", { required: true });
    s.id = p.id ? clean(p.id).toLowerCase() : slug(s.name);
    if (!/^[a-z0-9][a-z0-9-]{0,39}$/.test(s.id)) throw new SupplyError("id: lower-case letters, digits and dashes");
  } else if (p.name !== undefined) {
    s.name = text(p.name, LIMITS.name, "name", { required: true });
  }
  if (p.product !== undefined) s.product = text(p.product, LIMITS.product, "product");
  if (p.unit !== undefined) s.unit = text(p.unit, LIMITS.unit, "unit");
  if (p.notes !== undefined) s.notes = p.notes === null ? undefined : text(p.notes, LIMITS.notes, "notes");
  if (p.leadDays !== undefined) {
    if (p.leadDays !== null && !intIn(p.leadDays, 0, 365)) throw new SupplyError("leadDays: whole days before running out, 0 to 365, or null for automatic");
    s.lead_days = p.leadDays ?? undefined;
  }
  if (p.remindTime !== undefined) {
    if (p.remindTime !== null && !/^([01][0-9]|2[0-3]):[0-5][0-9]$/.test(p.remindTime)) throw new SupplyError("remindTime: HH:MM");
    s.remind_time = p.remindTime ?? undefined;
  }
  if (p.lines !== undefined) {
    if (!Array.isArray(p.lines) || p.lines.length === 0) throw new SupplyError("lines: a list of at least one line");
    for (const l of p.lines) {
      const key = clean(l?.key ?? "").toLowerCase();
      const i = s.lines.findIndex((x) => x.key === key);
      const line = checkLine(l, i >= 0 ? s.lines[i] : null);
      if (i >= 0) s.lines[i] = line; else s.lines.push(line);
    }
    if (s.lines.length > LIMITS.lines) throw new SupplyError(`at most ${LIMITS.lines} lines`);
  }
  if (isNew && s.lines.length === 0) {
    // One line by default, so a simple supply needs no line list.
    s.lines.push(checkLine({ key: "main", label: s.name, ...(p.perPack !== undefined ? { perPack: p.perPack } : {}), ...(p.use !== undefined ? { use: p.use } : {}) }, null));
  } else if (p.perPack !== undefined || p.use !== undefined) {
    if (s.lines.length !== 1) throw new SupplyError("perPack and use on their own fit a supply with one line; give them per line");
    s.lines[0] = checkLine({ key: s.lines[0].key, ...(p.perPack !== undefined ? { perPack: p.perPack } : {}), ...(p.use !== undefined ? { use: p.use } : {}) }, s.lines[0]);
  }
  if (p.undoLast === true) {
    if (s.events.length === 0) throw new SupplyError("there is no purchase or count to undo");
    s.events.pop();
  }
  if (p.event !== undefined && p.event !== null) {
    const e = checkEvent(p.event, s.lines, todayDate);
    for (const k of Object.keys(e.packs ?? {})) {
      if (!s.lines.find((l) => l.key === k)?.perPack) throw new SupplyError(`line ${k} has no pack size yet: say how many units are in one pack`);
    }
    s.events.push({ ...e, recorded_at: nowIso });
    if (s.events.length > LIMITS.events) s.events.splice(0, s.events.length - LIMITS.events);
  }
  if (s.product === undefined) delete s.product;
  if (s.unit === undefined) delete s.unit;
  if (s.notes === undefined) delete s.notes;
  if (s.lead_days === undefined) delete s.lead_days;
  if (s.remind_time === undefined) delete s.remind_time;
  s.updated_at = nowIso;
  return s;
}

/** Cover of each line, from the events in date order (same date: the order they were recorded). */
export function lineCover(supply, extraEvents = []) {
  const events = [...supply.events, ...extraEvents].map((e, i) => ({ e, i })).sort((a, b) => (a.e.date < b.e.date ? -1 : a.e.date > b.e.date ? 1 : a.i - b.i));
  const out = {};
  for (const line of supply.lines) {
    let until = null;
    let last = null;
    let bought = 0;
    let lastCover = null;
    let missing = null;
    for (const { e } of events) {
      if (e.type === "purchase" && e.packs?.[line.key] > 0) {
        if (!line.perPack || !line.use) { missing = !line.perPack ? "pack size" : "how fast it's used"; continue; }
        const units = e.packs[line.key] * line.perPack;
        const cover = coverDays(units, line.use);
        const start = until && until > e.date ? until : e.date;
        until = addDays(start, cover);
        bought += units;
        lastCover = cover;
        last = { type: "purchase", date: e.date, packs: e.packs[line.key], units };
      } else if (e.type === "count" && e.units?.[line.key] !== undefined) {
        if (!line.use) { missing = "how fast it's used"; continue; }
        const cover = coverDays(e.units[line.key], line.use);
        until = addDays(e.date, cover);
        lastCover = cover;
        last = { type: "count", date: e.date, units: e.units[line.key] };
      }
    }
    out[line.key] = until
      ? { runs_out_on: until, last, last_cover_days: lastCover, units_bought: bought }
      : { runs_out_on: "unknown", reason: missing ? `no ${missing} for this line` : "no purchase or count recorded yet" };
  }
  return out;
}

const REORDER_THEN = (id) => `Call supply_list for ${id} and tell Adam what to reorder (product and pack). When he says he has ordered, record it with supply_save, which sets the next reminder.`;

/**
 * Where a supply stands on `todayDate`: per line and overall, the reminder date, and the exact
 * automations call that sets (or moves) its one reminder. Never invents a number: a line with no
 * data is "unknown", and the supply's date then covers only the lines that are known.
 */
export function status(supply, { todayDate, timeZone, now, defaultTime = "09:00", extraEvents = [] }) {
  const lines = lineCover(supply, extraEvents);
  const known = Object.entries(lines).filter(([, v]) => v.runs_out_on !== "unknown");
  const unknown = Object.entries(lines).filter(([, v]) => v.runs_out_on === "unknown").map(([k]) => k);
  const lineList = supply.lines.map((l) => ({ key: l.key, label: l.label, ...(l.spec ? { spec: l.spec } : {}), per_pack: l.perPack ?? "unknown", use: l.use ?? "unknown", ...lines[l.key] }));
  const base = {
    id: supply.id, name: supply.name, ...(supply.product ? { product: supply.product } : {}), ...(supply.unit ? { unit: supply.unit } : {}),
    ...(supply.notes ? { notes: supply.notes } : {}), lines: lineList,
    last_purchase: [...supply.events].reverse().find((e) => e.type === "purchase") ?? null,
  };
  if (known.length === 0) {
    return { ...base, runs_out_on: "unknown", reason: "no purchase or count recorded yet: ask Adam when he last bought and how many, or how many are left", reminder: { status: "not set", reason: "the run-out date is unknown" } };
  }
  let first = known[0];
  for (const k of known) if (k[1].runs_out_on < first[1].runs_out_on) first = k;
  const runsOut = first[1].runs_out_on;
  const lead = supply.lead_days ?? autoLead(first[1].last_cover_days ?? 0);
  const remindOn = addDays(runsOut, -lead);
  const daysLeft = daysBetween(todayDate, runsOut);
  const out = {
    ...base,
    runs_out_on: runsOut,
    runs_out_spoken: longDate(runsOut),
    days_left: daysLeft,
    ...(daysLeft < 0 ? { ran_out: `by the record, ran out ${-daysLeft} days ago` } : {}),
    first_line_out: first[0],
    ...(unknown.length ? { partial: `lines with no data, not counted: ${unknown.join(", ")}` } : {}),
    lead_days: lead,
    lead_source: supply.lead_days !== undefined ? "set by Adam" : "automatic: a third of the last cover, at most 30 days",
  };
  if (remindOn <= todayDate) {
    out.reminder = { status: "due now", remind_on: remindOn, say: daysLeft < 0 ? `Reorder now: by the record it ran out on ${longDate(runsOut)}.` : `Reorder now: it runs out on ${longDate(runsOut)}, in ${daysLeft} days.` };
    return out;
  }
  const r = buildReminder({
    text: `${supply.name}${supply.product ? ` (${supply.product})` : ""} runs out on ${runsOut} by Jorah's supplies record: time to reorder.`,
    then: REORDER_THEN(supply.id),
    when: { date: remindOn, time: supply.remind_time ?? defaultTime },
    key: `jorah:restock:${supply.id}`,
    name: `Restock: ${supply.name}`.slice(0, 80),
    timeZone, now, defaultTime,
  });
  out.reminder = r.status === "ok"
    ? { status: "to set", remind_on: remindOn, local: r.local, key: r.key, call: r.call, how: "pass call to automations exactly as given; the same key moves an earlier reminder, so there is never a second one" }
    : { status: "due now", remind_on: remindOn, say: `Reorder soon: it runs out on ${longDate(runsOut)}.` };
  return out;
}

/** What-if: the same status with a purchase or count that isn't saved. */
export function plan(supply, event, ctx) {
  const e = checkEvent(event, supply.lines, ctx.todayDate);
  for (const k of Object.keys(e.packs ?? {})) {
    if (!supply.lines.find((l) => l.key === k)?.perPack) throw new SupplyError(`line ${k} has no pack size yet`);
  }
  const s = status(supply, { ...ctx, extraEvents: [e] });
  delete s.reminder;
  return { ...s, if: e, saved: false };
}
