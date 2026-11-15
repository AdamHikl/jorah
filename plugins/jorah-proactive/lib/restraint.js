// C3: restraint, in code (docs/plan/01-vision-and-ux.md section 11). Every proactive item comes
// through decide(); nothing here sends. A "push" goes to the outbox, which only the tick job drains
// (proactive_tick, delivered by OpenClaw's announce to Adam's chat); everything else goes to the
// digest or nowhere. Each decision leaves a record that answers "why did you tell me?".
//
// Classes: P0 safety (always, no budget, even in quiet hours); P1 a decision with a deadline
// (pushed unless quiet hours, then the digest); P2 useful now (the five checks and a budget of 5
// pushed and 3 spoken a day, else the digest); P3 digest only; "digest" for the morning brief and
// evening wrap-up themselves. Nothing is spoken yet: no speaking path exists before M10.

import { localDate, localNow, minutesBetween, quietHours } from "./clock.js";
import { lessUrgent } from "./types.js";

export const DEFAULTS = Object.freeze({
  quietStart: "22:30",
  quietEnd: "07:30",
  awakeEndsQuiet: true,
  p2PushPerDay: 5,
  p2SpokenPerDay: 3,
  soonHours: 12,
  freshMinutes: 30,
  busyFocuses: ["sleep", "driving", "do_not_disturb", "work", "school", "fitness", "reading", "other"],
  ignoreAfterHours: 3,
  demoteAfter: 3,
  outboxMinutes: { P0: 60, P1: 60, P2: 20, digest: 60 },
  maxLinesPerMessage: 3,
  keepDays: 30,
});

export const EMPTY = Object.freeze({ v: 1, seq: 1, records: [], outbox: [], digest: [], counts: {}, stopped: {}, demoted: {}, cursor: {}, lastSent: {} });

const CONTROL = /[\u0000-\u001f\u007f-\u009f\u2028\u2029]/u;
const LINK = /\b(?:[a-z][a-z0-9+.-]*:\/\/|www\.)|\b[a-z0-9-]+\.(?:com|org|net|io|sk|cz|eu|ai|dev|app|me|co|info|link|ly|gl|to)\b/i;

/** A line Jorah wrote itself: one line, at most 300 characters, no links or web addresses. */
export function checkLine(text) {
  if (typeof text !== "string" || text.trim().length === 0) return "text is required";
  if (text.length > 300) return "text is longer than 300 characters";
  if (CONTROL.test(text)) return "text must be one line";
  if (LINK.test(text)) return "text may not hold a link or a web address";
  return null;
}

const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

function loopsPhrase(loops, when) {
  if (!loops || loops.status !== "ok") return "open loops unknown";
  const due = when === "tomorrow" ? loops.due_tomorrow ?? 0 : loops.due_today.length;
  const over = loops.overdue.length;
  if (due === 0 && over === 0) return `no open loops due ${when}`;
  return [due ? `${plural(due, "open loop")} due ${when}` : null, over ? `${over} overdue` : null].filter(Boolean).join(", ");
}

/**
 * Lines written by code for the types whose catalogue entry says render "code". Counts and times
 * only (06 section 3.3): never a name, a title or a loop's text, because Telegram isn't end to end.
 */
export function renderLine(type, facts = {}) {
  const digest = facts.digestCount > 0 ? `${plural(facts.digestCount, "digest item")}. ` : "";
  switch (type) {
    case "morning_brief": {
      const woke = facts.wokeAt ? `Woke ${facts.wokeAt}. ` : "";
      return `Morning brief: ${loopsPhrase(facts.loops, "today")}. ${woke}${digest}Detail in the Jorah app.`;
    }
    case "evening_wrap":
      return `Evening wrap: ${loopsPhrase(facts.loops, "tomorrow")}. ${digest}Detail in the Jorah app.`;
    case "home_loops":
      return `Home. ${loopsPhrase(facts.loops, "today")}. They're in the app.`;
    case "left_home_loops":
      return `On your way: ${loopsPhrase(facts.loops, "today")}. They're in the app.`;
    default:
      return null;
  }
}

const dayCounts = (data, day) => (data.counts[day] ??= { pushed: 0, spoken: 0, perType: {} });

