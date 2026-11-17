// jorah-errands' tools as OpenClaw calls them, with a stand-in api: registration, the private store
// on disk, logs without private details, and refusals. No Gateway, model or network.

import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import plugin, { register, settings, TOOLS } from "../index.js";

const here = dirname(fileURLToPath(import.meta.url));
const NOW = new Date("2026-11-17T15:00:00Z");
const SPEC_R = "PLACEHOLDER-R";
const SPEC_L = "PLACEHOLDER-L";

function load({ stateDir = join(mkdtempSync(join(tmpdir(), "jorah-errands-")), "state"), now = NOW } = {}) {
  const tools = new Map();
  const logs = [];
  register({
    pluginConfig: { stateDir, timeZone: "Europe/Bratislava", remindTime: "09:00" },
    logger: { info: (m) => logs.push(m), warn: (m) => logs.push(m) },
    on: () => {},
    registerTool: (t) => tools.set(t.name, t),
  }, { now: () => now });
  const call = async (name, params = {}) => JSON.parse((await tools.get(name).execute("call-1", params)).content[0].text);
  return { tools, logs, call, stateDir };
}

const LENSES = {
  name: "Contact lenses", product: "Example Lens 30", unit: "lens", leadDays: 30,
  lines: [
    { key: "right", label: "Right eye", spec: SPEC_R, perPack: 6, use: { units: 1, days: 30 } },
    { key: "left", label: "Left eye", spec: SPEC_L, perPack: 6, use: { units: 1, days: 30 } },
  ],
};

test("manifest, package and registration agree on the six tools", () => {
  const manifest = JSON.parse(readFileSync(join(here, "..", "openclaw.plugin.json"), "utf8"));
  const pkg = JSON.parse(readFileSync(join(here, "..", "package.json"), "utf8"));
  assert.deepEqual(manifest.contracts.tools, TOOLS);
  assert.equal(manifest.id, plugin.id);
  assert.deepEqual(pkg.openclaw.extensions, ["./index.js"]);
  const { tools } = load();
  assert.deepEqual([...tools.keys()].sort(), [...TOOLS].sort());
  for (const t of tools.values()) {
    assert.equal(t.parameters.additionalProperties, false, t.name);
    assert.ok(t.description.length > 40, t.name);
    assert.equal(t.catalogMode, "direct-only", t.name);
  }
  assert.deepEqual(Object.keys(manifest.configSchema.properties).sort(), Object.keys(settings()).sort());
});

test("settings: defaults, and nonsense falls back to them", () => {
  assert.deepEqual(settings(), { stateDir: "/home/jorah/.jorah-errands", timeZone: "Europe/Bratislava", remindTime: "09:00" });
  assert.deepEqual(settings({ stateDir: "relative", timeZone: "Mars/Base", remindTime: "9" }), settings());
});

test("supply_save keeps the record private on disk and out of the logs", async () => {
  const { call, logs, stateDir } = load();
  const r = await call("supply_save", LENSES);
  assert.equal(r.status, "saved");
  assert.equal(r.created, true);
  assert.equal(r.supply.runs_out_on, "unknown");
  assert.equal(statSync(stateDir).mode & 0o777, 0o700);
  assert.equal(statSync(join(stateDir, "supplies.json")).mode & 0o777, 0o600);
  const disk = JSON.parse(readFileSync(join(stateDir, "supplies.json"), "utf8"));
  assert.equal(disk.v, 1);
  assert.equal(disk.supplies["contact-lenses"].lines[0].spec, SPEC_R);
  const bought = await call("supply_save", { id: "contact-lenses", event: { type: "purchase", packs: { right: 1, left: 1 }, shop: "Shop A", price: { amount: 59.8, currency: "EUR" } } });
  assert.equal(bought.created, false);
  assert.equal(bought.supply.runs_out_on, "2027-05-16");
  assert.equal(bought.supply.reminder.call.job.declarationKey, "jorah:restock:contact-lenses");
  for (const line of logs) assert.ok(!line.includes(SPEC_R) && !line.includes(SPEC_L) && !line.includes("Shop A"), line);
  assert.deepEqual(logs, ["jorah-errands: supply contact-lenses created", "jorah-errands: supply contact-lenses changed (purchase)"]);
});

