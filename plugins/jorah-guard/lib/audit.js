// One line per guard decision, hash-chained so a removed or edited line shows (p5-plan 4.6).
// Arguments are never written, only a hash of them. The off-machine copy waits for the offsite
// backup (D8), so a user who can write this file can still rewrite the whole chain.

import { appendFileSync, existsSync, readFileSync } from "node:fs";
import { createHash } from "node:crypto";

const sha = (s) => createHash("sha256").update(s).digest("hex");

export function argsHash(params) {
  let text;
  try { text = JSON.stringify(params ?? {}); } catch { text = "unserialisable"; }
  return sha(text).slice(0, 16);
}

export class AuditLog {
  constructor(file) {
    this.file = file;
    this.prev = "genesis";
    try {
      if (existsSync(file)) {
        const lines = readFileSync(file, "utf8").trim().split("\n").filter(Boolean);
        const last = lines.at(-1);
        if (last) this.prev = JSON.parse(last).hash ?? "unreadable";
      }
    } catch {
      this.prev = "unreadable";
    }
  }

  write(entry) {
    const body = { t: new Date().toISOString(), ...entry, prev: this.prev };
    const hash = sha(JSON.stringify(body));
    appendFileSync(this.file, JSON.stringify({ ...body, hash }) + "\n", { mode: 0o600 });
    this.prev = hash;
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