/** Pushed items of a type, newest first, and whether Adam reacted to each. */
function streak(data, type, now, cfg) {
  let count = 0;
  const pushed = data.records.filter((r) => r.type === type && r.delivered_at).reverse();
  for (const r of pushed) {
    if (r.outcome === "acted") break;
    if (r.outcome === "dismissed") { count += 1; continue; }
    if (r.outcome === "pending" && minutesBetween(r.delivered_at, now) >= cfg.ignoreAfterHours * 60) { count += 1; continue; }
    if (r.outcome === "pending") break; // still waiting for a reaction: not counted either way
    break;
  }
  return count;
}

function focusFrom(phone) {
  if (!phone?.ok) return { known: false, reason: phone?.reason ?? "phone not asked" };
  return { known: true, value: phone.body.phone.focus.value, woke_at: phone.body.phone.woke_at };
}

/**
 * Decide what happens to one candidate. Mutates `data` (counts, outbox, digest, records) and
 * returns the record. `candidate`: { type, class, text?, facts?, matters_until?, actionable?,
 * source_at?, want? ("push" or "speak") }. `phone`: PhoneClient.today()'s answer, or null.
 */
export function decide({ catalogue, enabled, cfg: rawCfg = {}, data, now, candidate, phone, timeZone }) {
  const cfg = { ...DEFAULTS, ...rawCfg };
  const day = localNow(timeZone, now).date;
  const t = catalogue.get(candidate.type);
  const rec = {
    id: `P${data.seq}`, at: now.toISOString(), type: candidate.type ?? null, asked: candidate.class ?? null, class: null,
    decision: null, reason: null, checks: [], facts: {}, line: null, outcome: null, delivered_at: null,
  };
  data.seq += 1;
  const finish = (decision, reason) => {
    rec.decision = decision;
    rec.reason = reason;
    data.records.push(rec);
    if (data.records.length > 2000) data.records.splice(0, data.records.length - 2000);
    return rec;
  };

  if (!t) return finish("refused", "unknown type");
  if (!["P0", "P1", "P2", "P3", "digest"].includes(candidate.class)) return finish("refused", "class must be P0, P1, P2, P3 or digest");
  rec.class = lessUrgent(candidate.class, t.class);
  if (t.class === "digest") rec.class = "digest";
  if (!enabled.includes(t.name)) return finish("off", `${t.title} is off: Adam hasn't turned it on`);
  if (data.stopped[t.name]) return finish("stopped", `Adam said to stop ${t.title} (${data.stopped[t.name].slice(0, 10)})`);

  // The line: code writes it for code types; Jorah's own text is checked for the rest.
  if (t.render === "code") {
    rec.line = renderLine(t.name, candidate.facts);
    if (!rec.line) return finish("refused", "no code template for this type");
  } else {
    const bad = checkLine(candidate.text);
    if (bad) return finish("refused", bad);
    rec.line = candidate.text.trim();
  }

  if (t.maxPerDay && (dayCounts(data, day).perType[t.name] ?? 0) >= t.maxPerDay) {
    return finish("dropped", `${t.title} went out ${plural(t.maxPerDay, "time")} today already`);
  }

  // Demotion after 3 pushes in a row that were dismissed or got no reaction (P2 only).
  if (rec.class === "P2") {
    if (!data.demoted[t.name] && streak(data, t.name, now, cfg) >= cfg.demoteAfter) {
      data.demoted[t.name] = { at: now.toISOString() };
      data.digest.push({ record: rec.id, at: rec.at, type: t.name, line: `I've moved "${t.title}" to the digest: you didn't react the last ${cfg.demoteAfter} times. Say "keep telling me ${t.title}" to undo.` });
    }
    if (data.demoted[t.name]) {
      rec.class = "P3";
      rec.checks.push({ check: "demoted", pass: false, detail: `moved to the digest on ${data.demoted[t.name].at.slice(0, 10)} after ${cfg.demoteAfter} pushes without a reaction` });
    }
  }

  const focus = focusFrom(phone);
  const quiet = quietHours({ timeZone, now, start: cfg.quietStart, end: cfg.quietEnd, wokeAt: focus.woke_at ?? null, awakeEndsQuiet: cfg.awakeEndsQuiet });
  rec.facts = {
    quiet_hours: `${quiet.start}-${quiet.end}`, quiet_active: quiet.active,
    focus: focus.known ? focus.value : `unknown (${focus.reason})`,
    presence: "not measured: jorah-presence isn't built",
    ...(candidate.source_at ? { source_at: candidate.source_at } : {}),
    ...(candidate.matters_until ? { matters_until: candidate.matters_until } : {}),
    ...(candidate.actionable !== undefined ? { actionable: candidate.actionable } : {}),
    ...(candidate.event ? { event: candidate.event } : {}),
  };
  const counts = dayCounts(data, day);
  const toDigest = (reason) => {
    data.digest.push({ record: rec.id, at: rec.at, type: t.name, line: rec.line });
    return finish("digest", reason);
  };
  const toOutbox = (reason) => {
    const minutes = cfg.outboxMinutes[rec.class] ?? 20;
    data.outbox.push({ record: rec.id, type: t.name, class: rec.class, line: rec.line, deliver_by: new Date(now.getTime() + minutes * 60000).toISOString() });
    counts.perType[t.name] = (counts.perType[t.name] ?? 0) + 1;
    if (rec.class === "P2") counts.pushed += 1;
    return finish("push", reason);
  };
  const speakNote = candidate.want === "speak" ? " Nothing is spoken yet (no speaking path before M10), so it goes as a Telegram line." : "";

  switch (rec.class) {
    case "P0":
      return toOutbox(`P0 safety: always sent.${speakNote}`);
    case "P1":
      rec.checks.push({ check: "quiet hours", pass: !quiet.active, detail: quiet.reason });
      return quiet.active ? toDigest("P1 in quiet hours: held for the morning digest") : toOutbox(`P1: a decision with a deadline.${speakNote}`);
    case "P3":
      return toDigest(rec.checks.some((c) => c.check === "demoted") ? "demoted to the digest" : "P3 goes to the digest");
    case "digest":
      rec.checks.push({ check: "quiet hours", pass: !quiet.active, detail: quiet.reason });
      return quiet.active ? finish("dropped", "quiet hours: the next brief or wrap-up carries it") : toOutbox("a digest Adam turned on");
    default: break;
  }

  // P2: the five checks (01 section 11). Any failure sends it to the digest.
  const mu = Date.parse(candidate.matters_until ?? "");
  const soon = Number.isFinite(mu) && mu > now.getTime() && mu - now.getTime() <= cfg.soonHours * 3600000;
  rec.checks.push({ check: "1 matters in the next few hours", pass: soon, detail: Number.isFinite(mu) ? `matters until ${candidate.matters_until}; the limit is ${cfg.soonHours} h` : "no time given" });
  rec.checks.push({ check: "2 Adam can act on it now", pass: candidate.actionable === true, detail: candidate.actionable === true ? "yes" : "not said to be actionable" });
  const sa = Date.parse(candidate.source_at ?? "");
  const age = Number.isFinite(sa) ? minutesBetween(sa, now) : null;
  const fresh = age !== null && age >= -5 && age <= cfg.freshMinutes;
  rec.checks.push({ check: "3 context is fresh", pass: fresh, detail: age === null ? "no source time given" : `source is ${Math.round(age)} min old; the limit is ${cfg.freshMinutes}` });
  const left = cfg.p2PushPerDay - counts.pushed;
  rec.checks.push({ check: "4 budget left", pass: left > 0, detail: `${counts.pushed} of ${cfg.p2PushPerDay} pushes used today; spoken ${counts.spoken} of ${cfg.p2SpokenPerDay}` });
  const busy = !focus.known || (focus.value !== null && cfg.busyFocuses.includes(focus.value));
  rec.checks.push({
    check: "5 present, not busy, outside quiet hours",
    pass: !busy && !quiet.active,
    detail: [quiet.reason, focus.known ? `Focus ${focus.value ?? "off"}` : `busy unknown: ${focus.reason}`, "presence not measured (no jorah-presence yet)"].join("; "),
  });
  const failed = rec.checks.filter((c) => !c.pass && c.check !== "demoted");
  if (failed.length) return toDigest(`P2 failed: ${failed.map((c) => c.check.replace(/^\d /, "")).join(", ")}`);
  return toOutbox(`P2: all five checks passed.${speakNote}`);
}

