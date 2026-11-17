// Calendar and wall-clock maths for Adam's time zone (Europe/Bratislava by default), done in code so
// no model ever works out a date, a weekday or a UTC time. Pure: callers pass `now`. Uses Intl, so
// daylight saving is right without a library. Dates are "YYYY-MM-DD" strings, times "HH:MM".
//
// Reusable: nothing here knows about supplies or OpenClaw. lib/reminder.js and lib/supplies.js
// build on it, and any later feature that needs "the instant 09:00 on that day in Bratislava" or
// "a month before that date" can import it as it is.

const DAY_MS = 86400000;
const NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

export const isDate = (s) => typeof s === "string" && /^\d{4}-\d{2}-\d{2}$/.test(s)
  && !Number.isNaN(Date.parse(`${s}T00:00:00Z`)) && new Date(`${s}T00:00:00Z`).toISOString().slice(0, 10) === s;

export const isTime = (s) => typeof s === "string" && /^([01][0-9]|2[0-3]):[0-5][0-9]$/.test(s);

export const isTimeZone = (tz) => {
  if (typeof tz !== "string" || !tz) return false;
  try { new Intl.DateTimeFormat("en-GB", { timeZone: tz }); return true; } catch { return false; }
};

const utcNoon = (date) => Date.parse(`${date}T12:00:00Z`);
const fromMs = (ms) => new Date(ms).toISOString().slice(0, 10);

/** date + n calendar days (n may be negative). */
export function addDays(date, n) {
  return fromMs(utcNoon(date) + Math.trunc(n) * DAY_MS);
}

/** date + n calendar months; the 31st becomes the month's last day when the month is shorter. */
export function addMonths(date, n) {
  const [y, m, d] = date.split("-").map(Number);
  const total = y * 12 + (m - 1) + Math.trunc(n);
  const ny = Math.floor(total / 12);
  const nm = total - ny * 12;
  const last = new Date(Date.UTC(ny, nm + 1, 0)).getUTCDate();
  return `${String(ny).padStart(4, "0")}-${String(nm + 1).padStart(2, "0")}-${String(Math.min(d, last)).padStart(2, "0")}`;
}

/** Whole calendar days from a to b (b later: positive). */
export function daysBetween(a, b) {
  return Math.round((utcNoon(b) - utcNoon(a)) / DAY_MS);
}

export const minDate = (a, b) => (a <= b ? a : b);
export const maxDate = (a, b) => (a >= b ? a : b);

/** 1 (Monday) to 7 (Sunday) for a calendar date. */
export function weekdayOf(date) {
  const w = new Date(utcNoon(date)).getUTCDay();
  return w === 0 ? 7 : w;
}

export const weekdayName = (date) => NAMES[weekdayOf(date) - 1];

/** "Thursday 15 April 2027" */
export function longDate(date) {
  const [y, m, d] = date.split("-").map(Number);
  return `${weekdayName(date)} ${d} ${MONTHS[m - 1]} ${y}`;
}

function wallParts(ms, timeZone) {
  const f = new Intl.DateTimeFormat("en-GB", {
    timeZone, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  });
  const p = {};
  for (const x of f.formatToParts(new Date(ms))) p[x.type] = x.value;
  return { date: `${p.year}-${p.month}-${p.day}`, time: `${p.hour}:${p.minute}` };
}

// The zone's offset at an instant, in whole minutes times 60000 (local wall clock minus UTC).
function offsetMs(ms, timeZone) {
  const w = wallParts(ms, timeZone);
  const asUtc = Date.parse(`${w.date}T${w.time}:00Z`);
  const floored = Math.floor(ms / 60000) * 60000;
  return asUtc - floored;
}

/** { date, time, minutes, weekday, weekdayName } of the wall clock in timeZone at `now`. */
export function localNow(timeZone, now = new Date()) {
  const w = wallParts(now.getTime(), timeZone);
  const [h, mi] = w.time.split(":").map(Number);
  return { date: w.date, time: w.time, minutes: h * 60 + mi, weekday: weekdayOf(w.date), weekdayName: weekdayName(w.date) };
}

export const today = (timeZone, now = new Date()) => localNow(timeZone, now).date;

/**
 * The instant at which the wall clock in timeZone shows `date` `time`. In the spring gap (a time
 * that doesn't exist that night) it gives the moment just after the clocks jump, the same wall
 * time shifted forward; in the autumn overlap it gives the first of the two.
 * Returns { at: Date, shifted: boolean }.
 */
export function zonedInstant(date, time, timeZone) {
  const wall = Date.parse(`${date}T${time}:00Z`);
  const o1 = offsetMs(wall, timeZone);
  const candidates = [...new Set([wall - o1, wall - offsetMs(wall - o1, timeZone)])].sort((a, b) => a - b);
  const exact = candidates.filter((t) => { const w = wallParts(t, timeZone); return w.date === date && w.time === time; });
  if (exact.length) {
    // An overlap hour has two exact answers an hour apart; look an hour earlier too.
    const earlier = exact[0] - 3600000;
    const we = wallParts(earlier, timeZone);
    const first = we.date === date && we.time === time ? earlier : exact[0];
    return { at: new Date(first), shifted: false };
  }
  return { at: new Date(candidates[candidates.length - 1]), shifted: true };
}

/** "2027-04-15T07:00:00.000Z": what OpenClaw's scheduler takes for kind "at" (no zone means UTC). */
export const utcIso = (d) => d.toISOString();
