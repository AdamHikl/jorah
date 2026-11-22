// One line per guard decision, hash-chained so a removed or edited line shows (p5-plan 4.6).
// Arguments are never written, only a hash of them. The off-machine copy waits for the offsite
// backup (D8), so a user who can write this file can still rewrite the whole chain.

// Two processes may load the guard (the Gateway and a command-line turn): each append takes a lock
// and re-reads the last line's hash first, so a second writer extends the chain instead of forking
// it (P5.5 review, 2026-11-20, fix 2). If the lock can't be had, the line is still written, chained
// to the last line read, and the fork shows in guard-report.py.

import { appendFileSync, closeSync, existsSync, fstatSync, mkdirSync, openSync, readSync, rmdirSync, statSync } from "node:fs";
import { createHash } from "node:crypto";

const LOCK_TRIES = 200;
const LOCK_STALE_MS = 5000;
const TAIL = 65536;
const pause = (ms) => Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);

function lastHash(file) {
  if (!existsSync(file)) return "genesis";
  const fd = openSync(file, "r");
  try {
    const size = fstatSync(fd).size;
    if (size === 0) return "genesis";
    const n = Math.min(size, TAIL);
    const buf = Buffer.alloc(n);
    readSync(fd, buf, 0, n, size - n);
    const lines = buf.toString("utf8").split("\n").filter(Boolean);
    const last = lines.at(-1);
    return last ? JSON.parse(last).hash ?? "unreadable" : "genesis";
  } catch {
    return "unreadable";
  } finally {
    closeSync(fd);
  }
}

function withLock(lockDir, fn) {
  let held = false;
  for (let i = 0; i < LOCK_TRIES && !held; i++) {
    try {
      mkdirSync(lockDir, { mode: 0o700 });
      held = true;
    } catch (e) {
      if (e?.code !== "EEXIST") break;
      try { if (Date.now() - statSync(lockDir).mtimeMs > LOCK_STALE_MS) rmdirSync(lockDir); } catch { /* gone */ }
      pause(5);
    }
  }
  try {
    return fn();
  } finally {
    if (held) try { rmdirSync(lockDir); } catch { /* gone */ }
  }
}

const sha = (s) => createHash("sha256").update(s).digest("hex");

export function argsHash(params) {
  let text;
  try { text = JSON.stringify(params ?? {}); } catch { text = "unserialisable"; }
  return sha(text).slice(0, 16);
}

export class AuditLog {
  constructor(file) {
    this.file = file;
    this.lock = `${file}.lock`;
    this.prev = lastHash(file);
  }

  write(entry) {
    withLock(this.lock, () => {
      this.prev = lastHash(this.file);
      const body = { t: new Date().toISOString(), ...entry, prev: this.prev };
      const hash = sha(JSON.stringify(body));
      appendFileSync(this.file, JSON.stringify({ ...body, hash }) + "\n", { mode: 0o600 });
      this.prev = hash;
    });
  }
}

// Recompute the chain; returns the first broken line number (1-based) or 0 if intact.
export function verifyChain(text) {
  let prev = "genesis";
  const lines = text.trim().split("\n").filter(Boolean);
  for (let i = 0; i < lines.length; i++) {
    let row;
    try { row = JSON.parse(lines[i]); } catch { return i + 1; }
    const { hash, ...body } = row;
    if (body.prev !== prev || sha(JSON.stringify(body)) !== hash) return i + 1;
    prev = hash;
  }
  return 0;
}
