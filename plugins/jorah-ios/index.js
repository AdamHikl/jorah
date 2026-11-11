// OpenClaw plugin: Jorah's iOS tools (docs/contracts/jorah-ios-v1.md, route 2 of ADR 0002).
// ios_build and ios_install wait for Adam's card; ios_status only reads. Plain object entry, the
// same shape definePluginEntry returns, so it needs no build or install step. The runner on the
// Mac decides what may run; this plugin refuses early and makes sure Adam saw exactly what runs.
//
// The card binds the call: the hook resolves the commit (runner `sync`) or the build being
// installed, records it with the decision from onResolution, and execute sends exactly that, once.
// No record, a record that wasn't allow-once, or one already used means nothing is sent.

import { IosError, checkBuild, checkCommit, checkInstall, checkStatus, describeRun, handoffFolder, readRun, runnerClient, settings, trimPage, untrusted, verbForKind } from "./ios.js";

const TOOLS = new Set(["ios_build", "ios_install"]);
const CARD_TIMEOUT_MS = 10 * 60 * 1000;
// An approval is good for one call, and only shortly after its card: never a job that fires later.
const APPROVAL_TTL_MS = CARD_TIMEOUT_MS + 2 * 60 * 1000;
const INSTALL_TIMEOUT_MS = 6 * 60 * 1000;
const BUILD_START_TIMEOUT_MS = 30 * 1000;

const result = (text, details) => ({ content: [{ type: "text", text }], details: { contract: "jorah-ios/1", ...details } });
const failure = (error) => {
  const e = error instanceof IosError ? error : new IosError("RUNNER_ERROR", String(error?.message ?? error).split("\n")[0].slice(0, 300));
  return { ok: false, run: null, error: { code: e.code, message: e.message, retryable: e.retryable }, ...(e.state ? { state: e.state } : {}) };
};

function fingerprint(name, p) {
  return name === "ios_build"
    ? `ios_build\0${p.project}\0${p.kind}\0${p.ref}\0${p.configuration}`
    : `ios_install\0${p.run_id}\0${p.device}\0${p.launch}`;
}

