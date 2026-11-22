// jorah-guard and project mode (docs/plan/11-project-mode.md sections 5 and 9). The model is
// hijacked by text a project run brought in from the web (PM-T4): it tries to answer Adam's founder
// questions, file task results, start runs and raise limits, by chat, by voice and from the 18:00
// digest automation. Pass means the guard decides as the matrix says.

import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { classify, decide } from "../lib/policy.js";
import { GuardState } from "../lib/state.js";

const here = dirname(fileURLToPath(import.meta.url));
const MATRIX_FILE = join(here, "..", "..", "..", "config", "permission-matrix.json");
const PROJECTS_MANIFEST = join(here, "..", "..", "jorah-projects", "openclaw.plugin.json");
const matrix = JSON.parse(readFileSync(MATRIX_FILE, "utf8"));
const settings = { workspace: "/home/jorah/workspace", cleanSessionKeys: ["agent:main:main"] };

const ADAM = { agentId: "main", sessionKey: "agent:main:main", requester: { channel: "telegram", senderId: "owner-id", senderIsOwner: true } };
const VOICE = { agentId: "main", sessionKey: "agent:main:voice-1", requester: { channel: "voice", senderIsOwner: true } };
const DIGEST_JOB = { agentId: "main", sessionKey: "agent:main:cron:project-digest" };
const P = "tree-watering-robot";
const ANSWER = { project: P, question_id: "Q-0001", key: "B", note: "your pick" };

function fresh() {
  const dir = mkdtempSync(join(tmpdir(), "jorah-guard-projects-"));
  const state = new GuardState(dir);
  const view = {
    taintOf: (k) => state.taintOf(k), hasSeen: (k, u) => state.hasSeen(k, u), wordsOf: (k) => state.wordsOf(k),
    readRepos: (k) => state.readRepos(k), countAcp: (k) => state.countAcp(k), frozen: () => state.frozen(), parentOf: (k) => state.parentOf(k),
  };
  const run = (tool, params, ctx = ADAM, trigger = "user") => {
    const d = decide({ tool, params, ctx, matrix, view, settings, run: { trigger } });
    if (d.taint && d.verdict !== "block") state.markTainted(ctx.sessionKey, d.taint);
    if (d.readRepo && d.verdict !== "block") state.markReadPrivateRepo(ctx.sessionKey, d.readRepo);
    return d;
  };
  return { state, run };
}

test("matrix: every jorah-projects tool has the class section 5 gives it", () => {
  const tools = JSON.parse(readFileSync(PROJECTS_MANIFEST, "utf8")).contracts.tools;
  assert.equal(tools.length, 18); // fourteen project tools and four toolbox tools (toolbox.test.js)
  for (const t of tools) assert.notEqual(classify(matrix, t), null, t);
  for (const t of ["project_list", "project_status", "project_pause"]) assert.equal(classify(matrix, t), "read", t);
  assert.equal(classify(matrix, "project_digest"), "taintRead");
  for (const t of ["project_answer", "project_task_result", "project_run_now", "project_resume", "project_start"]) assert.equal(classify(matrix, t), "localWrite", t);
  for (const t of ["project_set_limits", "project_connect", "project_set_level", "project_set_capabilities"]) assert.equal(classify(matrix, t), "confirmAlways", t);
  assert.equal(classify(matrix, "project_preview"), "taintRead");
  for (const t of ["project_answer", "project_task_result", "project_run_now", "project_resume", "project_set_limits", "project_start", "project_connect", "project_set_level", "project_set_capabilities"]) assert.ok(matrix.cardTitles[t], t);
});

test("reads: list and status are free and leave the chat clean", () => {
  const { run, state } = fresh();
  assert.equal(run("project_list", {}).verdict, "allow");
  assert.equal(run("project_status", { project: P }).verdict, "allow");
  assert.equal(state.taintOf(ADAM.sessionKey)?.tainted ?? false, false);
  assert.equal(run("project_answer", ANSWER).verdict, "allow");
});

test("project_digest marks the chat as having read outside text, naming the project", () => {
  const { run, state } = fresh();
  assert.equal(run("project_digest", { project: P }).verdict, "allow");
  const t = state.taintOf(ADAM.sessionKey);
  assert.equal(t.tainted, true);
  assert.match(t.source, /project_digest tree-watering-robot/);
});

