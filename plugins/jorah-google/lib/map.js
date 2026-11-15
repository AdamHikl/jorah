// Turns gog's JSON (v0.48.0) into the fixed fields Jorah gets (packages/contracts/google/). Pure:
// no I/O. Every string is someone else's text, so each is cleaned (links removed, one-time codes
// masked, control characters dropped) and capped. Unknown or missing values become null, never
// zero or an invented value.

const URL_RE = /\b(?:https?:\/\/|www\.|mailto:)[^\s<>"')\]]+/gi;
const CODE_WORDS = /\b(code|kód|kod|otp|pin|passcode|verification|verify|overenie|overovací|2fa|one[- ]time|jednorazov)/i;
const CODE_RE = /\b\d{4,8}\b/g;
const CONTROL = /[\u0000-\u0008\u000b-\u001f\u007f​-‏‪-‮⁦-⁩]/g;

export const EVENT_TYPES = ["default", "birthday", "focus-time", "out-of-office", "working-location", "from-gmail"];
export const RESPONSES = ["accepted", "declined", "tentative", "needsAction"];
export const CATEGORIES = { CATEGORY_PERSONAL: "primary", CATEGORY_SOCIAL: "social", CATEGORY_PROMOTIONS: "promotions", CATEGORY_UPDATES: "updates", CATEGORY_FORUMS: "forums" };

/** Clean one untrusted string: no links, no control characters, one line unless keepLines, capped. */
export function clean(value, max, { keepLines = false } = {}) {
  if (typeof value !== "string") return null;
  let t = value.replace(CONTROL, "").replace(URL_RE, "[link removed]");
  if (CODE_WORDS.test(t)) t = t.replace(CODE_RE, "[code hidden]");
  t = keepLines ? t.replace(/[ \t]+/g, " ").replace(/\n{3,}/g, "\n\n").trim() : t.replace(/\s+/g, " ").trim();
  if (!t) return null;
  const chars = [...t];
  return chars.length > max ? `${chars.slice(0, max - 1).join("")}…` : t;
}

/** "Jana Nová <jana@example.com>" → { name, email }. */
export function splitAddress(raw) {
  if (typeof raw !== "string" || !raw.trim()) return { name: null, email: null };
  const m = raw.match(/^\s*"?([^"<]*?)"?\s*<([^>]+)>\s*$/);
  if (m) return { name: clean(m[1], 60), email: clean(m[2].trim().toLowerCase(), 100) };
  const t = raw.trim();
  return t.includes("@") && !t.includes(" ") ? { name: null, email: clean(t.toLowerCase(), 100) } : { name: clean(t, 60), email: null };
}

function isoOrNull(value) {
  if (typeof value !== "string") return null;
  return Number.isNaN(Date.parse(value)) ? null : value;
}

