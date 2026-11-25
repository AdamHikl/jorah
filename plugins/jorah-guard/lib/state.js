// Session state for the guard (p5-plan 4.1). Taint survives a Gateway restart because it is
// written to disk before the tool it guards runs. If the file can't be read or written, the
// store says "unknown", and the policy treats unknown as tainted. Seen URLs and Adam's latest
// words stay in memory only: after a restart a session has seen nothing, which is stricter.

import { mkdirSync, readFileSync, renameSync, writeFileSync, existsSync, rmSync } from "node:fs";
import { join } from "node:path";

const MAX_SESSIONS = 2000;
const MAX_WRITTEN = 5000;

export class GuardState {
  constructor(dir, { now = () => Date.now() } = {}) {
    this.dir = dir;
    this.file = join(dir, "taint.json");
    this.freezeFile = join(dir, "FROZEN");
    this.carefulFile = join(dir, "CAREFUL");
    this.now = now;
    this.broken = null;
    this.unsaved = false;
    this.data = { sessions: {}, parents: {} };
    this.seen = new Map(); // sessionKey -> Map(normalised URL -> "adam" | "outside")
    this.written = new Map(); // sessionKey -> { tokens: Set, full: boolean }: what the model wrote after outside text
    this.words = new Map(); // sessionKey -> { text, at }
    this.typed = new Map(); // sessionKey -> Adam's own typed messages in this session, newest last
    this.acp = new Map(); // sessionKey -> [timestamps]
    this.current = new Map(); // sessionKey -> sessionId last seen in a hook
    try {
      mkdirSync(dir, { recursive: true, mode: 0o700 });
      if (existsSync(this.file)) {
        const parsed = JSON.parse(readFileSync(this.file, "utf8"));
        if (!parsed || typeof parsed.sessions !== "object" || typeof parsed.parents !== "object") throw new Error("bad shape");
        this.data = parsed;
      }
    } catch (error) {
      this.broken = `state unreadable: ${error?.message ?? error}`;
    }
  }

  persist() {
    if (this.broken) throw new Error(this.broken);
    const keys = Object.keys(this.data.sessions);
    if (keys.length > MAX_SESSIONS) {
      keys.sort((a, b) => (this.data.sessions[a].at ?? 0) - (this.data.sessions[b].at ?? 0));
      for (const k of keys.slice(0, keys.length - MAX_SESSIONS)) delete this.data.sessions[k];
    }
    const tmp = `${this.file}.${process.pid}.tmp`;
    try {
      writeFileSync(tmp, JSON.stringify(this.data), { mode: 0o600 });
      renameSync(tmp, this.file);
      this.unsaved = false;
    } catch (error) {
      // The memory copy is ahead of the disk now; until a save succeeds, every call that records
      // anything tries again and is blocked if it fails (P5.4: an unwritable folder let the second
      // call through on the memory copy alone).
      this.unsaved = true;
      throw error;
    }
  }

  // Taint as recorded: { tainted, source, at } or null for "never touched". Throws if broken.
  taintOf(sessionKey) {
    if (this.broken) return { tainted: true, source: "guard state unreadable" };
    if (!sessionKey) return { tainted: true, source: "no session key" };
    const own = this.data.sessions[sessionKey];
    if (own?.tainted) return own;
    // A clean extension child (markCleanChild) was judged by its parent's state when it was asked;
    // the parent's later marks (its own "worker result" for this very spawn) don't reach back down.
    if (this.data.cleanChildren?.[sessionKey]) return own ?? null;
    // Children inherit; an unknown parent counts as tainted (checked by the caller via isChild).
    let parent = this.data.parents[sessionKey];
    for (let i = 0; parent && i < 10; i++) {
      const p = this.data.sessions[parent];
      if (p?.tainted) return { tainted: true, source: `parent ${parent}: ${p.source}`, at: p.at };
      parent = this.data.parents[parent];
    }
    return this.taintedChildOf(sessionKey) ?? own ?? null;
  }

  // A clean extension child's answer comes back into the chat that asked it, so that chat reads
  // outside text once the child does, and not before (Adam, 2026-11-25: memory cards after a deep
  // job that read nothing outside were noise). Only children asked in the chat's current session
  // count; a mark without a session id counts always.
  taintedChildOf(parentKey) {
    const marks = this.data.cleanChildren;
    if (!marks) return null;
    const cur = this.current.get(parentKey) ?? this.data.sessions[parentKey]?.sessionId;
    for (const [child, m] of Object.entries(marks)) {
      if (m?.parent !== parentKey) continue;
      if (cur !== undefined && m.parentSession !== undefined && m.parentSession !== cur) continue;
      const c = this.data.sessions[child];
      if (c?.tainted) return { tainted: true, source: `worker result: ${String(c.source).slice(0, 80)}`, at: c.at };
    }
    return null;
  }

