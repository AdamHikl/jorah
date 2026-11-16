// The intake.md project_start writes, against the contract's own check (packages/contracts/project/
// projectcheck.py check_intake_text): the runner copies the file into the project folder and the
// checker must pass it, or the setup run never starts. Skipped where python3 with PyYAML is missing.

import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { checkIntake, intakeText } from "../lib/intake.js";
import { newEntry } from "../lib/registry.js";

const here = dirname(fileURLToPath(import.meta.url));
const contract = join(here, "..", "..", "..", "packages", "contracts", "project");

const SCRIPT = `
import json, sys
sys.path.insert(0, sys.argv[1])
import projectcheck
if not hasattr(projectcheck, "check_intake_text"):
    print("null"); sys.exit(0)
print(json.dumps([projectcheck.check_intake_text(t) for t in json.loads(sys.stdin.read())]))
`;

test("intake.md: every way project_start writes it passes the contract's check", (t) => {
  const at = "2026-11-16T18:05:00.000Z";
  const texts = [
    intakeText({ ...checkIntake("A robot that waters street trees."), at, via: "telegram" }),
    intakeText({ ...checkIntake("Line one\r\n\r\nLine three\u0007", [{ question: "Money?", answer: "You decide" }]), at, via: "voice" }),
    intakeText({ ...checkIntake("# My idea\n\n- a list"), at, via: "app" }),
  ];
  let out;
  try {
    out = JSON.parse(execFileSync("python3", ["-I", "-c", SCRIPT, contract], { input: JSON.stringify(texts), stdio: ["pipe", "pipe", "pipe"] }).toString());
  } catch {
    return t.skip("python3 with PyYAML isn't available");
  }
  if (out === null) return t.skip("this checkout's contract has no check_intake_text");
  assert.deepEqual(out, texts.map(() => []));
});

test("registry: the entries project_start writes (local-only and with a repo) pass the contract's check", (t) => {
  const reg = {
    "street-trees": newEntry({ repo: null, workDir: "/home/jorah/work/street-trees" }),
    "robot-tour": newEntry({ repo: "AdamHikl/robot_tour", workDir: "/home/jorah/work/robot_tour" }),
  };
  const script = `
import json, sys
sys.path.insert(0, sys.argv[1])
import projectcheck
print(json.dumps(projectcheck.check_registry(json.loads(sys.stdin.read()))))
`;
  let out;
  try {
    out = JSON.parse(execFileSync("python3", ["-I", "-c", script, contract], { input: JSON.stringify(reg), stdio: ["pipe", "pipe", "pipe"] }).toString());
  } catch {
    return t.skip("python3 with PyYAML isn't available");
  }
  assert.deepEqual(out, []);
});
