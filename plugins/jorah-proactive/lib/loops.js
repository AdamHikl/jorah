// Open loops (C2): things someone is waiting on Adam for, and things Adam promised. Kept in this
// plugin's own store, not in Jorah's memory. A loop is saved only after Adam taps "Allow once" on
// the guard's card for loop_propose, which shows these exact fields; so the tool stores exactly
// what it was given and refuses, rather than changes, anything it wouldn't store as is.

import { addDays, isDate } from "./clock.js";

export const KINDS = Object.freeze({
  waiting_on_me: "someone is waiting on Adam (a reply, a thing, a decision)",
  i_promised: "Adam promised to do something",
});
export const LIMITS = Object.freeze({ who: 60, what: 100, open: 200, keepClosedDays: 30 });
export const EMPTY = Object.freeze({ v: 1, next: 1, items: [] });

const CONTROL = /[\u0000-\u001f\u007f-\u009f\u2028\u2029]/u;

export function checkText(name, value, max) {
  if (typeof value !== "string" || value.length === 0) return `${name} is required`;
  if (value.length > max) return `${name} is longer than ${max} characters`;
  if (CONTROL.test(value)) return `${name} has a line break or control character`;
  if (value.trim() !== value) return `${name} starts or ends with a space`;
  return null;
}

/** Checks a proposal; returns { loop } or { error }. `today` is Adam's local date. */
export function checkProposal(p, today) {
  if (!p || typeof p !== "object") return { error: "no arguments" };
  const extra = Object.keys(p).filter((k) => !["kind", "who", "what", "due"].includes(k));
  if (extra.length) return { error: `unknown field ${extra[0]}` };
  if (!Object.hasOwn(KINDS, p.kind)) return { error: "kind must be waiting_on_me or i_promised" };
  const bad = checkText("who", p.who, LIMITS.who) ?? checkText("what", p.what, LIMITS.what);
  if (bad) return { error: bad };
  if (p.due !== undefined && p.due !== null) {
    if (!isDate(p.due)) return { error: "due must be a date, YYYY-MM-DD" };
    if (p.due < addDays(today, -365) || p.due > addDays(today, 730)) return { error: "due is more than a year back or two years ahead" };
  }
  return { loop: { kind: p.kind, who: p.who, what: p.what, due: p.due ?? null } };
}

const view = (l, today) => ({
  id: l.id, kind: l.kind, who: l.who, what: l.what, due: l.due, status: l.status,
  ...(l.status === "open" && l.due ? { overdue: l.due < today, due_today: l.due === today } : {}),
  created: l.created_at.slice(0, 10), ...(l.closed_at ? { closed: l.closed_at.slice(0, 10) } : {}),
});

export function addLoop(data, loop, now) {
  const open = data.items.filter((l) => l.status === "open");
  const same = open.find((l) => l.kind === loop.kind && l.who === loop.who && l.what === loop.what);
  if (same) return { error: `already open as ${same.id}` };
  if (open.length >= LIMITS.open) return { error: `${LIMITS.open} loops are open already; close some first` };
  const item = { id: `L${data.next}`, ...loop, status: "open", created_at: now.toISOString(), closed_at: null };
  data.next += 1;
  data.items.push(item);
  return { item };
}

export function closeLoop(data, id, status, now) {
  if (typeof id !== "string" || !/^L[0-9]{1,6}$/.test(id)) return { error: "id must look like L12" };
  const item = data.items.find((l) => l.id === id);
  if (!item) return { error: `no loop ${id}` };
  if (item.status !== "open") return { error: `${id} is ${item.status} already` };
  item.status = status;
  item.closed_at = now.toISOString();
  return { item };
}

/** Drops closed loops older than the retention window. */
export function prune(data, now) {
  const cutoff = now.getTime() - LIMITS.keepClosedDays * 86400000;
  data.items = data.items.filter((l) => l.status === "open" || Date.parse(l.closed_at ?? l.created_at) >= cutoff);
}

export function listLoops(data, { status = "open", today }) {
  const items = data.items.filter((l) => status === "all" || l.status === status);
  items.sort((a, b) => (a.due ?? "9999").localeCompare(b.due ?? "9999") || a.id.localeCompare(b.id, "en", { numeric: true }));
  return items.map((l) => view(l, today));
}

/** For today_picture and the triggers: open loops due today or overdue, plus a count of undated. */
export function dueSummary(data, today) {
  const open = data.items.filter((l) => l.status === "open");
  const dueToday = open.filter((l) => l.due === today).map((l) => view(l, today));
  const overdue = open.filter((l) => l.due && l.due < today).map((l) => view(l, today)).sort((a, b) => a.due.localeCompare(b.due));
  const tomorrow = addDays(today, 1);
  return {
    status: "ok", due_today: dueToday, overdue, due_tomorrow: open.filter((l) => l.due === tomorrow).length,
    open_total: open.length, open_undated: open.filter((l) => !l.due).length,
  };
}
