// C1 and C4's time rules: today's picture, built by code from the clock, the phone service and the
// open loops, and when the brief and the wrap-up are due. Anything that couldn't be read is
// { status: "unavailable", reason } or { status: "not_connected" }, never a zero.

import { endOfLocalDay, hhmm, localDate, localNow, quietHours } from "./clock.js";
import { DEFAULTS, todayCounts } from "./restraint.js";

export const HEALTH_OFF = Object.freeze({ status: "off", received_at: null, night: null, hrv_ms: null, resting_bpm: null, workouts: [] });
export const SCHOOL_DAYS = [1, 2, 3, 4, 5];

export function buildToday({ now, timeZone, phone, loops, proactive, cfg = {}, includeHealth = false }) {
  const here = localNow(timeZone, now);
  const schoolDays = cfg.schoolDays ?? SCHOOL_DAYS;
  let phonePart;
  if (phone?.ok) {
    phonePart = { status: "ok", ...phone.body.phone, health: includeHealth ? phone.body.health : { ...HEALTH_OFF } };
  } else {
    phonePart = { status: "unavailable", reason: phone?.reason ?? "not asked" };
  }
  const quiet = quietHours({
    timeZone, now, start: cfg.quietStart ?? DEFAULTS.quietStart, end: cfg.quietEnd ?? DEFAULTS.quietEnd,
    wokeAt: phone?.ok ? phone.body.phone.woke_at : null, awakeEndsQuiet: cfg.awakeEndsQuiet ?? DEFAULTS.awakeEndsQuiet,
  });
  return {
    v: 1,
    generated_at: now.toISOString(),
    tz: timeZone,
    local: {
      date: here.date, time: here.time, weekday: here.weekdayName,
      school_day: { value: schoolDays.includes(here.weekday), basis: "weekday only: school holidays aren't known until the school is connected" },
    },
    phone: phonePart,
    loops,
    calendar: { status: "not_connected", reason: "Google Calendar comes with M4, through a reader with no network" },
    school: { status: "not_connected", reason: "the site reader isn't set up for the school yet" },
    weather: { status: "not_included", reason: "look it up with web search if it matters" },
    proactive: proactive?.ok === false
      ? { status: "unavailable", reason: proactive.reason }
      : {
        status: "ok", quiet_hours: { start: quiet.start, end: quiet.end, active: quiet.active, set_by_adam: cfg.quietSetByAdam === true },
        pushed_today: todayCounts(proactive.data, timeZone, now).pushed, push_budget: cfg.p2PushPerDay ?? DEFAULTS.p2PushPerDay,
        digest_waiting: proactive.data.digest.length,
      },
  };
}

/**
 * Whether the morning brief should run now (D9 proposal: on "alarm stopped" on a school day, else
 * at 07:30, never after 10:00). The brief automation's condition script asks this every 5 minutes,
 * so the model runs once, when this says yes. The evening wrap-up simply runs at its own time.
 */
export function due({ type, now, timeZone, phone, data, cfg = {}, enabled }) {
  const here = localNow(timeZone, now);
  if (!enabled.includes(type)) return { due: false, reason: `${type} is off` };
  const sentToday = (data.counts[here.date]?.perType?.[type] ?? 0) > 0;
  if (sentToday) return { due: false, reason: "already sent today" };
  if (type === "morning_brief") {
    const fallback = hhmm(cfg.briefFallback ?? "07:30");
    const latest = hhmm(cfg.briefLatest ?? "10:00");
    if (fallback === null || latest === null) return { due: false, reason: "brief times unreadable" };
    if (here.minutes >= latest) return { due: false, reason: `after ${cfg.briefLatest ?? "10:00"}: today's brief was missed` };
    const school = (cfg.schoolDays ?? SCHOOL_DAYS).includes(here.weekday);
    const woke = phone?.ok ? phone.body.phone.woke_at : null;
    if (school && woke && localDate(timeZone, woke) === here.date && Date.parse(woke) <= now.getTime()) {
      return { due: true, reason: `alarm stopped at ${localNow(timeZone, new Date(woke)).time} on a school day` };
    }
    if (here.minutes >= fallback) return { due: true, reason: `${cfg.briefFallback ?? "07:30"}${school ? ", no alarm seen" : ", not a school day"}` };
    return { due: false, reason: phone?.ok ? "waiting for the alarm or the fallback time" : `phone unavailable (${phone?.reason ?? "not asked"}); waiting for the fallback time` };
  }
  return { due: false, reason: "only the morning brief has a condition; the wrap-up runs at its automation's time" };
}

/**
 * C4, phone events: the event kinds that become P2 candidates for enabled types. Arriving home and
 * leaving home before noon point at the open loops due today; nothing else does yet. Each event is
 * looked at once (the cursor moves past it); events older than the freshness limit are skipped.
 */
export function eventCandidates({ events, now, timeZone, loops, enabled, cfg = {} }) {
  const out = [];
  let skipped = 0;
  const fresh = (cfg.freshMinutes ?? DEFAULTS.freshMinutes) * 60000;
  const hasLoops = loops?.status === "ok" && loops.due_today.length + loops.overdue.length > 0;
  for (const ev of events) {
    if (now.getTime() - Date.parse(ev.at) > fresh) { skipped += 1; continue; }
    const base = { class: "P2", facts: { loops }, matters_until: endOfLocalDay(timeZone, now), actionable: true, source_at: ev.at, event: `${ev.kind} ${ev.place ?? ev.focus ?? ""}`.trim() };
    if (ev.kind === "arrive" && ev.place === "home" && enabled.includes("home_loops") && hasLoops) out.push({ type: "home_loops", ...base });
    if (ev.kind === "leave" && ev.place === "home" && enabled.includes("left_home_loops") && hasLoops && localNow(timeZone, new Date(ev.at)).minutes < 12 * 60) {
      out.push({ type: "left_home_loops", ...base });
    }
  }
  return { candidates: out, skipped };
}
