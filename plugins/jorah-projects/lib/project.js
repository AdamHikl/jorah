// The project folder in the project's repo (contract jorah-project-v1, docs/plan/11-project-mode.md
// section 3): backlog.yaml, questions.yaml, adam-tasks.yaml, DECISIONS.md and log/. Runs write it,
// and runs read the web, so its text is outside text. Each file comes back as
// { status: "ok", ... } or { status: "missing" | "unreadable", reason }: a file that can't be read
// is unknown, never empty. Code-shaped values (ids, statuses, dates) are checked here; free text is
// kept only for the digest, cut to a length and stripped of control characters.

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { parseYaml } from "./yaml.js";
import { A_ID, Q_ID, T_ID } from "./runner.js";

export const BACKLOG_STATUS = ["ready", "doing", "blocked", "done", "dropped"];
export const QUESTION_STATUS = ["open", "answered", "defaulted", "withdrawn"];
export const TASK_STATUS = ["open", "done", "skipped"];
export const TRACKS = ["eng", "biz", "research", "ops", "adam"];
const MAX_BYTES = 2 * 1024 * 1024;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const KEY = /^[A-Za-z0-9]{1,8}$/;

/** Outside text for the digest: no control characters, one length limit. */
export function clean(v, n = 300) {
  if (v === null || v === undefined) return null;
  const s = String(typeof v === "object" ? JSON.stringify(v) : v).replace(/[\u0000-\u0008\u000b-\u001f\u007f-\u009f\u2028\u2029]/gu, " ").replace(/[ \t]+/g, " ").trim();
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}
const date = (v) => (typeof v === "string" && DATE.test(v) ? v : typeof v === "string" && /^\d{4}-\d{2}-\d{2}T/.test(v) ? v.slice(0, 10) : null);
const list = (v, n, each = 200) => (Array.isArray(v) ? v.slice(0, n).map((x) => clean(x, each)).filter(Boolean) : []);

function readYaml(file) {
  let text;
  try {
    if (statSync(file).size > MAX_BYTES) return { status: "unreadable", reason: "file is over 2 MB" };
    text = readFileSync(file, "utf8");
  } catch (e) {
    return e?.code === "ENOENT" ? { status: "missing", reason: "file doesn't exist" } : { status: "unreadable", reason: "file can't be read" };
  }
  try {
    return { status: "ok", data: parseYaml(text) };
  } catch (e) {
    return { status: "unreadable", reason: `not readable as YAML (${clean(e.message, 80)})` };
  }
}

// Reads one list file and keeps entries whose id fits; others are counted as malformed.
function readList(file, key, idRe, normalise) {
  const r = readYaml(file);
  if (r.status !== "ok") return r;
  const arr = r.data?.[key];
  if (!r.data || typeof r.data !== "object" || !Array.isArray(arr)) return { status: "unreadable", reason: `no ${key} list` };
  const entries = [];
  let malformed = 0;
  const seen = new Set();
  for (const raw of arr) {
    if (!raw || typeof raw !== "object" || typeof raw.id !== "string" || !idRe.test(raw.id) || seen.has(raw.id)) { malformed++; continue; }
    seen.add(raw.id);
    entries.push(normalise(raw));
  }
  return { status: "ok", entries, malformed, version: r.data.version ?? null };
}

export function readBacklog(dir) {
  return readList(join(dir, "backlog.yaml"), "items", T_ID, (x) => ({
    id: x.id,
    status: BACKLOG_STATUS.includes(x.status) ? x.status : "other",
    track: TRACKS.includes(x.track) ? x.track : null,
    priority: Number.isInteger(x.priority) && x.priority >= 1 && x.priority <= 5 ? x.priority : null,
    blocked_on: typeof x.blocked_on === "string" && (Q_ID.test(x.blocked_on) || A_ID.test(x.blocked_on) || T_ID.test(x.blocked_on)) ? x.blocked_on : null,
    updated: date(x.updated),
    // Outside text, for the digest only.
    title: clean(x.title, 160),
    acceptance: clean(x.acceptance, 300),
    evidence: list(x.evidence, 8),
  }));
}

export function readQuestions(dir) {
  return readList(join(dir, "questions.yaml"), "questions", Q_ID, (x) => {
    const options = Array.isArray(x.options) ? x.options.filter((o) => o && typeof o === "object" && typeof o.key === "string" && KEY.test(o.key)).slice(0, 8) : [];
    const keys = options.map((o) => o.key);
    const keyOrNull = (v) => (typeof v === "string" && keys.includes(v) ? v : null);
    return {
      id: x.id,
      status: QUESTION_STATUS.includes(x.status) ? x.status : "other",
      asked: date(x.asked),
      decide_by: date(x.decide_by),
      recommendation: keyOrNull(x.recommendation),
      default_if_silent: keyOrNull(x.default_if_silent),
      keys,
      // Outside text, for the digest only.
      question: clean(x.question, 300),
      why_it_matters: clean(x.why_it_matters, 300),
      options: options.map((o) => ({ key: o.key, text: clean(o.text, 160), consequence: clean(o.consequence, 200) })),
    };
  });
}

