// Local time for Adam (Europe/Bratislava by default), computed with Intl so daylight saving is
// right without a library. Everything here is pure: callers pass `now`.

const parts = (timeZone, now) => {
  const f = new Intl.DateTimeFormat("en-GB", {
    timeZone, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit",
    weekday: "short", hourCycle: "h23",
  });
  const out = {};
  for (const p of f.formatToParts(now)) out[p.type] = p.value;
  return out;
};

const WEEKDAYS = { Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6, Sun: 7 };
const NAMES = ["", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

/** { date: "YYYY-MM-DD", time: "HH:MM", minutes: 0..1439, weekday: 1 (Mon)..7 (Sun), weekdayName } */
export function localNow(timeZone, now = new Date()) {
  const p = parts(timeZone, now);
  const weekday = WEEKDAYS[p.weekday];
  return {
    date: `${p.year}-${p.month}-${p.day}`,
    time: `${p.hour}:${p.minute}`,
    minutes: Number(p.hour) * 60 + Number(p.minute),
    weekday,
    weekdayName: NAMES[weekday],
  };
}

export const localDate = (timeZone, at) => localNow(timeZone, at instanceof Date ? at : new Date(at)).date;

/** "HH:MM" -> minutes after midnight, or null. */
export function hhmm(value) {
  const m = /^([01][0-9]|2[0-3]):([0-5][0-9])$/.exec(String(value ?? ""));
  return m ? Number(m[1]) * 60 + Number(m[2]) : null;
}

/** Calendar date arithmetic on "YYYY-MM-DD" (no time zone involved). */
export function addDays(date, n) {
  const d = new Date(`${date}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

export const isDate = (s) => typeof s === "string" && /^\d{4}-\d{2}-\d{2}$/.test(s) && !Number.isNaN(Date.parse(`${s}T00:00:00Z`))
  && new Date(`${s}T00:00:00Z`).toISOString().slice(0, 10) === s;

/**
 * Quiet hours (01 section 11): a window such as 22:30 to 07:30 that may wrap midnight. When
 * `wokeAt` (the phone's alarm_stopped or wake today) falls inside this morning's part of the
 * window and `awakeEndsQuiet` is on, the window ends at that moment: Adam is up.
 * Returns { active, start, end, reason }.
 */
export function quietHours({ timeZone, now = new Date(), start = "22:30", end = "07:30", wokeAt = null, awakeEndsQuiet = true }) {
  const s = hhmm(start);
  const e = hhmm(end);
  if (s === null || e === null) return { active: true, start, end, reason: "quiet hours setting unreadable, so treated as quiet" };
  if (s === e) return { active: false, start, end, reason: "no quiet hours set" };
  const here = localNow(timeZone, now);
  const m = here.minutes;
  const inside = s < e ? m >= s && m < e : m >= s || m < e;
  if (!inside) return { active: false, start, end, reason: "outside quiet hours" };
  // Morning part of a window that wraps midnight, or a window that lies wholly in the morning.
  const morning = s < e ? true : m < e;
  if (awakeEndsQuiet && morning && wokeAt) {
    const w = new Date(wokeAt);
    if (!Number.isNaN(w.getTime()) && w <= now && localDate(timeZone, w) === here.date) {
      const wm = localNow(timeZone, w).minutes;
      const afterStart = s < e ? wm >= s : true;
      if (afterStart && wm <= m) return { active: false, start, end, reason: `inside quiet hours, but the phone says Adam woke at ${localNow(timeZone, w).time}` };
    }
  }
  return { active: true, start, end, reason: `quiet hours ${start} to ${end}` };
}

/** Minutes between two instants, b - a. */
export const minutesBetween = (a, b) => (new Date(b).getTime() - new Date(a).getTime()) / 60000;

/** The end of Adam's local day containing `now`, as an ISO instant (23:59:59 local). */
export function endOfLocalDay(timeZone, now = new Date()) {
  const here = localNow(timeZone, now);
  const minutesLeft = 24 * 60 - here.minutes;
  const into = now.getUTCSeconds() * 1000 + now.getUTCMilliseconds();
  return new Date(now.getTime() + minutesLeft * 60000 - into - 1000).toISOString();
}
