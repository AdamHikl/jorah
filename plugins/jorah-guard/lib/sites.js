// Site readers (docs/runbooks/site-readers.md). Adam's signed-in sites are read through a browser
// that only the site reader agent may drive, and only to open and read the pages listed in that
// site's file in config/sites/. Adding a site is adding a file there, plus Adam's sign-in.
//
// Shared by three parts, so one rule set holds everywhere:
//   jorah-guard   enforces it on every tool call (siteDecision);
//   jorah-sites   runs the reader and checks what it hands back (pageUrls, kinds, keepNames);
//   site proxy    fences the browser's network to the hosts named here (allowedHosts).
// Everything here fails closed: a broken file disables that site, never widens it.

import { readFileSync, readdirSync } from "node:fs";
import { basename, join } from "node:path";
import { strings } from "./urls.js";

export const READER_AGENT = "reader-site";
export const KINDS = ["event", "grade", "notice", "task", "item"];
export const CDP_PORTS = [43220, 43229];

// Only reading. "act" (click, type, fill, press, select, drag, upload, evaluate), "requests"
// (the network log can hold tokens), "emulate", "doctor", "start", "stop", "dashboard" and anything
// added to OpenClaw later are refused.
const READ_ACTIONS = new Set(["status", "tabs", "open", "focus", "close", "snapshot", "screenshot", "navigate", "text"]);
const URL_ACTIONS = new Set(["open", "navigate"]);
const NAME_RE = /^[a-z][a-z0-9-]{1,30}$/;
const HOST_RE = /^(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$/;
const NONCE_RE = /^[a-f0-9]{16,64}$/;
const DEFAULT_BLOCK = ["logout", "log-out", "signout", "sign-out", "delete", "remove", "unsubscribe"];

export const profileOf = (name) => `site-${name}`;
export const sessionKeyFor = (name, nonce) => `agent:${READER_AGENT}:site:${name}:${nonce}`;

// Only jorah-sites starts sessions with this shape; sessions_spawn, cron and hooks produce others.
export function siteOfSession(sessionKey) {
  const parts = String(sessionKey ?? "").split(":");
  if (parts.length !== 5 || parts[0] !== "agent" || parts[1] !== READER_AGENT || parts[2] !== "site") return null;
  return NAME_RE.test(parts[3]) && NONCE_RE.test(parts[4]) ? parts[3] : null;
}

const fail = (file, msg) => { throw new Error(`${basename(file)}: ${msg}`); };
const isObj = (v) => v !== null && typeof v === "object" && !Array.isArray(v);
const str = (v, max) => typeof v === "string" && v.length > 0 && v.length <= max;

function checkKeys(file, obj, allowed, where) {
  for (const k of Object.keys(obj)) if (!allowed.includes(k)) fail(file, `unknown field ${where}${k}`);
}

// Parse and check one site file. Throws on anything unexpected.
export function parseSite(raw, file, { allowTest = false } = {}) {
  if (!isObj(raw)) fail(file, "not a JSON object");
  checkKeys(file, raw, ["version", "name", "title", "about", "host", "extraHosts", "cdpPort", "pages", "extraPaths",
    "blockPaths", "kinds", "redactNames", "maxPagesPerRead", "signedOutPaths", "test"], "");
  if (raw.version !== 1) fail(file, "version must be 1");
  if (!NAME_RE.test(raw.name ?? "")) fail(file, "name must be lower-case letters, digits and dashes");
  if (`${raw.name}.json` !== basename(file)) fail(file, "file name must be <name>.json");
  if (!str(raw.title, 40)) fail(file, "title: 1 to 40 characters");
  if (raw.about !== undefined && !str(raw.about, 400)) fail(file, "about: up to 400 characters");

  let host = null;
  let hostPattern = null;
  if (typeof raw.host === "string") {
    if (!HOST_RE.test(raw.host)) fail(file, "host isn't a plain host name");
    host = raw.host;
  } else if (isObj(raw.host)) {
    checkKeys(file, raw.host, ["from", "pattern"], "host.");
    if (raw.host.from !== "private") fail(file, 'host.from must be "private"');
    if (!str(raw.host.pattern, 200) || !raw.host.pattern.startsWith("^") || !raw.host.pattern.endsWith("$")) fail(file, "host.pattern must be anchored with ^ and $");
    try { hostPattern = new RegExp(raw.host.pattern); } catch { fail(file, "host.pattern isn't a valid pattern"); }
  } else fail(file, "host: a host name, or { from: \"private\", pattern }");

  const extraHosts = raw.extraHosts ?? [];
  if (!Array.isArray(extraHosts) || extraHosts.length > 10 || !extraHosts.every((h) => HOST_RE.test(h))) fail(file, "extraHosts: up to 10 plain host names");

  if (!Number.isInteger(raw.cdpPort) || raw.cdpPort < CDP_PORTS[0] || raw.cdpPort > CDP_PORTS[1]) fail(file, `cdpPort: ${CDP_PORTS[0]} to ${CDP_PORTS[1]}`);

  if (!Array.isArray(raw.pages) || raw.pages.length < 1 || raw.pages.length > 20) fail(file, "pages: 1 to 20");
  const ids = new Set();
  const pages = raw.pages.map((p, i) => {
    if (!isObj(p)) fail(file, `pages[${i}] isn't an object`);
    checkKeys(file, p, ["id", "path", "query", "about", "confirmed"], `pages[${i}].`);
    if (!NAME_RE.test(p.id ?? "") || ids.has(p.id)) fail(file, `pages[${i}].id: unique, lower-case`);
    ids.add(p.id);
    if (!str(p.path, 200) || !p.path.startsWith("/") || /(^|\/)\.\.?(\/|$)|\\|%|\s/.test(p.path)) fail(file, `pages[${i}].path: a plain absolute path`);
    const query = p.query ?? {};
    if (!isObj(query) || !Object.entries(query).every(([k, v]) => str(k, 40) && typeof v === "string" && v.length <= 100)) fail(file, `pages[${i}].query: names to strings`);
    if (!str(p.about, 120)) fail(file, `pages[${i}].about: 1 to 120 characters`);
    if (p.confirmed !== undefined && typeof p.confirmed !== "boolean") fail(file, `pages[${i}].confirmed: true or false`);
    return { id: p.id, path: p.path, query, about: p.about, confirmed: p.confirmed !== false };
  });

  const extraPaths = (raw.extraPaths ?? []).map((src, i) => {
    if (!str(src, 200)) fail(file, `extraPaths[${i}]: a pattern`);
    try { return new RegExp(`^(?:${src})$`); } catch { return fail(file, `extraPaths[${i}] isn't a valid pattern`); }
  });
  if (extraPaths.length > 10) fail(file, "extraPaths: up to 10");

  const blockPaths = raw.blockPaths ?? [];
  if (!Array.isArray(blockPaths) || !blockPaths.every((w) => str(w, 40))) fail(file, "blockPaths: words");

  const kinds = raw.kinds;
  if (!Array.isArray(kinds) || kinds.length === 0 || !kinds.every((k) => KINDS.includes(k))) fail(file, `kinds: some of ${KINDS.join(", ")}`);
  if (raw.redactNames !== undefined && typeof raw.redactNames !== "boolean") fail(file, "redactNames: true or false");
  const maxPages = raw.maxPagesPerRead ?? 6;
  if (!Number.isInteger(maxPages) || maxPages < 1 || maxPages > 20) fail(file, "maxPagesPerRead: 1 to 20");
  const signedOutPaths = raw.signedOutPaths ?? [];
  if (!Array.isArray(signedOutPaths) || !signedOutPaths.every((p) => str(p, 100) && p.startsWith("/"))) fail(file, "signedOutPaths: paths");

  // A test site, for jorah-dev only: plain http to a fake site on loopback through the proxy.
  let test = null;
  if (raw.test !== undefined) {
    if (!allowTest) fail(file, "test sites load only on jorah-dev");
    if (!isObj(raw.test) || !/^127\.0\.0\.1:\d{4,5}$/.test(raw.test.upstream ?? "")) fail(file, "test.upstream: 127.0.0.1:<port>");
    test = { upstream: raw.test.upstream };
  }

  return {
    name: raw.name, title: raw.title, about: raw.about ?? "", host, hostPattern, extraHosts, cdpPort: raw.cdpPort, pages,
    extraPaths, blockPaths: [...DEFAULT_BLOCK, ...blockPaths.map((w) => w.toLowerCase())], kinds,
    redactNames: raw.redactNames !== false, maxPagesPerRead: maxPages, signedOutPaths, test,
    keepNames: [], enabled: host !== null, disabledReason: host ? null : "its address isn't in the private file yet",
  };
}

// The private file (/etc/jorah/sites.private.json, root-owned, never in the repo) holds what
// shouldn't be public: a school's address, names to keep in output.
function applyPrivate(site, entry) {
  if (!entry) return site;
  if (!isObj(entry)) return { ...site, enabled: false, disabledReason: "its private entry isn't an object" };
  const out = { ...site };
  if (entry.host !== undefined) {
    const h = String(entry.host).toLowerCase();
    if (!site.hostPattern) return { ...site, enabled: false, disabledReason: "its host is public, so the private file can't set it" };
    if (!HOST_RE.test(h) || !site.hostPattern.test(h)) return { ...site, enabled: false, disabledReason: "the private host doesn't match the site's pattern" };
    out.host = h;
  }
  if (entry.keepNames !== undefined) {
    if (!Array.isArray(entry.keepNames) || !entry.keepNames.every((n) => str(n, 60))) return { ...site, enabled: false, disabledReason: "keepNames must be names" };
    out.keepNames = entry.keepNames;
  }
  if (entry.enabled === false) return { ...out, enabled: false, disabledReason: "turned off in the private file" };
  out.enabled = out.host !== null;
  out.disabledReason = out.enabled ? null : "its address isn't in the private file yet";
  return out;
}

/** Load every config/sites/<name>.json (files starting with "_" are templates) and the private file. */
export function loadSites({ dir, privateFile, allowTest = false } = {}) {
  const sites = new Map();
  const errors = [];
  let priv = {};
  if (privateFile) {
    try {
      const p = JSON.parse(readFileSync(privateFile, "utf8"));
      if (!isObj(p) || p.version !== 1 || !isObj(p.sites)) throw new Error("needs { version: 1, sites: {...} }");
      priv = p.sites;
    } catch (e) {
      if (e?.code !== "ENOENT") errors.push(`private file: ${e?.message ?? e}`);
    }
  }
  let files = [];
  try {
    files = readdirSync(dir).filter((f) => f.endsWith(".json") && !f.startsWith("_")).sort();
  } catch (e) {
    errors.push(`sites folder: ${e?.message ?? e}`);
  }
  const ports = new Map();
  for (const f of files) {
    const file = join(dir, f);
    try {
      const site = applyPrivate(parseSite(JSON.parse(readFileSync(file, "utf8")), file, { allowTest }), priv[f.slice(0, -5)]);
      if (ports.has(site.cdpPort)) throw new Error(`${f}: cdpPort ${site.cdpPort} is also used by ${ports.get(site.cdpPort)}`);
      ports.set(site.cdpPort, site.name);
      sites.set(site.name, site);
    } catch (e) {
      errors.push(e?.message ?? String(e));
    }
  }
  return { sites, errors };
}

/** Full addresses of a site's pages, for the reader's brief. */
export function pageUrls(site) {
  if (!site?.host) return [];
  const origin = site.test ? `http://${site.host}` : `https://${site.host}`;
  return site.pages.map((p) => {
    const u = new URL(p.path, origin);
    for (const [k, v] of Object.entries(p.query)) u.searchParams.set(k, v);
    return { id: p.id, url: u.toString(), about: p.about, confirmed: p.confirmed };
  });
}

/** Hosts the site's browser may reach through the proxy: the site, then its asset hosts. */
export function allowedHosts(sites) {
  const out = new Map();
  for (const s of sites.values()) {
    if (!s.enabled) continue;
    for (const h of [s.host, ...s.extraHosts]) out.set(h, s.test ? { upstream: s.test.upstream } : { port: 443 });
  }
  return out;
}

// Why a URL is not one of the site's pages, or null when it is. Reasons never repeat the address:
// they reach the decision log, which keeps no addresses.
export function checkSiteUrl(site, raw) {
  let u;
  try { u = new URL(raw); } catch { return "not a valid address"; }
  const scheme = site.test ? "http:" : "https:";
  if (u.protocol !== scheme) return `only ${scheme}// addresses on ${site.title}`;
  if (u.username || u.password) return "addresses with a user name or password aren't allowed";
  if (u.hostname.toLowerCase() !== site.host) return `that host isn't ${site.title}'s`;
  if (u.port) return "only the default port";
  const path = u.pathname;
  if (/%2e|%2f|%5c|\\/i.test(String(raw).split("?")[0]) || /(^|\/)\.\.?(\/|$)/.test(path)) return "odd path";
  const lower = decodeURIComponentSafe(`${path}${u.search}`).toLowerCase();
  const word = site.blockPaths.find((w) => lower.includes(w));
  if (word) return `addresses with "${word}" are blocked`;
  const same = (a, b) => a === b || a === `${b}/` || `${a}/` === b;
  const isPage = site.pages.some((p) => same(path, p.path) && Object.entries(p.query).every(([k, v]) => u.searchParams.get(k) === v));
  if (isPage) return null;
  if (site.extraPaths.some((re) => re.test(`${path}${u.search}`))) return null;
  return `that page isn't one of ${site.title}'s listed pages`;
}

function decodeURIComponentSafe(s) {
  try { return decodeURIComponent(s); } catch { return s; }
}

const block = (reason) => ({ verdict: "block", reason });
const WEBISH = /^(?:[a-z][a-z0-9+.-]*:|\/\/|www\.)/i;

// Every address-like value in the call: the usual URL fields, and any string that looks like one.
function addresses(params) {
  const out = [];
  for (const k of ["url", "targetUrl", "href", "uri", "link"]) if (typeof params?.[k] === "string") out.push(params[k]);
  for (const s of strings(params)) if (WEBISH.test(s.trim())) out.push(s.trim());
  return [...new Set(out)].map((s) => (/^[a-z][a-z0-9+.-]*:/i.test(s) ? s : `https://${s.replace(/^\/+/, "")}`));
}

/**
 * The site rules for one tool call, or null when the call has nothing to do with site readers.
 * @returns {null | { verdict: "allow"|"block", reason?: string, taint?: string }}
 */
export function siteDecision({ tool, params = {}, agent, sessionKey, sites }) {
  const p = isObj(params) ? params : {};
  const prof = typeof p.profile === "string" ? p.profile.trim().toLowerCase() : "";
  if (agent !== READER_AGENT) {
    if (tool === "browser" && prof.startsWith("site-")) return block("signed-in site browsers are only for the site reader; use site_read");
    if (tool === "sessions_spawn" && String(p.agentId ?? "").toLowerCase() === READER_AGENT) return block("the site reader runs only through site_read");
    if ((tool === "cron" || tool === "automations") && strings(p).some((s) => s.toLowerCase().includes(READER_AGENT))) return block("the site reader can't be scheduled directly");
    return null;
  }
  const name = siteOfSession(sessionKey);
  if (!name) return block("the site reader runs only through site_read");
  // The tool-search wrapper: judge the inner call by the same rules; a wrapper with no named tool is refused.
  if (tool === "tool_call") {
    const raw = typeof p.id === "string" ? p.id : typeof p.name === "string" ? p.name : "";
    const inner = raw.split(":").pop();
    if (!inner || inner === "tool_call") return block("the site reader can only read pages");
    return siteDecision({ tool: inner, params: p.args ?? p.arguments ?? {}, agent, sessionKey, sites });
  }
  const site = sites?.get?.(name);
  if (!site) return block(`no site called ${name}`);
  if (!site.enabled) return block(`${site.title} isn't set up: ${site.disabledReason}`);
  if (tool !== "browser") return block("the site reader can only read pages");
  if (prof !== profileOf(name)) return block(`the site reader must use the ${profileOf(name)} browser`);
  if (p.node != null || (p.target != null && p.target !== "host") || p.dashboard != null) return block("only the site's own browser");
  const action = typeof p.action === "string" ? p.action : "";
  if (!READ_ACTIONS.has(action)) return block(`"${action || "?"}" isn't reading: the site reader can only open and read pages`);
  if (p.request != null || "fn" in p || "expression" in p || "script" in p) return block("only plain reads");
  const urls = addresses(p);
  if (URL_ACTIONS.has(action) && urls.length === 0) return block(`${action} needs one of ${site.title}'s page addresses`);
  for (const u of urls) {
    const bad = checkSiteUrl(site, u);
    if (bad) return block(`Not opened: ${bad}.`);
  }
  return { verdict: "allow", taint: `site ${name}` };
}
