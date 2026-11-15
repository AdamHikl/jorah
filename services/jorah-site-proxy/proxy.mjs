#!/usr/bin/env node
// The site browsers' only way out (docs/runbooks/site-readers.md). Each signed-in site browser runs
// as the jorah-sites user, whose firewall rule lets it reach this proxy and nothing else. The proxy
// lets it tunnel (HTTPS CONNECT) only to the hosts named in config/sites, on port 443, and only when
// every address the name resolves to is public. So a hostile page in a signed-in browser can't send
// what it reads anywhere but the site itself. Node's standard library only, no packages.
//
//   node proxy.mjs --listen 127.0.0.1:43219 --sites /opt/jorah/config/sites \
//                  --private /etc/jorah/sites.private.json [--test-sites]
//
// --test-sites (jorah-dev only) also loads test sites and forwards plain-http requests for them to
// their fake upstream on loopback. The log names refused hosts (chosen by whoever tried) and, for
// allowed tunnels, only the site's name.

import http from "node:http";
import net from "node:net";
import dns from "node:dns/promises";
import { fileURLToPath } from "node:url";
import { allowedHosts, loadSites } from "../../plugins/jorah-guard/lib/sites.js";

const IDLE_MS = 120_000;
const MAX_SOCKETS = 64;

// Addresses a tunnel may never reach, whatever name led there (DNS rebinding included).
export function privateAddress(ip) {
  const kind = net.isIP(ip);
  if (kind === 4) {
    const [a, b] = ip.split(".").map(Number);
    return a === 0 || a === 10 || a === 127 || (a === 100 && b >= 64 && b <= 127) || (a === 169 && b === 254) ||
      (a === 172 && b >= 16 && b <= 31) || (a === 192 && (b === 168 || b === 0)) || (a === 198 && (b === 18 || b === 19)) || a >= 224;
  }
  if (kind === 6) {
    const h = ip.toLowerCase();
    if (h === "::" || h === "::1") return true;
    const mapped = /^::ffff:(\d+\.\d+\.\d+\.\d+)$/.exec(h);
    if (mapped) return privateAddress(mapped[1]);
    return /^f[cd]/.test(h) || /^fe[89ab]/.test(h) || /^ff/.test(h) || h.startsWith("64:ff9b:") || h.startsWith("2001:db8:");
  }
  return true; // not an address at all
}

const HOST_RE = /^[a-z0-9.-]{1,253}$/;

/** Parse "host:port" from a CONNECT line. Returns null for anything else (IP literals included). */
export function connectTarget(raw) {
  const m = /^([^:\s/[\]]+):(\d{1,5})$/.exec(String(raw ?? ""));
  if (!m) return null;
  const host = m[1].toLowerCase();
  if (!HOST_RE.test(host) || host.endsWith(".") || net.isIP(host)) return null;
  return { host, port: Number(m[2]) };
}

function siteNameOf(host, sitesMap) {
  for (const s of sitesMap.values()) if (s.enabled && (s.host === host || s.extraHosts.includes(host))) return s.name;
  return "?";
}

/**
 * @param {{ sites: () => Map, lookup?: Function, connect?: Function, log?: Function, testSites?: boolean }} opts
 */