test("saving by name again changes the same supply instead of making a second", async () => {
  const { call } = load();
  await call("supply_save", LENSES);
  const again = await call("supply_save", { name: "Contact lenses", event: { type: "count", units: { right: 4, left: 4 } } });
  assert.equal(again.created, false);
  assert.equal(again.supply.id, "contact-lenses");
  const list = await call("supply_list");
  assert.equal(list.count, 1);
  assert.equal(list.supplies[0].runs_out_on, "2027-03-17"); // 4 lenses, one a month
});

test("supply_list: one, all, unknown id, and nothing yet", async () => {
  const { call } = load();
  assert.equal((await call("supply_list")).note, "nothing recorded yet");
  await call("supply_save", LENSES);
  assert.equal((await call("supply_list", { id: "contact-lenses" })).supply.lines[1].spec, SPEC_L);
  const missing = await call("supply_list", { id: "lenses" });
  assert.equal(missing.status, "not found");
  assert.deepEqual(missing.ids, ["contact-lenses"]);
});

test("supply_plan: a saved supply or an inline one, never saved", async () => {
  const { call } = load();
  await call("supply_save", LENSES);
  const p = await call("supply_plan", { id: "contact-lenses", event: { type: "purchase", packs: { right: 2, left: 2 } } });
  assert.equal(p.plan.runs_out_on, "2027-11-12");
  assert.equal((await call("supply_list", { id: "contact-lenses" })).supply.runs_out_on, "unknown");
  const inline = await call("supply_plan", { perPack: 90, use: { units: 1, days: 1 }, event: { type: "purchase", packs: 1 } });
  assert.equal(inline.plan.runs_out_on, "2027-02-15");
  assert.equal((await call("supply_list")).count, 1);
});

test("refusals change nothing and say why", async () => {
  const { call, stateDir } = load();
  assert.match((await call("supply_save", { product: "x" })).reason, /id|name/);
  assert.match((await call("supply_save", { id: "nothing-here" })).reason, /no supply nothing-here/);
  await call("supply_save", LENSES);
  const before = readFileSync(join(stateDir, "supplies.json"), "utf8");
  const r = await call("supply_save", { id: "contact-lenses", event: { type: "purchase", date: "2030-01-01", packs: { right: 1 } } });
  assert.equal(r.status, "refused");
  assert.match(r.reason, /future/);
  assert.equal(readFileSync(join(stateDir, "supplies.json"), "utf8"), before);
});

test("an unreadable record is left alone, and every call says unavailable", async () => {
  const { call, stateDir } = load();
  await call("supply_save", LENSES);
  writeFileSync(join(stateDir, "supplies.json"), "{broken");
  assert.equal((await call("supply_list")).status, "unavailable");
  const r = await call("supply_save", { id: "contact-lenses", event: { type: "count", units: { right: 1 } } });
  assert.equal(r.status, "unavailable");
  assert.match(r.reason, /nothing changed/);
  assert.equal(readFileSync(join(stateDir, "supplies.json"), "utf8"), "{broken");
});

test("supply_forget deletes the record and names the reminder key", async () => {
  const { call, stateDir } = load();
  await call("supply_save", LENSES);
  const r = await call("supply_forget", { id: "contact-lenses" });
  assert.equal(r.status, "forgotten");
  assert.equal(r.reminder_key, "jorah:restock:contact-lenses");
  assert.ok(!readFileSync(join(stateDir, "supplies.json"), "utf8").includes(SPEC_R));
  assert.equal((await call("supply_forget", { id: "contact-lenses" })).status, "refused");
});

test("reminder_job and price_compare through the tool interface", async () => {
  const { call } = load();
  const r = await call("reminder_job", { text: "Passport expires next month", before: "2027-05-14", months: 1, key: "passport" });
  assert.equal(r.call.job.schedule.at, "2027-04-14T07:00:00.000Z");
  assert.equal(r.call.job.declarationKey, "jorah:reminder:passport");
  assert.equal((await call("reminder_job", { text: "x", months: 1 })).status, "refused");
  assert.equal((await call("reminder_job", { text: "x", date: "2026-11-17", time: "08:00" })).status, "past");
  const c = await call("price_compare", { need: { units: 1, days: 30, lines: 2 }, offers: [{ shop: "Shop A", packPrice: 29.9, unitsPerPack: 6, shipping: 3.9, freeShippingFrom: 50, checkedOn: "2026-11-17" }] });
  assert.equal(c.ranked[0].period.total, 59.8);
  assert.equal((await call("price_compare", { offers: [] })).status, "refused");
});
