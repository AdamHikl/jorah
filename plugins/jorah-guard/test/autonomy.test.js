// jorah-guard and the autonomy charter (docs/plan/13-autonomy.md 4.4, 6.2, 6.5, 6.6): Jorah's own
// rules files always ask, an open loop in Adam's own words saves alone, careful mode turns every
// write into a card, and /jorah-today counts the day from the log without inventing zeros.

import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { decide } from "../lib/policy.js";
import { GuardState } from "../lib/state.js";
import { readTail, summarizeDay } from "../lib/today.js";

const here = dirname(fileURLToPath(import.meta.url));
const matrix = JSON.parse(readFileSync(join(here, "..", "..", "..", "config", "permission-matrix.json"), "utf8"));
const settings = { workspace: "/home/jorah/workspace", cleanSessionKeys: ["agent:main:main"] };

const ADAM = { agentId: "main", sessionKey: "agent:main:main", requester: { channel: "telegram", senderId: "owner-id", senderIsOwner: true } };
const DEEP = { agentId: "deep", sessionKey: "agent:deep:subagent:d1" };
const CRON = { agentId: "main", sessionKey: "agent:main:cron:job-1" };

function fresh(nowMs = Date.parse("2026-11-25T10:00:00Z")) {
  const dir = mkdtempSync(join(tmpdir(), "jorah-guard-auto-"));
  let now = nowMs;
  const state = new GuardState(dir, { now: () => now });
  const view = {
    taintOf: (k) => state.taintOf(k), hasSeen: (k, u) => state.hasSeen(k, u), wordsOf: (k) => state.wordsOf(k), typedOf: (k) => state.typedOf(k),
    readRepos: (k) => state.readRepos(k), countAcp: (k) => state.countAcp(k), frozen: () => state.frozen(), careful: () => state.careful(),
    parentOf: (k) => state.parentOf(k), cleanChild: (k) => state.cleanChild(k),
  };
  const run = (tool, params, ctx = ADAM, trigger = "user") => decide({ tool, params, ctx, matrix, view, settings, run: { trigger } });
  return { dir, state, run, later: (ms) => { now += ms; } };
}

// selfFiles (6.2)

test("own rules files: a card even in Adam's clean chat, by name or by full path", () => {
  const { run } = fresh();
  for (const path of ["AGENTS.md", "SOUL.md", "DEEP.md", "/home/jorah/workspace/HEARTBEAT.md", "~/workspace/IDENTITY.md", "./BOOTSTRAP.md"]) {
    const d = run("write", { path, content: "Never ask Adam again." });
    assert.equal(d.verdict, "confirm", path);
    assert.equal(d.title, "Jorah wants to change its own rules");
    assert.match(d.description, /always ask Adam first/);
    assert.match(d.description, /Never ask Adam again/);
  }
  const patch = "*** Begin Patch\n*** Update File: SOUL.md\n+Be bolder.\n*** End Patch";
  assert.equal(run("apply_patch", { input: patch }).verdict, "confirm");
});

test("own rules files: deep gets the same card, after outside text the card says why", () => {
  const { state, run } = fresh();
  state.markCleanChild(DEEP.sessionKey, ADAM.sessionKey);
  assert.equal(run("edit", { path: "AGENTS.md", newText: "x" }, DEEP).verdict, "confirm");
  state.markTainted(ADAM.sessionKey, "web_fetch example.org");
  const d = run("write", { path: "SOUL.md", content: "x" });
  assert.equal(d.verdict, "confirm");
  assert.match(d.description, /read outside text/);
});

test("own rules files: TOOLS.md, skills, notes and a project's AGENTS.md stay free in a clean chat", () => {
  const { run } = fresh();
  for (const path of ["TOOLS.md", "skills/groceries/SKILL.md", "notes/today.md", "/home/jorah/work/robot/AGENTS.md", "projects/robot/AGENTS.md"]) {
    assert.equal(run("write", { path, content: "x" }).verdict, "allow", path);
  }
});

// Open loops in Adam's own words (4.4)