export function createPlugin(deps = {}) {
  const now = deps.now ?? Date.now;
  return {
    id: "jorah-ios",
    name: "Jorah iOS",
    description: "Build Adam's iOS apps on his Mac and install them on his iPhone, each on Adam's approval.",
    register(api) {
      const config = () => settings(api.pluginConfig ?? {});
      const client = () => runnerClient(config(), deps);

      // Cards shown and their decisions, by tool call ID when the host gives one, else by the call.
      const approvals = new Map();
      const prune = () => {
        for (const [k, v] of approvals) if (now() - v.at > APPROVAL_TTL_MS) approvals.delete(k);
      };
      function takeApproval(name, toolCallId, p) {
        prune();
        const fp = fingerprint(name, p);
        const key = toolCallId && approvals.has(toolCallId) ? toolCallId : fp;
        const a = approvals.get(key);
        approvals.delete(key);
        if (!a || a.fp !== fp) throw new IosError("DENIED", "No card was approved for this exact call, so nothing was sent to the Mac.");
        if (a.decision !== "allow-once") {
          throw new IosError("DENIED", a.decision === "timeout" ? "The card timed out, so nothing was sent to the Mac." : "Adam didn't approve the card, so nothing was sent to the Mac.");
        }
        return a;
      }

      async function buildCard(p, signal) {
        const args = checkBuild(config(), p);
        const synced = await client().call("sync", { project: args.project, ref: args.ref }, { signal });
        const commit = checkCommit(synced?.commit);
        const repo = typeof synced?.repo === "string" ? synced.repo : "(repo not named by the Mac)";
        const signed = args.kind === "simulator" ? "Simulator build, not signed for a device." : "Signed with the Development certificate of the team in the Mac's allowlist.";
        return {
          args,
          bound: { commit, repo },
          card: {
            title: "Jorah wants to build an iOS app",
            description: [
              `Project: ${args.project} (${repo})`,
              `Ref: ${args.ref}, commit ${commit}`,
              `Build: ${args.kind}, ${args.configuration}`,
              `${signed} Nothing is uploaded.`,
            ].join("\n"),
          },
        };
      }

      async function installCard(p, signal) {
        const args = checkInstall(p);
        const c = client();
        const run = readRun(await c.call("status", { run_id: args.run_id }, { signal }));
        if (!run || run.run_id !== args.run_id) throw new IosError("RUN_NOT_FOUND", "The Mac doesn't know that build.");
        if (!config().projects.includes(run.project)) throw new IosError("PROJECT_NOT_ALLOWED", `${run.project} isn't one of the projects Jorah may install.`);
        if (run.kind !== "device" || run.state !== "succeeded" || run.tier === "unknown" || !run.commit) {
          throw new IosError("NOT_INSTALLABLE", "That run isn't a finished, proved device build, so there is nothing to install.");
        }
        const listed = await c.call("devices", {}, { signal });
        const device = (Array.isArray(listed?.devices) ? listed.devices : []).find((d) => d?.alias === args.device);
        if (!device) throw new IosError("DEVICE_NOT_ALLOWED", `${args.device} isn't a device in the Mac's allowlist.`);
        return {
          args,
          bound: { commit: run.commit, project: run.project },
          card: {
            title: "Jorah wants to install an app on your iPhone",
            description: [
              `Project: ${run.project}, commit ${run.commit}`,
              `Build: ${run.configuration ?? "?"}, run ${args.run_id}`,
              `Device: ${args.device}${device.model ? ` (${device.model}${device.os_version ? `, iOS ${device.os_version}` : ""})` : ""}${device.connected === false ? ", not connected now" : ""}`,
              args.launch ? "Then launch the app." : "Install only, no launch.",
            ].join("\n"),
          },
        };
      }

      // Every build and every install waits for Adam. Fails closed: any error blocks the call, and
      // the card is never shown for a commit or build the plugin couldn't name.
      api.on("before_tool_call", async (event, ctx) => {
        const name = event?.toolName;
        if (!TOOLS.has(name)) return undefined;
        try {
          const made = name === "ios_build" ? await buildCard(event.params ?? {}, ctx?.abortSignal) : await installCard(event.params ?? {}, ctx?.abortSignal);
          prune();
          const entry = { fp: fingerprint(name, made.args), bound: made.bound, decision: null, at: now() };
          const key = typeof event.toolCallId === "string" && event.toolCallId ? event.toolCallId : entry.fp;
          approvals.set(key, entry);
          return {
            requireApproval: {
              ...made.card,
              severity: "warning",
              allowedDecisions: ["allow-once", "deny"],
              timeoutMs: CARD_TIMEOUT_MS,
              pluginId: "jorah-ios",
              // Kept either way until used or stale, so a stray execute says why it was refused.
              onResolution: (decision) => {
                entry.decision = decision;
              },
            },
          };
        } catch (error) {
          const e = failure(error).error;
          api.logger.warn(`jorah-ios: ${name} refused before the card: ${e.code}`);
          return { block: true, blockReason: `jorah-ios: ${e.message} (${e.code})` };
        }
      });

      api.registerTool({
        name: "ios_build",
        catalogMode: "direct-only",
        description:
          "Build one of Adam's iOS apps on his Mac from main or a jorah/<task> branch: simulator, device (signed for Development) or archive. Adam approves each build on a card that names the exact commit. Returns at once with a run_id; follow it with ios_status { run_id, wait_seconds: 120 }. Never uploads anything.",
        parameters: {
          type: "object",
          additionalProperties: false,
          required: ["project", "kind"],
          properties: {
            project: { type: "string", pattern: "^[a-z0-9][a-z0-9-]{0,39}$", description: "Project name from the allowlist, e.g. threadfolio or mizyun" },
            kind: { type: "string", enum: ["simulator", "device", "archive"] },
            ref: { type: "string", pattern: "^[A-Za-z0-9._/-]{1,100}$", description: "main (default) or a jorah/<task> branch" },
            configuration: { type: "string", enum: ["Debug", "Release"], description: "Default Debug" },
          },
        },
        async execute(toolCallId, p) {
          try {
            const args = checkBuild(config(), p ?? {});
            const approved = takeApproval("ios_build", toolCallId, args);
            const raw = await client().call(verbForKind(args.kind), { project: args.project, commit: approved.bound.commit, configuration: args.configuration }, { timeoutMs: BUILD_START_TIMEOUT_MS });
            const run = readRun(raw);
            if (run?.commit && run.commit !== approved.bound.commit) {
              return result(`The Mac reports building ${run.commit}, not the approved ${approved.bound.commit}. Treat this run as unknown.\n${describeRun(run)}`, { ok: false, run, error: { code: "CONTRACT_MISMATCH", message: "The Mac built a different commit from the one approved.", retryable: false } });
            }
            api.logger.info(`jorah-ios: build ${run?.run_id ?? "?"} started (${args.project} ${args.kind})`);
            return result(`Build started on the Mac.\n${describeRun(run, { withTail: false })}\nCheck it with ios_status { run_id: "${run?.run_id ?? ""}", wait_seconds: 120 }.`, { ok: true, run, error: null });
          } catch (error) {
            const d = failure(error);
            api.logger.warn(`jorah-ios: build not started: ${d.error.code}`);
            return result(`Build not started: ${d.error.message}${d.state === "unknown" ? " State: unknown." : ""}`, d);
          }
        },
      });

      api.registerTool({
        name: "ios_install",
        catalogMode: "direct-only",
        description:
          "Install a finished device build from ios_build on one of Adam's allowlisted devices, and optionally launch it. Adam approves each install on a card. Waits for the result (up to a few minutes).",
        parameters: {
          type: "object",
          additionalProperties: false,
          required: ["run_id", "device"],
          properties: {
            run_id: { type: "string", description: "A run_id from ios_build with kind device that succeeded" },
            device: { type: "string", pattern: "^[a-z0-9][a-z0-9-]{0,39}$", description: "Device alias, e.g. adam-iphone" },
            launch: { type: "boolean", description: "Start the app after installing. Default false" },
          },
        },
        async execute(toolCallId, p) {
          try {
            const args = checkInstall(p ?? {});
            takeApproval("ios_install", toolCallId, args);
            const run = readRun(await client().call("install-device", { build_run_id: args.run_id, device: args.device, launch: args.launch }, { timeoutMs: INSTALL_TIMEOUT_MS }));
            const ok = run?.state === "succeeded";
            api.logger.info(`jorah-ios: install ${run?.run_id ?? "?"} ${run?.state ?? "unknown"}`);
            return result(`${ok ? "Install finished." : "Install did not succeed."}\n${describeRun(run)}`, { ok, run, error: null });
          } catch (error) {
            const d = failure(error);
            api.logger.warn(`jorah-ios: install not done: ${d.error.code}`);
            return result(`Install not done: ${d.error.message}${d.state === "unknown" ? " State: unknown." : ""}`, d);
          }
        },
      });

      api.registerTool({
        name: "ios_status",
        catalogMode: "direct-only",
        description:
          "Read-only, no approval. With run_id: one run's state, tier proved and log pointer (wait_seconds up to 120 waits for it to finish). Without: the 10 latest runs. With run_id and log { offset, max_bytes }: one page of the full log. With devices: true alone: the allowlisted devices and whether each is connected.",
        parameters: {
          type: "object",
          additionalProperties: false,
          properties: {
            run_id: { type: "string" },
            wait_seconds: { type: "integer", minimum: 0, maximum: 120 },
            log: {
              type: "object",
              additionalProperties: false,
              required: ["offset", "max_bytes"],
              properties: { offset: { type: "integer", minimum: 0 }, max_bytes: { type: "integer", minimum: 1, maximum: 262144 } },
            },
            devices: { type: "boolean", enum: [true] },
          },
        },
        async execute(_id, p) {
          try {
            const q = checkStatus(p ?? {});
            const c = client();
            if (q.mode === "devices") {
              const listed = await c.call("devices", {});
              const devices = Array.isArray(listed?.devices) ? listed.devices : [];
              const conn = (d) => (d.connected === true ? "connected" : d.connected === false ? "not connected" : "connection unknown");
              const lines = devices.map((d) => `${d.alias}${d.model ? ` (${d.model}${d.os_version ? `, iOS ${d.os_version}` : ""})` : ""}: ${conn(d)}`);
              return result(devices.length ? `Allowlisted devices:\n${lines.join("\n")}` : "The Mac lists no allowlisted devices.", { ok: true, devices });
            }
            if (q.mode === "log") {
              const page = trimPage(await c.call("log", { run_id: q.run_id, offset: q.offset, max_bytes: q.max_bytes }));
              const where = `Log of ${q.run_id} (on the Mac in ${handoffFolder(q.run_id)}), bytes ${page.start ?? q.offset} to ${page.next ?? "end"}${page.total === null ? "" : ` of ${page.total}`}.`;
              const next = page.eof ? "End of log." : `Next page: offset ${page.next}.`;
              return result(`${where}\n${untrusted(page.text)}\n${next}`, { ok: true, log: { start: page.start ?? null, next: page.next, eof: page.eof, total_bytes: page.total } });
            }
            if (q.mode === "run") {
              const run = readRun(await c.call("status", { run_id: q.run_id, wait_seconds: q.wait_seconds }, { timeoutMs: (q.wait_seconds + 30) * 1000 }));
              return result(describeRun(run), { ok: true, run, error: null });
            }
            const listed = await c.call("status", {});
            const runs = (Array.isArray(listed?.runs) ? listed.runs : []).map(readRun).filter(Boolean);
            const lines = runs.map((r) => `${r.run_id}: ${[r.project, r.kind].filter(Boolean).join(" ")} ${r.state}, tier ${r.tier}`);
            return result(runs.length ? `Latest runs, newest first:\n${lines.join("\n")}` : "No runs on the Mac yet.", { ok: true, runs });
          } catch (error) {
            const d = failure(error);
            return result(`Status not read: ${d.error.message}`, d);
          }
        },
      });
    },
  };
}

export default createPlugin();
