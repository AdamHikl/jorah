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
import { existsSync, lstatSync, readdirSync, readFileSync, renameSync, unlinkSync, writeFileSync } from "node:fs";
import { join } from "node:path";

export const CONTRACT = "jorah-tool-v1";
export const MIN_AGE_DAYS = 7;
export const MAX_URL = 150;
export const MAX_LICENCE = 60;
const MAX_BYTES = 64 * 1024;
export const UNSTATED_DOWNLOAD_MB = 1024;
export const SIZE_FLOOR_MB = 64;
const MAX_DOWNLOAD_MB = 4096;
const MAX_INSTALLED_MB = 16384;
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
const ARCHIVE = { url: true, sha256: true, format: true, download_mb: false, installed_mb: false, commands: true, strip: false, env: false };
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
  if (!Number.isInteger(v) || v < 1 || v > high) {
    problems.push(`${key}: must be a whole number of megabytes from 1 to ${high}`);
    return null;
  }
  return v;
}

const relpath = (v) => typeof v === "string" && v.length >= 1 && v.length <= 200 && v.split("/").every((p) => RELPART.test(p) && p !== "." && p !== "..");

function addDays(day, n) {
  const d = new Date(`${day}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

/** Problems with manifest `m`; `today` is "YYYY-MM-DD". Empty when it's good. `filledLater`: required
 * fields that may be missing because a lookup fills them in (see checkRequest). */
export function checkManifest(m, today, filledLater = []) {
  if (!isObj(m)) return ["the request must be a JSON object"];
  const problems = [];
  let fields = { ...COMMON };
  if (!KINDS.includes(m.kind)) problems.push(`kind: must be one of ${KINDS.join(", ")}`);
  else fields = { ...COMMON, ...(m.kind === "archive" ? ARCHIVE : APT) };
  for (const key of Object.keys(m)) if (!(key in fields)) problems.push(`${key.slice(0, 40)}: unknown field`);
  for (const [key, required] of Object.entries(fields)) {
    if (required && !(key in m) && !filledLater.includes(key)) problems.push(`${key}: missing${GITHUB_FILLS.includes(key) ? MISSING_HINT : ""}`);
  }
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

  const released = m.released ?? "2000-01-01";
  if (typeof released !== "string" || !DAY.test(released)) problems.push("released: must be a date, YYYY-MM-DD");
  else if (Number.isNaN(Date.parse(`${released}T00:00:00Z`)) || new Date(`${released}T00:00:00Z`).toISOString().slice(0, 10) !== released) problems.push("released: isn't a real date");
  else if (released > addDays(today, -MIN_AGE_DAYS)) {
    problems.push(`released: ${released} is less than ${MIN_AGE_DAYS} days ago; wait until ${addDays(released, MIN_AGE_DAYS)} or pick an older release`);
  }
  if (m.for_project !== undefined && m.for_project !== null && (typeof m.for_project !== "string" || !PROJECT.test(m.for_project))) problems.push("for_project: a project's name, or null");
  const sb = m.sandbox;
  if (!isObj(sb) || Object.keys(sb).length !== 1 || !Array.isArray(sb.network) || sb.network.length !== 0) {
    problems.push('sandbox: must be {"network": []}: toolbox tools run offline inside the project sandbox; a tool that needs the network while it runs is a build-session decision');
  }

  let smokeNames = null;
  if (m.kind === "archive") {
    https(problems, "url", m.url, MAX_URL);
    if ("sha256" in m && (typeof m.sha256 !== "string" || !SHA256.test(m.sha256))) problems.push("sha256: 64 lower-case hex digits, from the publisher's checksum");
    if (!FORMATS.includes(m.format)) problems.push(`format: must be one of ${FORMATS.join(", ")}`);
    const given = [["download_mb", MAX_DOWNLOAD_MB], ["installed_mb", MAX_INSTALLED_MB]].filter(([key]) => key in m)
      .map(([key, high]) => whole(problems, m, key, high));
    if (given.length === 2 && !given.includes(null) && given[1] < given[0]) {
      problems.push(`installed_mb: less than the ${given[0]} MB download; leave installed_mb out and a limit is set from the download size`);
    }
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

// ---- GitHub release assets (toolcheck.py's github_asset, check_request, apply_github) ----------

const GITHUB_ASSET = /^https:\/\/github\.com\/([A-Za-z0-9-]{1,39})\/([A-Za-z0-9._-]{1,100})\/releases\/download\/([^/?#]{1,100})\/([^/?#]{1,200})$/;
export const GITHUB_API = "https://api.github.com";
export const GITHUB_FILLS = ["sha256", "released", "download_mb"];
const GITHUB_DIGEST = /^sha256:([0-9a-f]{64})$/;
const ASSET_NAME = /^[A-Za-z0-9._+-]{1,120}$/;
export const MISSING_HINT = " (filled in from GitHub only when url is a GitHub release asset)";
const MIB = 1048576;

// Python's unquote: a bad escape stays as it is instead of throwing.
const unquote = (v) => v.replace(/(%[0-9A-Fa-f]{2})+/g, (run) => {
  try {
    return decodeURIComponent(run);
  } catch {
    return run;
  }
});
// Python's quote(v, safe=""): encodeURIComponent also leaves ! ' ( ) * alone.
const quote = (v) => encodeURIComponent(v).replace(/[!'()*]/g, (c) => `%${c.charCodeAt(0).toString(16).toUpperCase()}`);

/** {owner, repo, tag, asset, path} for a GitHub release asset URL, `path` being the release's API path; else null. */
export function githubAsset(url) {
  const match = typeof url === "string" ? GITHUB_ASSET.exec(url) : null;
  if (!match || match[2] === "." || match[2] === "..") return null;
  const [, owner, repo] = match;
  const tag = unquote(match[3]);
  return { owner, repo, tag, asset: unquote(match[4]), path: `/repos/${owner}/${repo}/releases/tags/${quote(tag)}`, list: `/repos/${owner}/${repo}/releases?per_page=10` };
}

/** checkManifest for a request as Jorah writes it: for a GitHub release asset, the fields GitHub
 * fills in may be missing; for Ubuntu packages, the fields Ubuntu's own records fill in. */
export function checkRequest(m, today) {
  if (isObj(m) && m.kind === "apt") {
    // Check the rest with stand-ins for what Ubuntu's record fills in; applyUbuntu then sets them.
    const standIn = { version: "0", released: "2000-01-01", release_page: "https://launchpad.net/", homepage: "https://launchpad.net/",
      licence: "stand-in", licence_source: "stand-in" };
    const probe = { ...m };
    for (const k of UBUNTU_FILLS) if (!(k in probe)) probe[k] = standIn[k];
    return checkManifest(probe, today);
  }
  const url = isObj(m) && m.kind === "archive" ? m.url : null;
  return checkManifest(m, today, githubAsset(url) ? GITHUB_FILLS : []);
}

// ---- Ubuntu packages: Launchpad's publishing record and the package's own copyright file ------
// For kind "apt" (2026-11-22, after Jorah couldn't read cowsay's version, date and licence off web
// pages): Launchpad, Ubuntu's archive, says which version of each binary package is published for
// the series on amd64 and when; changelogs.ubuntu.com serves that exact version's debian/copyright.
export const LAUNCHPAD = "https://api.launchpad.net/1.0";
export const UBUNTU_CHANGELOGS = "https://changelogs.ubuntu.com/changelogs/pool";
export const UBUNTU_FILLS = ["version", "released", "release_page", "homepage", "licence", "licence_source"];
const SERIES = /^[a-z]{3,20}$/;
const COMPONENT = /^(main|restricted|universe|multiverse)$/;
const DEB_VERSION = /^(?:\d+:)?[A-Za-z0-9][A-Za-z0-9.+~-]{0,79}$/;
const SOURCE = /^[a-z0-9][a-z0-9+.-]{1,62}$/;
export const noEpoch = (v) => String(v).replace(/^\d+:/, "");

export function launchpadBinaries(series, pkg) {
  const arch = `${LAUNCHPAD}/ubuntu/${series}/amd64`;
  return `${LAUNCHPAD}/ubuntu/+archive/primary?ws.op=getPublishedBinaries&binary_name=${encodeURIComponent(pkg)}&exact_match=true`
    + `&distro_arch_series=${encodeURIComponent(arch)}&status=Published`;
}

/** The newest published version of one binary package from Launchpad's answer, or null. */
export function newestBinary(answer, pkg) {
  const entries = (isObj(answer) && Array.isArray(answer.entries) ? answer.entries : []).filter((e) => isObj(e)
    && e.binary_package_name === pkg && e.status === "Published" && typeof e.binary_package_version === "string" && DEB_VERSION.test(e.binary_package_version)
    && typeof e.date_published === "string" && !Number.isNaN(Date.parse(e.date_published))
    && typeof e.source_package_name === "string" && SOURCE.test(e.source_package_name)
    && typeof e.source_package_version === "string" && DEB_VERSION.test(e.source_package_version)
    && typeof e.component_name === "string" && COMPONENT.test(e.component_name));
  if (!entries.length) return null;
  const e = entries.sort((a, b) => Date.parse(b.date_published) - Date.parse(a.date_published))[0];
  return { name: pkg, version: e.binary_package_version, published: new Date(Date.parse(e.date_published)).toISOString(), pocket: String(e.pocket ?? ""),
    component: e.component_name, source: e.source_package_name, sourceVersion: e.source_package_version };
}

export function copyrightUrl(b) {
  const prefix = b.source.startsWith("lib") ? b.source.slice(0, 4) : b.source[0];
  return `${UBUNTU_CHANGELOGS}/${b.component}/${prefix}/${b.source}/${b.source}_${noEpoch(b.sourceVersion)}/copyright`;
}

/** The licence of a machine-readable (DEP-5) copyright file's "Files: *" paragraph, or null. */
export function dep5Licence(text) {
  if (typeof text !== "string" || !/^Format:\s*https?:\/\/\S*copyright-format/m.test(text)) return null;
  for (const para of text.replace(/\r/g, "").split(/\n\s*\n/)) {
    if (!/^Files:\s*\*\s*$/m.test(para)) continue;
    const m = /^License:[ \t]*(\S[^\n]*)$/m.exec(para);
    if (!m) return null;
    const v = m[1].replace(/\s+/g, " ").trim();
    if (control(v)) return null;
    return v.length > MAX_LICENCE ? `${v.slice(0, MAX_LICENCE - 1)}…` : v;
  }
  return null;
}

/** Ubuntu's record fills in and checks an apt request: {manifest, record, problems}. `found` has one
 * newestBinary (or null) per package, in order; `copyright` is {url, text} for the first. */
export function applyUbuntu(m, series, found, copyright) {
  const problems = [];
  const out = { ...m };
  const record = { series, packages: [], copyright: copyright?.url ?? null, filled: [] };
  (m.packages ?? []).forEach((pkg, i) => {
    const b = found[i];
    if (!b) problems.push(`packages: Ubuntu ${series} publishes no package named ${String(pkg).slice(0, 63)} for amd64 (check the binary package's exact name)`);
    else record.packages.push({ name: b.name, version: b.version, pocket: b.pocket, published: b.published });
  });
  if (problems.length) return { manifest: out, record, problems };
  const main = found[0];
  const version = noEpoch(main.version);
  if (!("version" in m)) {
    out.version = version.slice(0, 30);
    record.filled.push("version");
  } else if (m.version !== version && m.version !== main.version) {
    problems.push(`version: Ubuntu ${series} publishes ${main.name} ${main.version}, which apt installs; leave version out and it is filled in`);
  }
  const day = found.map((b) => b.published.slice(0, 10)).sort().pop();
  if (!("released" in m)) {
    out.released = day;
    record.filled.push("released");
  } else if (m.released !== day) {
    problems.push(`released: Ubuntu published the newest of these packages on ${day}, not ${m.released}; leave released out and it is filled in`);
  }
  const page = `https://launchpad.net/ubuntu/+source/${main.source}/${encodeURIComponent(main.sourceVersion)}`;
  for (const k of ["release_page", "homepage"]) {
    if (!(k in m)) {
      out[k] = page;
      record.filled.push(k);
    }
  }
  // The licence Adam accepts is the package's own, from Ubuntu's copy of its copyright file.
  const licence = dep5Licence(copyright?.text);
  out.licence = licence ?? "see Ubuntu's copyright file";
  out.licence_source = copyright?.url ?? copyrightUrl(main);
  record.filled.push("licence", "licence_source");
  record.licenceFrom = licence ? "the package's copyright file" : "not machine-readable; see the copyright file";
  return { manifest: out, record, problems };
}
export const isSeries = (s) => typeof s === "string" && SERIES.test(s);

