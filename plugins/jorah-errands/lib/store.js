// The plugin's own state, on the PC only: one JSON file per concern in a folder of mode 700, files
// mode 600, written atomically (temp file, fsync, rename). The supplies record holds health details
// such as a lens prescription, so it lives here and nowhere else: not in the repo, not in Jorah's
// memory files, not in a log. A file that can't be read is never overwritten: every call that needs
// it fails with "unavailable" and the file stays for Adam to look at. Missing means empty.

import { chmodSync, closeSync, existsSync, fsyncSync, mkdirSync, openSync, readFileSync, renameSync, statSync, unlinkSync, writeSync } from "node:fs";
import { join } from "node:path";

export class StoreError extends Error {}

export class Store {
  constructor(dir) {
    this.dir = dir;
    this.problem = null;
    try {
      mkdirSync(dir, { recursive: true, mode: 0o700 });
      const st = statSync(dir);
      if ((st.mode & 0o077) !== 0) chmodSync(dir, 0o700);
    } catch (error) {
      this.problem = `state folder unusable: ${error?.code ?? error?.message}`;
    }
  }

  path(name) {
    if (!/^[a-z][a-z0-9-]{0,40}$/.test(name)) throw new StoreError("bad store name");
    return join(this.dir, `${name}.json`);
  }

  read(name, empty) {
    if (this.problem) throw new StoreError(this.problem);
    const file = this.path(name);
    if (!existsSync(file)) return structuredClone(empty);
    let parsed;
    try {
      parsed = JSON.parse(readFileSync(file, "utf8"));
    } catch (error) {
      throw new StoreError(`${name}.json unreadable (${error?.code ?? "bad JSON"}); left as it is`);
    }
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed) || parsed.v !== 1) throw new StoreError(`${name}.json has an unknown shape; left as it is`);
    return parsed;
  }

  write(name, data) {
    if (this.problem) throw new StoreError(this.problem);
    const file = this.path(name);
    const tmp = `${file}.${process.pid}.${Date.now()}.tmp`;
    const fd = openSync(tmp, "w", 0o600);
    try {
      writeSync(fd, JSON.stringify({ ...data, v: 1 }));
      fsyncSync(fd);
    } catch (error) {
      closeSync(fd);
      try { unlinkSync(tmp); } catch { /* already gone */ }
      throw error;
    }
    closeSync(fd);
    renameSync(tmp, file);
  }

  /** Read, change and write one file. `fn` returns the value handed back to the caller. */
  update(name, empty, fn) {
    const data = this.read(name, empty);
    const out = fn(data);
    this.write(name, data);
    return out;
  }
}
