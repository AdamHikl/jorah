// The runner's state (docs/plan/11-project-mode.md sections 3.4 and 4.1), in the formats the
// runner (services/jorah-projects, WS2) reads and writes under /home/jorah/.jorah-projects/:
//   <project>/runs/<run-id>.json, state.json, outbox/<run-id>.json, lock,
//   <project>/inbox/answers.jsonl, inbox/applied.json, inbox/results/<id>.json + results/files/,
//   <project>/requests/<id>.json (+ requests/done/), and the global usage.json and requests.signal.
// The plugin reads all of it and writes only inbox/ and requests/ (and touches requests.signal so
// the runner's path unit starts it within seconds). Each item appears whole: a temp name, then a
// rename; an answer is one appended line under 4 KB.

import { appendFileSync, chmodSync, closeSync, copyFileSync, existsSync, fsyncSync, mkdirSync, openSync, readdirSync, readFileSync, renameSync, statSync, unlinkSync, utimesSync, writeSync } from "node:fs";
import { randomUUID } from "node:crypto";
import { join } from "node:path";

export const OUTCOMES = ["ok", "skipped", "failed", "timeout", "usage-limit", "state-rejected", "secret-found", "error"];
const PROBLEMS = new Set(["failed", "timeout", "state-rejected", "secret-found", "error"]);
const REQUEST_TYPES = ["run-now", "pause", "resume"];
const RUN_LIMIT = 200;
const ISO = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})$/;
const SHA = /^[0-9a-f]{7,64}$/;

export const T_ID = /^T-\d{4}$/;
export const Q_ID = /^Q-\d{4}$/;
export const A_ID = /^A-\d{4}$/;

export const isProblem = (outcome) => PROBLEMS.has(outcome);
const iso = (v) => (typeof v === "string" && ISO.test(v) && !Number.isNaN(Date.parse(v)) ? v : null);
const ids = (v, re) => (Array.isArray(v) ? v.filter((x) => typeof x === "string" && re.test(x)) : []);
const num = (v) => (typeof v === "number" && Number.isFinite(v) ? v : null);

export class RunnerError extends Error {}

export const projectDir = (root, name) => join(root, name);

function readJson(file) {
  try {
    return { ok: true, value: JSON.parse(readFileSync(file, "utf8")) };
  } catch (e) {
    return { ok: false, missing: e?.code === "ENOENT" };
  }
}

/**
 * A run record reduced to what the plugin shows. Code-shaped fields are checked (outcome against
 * the known list, ids against their pattern, times as ISO); free text (reason, commit messages) is
 * kept for the digest only.
 */
export function normaliseRun(raw, file) {
  if (!raw || typeof raw !== "object") return null;
  const outcome = typeof raw.outcome === "string" && OUTCOMES.includes(raw.outcome) ? raw.outcome : "unknown";
  const commits = Array.isArray(raw.commits) ? raw.commits.filter((c) => c && typeof c.sha === "string" && SHA.test(c.sha)).map((c) => ({
    sha: c.sha.slice(0, 12),
    message: typeof c.message === "string" ? c.message : "",
    files: Array.isArray(c.files) ? c.files.filter((f) => typeof f === "string").length : null,
  })) : [];
  const changed = Array.isArray(raw.backlog?.changed) ? raw.backlog.changed.filter((c) => c && typeof c.id === "string" && T_ID.test(c.id)).map((c) => ({
    id: c.id, from: typeof c.from === "string" ? c.from : null, to: typeof c.to === "string" ? c.to : null,
  })) : [];
  return {
    id: typeof raw.id === "string" ? raw.id.slice(0, 80) : file.replace(/\.json$/, ""),
    started_at: iso(raw.startedAt),
    ended_at: iso(raw.endedAt),
    trigger: typeof raw.trigger === "string" && /^[a-z-]{1,20}$/.test(raw.trigger) ? raw.trigger : null,
    outcome,
    reason: typeof raw.reason === "string" ? raw.reason : null,
    commits,
    backlog_added: ids(raw.backlog?.added, T_ID),
    backlog_changes: changed,
    new_questions: ids(raw.questions?.new, Q_ID),
    new_adam_tasks: ids(raw.adamTasks?.new, A_ID),
    intake: {
      answers: ids(raw.intake?.answers, Q_ID),
      results: ids(raw.intake?.results, A_ID),
      defaults: ids(raw.intake?.defaults, Q_ID),
      refused: Array.isArray(raw.intake?.refused) ? raw.intake.refused.length : 0,
    },
    reverted: Array.isArray(raw.reverted) ? raw.reverted.length : 0,
    secret_findings: Array.isArray(raw.gitleaks?.findings) ? raw.gitleaks.findings.length : 0,
    usage: raw.usage && typeof raw.usage === "object" ? { limited: raw.usage.limited === true, resets_at: iso(raw.usage.resetsAt) } : null,
  };
}

