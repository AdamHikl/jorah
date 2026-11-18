// Jorah's toolbox, the plugin's side (docs/runbooks/toolbox.md, contract jorah-tool-v1 in
// docs/contracts/jorah-tool-v1.md). A JavaScript copy of packages/contracts/toolbox/toolcheck.py's
// rules, tested against the same examples; the runner and the installer check again in Python, so
// this copy only has to refuse early, never to be the last word.
//
// Files (all JSON):
//   /var/lib/jorah-toolbox/proposals/<id>.json  proposals: from runs (the runner) or from chat (here)
//   /var/lib/jorah-toolbox/approved/<id>.json   approvals: written here only, after Adam's card
//   /var/lib/jorah-toolbox/results/<id>.json    the installer's results (user jorah-toolbox)
//   /var/lib/jorah-toolbox/tested/<name>.json   the runner's smoke tests and learning runs
//   /opt/jorah-toolbox/installed.json           what is installed

import { createHash } from "node:crypto";
import { existsSync, lstatSync, readdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { join } from "node:path";

export const CONTRACT = "jorah-tool-v1";
export const MIN_AGE_DAYS = 7;
export const MAX_URL = 150;
export const MAX_LICENCE = 60;
const MAX_BYTES = 64 * 1024;
const KINDS = ["archive", "apt"];
const FORMATS = ["tar", "zip", "appimage", "file"];

export const NAME = /^[a-z][a-z0-9-]{1,39}$/;
const VERSION = /^[A-Za-z0-9][A-Za-z0-9.+_~-]{0,29}$/;
const COMMAND = /^[a-z0-9][a-z0-9._+-]{0,39}$/;
const PROJECT = /^[a-z0-9][a-z0-9-]{0,62}$/;
const PACKAGE = /^[a-z0-9][a-z0-9+.-]{1,62}$/;
const SHA256 = /^[0-9a-f]{64}$/;
const DAY = /^\d{4}-\d{2}-\d{2}$/;
const ENV_KEY = /^[A-Z][A-Z0-9_]{0,63}$/;
const RELPART = /^[A-Za-z0-9_+@-][A-Za-z0-9._+@-]{0,99}$/;
export const ID = /^tb-[0-9a-f]{10}$/;
const FORBIDDEN_ENV = new Set(["PATH", "HOME", "SHELL", "ENV", "BASH_ENV", "IFS", "PS4", "PROMPT_COMMAND", "LD_PRELOAD", "LD_AUDIT",
  "PYTHONSTARTUP", "PYTHONHOME", "NODE_OPTIONS", "GIT_SSH", "GIT_SSH_COMMAND", "GIT_EXEC_PATH", "JORAH_TOOLBOX_STATE", "TMPDIR",
  "XDG_RUNTIME_DIR", "CLAUDE_CONFIG_DIR"]);

const COMMON = { contract: true, name: true, title: true, version: true, kind: true, purpose: true, homepage: true, licence: true,
  licence_source: true, released: true, release_page: true, sandbox: true, smoke: true, for_project: false, smoke_expect: false };
const ARCHIVE = { url: true, sha256: true, format: true, download_mb: true, installed_mb: true, commands: true, strip: false, env: false };
const APT = { packages: true, download_mb: false, installed_mb: false };

const isObj = (v) => v !== null && typeof v === "object" && !Array.isArray(v);
const control = (s) => [...s].some((c) => (c.charCodeAt(0) < 32 && c !== "\n" && c !== "\t") || c === "\x7f");

function text(problems, m, key, low, high, oneLine = true) {
  const v = m[key];
  if (typeof v !== "string" || v.trim().length < low || v.trim().length > high || v !== v.trim()) {
    problems.push(`${key}: must be text of ${low} to ${high} characters, without spaces at the ends`);
    return;
  }
  if (oneLine && /[\r\n]/.test(v)) problems.push(`${key}: must be one line`);
  if (control(v)) problems.push(`${key}: has control characters`);
}

function https(problems, key, v, high) {
  if (typeof v !== "string" || v.length < 12 || v.length > high) {
    problems.push(`${key}: must be an https URL of at most ${high} characters`);
    return;
  }
  let u;
  try {
    u = new URL(v);
  } catch {
    problems.push(`${key}: isn't a URL`);
    return;
  }
  const host = u.hostname;
  if (u.protocol !== "https:" || !host || u.username || u.password || (u.port && u.port !== "443") || !v.toLowerCase().startsWith("https://")) {
    problems.push(`${key}: must be https, on the default port, with no user or password`);
    return;
  }
  if (/^[0-9.]+$/.test(host) || host.includes(":") || host.startsWith("[") || !host.includes(".") || /\.(local|internal|localhost|lan)$/.test(host)) {
    problems.push(`${key}: must name a public host, not an address`);
  }
  if (/\s|\\/.test(v)) problems.push(`${key}: has spaces or backslashes`);
}

function whole(problems, m, key, high) {
  const v = m[key];
  if (!Number.isInteger(v) || v < 1 || v > high) problems.push(`${key}: must be a whole number of megabytes from 1 to ${high}`);
}

const relpath = (v) => typeof v === "string" && v.length >= 1 && v.length <= 200 && v.split("/").every((p) => RELPART.test(p) && p !== "." && p !== "..");

function addDays(day, n) {
  const d = new Date(`${day}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

/** Problems with manifest `m`; `today` is "YYYY-MM-DD". Empty when it's good. */
export function checkManifest(m, today) {
  if (!isObj(m)) return ["the request must be a JSON object"];
  const problems = [];
  let fields = { ...COMMON };
  if (!KINDS.includes(m.kind)) problems.push(`kind: must be one of ${KINDS.join(", ")}`);
  else fields = { ...COMMON, ...(m.kind === "archive" ? ARCHIVE : APT) };
  for (const key of Object.keys(m)) if (!(key in fields)) problems.push(`${key.slice(0, 40)}: unknown field`);
  for (const [key, required] of Object.entries(fields)) if (required && !(key in m)) problems.push(`${key}: missing`);
  if (problems.length) return problems;

  if (m.contract !== CONTRACT) problems.push(`contract: must be ${CONTRACT}`);
  if (typeof m.name !== "string" || !NAME.test(m.name)) problems.push("name: lower-case letters, digits and dashes, 2 to 40, starting with a letter");
  text(problems, m, "title", 1, 80);
  if (typeof m.version !== "string" || !VERSION.test(m.version)) problems.push("version: letters, digits and . + _ ~ -, at most 30, starting with a letter or digit");
  text(problems, m, "purpose", 10, 600, false);
  https(problems, "homepage", m.homepage, 300);
  https(problems, "release_page", m.release_page, 300);
  text(problems, m, "licence", 2, MAX_LICENCE);
  text(problems, m, "licence_source", 2, 300);

  if (typeof m.released !== "string" || !DAY.test(m.released)) problems.push("released: must be a date, YYYY-MM-DD");
  else if (Number.isNaN(Date.parse(`${m.released}T00:00:00Z`)) || new Date(`${m.released}T00:00:00Z`).toISOString().slice(0, 10) !== m.released) problems.push("released: isn't a real date");
  else if (m.released > addDays(today, -MIN_AGE_DAYS)) {
    problems.push(`released: ${m.released} is less than ${MIN_AGE_DAYS} days ago; wait until ${addDays(m.released, MIN_AGE_DAYS)} or pick an older release`);
  }
  if (m.for_project !== undefined && m.for_project !== null && (typeof m.for_project !== "string" || !PROJECT.test(m.for_project))) problems.push("for_project: a project's name, or null");
  const sb = m.sandbox;
  if (!isObj(sb) || Object.keys(sb).length !== 1 || !Array.isArray(sb.network) || sb.network.length !== 0) {
    problems.push('sandbox: must be {"network": []}: toolbox tools run offline inside the project sandbox; a tool that needs the network while it runs is a build-session decision');
  }

  let smokeNames = null;
  if (m.kind === "archive") {
    https(problems, "url", m.url, MAX_URL);
    if (typeof m.sha256 !== "string" || !SHA256.test(m.sha256)) problems.push("sha256: 64 lower-case hex digits, from the publisher's checksum");
    if (!FORMATS.includes(m.format)) problems.push(`format: must be one of ${FORMATS.join(", ")}`);
    whole(problems, m, "download_mb", 4096);
    whole(problems, m, "installed_mb", 16384);
    const strip = m.strip ?? 0;
    if (!Number.isInteger(strip) || strip < 0 || strip > 3) problems.push("strip: a whole number from 0 to 3");
    else if (strip && !["tar", "zip"].includes(m.format)) problems.push("strip: only for tar and zip");
    let commands = m.commands;
    if (!isObj(commands) || Object.keys(commands).length < 1 || Object.keys(commands).length > 12) {
      problems.push("commands: an object of 1 to 12 command names and paths inside the tool");
      commands = {};
    }
    for (const [cmd, path] of Object.entries(commands)) {
      if (!COMMAND.test(cmd)) problems.push(`commands: '${cmd.slice(0, 40)}' isn't a plain command name`);
      if (!relpath(path)) problems.push(`commands.${cmd.slice(0, 40)}: must be a relative path inside the tool: letters, digits and . _ + @ -, no .. or empty parts`);
    }
    if (m.format === "file" && Object.keys(commands).length !== 1) problems.push("commands: a single-file tool has exactly one command");
    let env = m.env ?? {};
    if (!isObj(env) || Object.keys(env).length > 12) {
      problems.push("env: an object of at most 12 variables");
      env = {};
    }
    for (const [key, value] of Object.entries(env)) {
      if (!ENV_KEY.test(key) || FORBIDDEN_ENV.has(key) || /^(LD_|BASH_FUNC|DYLD_)/.test(key)) {
        problems.push(`env: ${key.slice(0, 40)} can't be set`);
        continue;
      }
      const rest = typeof value === "string" ? value.replace(/\$\{(TOOL|STATE)\}/g, "") : null;
      if (rest === null || value.length > 300 || /[$`"\\\n\r]/.test(rest) || [...value].some((c) => c.charCodeAt(0) < 32)) {
        problems.push(`env.${key}: text of at most 300 characters; only \${TOOL} and \${STATE} may be used, and no $, backquote, double quote, backslash or newline otherwise`);
      }
    }
    smokeNames = new Set(Object.keys(commands));
  } else {
    const pk = m.packages;
    if (!Array.isArray(pk) || pk.length < 1 || pk.length > 20 || !pk.every((p) => typeof p === "string" && PACKAGE.test(p))) problems.push("packages: 1 to 20 Ubuntu package names");
    else if (new Set(pk).size !== pk.length) problems.push("packages: a name is listed twice");
    else if (pk.join(" ").length > MAX_URL - 16) problems.push(`packages: at most ${MAX_URL - 16} characters in all (the card shows them in full)`);
    for (const key of ["download_mb", "installed_mb"]) if (key in m) whole(problems, m, key, 16384);
  }

  const smoke = m.smoke;
  if (!Array.isArray(smoke) || smoke.length < 1 || smoke.length > 20 || !smoke.every((a) => typeof a === "string" && a.length > 0 && a.length <= 300)) {
    problems.push("smoke: a command line as a list of 1 to 20 arguments");
  } else if (smoke.some((a) => [...a].some((c) => c.charCodeAt(0) < 32))) {
    problems.push("smoke: arguments can't have control characters");
  } else if (smokeNames && !smokeNames.has(smoke[0])) {
    problems.push("smoke: must start with one of the tool's commands");
  } else if (!smokeNames && !COMMAND.test(smoke[0])) {
    problems.push("smoke: must start with a plain command name");
  }
  if ("smoke_expect" in m) text(problems, m, "smoke_expect", 1, 200);
  return problems;
}

// Python's json.dumps(m, sort_keys=True, separators=(",", ":"), ensure_ascii=False). Manifests
// hold only text, whole numbers, booleans, null, lists and objects with ASCII keys.
export function canonical(v) {
  if (Array.isArray(v)) return `[${v.map(canonical).join(",")}]`;
  if (isObj(v)) return `{${Object.keys(v).sort().map((k) => `${JSON.stringify(k)}:${canonical(v[k])}`).join(",")}}`;
  return JSON.stringify(v);
}

export const digest = (m) => createHash("sha256").update(canonical(m), "utf8").digest("hex");
export const proposalId = (m) => `tb-${digest(m).slice(0, 10)}`;
export const sourceText = (m) => (m.kind === "archive" ? m.url : `Ubuntu archive: ${(m.packages ?? []).join(" ")}`);

export function sizeText(m) {
  if (m.download_mb === undefined && m.installed_mb === undefined) return "not given (apt shows it before installing)";
  return `${m.download_mb ?? "?"} MB download, ${m.installed_mb ?? "?"} MB installed`;
}

/** What toolbox_install takes and the card shows: the same fields as toolcheck.card_fields. */
export function cardFields(m, id) {
  return { id, name: m.name, version: m.version, source: sourceText(m),
    sha256: m.kind === "archive" ? m.sha256.slice(0, 16) : "none (Ubuntu's signed archive)",
    licence: m.licence, released: m.released, size: sizeText(m) };
}

// The guard cuts each card line at 160 characters and the whole card at 500, and may add a line of
// up to 116 characters about outside text. A card that would be cut isn't offered.
export function cardLength(fields) {
  return Object.keys(fields).sort().map((k) => `${k}: ${fields[k]}`).join("\n").length;
}
export const CARD_ROOM = 500 - 117;

// ---- files -------------------------------------------------------------------------------------

function readJson(path) {
  const st = lstatSync(path);
  if (!st.isFile() || st.size > (4 << 20)) throw new Error(`${path} isn't a plain file under 4 MB`);
  return JSON.parse(readFileSync(path, "utf8"));
}

function list(dir, max = 200) {
  if (!existsSync(dir)) return { ok: false, items: [] };
  const items = [];
  let broken = 0;
  for (const name of readdirSync(dir).filter((n) => n.endsWith(".json")).sort().slice(-max)) {
    try {
      const st = lstatSync(join(dir, name));
      if (!st.isFile() || st.size > MAX_BYTES * 4) {
        broken += 1;
        continue;
      }
      items.push({ file: name, data: JSON.parse(readFileSync(join(dir, name), "utf8")), mtime: st.mtimeMs });
    } catch {
      broken += 1;
    }
  }
  return { ok: true, items, broken };
}

export function readToolbox(s) {
  let installed = {};
  let installedOk = false;
  try {
    const data = readJson(join(s.toolboxDir, "installed.json"));
    if (isObj(data?.tools)) {
      installed = data.tools;
      installedOk = true;
    }
  } catch {
    installedOk = existsSync(s.toolboxDir) && !existsSync(join(s.toolboxDir, "installed.json"));
  }
  return {
    available: existsSync(s.toolboxVar),
    installed,
    installedOk,
    proposals: list(join(s.toolboxVar, "proposals")),
    approved: list(join(s.toolboxVar, "approved")),
    results: list(join(s.toolboxVar, "results")),
    tested: list(join(s.toolboxVar, "tested")),
  };
}

// Written beside, then renamed in, so the installer's folder only ever holds whole files (its path
// unit starts the installer while the folder isn't empty). Mode 644: the approved/ folder itself is
// 2770 jorah:jorah-toolbox, so only jorah and the installer can reach the file.
export function writeFresh(dir, name, body, tmpDir = dir) {
  const path = join(dir, name);
  if (existsSync(path)) return false;
  const tmp = join(tmpDir, `.${name}.${process.pid}.tmp`);
  writeFileSync(tmp, `${JSON.stringify(body, null, 2)}\n`, { mode: 0o644, flag: "wx" });
  renameSync(tmp, path);
  return true;
}

export function readProposal(s, id) {
  if (!ID.test(id ?? "")) return null;
  const path = join(s.toolboxVar, "proposals", `${id}.json`);
  if (!existsSync(path)) return null;
  return readJson(path);
}
