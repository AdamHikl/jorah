// A stand-in for the Mac runner that speaks docs/contracts/jorah-ios-v1.md section 4: unsigned
// health, HMAC-signed POST routes, 401 with no detail for a bad signature, time or nonce. It
// checks signatures independently of the plugin's code, so a signing bug fails the tests.

import { createServer } from "node:http";
import { createHash, createHmac, timingSafeEqual } from "node:crypto";

export const COMMIT = "3f9c2e0d1a4b5c6d7e8f90123456789abcdef012";
export const SHA = "a".repeat(64);

export function deviceRun(over = {}) {
  return {
    run_id: "20261111T213005Z-threadfolio-3f9c2e",
    project: "threadfolio",
    kind: "device",
    configuration: "Debug",
    repo: "AdamHikl/threadfolio",
    commit: COMMIT,
    state: "succeeded",
    tier: "build",
    tier_note: "Built and signed for Development. Not installed, not launched.",
    started_at: "2026-11-11T21:30:05Z",
    finished_at: "2026-11-11T21:36:40Z",
    artifact: { kind: "app", path: "/Users/Shared/jorah-handoff/20261111T213005Z-threadfolio-3f9c2e/Threadfolio.app", bytes: 48213760, sha256: SHA },
    device: null,
    summary: { errors: 0, warnings: 12, first_errors: [] },
    log: { bytes: 31457280, tail: "line\n".repeat(100), complete: true },
    ...over,
  };
}

/**
 * @param {Buffer} key the shared key
 * @param {object} opts contract, hangHealth, hangVerbs (Set), syncCommit, runs (Map), devices, now
 */
export async function startFakeRunner(key, opts = {}) {
  const calls = [];
  const nonces = new Set();
  const runs = opts.runs ?? new Map([[deviceRun().run_id, deviceRun()]]);
  const state = { ...opts };
  const send = (res, status, body) => {
    res.writeHead(status, { "Content-Type": "application/json" });
    res.end(body === undefined ? "" : JSON.stringify(body));
  };
  const envelope = (run) => ({ contract: state.contract ?? "jorah-ios/1", ok: true, run, error: null });
  const fail = (code, message) => ({ contract: "jorah-ios/1", ok: false, run: null, error: { code, message, retryable: false } });

  function verify(req, path, body) {
    const h = req.headers;
    const time = h["x-jorah-time"], nonce = h["x-jorah-nonce"], sig = h["x-jorah-sig"];
    if (h["x-jorah-contract"] !== "jorah-ios/1" || !time || !nonce || !sig) return false;
    const now = Math.floor((state.now ?? Date.now)() / 1000);
    if (Math.abs(now - Number(time)) > 60) return false;
    if (!/^[0-9a-f]{32}$/.test(nonce) || nonces.has(nonce)) return false;
    const want = createHmac("sha256", key).update(`POST\n${path}\n${time}\n${nonce}\n${createHash("sha256").update(body).digest("hex")}`).digest();
    const got = Buffer.from(String(sig), "hex");
    if (got.length !== want.length || !timingSafeEqual(got, want)) return false;
    nonces.add(nonce);
    return true;
  }

  const server = createServer((req, res) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => {
      const body = Buffer.concat(chunks);
      const path = req.url;
      if (req.method === "GET" && path === "/v1/health") {
        calls.push({ verb: "health" });
        if (state.hangHealth) return; // asleep: accepts, never answers
        return send(res, 200, { contract: state.contract ?? "jorah-ios/1", runner_version: "fake", busy: false });
      }
      if (req.method !== "POST" || !path.startsWith("/v1/")) return send(res, 404, fail("BAD_ARGUMENT", "unknown route"));
      if (body.length > 8192) return send(res, 413, fail("BAD_ARGUMENT", "body too large"));
      if (!verify(req, path, body)) { calls.push({ verb: "rejected" }); return send(res, 401); }
      const verb = path.slice(4);
      const p = JSON.parse(body.toString("utf8"));
      calls.push({ verb, body: p });
      if (state.hangVerbs?.has(verb)) { req.socket.destroy(); return; }
      switch (verb) {
        case "sync":
          return send(res, 200, { commit: state.syncCommit ?? COMMIT, repo: `AdamHikl/${p.project}`, default_branch: "main" });
        case "build-sim":
        case "build-device":
        case "archive": {
          const run = { ...deviceRun({ run_id: "20261111T220000Z-threadfolio-abcdef", kind: { "build-sim": "simulator", "build-device": "device", archive: "archive" }[verb], commit: p.commit, configuration: p.configuration }), state: "queued", tier: "none", artifact: null, log: { bytes: 0, tail: "", complete: false }, summary: { errors: null, warnings: null, first_errors: [] } };
          runs.set(run.run_id, run);
          return send(res, 200, envelope(run));
        }
        case "install-device": {
          const build = runs.get(p.build_run_id);
          if (!build) return send(res, 404, fail("RUN_NOT_FOUND", "No such run."));
          const run = { ...build, run_id: "20261111T221000Z-threadfolio-fedcba", build_run_id: p.build_run_id, tier: p.launch ? "launch" : "install", device: { alias: p.device, model: "iPhone 16 Pro", os_version: "26.1" } };
          return send(res, 200, envelope(run));
        }
        case "status":
          if (!p.run_id) return send(res, 200, { contract: "jorah-ios/1", ok: true, runs: [...runs.values()] });
          return runs.has(p.run_id) ? send(res, 200, envelope(runs.get(p.run_id))) : send(res, 404, fail("RUN_NOT_FOUND", "No such run."));
        case "log": {
          const text = state.logText ?? "";
          const bytes = Buffer.from(text);
          const page = bytes.subarray(p.offset, p.offset + p.max_bytes);
          return send(res, 200, { offset: p.offset, bytes: page.length, total_bytes: bytes.length, eof: p.offset + page.length >= bytes.length, text: page.toString("utf8") });
        }
        case "devices":
          return send(res, 200, { devices: state.devices ?? [{ alias: "adam-iphone", model: "iPhone 16 Pro", os_version: "26.1", connected: true }] });
        default:
          return send(res, 400, fail("BAD_ARGUMENT", "unknown verb"));
      }
    });
  });
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  const url = `http://127.0.0.1:${server.address().port}`;
  return {
    url,
    calls,
    runs,
    state,
    verbs: () => calls.map((c) => c.verb),
    close: () => new Promise((r) => { server.closeAllConnections?.(); server.close(() => r()); }),
  };
}
