// One-shot reminders, built in code: the exact `automations` call for "on that date at that time in
// Adam's zone", so the model never works out a date, a weekday or a UTC time. Pure: `now` is passed.
//
// The job is a main-session system event (the heartbeat lane), not an isolated or current run:
// those are bound to the chat that created them, and Adam's chat resets every day at 04:00, so a
// reminder months away could find its chat gone. A main-session event goes to the main session as it
// is when the time comes (docs: automation/cron-jobs/payloads.md, "Main session vs current vs
// isolated vs custom"). A declarationKey makes `add` an upsert: adding again with the same key moves
// the earlier reminder instead of making a second one (OpenClaw 2026.10.9, cron service add).
//
// jorah-guard (config/permission-matrix.json, "schedule") lets a one-off reminder through in Adam's
// clean chat unless its text mentions the web; after outside text it shows Adam a card. So the
// text built here never uses those words itself, and `guardCard` says when Adam's own text will.

import { addDays, addMonths, daysBetween, isDate, isTime, localNow, longDate, utcIso, weekdayName, zonedInstant } from "./dates.js";

export const KEY_PREFIX = "jorah:";
export const MAX_TEXT = 300;
const GUARD_WORDS = /\b(fetch|browse|web|search|http)/i;
const KEY_RE = /^[a-z0-9][a-z0-9:-]{0,59}$/;

export class ReminderError extends Error {}

const clean = (s) => String(s ?? "").replace(/[\u0000-\u001f\u007f]+/g, " ").replace(/\s+/g, " ").trim();

/** "Contact lenses!" -> "contact-lenses" */
export function slug(s, max = 40) {
  return clean(s).toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, max).replace(/-+$/g, "");
}

const intIn = (v, lo, hi) => Number.isInteger(v) && v >= lo && v <= hi;

/**
 * When, in one of four shapes (exactly one):
 *   { date: "YYYY-MM-DD", time?: "HH:MM" }
 *   { inDays: 1..3650, time?: "HH:MM" }                     calendar days from today
 *   { inMinutes: 1..10080 }                                  from now
 *   { before: "YYYY-MM-DD", days?, weeks?, months?, time? }  that date minus the offset
 * Returns { date, time, at: Date, shifted } or throws ReminderError.
 */
export function resolveWhen(when, { timeZone, now, defaultTime = "09:00" }) {
  if (!when || typeof when !== "object") throw new ReminderError("say when: date, inDays, inMinutes or before");
  const forms = ["date", "inDays", "inMinutes", "before"].filter((k) => when[k] !== undefined);
  if (forms.length !== 1) throw new ReminderError("give exactly one of date, inDays, inMinutes or before");
  const form = forms[0];
  const time = when.time ?? defaultTime;
  if (form !== "inMinutes" && !isTime(time)) throw new ReminderError("time must be HH:MM, 24-hour");
  const here = localNow(timeZone, now);

  if (form === "inMinutes") {
    if (when.time !== undefined) throw new ReminderError("inMinutes takes no time");
    if (!intIn(when.inMinutes, 1, 10080)) throw new ReminderError("inMinutes must be a whole number from 1 to 10080 (a week)");
    const at = new Date(Math.ceil((now.getTime() + when.inMinutes * 60000) / 60000) * 60000);
    const local = localNow(timeZone, at);
    return { date: local.date, time: local.time, at, shifted: false };
  }

  let date;
  if (form === "date") {
    if (!isDate(when.date)) throw new ReminderError("date must be a real date, YYYY-MM-DD");
    date = when.date;
  } else if (form === "inDays") {
    if (!intIn(when.inDays, 0, 3650)) throw new ReminderError("inDays must be a whole number from 0 to 3650");
    date = addDays(here.date, when.inDays);
  } else {
    if (!isDate(when.before)) throw new ReminderError("before must be a real date, YYYY-MM-DD");
    const { days = 0, weeks = 0, months = 0 } = when;
    if (![days, weeks, months].every((n) => intIn(n, 0, 3650))) throw new ReminderError("days, weeks and months must be whole numbers from 0");
    if (days + weeks + months === 0) throw new ReminderError("before needs days, weeks or months");
    date = addDays(addMonths(when.before, -months), -(weeks * 7 + days));
  }
  const { at, shifted } = zonedInstant(date, time, timeZone);
  return { date, time, at, shifted };
}

/**
 * The exact automations call for a one-shot reminder.
 *   text  what Jorah should tell Adam when it fires (Adam's words where possible), up to 300 chars
 *   key   optional; the same key later moves this reminder instead of adding a second one
 *   then  optional instruction for Jorah when it fires (built by code, e.g. "call supply_list")
 * Returns { status: "ok", ... } or { status: "past", ... } when that moment has already gone.
 */
export function buildReminder({ text, when, key, name, then, timeZone, now, defaultTime = "09:00", minLeadMinutes = 1 }) {
  const what = clean(text);
  if (!what) throw new ReminderError("text is empty: say what the reminder is for");
  if (what.length > MAX_TEXT) throw new ReminderError(`text is longer than ${MAX_TEXT} characters`);
  let declarationKey;
  if (key !== undefined && key !== null) {
    const k = String(key).toLowerCase().startsWith(KEY_PREFIX) ? String(key).toLowerCase() : `${KEY_PREFIX}reminder:${slug(key, 40)}`;
    if (!KEY_RE.test(k) || k === KEY_PREFIX || k.endsWith(":")) throw new ReminderError("key must be a few letters, digits or dashes");
    declarationKey = k;
  }
  const r = resolveWhen(when, { timeZone, now, defaultTime });
  const local = { date: r.date, time: r.time, weekday: weekdayName(r.date), spoken: `${longDate(r.date)} at ${r.time}` };
  const todayDate = localNow(timeZone, now).date;
  if (r.at.getTime() < now.getTime() + minLeadMinutes * 60000) {
    return { status: "past", reason: `${local.spoken} (${timeZone}) has already passed`, local, timeZone };
  }
  const event = clean(`Reminder Adam asked for, due now: ${what}${then ? ` ${clean(then)}` : ""} Tell him now, even in quiet hours: he chose this time.`);
  const job = {
    name: clean(name ?? `Reminder: ${what}`).slice(0, 80),
    ...(declarationKey ? { declarationKey } : {}),
    schedule: { kind: "at", at: utcIso(r.at) },
    sessionTarget: "main",
    wakeMode: "now",
    payload: { kind: "systemEvent", text: event },
  };
  return {
    status: "ok",
    local,
    timeZone,
    in_days: daysBetween(todayDate, r.date),
    ...(r.shifted ? { note: `${r.time} doesn't exist that night (clocks go forward), so it fires an hour later` } : {}),
    ...(declarationKey ? { key: declarationKey, replaces: "an earlier reminder with this key, if one is still waiting" } : {}),
    guard_card: GUARD_WORDS.test(event),
    call: { action: "add", job },
  };
}