/**
 * The tick's half: hand at most a few outbox lines to delivery. Items past their window go to the
 * digest; quiet hours (except P0), "stop" and "off" are checked again because they may have changed
 * since the item was queued. Returns { notify: string|null, sent: [record ids], moved: n }.
 */
export function drain({ data, now, enabled, cfg: rawCfg = {}, timeZone, wokeAt = null }) {
  const cfg = { ...DEFAULTS, ...rawCfg };
  const quiet = quietHours({ timeZone, now, start: cfg.quietStart, end: cfg.quietEnd, wokeAt, awakeEndsQuiet: cfg.awakeEndsQuiet });
  const byId = new Map(data.records.map((r) => [r.id, r]));
  const keep = [];
  const send = [];
  let moved = 0;
  for (const item of data.outbox) {
    const rec = byId.get(item.record);
    const note = (decision, reason) => { if (rec) { rec.decision = decision; rec.reason = `${rec.reason} Then: ${reason}.`; } };
    if (!enabled.includes(item.type) || data.stopped[item.type]) { note("dropped", "turned off or stopped before it went out"); moved += 1; continue; }
    if (Date.parse(item.deliver_by) < now.getTime()) {
      data.digest.push({ record: item.record, at: now.toISOString(), type: item.type, line: item.line });
      note("digest", "not delivered in time, so it went to the digest"); moved += 1; continue;
    }
    if (item.class !== "P0" && quiet.active) {
      if (item.class === "digest") { note("dropped", "quiet hours began first"); moved += 1; continue; }
      data.digest.push({ record: item.record, at: now.toISOString(), type: item.type, line: item.line });
      note("digest", "quiet hours began first"); moved += 1; continue;
    }
    if (send.length < cfg.maxLinesPerMessage) send.push(item); else keep.push(item);
  }
  data.outbox = keep;
  for (const item of send) {
    const rec = byId.get(item.record);
    if (rec) { rec.delivered_at = now.toISOString(); rec.outcome = "pending"; }
    data.lastSent[item.type] = now.toISOString();
  }
  return { notify: send.length ? send.map((i) => i.line).join("\n") : null, sent: send.map((i) => i.record), moved };
}