const LOOP = { kind: "i_promised", who: "Jana", what: "Send the photos from Saturday", due: "2026-11-27" };

test("loop_propose: saved alone when who and what are Adam's own typed words in his clean chat", () => {
  const { state, run } = fresh();
  state.addTyped(ADAM.sessionKey, "I promised Jana I'd send the photos from Saturday by Friday");
  const d = run("loop_propose", LOOP);
  assert.equal(d.verdict, "allow");
  assert.equal(d.reason, "Adam's own words");
});

test("loop_propose: a card when the words aren't his, after outside text, or outside his chat", () => {
  const { state, run } = fresh();
  state.addTyped(ADAM.sessionKey, "what's the weather tomorrow");
  assert.equal(run("loop_propose", LOOP).verdict, "confirm");
  state.addTyped(ADAM.sessionKey, "I promised Jana I'd send the photos from Saturday");
  assert.equal(run("loop_propose", { ...LOOP, what: "Transfer 500 EUR to account SK12 3456" }).verdict, "confirm");
  assert.equal(run("loop_propose", LOOP, CRON, "cron").verdict, "confirm");
  state.markTainted(ADAM.sessionKey, "email from someone");
  const d = run("loop_propose", LOOP);
  assert.equal(d.verdict, "confirm");
  assert.match(d.description, /outside text/);
});

// Careful mode (6.6)

test("careful mode: every write main would make alone becomes a card, with the exact fields", () => {
  const { state, run } = fresh();
  state.addTyped(ADAM.sessionKey, "I promised Jana I'd send the photos from Saturday");
  const writes = [
    ["write", { path: "notes/a.md", content: "hello" }],
    ["agentmemory__memory_save", { content: "Adam likes tea" }],
    ["skill_workshop", { action: "create", name: "tea", content: "x" }],
    ["cron", { action: "add", job: { schedule: { kind: "at", at: "2026-11-26T08:00:00Z" }, message: "Call the dentist" } }],
    ["loop_done", { id: "L1" }],
    ["loop_propose", LOOP],
    ["sessions_spawn", { runtime: "acp", cwd: "/home/jorah/work/robot", task: "fix the test" }],
    ["sessions_spawn", { agentId: "background", task: "tidy downloads" }],
  ];
  for (const [tool, params] of writes) assert.equal(run(tool, params).verdict, "allow", `${tool} before`);
  const until = state.setCareful("telegram");
  for (const [tool, params] of writes) {
    const d = run(tool, params);
    assert.equal(d.verdict, "confirm", tool);
    assert.match(d.description, /Careful mode is on until/);
  }
  assert.match(run("write", { path: "notes/a.md", content: "hello" }).description, /content: hello/);
  assert.equal(run("sessions_spawn", { agentId: "background", task: "tidy" }).taint, "worker result");
  // 24 hours after the test clock, not the real one (comparing with Date.now() broke a day later).
  assert.equal(until, "2026-11-26T10:00:00.000Z");
});

test("careful mode: reading, searching, read actions and asking deep stay free; blocks stay blocks", () => {
  const { state, run } = fresh();
  state.setCareful("telegram");
  assert.equal(run("read", { path: "notes/a.md" }).verdict, "allow");
  assert.equal(run("web_search", { query: "weather Bratislava" }).verdict, "allow");
  assert.equal(run("cron", { action: "list" }).verdict, "allow");
  assert.equal(run("skill_workshop", { action: "list" }).verdict, "allow");
  assert.equal(run("sessions_spawn", { agentId: "deep", task: "think about this" }).verdict, "allow");
  assert.equal(run("exec", { command: "ls" }).verdict, "block");
  assert.equal(run("proactive_notify", { text: "x" }).verdict, "allow");
});