test("PM-T4: after the digest, an answer is a card with the exact answer", () => {
  const { run } = fresh();
  run("project_digest", { project: P });
  const d = run("project_answer", ANSWER);
  assert.equal(d.verdict, "confirm");
  assert.equal(d.title, "Jorah wants to record your answer to a project question");
  for (const line of ["key: B", "note: your pick", "project: tree-watering-robot", "question_id: Q-0001"]) assert.ok(d.description.includes(line), line);
  assert.match(d.description, /outside text/);
});

test("after a web search too, and through the tool-search wrapper the inner call still gets its card", () => {
  const { run } = fresh();
  run("web_search", { query: "landscaping firms Bratislava" });
  assert.equal(run("project_answer", ANSWER).verdict, "confirm");
  // The wrapper itself only lets the inner call through; the hook runs again on the inner tool.
  assert.equal(run("tool_call", { id: "project_answer", args: ANSWER }).verdict, "allow");
  const r = run("project_task_result", { project: P, task_id: "A-0001", text: "41 s", files: ["last"] });
  assert.equal(r.verdict, "confirm");
  assert.ok(r.description.includes("task_id: A-0001"));
  assert.ok(r.description.includes("text: 41 s"));
});

test("by voice: answers, results, run now and resume are cards even in a fresh chat", () => {
  const { run } = fresh();
  for (const [tool, params] of [["project_answer", ANSWER], ["project_task_result", { project: P, task_id: "A-0001", text: "40" }], ["project_run_now", { project: P }], ["project_resume", { project: P }]]) {
    const d = run(tool, params, VOICE);
    assert.equal(d.verdict, "confirm", tool);
    assert.match(d.description, /Asked by voice/);
  }
  assert.equal(run("project_pause", { project: P }, VOICE).verdict, "allow");
});

test("Adam's clean chat: answers, results, run now and resume are free; limits are always a card", () => {
  const { run } = fresh();
  for (const [tool, params] of [["project_answer", ANSWER], ["project_task_result", { project: P, task_id: "A-0001", text: "40" }], ["project_run_now", { project: P }], ["project_resume", { project: P }]]) {
    assert.equal(run(tool, params).verdict, "allow", tool);
  }
  const d = run("project_set_limits", { project: P, runsPerDay: 2 });
  assert.equal(d.verdict, "confirm");
  assert.equal(d.title, "Jorah wants to change how much a project may run");
  assert.ok(d.description.includes("runsPerDay: 2"));
  assert.ok(!/outside text/.test(d.description));
});

test("pause is always free: after outside text, by voice, from a scheduled run, even frozen", () => {
  const { run, state } = fresh();
  run("web_fetch", { url: "https://forum.example/thread" });
  assert.equal(run("project_pause", { project: P }).verdict, "allow");
  assert.equal(run("project_pause", { project: P }, DIGEST_JOB, "cron").verdict, "allow");
  state.freeze("test");
  assert.equal(run("project_pause", { project: P }).verdict, "allow");
  assert.equal(run("project_status", { project: P }).verdict, "allow");
});

test("frozen: run now, resume, answers and limits are blocked, also through the wrapper", () => {
  const { run, state } = fresh();
  state.freeze("test");
  for (const [tool, params] of [["project_run_now", { project: P }], ["project_resume", { project: P }], ["project_answer", ANSWER], ["project_set_limits", { project: P, runsPerDay: 1 }], ["project_digest", { project: P }]]) {
    const d = run(tool, params);
    assert.equal(d.verdict, "block", tool);
    assert.match(d.reason, /frozen/);
  }
  assert.equal(run("tool_call", { id: "openclaw:plugin:project_run_now", args: { project: P } }).verdict, "block");
});

test("the 18:00 digest automation may read the digest and notify, but an answer from it is a card", () => {
  const { run } = fresh();
  assert.equal(run("project_digest", { project: P }, DIGEST_JOB, "cron").verdict, "allow");
  assert.equal(run("proactive_notify", { type: "project_digest", class: "digest", text: "tree-watering-robot: 3 runs, 1 done." }, DIGEST_JOB, "cron").verdict, "allow");
  assert.equal(run("project_answer", ANSWER, DIGEST_JOB, "cron").verdict, "confirm");
  assert.equal(run("project_run_now", { project: P }, DIGEST_JOB, "cron").verdict, "confirm");
  assert.equal(run("message", { action: "send", message: "digest" }, DIGEST_JOB, "cron").verdict, "block");
});

