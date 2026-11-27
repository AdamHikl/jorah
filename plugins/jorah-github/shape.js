// Shaped results (docs/plan/13-autonomy.md 6.3a, 2026-11-27). github_sync and github_clone
// return only what this plugin computed and checked against strict patterns: names it validated,
// short hashes, counts and dates. Never a commit subject, a file's text, or text GitHub, git or a
// run wrote. jorah-guard counts them as reads (matrix class shapedRead) only while the result
// carries SHAPE; any other result, a thrown error included, marks the chat (policy.shapedBackstop).
// github_branch_report uses the same shapes, but file paths are chosen by whoever wrote the
// branch, so the guard keeps it in taintRead.

export const SHAPE = "jorah-github/1";

const NAME = /^[A-Za-z0-9][A-Za-z0-9._/-]{0,79}$/;
const JORAH = /^jorah\/[A-Za-z0-9][A-Za-z0-9._-]*(\/[A-Za-z0-9][A-Za-z0-9._-]*)*$/;
const HASH = /^[0-9a-f]{7,40}$/;
const PROJECT = /^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$/;
const REPO = /^[A-Za-z0-9-]{1,39}\/[A-Za-z0-9._-]{1,100}$/;
const PATH = /^[A-Za-z0-9._@+-][A-Za-z0-9._@+/-]{0,199}$/;
const DATE = /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(Z|[+-]\d\d:\d\d)$/;

export const MAX_JORAH_BRANCHES = 30;
export const MAX_FILES = 40;

const okName = (n) => typeof n === "string" && NAME.test(n) && !n.includes("..") && !n.endsWith(".lock") && !n.endsWith("/");
export const okBranch = (n) => okName(n) && JORAH.test(n);
export const okHash = (h) => typeof h === "string" && HASH.test(h);
export const okPath = (p) => typeof p === "string" && PATH.test(p) && !p.split("/").some((s) => s === "" || s === "." || s === "..");
export const okDate = (d) => typeof d === "string" && DATE.test(d);
export const okProject = (p) => typeof p === "string" && PROJECT.test(p);
export const okRepo = (r) => typeof r === "string" && REPO.test(r);

const short = (h) => (okHash(h) ? h.slice(0, 7) : null);

/** The default branch's name if it's a plain name, else null ("its default branch"). */
export const defaultName = (n) => (okName(n) ? n : null);

/** syncMirror's "name shorthash" lines → the default branch, Jorah's branches and a count of the rest. */
export function shapeBranches(lines, defaultBranch) {
  const def = defaultName(defaultBranch);
  let defaultHead = null;
  const jorah = [];
  let others = 0;
  let total = 0;
  for (const line of Array.isArray(lines) ? lines : []) {
    if (typeof line !== "string" || !line) continue;
    total++;
    const [name, hash, ...rest] = line.split(" ");
    if (rest.length === 0 && def && name === def && okHash(hash)) defaultHead = short(hash);
    else if (rest.length === 0 && okBranch(name) && okHash(hash) && jorah.length < MAX_JORAH_BRANCHES) jorah.push({ name, head: short(hash) });
    else others++;
  }
  return { defaultBranch: def, defaultHead, jorah, others, total };
}

/** github_sync's text and details. */
export function syncResult(target, synced) {
  const repo = okRepo(target?.repo) ? target.repo : "the repo";
  const project = okProject(target?.project) ? target.project : null;
  const b = shapeBranches(synced?.branches, synced?.defaultBranch);
  const def = b.defaultBranch ? `${b.defaultBranch}${b.defaultHead ? ` at ${b.defaultHead}` : ""}` : "unknown (GitHub didn't say)";
  const mine = b.jorah.length ? b.jorah.map((j) => `${j.name} (${j.head})`).join(", ") : "none";
  const lines = [
    `Synced ${repo} into Jorah's mirror: ${b.total} branch${b.total === 1 ? "" : "es"}.`,
    `Default branch: ${def}.`,
    `Jorah's branches on GitHub: ${mine}.`,
  ];
  if (b.others) lines.push(`${b.others} other branch${b.others === 1 ? "" : "es"} (names not shown).`);
  if (project) lines.push(`In ~/work/${project}, \`git fetch github\` gets them.`);
  return {
    text: lines.join("\n"),
    details: { shape: SHAPE, ok: true, repo: okRepo(target?.repo) ? target.repo : null, project, defaultBranch: b.defaultBranch, defaultHead: b.defaultHead, branchCount: b.total, jorahBranches: b.jorah, otherBranches: b.others },
  };
}

/** github_clone's text and details. cloned.head is a hash only (cloneFromMirror). */
export function cloneResult(target, synced, cloned) {
  const repo = okRepo(target?.repo) ? target.repo : "the repo";
  const project = okProject(target?.project) ? target.project : null;
  const branch = defaultName(cloned?.branch);
  const head = short(cloned?.head);
  const count = Array.isArray(synced?.branches) ? synced.branches.length : 0;
  const where = project ? `~/work/${project}` : "~/work";
  const on = branch ? `on ${branch}${head ? ` at ${head}` : ""}` : "on its default branch";
  return {
    text: `Cloned ${repo} into ${where}, ${on}. Remote \`github\` reads Jorah's mirror (${count} branch${count === 1 ? "" : "es"}). ` +
      `Claude Code works there on a new jorah/<task> branch from github/${branch ?? "<default branch>"}.`,
    details: { shape: SHAPE, ok: true, repo: okRepo(target?.repo) ? target.repo : null, project, path: project ? `~/work/${project}` : null, branch, head, branchCount: count },
  };
}