export function readAdamTasks(dir) {
  return readList(join(dir, "adam-tasks.yaml"), "tasks", A_ID, (x) => ({
    id: x.id,
    status: TASK_STATUS.includes(x.status) ? x.status : "other",
    // Outside text, for the digest only.
    title: clean(x.title, 160),
    why: clean(x.why, 300),
    when: clean(x.when, 120),
    steps: list(x.steps, 12),
    materials: list(x.materials, 12, 120),
    send_back: clean(x.send_back, 300),
  }));
}

/** Counts by status. The status tool shows only these and ids, never the text. */
export function counts(entries, statuses) {
  const out = Object.fromEntries([...statuses, "other"].map((s) => [s, 0]));
  for (const e of entries) out[e.status] = (out[e.status] ?? 0) + 1;
  if (out.other === 0) delete out.other;
  return out;
}

const HEADING = /^#{1,4}\s+(.*)$/;

/**
 * DECISIONS.md sections whose heading carries a date on or after `sinceDate` (the weekly review).
 * The contract's template puts the date in each heading; a section without one isn't listed.
 */
export function readDecisions(dir, sinceDate, maxChars = 2500) {
  let text;
  try {
    text = readFileSync(join(dir, "DECISIONS.md"), "utf8");
  } catch (e) {
    return e?.code === "ENOENT" ? { status: "missing", reason: "file doesn't exist" } : { status: "unreadable", reason: "file can't be read" };
  }
  const out = [];
  let cur = null;
  for (const line of text.split(/\r?\n/)) {
    const h = HEADING.exec(line);
    if (h) {
      const d = /(\d{4}-\d{2}-\d{2})/.exec(h[1]);
      cur = d && d[1] >= sinceDate ? { date: d[1], heading: clean(h[1], 160), body: [] } : null;
      if (cur) out.push(cur);
      continue;
    }
    if (cur && line.trim()) cur.body.push(line.trim());
  }
  let budget = maxChars;
  const sections = [];
  for (const s of out) {
    if (budget <= 0) break;
    const body = clean(s.body.join(" "), Math.min(600, budget));
    budget -= body?.length ?? 0;
    sections.push({ date: s.date, heading: s.heading, text: body });
  }
  return { status: "ok", sections };
}

/** The tail of each daily log from sinceDate on, newest first, within a character budget. */
export function readLogs(dir, sinceDate, maxChars = 3000) {
  let names;
  try {
    names = readdirSync(join(dir, "log")).filter((n) => /^\d{4}-\d{2}-\d{2}\.md$/.test(n) && n.slice(0, 10) >= sinceDate).sort().reverse();
  } catch (e) {
    return e?.code === "ENOENT" ? { status: "missing", reason: "no log folder" } : { status: "unreadable", reason: "log folder can't be read" };
  }
  let budget = maxChars;
  const days = [];
  for (const n of names) {
    if (budget <= 0) break;
    try {
      const t = readFileSync(join(dir, "log", n), "utf8");
      const take = Math.min(1500, budget);
      const tail = t.length > take ? `…${t.slice(-take)}` : t;
      budget -= tail.length;
      days.push({ date: n.slice(0, 10), text: clean(tail.replace(/\s*\n\s*/g, " / "), take + 1) });
    } catch {
      days.push({ date: n.slice(0, 10), text: null, problem: "can't be read" });
    }
  }
  return { status: "ok", days };
}

/** Everything in the project folder at once. */
export function readProject(entry) {
  const dir = join(entry.workDir, entry.stateDir);
  return { dir, backlog: readBacklog(dir), questions: readQuestions(dir), tasks: readAdamTasks(dir) };
}

/** Whether the project folder has its charter: true, false, or null when that can't be told. */
export function charterExists(dir) {
  try {
    return statSync(join(dir, "CHARTER.md")).isFile();
  } catch (e) {
    return e?.code === "ENOENT" || e?.code === "ENOTDIR" ? false : null;
  }
}

/**
 * The charter's text for Adam to read (the setup run drafts it, then it is Adam's): Markdown kept
 * line by line, control characters removed, cut at maxChars.
 */
export function readCharter(dir, maxChars = 6000) {
  let text;
  try {
    if (statSync(join(dir, "CHARTER.md")).size > MAX_BYTES) return { status: "unreadable", reason: "file is too big" };
    text = readFileSync(join(dir, "CHARTER.md"), "utf8");
  } catch (e) {
    return e?.code === "ENOENT" || e?.code === "ENOTDIR" ? { status: "missing", reason: "no charter yet" } : { status: "unreadable", reason: "file can't be read" };
  }
  const lines = text.split(/\r?\n/).map((l) => l.replace(/[\u0000-\u0008\u000b-\u001f\u007f-\u009f\u2028\u2029]/gu, " ").trimEnd());
  const body = lines.join("\n").replace(/\n{3,}/g, "\n\n").trim();
  return body.length > maxChars ? { status: "ok", text: `${body.slice(0, maxChars - 1)}…`, truncated: true } : { status: "ok", text: body };
}
