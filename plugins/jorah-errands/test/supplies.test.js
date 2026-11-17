// Run-out and reorder dates for things Adam buys again, worked out in code. Lens powers here are
// placeholders, never Adam's: his are health data and stay on the PC.

import { test } from "node:test";
import assert from "node:assert/strict";
import { addDays } from "../lib/dates.js";
import { applySave, autoLead, coverDays, plan, status, SupplyError } from "../lib/supplies.js";

const TZ = "Europe/Bratislava";
const NOW = new Date("2026-11-17T15:00:00Z");
const TODAY = "2026-11-17";
const ctx = { todayDate: TODAY, timeZone: TZ, now: NOW };
const at = { todayDate: TODAY, nowIso: NOW.toISOString() };
const SPEC_R = "PLACEHOLDER-R";
const SPEC_L = "PLACEHOLDER-L";

const lenses = () => applySave(null, {
  name: "Contact lenses", product: "Example Lens 30", unit: "lens", leadDays: 30,
  lines: [
    { key: "right", label: "Right eye", spec: SPEC_R, perPack: 6, use: { units: 1, days: 30 } },
    { key: "left", label: "Left eye", spec: SPEC_L, perPack: 6, use: { units: 1, days: 30 } },
  ],
}, at);
const buy = (s, packs, date = TODAY) => applySave(s, { event: { type: "purchase", date, packs } }, at);

test("cover is whole days, rounded down; the automatic lead is a third, at most 30", () => {
  assert.equal(coverDays(6, { units: 1, days: 30 }), 180);
  assert.equal(coverDays(1000, { units: 250, days: 7 }), 28);
  assert.equal(coverDays(10, { units: 3, days: 10 }), 33);
  assert.equal(coverDays(60, { units: 1, days: 1 }), 60);
  assert.equal(autoLead(180), 30);
  assert.equal(autoLead(28), 9);
  assert.equal(autoLead(2), 1);
});

test("a new supply with no purchase is unknown, never zero, and sets no reminder", () => {
  const st = status(lenses(), ctx);
  assert.equal(st.id, "contact-lenses");
  assert.equal(st.runs_out_on, "unknown");
  assert.equal(st.reminder.status, "not set");
  assert.equal(st.lines[0].spec, SPEC_R);
});

test("one box of 6 per eye: six months, a reminder 30 days before at 09:00, under the restock key", () => {
  const st = status(buy(lenses(), { right: 1, left: 1 }), ctx);
  assert.equal(st.runs_out_on, "2027-05-16");
  assert.equal(st.days_left, 180);
  assert.equal(st.lead_days, 30);
  assert.equal(st.reminder.status, "to set");
  assert.equal(st.reminder.remind_on, "2027-04-16");
  assert.equal(st.reminder.local.spoken, "Friday 16 April 2027 at 09:00");
  const job = st.reminder.call.job;
  assert.equal(st.reminder.call.action, "add");
  assert.equal(job.declarationKey, "jorah:restock:contact-lenses");
  assert.deepEqual(job.schedule, { kind: "at", at: "2027-04-16T07:00:00.000Z" });
  assert.equal(job.sessionTarget, "main");
  assert.match(job.payload.text, /Contact lenses \(Example Lens 30\) runs out on 2027-05-16/);
  assert.match(job.payload.text, /supply_list/);
});

test("the reminder never carries a line's spec (a prescription stays in the record)", () => {
  const st = status(buy(lenses(), { right: 1, left: 1 }), ctx);
  const call = JSON.stringify(st.reminder.call);
  assert.ok(!call.includes(SPEC_R) && !call.includes(SPEC_L));
  assert.doesNotMatch(call, /\b(fetch|browse|web|search|http)/i);
});

test("buying again before running out adds to the end; after running out, from the purchase", () => {
  let s = buy(lenses(), { right: 1, left: 1 }, "2026-05-01"); // runs out 2026-10-28, already past
  assert.equal(status(s, ctx).runs_out_on, "2026-10-28");
  assert.match(status(s, ctx).ran_out, /20 days ago/);
  assert.equal(status(s, ctx).reminder.status, "due now");
  s = buy(s, { right: 1, left: 1 }, TODAY);
  assert.equal(status(s, ctx).runs_out_on, addDays(TODAY, 180));
  let t = buy(lenses(), { right: 1, left: 1 }, "2026-11-01"); // to 2027-04-30
  t = buy(t, { right: 1, left: 1 }, TODAY);
  assert.equal(status(t, ctx).runs_out_on, "2027-10-27");
});

test("the first eye to run out sets the date", () => {
  const st = status(buy(lenses(), { right: 2, left: 1 }), ctx);
  assert.equal(st.first_line_out, "left");
  assert.equal(st.runs_out_on, "2027-05-16");
  assert.equal(st.lines.find((l) => l.key === "right").runs_out_on, "2027-11-12");
});

