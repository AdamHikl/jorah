// The plugin's small YAML reader against the contract's own loader (packages/contracts/project/
// projectcheck.py, PyYAML's safe loader narrowed): every example and template must read the same,
// or fail in both. The runner validates with the Python loader, so a file the plugin reads
// differently would show Adam something the runner never saw. Skipped where PyYAML is missing.

import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { parseYaml } from "../lib/yaml.js";

const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, "..", "..", "..");
const contract = join(repo, "packages", "contracts", "project");

function yamlFiles(dir) {
  const out = [];
  let names;
  try { names = readdirSync(dir); } catch { return out; }
  for (const n of names) {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) out.push(...yamlFiles(p));
    else if (n.endsWith(".yaml") || n.endsWith(".yml")) out.push(p);
  }
  return out;
}

const SCRIPT = `
import json, sys
sys.path.insert(0, sys.argv[1])
import projectcheck
out = {}
for p in sys.argv[2:]:
    try:
        out[p] = {"ok": True, "value": projectcheck.load_yaml(p)}
    except Exception as e:
        out[p] = {"ok": False, "error": type(e).__name__}
print(json.dumps(out, default=str))
`;

function python(files) {
  try {
    return JSON.parse(execFileSync("python3", ["-I", "-c", SCRIPT, contract, ...files], { stdio: ["ignore", "pipe", "pipe"] }).toString());
  } catch {
    return null;
  }
}

test("yaml: every contract example and template reads as the contract's Python loader reads it", (t) => {
  const files = [...yamlFiles(join(contract, "examples")), ...yamlFiles(join(repo, "templates", "project"))];
  if (files.length === 0) return t.skip("no contract examples in this checkout");
  const py = python(files);
  if (!py) return t.skip("python3 with PyYAML isn't available");
  let compared = 0;
  for (const f of files) {
    const want = py[f];
    let got;
    try {
      got = { ok: true, value: parseYaml(readFileSync(f, "utf8")) };
    } catch (e) {
      got = { ok: false, error: e.message };
    }
    assert.equal(got.ok, want.ok, `${f}: plugin ${got.ok ? "read it" : `refused (${got.error})`}, Python ${want.ok ? "read it" : `refused (${want.error})`}`);
    if (want.ok) assert.deepEqual(got.value, want.value, f);
    compared++;
  }
  assert.ok(compared >= 10, `only ${compared} files compared`);
});