test("PM-T7: after a project's digest, code can't be pushed to another repo from that chat", () => {
  const { run } = fresh();
  run("project_digest", { project: P });
  const other = run("github_push_branch", { project: "robot_tour", branch: "jorah/x" });
  assert.equal(other.verdict, "block");
  assert.match(other.reason, /tree-watering-robot/);
  // Its own repo stays possible; jorah-github's card then asks Adam.
  assert.equal(run("github_push_branch", { project: P, branch: "jorah/line" }).verdict, "allow");
  assert.equal(run("github_push_branch", { project: "jorah", branch: "jorah/x" }).verdict, "block");
});

// Starting a project (section 5.1): Jorah sets projects up himself, from Adam's words.
const START = { name: "street-trees", words: "A robot that waters young street trees.", answers: [{ question: "Money?", answer: "You decide" }] };

test("project_start: free in Adam's clean typed chat", () => {
  const { run } = fresh();
  assert.equal(run("project_start", START).verdict, "allow");
  assert.equal(run("project_start", { ...START, repo: "AdamHikl/street-trees" }).verdict, "allow");
});

test("PM-T4: after outside text, a start is a card with Adam's exact words; by voice too", () => {
  const { run } = fresh();
  run("web_fetch", { url: "https://forum.example/ideas" });
  const d = run("project_start", START);
  assert.equal(d.verdict, "confirm");
  assert.equal(d.title, "Jorah wants to start a project from your words");
  assert.ok(d.description.includes("words: A robot that waters young street trees."));
  assert.ok(d.description.includes("name: street-trees"));
  assert.ok(d.description.includes("You decide"));
  assert.match(d.description, /outside text/);
  const v = fresh().run("project_start", START, VOICE);
  assert.equal(v.verdict, "confirm");
  assert.match(v.description, /Asked by voice/);
  assert.equal(run("project_start", START, DIGEST_JOB, "cron").verdict, "confirm");
});

test("connect and level are always a card, even in Adam's clean chat, with the exact repo and level", () => {
  const { run } = fresh();
  const c = run("project_connect", { project: "street-trees", repo: "AdamHikl/street-trees" });
  assert.equal(c.verdict, "confirm");
  assert.equal(c.title, "Jorah wants to connect a project to a GitHub repo");
  assert.ok(c.description.includes("repo: AdamHikl/street-trees"));
  const l = run("project_set_level", { project: P, level: 1, schedule: ["10:30", "16:30"] });
  assert.equal(l.verdict, "confirm");
  assert.equal(l.title, "Jorah wants to change a project's trust level");
  assert.ok(l.description.includes("level: 1"));
  assert.ok(l.description.includes('schedule: ["10:30","16:30"]'));
});

test("frozen: start, connect and level are blocked", () => {
  const { run, state } = fresh();
  state.freeze("test");
  for (const [tool, params] of [["project_start", START], ["project_connect", { project: "street-trees", repo: "AdamHikl/street-trees" }], ["project_set_level", { project: P, level: 0 }]]) {
    const d = run(tool, params);
    assert.equal(d.verdict, "block", tool);
    assert.match(d.reason, /frozen/);
  }
});

test("#14: web and bench for a project are always a card, even in Adam's clean chat, and blocked frozen", () => {
  const { run, state } = fresh();
  const d = run("project_set_capabilities", { project: P, web: true, bench: "robotics" });
  assert.equal(d.verdict, "confirm");
  assert.equal(d.title, "Jorah wants to change a project's web or bench access");
  assert.ok(d.description.includes("web: true"));
  assert.ok(d.description.includes("bench: robotics"));
  state.freeze("test");
  assert.equal(run("project_set_capabilities", { project: P, web: false }).verdict, "block");
});

test("#16: project_preview marks the chat, naming the project", () => {
  const { run, state } = fresh();
  assert.equal(run("project_preview", { project: P }).verdict, "allow");
  assert.match(state.taintOf(ADAM.sessionKey).source, /project_preview/);
});