/**
 * Newest run records first. { ok, runs, broken } or { ok: false, reason }. A missing runs/ folder
 * is "no run records yet" (or "no runner state" when the project's folder is missing too): the
 * caller says so, never "0 runs".
 */
export function readRuns(dir, limit = RUN_LIMIT) {
  const runsDir = join(dir, "runs");
  let names;
  try {
    names = readdirSync(runsDir).filter((n) => n.endsWith(".json") && !n.startsWith(".")).sort().reverse().slice(0, limit);
  } catch (e) {
    if (e?.code === "ENOENT") return { ok: false, reason: existsSync(dir) ? "no run records yet" : "the runner has no state for this project yet" };
    return { ok: false, reason: "the run records can't be read" };
  }
  const runs = [];
  let broken = 0;
  for (const n of names) {
    const j = readJson(join(runsDir, n));
    const r = j.ok ? normaliseRun(j.value, n) : null;
    if (r) runs.push(r);
    else broken++;
  }
  runs.sort((a, b) => (b.started_at ?? "").localeCompare(a.started_at ?? ""));
  return { ok: true, runs, broken };
}

/** The runner's own state for a project: its pause (e.g. after a secret was found) and push block. */
export function readState(dir) {
  const j = readJson(join(dir, "state.json"));
  if (!j.ok) return j.missing ? { ok: true, paused: false, pausedReason: null, pushBlocked: false, pushBlockedReason: null, missing: true } : { ok: false, reason: "the runner's state.json can't be read" };
  const s = j.value ?? {};
  return {
    ok: true,
    paused: s.paused === true,
    pausedReason: typeof s.pausedReason === "string" ? s.pausedReason : null,
    pausedAt: iso(s.pausedAt),
    pushBlocked: s.pushBlocked === true,
    pushBlockedReason: typeof s.pushBlockedReason === "string" ? s.pushBlockedReason : null,
  };
}

/** The runner's global usage backoff (all projects). */
export function readUsage(root) {
  const j = readJson(join(root, "usage.json"));
  if (!j.ok) return j.missing ? { ok: false, reason: "no usage record yet" } : { ok: false, reason: "usage.json can't be read" };
  const u = j.value ?? {};
  const window = (w) => (w && typeof w === "object" ? { utilization: num(w.utilization), resets_at: iso(w.resetsAt) } : null);
  return {
    ok: true,
    backoff_until: iso(u.backoffUntil),
    skipped: Number.isInteger(u.skipped) ? u.skipped : null,
    seen_at: iso(u.lastSeen?.at),
    five_hour: window(u.lastSeen?.fiveHour),
    seven_day: window(u.lastSeen?.sevenDay),
  };
}

/** Is a run holding the lock? { held, since } or { held: null } when it can't be told. */
export function readLock(dir) {
  try {
    const st = statSync(join(dir, "lock"));
    return { held: true, since: st.mtime.toISOString() };
  } catch (e) {
    return e?.code === "ENOENT" ? { held: false } : { held: null };
  }
}

/** Requests the runner hasn't taken yet (taken ones move to requests/done/). */
export function readRequests(dir) {
  const rq = join(dir, "requests");
  let names;
  try {
    names = readdirSync(rq).filter((n) => n.endsWith(".json") && !n.startsWith("."));
  } catch (e) {
    return e?.code === "ENOENT" ? { ok: true, pending: [] } : { ok: false, reason: "the request folder can't be read" };
  }
  const pending = [];
  for (const n of names) {
    const j = readJson(join(rq, n));
    if (j.ok && REQUEST_TYPES.includes(j.value?.type) && iso(j.value.at)) pending.push({ type: j.value.type, at: j.value.at });
  }
  pending.sort((a, b) => a.at.localeCompare(b.at));
  return { ok: true, pending };
}