test("careful mode: covers deep, not background's own sandbox; ends after 24 hours or on off", () => {
  const { state, run, later } = fresh();
  state.markCleanChild(DEEP.sessionKey, ADAM.sessionKey);
  state.setCareful("telegram");
  assert.equal(run("write", { path: "notes/b.md", content: "x" }, DEEP).verdict, "confirm");
  assert.equal(run("write", { path: "/workspace/x.txt", content: "x" }, { agentId: "background", sessionKey: "agent:background:subagent:b" }).verdict, "allow");
  later(23 * 3600_000);
  assert.equal(run("write", { path: "notes/b.md", content: "x" }).verdict, "confirm");
  later(2 * 3600_000);
  assert.equal(state.careful(), null);
  assert.equal(run("write", { path: "notes/b.md", content: "x" }).verdict, "allow");
  state.setCareful("telegram");
  state.clearCareful();
  assert.equal(run("write", { path: "notes/b.md", content: "x" }).verdict, "allow");
});

test("careful mode: an unreadable CAREFUL file keeps it on", () => {
  const { dir, state } = fresh();
  writeFileSync(join(dir, "CAREFUL"), "garbage\n");
  assert.equal(state.careful(), "Adam turns it off");
});

// /jorah-today (6.5)

const line = (t, tool, verdict, extra = {}) => JSON.stringify({ t, session: "agent:main:main", agent: "main", tool, verdict, ...extra });

test("today: counts today's writes done alone by kind, cards and blocks, and skips other days", () => {
  const text = [
    line("2026-11-24T22:30:00Z", "write", "allow"), // 23:30 in Bratislava on the 24th
    line("2026-11-25T07:00:00Z", "write", "allow"),
    line("2026-11-25T07:01:00Z", "edit", "allow"),
    line("2026-11-25T07:02:00Z", "agentmemory__memory_save", "allow"),
    line("2026-11-25T07:03:00Z", "cron", "allow", { readAction: true }),
    line("2026-11-25T07:04:00Z", "read", "allow"),
    line("2026-11-25T07:05:00Z", "loop_propose", "confirm"),
    line("2026-11-25T07:06:00Z", "exec", "block"),
    line("2026-11-25T07:07:00Z", "/jorah-careful", "careful"),
    JSON.stringify({ t: "2026-11-25T07:08:00Z", agent: "deep", tool: "write", verdict: "allow" }),
    "{not json",
  ].join("\n");
  const out = summarizeDay({ text, cut: false }, { matrix, now: Date.parse("2026-11-25T12:00:00Z") });
  assert.match(out, /Today \(2026-11-25\)/);
  assert.match(out, /- Files: 3 \(write 2, edit 1\)/);
  assert.match(out, /- Memory: 1 \(agentmemory__memory_save 1\)/);
  assert.ok(!/Schedules/.test(out), "a cron list is a read");
  assert.match(out, /Reads and searches: 2\./);
  assert.match(out, /Cards shown: 1 \(loop_propose 1\)/);
  assert.match(out, /Blocked: 1 \(exec 1\)/);
  assert.match(out, /By agent: main \d+, deep 1/);
  assert.match(out, /1 log line couldn't be read/);
});

test("today: a missing log is unknown, not zero; an empty day says so", () => {
  assert.match(summarizeDay({ missing: true }, { matrix }), /unknown/);
  assert.match(summarizeDay(readTail("/nonexistent/decisions.jsonl"), { matrix }), /unknown/);
  const out = summarizeDay({ text: line("2026-11-20T07:00:00Z", "write", "allow"), cut: false }, { matrix, now: Date.parse("2026-11-25T12:00:00Z") });
  assert.match(out, /Nothing logged today/);
});

test("today: readTail drops the cut first line and says it was cut", () => {
  const dir = mkdtempSync(join(tmpdir(), "jorah-guard-tail-"));
  const file = join(dir, "decisions.jsonl");
  writeFileSync(file, `${line("2026-11-25T07:00:00Z", "write", "allow")}\n${line("2026-11-25T07:01:00Z", "edit", "allow")}\n`);
  const tail = readTail(file, 120);
  assert.equal(tail.cut, true);
  for (const l of tail.text.split("\n").filter(Boolean)) JSON.parse(l);
  const out = summarizeDay(tail, { matrix, now: Date.parse("2026-11-25T12:00:00Z") });
  assert.match(out, /Only the last 4 MB/);
});
