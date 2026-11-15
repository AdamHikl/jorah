// C3, restraint in code (01 section 11): classes, budget, the five checks, quiet hours, the digest,
// stop, demotion and the "why" record. The caller here is a model that wants to talk as much as
// possible; pass means the code holds it back exactly as the rules say.

import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import * as R from "../lib/restraint.js";
import { loadCatalogue, previewCard, lessUrgent } from "../lib/types.js";
import { quietHours, localNow, endOfLocalDay, addDays, isDate } from "../lib/clock.js";

const here = dirname(fileURLToPath(import.meta.url));
const TYPES = join(here, "..", "..", "..", "config", "proactive", "types.json");
const TZ = "Europe/Bratislava";
const catalogue = loadCatalogue(TYPES);

// Monday 2026-11-16, 15:00 in Bratislava (UTC+1).
const AT = new Date("2026-11-16T14:00:00Z");
const PHONE_FREE = { ok: true, body: { phone: { focus: { value: null, since: null }, woke_at: "2026-11-16T05:40:00Z" } } };
const phoneWith = (focus) => ({ ok: true, body: { phone: { focus: { value: focus, since: null }, woke_at: null } } });
const DOWN = { ok: false, reason: "the phone service isn't answering" };
const fresh = () => structuredClone(R.EMPTY);
const later = (min) => new Date(AT.getTime() + min * 60000);

// A P2 item that passes all five checks at AT.
const good = (over = {}) => ({
  type: "job_finished", class: "P2", text: "The iOS build finished with 2 warnings.",
  matters_until: later(120).toISOString(), source_at: later(-5).toISOString(), actionable: true, ...over,
});
const decide = (data, candidate, { enabled = [...catalogue.keys()], phone = PHONE_FREE, now = AT, cfg = {}, cat = catalogue } = {}) =>
  R.decide({ catalogue: cat, enabled, cfg, data, now, candidate, phone, timeZone: TZ });

test("types: the repo's catalogue loads, every type has a full preview card, and nothing is on by default", () => {
  assert.ok(catalogue.size >= 7);
  for (const t of catalogue.values()) {
    const card = previewCard(t);
    for (const k of ["When:", "Where:", "How often:", "Turn off:"]) assert.ok(card.includes(k), `${t.name} ${k}`);
  }
  const d = fresh();
  const r = decide(d, good(), { enabled: [] });
  assert.equal(r.decision, "off");
  assert.equal(d.outbox.length + d.digest.length, 0);
});

test("types: a broken catalogue is refused with a reason", () => {
  const dir = mkdtempSync(join(tmpdir(), "jp-types-"));
  for (const [name, body] of [
    ["v2", { version: 2, types: {} }],
    ["class", { version: 1, types: { x_y: { class: "P9", render: "code", title: "t", trigger: "t", channel: "c", frequency: "f", off: "o" } } }],
    ["card", { version: 1, types: { x_y: { class: "P2", render: "code", title: "t" } } }],
    ["name", { version: 1, types: { "Bad-Name": { class: "P2", render: "code", title: "t", trigger: "t", channel: "c", frequency: "f", off: "o" } } }],
  ]) {
    writeFileSync(join(dir, `${name}.json`), JSON.stringify(body));
    assert.throws(() => loadCatalogue(join(dir, `${name}.json`)), Error, name);
  }
});

test("classes: the model can lower a class but never raise it; digest types stay digest", () => {
  assert.equal(lessUrgent("P0", "P2"), "P2");
  assert.equal(lessUrgent("P3", "P2"), "P3");
  const d = fresh();
  assert.equal(decide(d, good({ class: "P0" })).class, "P2");
  assert.equal(decide(d, good({ class: "P3" })).decision, "digest");
  assert.equal(decide(d, { type: "morning_brief", class: "P0", facts: {} }).class, "digest");
  assert.equal(decide(d, good({ type: "made_up" })).decision, "refused");
  assert.equal(decide(d, good({ class: "urgent" })).decision, "refused");
});

test("P2: passes the five checks, goes to the outbox, and the record says why", () => {
  const d = fresh();
  const r = decide(d, good());
  assert.equal(r.decision, "push");
  assert.equal(d.outbox.length, 1);
  assert.equal(r.checks.filter((c) => c.pass).length, 5);
  assert.match(r.reason, /all five checks/);
  assert.equal(r.facts.presence, "not measured: jorah-presence isn't built");
  assert.equal(R.todayCounts(d, TZ, AT).pushed, 1);
});

