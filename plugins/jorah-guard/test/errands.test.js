// jorah-guard and jorah-errands (docs/runbooks/errands.md): the reads stay free, a supplies change is
// free only in Adam's clean typed chat, deleting one is always a card, and the reminder calls the
// plugin builds pass the schedule rule as one-off reminders: free in a clean chat, a card after
// outside text (a shop page, deep's research) or by voice. Lens powers are placeholders.

import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { classify, decide } from "../lib/policy.js";
import { GuardState } from "../lib/state.js";
import { buildReminder } from "../../jorah-errands/lib/reminder.js";
import { applySave, status } from "../../jorah-errands/lib/supplies.js";

const here = dirname(fileURLToPath(import.meta.url));
const matrix = JSON.parse(readFileSync(join(here, "..", "..", "..", "config", "permission-matrix.json"), "utf8"));
const MANIFEST = join(here, "..", "..", "jorah-errands", "openclaw.plugin.json");
const settings = { workspace: "/home/jorah/workspace", cleanSessionKeys: ["agent:main:main"] };

const ADAM = { agentId: "main", sessionKey: "agent:main:main", requester: { channel: "telegram", senderId: "owner-id", senderIsOwner: true } };
const VOICE = { agentId: "main", sessionKey: "agent:main:voice-1", requester: { channel: "webchat", senderIsOwner: true } };
const DEEP = { agentId: "deep", sessionKey: "agent:deep:subagent:research-1" };
const NOW = new Date("2026-11-17T15:00:00Z");
const TZ = "Europe/Bratislava";

const SAVE = { id: "contact-lenses", event: { type: "purchase", packs: { right: 1, left: 1 }, shop: "Shop A" } };

function fresh() {
  const dir = mkdtempSync(join(tmpdir(), "jorah-guard-errands-"));
  const state = new GuardState(dir);
  const view = {
    taintOf: (k) => state.taintOf(k), hasSeen: (k, u) => state.hasSeen(k, u), wordsOf: (k) => state.wordsOf(k),
    readRepos: (k) => state.readRepos(k), countAcp: (k) => state.countAcp(k), frozen: () => state.frozen(), parentOf: (k) => state.parentOf(k),
  };
  const run = (tool, params, ctx = ADAM, trigger = "user") => {
    const d = decide({ tool, params, ctx, matrix, view, settings, run: { trigger } });
    if (d.taint && d.verdict !== "block") state.markTainted(ctx.sessionKey, d.taint);
    return d;
  };
  return { state, run };
}

const restockCall = () => {
  const at = { todayDate: "2026-11-17", nowIso: NOW.toISOString() };
  let s = applySave(null, {
    name: "Contact lenses", product: "Example Lens 30", leadDays: 30,
    lines: [{ key: "right", spec: "PLACEHOLDER-R", perPack: 6, use: { units: 1, days: 30 } }, { key: "left", spec: "PLACEHOLDER-L", perPack: 6, use: { units: 1, days: 30 } }],
  }, at);
  s = applySave(s, { event: { type: "purchase", packs: { right: 1, left: 1 } } }, at);
  return status(s, { todayDate: "2026-11-17", timeZone: TZ, now: NOW }).reminder.call;
};

test("matrix: every jorah-errands tool has its class and card title", () => {
  const tools = JSON.parse(readFileSync(MANIFEST, "utf8")).contracts.tools;
  assert.equal(tools.length, 6);
  for (const t of tools) assert.notEqual(classify(matrix, t), null, t);
  for (const t of ["reminder_job", "price_compare", "supply_list", "supply_plan"]) assert.equal(classify(matrix, t), "read", t);
  assert.equal(classify(matrix, "supply_save"), "localWrite");
  assert.equal(classify(matrix, "supply_forget"), "confirmAlways");
  for (const t of ["supply_save", "supply_forget"]) assert.ok(matrix.cardTitles[t], t);
});

test("Adam's clean chat: saves and the reminders the plugin builds go through without a card", () => {
  const { run, state } = fresh();
  assert.equal(run("supply_list", {}).verdict, "allow");
  assert.equal(run("supply_save", SAVE).verdict, "allow");
  assert.equal(run("automations", restockCall()).verdict, "allow");
  const generic = buildReminder({ text: "Call the dentist", when: { inDays: 2 }, timeZone: TZ, now: NOW }).call;
  assert.equal(run("automations", generic).verdict, "allow");
  assert.equal(state.taintOf(ADAM.sessionKey)?.tainted ?? false, false);
});

test("deleting a record is always a card, even in a clean chat", () => {
  const { run } = fresh();
  const d = run("supply_forget", { id: "contact-lenses" });
  assert.equal(d.verdict, "confirm");
  assert.equal(d.title, "Jorah wants to delete a supplies record");
  assert.match(d.description, /id: contact-lenses/);
});

test("after shop research, a purchase and its reminder each show Adam a card with the exact fields", () => {
  const { run } = fresh();
  assert.equal(run("web_search", { query: "example lens 30 price" }).verdict, "allow");
  const save = run("supply_save", SAVE);
  assert.equal(save.verdict, "confirm");
  assert.equal(save.title, "Jorah wants to update your supplies record");
  assert.match(save.description, /read outside text/);
  assert.match(save.description, /event: .*purchase/);
  const remind = run("automations", restockCall());
  assert.equal(remind.verdict, "confirm");
  assert.match(remind.description, /Reminder Adam asked for/);
  // Reads stay free and change nothing.
  for (const t of ["supply_list", "supply_plan", "reminder_job", "price_compare"]) assert.equal(run(t, {}).verdict, "allow", t);
});

test("deep's result marks the chat too, so a save after it is a card", () => {
  const { run } = fresh();
  assert.equal(run("sessions_spawn", { agentId: "deep", task: "Compare shops for Example Lens 30 in Slovakia" }).verdict, "allow");
  assert.equal(run("supply_save", SAVE).verdict, "confirm");
});

test("by voice, a save is a card; deep may use price_compare but never saves silently", () => {
  const { run } = fresh();
  assert.equal(run("supply_save", SAVE, VOICE).verdict, "confirm");
  assert.equal(run("price_compare", { offers: [] }, DEEP).verdict, "allow");
  assert.equal(run("supply_save", SAVE, DEEP).verdict, "confirm");
});

test("a reminder whose own text mentions the web is a card even in a clean chat", () => {
  const { run } = fresh();
  const call = buildReminder({ text: "Search for a cheaper lens shop", when: { inDays: 30 }, timeZone: TZ, now: NOW }).call;
  assert.equal(run("automations", call).verdict, "confirm");
});

test("frozen: reads still answer, saves are blocked", () => {
  const { run, state } = fresh();
  state.freeze("test");
  assert.equal(run("supply_list", {}).verdict, "allow");
  assert.equal(run("supply_save", SAVE).verdict, "block");
  assert.equal(run("automations", restockCall()).verdict, "block");
});
