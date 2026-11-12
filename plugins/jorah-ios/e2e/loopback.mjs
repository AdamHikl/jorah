// End-to-end check of plugins/jorah-ios against the REAL runner (services/ios-runner) on loopback,
// outside the Gateway. Mac only, needs Xcode and a shut-down iPhone simulator. Run: just ios-e2e-local
//
// What it sets up, all in a new temp folder, removed at the end:
// - The fixture app (services/ios-runner/tests/fixtures/Sample) copied into its own git repo, with a
//   local bare repo as `origin`. The runner's `sync` fetches from origin and its build may
//   `git switch --detach`, so it must never point at this checkout. No network is used.
// - A throwaway 32-byte key, a runner allowlist with only that project, simulatorAllowed true,
//   installAllowed false. `jorah-ios-runner serve` on 127.0.0.1, a free port.
// - The plugin, registered against a stand-in for the Gateway's plugin API: it runs the
//   before_tool_call hook, answers the card as the step says, then calls execute, as the Gateway does.
//
// Steps: list simulators; ios_build simulator (card allowed), wait for it; boot, install + launch,
// launch, screenshot, terminate, shutdown (no card, the default); ios_status for the run, the run
// list and a log page; a denied card and a timed-out card (nothing runs); an off-allowlist project
// and injected arguments (refused); a wrong key (runner rejects the signature); the runner stopped
// ("Mac not reachable"). Prints one JSON summary on stdout, temp paths replaced by <temp>.

import { spawn, execFileSync } from "node:child_process";
import { cpSync, mkdtempSync, rmSync, writeFileSync, chmodSync } from "node:fs";
import { randomBytes, createHash } from "node:crypto";
import { tmpdir } from "node:os";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { createPlugin } from "../index.js";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
const RUNNER = join(ROOT, "services/ios-runner");
const FIXTURE = join(RUNNER, "tests/fixtures/Sample");
const tmp = mkdtempSync(join(tmpdir(), "jorah-ios-e2e-"));
const redact = (v) => JSON.parse(JSON.stringify(v ?? null).replaceAll(tmp, "<temp>").replaceAll(tmpdir().replace(/\/$/, ""), "<tmpdir>"));
const log = (...a) => console.error("[e2e]", ...a);
const steps = [];
let failures = 0;

function record(name, pass, info = {}) {
  steps.push({ step: name, pass, ...redact(info) });
  if (!pass) failures++;
  log(`${pass ? "PASS" : "FAIL"} ${name}`);
}

const git = (cwd, ...args) => execFileSync("git", ["-c", "user.name=jorah-e2e", "-c", "user.email=e2e@localhost", "-c", "commit.gpgsign=false", ...args], { cwd, encoding: "utf8" }).trim();

function setupRepo() {
  const origin = join(tmp, "origin.git");
  const clone = join(tmp, "src", "sample");
  git(tmp, "init", "-q", "--bare", "-b", "main", origin);
  cpSync(FIXTURE, clone, { recursive: true });
  git(clone, "init", "-q", "-b", "main");
  git(clone, "add", ".");
  git(clone, "commit", "-q", "-m", "fixture");
  git(clone, "remote", "add", "origin", origin);
  git(clone, "push", "-q", "origin", "main");
  git(clone, "remote", "set-head", "origin", "main");
  return { clone, commit: git(clone, "rev-parse", "HEAD") };
}

function keyFile(name) {
  const f = join(tmp, name);
  writeFileSync(f, randomBytes(32), { mode: 0o600 });
  chmodSync(f, 0o600);
  return f;
}

