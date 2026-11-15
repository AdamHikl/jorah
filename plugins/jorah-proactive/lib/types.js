// The catalogue of proactive types (config/proactive/types.json): what each one is, its class,
// how its line is written, and what its preview card tells Adam. A type reaches Adam only when it
// is also in the plugin's `enabledTypes`, which Adam approves type by type (01 section 11).

import { readFileSync } from "node:fs";

export const CLASSES = ["P0", "P1", "P2", "P3", "digest"];
const RANK = { P0: 0, P1: 1, P2: 2, P3: 3 };
const RENDER = ["code", "text"];
const CARD = ["title", "trigger", "channel", "frequency", "off"];

export function loadCatalogue(file) {
  const raw = JSON.parse(readFileSync(file, "utf8"));
  if (!raw || raw.version !== 1 || typeof raw.types !== "object") throw new Error("types file: version 1 with a types object expected");
  const types = new Map();
  for (const [name, t] of Object.entries(raw.types)) {
    if (!/^[a-z][a-z0-9_]{1,40}$/.test(name)) throw new Error(`types file: bad type name ${name}`);
    if (!CLASSES.includes(t?.class)) throw new Error(`types file: ${name} has no valid class`);
    if (!RENDER.includes(t.render)) throw new Error(`types file: ${name} render must be code or text`);
    for (const k of CARD) if (typeof t[k] !== "string" || !t[k]) throw new Error(`types file: ${name} lacks ${k}`);
    if (t.maxPerDay !== undefined && !(Number.isInteger(t.maxPerDay) && t.maxPerDay >= 1 && t.maxPerDay <= 20)) throw new Error(`types file: ${name} maxPerDay`);
    types.set(name, Object.freeze({ name, ...t }));
  }
  return types;
}

/** The less urgent of two classes; digest stays digest. */
export function lessUrgent(a, b) {
  if (a === "digest" || b === "digest") return "digest";
  return RANK[a] >= RANK[b] ? a : b;
}

/** The preview card text for one type (01 section 11: trigger, channel, frequency, how to turn it off). */
export function previewCard(t) {
  return [`${t.title} (${t.name}, ${t.class})`, `When: ${t.trigger}`, `Where: ${t.channel}`, `How often: ${t.frequency}`, `Turn off: ${t.off}`].join("\n");
}