  // A chat starts a new session on the daily and idle resets (a new sessionId, OpenClaw's
  // session schema) and on /new or /reset (same sessionId, a before_reset event). Either way its
  // context no longer holds the outside text, so its record starts again. Compaction keeps the
  // sessionId, so it never clears anything. A hook without a sessionId changes nothing (stricter).
  enter(sessionKey, sessionId) {
    if (!sessionKey || typeof sessionId !== "string" || sessionId.length === 0) return;
    const rec = this.data.sessions[sessionKey];
    const known = this.current.get(sessionKey) ?? rec?.sessionId;
    this.current.set(sessionKey, sessionId);
    if (known === undefined || known === sessionId) {
      if (rec && rec.sessionId === undefined) { rec.sessionId = sessionId; this.persist(); }
      return;
    }
    this.reset(sessionKey, `new session ${sessionId.slice(0, 8)}`);
  }

  reset(sessionKey) {
    if (!sessionKey) return;
    this.seen.delete(sessionKey);
    this.written.delete(sessionKey);
    this.words.delete(sessionKey);
    this.typed.delete(sessionKey);
    this.acp.delete(sessionKey);
    if (this.data.sessions[sessionKey]) {
      delete this.data.sessions[sessionKey];
      this.persist();
    }
  }

  currentSession(sessionKey) {
    return this.current.get(sessionKey);
  }

  markTainted(sessionKey, source) {
    if (!sessionKey) return;
    const cur = this.data.sessions[sessionKey];
    if (cur?.tainted) { if (this.unsaved) this.persist(); return; }
    this.data.sessions[sessionKey] = { ...(cur ?? {}), tainted: true, source: String(source).slice(0, 120), at: this.now(), sessionId: this.current.get(sessionKey) ?? cur?.sessionId };
    this.persist();
  }

  markReadPrivateRepo(sessionKey, repo) {
    if (!sessionKey) return;
    const cur = this.data.sessions[sessionKey] ?? { tainted: false, at: this.now(), sessionId: this.current.get(sessionKey) };
    cur.readRepos = Array.from(new Set([...(cur.readRepos ?? []), String(repo).slice(0, 100)])).slice(0, 50);
    this.data.sessions[sessionKey] = cur;
    this.persist();
  }

  readRepos(sessionKey) {
    return this.data.sessions[sessionKey]?.readRepos ?? [];
  }

  // The child gets the parent's seen URLs, merged with any it already gathered (its first calls
  // can finish before the spawn's own result arrives).
  linkChild(childKey, parentKey) {
    if (!childKey || !parentKey) return;
    this.data.parents[childKey] = parentKey;
    const seen = this.seen.get(parentKey);
    if (seen) {
      const merged = new Map(seen);
      for (const [u, s] of this.seen.get(childKey) ?? []) if (!merged.has(u)) merged.set(u, s);
      this.seen.set(childKey, merged);
    }
    this.persist();
  }

  // URLs this session gathered from outside readers' results itself, not copied from a parent or
  // typed by Adam. Only these may go up from a consult child to its parent (issue #13).
  ownOutsideSeen(sessionKey) {
    const parent = this.data.parents[sessionKey];
    const inherited = parent ? this.seen.get(parent) : null;
    return [...(this.seen.get(sessionKey) ?? [])].filter(([u, s]) => s === "outside" && !inherited?.has(u)).map(([u]) => u);
  }

  // An extension agent's session (policy.isExtensionAgent) started from Adam's own clean chat by a
  // typed, non-scheduled turn. Anything else, or a child not marked yet, counts as not clean.
  markCleanChild(childKey, parentKey) {
    if (!childKey || !parentKey) return;
    const marks = (this.data.cleanChildren ??= {});
    marks[childKey] = { parent: parentKey, parentSession: this.current.get(parentKey) ?? this.data.sessions[parentKey]?.sessionId, at: this.now() };
    const keys = Object.keys(marks);
    for (const k of keys.slice(0, Math.max(0, keys.length - 1000))) delete marks[k];
    this.persist();
  }