async function startRunner(clone, key) {
  const config = {
    contract: "jorah-ios/1", installAllowed: false, simulatorAllowed: true,
    stateDir: join(tmp, "state"), handoffDir: join(tmp, "handoff"), keyFile: key,
    listen: { host: "127.0.0.1", port: 0 },
    path: ["/usr/bin", "/bin", "/usr/sbin", "/sbin"],
    projects: { sample: { repo: "AdamHikl/jorah-e2e-sample", path: clone, project: "Sample.xcodeproj", scheme: "Sample", bundleId: "dev.jorah.fixture.sample" } },
  };
  const cfg = join(tmp, "projects.json");
  writeFileSync(cfg, JSON.stringify(config), { mode: 0o600 });
  chmodSync(cfg, 0o600);
  const env = { PATH: "/usr/bin:/bin", HOME: process.env.HOME, TMPDIR: process.env.TMPDIR ?? "/tmp", JORAH_IOS_RUNNER_CONFIG: cfg };
  const child = spawn("python3", ["-I", join(RUNNER, "bin/jorah-ios-runner"), "serve"], { env, stdio: ["ignore", "ignore", "pipe"] });
  const url = await new Promise((ok, fail) => {
    let buf = "";
    const timer = setTimeout(() => fail(new Error(`runner did not start: ${buf}`)), 15000);
    child.stderr.on("data", (d) => {
      buf += d;
      const m = buf.match(/listening on [^\n]*:(\d+)\s*\n/);
      if (m) { clearTimeout(timer); ok(`http://127.0.0.1:${m[1]}`); }
    });
    child.on("exit", (code) => fail(new Error(`runner exited ${code}: ${buf}`)));
  });
  child.stderr.resume();
  const health = await (await fetch(`${url}/v1/health`)).json();
  return { child, url, health };
}

/** The plugin against a stand-in Gateway API. call() = hook, card decision, execute. */
function gateway(pluginConfig) {
  const hooks = {};
  const tools = {};
  createPlugin().register({ pluginConfig, logger: { info() {}, warn() {} }, on: (n, f) => (hooks[n] = f), registerTool: (t) => (tools[t.name] = t) });
  let n = 0;
  async function call(name, params, decision = "allow-once") {
    const id = `e2e-${++n}`;
    const hook = await hooks.before_tool_call({ toolName: name, params, toolCallId: id }, {});
    const card = hook?.requireApproval ? { title: hook.requireApproval.title, description: hook.requireApproval.description } : null;
    if (hook?.block) return { blocked: hook.blockReason, card };
    if (hook?.requireApproval) {
      await hook.requireApproval.onResolution(decision);
      if (decision !== "allow-once") return { denied: decision, card };
    }
    const out = await tools[name].execute(id, params);
    return { card, text: out.content.find((c) => c.type === "text")?.text ?? "", image: out.content.find((c) => c.type === "image") ?? null, details: out.details };
  }
  return { call, tools };
}

// What Jorah would read, cut to the first lines, plus the fields each check looks at.
const short = (r) => ({ card: r.card ? r.card.title : null, blocked: r.blocked, denied: r.denied, ok: r.details?.ok, code: r.details?.error?.code, state: r.details?.run?.state ?? r.details?.state, tier: r.details?.run?.tier, kind: r.details?.run?.kind, text: r.text ? r.text.split("\n").slice(0, 8) : undefined });