export const downloadCap = (mb) => Math.trunc(mb * 1.1 * MIB) + 5 * MIB;

/** GitHub's answer for the release fills in and checks the request: {manifest, record, problems}. */
export function applyGithub(m, release) {
  const where = githubAsset(m?.url);
  if (!where) return { manifest: m, record: null, problems: ["url: isn't a GitHub release asset URL"] };
  const { tag, asset: name } = where;
  if (!isObj(release)) return { manifest: m, record: null, problems: ["GitHub's answer isn't a release"] };
  const problems = [];
  const out = { ...m };
  const record = { tag, asset: name, publishedAt: null, assetBytes: null, digest: null,
    immutable: typeof release.immutable === "boolean" ? release.immutable : null, filled: [] };
  if (release.draft) problems.push(`url: GitHub marks release ${tag} a draft`);
  if (release.prerelease) problems.push(`url: GitHub marks ${tag} a pre-release; pick a full release`);

  const published = release.published_at;
  const ms = typeof published === "string" && /^\d{4}-\d{2}-\d{2}T/.test(published) ? Date.parse(published) : NaN;
  if (Number.isNaN(ms)) problems.push(`released: GitHub gives no publication date for ${tag}`);
  else {
    const day = new Date(ms).toISOString().slice(0, 10);
    record.publishedAt = published;
    if (!("released" in m)) {
      out.released = day;
      record.filled.push("released");
    } else if (m.released !== day) {
      problems.push(`released: GitHub says ${tag} was published ${day} (UTC), not ${m.released}; leave released out and it is filled in`);
    }
  }

  const assets = (Array.isArray(release.assets) ? release.assets : []).filter(isObj);
  const found = assets.find((a) => a.name === name);
  if (!found) {
    const names = assets.map((a) => a.name).filter((n) => typeof n === "string" && ASSET_NAME.test(n)).slice(0, 8);
    problems.push(`url: release ${tag} has no asset named ${name.slice(0, 80)}${names.length ? `; its assets include ${names.join(", ")}` : ""}`);
    return { manifest: out, record, problems };
  }
  if (found.state !== undefined && found.state !== null && found.state !== "uploaded") problems.push(`url: GitHub says ${name.slice(0, 80)} isn't fully uploaded`);

  const dm = typeof found.digest === "string" ? GITHUB_DIGEST.exec(found.digest) : null;
  if (dm) {
    record.digest = found.digest;
    if (!("sha256" in m)) {
      out.sha256 = dm[1];
      record.filled.push("sha256");
    } else if (m.sha256 !== dm[1]) {
      problems.push(`sha256: GitHub's digest for ${name.slice(0, 80)} is ${dm[1].slice(0, 16)}..., not ${String(m.sha256).slice(0, 16)}...; leave sha256 out and it is filled in`);
    }
  } else if (!("sha256" in m)) {
    problems.push("sha256: GitHub holds no digest for this asset (an older release): give the publisher's own checksum");
  }

  const size = found.size;
  if (Number.isInteger(size) && size > 0) {
    record.assetBytes = size;
    const need = Math.max(1, Math.ceil(size / MIB));
    const given = m.download_mb;
    if (given === undefined || given === null) {
      out.download_mb = need;
      record.filled.push("download_mb");
    } else if (Number.isInteger(given) && (size > downloadCap(given) || Math.abs(given - size / MIB) > Math.max(3, size / MIB / 4))) {
      problems.push(`download_mb: GitHub says ${name.slice(0, 80)} is ${size} bytes; use ${need}, or leave download_mb out`);
    }
  }
  return { manifest: out, record, problems };
}

