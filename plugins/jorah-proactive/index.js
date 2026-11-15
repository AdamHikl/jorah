// OpenClaw plugin: Jorah's proactive layer, step C of the phone-layer plan (docs/runbooks/proactive.md).
//
// C1 today_picture: one typed object built by code. C2 open loops in this plugin's own store; a
// loop is saved only after Adam's "Allow once" on the guard's card. C3 restraint in code
// (lib/restraint.js): every proactive item goes through proactive_notify, which decides push,
// digest or nothing and keeps a record that answers "why did you tell me". C4 triggers: the
// brief's condition (proactive_due) and the tick (proactive_tick), which reads new phone events
// and hands queued lines to OpenClaw's announce. Nothing here sends a message itself, and the only
// network use is the phone service on 127.0.0.1. Every type is off until Adam lists it in
// enabledTypes. Plain object entry, the same shape definePluginEntry returns, so it needs no build.

import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { localDate, localNow } from "./lib/clock.js";
import * as L from "./lib/loops.js";
import * as R from "./lib/restraint.js";
import { PhoneClient } from "./lib/phone.js";
import { Store, StoreError } from "./lib/store.js";
import { buildToday, due, eventCandidates } from "./lib/today.js";
import { loadCatalogue, previewCard } from "./lib/types.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, "..", "..");

const reply = (body, details = {}) => ({ content: [{ type: "text", text: JSON.stringify(body) }], details });
const fail = (reason, extra = {}) => reply({ status: "unavailable", reason, ...extra }, { status: "unavailable", ...extra });
const refuse = (reason) => reply({ status: "refused", reason }, { status: "refused" });
const why = (e) => (e instanceof StoreError ? e.message : "the plugin's state couldn't be read or written");

const num = (v, d, lo, hi) => (Number.isFinite(v) && v >= lo && v <= hi ? v : d);

/** Settings from plugins.entries.jorah-proactive.config, with the defaults the runbook names. */
export function settings(cfg = {}) {
  return {
    stateDir: cfg.stateDir ?? "/home/jorah/.jorah-proactive",
    typesFile: cfg.typesFile ?? join(REPO, "config", "proactive", "types.json"),
    enabledTypes: Array.isArray(cfg.enabledTypes) ? cfg.enabledTypes.filter((t) => typeof t === "string") : [],
    timeZone: cfg.timeZone ?? "Europe/Bratislava",
    includeHealth: cfg.includeHealth === true,
    phone: {
      serviceUrl: cfg.phoneServiceUrl ?? "http://127.0.0.1:43212",
      tokenFile: cfg.phoneTokenFile ?? "/home/jorah/.config/jorah-phone/read-token",
      contractsDir: cfg.contractsDir ?? join(REPO, "packages", "contracts", "phone"),
      timeoutMs: num(cfg.phoneTimeoutMs, 5000, 500, 20000),
    },
    rules: {
      quietStart: cfg.quietStart ?? R.DEFAULTS.quietStart,
      quietEnd: cfg.quietEnd ?? R.DEFAULTS.quietEnd,
      quietSetByAdam: cfg.quietSetByAdam === true,
      awakeEndsQuiet: cfg.awakeEndsQuiet !== false,
      p2PushPerDay: num(cfg.p2PushPerDay, R.DEFAULTS.p2PushPerDay, 0, 20),
      p2SpokenPerDay: num(cfg.p2SpokenPerDay, R.DEFAULTS.p2SpokenPerDay, 0, 20),
      soonHours: num(cfg.soonHours, R.DEFAULTS.soonHours, 1, 24),
      freshMinutes: num(cfg.freshMinutes, R.DEFAULTS.freshMinutes, 1, 240),
      ignoreAfterHours: num(cfg.ignoreAfterHours, R.DEFAULTS.ignoreAfterHours, 1, 48),
      busyFocuses: Array.isArray(cfg.busyFocuses) ? cfg.busyFocuses : R.DEFAULTS.busyFocuses,
      schoolDays: Array.isArray(cfg.schoolDays) ? cfg.schoolDays.filter((d) => Number.isInteger(d) && d >= 1 && d <= 7) : undefined,
      briefFallback: cfg.briefFallback ?? "07:30",
      briefLatest: cfg.briefLatest ?? "10:00",
    },
  };
}

