// The Tool Search wrapper: `tool_call` in OpenClaw 2026.10.9, renamed `dispatch_action` in
// 2026.10.33 (canary, 2026-11-19). Either way the Gateway runs before_tool_call again on the inner
// tool under its real name (10.33: tool-search's catalog entries are wrapped with the hook), so the
// guard decides on the wrapper only to block early, and to know which tool a result came from.
//
// The argument shape follows 2026.10.33's dist/tool-search (readToolSearchCallArgs and
// prepareToolSearchDispatcherArguments), read on the PC: the selector is `id`, `toolId` or `name`
// (namespaced ids such as "openclaw:core:web_fetch" end in the tool name); the target's arguments
// are nested in `args` or `input` (10.9 also `arguments`), given as `args.<key>` fields, or flat
// beside the selector; a selector nested inside `args` is lifted up. Anything the guard can't read
// the same way, or that could name two tools, is malformed, and the caller blocks it.

export const WRAPPERS = new Set(["tool_call", "dispatch_action"]);
const SELECTORS = ["id", "toolId", "name"];
const isRecord = (v) => v !== null && typeof v === "object" && !Array.isArray(v);
const selectorOf = (p) => SELECTORS.map((k) => p[k]).find((v) => typeof v === "string" && v.trim());

export function isWrapper(tool) {
  return WRAPPERS.has(tool);
}

/** @returns {{ inner: string, args: object } | { malformed: string }} */
export function unwrap(params) {
  if (!isRecord(params)) return { malformed: "the wrapper call has no arguments" };
  let p = params;
  const nested0 = p.args ?? p.input ?? p.arguments;
  if (!SELECTORS.some((k) => Object.hasOwn(p, k)) && isRecord(nested0) && selectorOf(nested0) !== undefined) {
    const { args: _a, input: _i, arguments: _r, ...outer } = p;
    p = { ...outer, ...nested0, id: selectorOf(nested0) };
  }
  // OpenClaw picks whichever selector matches its catalog, so two different ones could name a tool
  // other than the one the guard reads: refused (put a target's own `name` inside `args`).
  const named = SELECTORS.filter((k) => p[k] !== undefined);
  if (named.length === 0) return { malformed: "the wrapper call names no tool" };
  if (new Set(named.map((k) => p[k])).size > 1) return { malformed: "the wrapper call names more than one tool" };
  const key = named[0];
  const raw = p[key];
  if (typeof raw !== "string" || !raw.trim()) return { malformed: "the wrapper call names no tool" };
  const inner = raw.trim().split(":").pop().trim();
  if (!inner) return { malformed: "the wrapper call names no tool" };
  if (WRAPPERS.has(inner)) return { malformed: "a wrapper can't call another wrapper" };
  const dotted = Object.fromEntries(Object.entries(p).filter(([k]) => k.startsWith("args.") && k.length > 5).map(([k, v]) => [k.slice(5), v]));
  const nested = p.args ?? p.input ?? p.arguments;
  if (nested != null && !(isRecord(nested) && Object.keys(nested).length === 0)) {
    if (!isRecord(nested)) return { malformed: "the wrapper call's arguments aren't an object" };
    return { inner, args: { ...dotted, ...nested } };
  }
  const flat = Object.fromEntries(Object.entries(p).filter(([k]) => !named.includes(k) && k !== "args" && k !== "input" && k !== "arguments" && !(k.startsWith("args.") && k.length > 5)));
  return { inner, args: { ...dotted, ...flat } };
}