// ---- sizes (toolcheck.py's unpack_factor, installed_ceiling, fill_sizes) -----------------------
// Unpacked growth measured 2026-11-20 on 14 Linux releases: zip 2.3x, AppImage 3.2x, gzip tar
// 3.5x, xz tar 12.8x at most. The installer also allows 25% and 50 MB over the ceiling.

export function unpackFactor(fmt, url) {
  if (fmt === "file") return 1;
  if (fmt === "zip") return 4;
  if (fmt === "appimage") return 6;
  const path = typeof url === "string" ? url.split("#")[0].split("?")[0].toLowerCase() : "";
  return path.endsWith(".tar.gz") || path.endsWith(".tgz") ? 6 : 16;
}

export function installedCeiling(fmt, url, downloadMb) {
  const factor = unpackFactor(fmt, url);
  const mb = downloadMb * factor;
  return Math.min(MAX_INSTALLED_MB, factor === 1 ? mb : Math.max(SIZE_FLOOR_MB, mb));
}

/** {manifest, filled}: an archive with a download size and no installed_mb gets installedCeiling. */
export function fillSizes(m) {
  if (!isObj(m) || m.kind !== "archive" || "installed_mb" in m) return { manifest: m, filled: [] };
  const d = m.download_mb;
  if (!Number.isInteger(d) || d < 1 || d > MAX_DOWNLOAD_MB) return { manifest: m, filled: [] };
  return { manifest: { ...m, installed_mb: installedCeiling(m.format, m.url, d) }, filled: ["installed_mb"] };
}