/** The tools, built from settings; `now` and `logger` are injectable for tests. */
export function createTools(cfg = {}, { logger = console, now = () => new Date() } = {}) {
  const s = settings(cfg);
  const store = new Store(s.stateDir);
  const phone = new PhoneClient({ ...s.phone, logger });
  let catalogue = null;
  let catalogueProblem = null;
  try {
    catalogue = loadCatalogue(s.typesFile);
    const unknown = s.enabledTypes.filter((t) => !catalogue.has(t));
    if (unknown.length) logger.warn?.(`jorah-proactive: enabledTypes names unknown types: ${unknown.join(", ")}`);
  } catch (error) {
    catalogueProblem = String(error?.message ?? error).split("\n")[0].slice(0, 160);
    logger.warn?.(`jorah-proactive: ${catalogueProblem}`);
  }
  const enabled = catalogue ? s.enabledTypes.filter((t) => catalogue.has(t)) : [];
  const tz = s.timeZone;
  let ticking = false;

  const loopsSummary = (at) => {
    try {
      return L.dueSummary(store.read("loops", L.EMPTY), localDate(tz, at));
    } catch (error) {
      return { status: "unavailable", reason: why(error) };
    }
  };
  const readProactive = () => {
    try { return { ok: true, data: store.read("proactive", R.EMPTY) }; } catch (error) { return { ok: false, reason: why(error) }; }
  };
  const wokeAtToday = (p, at) => {
    const w = p?.ok ? p.body.phone.woke_at : null;
    return w && localDate(tz, w) === localDate(tz, at) ? localNow(tz, new Date(w)).time : null;
  };

  const tools = [];
  const tool = (def) => tools.push(def);

  // ---- C1 -----------------------------------------------------------------------------------
  tool({
    name: "today_picture",
    label: "Today's picture",
    description: "Today as one object written by code: Adam's local date and time (Europe/Bratislava), what Adam's phone reported "
      + "(where, woke at, Focus; health only if Adam turned it on), open loops due today or overdue, quiet hours and how many "
      + "pushes are left. Calendar and school say not_connected. Anything unknown says so with a reason; never read it as zero.",
    parameters: { type: "object", additionalProperties: false, properties: {} },
    async execute() {
      const at = now();
      const p = await phone.today();
      const pic = buildToday({ now: at, timeZone: tz, phone: p, loops: loopsSummary(at), proactive: readProactive(), cfg: s.rules, includeHealth: s.includeHealth });
      return reply(pic, { status: "ok", phone: pic.phone.status, loops: pic.loops.status });
    },
  });

  // ---- C2 -----------------------------------------------------------------------------------
  tool({
    name: "loops_list",
    label: "Open loops",
    description: "List Adam's open loops: things someone is waiting on Adam for (waiting_on_me) and things Adam promised (i_promised). "
      + "status: open (default), done, dropped or all.",
    parameters: { type: "object", additionalProperties: false, properties: { status: { enum: ["open", "done", "dropped", "all"] } } },
    async execute(_id, p) {
      const at = now();
      try {
        const items = L.listLoops(store.read("loops", L.EMPTY), { status: p?.status ?? "open", today: localDate(tz, at) });
        return reply({ status: "ok", count: items.length, loops: items }, { status: "ok", count: items.length });
      } catch (error) {
        return fail(why(error));
      }
    },
  });

  tool({
    name: "loop_propose",
    label: "Note an open loop",
    description: "Propose an open loop. Adam sees these exact fields on a card and it is saved only on a tap of Allow once. "
      + "kind: waiting_on_me (someone is waiting on Adam) or i_promised (Adam promised to do it). who: at most 60 characters. "
      + "what: at most 100 characters, one line. due: optional YYYY-MM-DD. Write the fields exactly as they should be stored.",
    parameters: {
      type: "object", additionalProperties: false, required: ["kind", "who", "what"],
      properties: {
        kind: { enum: ["waiting_on_me", "i_promised"] },
        who: { type: "string", minLength: 1, maxLength: L.LIMITS.who },
        what: { type: "string", minLength: 1, maxLength: L.LIMITS.what },
        due: { type: "string", pattern: "^[0-9]{4}-[0-9]{2}-[0-9]{2}$" },
      },
    },
    async execute(_id, p) {
      const at = now();
      const checked = L.checkProposal(p, localDate(tz, at));
      if (checked.error) return refuse(checked.error);
      try {
        const r = store.update("loops", L.EMPTY, (d) => { L.prune(d, at); return L.addLoop(d, checked.loop, at); });
        if (r.error) return refuse(r.error);
        return reply({ status: "saved", loop: { id: r.item.id, kind: r.item.kind, who: r.item.who, what: r.item.what, due: r.item.due } }, { status: "saved", id: r.item.id });
      } catch (error) {
        return fail(why(error));
      }
    },
  });

  for (const [name, status, label] of [["loop_done", "done", "Close a loop as done"], ["loop_drop", "dropped", "Drop a loop"]]) {
    tool({
      name,
      label,
      description: status === "done" ? "Mark an open loop done, by id (L12)." : "Drop an open loop Adam no longer cares about, by id (L12). It is kept 30 days, then removed.",
      parameters: { type: "object", additionalProperties: false, required: ["id"], properties: { id: { type: "string", pattern: "^L[0-9]{1,6}$" } } },
      async execute(_id, p) {
        const at = now();
        try {
          const r = store.update("loops", L.EMPTY, (d) => L.closeLoop(d, p?.id, status, at));
          if (r.error) return refuse(r.error);
          return reply({ status, id: r.item.id }, { status, id: r.item.id });
        } catch (error) {
          return fail(why(error));
        }
      },
    });
  }

  // ---- C3 -----------------------------------------------------------------------------------
  tool({
    name: "proactive_notify",
    label: "Tell Adam something unasked",
    description: "The only way a scheduled or background run may tell Adam anything. Code decides: push to Telegram, the digest, or "
      + "nothing, by class, budget, quiet hours and the five checks, and keeps a record for \"why did you tell me\". "
      + "type: a type from proactive_why. class: P0 safety, P1 decision with a deadline, P2 useful now, P3 digest, digest (the "
      + "brief and wrap-up). For P2 give matters_until and source_at (ISO times) and actionable. text: one neutral line, at most 300 "
      + "characters, no links, no names or private details (Telegram isn't end to end); types written by code ignore it. "
      + "A \"push\" answer means queued: never send it again with the message tool.",
    parameters: {
      type: "object", additionalProperties: false, required: ["type", "class"],
      properties: {
        type: { type: "string", maxLength: 40 },
        class: { enum: ["P0", "P1", "P2", "P3", "digest"] },
        text: { type: "string", maxLength: 300 },
        matters_until: { type: "string", maxLength: 40 },
        source_at: { type: "string", maxLength: 40 },
        actionable: { type: "boolean" },
        want: { enum: ["push", "speak"] },
      },
    },
    async execute(_id, p) {
      if (!catalogue) return fail(`the proactive types can't be read: ${catalogueProblem}`);
      const at = now();
      const t = catalogue.get(p?.type);
      const ph = await phone.today();
      const pre = readProactive();
      if (!pre.ok) return fail(pre.reason);
      const facts = t?.render === "code" ? { loops: loopsSummary(at), wokeAt: wokeAtToday(ph, at), digestCount: pre.data.digest.length } : undefined;
      try {
        const rec = store.update("proactive", R.EMPTY, (d) => {
          R.prune(d, at);
          const r = R.decide({
            catalogue, enabled, cfg: s.rules, data: d, now: at, timeZone: tz, phone: ph,
            candidate: { type: p?.type, class: p?.class, text: p?.text, facts, matters_until: p?.matters_until, source_at: p?.source_at, actionable: p?.actionable, want: p?.want },
          });
          if (r.decision === "push" && t?.class === "digest") r.facts.digest_cleared = R.clearDigest(d, at.toISOString());
          return r;
        });
        const said = {
          push: "Queued for Adam's Telegram; the tick job delivers it within a few minutes. Don't send it again.",
          digest: "Kept for the next brief or wrap-up.",
          off: "This type is off: say nothing about it.",
          stopped: "Adam asked to stop this type: say nothing about it.",
          dropped: "Not sent.",
          refused: "Refused; fix the arguments only if the reason says how.",
        }[rec.decision];
        return reply({ status: rec.decision, record: rec.id, reason: rec.reason, line: rec.line, next: said }, { status: rec.decision, record: rec.id });
      } catch (error) {
        return fail(why(error));
      }
    },
  });

  tool({
    name: "proactive_feedback",
    label: "Adam's reaction to a proactive item",
    description: "Record how Adam reacted to something Jorah said unasked: acted (Adam did something with it), dismissed, or stop "
      + "(\"stop telling me this\": that type stops at once, until Adam says otherwise). Give the record (P12) from the line's "
      + "proactive_why, or the type for stop.",
    parameters: {
      type: "object", additionalProperties: false, required: ["reaction"],
      properties: { record: { type: "string", pattern: "^P[0-9]{1,8}$" }, type: { type: "string", maxLength: 40 }, reaction: { enum: ["acted", "dismissed", "stop"] } },
    },
    async execute(_id, p) {
      const at = now();
      try {
        const out = store.update("proactive", R.EMPTY, (d) => {
          const rec = p?.record ? d.records.find((r) => r.id === p.record) : null;
          if (p?.record && !rec) return { error: `no record ${p.record}` };
          if (p?.reaction === "stop") {
            const type = p?.type ?? rec?.type;
            if (!catalogue?.has(type)) return { error: "stop needs a known type or record" };
            R.stop(d, type, at);
            return { ok: `${catalogue.get(type).title} stopped. Undo: proactive_resume, which asks Adam on a card.` };
          }
          if (!rec) return { error: "acted and dismissed need a record" };
          const r = R.react(d, rec.id, p.reaction);
          return r.error ? r : { ok: `${rec.id} marked ${p.reaction}` };
        });
        if (out.error) return refuse(out.error);
        return reply({ status: "ok", said: out.ok }, { status: "ok" });
      } catch (error) {
        return fail(why(error));
      }
    },
  });

  tool({
    name: "proactive_resume",
    label: "Start a stopped or demoted type again",
    description: "Undo \"stop telling me this\", or move a type back out of the digest after it was demoted. Adam confirms on a card. "
      + "It can't turn on a type Adam hasn't turned on in the settings.",
    parameters: { type: "object", additionalProperties: false, required: ["type"], properties: { type: { type: "string", maxLength: 40 } } },
    async execute(_id, p) {
      if (!catalogue?.has(p?.type)) return refuse("unknown type");
      if (!enabled.includes(p.type)) return refuse(`${p.type} is off in the settings; only Adam can turn it on there`);
      try {
        const was = store.update("proactive", R.EMPTY, (d) => R.resume(d, p.type));
        return reply({ status: "ok", type: p.type, ...was }, { status: "ok" });
      } catch (error) {
        return fail(why(error));
      }
    },
  });

  tool({
    name: "proactive_why",
    label: "Why did you tell me",
    description: "Answer \"why did you tell me that?\": with record (P12), the rule, the checks and the data behind that item. Without "
      + "one: which types are on, stopped or demoted, quiet hours, today's pushes, and the latest decisions.",
    parameters: { type: "object", additionalProperties: false, properties: { record: { type: "string", pattern: "^P[0-9]{1,8}$" } } },
    async execute(_id, p) {
      const at = now();
      const pr = readProactive();
      if (!pr.ok) return fail(pr.reason);
      const d = pr.data;
      if (p?.record) {
        const rec = d.records.find((r) => r.id === p.record);
        return rec ? reply({ status: "ok", record: rec, type: catalogue?.get(rec.type) ?? null }, { status: "ok" }) : refuse(`no record ${p.record}`);
      }
      const types = catalogue ? [...catalogue.values()].map((t) => ({
        type: t.name, title: t.title, class: t.class, on: enabled.includes(t.name),
        ...(d.stopped[t.name] ? { stopped: d.stopped[t.name] } : {}), ...(d.demoted[t.name] ? { demoted: d.demoted[t.name].at } : {}),
        card: previewCard(t),
      })) : { status: "unavailable", reason: catalogueProblem };
      const latest = d.records.slice(-8).reverse().map((r) => ({ record: r.id, at: r.at, type: r.type, decision: r.decision, reason: r.reason }));
      return reply({
        status: "ok", types, quiet_hours: { start: s.rules.quietStart, end: s.rules.quietEnd, set_by_adam: s.rules.quietSetByAdam },
        today: R.todayCounts(d, tz, at), push_budget: s.rules.p2PushPerDay, outbox: d.outbox.length, digest: d.digest.length, latest,
      }, { status: "ok" });
    },
  });

  tool({
    name: "digest_list",
    label: "The digest",
    description: "Lines kept for the next brief or wrap-up (P3 items, P2 items that failed a check, P1 items held over quiet hours). "
      + "Reading doesn't clear them; a brief or wrap-up sent through proactive_notify does.",
    parameters: { type: "object", additionalProperties: false, properties: {} },
    async execute() {
      const pr = readProactive();
      if (!pr.ok) return fail(pr.reason);
      const items = R.digestItems(pr.data);
      return reply({ status: "ok", count: items.length, items }, { status: "ok", count: items.length });
    },
  });

  // ---- C4 -----------------------------------------------------------------------------------
  tool({
    name: "proactive_due",
    label: "Is the brief due",
    description: "For the morning brief automation's condition script: is the brief due now, and why.",
    parameters: { type: "object", additionalProperties: false, required: ["type"], properties: { type: { enum: ["morning_brief"] } } },
    async execute(_id, p) {
      const at = now();
      const pr = readProactive();
      if (!pr.ok) return reply({ due: false, reason: pr.reason }, { due: false, reason: pr.reason });
      const ph = p?.type === "morning_brief" ? await phone.today() : null;
      const r = due({ type: p?.type, now: at, timeZone: tz, phone: ph, data: pr.data, cfg: s.rules, enabled });
      return reply(r, r);
    },
  });

  tool({
    name: "proactive_tick",
    label: "Proactive tick",
    description: "Only for the tick automation's script: reads new phone events, turns the chosen kinds into candidates, and hands "
      + "queued lines to delivery. Returns notify: the text OpenClaw's announce sends to Adam, or nothing.",
    parameters: { type: "object", additionalProperties: false, properties: {} },
    async execute() {
      if (!catalogue) return reply({ status: "unavailable", reason: catalogueProblem, notify: null }, { status: "unavailable", notify: null });
      if (ticking) return reply({ status: "busy", notify: null }, { status: "busy", notify: null });
      ticking = true;
      try {
        const at = now();
        const pre = readProactive();
        if (!pre.ok) return reply({ status: "unavailable", reason: pre.reason, notify: null }, { status: "unavailable", notify: null });
        const ph = await phone.today();
        const since = pre.data.cursor.events_since ?? null;
        const ev = since && enabled.some((t) => ["home_loops", "left_home_loops"].includes(t)) ? await phone.events(since) : null;
        const loops = loopsSummary(at);
        const result = store.update("proactive", R.EMPTY, (d) => {
          R.prune(d, at);
          const events = { status: "not_read" };
          if (!since || !d.cursor.events_since) {
            d.cursor.events_since = at.toISOString(); // first tick: start now, never replay the backlog
            events.status = "cursor_started";
          } else if (ev && ev.ok) {
            const list = ev.body.events;
            const { candidates, skipped } = eventCandidates({ events: list, now: at, timeZone: tz, loops, enabled, cfg: s.rules });
            const decided = candidates.map((c) => R.decide({ catalogue, enabled, cfg: s.rules, data: d, now: at, timeZone: tz, phone: ph, candidate: c }));
            if (list.length) d.cursor.events_since = list[list.length - 1].received_at;
            Object.assign(events, { status: "ok", seen: list.length, skipped_stale: skipped, decisions: decided.map((r) => `${r.id} ${r.type} ${r.decision}`) });
          } else if (ev) {
            Object.assign(events, { status: "unavailable", reason: ev.reason });
          } else {
            d.cursor.events_since = at.toISOString(); // no event types on: keep the cursor current
          }
          const out = R.drain({ data: d, now: at, enabled, cfg: s.rules, timeZone: tz, wokeAt: ph?.ok ? ph.body.phone.woke_at : null });
          return { status: "ok", notify: out.notify, sent: out.sent, moved_to_digest_or_dropped: out.moved, events };
        });
        return reply(result, result);
      } catch (error) {
        return reply({ status: "unavailable", reason: why(error), notify: null }, { status: "unavailable", notify: null });
      } finally {
        ticking = false;
      }
    },
  });

  return { tools, settings: s, enabled, catalogueProblem };
}

export default {
  id: "jorah-proactive",
  name: "Jorah proactive",
  description: "Today's picture, open loops, and restraint in code for anything Jorah says unasked.",
  register(api) {
    const { tools, enabled, catalogueProblem } = createTools(api.pluginConfig ?? {}, { logger: api.logger });
    for (const t of tools) api.registerTool(t);
    api.logger.info(`jorah-proactive: ${tools.length} tools; types on: ${enabled.length ? enabled.join(", ") : "none"}${catalogueProblem ? `; TYPES UNREADABLE (${catalogueProblem})` : ""}`);
  },
};
