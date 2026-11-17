// OpenClaw plugin: Jorah's errands. Code, not the model, does the parts of everyday errands that
// must be exact, and keeps the one record that must last:
//
//   reminder_job   the exact automations call for any one-shot reminder (a date, "in 3 days", "a
//                  month before 14 May"), in Adam's zone, so no model works out a date or UTC time
//   price_compare  per unit, per month and period totals with shipping, for any shopping question
//   supply_list    things Adam buys again (lenses, vitamins, filters, coffee...) and when each runs out
//   supply_plan    what-if: "if I buy 2 boxes, when do I run out?", saved nothing
//   supply_save    a new supply, a change, a purchase or a count; returns the reminder to (re)set
//   supply_forget  deletes one supply's record
//
// Guard rules (config/permission-matrix.json): the four reads are free; supply_save is free in Adam's
// clean typed chat and a card with the exact fields after outside text or by voice; supply_forget is
// always a card. The plugin sends nothing, sets no schedule itself (Jorah passes reminder calls to
// the automations tool, which the guard checks), and has no network. State: stateDir on the PC, mode
// 700. Health details (a prescription) stay in that file: never logged, never in the repo.
// Plain object entry, the same shape definePluginEntry returns, so it needs no build or install.

import { isTime, isTimeZone, today } from "./lib/dates.js";
import { compare, PriceError } from "./lib/prices.js";
import { buildReminder, ReminderError, slug } from "./lib/reminder.js";
import { Store, StoreError } from "./lib/store.js";
import { applySave, plan, status, SupplyError } from "./lib/supplies.js";

export const TOOLS = ["reminder_job", "price_compare", "supply_list", "supply_plan", "supply_save", "supply_forget"];
const EMPTY = { supplies: {} };
const ID = { type: "string", maxLength: 40, description: "The supply's id as supply_list gives it, e.g. contact-lenses" };

const reply = (body) => ({ content: [{ type: "text", text: JSON.stringify(body) }], details: body });
const refuse = (reason) => reply({ status: "refused", reason });
const unavailable = (reason) => reply({ status: "unavailable", reason });
const firstLine = (e) => String(e?.message ?? e).split("\n")[0].slice(0, 200);
const known = (e) => e instanceof SupplyError || e instanceof ReminderError || e instanceof PriceError;

/** Settings from plugins.entries.jorah-errands.config. */
export function settings(cfg = {}) {
  return {
    stateDir: typeof cfg.stateDir === "string" && cfg.stateDir.startsWith("/") ? cfg.stateDir : "/home/jorah/.jorah-errands",
    timeZone: isTimeZone(cfg.timeZone) ? cfg.timeZone : "Europe/Bratislava",
    remindTime: isTime(cfg.remindTime) ? cfg.remindTime : "09:00",
  };
}

const LINE = {
  type: "object", additionalProperties: false, required: ["key"],
  properties: {
    key: { type: "string", maxLength: 20, description: "Short lower-case name: right, left, main" },
    label: { type: "string", maxLength: 40, description: "e.g. Right eye" },
    spec: { type: ["string", "null"], maxLength: 60, description: "What to order for this line, in Adam's words (a lens power, a size, a colour). Private: it stays in this record" },
    perPack: { type: "integer", minimum: 1, maximum: 100000, description: "Units in one pack (6 lenses in a box)" },
    use: { type: "object", additionalProperties: false, required: ["units", "days"], properties: { units: { type: "number", minimum: 0.001 }, days: { type: "integer", minimum: 1, maximum: 3650 } }, description: "How fast Adam uses them: units per days, e.g. 1 lens per 30 days" },
  },
};

const EVENT = {
  type: "object", additionalProperties: false, required: ["type"],
  description: "A purchase Adam made, or a count of what he has left (unopened). Only what he told you",
  properties: {
    type: { type: "string", enum: ["purchase", "count"] },
    date: { type: "string", description: "YYYY-MM-DD, Adam's local date; default today. Never in the future" },
    packs: { type: ["object", "integer"], description: "purchase: packs per line, e.g. { right: 1, left: 1 }; a number for a one-line supply" },
    units: { type: ["object", "number"], description: "count: units left per line, e.g. { right: 2, left: 2 }; a number for a one-line supply" },
    shop: { type: "string", maxLength: 80 },
    price: { type: "object", additionalProperties: false, required: ["amount", "currency"], properties: { amount: { type: "number", minimum: 0 }, currency: { type: "string", pattern: "^[A-Z]{3}$" } }, description: "What Adam paid in total, if he said" },
    note: { type: "string", maxLength: 200 },
  },
};