const TAG = /^[A-Za-z0-9][A-Za-z0-9.+_~-]{0,59}$/;
const publishedDay = (r) => {
  const ms = typeof r.published_at === "string" && /^\d{4}-\d{2}-\d{2}T/.test(r.published_at) ? Date.parse(r.published_at) : NaN;
  return Number.isNaN(ms) ? null : new Date(ms).toISOString().slice(0, 10);
};

/** The newest full release at least MIN_AGE_DAYS old in GitHub's list: {tag, released, url}, or null (toolcheck.older_release). */
export function olderRelease(releases, where, today) {
  const limit = addDays(today, -MIN_AGE_DAYS);
  let best = null;
  for (const r of Array.isArray(releases) ? releases : []) {
    if (!isObj(r) || r.draft || r.prerelease) continue;
    const tag = r.tag_name;
    const day = publishedDay(r);
    if (typeof tag !== "string" || !TAG.test(tag) || !day || day > limit) continue;
    if (!best || r.published_at > best.r.published_at) best = { r, tag, day };
  }
  if (!best) return null;
  const names = new Set((Array.isArray(best.r.assets) ? best.r.assets : []).filter(isObj).map((a) => a.name));
  const strip = (t) => t.replace(/^[vV]+/, "");
  const tries = [where.asset.replaceAll(where.tag, best.tag), strip(where.tag) ? where.asset.replaceAll(strip(where.tag), strip(best.tag)) : null];
  const found = tries.find((n) => n && names.has(n) && ASSET_NAME.test(n));
  return { tag: best.tag, released: best.day, url: found ? `https://github.com/${where.owner}/${where.repo}/releases/download/${quote(best.tag)}/${quote(found)}` : null };
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
  const download = m.download_mb ?? null;
  let installed = m.installed_mb ?? null;
  if (m.kind !== "archive") {
    if (download === null && installed === null) return "not given (apt shows it before installing)";
    return `${download ?? "?"} MB download, ${installed ?? "?"} MB installed`;
  }
  if (download === null) {
    const first = `up to ${UNSTATED_DOWNLOAD_MB} MB download (measured at install)`;
    if (installed !== null) return `${first}, up to ${installed} MB installed`;
    const factor = unpackFactor(m.format, m.url);
    return `${first}, installed ${factor > 1 ? `up to ${factor}x it, min ${SIZE_FLOOR_MB} MB` : "the same"}`;
  }
  if (installed === null) installed = installedCeiling(m.format, m.url, download);
  return `${download} MB download, up to ${installed} MB installed`;
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

// A new chat proposal replaces older ones for the same tool and version that still wait for a card,
// so they don't pile up each time Jorah rewords the purpose (each wording is a new id). A run's
// proposals and anything approved stay. Returns the ids it removed.
export function supersede(s, m, keepId) {
  const tb = readToolbox(s);
  const approved = new Set(tb.approved.items.map((a) => a.data?.id));
  const gone = [];
  for (const { file, data } of tb.proposals.items) {
    const old = data?.manifest;
    if (!old || data.id === keepId || file !== `${data.id}.json` || !ID.test(data.id ?? "") || approved.has(data.id)) continue;
    if (old.name !== m.name || old.version !== m.version || data.from?.via === "run") continue;
    try {
      unlinkSync(join(s.toolboxVar, "proposals", file));
      gone.push(data.id);
    } catch {
      // Left in place: toolbox_list still shows it, and the next proposal tries again.
    }
  }
  return gone;
}

export function readProposal(s, id) {
  if (!ID.test(id ?? "")) return null;
  const path = join(s.toolboxVar, "proposals", `${id}.json`);
  if (!existsSync(path)) return null;
  return readJson(path);
}
