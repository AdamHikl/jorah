// What the site reader may hand back to Jorah (docs/runbooks/site-readers.md). The reader saw raw
// page text, which other people wrote, so its answer is untrusted: only fixed fields of fixed kinds
// pass, links are removed, people's names are hidden, lengths are capped. Anything that isn't the
// expected shape becomes "not available"; there is no fallback to free text.

import { KINDS } from "../../jorah-guard/lib/sites.js";

// Field types: "date" YYYY-MM-DD, "time" HH:MM, "sN" a string of at most N characters, "bool".
// A trailing "?" makes a field optional.
export const FIELDS = {
  event: { date: "date", start: "time?", end: "time?", title: "s120", place: "s60?", change: "s120?" },
  grade: { date: "date?", subject: "s60", value: "s20", note: "s120?" },
  notice: { date: "date?", from: "s60?", title: "s120?", text: "s300" },
  task: { due: "date?", subject: "s60?", text: "s300", done: "bool?" },
  item: { date: "date?", title: "s120", text: "s300?", status: "s40?", amount: "s40?" },
};
const MAX_ITEMS = 60;
const STATUSES = new Set(["ok", "signed_out", "unavailable"]);
const ENVELOPE = new Set(["site", "status", "reason", "items", "contains_instructions", "pages_read"]);

const LINK_RES = [
  /\[([^\]]{0,200})\]\([^)]{0,500}\)/g, // markdown link: keep the label
  /\b(?:https?|ftp|file|data|javascript|mailto|tel):[^\s"'<>)]*/gi,
  /\bwww\.[^\s"'<>)]+/gi,
  /\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|org|net|sk|cz|eu|io|ai|app|dev|me|info|biz|ru|cn|tk|xyz|site|online|link)(?:\/[^\s"'<>)]*)?/gi,
];
const EMAIL = /\b[^\s@<>]+@[^\s@<>]+\.[a-z]{2,}\b/gi;
// Nine or more digits, optionally with + and spaces or dashes; dates (8 digits) don't match.
const PHONE = /(?<![\d-])(?:\+\d{1,3}[ -]?)?(?:\d[ -]?){8,13}\d(?![\d-])/g;
// Two to four capitalised words in a row, as people's names are written: "Ján Novák", "Mária Kováčová-Horná".
const NAME = /\p{Lu}[\p{Ll}'’]+(?:[ -]\p{Lu}[\p{Ll}'’]+){1,3}/gu;

export function stripLinks(s) {
  let out = String(s);
  out = out.replace(LINK_RES[0], "$1");
  for (const re of LINK_RES.slice(1)) out = out.replace(re, "[link removed]");
  return out.replace(EMAIL, "[address removed]").replace(PHONE, "[number removed]");
}

export function hideNames(s, keep = []) {
  const keepSet = new Set(keep.map((k) => k.toLowerCase()));
  return String(s).replace(NAME, (m) => (keepSet.has(m.toLowerCase()) ? m : "[name]"));
}

function clean(value, max, site) {
  if (typeof value !== "string") return null;
  let s = value.replace(/[\u0000-\u001f\u007f​-‏‪-‮⁦-⁩]/g, " ").replace(/\s+/g, " ").trim();
  s = stripLinks(s);
  if (site.redactNames) s = hideNames(s, site.keepNames ?? []);
  if (s.length === 0) return null;
  return s.length > max ? `${s.slice(0, max - 1)}…` : s;
}

function realDate(s) {
  if (typeof s !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(s)) return false;
  const d = new Date(`${s}T00:00:00Z`);
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === s;
}

function field(type, value, site) {
  const optional = type.endsWith("?");
  const t = optional ? type.slice(0, -1) : type;
  if (value === undefined || value === null || value === "") return optional ? { skip: true } : { bad: true };
  if (t === "date") return realDate(value) ? { value } : { bad: true };
  if (t === "time") return typeof value === "string" && /^([01]\d|2[0-3]):[0-5]\d$/.test(value) ? { value } : { bad: true };
  if (t === "bool") return typeof value === "boolean" ? { value } : { bad: true };
  const max = Number(t.slice(1));
  const s = clean(value, max, site);
  return s === null ? (optional ? { skip: true } : { bad: true }) : { value: s };
}

export function checkItem(raw, site) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const kind = raw.kind;
  if (!KINDS.includes(kind) || !site.kinds.includes(kind)) return null;
  const spec = FIELDS[kind];
  for (const k of Object.keys(raw)) if (k !== "kind" && !(k in spec)) return null;
  const out = { kind };
  for (const [k, type] of Object.entries(spec)) {
    const r = field(type, raw[k], site);
    if (r.bad) return null;
    if (!r.skip) out[k] = r.value;
  }
  return out;
}

// The reader's final message must be one JSON object, optionally in a single ```json fence.
export function parseReply(text) {
  if (typeof text !== "string") return null;
  let t = text.trim();
  const fence = /^```(?:json)?\s*\n([\s\S]*?)\n```$/.exec(t);
  if (fence) t = fence[1].trim();
  if (!t.startsWith("{") || !t.endsWith("}")) return null;
  try { return JSON.parse(t); } catch { return null; }
}

const unavailable = (site, reason) => ({ site: site?.name ?? "?", status: "unavailable", reason, items: [] });

/** Check the reader's reply for one site. Always returns a result Jorah can show. */
export function checkReply(text, site, { asked = [] } = {}) {
  const raw = parseReply(text);
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return unavailable(site, "the reader's answer wasn't in the expected form");
  for (const k of Object.keys(raw)) if (!ENVELOPE.has(k)) return unavailable(site, "the reader's answer had unexpected fields");
  if (raw.site !== site.name) return unavailable(site, "the reader answered for a different site");
  if (!STATUSES.has(raw.status)) return unavailable(site, "the reader's answer had no valid status");
  if (raw.status === "signed_out") return { site: site.name, status: "signed_out", reason: `Signed out of ${site.title}: Adam needs to sign in again.`, items: [] };
  if (raw.status === "unavailable") return unavailable(site, clean(raw.reason ?? "", 120, site) ?? "the reader couldn't read the site");
  if (!Array.isArray(raw.items)) return unavailable(site, "the reader's answer had no items list");
  const items = [];
  let dropped = 0;
  for (const it of raw.items.slice(0, MAX_ITEMS)) {
    const ok = checkItem(it, site);
    if (ok) items.push(ok); else dropped++;
  }
  dropped += Math.max(0, raw.items.length - MAX_ITEMS);
  const pagesRead = Array.isArray(raw.pages_read) ? raw.pages_read.filter((p) => site.pages.some((x) => x.id === p)) : [];
  const out = { site: site.name, status: "ok", items, pages_read: pagesRead };
  if (dropped) out.dropped = dropped;
  if (raw.contains_instructions === true) out.contains_instructions = true;
  const missing = asked.filter((p) => !pagesRead.includes(p));
  if (missing.length) out.not_read = missing;
  return out;
}
