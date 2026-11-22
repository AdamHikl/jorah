#!/usr/bin/env node
// Runs one toolbox drill case through jorah-projects' real toolbox_propose and toolbox_install
// against scratch directories, using the real fetch and an instant sleep (so toolbox_install
// writes the approval and returns without waiting). Prints one JSON line: {propose, install}.

import { readFileSync } from "node:fs";
import { register } from "../../plugins/jorah-projects/index.js";

const FLAGS = {
  "--toolbox-dir": "toolboxDir",
  "--toolbox-var": "toolboxVar",
  "--state-root": "stateRoot",
  "--registry-file": "registryFile",
  "--work-root": "workRoot",
  "--guard-state-dir": "guardStateDir",
};

function parseArgs(argv) {
  const cfg = {};
  for (let i = 0; i < argv.length; i += 2) {
    const key = FLAGS[argv[i]];
    const val = argv[i + 1];
    if (!key || !val || val.startsWith("--")) {
      throw new Error(`Usage: toolbox-drill.mjs ${Object.keys(FLAGS).map((f) => `${f} <path>`).join(" ")}`);
    }
    cfg[key] = val;
  }
  for (const [flag, key] of Object.entries(FLAGS)) {
    if (!cfg[key]) throw new Error(`Missing required flag ${flag}`);
  }
  return cfg;
}

const ADAM = {
  agentId: "main",
  sessionKey: "agent:main:main",
  requester: { channel: "telegram", senderId: "owner-id", senderIsOwner: true },
};

function load(pluginConfig) {
  const tools = new Map();
  const hooks = {};
  register(
    {
      pluginConfig,
      logger: { info: () => {}, warn: () => {} },
      on: (name, fn) => {
        (hooks[name] ??= []).push(fn);
      },
      registerTool: (t) => tools.set(t.name, t),
    },
    { fetch: globalThis.fetch, sleep: async () => {} },
  );
  let n = 0;
  return async (name, params = {}, ctx = ADAM) => {
    const id = `call-${++n}`;
    for (const h of hooks.before_tool_call ?? []) {
      h({ toolName: name, params, toolCallId: id }, ctx);
    }
    return JSON.parse((await tools.get(name).execute(id, params)).content[0].text);
  };
}

async function main() {
  const pluginConfig = parseArgs(process.argv.slice(2));
  const raw = readFileSync(0, "utf8");
  const input = JSON.parse(raw);
  const manifest = input && typeof input === "object" && "request" in input && !("contract" in input)
    ? input.request
    : input;

  const call = load(pluginConfig);
  const propose = await call("toolbox_propose", { manifest });
  const install = propose?.status === "proposed" ? await call("toolbox_install", propose.card) : null;
  process.stdout.write(`${JSON.stringify({ propose, install })}\n`);
}

main().catch((err) => {
  process.stderr.write(`${err?.stack || err}\n`);
  process.exit(1);
});
