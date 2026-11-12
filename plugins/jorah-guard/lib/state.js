// Session state for the guard (p5-plan 4.1). Taint survives a Gateway restart because it is
// written to disk before the tool it guards runs. If the file can't be read or written, the
// store says "unknown", and the policy treats unknown as tainted. Seen URLs and Adam's latest
// words stay in memory only: after a restart a session has seen nothing, which is stricter.

import { mkdirSync, readFileSync, renameSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";

const MAX_SESSIONS = 2000;

export class GuardState {
  constructor(dir, { now = () => Date.now() } = {}) {
    this.dir = dir;
    this.file = join(dir, "taint.json");
    this.freezeFile = join(dir, "FROZEN");
    this.now = now;
    this.broken = null;
    this.data = { sessions: {}, parents: {} };
    this.seen = new Map(); // sessionKey -> Set(normalised URL)
    this.words = new Map(); // sessionKey -> { text, at }
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
    writeFileSync(tmp, JSON.stringify(this.data), { mode: 0o600 });
    renameSync(tmp, this.file);
  }

  // Taint as recorded: { tainted, source, at } or null for "never touched". Throws if broken.
  taintOf(sessionKey) {
    if (this.broken) return { tainted: true, source: "guard state unreadable" };
    if (!sessionKey) return { tainted: true, source: "no session key" };
    const own = this.data.sessions[sessionKey];
    if (own?.tainted) return own;
    // Children inherit; an unknown parent counts as tainted (checked by the caller via isChild).
    let parent = this.data.parents[sessionKey];
    for (let i = 0; parent && i < 10; i++) {
      const p = this.data.sessions[parent];
      if (p?.tainted) return { tainted: true, source: `parent ${parent}: ${p.source}`, at: p.at };
      parent = this.data.parents[parent];
    }
    return own ?? null;
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
    this.words.delete(sessionKey);
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
    if (cur?.tainted) return;
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

  linkChild(childKey, parentKey) {
    if (!childKey || !parentKey) return;
    this.data.parents[childKey] = parentKey;
    const seen = this.seen.get(parentKey);
    if (seen) this.seen.set(childKey, new Set(seen));
    this.persist();
  }

  parentOf(childKey) {
    return this.data.parents[childKey] ?? null;
  }

  addSeen(sessionKey, urls) {
    if (!sessionKey || urls.length === 0) return;
    const set = this.seen.get(sessionKey) ?? new Set();
    for (const u of urls) if (set.size < 5000) set.add(u);
    this.seen.set(sessionKey, set);
  }

  hasSeen(sessionKey, url) {
    return this.seen.get(sessionKey)?.has(url) === true;
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
}