export function createProxy({ sites, lookup = (h) => dns.lookup(h, { all: true, verbatim: true }), connect = (o) => net.connect(o), log = (l) => console.log(l), testSites = false }) {
  const server = http.createServer((req, res) => {
    // Plain http: refused, except a test site's fake upstream on jorah-dev.
    let target = null;
    try { target = new URL(req.url); } catch { /* origin-form or junk */ }
    const host = target?.hostname?.toLowerCase();
    const rule = host ? allowedHosts(sites()).get(host) : null;
    if (!testSites || !rule?.upstream || target.protocol !== "http:" || target.port) {
      log(`deny http ${host ?? "?"}`);
      res.writeHead(403, { "content-type": "text/plain", connection: "close" }).end("Blocked by Jorah's site proxy.\n");
      return;
    }
    const [uh, up] = rule.upstream.split(":");
    const headers = { ...req.headers, host };
    delete headers["proxy-connection"];
    delete headers["proxy-authorization"];
    const out = http.request({ host: uh, port: Number(up), method: req.method, path: `${target.pathname}${target.search}`, headers }, (r) => {
      res.writeHead(r.statusCode ?? 502, r.headers);
      r.pipe(res);
    });
    out.on("error", () => { if (!res.headersSent) res.writeHead(502).end(); else res.destroy(); });
    req.pipe(out);
    log(`allow http test ${siteNameOf(host, sites())}`);
  });

  server.maxConnections = MAX_SOCKETS;

  server.on("connect", async (req, client, head) => {
    const refuse = (why, who) => {
      log(`deny ${who ?? "?"} ${why}`);
      if (!client.destroyed) client.end("HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n");
    };
    client.on("error", () => client.destroy());
    const t = connectTarget(req.url);
    if (!t) return refuse("not a host name and port", String(req.url ?? "").slice(0, 80));
    const current = sites();
    const rule = allowedHosts(current).get(t.host);
    if (!rule || rule.upstream) return refuse("not a site host", t.host);
    if (t.port !== 443) return refuse(`port ${t.port}`, t.host);
    let addrs;
    try {
      addrs = await lookup(t.host);
    } catch {
      return refuse("name not found", t.host);
    }
    const list = (Array.isArray(addrs) ? addrs : [addrs]).map((a) => (typeof a === "string" ? a : a?.address)).filter(Boolean);
    if (list.length === 0 || list.some(privateAddress)) return refuse("resolves to a private address", t.host);
    const upstream = connect({ host: list[0], port: 443 });
    upstream.setTimeout(IDLE_MS, () => upstream.destroy());
    client.setTimeout(IDLE_MS, () => client.destroy());
    upstream.on("error", () => { if (!client.destroyed) client.end("HTTP/1.1 502 Bad Gateway\r\n\r\n"); });
    upstream.on("connect", () => {
      client.write("HTTP/1.1 200 Connection Established\r\n\r\n");
      if (head?.length) upstream.write(head);
      upstream.pipe(client);
      client.pipe(upstream);
      log(`allow ${siteNameOf(t.host, current)}`);
    });
    client.on("close", () => upstream.destroy());
    upstream.on("close", () => client.destroy());
  });

  server.on("clientError", (_e, socket) => socket.destroy());
  return server;
}

function args(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--test-sites") out.testSites = true;
    else if (["--listen", "--sites", "--private"].includes(a)) out[a.slice(2)] = argv[++i];
    else throw new Error(`unknown argument ${a}`);
  }
  return out;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const a = args(process.argv.slice(2));
  const [host, port] = String(a.listen ?? "127.0.0.1:43219").split(":");
  if (host !== "127.0.0.1") throw new Error("the proxy listens on 127.0.0.1 only");
  let cache = { at: 0, value: new Map(), errors: "" };
  const sites = () => {
    if (Date.now() - cache.at < 30_000) return cache.value;
    const r = loadSites({ dir: a.sites ?? "/opt/jorah/config/sites", privateFile: a.private ?? "/etc/jorah/sites.private.json", allowTest: a.testSites === true });
    const e = r.errors.join("; ");
    if (e && e !== cache.errors) console.error(`site files: ${e}`);
    cache = { at: Date.now(), value: r.sites, errors: e };
    return r.sites;
  };
  const server = createProxy({ sites, testSites: a.testSites === true });
  server.listen(Number(port), host, () => {
    const names = [...sites().values()].filter((s) => s.enabled).map((s) => s.name);
    console.log(`jorah-site-proxy on ${host}:${port}; sites: ${names.join(", ") || "none set up"}${a.testSites ? "; TEST SITES ON" : ""}`);
  });
  for (const sig of ["SIGTERM", "SIGINT"]) process.on(sig, () => server.close(() => process.exit(0)));
}
