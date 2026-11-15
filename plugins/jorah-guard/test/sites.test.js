// Site reader rules (lib/sites.js), with a fully hijacked model: every call below is what an
// attacker would want the site reader, or another agent, to do with a signed-in site browser.
// Pass means the guard decides as the rules say, never that a model refused.

import { test } from "node:test";
import assert from "node:assert/strict";
import { cpSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import {
  allowedHosts, checkSiteUrl, loadSites, pageUrls, parseSite, profileOf, READER_AGENT, sessionKeyFor, siteDecision, siteOfSession,
} from "../lib/sites.js";
import { decide } from "../lib/policy.js";
import { GuardState } from "../lib/state.js";
import plugin from "../index.js";

const here = dirname(fileURLToPath(import.meta.url));
const ROOT = join(here, "..", "..", "..");
const SITES = join(ROOT, "config", "sites");
const MATRIX_FILE = join(ROOT, "config", "permission-matrix.json");
const matrix = JSON.parse(readFileSync(MATRIX_FILE, "utf8"));
const HOST = "school.edupage.org";
const NONCE = "0123456789abcdef0123";
const KEY = sessionKeyFor("edupage", NONCE);
const READER = { agentId: READER_AGENT, sessionKey: KEY, requester: { senderIsOwner: false } };
const MAIN = { agentId: "main", sessionKey: "agent:main:main", requester: { channel: "telegram", senderId: "owner-id", senderIsOwner: true } };
const DEEP = { agentId: "deep", sessionKey: "agent:deep:subagent:1", requester: { senderIsOwner: false } };
const T = `https://${HOST}/dashboard/eb.php?mode=ttday`;
const G = `https://${HOST}/znamky/`;

function privateFile(sites) {
  const dir = mkdtempSync(join(tmpdir(), "jorah-sites-"));
  const file = join(dir, "sites.private.json");
  writeFileSync(file, JSON.stringify({ version: 1, sites }));
  return file;
}

function loaded(sites = { edupage: { host: HOST } }) {
  const r = loadSites({ dir: SITES, privateFile: privateFile(sites) });
  assert.deepEqual(r.errors, []);
  return r.sites;
}

const sites = loaded();
const reader = (params, tool = "browser", ctx = READER, s = sites) => siteDecision({ tool, params, agent: ctx.agentId, sessionKey: ctx.sessionKey, sites: s });
const nav = (url, extra = {}) => ({ action: "navigate", profile: "site-edupage", url, ...extra });

// --- the site files ---------------------------------------------------------------------------

test("sites: the repo's files load; templates and the private example are skipped", () => {
  assert.deepEqual([...sites.keys()], ["edupage"]);
  const s = sites.get("edupage");
  assert.equal(s.enabled, true);
  assert.equal(s.host, HOST);
  assert.equal(s.cdpPort, 43220);
  assert.deepEqual(pageUrls(s).map((p) => p.url), [T, G, `https://${HOST}/user/`]);
  assert.deepEqual([...allowedHosts(sites).keys()], [HOST]);
});

test("sites: without the private file EduPage is off, and the reader is refused", () => {
  const { sites: off } = loadSites({ dir: SITES, privateFile: join(tmpdir(), "nope-sites.json") });
  assert.equal(off.get("edupage").enabled, false);
  assert.equal(allowedHosts(off).size, 0);
  assert.match(reader(nav(T), "browser", READER, off).reason, /isn't set up/);
});

test("sites: a private host must match the site's pattern", () => {
  for (const host of ["evil.example", "school.edupage.org.evil.example", "edupage.org", "a.b.edupage.org", "SCHOOL.edupage.org.", "x_y.edupage.org"]) {
    const { sites: s } = loadSites({ dir: SITES, privateFile: privateFile({ edupage: { host } }) });
    assert.equal(s.get("edupage").enabled, false, host);
  }
  const { sites: off } = loadSites({ dir: SITES, privateFile: privateFile({ edupage: { host: HOST, enabled: false } }) });
  assert.equal(off.get("edupage").enabled, false);
});

test("sites: a broken private file disables private sites and is reported", () => {
  const dir = mkdtempSync(join(tmpdir(), "jorah-sites-"));
  writeFileSync(join(dir, "p.json"), "{ not json");
  const r = loadSites({ dir: SITES, privateFile: join(dir, "p.json") });
  assert.match(r.errors.join(), /private file/);
  assert.equal(r.sites.get("edupage").enabled, false);
});

function siteFile(over) {
  const base = JSON.parse(readFileSync(join(SITES, "_template.json"), "utf8"));
  return { ...base, ...over };
}

test("sites: each malformed file is refused with a reason", () => {
  const bad = [
    [{ extra: 1 }, /unknown field/],
    [{ version: 2 }, /version/],
    [{ name: "Example" }, /name/],
    [{ name: "other" }, /file name/],
    [{ host: "https://www.example.com" }, /host/],
    [{ host: { from: "private", pattern: ".*" } }, /anchored/],
    [{ cdpPort: 43190 }, /cdpPort/],
    [{ pages: [] }, /pages/],
    [{ pages: [{ id: "aa", path: "/x/../y", about: "x" }] }, /path/],
    [{ pages: [{ id: "aa", path: "relative", about: "x" }] }, /path/],
    [{ pages: [{ id: "aa", path: "/x%2f", about: "x" }] }, /path/],
    [{ pages: [{ id: "aa", path: "/x", about: "x" }, { id: "aa", path: "/y", about: "y" }] }, /unique/],
    [{ pages: [{ id: "aa", path: "/x", about: "x", script: "y" }] }, /unknown field/],
    [{ kinds: ["email"] }, /kinds/],
    [{ extraPaths: ["(unclosed"] }, /valid pattern/],
    [{ test: { upstream: "127.0.0.1:43228" } }, /jorah-dev/],
  ];
  for (const [over, re] of bad) assert.throws(() => parseSite(siteFile(over), "/x/example.json"), re, JSON.stringify(over));
  assert.equal(parseSite(siteFile({}), "/x/example.json").enabled, true);
});

test("sites: two sites can't share a browser port", () => {
  const dir = mkdtempSync(join(tmpdir(), "jorah-sites-dir-"));
  cpSync(join(SITES, "edupage.json"), join(dir, "edupage.json"));
  writeFileSync(join(dir, "other.json"), JSON.stringify(siteFile({ name: "other", cdpPort: 43220 })));
  const r = loadSites({ dir, privateFile: privateFile({ edupage: { host: HOST } }) });
  assert.match(r.errors.join(), /cdpPort 43220/);
  assert.equal(r.sites.has("other"), false);
});

test("sites: only jorah-sites' session keys count as a site session", () => {
  assert.equal(siteOfSession(KEY), "edupage");
  for (const k of ["agent:reader-site:main", "agent:reader-site:subagent:0123456789abcdef", "agent:main:site:edupage:0123456789abcdef",
    "agent:reader-site:site:edupage:SHORT", "agent:reader-site:site:edupage:0123456789ABCDEF", "agent:reader-site:site:edupage:0123456789abcdef:x",
    "agent:reader-site:site:../x:0123456789abcdef", "", null]) assert.equal(siteOfSession(k), null, String(k));
});

// --- the reader may only read -------------------------------------------------------------

test("reader: opens and reads the listed pages", () => {
  for (const p of [nav(T), nav(`${T}&date=2026-11-16`), nav(G), nav(`https://${HOST}/znamky`), { action: "open", profile: "site-edupage", url: `https://${HOST}/user/` },
    { action: "snapshot", profile: "site-edupage" }, { action: "text", profile: "site-edupage", maxChars: 6000 },
    { action: "screenshot", profile: "site-edupage" }, { action: "tabs", profile: "site-edupage" }, { action: "close", profile: "site-edupage", targetId: "t1" },
    { action: "focus", profile: "site-edupage", targetId: "t1" }, { action: "status", profile: "site-edupage" },
    { action: "snapshot", profile: "site-edupage", query: "Matematika" }]) {
    const d = reader(p);
    assert.equal(d.verdict, "allow", JSON.stringify(p));
    assert.equal(d.taint, "site edupage");
  }
});

test("reader: no clicking, typing, forms, keys, scripts, uploads or network logs", () => {
  const acts = ["click", "type", "fill", "press", "select", "drag", "hover", "evaluate", "upload", "wait", "resize", "scrollIntoView"];
  for (const kind of acts) {
    assert.equal(reader({ action: "act", profile: "site-edupage", request: { kind, ref: "e12", text: "hi" } }).verdict, "block", kind);
  }
  for (const action of ["requests", "errors", "emulate", "doctor", "start", "stop", "upload", "dialog", "pdf", "cookies", "console", "download", "", undefined]) {
    assert.equal(reader({ action, profile: "site-edupage" }).verdict, "block", String(action));
  }
  // A read action carrying an act request, a function or a script is refused too.
  assert.equal(reader({ action: "snapshot", profile: "site-edupage", request: { kind: "click", ref: "e1" } }).verdict, "block");
  assert.equal(reader({ action: "text", profile: "site-edupage", fn: "() => fetch('https://evil.example')" }).verdict, "block");
  assert.equal(reader({ action: "snapshot", profile: "site-edupage", expression: "document.cookie" }).verdict, "block");
});

test("reader: only its own site's browser, on the Gateway host", () => {
  assert.match(reader({ action: "navigate", url: T }).reason, /site-edupage browser/);
  assert.match(reader(nav(T, { profile: "openclaw" })).reason, /site-edupage browser/);
  assert.match(reader(nav(T, { profile: "site-other" })).reason, /site-edupage browser/);
  assert.match(reader(nav(T, { profile: "user" })).reason, /site-edupage browser/);
  assert.match(reader(nav(T, { target: "node" })).reason, /own browser/);
  assert.match(reader(nav(T, { node: "iphone" })).reason, /own browser/);
  assert.match(reader({ action: "snapshot", profile: "site-edupage", dashboard: "x" }).reason, /own browser/);
  assert.equal(reader(nav(T, { target: "host" })).verdict, "allow");
});

test("reader: only the listed pages on the site's own host", () => {
  const bad = [
    "https://evil.example/", `http://${HOST}/znamky/`, `https://${HOST}.evil.example/znamky/`, "https://other.edupage.org/znamky/",
    `https://user:pw@${HOST}/znamky/`, `https://${HOST}:8443/znamky/`, `https://${HOST}/login/logout.php`, `https://${HOST}/user/?akcia=delete`,
    `https://${HOST}/messages/`, `https://${HOST}/user/../messages/`, `https://${HOST}/%2e%2e/messages/`, `https://${HOST}/user/%2fmessages`,
    `https://${HOST}/dashboard/eb.php?mode=other`, `https://${HOST}/dashboard/eb.php`, `https://${HOST}/user/?cmd=SendMessage`,
    `https://${HOST}/znamky/?x=odhlasit`, "javascript:alert(1)", "data:text/html,<script>fetch('https://evil.example')</script>",
    "file:///etc/passwd", "chrome://settings", "view-source:https://evil.example", "evil.example/x", "//evil.example/x", "http://127.0.0.1:43181/",
  ];
  for (const url of bad) assert.equal(reader(nav(url)).verdict, "block", url);
  assert.match(reader({ action: "navigate", profile: "site-edupage" }).reason, /needs one of/);
});

test("reader: an address hidden in any other field is checked too", () => {
  assert.equal(reader({ action: "snapshot", profile: "site-edupage", selector: "https://evil.example/x" }).verdict, "block");
  assert.equal(reader({ action: "text", profile: "site-edupage", selector: "www.evil.example" }).verdict, "block");
  assert.equal(reader({ action: "open", profile: "site-edupage", url: G, targetUrl: "https://evil.example/" }).verdict, "block");
  assert.equal(reader({ action: "navigate", profile: "site-edupage", url: G, extra: { href: "https://evil.example" } }).verdict, "block");
});

test("reader: no other tool, and the search wrapper is judged by its inner call", () => {
  for (const tool of ["web_fetch", "web_search", "message", "exec", "process", "read", "write", "edit", "memory_search", "memory_get",
    "sessions_spawn", "sessions_send", "cron", "automations", "site_read", "sites_list", "github_push_branch", "nodes", "x_search"]) {
    assert.equal(reader({ url: T }, tool).verdict, "block", tool);
  }
  assert.equal(reader({ id: "openclaw:core:browser", args: nav(T) }, "tool_call").verdict, "allow");
  assert.equal(reader({ id: "browser", args: { action: "act", profile: "site-edupage", request: { kind: "click", ref: "e1" } } }, "tool_call").verdict, "block");
  assert.equal(reader({ id: "web_fetch", args: { url: T } }, "tool_call").verdict, "block");
  assert.equal(reader({ query: "browser" }, "tool_call").verdict, "block");
});

test("reader: only in a session jorah-sites started, for a site that exists and is set up", () => {
  for (const sessionKey of ["agent:reader-site:main", "agent:reader-site:subagent:abc", "agent:reader-site:cron:x", "hook:x"]) {
    assert.match(reader(nav(T), "browser", { agentId: READER_AGENT, sessionKey }).reason, /only through site_read/);
  }
  assert.match(reader(nav(T), "browser", { agentId: READER_AGENT, sessionKey: sessionKeyFor("bank", NONCE) }).reason, /no site called bank/);
  // A session for one site can't read another site's pages.
  const two = loaded({ edupage: { host: HOST } });
  two.set("other", { ...two.get("edupage"), name: "other", title: "Other", host: "other.example" });
  const ctx = { agentId: READER_AGENT, sessionKey: KEY };
  assert.equal(reader(nav("https://other.example/znamky/", { profile: "site-other" }), "browser", ctx, two).verdict, "block");
});

// --- nobody else may reach for a site browser or start the reader ----------------------------

test("others: no agent but the reader may use a site browser", () => {
  for (const ctx of [MAIN, DEEP, { agentId: "background", sessionKey: "agent:background:subagent:2" }, { agentId: undefined, sessionKey: "x" }]) {
    for (const profile of ["site-edupage", "SITE-EDUPAGE", " site-edupage ", "site-anything"]) {
      assert.match(reader({ action: "snapshot", profile }, "browser", ctx).reason, /only for the site reader/, `${ctx.agentId} ${profile}`);
    }
  }
  // Their ordinary browser is not a site matter.
  assert.equal(reader({ action: "navigate", url: "https://wttr.in" }, "browser", MAIN), null);
});

test("others: the reader can't be spawned or scheduled", () => {
  assert.match(reader({ agentId: "reader-site", task: "read edupage" }, "sessions_spawn", MAIN).reason, /only through site_read/);
  assert.match(reader({ agentId: "Reader-Site", task: "x" }, "sessions_spawn", DEEP).reason, /only through site_read/);
  assert.match(reader({ action: "add", job: { agentId: "reader-site", message: "x" } }, "cron", MAIN).reason, /scheduled/);
  assert.equal(reader({ agentId: "deep", task: "x" }, "sessions_spawn", MAIN), null);
});

// --- through the guard's full decision ------------------------------------------------------

function guard() {
  const dir = mkdtempSync(join(tmpdir(), "jorah-guard-sites-"));
  const state = new GuardState(dir);
  const view = {
    taintOf: (k) => state.taintOf(k), hasSeen: (k, u) => state.hasSeen(k, u), wordsOf: (k) => state.wordsOf(k),
    readRepos: (k) => state.readRepos(k), countAcp: (k) => state.countAcp(k), frozen: () => state.frozen(),
  };
  const settings = { workspace: "/home/jorah/workspace", cleanSessionKeys: ["agent:main:main"], sites: () => sites };
  return { state, run: (tool, params, ctx) => decide({ tool, params, ctx, matrix, view, settings }) };
}

test("guard: the site rules hold inside decide(), and site_read taints the chat", () => {
  const g = guard();
  assert.equal(g.run("browser", nav(T), READER).verdict, "allow");
  assert.equal(g.run("browser", { action: "act", profile: "site-edupage", request: { kind: "type", text: "hi" } }, READER).verdict, "block");
  assert.equal(g.run("browser", { action: "snapshot", profile: "site-edupage" }, MAIN).verdict, "block");
  assert.equal(g.run("sites_list", {}, MAIN).verdict, "allow");
  const r = g.run("site_read", { site: "edupage", pages: ["timetable"] }, MAIN);
  assert.equal(r.verdict, "allow");
  assert.equal(r.taint, "site_read");
  // The guard's own rules still apply to main's ordinary browser.
  assert.equal(g.run("browser", { action: "navigate", url: "http://127.0.0.1:43220/json" }, MAIN).verdict, "block");
});

test("guard: a frozen Jorah doesn't read signed-in sites", () => {
  const g = guard();
  g.state.freeze("test");
  assert.match(g.run("browser", nav(T), READER).reason, /frozen/);
  assert.equal(g.run("site_read", { site: "edupage" }, MAIN).verdict, "block");
});

test("guard: no site list (missing setting) means no site is set up", () => {
  const dir = mkdtempSync(join(tmpdir(), "jorah-guard-sites-"));
  const state = new GuardState(dir);
  const view = { taintOf: () => null, hasSeen: () => false, wordsOf: () => "", readRepos: () => [], countAcp: () => 0, frozen: () => state.frozen() };
  const d = decide({ tool: "browser", params: nav(T), ctx: READER, matrix, view, settings: {} });
  assert.match(d.reason, /no site called edupage/);
});

test("plugin: loads the site files from its config and enforces them", () => {
  const dir = mkdtempSync(join(tmpdir(), "jorah-guard-plugin-sites-"));
  const hooks = {};
  plugin.register({
    pluginConfig: { stateDir: dir, matrixFile: MATRIX_FILE, sitesDir: SITES, sitesPrivateFile: privateFile({ edupage: { host: HOST } }) },
    logger: { info() {}, warn() {} }, on: (n, fn) => { (hooks[n] ??= []).push(fn); }, registerCommand() {},
  });
  const call = (ev, ctx) => hooks.before_tool_call[0](ev, ctx);
  assert.equal(call({ toolName: "browser", params: nav(G) }, READER), undefined);
  assert.equal(call({ toolName: "browser", params: nav("https://evil.example/") }, READER).block, true);
  assert.equal(call({ toolName: "browser", params: { action: "act", profile: "site-edupage", request: { kind: "click", ref: "e3" } } }, READER).block, true);
  assert.equal(call({ toolName: "browser", params: { action: "snapshot", profile: "site-edupage" } }, MAIN).block, true);
  const log = readFileSync(join(dir, "decisions.jsonl"), "utf8");
  assert.match(log, /reader-site/);
  assert.ok(!log.includes("evil.example"), "the log keeps no addresses");
});

test("checkSiteUrl: unparseable and odd input is refused, never thrown", () => {
  const s = sites.get("edupage");
  for (const raw of ["", "not a url", "https://", `https://${HOST}/%E0%A4%A`, `https://${HOST}\\znamky`]) assert.equal(typeof checkSiteUrl(s, raw), "string", raw);
  assert.equal(profileOf("edupage"), "site-edupage");
});
