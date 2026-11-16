// The project registry (docs/plan/11-project-mode.md section 3.4):
// /home/jorah/.config/jorah-projects/projects.json, mode 600, one entry per project. The plugin
// reads it whole. It writes a new level-0 entry (project_start), and in one existing entry only
// `limits` (project_set_limits), `repo` of a local-only project (project_connect) and `level` with
// `schedule` (project_set_level). Every write re-reads the file and keeps everything else as it was.

import { chmodSync, closeSync, fsyncSync, openSync, readFileSync, renameSync, unlinkSync, writeSync } from "node:fs";
import { randomBytes } from "node:crypto";
import { basename, dirname, isAbsolute, join, posix } from "node:path";

// Names and branch as project-config.schema.json (packages/contracts/project) has them.
export const NAME = /^[a-z0-9][a-z0-9-]{0,62}$/;
export const DEFAULT_LIMITS = Object.freeze({ runsPerDay: 3, minutesPerRun: 45, maxTurns: 200 });
// What project_set_limits accepts. Wider needs a commit here and Adam's yes.
export const LIMIT_RANGES = Object.freeze({ runsPerDay: [1, 6], minutesPerRun: [10, 120], maxTurns: [20, 400] });
// owner/name on GitHub, as project-config.schema.json has it; a name of only dots is refused here.
export const REPO = /^[A-Za-z0-9-]{1,39}\/(?!\.)[A-Za-z0-9._-]{1,100}$/;
export const SCHEDULE_MAX = 8;
const BRANCH = /^jorah\/(?!.*\.\.)(?!.*\/\/)[A-Za-z0-9._/-]{1,95}$/;
const SLOT = /^([01]\d|2[0-3]):[0-5]\d$/;

export class RegistryError extends Error {}

const int = (v) => (Number.isInteger(v) ? v : null);

/** One registry entry, with the plan's defaults filled in and anything unsafe refused. */
export function normaliseEntry(name, raw, workRoot = "/home/jorah/work") {
  if (!NAME.test(name)) throw new RegistryError(`project name ${JSON.stringify(name).slice(0, 40)} isn't allowed`);
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) throw new RegistryError(`${name}: entry isn't an object`);
  const workDir = raw.workDir ?? join(workRoot, name);
  if (typeof workDir !== "string" || !isAbsolute(workDir) || posix.normalize(workDir) !== workDir) throw new RegistryError(`${name}: workDir must be a plain absolute path`);
  const stateDir = raw.stateDir ?? "project";
  if (typeof stateDir !== "string" || isAbsolute(stateDir) || stateDir.split("/").some((p) => p === ".." || p === "") || stateDir.length > 100) {
    throw new RegistryError(`${name}: stateDir must be a relative path inside the repo`);
  }
  const branch = raw.branch ?? "jorah/line";
  if (typeof branch !== "string" || !BRANCH.test(branch)) throw new RegistryError(`${name}: branch must be a jorah/ branch`);
  const limits = { ...DEFAULT_LIMITS };
  for (const k of Object.keys(DEFAULT_LIMITS)) if (int(raw.limits?.[k]) !== null) limits[k] = raw.limits[k];
  const schedule = Array.isArray(raw.schedule) ? raw.schedule.filter((s) => typeof s === "string" && SLOT.test(s)) : [];
  return {
    name,
    repo: typeof raw.repo === "string" ? raw.repo : null,
    local_only: raw.repo === null,
    title: typeof raw.title === "string" && raw.title.trim() ? raw.title.trim().slice(0, 60) : null,
    workDir,
    branch,
    stateDir,
    level: int(raw.level) !== null && raw.level >= 0 && raw.level <= 2 ? raw.level : null,
    schedule,
    limits,
    web: raw.web === true,
    bench: typeof raw.bench === "string" ? raw.bench : null,
    paused: raw.paused === true,
  };
}

/**
 * The whole registry. { ok: true, projects: Map } or { ok: false, reason } (missing, unreadable or
 * broken: the caller says unknown, never "no projects"). A bad entry is reported, not dropped silently.
 */
export function readRegistry(file, workRoot) {
  let raw;
  try {
    raw = JSON.parse(readFileSync(file, "utf8"));
  } catch (e) {
    if (e?.code === "ENOENT") return { ok: false, reason: "the project registry doesn't exist yet (the runner isn't installed)" };
    return { ok: false, reason: e instanceof SyntaxError ? "the project registry isn't valid JSON" : "the project registry can't be read" };
  }
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return { ok: false, reason: "the project registry isn't an object" };
  const projects = new Map();
  const broken = [];
  for (const [name, entry] of Object.entries(raw)) {
    try {
      projects.set(name, normaliseEntry(name, entry, workRoot));
    } catch (e) {
      broken.push(e.message);
    }
  }
  return { ok: true, projects, broken };
}

/**
 * Find a project by its exact name. A unique part of a name ("robot") is refused with the full
 * name, so every card, record and guard mark carries the same name (the guard's cross-repo push
 * rule compares names).
 */