/** Local date and time pieces of an instant, in a time zone. */
export function localParts(iso, timeZone) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  const f = new Intl.DateTimeFormat("en-GB", { timeZone, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", weekday: "short", hourCycle: "h23" });
  const p = Object.fromEntries(f.formatToParts(d).map((x) => [x.type, x.value]));
  return { date: `${p.year}-${p.month}-${p.day}`, time: `${p.hour}:${p.minute}`, weekday: p.weekday };
}

function eventTime(part, timeZone) {
  if (!part || typeof part !== "object") return { at: null, allDay: false, date: null, time: null, weekday: null };
  if (typeof part.date === "string" && /^\d{4}-\d{2}-\d{2}$/.test(part.date)) {
    const wd = new Intl.DateTimeFormat("en-GB", { timeZone: "UTC", weekday: "short" }).format(new Date(`${part.date}T12:00:00Z`));
    return { at: part.date, allDay: true, date: part.date, time: null, weekday: wd };
  }
  const at = isoOrNull(part.dateTime);
  const lp = at ? localParts(at, timeZone) : null;
  return { at, allDay: false, date: lp?.date ?? null, time: lp?.time ?? null, weekday: lp?.weekday ?? null };
}

/** gog `calendar events --json` → full events. Cancelled events and events without a start are left out. */
export function mapEvents(payload, timeZone, max = 50) {
  const list = Array.isArray(payload) ? payload : Array.isArray(payload?.events) ? payload.events : null;
  if (!list) return null;
  const out = [];
  for (const e of list) {
    if (!e || typeof e !== "object" || e.status === "cancelled") continue;
    const start = eventTime(e.start, timeZone);
    if (!start.at) continue;
    const end = eventTime(e.end, timeZone);
    const attendees = Array.isArray(e.attendees) ? e.attendees.filter((a) => a && typeof a === "object") : [];
    const me = attendees.find((a) => a.self === true);
    out.push({
      title: clean(e.summary, 120) ?? "(no title)",
      start: start.at,
      end: end.at,
      all_day: start.allDay,
      weekday: start.weekday,
      local_date: start.date,
      local_time: start.time,
      local_end_time: end.time,
      location: clean(e.location, 120),
      organizer: e.organizer?.self === true ? "you" : clean(e.organizer?.displayName ?? e.organizer?.email, 80),
      attendees: attendees.length,
      attendee_names: attendees.filter((a) => a.self !== true).slice(0, 10).map((a) => clean(a.displayName ?? a.email, 60)).filter(Boolean),
      my_response: RESPONSES.includes(me?.responseStatus) ? me.responseStatus : null,
      tentative: e.status === "tentative",
      type: EVENT_TYPES.includes(e.eventType) ? e.eventType : "default",
      has_description: typeof e.description === "string" && e.description.trim().length > 0,
    });
    if (out.length >= max) break;
  }
  out.sort((a, b) => String(a.start).localeCompare(String(b.start)));
  return out;
}

/** Counts and times only: what Telegram, Siri and runs Adam didn't start may get. */
export function summariseEvents(events) {
  const timed = events.filter((e) => !e.all_day);
  return {
    count: events.length,
    all_day: events.length - timed.length,
    first_start: timed[0]?.local_time ?? null,
    times: timed.slice(0, 20).map((e) => ({ date: e.local_date, start: e.local_time, end: e.local_end_time })),
  };
}

/** gog `gmail search --json` → threads. */
export function mapThreads(payload, max = 20) {
  const list = Array.isArray(payload) ? payload : Array.isArray(payload?.threads) ? payload.threads : null;
  if (!list) return null;
  const out = [];
  for (const t of list) {
    if (!t || typeof t !== "object" || typeof t.id !== "string" || !/^[A-Za-z0-9_-]{6,64}$/.test(t.id)) continue;
    const labels = Array.isArray(t.labels) ? t.labels.map(String) : [];
    const from = splitAddress(t.from);
    const category = labels.map((l) => CATEGORIES[l]).find(Boolean) ?? (labels.includes("INBOX") ? "primary" : "other");
    out.push({
      id: t.id,
      from_name: from.name,
      from_email: from.email,
      subject: clean(t.subject, 140) ?? "(no subject)",
      received: isoOrNull(t.internalDateIso) ?? null,
      unread: labels.includes("UNREAD"),
      important: labels.includes("IMPORTANT"),
      starred: labels.includes("STARRED"),
      category,
      messages: Number.isInteger(t.messageCount) && t.messageCount > 0 ? Math.min(t.messageCount, 999) : null,
    });
    if (out.length >= max) break;
  }
  return out;
}

export function summariseThreads(threads) {
  return {
    count: threads.length,
    unread: threads.filter((t) => t.unread).length,
    important: threads.filter((t) => t.important).length,
  };
}

function header(headers, name) {
  if (!headers || typeof headers !== "object") return null;
  const key = Object.keys(headers).find((k) => k.toLowerCase() === name);
  return key ? headers[key] : null;
}

/** gog `gmail thread get --sanitize-content --json` → the newest messages, oldest first. */
export function mapThread(payload, keep = 3, textMax = 1500) {
  const thread = payload?.thread ?? payload;
  const list = Array.isArray(thread?.messages) ? thread.messages : null;
  if (!list) return null;
  const messages = list.filter((m) => m && typeof m === "object").slice(-keep).map((m) => {
    const from = splitAddress(header(m.headers, "from"));
    const internal = Number.isFinite(m.internalDate) ? new Date(m.internalDate).toISOString() : null;
    return {
      from_name: from.name,
      from_email: from.email,
      date: internal,
      subject: clean(header(m.headers, "subject"), 140),
      text: clean(typeof m.body === "string" && m.body.trim() ? m.body : m.snippet, textMax, { keepLines: true }),
      attachments: Array.isArray(m.attachments) ? Math.min(m.attachments.length, 99) : 0,
    };
  });
  return { messages_in_thread: list.length, messages };
}

/** gog `contacts search --json` → at most `max` contacts. */
export function mapContacts(payload, max = 5) {
  const list = Array.isArray(payload) ? payload : Array.isArray(payload?.contacts) ? payload.contacts : null;
  if (!list) return null;
  return list.filter((c) => c && typeof c === "object").slice(0, max).map((c) => ({
    name: clean(c.name, 80),
    email: clean(typeof c.email === "string" ? c.email.toLowerCase() : null, 100),
    phone: clean(c.phone, 40),
    birthday: clean(c.birthday, 20),
  }));
}
