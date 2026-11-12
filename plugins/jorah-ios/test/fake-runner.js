// A stand-in for the Mac runner that speaks docs/contracts/jorah-ios-v1.md section 4: unsigned
// health, HMAC-signed POST routes, 401 with no detail for a bad signature, time or nonce. It
// checks signatures independently of the plugin's code, so a signing bug fails the tests.

import { createServer } from "node:http";
import { createHash, createHmac, timingSafeEqual } from "node:crypto";
import { deflateSync } from "node:zlib";

export const COMMIT = "3f9c2e0d1a4b5c6d7e8f90123456789abcdef012";
export const SHA = "a".repeat(64);
export const SIM = { name: "iPhone 17", os: "27.0" };

/** A small real PNG (a solid square), so the plugin's PNG check sees genuine bytes. */
export function png(size = 64) {
  const crcTable = Array.from({ length: 256 }, (_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; });
  const crc = (b) => { let c = 0xffffffff; for (const x of b) c = crcTable[(c ^ x) & 0xff] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
  const chunk = (type, data) => { const len = Buffer.alloc(4); len.writeUInt32BE(data.length); const td = Buffer.concat([Buffer.from(type), data]); const c = Buffer.alloc(4); c.writeUInt32BE(crc(td)); return Buffer.concat([len, td, c]); };
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(size, 0); ihdr.writeUInt32BE(size, 4); ihdr[8] = 8; ihdr[9] = 2;
  const raw = Buffer.alloc(size * (1 + size * 3), 0x7f); for (let y = 0; y < size; y++) raw[y * (1 + size * 3)] = 0;
  return Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), chunk("IHDR", ihdr), chunk("IDAT", deflateSync(raw)), chunk("IEND", Buffer.alloc(0))]);
}
const sha256 = (b) => createHash("sha256").update(b).digest("hex");

export function simBuildRun(over = {}) {
  return deviceRun({ run_id: "20261112T110132Z-threadfolio-376310", kind: "simulator", tier_note: "Built for the simulator. Not installed, not launched.", ...over });
}

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
  const runs = opts.runs ?? new Map([[deviceRun().run_id, deviceRun()], [simBuildRun().run_id, simBuildRun()]]);
  const sims = opts.simulators ?? [{ ...SIM, state: "booted" }, { name: "iPad Air", os: "27.0", state: "shutdown" }];
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
          return send(res, 200, { contract: "jorah-ios/1", ok: true, commit: state.syncCommit ?? COMMIT, repo: `AdamHikl/${p.project}`, default_branch: "main", error: null });
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
          const run = { ...build, run_id: "20261111T221000Z-threadfolio-fedcba", kind: "install", build_run_id: p.build_run_id, tier: p.launch ? "launch" : "install", process_id: p.launch ? 4242 : null, device: { alias: p.device, model: "iPhone 16 Pro", os_version: "26.1" } };
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
          return send(res, 200, { contract: "jorah-ios/1", ok: true, devices: state.devices ?? [{ alias: "adam-iphone", model: "iPhone 16 Pro", os_version: "26.1", connected: true }], error: null });
        // Contract 4a. The fake looks the pair up as the runner does: exactly one match, else SIMULATOR_NOT_FOUND.
        case "sim-list":
          return send(res, 200, { contract: "jorah-ios/1", ok: true, simulators: sims, error: null });
        case "sim-boot":
        case "sim-shutdown":
        case "sim-install":
        case "sim-launch":
        case "sim-terminate":
        case "sim-screenshot": {
          const found = sims.filter((x) => x.name === p.simulator?.name && x.os === p.simulator?.os);
          if (found.length !== 1) return send(res, 200, fail("SIMULATOR_NOT_FOUND", "No such simulator."));
          const sim = found[0];
          const runBase = { project: p.project ?? null, simulator: { ...sim }, summary: { errors: null, warnings: null, first_errors: [] }, started_at: "2026-11-12T11:02:13Z", finished_at: "2026-11-12T11:02:20Z" };
          if (verb === "sim-boot") { sim.state = "booted"; return send(res, 200, { contract: "jorah-ios/1", ok: true, simulator: { ...sim }, error: null }); }
          if (verb === "sim-shutdown") { sim.state = state.shutdownSticks === false ? "booted" : "shutdown"; return send(res, 200, { contract: "jorah-ios/1", ok: true, simulator: { ...sim }, error: null }); }
          if (verb === "sim-terminate") return send(res, 200, { contract: "jorah-ios/1", ok: true, project: p.project, simulator: { ...sim }, terminated: "terminated" in state ? state.terminated : true, error: null });
          if (verb === "sim-install") {
            const build = runs.get(p.build_run_id);
            if (!build) return send(res, 200, fail("RUN_NOT_FOUND", "No such run."));
            if (build.kind !== "simulator" || build.state !== "succeeded") return send(res, 200, fail("NOT_INSTALLABLE", "Not a succeeded simulator build."));
            const run = { ...build, ...runBase, project: build.project, run_id: "20261112T110213Z-threadfolio-dbccd7", kind: "sim-install", build_run_id: p.build_run_id, state: "succeeded", tier: p.launch ? "launch" : "install", process_id: p.launch ? 79575 : null, tier_note: "Installed on the simulator.", ...(state.simInstallOver ?? {}) };
            return send(res, 200, envelope(run));
          }
          if (verb === "sim-launch") {
            const run = { ...runBase, run_id: "20261112T110220Z-threadfolio-aaaa11", kind: "sim-launch", commit: null, configuration: null, artifact: null, state: "succeeded", tier: "launch", process_id: 79600, tier_note: "Launched whatever copy is installed; which build that is was not checked.", ...(state.simLaunchOver ?? {}) };
            return send(res, 200, envelope(run));
          }
          const shot = state.png ?? png();
          state.shot = shot;
          const run = { ...runBase, run_id: "20261112T110229Z-threadfolio-c79f51", kind: "sim-screenshot", commit: null, configuration: null, build_run_id: null, process_id: null, state: "succeeded", tier: "none", tier_note: "A screenshot of the simulator's screen. It proves no install or launch.", artifact: { kind: "png", path: "/Users/Shared/jorah-handoff/20261112T110229Z-threadfolio-c79f51/screenshot.png", bytes: shot.length, sha256: state.reportedSha ?? sha256(shot) }, ...(state.shotOver ?? {}) };
          runs.set(run.run_id, run);
          return send(res, 200, envelope(run));
        }
        case "sim-screenshot-read": {
          const run = runs.get(p.run_id);
          if (!run || run.kind !== "sim-screenshot") return send(res, 200, fail("RUN_NOT_FOUND", "Not a screenshot run."));
          const file = state.servedPng ?? state.shot ?? png();
          const offset = p.offset ?? 0;
          const page = file.subarray(offset, offset + (p.max_bytes ?? 262144));
          return send(res, 200, { contract: "jorah-ios/1", ok: true, run_id: p.run_id, offset, bytes: page.length, total_bytes: file.length, eof: offset + page.length >= file.length, sha256: state.readSha ?? sha256(file), media_type: state.mediaType ?? "image/png", data_base64: page.toString("base64"), error: null });
        }
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