async function main() {
  const { clone, commit } = setupRepo();
  const key = keyFile("runner.key");
  const runner = await startRunner(clone, key);
  const base = { runnerUrl: runner.url, keyFile: key, projects: ["sample"] };
  const gw = gateway(base);
  let sim = null;
  let simBooted = false;
  try {
    // Simulators: pick a shut-down iPhone with a unique name and the newest iOS, never one in use.
    const listed = await gw.tools.ios_status.execute("s", { simulators: true });
    const sims = listed.details.simulators ?? [];
    const count = (s) => sims.filter((x) => x.name === s.name && x.os === s.os).length;
    const pick = sims.filter((s) => s.name.startsWith("iPhone") && s.state === "shutdown" && count(s) === 1)
      .sort((a, b) => b.os.localeCompare(a.os, undefined, { numeric: true }))[0];
    record("ios_status simulators", listed.details.ok === true && !!pick, { simulators: sims.length, picked: pick ?? null });
    if (!pick) throw new Error("no shut-down iPhone simulator to use");
    sim = { name: pick.name, os: pick.os };

    // Build, card allowed. The card must name the exact commit sync resolved.
    const built = await gw.call("ios_build", { project: "sample", kind: "simulator" });
    record("ios_build simulator: card names the commit, build starts", built.card?.description.includes(commit) && built.details?.ok === true && ["queued", "running"].includes(built.details.run.state), { ...short(built), card_text: built.card?.description });
    const runId = built.details?.run?.run_id;
    let status;
    for (let i = 0; i < 25 && runId; i++) {
      status = await gw.tools.ios_status.execute("s", { run_id: runId, wait_seconds: 120 });
      if (["succeeded", "failed", "cancelled", "unknown"].includes(status.details.run?.state)) break;
    }
    record("ios_status: build succeeded, tier build, artifact hashed", status?.details.run?.state === "succeeded" && status.details.run.tier === "build" && !!status.details.run.artifact, { state: status?.details.run?.state, tier: status?.details.run?.tier, commit_matches: status?.details.run?.commit === commit, text: status?.content[0].text.split("\n").slice(0, 4) });

    const page = await gw.tools.ios_status.execute("s", { run_id: runId, log: { offset: 0, max_bytes: 4096 } });
    record("ios_status log page: whole lines, untrusted wrapper", page.details.ok === true && page.content[0].text.includes("untrusted build output"), { log: page.details.log, first_line: page.content[0].text.split("\n")[0] });
    const recent = await gw.tools.ios_status.execute("s", {});
    record("ios_status run list", recent.details.ok === true && recent.details.runs.some((r) => r.run_id === runId), { runs: recent.details.runs?.length, text: recent.content[0].text.split("\n") });

    // Simulator actions, no card (the default).
    const boot = await gw.call("ios_install", { simulator: sim, action: "boot" });
    simBooted = boot.details?.ok === true;
    record("simulator boot, no card", boot.card === null && boot.details?.ok === true, short(boot));
    const inst = await gw.call("ios_install", { simulator: sim, run_id: runId, launch: true });
    record("simulator install + launch, no card, tier launch", inst.card === null && inst.details?.ok === true && inst.details.run.tier === "launch" && Number.isInteger(inst.details.run.process_id), short(inst));
    const launch = await gw.call("ios_install", { simulator: sim, action: "launch", project: "sample" });
    record("simulator launch, no card, tier launch", launch.card === null && launch.details?.ok === true && launch.details.run.tier === "launch", short(launch));
    const shot = await gw.call("ios_install", { simulator: sim, action: "screenshot", project: "sample" });
    const png = shot.image ? Buffer.from(shot.image.data, "base64") : null;
    record("simulator screenshot, image shown, sha256 checked, tier none", shot.card === null && !!png && shot.details.run.tier === "none" && createHash("sha256").update(png).digest("hex") === shot.details.run.artifact.sha256, { ...short(shot), png_bytes: png?.length ?? null });
    const again = await gw.tools.ios_status.execute("s", { run_id: shot.details?.run?.run_id, screenshot: { offset: 0, max_bytes: 16384 } });
    record("ios_status screenshot in 16 KiB pages, same image", !!again.content.find((c) => c.type === "image") && again.details.screenshot?.sha256 === shot.details?.run?.artifact?.sha256, { screenshot: again.details.screenshot });
    const term = await gw.call("ios_install", { simulator: sim, action: "terminate", project: "sample" });
    record("simulator terminate, no card", term.card === null && term.details?.ok === true, short(term));
    const down = await gw.call("ios_install", { simulator: sim, action: "shutdown" });
    simBooted = !(down.details?.ok === true);
    record("simulator shutdown, no card", down.card === null && down.details?.ok === true, short(down));

    // Refusals. The run count on the Mac must not change for any of them.
    const runsBefore = (await gw.tools.ios_status.execute("s", {})).details.runs.length;
    const denied = await gw.call("ios_build", { project: "sample", kind: "simulator" }, "deny");
    const timedOut = await gw.call("ios_build", { project: "sample", kind: "device" }, "timeout");
    const forced = await gw.tools.ios_build.execute("e2e-forced", { project: "sample", kind: "simulator" });
    const offList = await gw.call("ios_build", { project: "threadfolio", kind: "simulator" });
    const injected = [
      await gw.call("ios_build", { project: "sample", kind: "simulator", ref: "main; touch /tmp/x" }),
      await gw.call("ios_build", { project: "sample", kind: "simulator", ref: "--upload-pack=touch" }),
      await gw.call("ios_build", { project: "sample", kind: "simulator", configuration: "Debug -allowProvisioningUpdates" }),
      await gw.call("ios_build", { project: "sample", kind: "simulator", scheme: "Other" }),
      await gw.call("ios_install", { simulator: { name: "iPhone 17\"; rm -rf ~", os: "27.0" }, action: "boot" }),
      await gw.call("ios_install", { simulator: sim, action: "screenshot", project: "sample", path: "/etc/passwd" }),
    ];
    const notCarded = await gw.call("ios_install", { simulator: sim, run_id: "20261112T000000Z-sample-000000" });
    const runsAfter = (await gw.tools.ios_status.execute("s", {})).details.runs.length;
    record("denied card: nothing runs", denied.denied === "deny" && !!denied.card, short(denied));
    record("timed-out card: nothing runs", timedOut.denied === "timeout" && !!timedOut.card, short(timedOut));
    record("execute without a card: DENIED", forced.details.error?.code === "DENIED", { code: forced.details.error?.code });
    record("off-allowlist project refused before the Mac", /PROJECT_NOT_ALLOWED/.test(offList.blocked ?? ""), short(offList));
    record("injected arguments refused", injected.every((r) => r.blocked && /BAD_ARGUMENT/.test(r.blocked)), { blocked: injected.map((r) => r.blocked) });
    record("simulator install of a build without a card refused", /NOT_INSTALLABLE/.test(notCarded.blocked ?? ""), short(notCarded));
    record("no run started by any refusal", runsAfter === runsBefore, { runsBefore, runsAfter });

    // Wrong key: the real runner rejects the signature.
    const wrong = gateway({ ...base, keyFile: keyFile("wrong.key") });
    const bad = await wrong.tools.ios_status.execute("s", { simulators: true });
    const badBuild = await wrong.call("ios_build", { project: "sample", kind: "simulator" });
    record("wrong key: AUTH_FAILED, no card", bad.details.error?.code === "AUTH_FAILED" && /AUTH_FAILED/.test(badBuild.blocked ?? ""), { status: bad.details.error?.code, build: badBuild.blocked });
  } catch (error) {
    record("unexpected error", false, { error: String(error?.stack ?? error).split("\n").slice(0, 3) });
  } finally {
    if (simBooted && sim) await gw.call("ios_install", { simulator: sim, action: "shutdown" }).catch(() => {});
    runner.child.kill("SIGTERM");
    await new Promise((r) => runner.child.once("exit", r));
  }

  // The Mac gone: the runner stopped.
  const gone = await gw.tools.ios_status.execute("s", { simulators: true });
  const goneBuild = await gw.call("ios_build", { project: "sample", kind: "simulator" });
  record("runner stopped: Mac not reachable", gone.details.error?.code === "MAC_UNREACHABLE" && /Mac not reachable/.test(gone.content[0].text) && /Mac not reachable/.test(goneBuild.blocked ?? ""), { status: gone.content[0].text, build: goneBuild.blocked });

  const xcode = (() => { try { return execFileSync("xcodebuild", ["-version"], { encoding: "utf8" }).split("\n")[0]; } catch { return null; } })();
  console.log(JSON.stringify(redact({ when: new Date().toISOString(), xcode, runner_health: runner.health, node: process.version, passed: steps.filter((s) => s.pass).length, failed: failures, steps }), null, 2));
  rmSync(tmp, { recursive: true, force: true });
  process.exitCode = failures ? 1 : 0;
}

main();