/** Answers and results waiting for the runner's next run (answers it hasn't marked applied). */
export function readInbox(dir) {
  const out = { answers: 0, results: 0 };
  const applied = readJson(join(dir, "inbox", "applied.json"));
  const done = new Set(applied.ok && Array.isArray(applied.value?.answers) ? applied.value.answers : []);
  try {
    const lines = readFileSync(join(dir, "inbox", "answers.jsonl"), "utf8").split("\n").filter((l) => l.trim());
    out.answers = lines.filter((l) => { try { return !done.has(JSON.parse(l).id); } catch { return false; } }).length;
  } catch (e) {
    if (e?.code !== "ENOENT") out.answers = null;
  }
  if (!applied.ok && !applied.missing) out.answers = null;
  try {
    out.results = readdirSync(join(dir, "inbox", "results")).filter((n) => n.endsWith(".json") && !n.startsWith(".")).length;
  } catch (e) {
    if (e?.code !== "ENOENT") out.results = null;
  }
  return out;
}

/** Outbox items, one per run: the runner's problems and urgent items. Read only, never deleted here. */
export function readOutbox(dir) {
  let names;
  try {
    names = readdirSync(join(dir, "outbox")).filter((n) => n.endsWith(".json") && !n.startsWith(".")).sort();
  } catch (e) {
    return e?.code === "ENOENT" ? { ok: true, items: [] } : { ok: false, reason: "the outbox can't be read" };
  }
  const items = [];
  for (const n of names.slice(-200)) {
    const j = readJson(join(dir, "outbox", n));
    const r = j.ok ? j.value : null;
    const at = iso(r?.at);
    if (!at) continue;
    items.push({
      at,
      run: typeof r.run === "string" ? r.run.slice(0, 80) : null,
      problems: Array.isArray(r.problems) ? r.problems.filter((p) => typeof p === "string") : [],
      urgent: Array.isArray(r.urgent) ? r.urgent.filter((u) => u && typeof u.text === "string").map((u) => ({
        kind: typeof u.kind === "string" ? u.kind.slice(0, 30) : "urgent", id: typeof u.id === "string" ? u.id.slice(0, 10) : null, text: u.text,
      })) : [],
    });
  }
  return { ok: true, items };
}

/** Is Jorah frozen? Reads jorah-guard's FROZEN file; an unreadable folder counts as frozen. */
export function frozen(guardStateDir) {
  try {
    return existsSync(join(guardStateDir, "FROZEN"));
  } catch {
    return true;
  }
}

// ---- writes: inbox/ and requests/ only ----

export const newId = () => randomUUID();

function ensure(dir) {
  mkdirSync(dir, { recursive: true, mode: 0o700 });
  return dir;
}

function writeWhole(dir, name, text) {
  const tmp = join(dir, `.tmp-${name}`);
  const fd = openSync(tmp, "wx", 0o600);
  try {
    writeSync(fd, text);
    fsyncSync(fd);
  } finally {
    closeSync(fd);
  }
  renameSync(tmp, join(dir, name));
}

/** Append one answer line to inbox/answers.jsonl (one write, under 4 KB, so it lands whole). */
export function writeAnswer(dir, record) {
  const line = `${JSON.stringify(record)}\n`;
  if (Buffer.byteLength(line) > 4000) throw new RunnerError("the answer is too long");
  appendFileSync(join(ensure(join(dir, "inbox")), "answers.jsonl"), line, { mode: 0o600 });
}

/**
 * A result: its files first, into inbox/results/files/<id>-<n>.<ext> (each renamed into place),
 * then inbox/results/<id>.json naming them. The runner reads only the .json, so it never sees a
 * result whose files aren't all there.
 */
export function writeResult(dir, record, files) {
  const results = ensure(join(dir, "inbox", "results"));
  const store = ensure(join(results, "files"));
  const names = [];
  try {
    files.forEach((f, i) => {
      const name = `${record.id}-${i + 1}.${f.ext}`;
      const tmp = join(store, `.tmp-${name}`);
      copyFileSync(f.path, tmp);
      chmodSync(tmp, 0o600);
      renameSync(tmp, join(store, name));
      names.push(name);
    });
    writeWhole(results, `${record.id}.json`, `${JSON.stringify({ ...record, files: names })}\n`);
    return names;
  } catch (e) {
    for (const n of names) { try { unlinkSync(join(store, n)); } catch { /* gone */ } }
    throw e;
  }
}

/** A request for the runner: requests/<id>.json, then a touch of the runner's signal file. */
export function writeRequest(root, dir, record) {
  writeWhole(ensure(join(dir, "requests")), `${record.id}.json`, `${JSON.stringify(record)}\n`);
  const signal = join(root, "requests.signal");
  try {
    const t = new Date();
    try { utimesSync(signal, t, t); } catch { closeSync(openSync(signal, "a", 0o600)); }
    return true;
  } catch {
    return false; // the request still runs at the runner's next 15-minute tick
  }
}