export function register(api, { now = () => new Date() } = {}) {
  const s = settings(api.pluginConfig ?? {});
  const store = new Store(s.stateDir);
  const ctx = () => { const n = now(); return { now: n, todayDate: today(s.timeZone, n), timeZone: s.timeZone, defaultTime: s.remindTime }; };
  const read = () => store.read("supplies", EMPTY);
  const failed = (e, what) => (known(e) ? refuse(firstLine(e)) : e instanceof StoreError ? unavailable(`${firstLine(e)}; nothing changed`) : unavailable(`${what} failed; nothing changed`));

  api.registerTool({
    name: "reminder_job",
    label: "Build a reminder",
    catalogMode: "direct-only",
    description: "The exact automations call for a one-shot reminder at a local date and time in Adam's zone. Use it for EVERY reminder on a date or time (\"remind me Friday at 6\", \"in 3 days\", \"a month before 14 May\"), never your own date or UTC maths. Give exactly one of date, inDays, inMinutes or before (with days, weeks or months). Then pass `call` to the automations tool as it is and confirm `local.spoken` back to Adam. A `key` (e.g. passport) makes a later reminder with the same key move this one instead of adding a second. Read-only: it sets nothing itself.",
    parameters: {
      type: "object", additionalProperties: false, required: ["text"],
      properties: {
        text: { type: "string", maxLength: 300, description: "What to tell Adam when it fires, in his words where possible" },
        date: { type: "string", description: "YYYY-MM-DD" },
        inDays: { type: "integer", minimum: 0, maximum: 3650, description: "Calendar days from today (0 is today)" },
        inMinutes: { type: "integer", minimum: 1, maximum: 10080, description: "Minutes from now; takes no time" },
        before: { type: "string", description: "YYYY-MM-DD: remind this long before that date" },
        days: { type: "integer", minimum: 0, maximum: 3650 },
        weeks: { type: "integer", minimum: 0, maximum: 520 },
        months: { type: "integer", minimum: 0, maximum: 120 },
        time: { type: "string", description: "HH:MM, 24-hour, Adam's local time. Default 09:00" },
        key: { type: "string", maxLength: 40, description: "Optional name for this reminder, so a later one with the same key replaces it" },
      },
    },
    async execute(_id, p = {}) {
      try {
        const c = ctx();
        const when = {};
        for (const k of ["date", "inDays", "inMinutes", "before", "days", "weeks", "months", "time"]) if (p[k] !== undefined) when[k] = p[k];
        if (when.before === undefined && (when.days !== undefined || when.weeks !== undefined || when.months !== undefined)) return refuse("days, weeks and months go with before");
        return reply(buildReminder({ text: p.text, when, key: p.key, timeZone: c.timeZone, now: c.now, defaultTime: c.defaultTime }));
      } catch (e) {
        return failed(e, "reminder_job");
      }
    },
  });

  api.registerTool({
    name: "price_compare",
    label: "Compare prices",
    catalogMode: "direct-only",
    description: "Price maths in code for any shopping comparison: price per unit, per month at Adam's rate of use, and the total for a period with shipping and the free-shipping threshold, ranked. Give only prices seen on a shop's page, each with the date it was checked; leave shipping out when the page didn't show it (it stays unknown). Never estimate a price to fill a gap. Read-only.",
    parameters: {
      type: "object", additionalProperties: false, required: ["offers"],
      properties: {
        offers: {
          type: "array", minItems: 1, maxItems: 20,
          items: {
            type: "object", additionalProperties: false, required: ["shop", "unitsPerPack", "checkedOn"],
            properties: {
              shop: { type: "string", maxLength: 80 },
              product: { type: "string", maxLength: 120, description: "Exact product and pack, as the page names it" },
              url: { type: "string", maxLength: 300 },
              packPrice: { type: ["number", "null"], minimum: 0, description: "Price of one pack as shown; null if the page showed none" },
              unitsPerPack: { type: "integer", minimum: 1 },
              shipping: { type: ["number", "null"], minimum: 0, description: "Shipping to Adam's country below the threshold; null if unknown" },
              freeShippingFrom: { type: ["number", "null"], minimum: 0, description: "Order value from which shipping is free, if shown" },
              checkedOn: { type: "string", description: "YYYY-MM-DD the page was read" },
              note: { type: "string", maxLength: 200 },
            },
          },
        },
        need: {
          type: "object", additionalProperties: false, required: ["units", "days"],
          description: "How fast Adam uses it: units per days; lines = variants that each need their own packs (2 for two eyes with different powers)",
          properties: { units: { type: "number", minimum: 0.001 }, days: { type: "integer", minimum: 1, maximum: 3650 }, lines: { type: "integer", minimum: 1, maximum: 20 } },
        },
        periodDays: { type: "integer", minimum: 1, maximum: 3650, description: "Period to price when need is given; default 180" },
        currency: { type: "string", pattern: "^[A-Z]{3}$", description: "All offers in this currency; default EUR" },
      },
    },
    async execute(_id, p = {}) {
      try {
        return reply(compare({ offers: p.offers, need: p.need, periodDays: p.periodDays, currency: p.currency ?? "EUR", todayDate: ctx().todayDate }));
      } catch (e) {
        return failed(e, "price_compare");
      }
    },
  });

  api.registerTool({
    name: "supply_list",
    label: "Supplies",
    catalogMode: "direct-only",
    description: "Things Adam buys again (contact lenses, vitamins, filters, coffee...): what he uses (product, pack, the spec per line such as a lens power), his last purchase, when it runs out and when the reorder reminder is due, all worked out in code. Call it FIRST whenever Adam mentions one (\"I need my lenses\", \"I'm out of X\"). With id: one supply; without: all. Read-only.",
    parameters: { type: "object", additionalProperties: false, properties: { id: ID } },
    async execute(_id, p = {}) {
      let data;
      try { data = read(); } catch (e) { return failed(e, "supply_list"); }
      const c = ctx();
      if (p.id) {
        const sup = data.supplies[p.id] ?? data.supplies[slug(p.id)];
        if (!sup) return reply({ status: "not found", id: p.id, ids: Object.keys(data.supplies) });
        return reply({ status: "ok", today: c.todayDate, supply: status(sup, c) });
      }
      const all = Object.values(data.supplies).map((sup) => status(sup, c));
      return reply({ status: "ok", today: c.todayDate, count: all.length, supplies: all, ...(all.length ? {} : { note: "nothing recorded yet" }) });
    },
  });

  api.registerTool({
    name: "supply_plan",
    label: "Supply what-if",
    catalogMode: "direct-only",
    description: "What-if, saved nothing: when a supply would run out after a purchase or a count, e.g. \"if I buy 2 boxes of 6 per eye today?\". Give id for a saved supply, or perPack and use (or lines) for one that isn't saved. Read-only.",
    parameters: {
      type: "object", additionalProperties: false, required: ["event"],
      properties: {
        id: ID,
        lines: { type: "array", maxItems: 6, items: LINE },
        perPack: { type: "integer", minimum: 1, maximum: 100000 },
        use: LINE.properties.use,
        event: EVENT,
      },
    },
    async execute(_id, p = {}) {
      const c = ctx();
      try {
        let sup;
        if (p.id) {
          sup = read().supplies[p.id];
          if (!sup) return reply({ status: "not found", id: p.id });
        } else {
          sup = applySave(null, { name: "what-if", lines: p.lines, perPack: p.perPack, use: p.use }, { todayDate: c.todayDate, nowIso: c.now.toISOString() });
        }
        return reply({ status: "ok", today: c.todayDate, plan: plan(sup, p.event, c) });
      } catch (e) {
        return failed(e, "supply_plan");
      }
    },
  });

  api.registerTool({
    name: "supply_save",
    label: "Save a supply",
    catalogMode: "direct-only",
    description: "Creates or changes Adam's record of something he buys again, from what he told you: name, product, lines (one per variant, e.g. right and left eye, with spec, perPack and use), and optionally one event: a purchase (packs per line) or a count of what's left. Ask Adam for a pack size or rate you don't know; never guess one. A new supply needs name; to change one give its id. Returns where it stands and `reminder.call`: pass that to the automations tool exactly as given (the same key moves the earlier reminder), then tell Adam the run-out date and the reminder date. If reminder.status is \"due now\", tell Adam now instead. undoLast removes the last purchase or count.",
    parameters: {
      type: "object", additionalProperties: false,
      properties: {
        id: ID,
        name: { type: "string", maxLength: 60, description: "e.g. Contact lenses" },
        product: { type: "string", maxLength: 80, description: "Brand and model, e.g. the lens's name" },
        unit: { type: "string", maxLength: 20, description: "Singular unit: lens, tablet, g, filter" },
        notes: { type: ["string", "null"], maxLength: 300 },
        lines: { type: "array", maxItems: 6, items: LINE, description: "One per variant with its own stock; leave out for a one-line supply and use perPack and use" },
        perPack: { type: "integer", minimum: 1, maximum: 100000, description: "One-line supply: units in a pack" },
        use: LINE.properties.use,
        leadDays: { type: ["integer", "null"], minimum: 0, maximum: 365, description: "Remind this many days before running out (Adam's choice); null: automatic, a third of the last cover, at most 30" },
        remindTime: { type: ["string", "null"], description: "HH:MM for this supply's reminder; default 09:00" },
        event: EVENT,
        undoLast: { type: "boolean" },
      },
    },
    async execute(_id, p = {}) {
      const c = ctx();
      try {
        const result = store.update("supplies", EMPTY, (data) => {
          let id = p.id ? String(p.id).toLowerCase() : null;
          if (!id) {
            if (!p.name) throw new SupplyError("give the supply's id to change it, or a name to start one");
            id = slug(p.name);
          }
          const current = data.supplies[id] ?? null;
          if (!current && !p.name) throw new SupplyError(`no supply ${id}: give a name to start one (supply_list shows the ids)`);
          const next = applySave(current, { ...p, id }, { todayDate: c.todayDate, nowIso: c.now.toISOString() });
          data.supplies[next.id] = next;
          return { created: !current, supply: next };
        });
        api.logger.info(`jorah-errands: supply ${result.supply.id} ${result.created ? "created" : "changed"}${p.event ? ` (${p.event.type})` : ""}${p.undoLast ? " (undo)" : ""}`);
        return reply({ status: "saved", created: result.created, today: c.todayDate, supply: status(result.supply, c) });
      } catch (e) {
        return failed(e, "supply_save");
      }
    },
  });

  api.registerTool({
    name: "supply_forget",
    label: "Forget a supply",
    catalogMode: "direct-only",
    description: "Deletes one supply's record for good (Adam asked). Its reorder reminder, if one is waiting, stays in automations: remove it there with the key this returns.",
    parameters: { type: "object", additionalProperties: false, required: ["id"], properties: { id: ID } },
    async execute(_id, p = {}) {
      try {
        const gone = store.update("supplies", EMPTY, (data) => {
          const sup = data.supplies[p.id];
          if (!sup) throw new SupplyError(`no supply ${String(p.id).slice(0, 40)}`);
          delete data.supplies[p.id];
          return sup;
        });
        api.logger.info(`jorah-errands: supply ${gone.id} forgotten`);
        return reply({ status: "forgotten", id: gone.id, reminder_key: `jorah:restock:${gone.id}`, note: "if a reorder reminder is waiting, remove it with automations (list, then remove the job with this key)" });
      } catch (e) {
        return failed(e, "supply_forget");
      }
    },
  });
}

export default {
  id: "jorah-errands",
  name: "Jorah errands",
  description: "Exact reminder dates, price maths, and a private record of things Adam buys again with run-out dates, all in code.",
  register(api) {
    register(api);
  },
};
