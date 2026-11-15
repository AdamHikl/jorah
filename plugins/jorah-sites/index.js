// OpenClaw plugin: Jorah's signed-in site readers (docs/runbooks/site-readers.md).
//
// site_read starts the reader-site agent in a fresh session whose key names the site
// (agent:reader-site:site:<name>:<nonce>). jorah-guard reads that key and lets the reader do
// nothing but open and read that site's listed pages in that site's own browser. When the reader
// finishes, its answer is checked here (lib/output.js): only fixed fields pass back to Jorah, and
// the reader's session, which holds the raw page text, is deleted. Plain object entry, the same
// shape definePluginEntry returns, so it needs no build.

import { randomBytes } from "node:crypto";
import { loadSites, sessionKeyFor } from "../jorah-guard/lib/sites.js";
import { brief } from "./lib/brief.js";
import { checkReply } from "./lib/output.js";

const RUN_MS = 180_000;
const text = (t, details = {}) => ({ content: [{ type: "text", text: t }], details });
const answer = (r) => text(JSON.stringify(r), { site: r.site, status: r.status, count: r.items?.length ?? 0 });
const unavailable = (site, reason) => ({ site, status: "unavailable", reason, items: [] });

export function lastAssistantText(messages) {
  for (let i = (messages?.length ?? 0) - 1; i >= 0; i--) {
    const m = messages[i];
    if (m?.role !== "assistant") continue;
    if (typeof m.content === "string" && m.content.trim()) return m.content;
    if (Array.isArray(m.content)) {
      const t = m.content.filter((b) => b?.type === "text" && typeof b.text === "string").map((b) => b.text).join("\n").trim();
      if (t) return t;
    }
  }
  return null;
}

export function today(timeZone, now = new Date()) {
  return new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).format(now);
}

export default {
  id: "jorah-sites",
  name: "Jorah site readers",
  description: "Read Adam's signed-in sites (EduPage first) through a read-only reader; only checked fields come back.",
  register(api) {
    const cfg = api.pluginConfig ?? {};
    const load = () => loadSites({
      dir: cfg.sitesDir ?? "/opt/jorah/config/sites",
      privateFile: cfg.sitesPrivateFile ?? "/etc/jorah/sites.private.json",
      allowTest: cfg.allowTestSites === true,
    });
    const tz = cfg.timeZone ?? "Europe/Bratislava";
    const busy = new Set(); // one read per site at a time: each site has one browser

    api.registerTool({
      name: "sites_list",
      label: "Signed-in sites",
      description: "List Adam's signed-in sites that Jorah can read (for example EduPage), with their pages and whether each is set up.",
      parameters: { type: "object", additionalProperties: false, properties: {} },
      async execute() {
        const { sites } = load();
        const list = [...sites.values()].map((s) => ({
          site: s.name, title: s.title, ready: s.enabled, ...(s.enabled ? {} : { why_not: s.disabledReason }),
          pages: s.pages.map((p) => ({ id: p.id, about: p.about })), kinds: s.kinds,
        }));
        return text(JSON.stringify({ sites: list }), { count: list.length });
      },
    });

    api.registerTool({
      name: "site_read",
      label: "Read a signed-in site",
      description: "Read one of Adam's signed-in sites (see sites_list), such as EduPage for timetable, grades, notices and homework. "
        + "A separate read-only reader opens the pages; you get checked fields only (no links, names hidden). "
        + "Takes up to a few minutes. status \"signed_out\" means Adam must sign in again; tell him.",
      parameters: {
        type: "object",
        additionalProperties: false,
        required: ["site"],
        properties: {
          site: { type: "string", description: "Site name from sites_list, e.g. \"edupage\"" },
          pages: { type: "array", items: { type: "string" }, maxItems: 20, description: "Page ids to read; all pages when left out" },
          question: { type: "string", maxLength: 200, description: "What you want to know, in a short sentence" },
        },
      },
      async execute(_id, p) {
        const name = String(p?.site ?? "");
        const { sites } = load();
        const site = sites.get(name);
        if (!site) return answer(unavailable(name, "no such site; see sites_list"));
        if (!site.enabled) return answer(unavailable(name, `${site.title} isn't set up: ${site.disabledReason}`));
        const wanted = Array.isArray(p?.pages) && p.pages.length ? [...new Set(p.pages.map(String))] : site.pages.map((x) => x.id);
        const unknown = wanted.filter((id) => !site.pages.some((x) => x.id === id));
        if (unknown.length) return answer(unavailable(name, `unknown page ids: ${unknown.slice(0, 5).join(", ")}; see sites_list`));
        const ids = wanted.slice(0, site.maxPagesPerRead);
        const question = typeof p?.question === "string" ? p.question.replace(/\s+/g, " ").trim().slice(0, 200) : "";
        if (busy.has(name)) return answer(unavailable(name, `already reading ${site.title}; try again in a minute`));

        busy.add(name);
        const sessionKey = sessionKeyFor(name, randomBytes(10).toString("hex"));
        let started = false;
        try {
          const run = await api.runtime.subagent.run({ sessionKey, message: brief(site, ids, question, today(tz)), deliver: false });
          started = true;
          const waited = await api.runtime.subagent.waitForRun({ runId: run.runId, timeoutMs: RUN_MS });
          if (waited?.status !== "ok") {
            return answer(unavailable(name, waited?.status === "timeout" || waited?.status === "pending" ? "the reader took too long" : "the reader stopped with an error"));
          }
          const { messages } = await api.runtime.subagent.getSessionMessages({ sessionKey: run.sessionKey ?? sessionKey, limit: 20 });
          const result = checkReply(lastAssistantText(messages), site, { asked: ids });
          api.logger.info(`jorah-sites: ${name} ${result.status}, ${result.items.length} items${result.dropped ? `, ${result.dropped} dropped` : ""}${result.contains_instructions ? ", page had instructions" : ""}`);
          return answer(result);
        } catch (error) {
          api.logger.warn(`jorah-sites: ${name}: ${String(error?.message ?? error).split("\n")[0].slice(0, 200)}`);
          return answer(unavailable(name, started ? "the reader failed" : "couldn't start the reader"));
        } finally {
          busy.delete(name);
          // The reader's session holds the raw page text: never keep it.
          if (started) await Promise.resolve(api.runtime.subagent.deleteSession({ sessionKey })).catch(() => {});
        }
      },
    });
  },
};
