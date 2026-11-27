// /jorah-today (docs/plan/13-autonomy.md 6.5): what Jorah did alone today, from the guard's own
// decision log. Pure apart from readTail. The log holds no arguments, so this counts tool calls,
// not what they did; a missing or unreadable log says so instead of showing zeros.

import { closeSync, existsSync, fstatSync, openSync, readSync } from "node:fs";
import { classify } from "./policy.js";

const TAIL_BYTES = 4 * 1024 * 1024;

// The last maxBytes of the log, without a cut first line. { text, cut } or { missing: true }.
export function readTail(file, maxBytes = TAIL_BYTES) {
  if (!existsSync(file)) return { missing: true };
  const fd = openSync(file, "r");
  try {
    const size = fstatSync(fd).size;
    const n = Math.min(size, maxBytes);
    const buf = Buffer.alloc(n);
    readSync(fd, buf, 0, n, size - n);
    let text = buf.toString("utf8");
    const cut = n < size;
    if (cut) text = text.slice(text.indexOf("\n") + 1);
    return { text, cut };
  } finally {
    closeSync(fd);
  }
}

const WRITES = [
  ["fileWrite", "Files"], ["memoryWrite", "Memory"], ["skill", "Skills"], ["schedule", "Schedules"],
  ["spawn", "Jobs started"], ["localWrite", "Records"], ["ownWordsWrite", "Open loops"],
  ["proactiveSend", "Notices queued"], ["message", "Messages"], ["github", "GitHub (then its own card)"],
];

const localDate = (ms, timeZone) => new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).format(ms);

function countBy(list, key) {
  const m = new Map();
  for (const e of list) m.set(key(e), (m.get(key(e)) ?? 0) + 1);
  return [...m.entries()].sort((a, b) => b[1] - a[1]);
}

const listed = (pairs, max = 4) => pairs.slice(0, max).map(([k, n]) => `${k} ${n}`).join(", ") + (pairs.length > max ? ", …" : "");

export function summarizeDay(tail, { matrix, now = Date.now(), timeZone = "Europe/Bratislava" } = {}) {
  if (!tail || tail.missing) return "No decision log yet, so what Jorah did today is unknown.";
  if (!matrix) return "The permission list is unreadable, so today's log can't be sorted.";
  const today = localDate(now, timeZone);
  let unreadable = 0;
  const entries = [];
  for (const line of String(tail.text ?? "").split("\n")) {
    if (!line.trim()) continue;
    let e;
    try { e = JSON.parse(line); } catch { unreadable++; continue; }
    const at = Date.parse(e?.t);
    if (Number.isNaN(at) || localDate(at, timeZone) !== today) continue;
    if (!["allow", "confirm", "block"].includes(e.verdict)) continue;
    entries.push(e);
  }
  const head = `Today (${today}), from the guard's log:`;
  const notes = [];
  if (tail.cut && entries.length > 0) notes.push("Only the last 4 MB of the log were read, so earlier calls today may be missing.");
  if (unreadable > 0) notes.push(`${unreadable} log line${unreadable === 1 ? "" : "s"} couldn't be read.`);
  if (entries.length === 0) return [head, "Nothing logged today.", ...notes].join("\n");

  const allowed = entries.filter((e) => e.verdict === "allow");
  const alone = allowed.filter((e) => e.readAction !== true && WRITES.some(([c]) => classify(matrix, e.tool) === c));
  const lines = [head, "Done without a card:"];
  let any = false;
  for (const [cls, label] of WRITES) {
    const mine = alone.filter((e) => classify(matrix, e.tool) === cls);
    if (mine.length === 0) continue;
    any = true;
    lines.push(`- ${label}: ${mine.length} (${listed(countBy(mine, (e) => e.tool))})`);
  }
  if (!any) lines.push("- no writes");
  const second = alone.filter((e) => e.second === "pass");
  if (second.length) lines.push(`- of these, allowed by the second check: ${second.length} (${listed(countBy(second, (e) => e.tool))})`);
  const secondNo = entries.filter((e) => e.verdict === "confirm" && typeof e.second === "string" && e.second !== "pass");
  if (secondNo.length) lines.push(`- second check said ask Adam: ${secondNo.length} (${listed(countBy(secondNo, (e) => e.second))})`);
  lines.push(`Reads and searches: ${allowed.length - alone.length}.`);
  const cards = entries.filter((e) => e.verdict === "confirm");
  lines.push(cards.length ? `Cards shown: ${cards.length} (${listed(countBy(cards, (e) => e.tool))}).` : "Cards shown: 0.");
  const blocks = entries.filter((e) => e.verdict === "block");
  lines.push(blocks.length ? `Blocked: ${blocks.length} (${listed(countBy(blocks, (e) => e.tool))}).` : "Blocked: 0.");
  lines.push(`By agent: ${listed(countBy(entries, (e) => e.agent ?? "unknown"), 5)}.`);
  return [...lines, ...notes].join("\n");
}