test("only one eye bought: the other is unknown and named, not counted as zero", () => {
  const st = status(buy(lenses(), { right: 1 }), ctx);
  assert.equal(st.runs_out_on, "2027-05-16");
  assert.match(st.partial, /left/);
  assert.equal(st.lines.find((l) => l.key === "left").runs_out_on, "unknown");
});

test("a count of what's left starts again from its date; due now when inside the lead", () => {
  let s = buy(lenses(), { right: 1, left: 1 }, "2026-09-01");
  s = applySave(s, { event: { type: "count", units: { right: 1, left: 1 } } }, at);
  const st = status(s, ctx);
  assert.equal(st.runs_out_on, "2026-12-17");
  assert.equal(st.reminder.status, "due now");
  assert.match(st.reminder.say, /Reorder now: it runs out on Thursday 17 December 2026, in 30 days/);
});

test("one-line supplies take plain numbers: vitamins and coffee", () => {
  let vit = applySave(null, { name: "Vitamin D", unit: "tablet", perPack: 60, use: { units: 1, days: 1 } }, at);
  vit = applySave(vit, { event: { type: "purchase", packs: 2 } }, at);
  const v = status(vit, ctx);
  assert.equal(v.runs_out_on, addDays(TODAY, 120));
  assert.equal(v.lead_days, 30);
  assert.equal(v.lead_source.startsWith("automatic"), true);
  let coffee = applySave(null, { name: "Coffee beans", unit: "g", perPack: 1000, use: { units: 250, days: 7 } }, at);
  coffee = applySave(coffee, { event: { type: "purchase", packs: 1, shop: "Example roastery", price: { amount: 24.9, currency: "EUR" } } }, at);
  const c = status(coffee, ctx);
  assert.equal(c.runs_out_on, addDays(TODAY, 28));
  assert.equal(c.lead_days, 9);
  assert.equal(c.reminder.remind_on, addDays(TODAY, 19));
  assert.deepEqual(c.last_purchase.price, { amount: 24.9, currency: "EUR" });
});

test("a renewal is a supply too: one item that lasts a year", () => {
  let ins = applySave(null, { name: "Bike insurance", perPack: 1, use: { units: 1, days: 365 }, leadDays: 21, remindTime: "18:00" }, at);
  ins = applySave(ins, { event: { type: "purchase", packs: 1, date: "2026-03-01" } }, at);
  const st = status(ins, ctx);
  assert.equal(st.runs_out_on, "2027-03-01");
  assert.equal(st.reminder.remind_on, "2027-02-08");
  assert.equal(st.reminder.call.job.schedule.at, "2027-02-08T17:00:00.000Z");
});

test("changes merge by line key; undoLast removes the last event", () => {
  let s = buy(lenses(), { right: 1, left: 1 });
  s = applySave(s, { lines: [{ key: "left", spec: "PLACEHOLDER-L2" }] }, at);
  assert.equal(s.lines.length, 2);
  assert.equal(s.lines.find((l) => l.key === "left").spec, "PLACEHOLDER-L2");
  assert.equal(s.lines.find((l) => l.key === "left").perPack, 6);
  s = applySave(s, { undoLast: true }, at);
  assert.equal(s.events.length, 0);
  assert.throws(() => applySave(s, { undoLast: true }, at), /nothing|no purchase/);
});

test("refusals name what's wrong", () => {
  const s = lenses();
  assert.throws(() => applySave(s, { event: { type: "purchase", packs: { middle: 1 } } }, at), /no line called middle/);
  assert.throws(() => applySave(s, { event: { type: "purchase", date: "2026-11-18", packs: { right: 1 } } }, at), /future/);
  assert.throws(() => applySave(s, { event: { type: "purchase", packs: 1 } }, at), /packs/);
  assert.throws(() => applySave(s, { event: { type: "refund", packs: { right: 1 } } }, at), /purchase or count/);
  assert.throws(() => applySave(null, { product: "x" }, at), /name is missing/);
  const noPack = applySave(null, { name: "Filters", use: { units: 1, days: 60 } }, at);
  assert.throws(() => applySave(noPack, { event: { type: "purchase", packs: 1 } }, at), /pack size/);
  assert.throws(() => applySave(null, { name: "x", perPack: 0 }, at), SupplyError);
  assert.throws(() => applySave(null, { name: "x", use: { units: 1, days: 0 } }, at), /use/);
});

test("plan shows a what-if without saving it", () => {
  const s = buy(lenses(), { right: 1, left: 1 });
  const p = plan(s, { type: "purchase", packs: { right: 1, left: 1 } }, ctx);
  assert.equal(p.saved, false);
  assert.equal(p.runs_out_on, "2027-11-12");
  assert.equal(p.reminder, undefined);
  assert.equal(s.events.length, 1);
  assert.equal(status(s, ctx).runs_out_on, "2027-05-16");
});