export function resolveProject(reg, wanted) {
  if (!reg.ok) throw new RegistryError(reg.reason);
  const w = String(wanted ?? "").trim().toLowerCase();
  if (!w) throw new RegistryError("which project? Name it");
  if (reg.projects.has(w)) return reg.projects.get(w);
  const hits = [...reg.projects.keys()].filter((n) => n.includes(w.replace(/\s+/g, "-")));
  if (hits.length === 1) throw new RegistryError(`use the project's full name: ${hits[0]}`);
  const names = [...reg.projects.keys()].join(", ") || "none";
  throw new RegistryError(hits.length > 1 ? `"${w}" fits more than one project: ${hits.join(", ")}` : `no project called "${w}". Projects: ${names}`);
}

/** Write a file atomically with mode 600: a temp file in the same folder, fsync, rename. */
export function writeAtomic(file, text) {
  const tmp = join(dirname(file), `.${basename(file)}.${randomBytes(4).toString("hex")}.tmp`);
  const fd = openSync(tmp, "wx", 0o600);
  try {
    writeSync(fd, text);
    fsyncSync(fd);
  } finally {
    closeSync(fd);
  }
  try {
    chmodSync(tmp, 0o600);
    renameSync(tmp, file);
  } catch (e) {
    try { unlinkSync(tmp); } catch { /* already gone */ }
    throw e;
  }
}

/** Check the requested limits. Returns { changes } or throws with what is wrong. */
export function checkLimits(params = {}) {
  const changes = {};
  for (const [k, [lo, hi]] of Object.entries(LIMIT_RANGES)) {
    if (params[k] === undefined || params[k] === null) continue;
    if (!Number.isInteger(params[k]) || params[k] < lo || params[k] > hi) throw new RegistryError(`${k} must be a whole number from ${lo} to ${hi}`);
    changes[k] = params[k];
  }
  if (Object.keys(changes).length === 0) throw new RegistryError("give at least one of runsPerDay, minutesPerRun or maxTurns");
  return changes;
}

// The registry as raw JSON, for a write. Throws when it can't be read: nothing is written then.
function readRaw(file) {
  let raw;
  try {
    raw = JSON.parse(readFileSync(file, "utf8"));
  } catch {
    throw new RegistryError("the project registry can't be read, so nothing was changed");
  }
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) throw new RegistryError("the project registry isn't an object, so nothing was changed");
  return raw;
}

/**
 * Change one existing entry: `change(entry)` edits the raw entry in place (and may throw to refuse).
 * Re-reads the file first, so a change the runner or the installer made meanwhile isn't lost.
 */
export function updateEntry(file, name, change) {
  const raw = readRaw(file);
  if (!raw[name] || typeof raw[name] !== "object") throw new RegistryError(`${name} isn't in the registry`);
  const result = change(raw[name]);
  writeAtomic(file, `${JSON.stringify(raw, null, 2)}\n`);
  return result;
}

/** Change one project's limits. Returns { before, after }. */
export function setLimits(file, name, changes) {
  return updateEntry(file, name, (e) => {
    const before = { ...DEFAULT_LIMITS, ...Object.fromEntries(Object.entries(e.limits ?? {}).filter(([, v]) => Number.isInteger(v))) };
    e.limits = { ...(e.limits ?? {}), ...changes };
    return { before: pick(before), after: pick({ ...before, ...changes }) };
  });
}

const pick = (l) => ({ runsPerDay: l.runsPerDay, minutesPerRun: l.minutesPerRun, maxTurns: l.maxTurns });

/**
 * "owner/name" or a bare "name" (the first of Adam's GitHub owners) -> "owner/name", only for one of
 * the owners Jorah may work for. Throws with what is wrong.
 */
export function repoOf(value, owners) {
  const v = String(value ?? "").trim().replace(/^https:\/\/github\.com\//i, "").replace(/\.git$/, "").replace(/\/$/, "");
  const full = v.includes("/") ? v : `${owners[0] ?? ""}/${v}`;
  if (!REPO.test(full)) throw new RegistryError("repo must be owner/name on GitHub, e.g. AdamHikl/tree-watering-robot");
  const [owner, name] = full.split("/");
  const own = owners.find((o) => o.toLowerCase() === owner.toLowerCase());
  if (!own) throw new RegistryError(`${owner} isn't one of Adam's GitHub owners (${owners.join(", ") || "none set"})`);
  return `${own}/${name}`;
}

/** A level-0 entry with the contract's defaults: no schedule, runs only on request, no web, no bench. */
export function newEntry({ repo, workDir }) {
  return {
    repo, workDir, branch: "jorah/line", stateDir: "project", level: 0, schedule: [],
    limits: { ...DEFAULT_LIMITS }, web: false, bench: null, paused: false,
  };
}

/**
 * Add a project. Refuses a name, repo or work folder another entry already has (re-read just
 * before the write). The registry must exist: the runner's installer creates it.
 */
export function addProject(file, name, entry) {
  if (!NAME.test(name)) throw new RegistryError("the name must be lower-case letters, digits and dashes");
  const raw = readRaw(file);
  if (Object.prototype.hasOwnProperty.call(raw, name)) throw new RegistryError(`there's already a project called ${name}`);
  for (const [other, e] of Object.entries(raw)) {
    if (entry.repo && typeof e?.repo === "string" && e.repo.toLowerCase() === entry.repo.toLowerCase()) throw new RegistryError(`${entry.repo} is already the project ${other}`);
    if (e?.workDir === entry.workDir) throw new RegistryError(`${entry.workDir} is already the project ${other}'s folder`);
  }
  raw[name] = entry;
  writeAtomic(file, `${JSON.stringify(raw, null, 2)}\n`);
}