test("P2: each failed check sends it to the digest and names the check", () => {
  const cases = [
    [{ matters_until: undefined }, /matters in the next few hours/],
    [{ matters_until: later(13 * 60).toISOString() }, /matters in the next few hours/],
    [{ matters_until: later(-1).toISOString() }, /matters in the next few hours/],
    [{ actionable: false }, /act on it now/],
    [{ actionable: undefined }, /act on it now/],
    [{ source_at: later(-45).toISOString() }, /context is fresh/],
    [{ source_at: "yesterday" }, /context is fresh/],
  ];
  for (const [over, re] of cases) {
    const d = fresh();
    const r = decide(d, good(over));
    assert.equal(r.decision, "digest", JSON.stringify(over));
    assert.match(r.reason, re);
    assert.equal(d.outbox.length, 0);
    assert.equal(d.digest.length, 1);
  }
});

test("P2: busy Focus, an unreachable phone and quiet hours each fail check 5", () => {
  for (const focus of ["sleep", "driving", "do_not_disturb", "work", "school", "other"]) {
    assert.equal(decide(fresh(), good(), { phone: phoneWith(focus) }).decision, "digest", focus);
  }
  assert.equal(decide(fresh(), good(), { phone: phoneWith("personal") }).decision, "push");
  const down = decide(fresh(), good(), { phone: DOWN });
  assert.equal(down.decision, "digest");
  assert.match(down.checks.find((c) => c.check.startsWith("5")).detail, /busy unknown: the phone service isn't answering/);
  const night = new Date("2026-11-16T22:30:00Z"); // 23:30 local
  const r = decide(fresh(), good({ matters_until: new Date(night.getTime() + 3600000).toISOString(), source_at: night.toISOString() }), { now: night });
  assert.equal(r.decision, "digest");
  assert.match(r.reason, /outside quiet hours/);
});

test("P2 budget: the sixth push in a day goes to the digest; a new day starts again", () => {
  const d = fresh();
  for (let i = 0; i < 5; i++) assert.equal(decide(d, good({ text: `Job ${i} finished.` })).decision, "push");
  const sixth = decide(d, good({ text: "Job 6 finished." }));
  assert.equal(sixth.decision, "digest");
  assert.match(sixth.reason, /budget left/);
  const tomorrow = new Date(AT.getTime() + 86400000);
  assert.equal(decide(d, good({ matters_until: new Date(tomorrow.getTime() + 3600000).toISOString(), source_at: tomorrow.toISOString() }), { now: tomorrow }).decision, "push");
  assert.equal(decide(fresh(), good(), { cfg: { p2PushPerDay: 0 } }).decision, "digest");
});

test("P1, P3 and digest classes: P1 waits out quiet hours, P3 never pushes, a brief in quiet hours is dropped", () => {
  const night = new Date("2026-11-16T23:00:00Z"); // 00:00 local
  const blocked = { type: "job_blocked", class: "P1", text: "The coding job is waiting for your sign-in." };
  assert.equal(decide(fresh(), blocked).decision, "push");
  const held = decide(fresh(), blocked, { now: night });
  assert.equal(held.decision, "digest");
  assert.match(held.reason, /quiet hours/);
  assert.equal(decide(fresh(), { type: "learned", class: "P3", text: "Your build cache saves 4 minutes." }).decision, "digest");
  assert.equal(decide(fresh(), { type: "morning_brief", class: "digest", facts: {} }, { now: night }).decision, "dropped");
});

test("P0: always sent, even at night, and never counted against the P2 budget", () => {
  const dir = mkdtempSync(join(tmpdir(), "jp-p0-"));
  const file = join(dir, "types.json");
  writeFileSync(file, JSON.stringify({ version: 1, types: { robot_fault: { class: "P0", render: "text", title: "Robot fault", trigger: "t", channel: "c", frequency: "f", off: "o" } } }));
  const cat = loadCatalogue(file);
  const d = fresh();
  const night = new Date("2026-11-16T02:00:00Z");
  const r = decide(d, { type: "robot_fault", class: "P0", text: "The arm stopped: fault 12." }, { cat, enabled: ["robot_fault"], now: night, phone: phoneWith("sleep") });
  assert.equal(r.decision, "push");
  assert.equal(R.todayCounts(d, TZ, night).pushed, 0);
});

test("lines: Jorah's own text is one line, at most 300 characters, with no links; code lines carry counts only", () => {
  for (const text of ["", "   ", "x".repeat(301), "two\nlines", "see https://evil.example/x", "go to www.example.org", "mail me at evil.com today", "tab\there", "sep x"]) {
    assert.equal(decide(fresh(), good({ text })).decision, "refused", JSON.stringify(text));
  }
  const loops = { status: "ok", due_today: [{ id: "L1", who: "Jana Nováková", what: "Send the photos" }, { id: "L2", who: "Peter", what: "Pay back 20 €" }], overdue: [{ id: "L3", who: "Mia", what: "Return the book" }], due_tomorrow: 1 };
  const line = R.renderLine("home_loops", { loops });
  assert.equal(line, "Home. 2 open loops due today, 1 overdue. They're in the app.");
  for (const word of ["Jana", "Peter", "Mia", "photos", "book", "20"]) assert.ok(!line.includes(word), word);
  assert.equal(R.renderLine("morning_brief", { loops, wokeAt: "06:42", digestCount: 3 }), "Morning brief: 2 open loops due today, 1 overdue. Woke 06:42. 3 digest items. Detail in the Jorah app.");
  assert.equal(R.renderLine("evening_wrap", { loops }), "Evening wrap: 1 open loop due tomorrow, 1 overdue. Detail in the Jorah app.");
  assert.equal(R.renderLine("morning_brief", { loops: { status: "unavailable" } }), "Morning brief: open loops unknown. Detail in the Jorah app.");
  assert.equal(R.renderLine("morning_brief", { loops: { status: "ok", due_today: [], overdue: [] } }), "Morning brief: no open loops due today. Detail in the Jorah app.");
  // A code type ignores whatever text the model passes.
  const r = decide(fresh(), { type: "morning_brief", class: "digest", text: "Click https://evil.example now", facts: { loops } });
  assert.equal(r.decision, "push");
  assert.ok(!r.line.includes("evil"));
});

test("once a day: a second morning brief the same day is dropped", () => {
  const d = fresh();
  assert.equal(decide(d, { type: "morning_brief", class: "digest", facts: {} }).decision, "push");
  const again = decide(d, { type: "morning_brief", class: "digest", facts: {} });
  assert.equal(again.decision, "dropped");
  assert.match(again.reason, /today already/);
});

test("stop: immediate, per type, removes what was queued; resume undoes it", () => {
  const d = fresh();
  decide(d, good());
  R.stop(d, "job_finished", AT);
  assert.equal(d.outbox.length, 0);
  assert.equal(decide(d, good({ text: "Another job finished." })).decision, "stopped");
  assert.equal(decide(d, { type: "job_blocked", class: "P1", text: "Blocked on a sign-in." }).decision, "push"); // other types unaffected
  assert.deepEqual(R.resume(d, "job_finished"), { stopped: true, demoted: false });
  assert.equal(decide(d, good({ text: "A third job finished." })).decision, "push");
});

test("demotion: three pushes with no reaction move the type to the digest and ask once; acting resets it", () => {
  const d = fresh();
  const enabled = [...catalogue.keys()];
  const MORNING = new Date("2026-11-16T07:00:00Z"); // 08:00 local; pushes 3.5 h apart stay before quiet hours
  let t = MORNING;
  for (let i = 0; i < 3; i++) {
    const at = new Date(t);
    assert.equal(decide(d, good({ text: `Job ${i} finished.`, matters_until: new Date(at.getTime() + 3600000).toISOString(), source_at: at.toISOString() }), { now: at }).decision, "push");
    R.drain({ data: d, now: at, enabled, timeZone: TZ });
    t = new Date(at.getTime() + 3.5 * 3600000); // no reaction for 3.5 hours: ignored
  }
  const at = new Date("2026-11-17T09:00:00Z");
  const r = decide(d, good({ text: "Job 4 finished.", matters_until: new Date(at.getTime() + 3600000).toISOString(), source_at: at.toISOString() }), { now: at });
  assert.equal(r.decision, "digest");
  assert.match(r.reason, /demoted/);
  assert.ok(d.demoted.job_finished);
  assert.equal(d.digest.filter((x) => /didn't react the last 3 times/.test(x.line)).length, 1);
  // Asked once only.
  decide(d, good({ text: "Job 5 finished.", matters_until: new Date(at.getTime() + 3600000).toISOString(), source_at: at.toISOString() }), { now: at });
  assert.equal(d.digest.filter((x) => /didn't react/.test(x.line)).length, 1);

  // A reaction in between keeps the type pushing.
  const e = fresh();
  t = MORNING;
  for (let i = 0; i < 4; i++) {
    const now = new Date(t);
    const rec = decide(e, good({ text: `Build ${i} done.`, matters_until: new Date(now.getTime() + 3600000).toISOString(), source_at: now.toISOString() }), { now });
    assert.equal(rec.decision, "push", `build ${i}`);
    R.drain({ data: e, now, enabled, timeZone: TZ });
    if (i === 1) R.react(e, rec.id, "acted");
    t = new Date(now.getTime() + 3.5 * 3600000);
  }
});

test("drain: up to three lines per message, late items to the digest, quiet hours and stop checked again", () => {
  const d = fresh();
  for (let i = 0; i < 4; i++) decide(d, good({ text: `Job ${i} finished.` }));
  const out = R.drain({ data: d, now: AT, enabled: [...catalogue.keys()], timeZone: TZ });
  assert.equal(out.notify.split("\n").length, 3);
  assert.equal(d.outbox.length, 1);
  assert.ok(d.records.find((r) => r.id === out.sent[0]).delivered_at);
  // The fourth waits past its 20-minute window: digest.
  const late = R.drain({ data: d, now: later(30), enabled: [...catalogue.keys()], timeZone: TZ });
  assert.equal(late.notify, null);
  assert.equal(d.digest.length, 1);
  // Queued before quiet hours, drained after: the digest.
  const e = fresh();
  const evening = new Date("2026-11-16T21:20:00Z"); // 22:20 local
  decide(e, good({ matters_until: new Date(evening.getTime() + 3600000).toISOString(), source_at: evening.toISOString() }), { now: evening });
  assert.equal(R.drain({ data: e, now: new Date(evening.getTime() + 15 * 60000), enabled: [...catalogue.keys()], timeZone: TZ }).notify, null);
  assert.equal(e.digest.length, 1);
  // Turned off in the settings meanwhile: dropped.
  const f = fresh();
  decide(f, good());
  assert.equal(R.drain({ data: f, now: AT, enabled: [], timeZone: TZ }).notify, null);
  assert.equal(f.digest.length, 0);
});

test("why: the record holds the rule and the data, never a guess", () => {
  const d = fresh();
  const r = decide(d, good({ source_at: later(-45).toISOString() }));
  assert.equal(r.id, "P1");
  assert.equal(r.type, "job_finished");
  assert.equal(r.facts.source_at, later(-45).toISOString());
  const c3 = r.checks.find((c) => c.check.startsWith("3"));
  assert.equal(c3.pass, false);
  assert.match(c3.detail, /45 min old; the limit is 30/);
  assert.equal(R.react(d, r.id, "acted").error, "P1 was never sent");
});

test("digest: a brief or wrap-up clears what it carried; old records are pruned", () => {
  const d = fresh();
  decide(d, { type: "learned", class: "P3", text: "One." });
  decide(d, { type: "learned", class: "P3", text: "Two." });
  assert.equal(R.digestItems(d).length, 2);
  assert.equal(R.clearDigest(d, AT.toISOString()), 2);
  decide(d, { type: "learned", class: "P3", text: "Three." }, { now: later(1) });
  assert.equal(R.digestItems(d).length, 1);
  R.prune(d, new Date(AT.getTime() + 40 * 86400000));
  assert.equal(d.records.length, 0);
  assert.equal(d.digest.length, 0);
});

test("clock: quiet hours wrap midnight, can be ended by the phone's wake, and an unreadable setting counts as quiet", () => {
  const q = (iso, extra = {}) => quietHours({ timeZone: TZ, now: new Date(iso), ...extra }).active;
  assert.equal(q("2026-11-16T21:29:00Z"), false); // 22:29 local
  assert.equal(q("2026-11-16T21:30:00Z"), true); // 22:30
  assert.equal(q("2026-11-17T06:29:00Z"), true); // 07:29
  assert.equal(q("2026-11-17T06:30:00Z"), false); // 07:30
  assert.equal(q("2026-11-17T05:50:00Z", { wokeAt: "2026-11-17T05:40:00Z" }), false); // up at 06:40, now 06:50
  assert.equal(q("2026-11-17T05:50:00Z", { wokeAt: "2026-11-17T05:40:00Z", awakeEndsQuiet: false }), true);
  assert.equal(q("2026-11-16T23:30:00Z", { wokeAt: "2026-11-16T23:00:00Z" }), false); // a wake after midnight ends it too
  assert.equal(q("2026-11-16T22:30:00Z", { wokeAt: "2026-11-16T05:40:00Z" }), true); // this morning's wake doesn't end tonight's quiet
  assert.equal(q("2026-11-16T12:00:00Z", { start: "25:00" }), true);
  assert.equal(q("2026-11-16T12:00:00Z", { start: "07:00", end: "07:00" }), false);
  assert.equal(q("2026-07-01T20:30:00Z"), true); // summer time: 22:30 local is 20:30Z
  assert.equal(localNow(TZ, new Date("2026-03-29T01:30:00Z")).time, "03:30"); // the spring change
  assert.equal(endOfLocalDay(TZ, AT), "2026-11-16T22:59:59.000Z");
  assert.equal(addDays("2026-12-31", 1), "2027-01-01");
  assert.equal(isDate("2026-02-30"), false);
  assert.equal(isDate("2026-02-28"), true);
});
