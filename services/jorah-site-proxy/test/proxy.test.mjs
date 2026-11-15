// The site proxy, with real sockets on loopback. Name lookups and the upstream connection are
// stand-ins, so nothing leaves this machine: "upstream" is a local echo server.

import { test, after } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import net from "node:net";
import { connectTarget, createProxy, privateAddress } from "../proxy.mjs";

const SITES = new Map([
  ["edupage", { name: "edupage", enabled: true, host: "school.edupage.org", extraHosts: ["cdn.edupage.org"], test: null }],
  ["off", { name: "off", enabled: false, host: "off.example", extraHosts: [], test: null }],
  ["fake", { name: "fake", enabled: true, host: "fakeschool.test", extraHosts: [], test: { upstream: "127.0.0.1:0" } }],
]);
const PUBLIC = "93.184.216.34";

const servers = [];
after(() => { for (const s of servers) s.close(); });

function listen(server) {
  servers.push(server);
  return new Promise((ok) => server.listen(0, "127.0.0.1", () => ok(server.address().port)));
}

const echo = net.createServer((s) => s.pipe(s));
const echoPort = await listen(echo);

async function proxy({ lookup = async () => [{ address: PUBLIC, family: 4 }], testSites = false, sites = SITES } = {}) {
  const lines = [];
  const connected = [];
  const p = createProxy({
    sites: () => sites, testSites, log: (l) => lines.push(l), lookup: async (h) => lookup(h),
    connect: (o) => { connected.push(o); return net.connect({ host: "127.0.0.1", port: echoPort }); },
  });
  return { port: await listen(p), lines, connected };
}

// Send a CONNECT and return the status line, plus the socket for the tunnel.
function connectThrough(port, target) {
  return new Promise((ok, fail) => {
    const s = net.connect(port, "127.0.0.1", () => s.write(`CONNECT ${target} HTTP/1.1\r\nHost: ${target}\r\n\r\n`));
    let buf = "";
    s.on("data", function first(d) {
      buf += d.toString();
      if (!buf.includes("\r\n\r\n")) return;
      s.off("data", first);
      ok({ status: buf.split("\r\n")[0], socket: s });
    });
    s.on("error", fail);
    s.on("end", () => ok({ status: buf.split("\r\n")[0] || "closed", socket: s }));
  });
}

test("a site's own host on 443 gets a working tunnel to its public address", async () => {
  const p = await proxy();
  for (const target of ["school.edupage.org:443", "SCHOOL.EDUPAGE.ORG:443", "cdn.edupage.org:443"]) {
    const { status, socket } = await connectThrough(p.port, target);
    assert.match(status, / 200 /, target);
    socket.write("ping");
    const back = await new Promise((ok) => socket.once("data", (d) => ok(d.toString())));
    assert.equal(back, "ping");
    socket.destroy();
  }
  assert.ok(p.connected.every((o) => o.host === PUBLIC && o.port === 443));
  assert.ok(p.lines.every((l) => !l.includes("school.edupage.org")), "allowed tunnels log the site's name only");
});

test("everything else is refused before any connection is made", async () => {
  const p = await proxy();
  const refused = [
    "evil.example:443", "school.edupage.org:80", "school.edupage.org:8443", "school.edupage.org.:443", "edupage.org:443",
    "school.edupage.org.evil.example:443", `${PUBLIC}:443`, "[::1]:443", "127.0.0.1:43181", "off.example:443",
    "fakeschool.test:443", "school.edupage.org", "school.edupage.org:443/x", "school edupage.org:443",
  ];
  for (const target of refused) {
    const { status, socket } = await connectThrough(p.port, target);
    // A request line that isn't valid HTTP is dropped without an answer, which is a refusal too.
    assert.match(status, /40[03]|^closed$/, target);
    socket.destroy();
  }
  assert.equal(p.connected.length, 0);
  assert.ok(p.lines.some((l) => l.startsWith("deny evil.example")));
});

test("a site name that resolves to a private address is refused (DNS rebinding)", async () => {
  for (const addrs of [["127.0.0.1"], ["10.0.0.5"], ["192.168.0.1"], ["100.100.1.1"], [PUBLIC, "169.254.169.254"], ["::1"], ["fd00::1"], ["::ffff:127.0.0.1"], []]) {
    const p = await proxy({ lookup: async () => addrs.map((address) => ({ address, family: net.isIP(address) })) });
    const { status, socket } = await connectThrough(p.port, "school.edupage.org:443");
    assert.match(status, / 403 /, addrs.join(","));
    assert.equal(p.connected.length, 0);
    socket.destroy();
  }
  const p = await proxy({ lookup: async () => { throw new Error("ENOTFOUND"); } });
  const { status, socket } = await connectThrough(p.port, "school.edupage.org:443");
  assert.match(status, / 403 /);
  socket.destroy();
});

function get(port, url) {
  return new Promise((ok, fail) => {
    const r = http.request({ host: "127.0.0.1", port, method: "GET", path: url, headers: { host: new URL(url).host } }, (res) => {
      let body = "";
      res.on("data", (d) => { body += d; });
      res.on("end", () => ok({ status: res.statusCode, body }));
    });
    r.on("error", fail);
    r.end();
  });
}

test("plain http is refused, test sites included, unless test sites are on", async () => {
  const p = await proxy();
  for (const url of ["http://evil.example/", "http://school.edupage.org/user/", "http://fakeschool.test/user/"]) {
    assert.equal((await get(p.port, url)).status, 403, url);
  }
});

test("test sites (jorah-dev only) reach their fake upstream over plain http", async () => {
  const fake = http.createServer((req, res) => res.end(`fake ${req.headers.host} ${req.url}`));
  const fakePort = await listen(fake);
  const sites = new Map(SITES);
  sites.set("fake", { ...SITES.get("fake"), test: { upstream: `127.0.0.1:${fakePort}` } });
  const p = await proxy({ testSites: true, sites });
  const ok = await get(p.port, "http://fakeschool.test/user/?a=1");
  assert.equal(ok.status, 200);
  assert.equal(ok.body, "fake fakeschool.test /user/?a=1");
  assert.equal((await get(p.port, "http://evil.example/")).status, 403);
  assert.equal((await get(p.port, "http://fakeschool.test:8080/")).status, 403);
  // A test site never gets a CONNECT tunnel.
  const { status, socket } = await connectThrough(p.port, "fakeschool.test:443");
  assert.match(status, / 403 /);
  socket.destroy();
});

test("helpers: target parsing and private addresses", () => {
  assert.deepEqual(connectTarget("School.Edupage.org:443"), { host: "school.edupage.org", port: 443 });
  for (const t of ["1.2.3.4:443", "[::1]:443", "a:b", "", null, "host:443:1", "ho st:443"]) assert.equal(connectTarget(t), null, String(t));
  for (const ip of ["127.0.0.1", "10.1.2.3", "172.16.0.1", "172.31.255.255", "192.168.1.1", "100.64.0.1", "169.254.1.1", "0.0.0.0", "224.0.0.1",
    "198.18.0.1", "::1", "::", "fe80::1", "fc00::1", "ff02::1", "::ffff:10.0.0.1", "not-an-ip"]) assert.equal(privateAddress(ip), true, ip);
  for (const ip of [PUBLIC, "1.1.1.1", "172.32.0.1", "100.128.0.1", "2a00:1450:4001::200e"]) assert.equal(privateAddress(ip), false, ip);
});
