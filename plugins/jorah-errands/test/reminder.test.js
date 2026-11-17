// One-shot reminder jobs: the right instant in Adam's zone, the main-session shape that survives the
// daily chat reset, the upsert key, and text that doesn't trip the guard by itself.

import { test } from "node:test";
import assert from "node:assert/strict";
import { buildReminder, ReminderError, slug } from "../lib/reminder.js";

const TZ = "Europe/Bratislava";
const NOW = new Date("2026-11-17T15:00:00Z"); // 16:00 in Bratislava, a Tuesday
const base = { timeZone: TZ, now: NOW };

test("a date at the default 09:00 becomes the right UTC instant, as a main-session system event", () => {
  const r = buildReminder({ ...base, text: "Renew the parking permit", when: { date: "2027-04-15" } });
  assert.equal(r.status, "ok");
  assert.equal(r.call.action, "add");
  assert.deepEqual(r.call.job.schedule, { kind: "at", at: "2027-04-15T07:00:00.000Z" });
  assert.equal(r.call.job.sessionTarget, "main");
  assert.equal(r.call.job.wakeMode, "now");
  assert.equal(r.call.job.payload.kind, "systemEvent");
  assert.match(r.call.job.payload.text, /^Reminder Adam asked for, due now: Renew the parking permit/);
  assert.equal(r.local.spoken, "Thursday 15 April 2027 at 09:00");
  assert.equal(r.in_days, 149);
  assert.equal(r.guard_card, false);
  assert.equal(r.call.job.declarationKey, undefined);
});

test("time, inDays, inMinutes and before", () => {
  assert.equal(buildReminder({ ...base, text: "x", when: { date: "2026-11-20", time: "18:00" } }).call.job.schedule.at, "2026-11-20T17:00:00.000Z");
  const tomorrow = buildReminder({ ...base, text: "x", when: { inDays: 1, time: "07:30" } });
  assert.equal(tomorrow.local.date, "2026-11-18");
  assert.equal(tomorrow.call.job.schedule.at, "2026-11-18T06:30:00.000Z");
  const soon = buildReminder({ ...base, text: "x", when: { inMinutes: 20 } });
  assert.equal(soon.call.job.schedule.at, "2026-11-17T15:20:00.000Z");
  assert.equal(soon.local.time, "16:20");
  const before = buildReminder({ ...base, text: "Passport", when: { before: "2027-05-14", months: 1 } });
  assert.equal(before.local.date, "2027-04-14");
  assert.equal(before.call.job.schedule.at, "2027-04-14T07:00:00.000Z");
  assert.equal(buildReminder({ ...base, text: "x", when: { before: "2027-05-14", weeks: 2, days: 1 } }).local.date, "2027-04-29");
});

test("a key makes the job an upsert under jorah:", () => {
  assert.equal(buildReminder({ ...base, text: "x", when: { inDays: 3 }, key: "Passport renewal" }).call.job.declarationKey, "jorah:reminder:passport-renewal");
  assert.equal(buildReminder({ ...base, text: "x", when: { inDays: 3 }, key: "jorah:restock:contact-lenses" }).call.job.declarationKey, "jorah:restock:contact-lenses");
  assert.throws(() => buildReminder({ ...base, text: "x", when: { inDays: 3 }, key: "!!!" }), ReminderError);
});

test("a moment that has passed is reported, not scheduled", () => {
  const r = buildReminder({ ...base, text: "x", when: { date: "2026-11-17", time: "09:00" } });
  assert.equal(r.status, "past");
  assert.equal(r.call, undefined);
  assert.equal(buildReminder({ ...base, text: "x", when: { inDays: 0, time: "18:00" } }).status, "ok");
});

test("bad input is refused with a reason", () => {
  assert.throws(() => buildReminder({ ...base, text: "x", when: {} }), /exactly one/);
  assert.throws(() => buildReminder({ ...base, text: "x", when: { date: "2027-02-29" } }), /real date/);
  assert.throws(() => buildReminder({ ...base, text: "x", when: { date: "2027-01-01", inDays: 2 } }), /exactly one/);
  assert.throws(() => buildReminder({ ...base, text: "x", when: { inMinutes: 5, time: "10:00" } }), /no time/);
  assert.throws(() => buildReminder({ ...base, text: "x", when: { before: "2027-05-14" } }), /days, weeks or months/);
  assert.throws(() => buildReminder({ ...base, text: "x", when: { date: "2027-01-01", time: "25:00" } }), /HH:MM/);
  assert.throws(() => buildReminder({ ...base, text: "   ", when: { inDays: 1 } }), /empty/);
  assert.throws(() => buildReminder({ ...base, text: "a".repeat(301), when: { inDays: 1 } }), /300/);
});

test("the guard's words appear only when Adam's own text has them", () => {
  assert.equal(buildReminder({ ...base, text: "Search for a new desk lamp", when: { inDays: 1 } }).guard_card, true);
  const plain = buildReminder({ ...base, text: "Call the dentist", when: { inDays: 1 }, then: "Then ask how it went." });
  assert.equal(plain.guard_card, false);
  assert.doesNotMatch(JSON.stringify(plain.call), /\b(fetch|browse|web|search|http)/i);
});

test("control characters and new lines are flattened", () => {
  const r = buildReminder({ ...base, text: "line one\nline two\u0007", when: { inDays: 1 } });
  assert.match(r.call.job.payload.text, /line one line two/);
  assert.equal(slug("Kontaktné šošovky!"), "kontaktne-sosovky");
});