// Errors: only messages this plugin itself throws, matched whole, pass through. Anything else
// (git's stderr, a remote's message, GitHub's own words) becomes a fixed sentence; the full
// error goes to the Gateway log, never to the model.
const ARG = String.raw`[A-Za-z0-9][A-Za-z0-9._/-]{0,120}`;
const SAFE_ERRORS = [
  /^project must be a folder name under ~\/work$/,
  new RegExp(`^${ARG} isn't one of Adam's repos Jorah may work on$`),
  /^repo must be a repo name, e\.g\. robot_tour$/,
  new RegExp(`^only ${ARG}'s repos can be cloned$`),
  /^only the configured owner's repos can be cloned$/,
  /^only branches named jorah\/<task> can be (pushed|reported)$/,
  /^project folder must be inside ~\/work$/,
  new RegExp(`^~/work/${ARG} already exists; use github_sync to update it$`),
  new RegExp(`^~/work/${ARG} doesn't exist; github_clone it first$`),
  new RegExp(`^no mirror of ${ARG} yet(; github_sync first)?$`),
  /^the App's ID isn't set$/,
  /^the App's key file must be readable by its owner only$/,
  /^the App's key file holds no private key$/,
  new RegExp(`^there's no repo named ${ARG} that jorah-bot can see; check the spelling \\(github_list_repos lists Adam's repos\\)$`),
  new RegExp(`^GitHub said \\d{3} (finding the App on|reading) ${ARG}$`),
  new RegExp(`^GitHub gave no usable default branch for ${ARG}$`),
];

export function shapedError(error) {
  const msg = String(error?.message ?? error ?? "").split("\n")[0].trim();
  if (SAFE_ERRORS.some((re) => re.test(msg))) return msg;
  const token = msg.match(/^GitHub said (\d{3}) making a token/);
  if (token) return `GitHub said ${token[1]} making a token`;
  if (/^(ENOENT|EACCES)\b/.test(msg) || /\b(ENOENT|EACCES)\b/.test(String(error?.code ?? ""))) return "a file Jorah needs is missing or unreadable (details in the Gateway log)";
  return "git or GitHub failed (details in the Gateway log)";
}

export function errorResult(prefix, error) {
  return { text: `${prefix}: ${shapedError(error)}`, details: { shape: SHAPE, ok: false } };
}

const STATUS = { A: "added", M: "changed", D: "deleted", T: "type changed" };

/** `git diff --name-status --no-renames -z` output → shaped file list. */
export function shapeFiles(raw) {
  const parts = String(raw ?? "").split("\0").filter((s) => s !== "");
  const files = [];
  let total = 0;
  let odd = 0;
  for (let i = 0; i + 1 < parts.length; i += 2) {
    total++;
    const status = STATUS[parts[i]];
    const path = parts[i + 1];
    if (!status || !okPath(path)) { odd++; continue; }
    if (files.length < MAX_FILES) files.push({ status, path });
  }
  return { files, total, odd, more: total - odd - files.length };
}

/** github_branch_report's text and details from the facts branchReport gathered. */
export function reportResult(r) {
  const project = okProject(r?.project) ? r.project : null;
  const branch = okBranch(r?.branch) ? r.branch : null;
  const where = project ? `~/work/${project}` : "the work folder";
  const name = branch ?? "that branch";
  if (r?.exists !== true) {
    return {
      text: `${where} has no branch ${name}.`,
      details: { shape: SHAPE, ok: true, project, branch, exists: false },
    };
  }
  const head = short(r.head);
  const date = okDate(r.date) ? r.date : null;
  const base = defaultName(r.base);
  const ahead = Number.isInteger(r.ahead) && r.ahead >= 0 ? r.ahead : null;
  const behind = Number.isInteger(r.behind) && r.behind >= 0 ? r.behind : null;
  const f = r.files ?? null;
  const onGitHub = ["same", "different", "absent"].includes(r.onGitHub) ? r.onGitHub : "unknown";
  const lines = [`${name} in ${where}: head ${head ?? "unknown"}${date ? `, last commit ${date}` : ""}.`];
  if (base && ahead !== null && behind !== null) {
    lines.push(`Against github/${base}: ${ahead} commit${ahead === 1 ? "" : "s"} ahead, ${behind} behind.`);
  } else {
    lines.push("Against the default branch: unknown (github_sync first).");
  }
  if (f) {
    lines.push(`Files changed: ${f.total}${f.total ? ":" : "."}`);
    for (const x of f.files) lines.push(`- ${x.status} ${x.path}`);
    if (f.more > 0) lines.push(`- and ${f.more} more`);
    if (f.odd > 0) lines.push(`- and ${f.odd} with names not shown`);
  }
  const gh = { same: "pushed, same head", different: "pushed, but GitHub's copy differs", absent: "not pushed", unknown: "unknown" }[onGitHub];
  lines.push(`On GitHub, as of the last sync: ${gh}.`);
  lines.push("Uncommitted changes in the folder aren't checked.");
  return {
    text: lines.join("\n"),
    details: { shape: SHAPE, ok: true, project, branch, exists: true, head, date, base, ahead, behind, files: f ? f.files : null, fileCount: f ? f.total : null, onGitHub },
  };
}