/** Adam's reaction to an item: "acted" or "dismissed". */
export function react(data, recordId, reaction) {
  const rec = data.records.find((r) => r.id === recordId);
  if (!rec) return { error: `no record ${recordId}` };
  if (!rec.delivered_at) return { error: `${recordId} was never sent` };
  rec.outcome = reaction;
  return { record: rec };
}

export function stop(data, type, now) {
  data.stopped[type] = now.toISOString();
  data.outbox = data.outbox.filter((i) => i.type !== type);
}

export function resume(data, type) {
  const was = { stopped: Boolean(data.stopped[type]), demoted: Boolean(data.demoted[type]) };
  delete data.stopped[type];
  delete data.demoted[type];
  return was;
}

/** Old records, digest lines and day counts go after `keepDays`. */
export function prune(data, now, keepDays = DEFAULTS.keepDays) {
  const cutoff = now.getTime() - keepDays * 86400000;
  data.records = data.records.filter((r) => Date.parse(r.at) >= cutoff);
  data.digest = data.digest.filter((d) => Date.parse(d.at) >= cutoff);
  for (const day of Object.keys(data.counts)) if (Date.parse(`${day}T00:00:00Z`) < cutoff) delete data.counts[day];
}

/** The digest since the last brief or wrap-up, oldest first. */
export const digestItems = (data) => data.digest.map((d) => ({ record: d.record, at: d.at, type: d.type, line: d.line }));

/** What a brief or wrap-up carried: those digest lines are done. */
export function clearDigest(data, upTo) {
  const n = data.digest.length;
  data.digest = data.digest.filter((d) => Date.parse(d.at) > Date.parse(upTo));
  return n - data.digest.length;
}

export function todayCounts(data, timeZone, now) {
  const c = data.counts[localDate(timeZone, now)] ?? { pushed: 0, spoken: 0, perType: {} };
  return { pushed: c.pushed, spoken: c.spoken, per_type: c.perType };
}
