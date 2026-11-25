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

// Wrapped scalars: PyYAML (the runner's dump, and runs that write YAML with it) wraps long plain
// and quoted strings over several lines. The plugin must read every way it wraps them, or a
// project's questions show as unknown (jorah-arm's questions.yaml, 2026-11-25).
const WRAP = `
import json, sys, yaml
sys.path.insert(0, sys.argv[1])
from jorah_projects import fsio
words = "Decides safety rules, what v1 builds and leaves out, and whether anything is reachable from the internet."
strings = [
    words * 3,
    'You want an arm "that you can then control". Who may move the real arm in v1, from where, and under what conditions?',
    "Jorah's proposal for every option: below 12 V DC from a CE-marked adapter, no mains wiring #1, slow moves. " * 2,
    "costs 5 - 10 EUR each " * 8,
    "  leading and trailing spaces  " * 4,
    "tab\\there and a backslash \\\\ and a quote \\" here " * 4,
    "Unicode: Zürich, €12, naïve café, 日本語, emoji 🤖 " * 4,
    "control \\x07 bell and \\x1b escape and \\u2028 separator " * 3,
    "x" * 150 + " short",
    "first line\\nsecond line that is long enough to need a wrap if it were plain " * 2,
    "a" + " " * 30 + "b " * 60,
    "- starts like an item, then goes on for long enough that PyYAML has to wrap it somewhere",
]
doc = {"questions": [{"id": f"Q-{i:04d}", "question": s, "why_it_matters": s[::-1],
                      "options": [{"key": "A", "consequence": s}]} for i, s in enumerate(strings)]}
out = []
for width in (20, 40, 80, 100):
    for name, dumper in (("runner", fsio.Dumper), ("safe", yaml.SafeDumper)):
        for style in (None, "'", '"'):
            if style:
                class D(dumper):
                    pass
                D.add_representer(str, lambda d, v, st=style: d.represent_scalar("tag:yaml.org,2002:str", v, style=st))
            else:
                D = dumper
            text = yaml.dump(doc, Dumper=D, sort_keys=False, allow_unicode=True, default_flow_style=False, width=width)
            out.append({"case": f"{name} width={width} style={style}", "text": text, "value": yaml.load(text, Loader=fsio.Loader)})
print(json.dumps(out))
`;

test("yaml: long strings PyYAML wraps over several lines read as PyYAML reads them", (t) => {
  let cases;
  try {
    cases = JSON.parse(execFileSync("python3", ["-I", "-c", WRAP, join(repo, "services", "jorah-projects")], { stdio: ["ignore", "pipe", "pipe"] }).toString());
  } catch {
    return t.skip("python3 with PyYAML isn't available");
  }
  let wrapped = 0;
  for (const c of cases) {
    if (/\n {4,}\S/.test(c.text)) wrapped++;
    assert.deepEqual(parseYaml(c.text), c.value, `${c.case}:\n${c.text}`);
  }
  assert.ok(wrapped >= 12, `only ${wrapped} dumps wrapped a line`);
});

test("yaml: jorah-arm's questions.yaml as it was on 2026-11-25", () => {
  const text = [
    "questions:",
    "- id: Q-0005",
    "  question: You want an arm \"that you can then control\". Who may move the real arm in v1, from where,",
    "    and under what conditions?",
    "  why_it_matters: 'Decides safety rules, what v1 builds and leaves out, and whether anything is reachable",
    "    from the internet. A hobby arm can pinch fingers. Jorah''s proposal",
    "",
    "    for every option: below 12 V DC.'",
    "  wrapped_double: \"one \\",
    "    \\ two\\tthree",
    "    four\" # a comment after it",
    "  status: open",
    "",
  ].join("\n");
  const q = parseYaml(text).questions[0];
  assert.equal(q.question, "You want an arm \"that you can then control\". Who may move the real arm in v1, from where, and under what conditions?");
  assert.equal(q.why_it_matters, "Decides safety rules, what v1 builds and leaves out, and whether anything is reachable from the internet. A hobby arm can pinch fingers. Jorah's proposal\nfor every option: below 12 V DC.");
  assert.equal(q.wrapped_double, "one  two\tthree four");
  assert.equal(q.status, "open");
  for (const bad of ["a: 'open\nb: 1\n", "a:\n  b: \"x\n  c\n", "a: 'x\n  y' z\n"]) assert.throws(() => parseYaml(bad), undefined, bad);
});