  cleanChild(childKey) {
    return !this.broken && !!childKey && !!this.data.cleanChildren?.[childKey];
  }

  parentOf(childKey) {
    return this.data.parents[childKey] ?? null;
  }

  // source "adam": in Adam's own typed words; "outside": in an outside reader's result.
  addSeen(sessionKey, urls, source = "outside") {
    if (!sessionKey || urls.length === 0) return;
    const map = this.seen.get(sessionKey) ?? new Map();
    for (const u of urls) {
      if (source === "adam") map.set(u, "adam");
      else if (!map.has(u) && map.size < 5000) map.set(u, source);
    }
    this.seen.set(sessionKey, map);
  }

  hasSeen(sessionKey, url) {
    return this.seen.get(sessionKey)?.has(url) === true;
  }

  typedSeen(sessionKey, url) {
    return this.seen.get(sessionKey)?.get(url) === "adam";
  }

  // Address-like words from the arguments of calls made after outside text. Past the cap the
  // session stops gaining seen URLs from results (fail closed) rather than forgetting any.
  addWritten(sessionKey, tokens) {
    if (!sessionKey || tokens.length === 0) return;
    const rec = this.written.get(sessionKey) ?? { tokens: new Set(), full: false };
    for (const t of tokens) {
      if (rec.tokens.has(t)) continue;
      if (rec.tokens.size >= MAX_WRITTEN) { rec.full = true; break; }
      rec.tokens.add(t);
    }
    this.written.set(sessionKey, rec);
  }

  // Did the model write this (any of its cores) in this session or a parent? "full" means unknown.
  wrote(sessionKey, cores) {
    let key = sessionKey;
    for (let i = 0; key && i < 10; i++, key = this.data.parents[key]) {
      const rec = this.written.get(key);
      if (!rec) continue;
      if (rec.full) return true;
      for (const t of rec.tokens) if (cores.some((c) => t.includes(c))) return true;
    }
    return false;
  }

  anySeen(url) {
    for (const set of this.seen.values()) if (set.has(url)) return true;
    return false;
  }

  setWords(sessionKey, text) {
    if (!sessionKey) return;
    this.words.set(sessionKey, { text: String(text ?? "").slice(0, 20000), at: this.now() });
  }

  wordsOf(sessionKey) {
    return this.words.get(sessionKey)?.text ?? "";
  }

  // Kept in memory only: after a Gateway restart the chat's earlier words are gone (stricter).
  addTyped(sessionKey, text) {
    const t = String(text ?? "").trim();
    if (!sessionKey || t.length === 0) return;
    const list = this.typed.get(sessionKey) ?? [];
    list.push(t.slice(0, 4000));
    this.typed.set(sessionKey, list.slice(-30));
  }

  typedOf(sessionKey) {
    return this.typed.get(sessionKey) ?? [];
  }

  // Counts ACP spawns in the last hour, including this one.
  countAcp(sessionKey) {
    const hourAgo = this.now() - 3600_000;
    const list = (this.acp.get(sessionKey) ?? []).filter((t) => t > hourAgo);
    list.push(this.now());
    this.acp.set(sessionKey, list);
    return list.length;
  }

  frozen() {
    try { return existsSync(this.freezeFile); } catch { return true; }
  }

  freeze(by) {
    writeFileSync(this.freezeFile, `frozen ${new Date(this.now()).toISOString()} by ${by}\n`, { mode: 0o600 });
  }

  // Careful mode (docs/plan/13-autonomy.md 6.6): the file's first word is the ISO time it ends.
  // Returns that time while it lasts, else null. A file the guard can't read keeps it on.
  careful() {
    let text;
    try {
      if (!existsSync(this.carefulFile)) return null;
      text = readFileSync(this.carefulFile, "utf8");
    } catch {
      return "Adam turns it off";
    }
    const until = String(text).trim().split(/\s+/)[0];
    const at = Date.parse(until);
    if (Number.isNaN(at)) return "Adam turns it off";
    return at > this.now() ? until : null;
  }

  setCareful(by, hours = 24) {
    const until = new Date(this.now() + hours * 3600_000).toISOString();
    writeFileSync(this.carefulFile, `${until} set ${new Date(this.now()).toISOString()} by ${by}\n`, { mode: 0o600 });
    return until;
  }

  clearCareful() {
    rmSync(this.carefulFile, { force: true });
  }
}
