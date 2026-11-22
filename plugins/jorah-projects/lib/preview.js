// Rendered previews from a project's folder for Adam's chat (issue #16): CAD, simulation and board
// renders a run wrote as PNG or JPEG. main's file tools stay inside its workspace, so the tool
// copies each picked image into <workspace>/media/outbound/previews/<project>/ and returns a
// MEDIA:<path> line for the reply. Only regular files inside the project's own folder (after
// resolving every link), with an image extension, image magic bytes, at most MAX_BYTES each and
// MAX_FILES per call. Nothing is ever executed or decoded beyond the magic bytes.

import { closeSync, copyFileSync, lstatSync, mkdirSync, openSync, readSync, readdirSync, realpathSync, renameSync, statSync, unlinkSync } from "node:fs";
import { basename, extname, isAbsolute, join, relative, sep } from "node:path";

export const MAX_FILES = 4;
export const MAX_BYTES = 10 * 1024 * 1024;
const LIST_MAX = 40;
const EXT = new Set([".png", ".jpg", ".jpeg"]);
const SKIP_DIRS = new Set([".git", "node_modules", ".venv", "venv", "__pycache__", ".cache"]);

export class PreviewError extends Error {}

function magicOk(file, ext) {
  const fd = openSync(file, "r");
  try {
    const b = Buffer.alloc(8);
    const n = readSync(fd, b, 0, 8, 0);
    if (ext === ".png") return n === 8 && b.equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]));
    return n >= 3 && b[0] === 0xff && b[1] === 0xd8 && b[2] === 0xff;
  } finally {
    closeSync(fd);
  }
}

/** A path inside workDir, checked. Returns { real, rel, size }. Throws PreviewError. */
export function checkImage(workDir, path) {
  if (typeof path !== "string" || path.length === 0 || path.length > 300 || path.includes("\0")) throw new PreviewError("give a path inside the project folder, e.g. renders/arm-front.png");
  if (isAbsolute(path) || path.split(/[\\/]/).includes("..")) throw new PreviewError(`${path.slice(0, 80)}: only a path inside the project folder`);
  const ext = extname(path).toLowerCase();
  if (!EXT.has(ext)) throw new PreviewError(`${path.slice(0, 80)}: only PNG or JPEG renders`);
  const root = realpathSync(workDir);
  let real;
  try { real = realpathSync(join(root, path)); } catch { throw new PreviewError(`${path.slice(0, 80)} isn't in the project folder`); }
  if (!real.startsWith(root + sep)) throw new PreviewError(`${path.slice(0, 80)} leads outside the project folder`);
  const rel = relative(root, real);
  if (rel.split(sep).some((p) => p === ".git")) throw new PreviewError(`${path.slice(0, 80)} is inside .git`);
  const st = lstatSync(real);
  if (!st.isFile()) throw new PreviewError(`${path.slice(0, 80)} isn't a regular file`);
  if (st.size === 0 || st.size > MAX_BYTES) throw new PreviewError(`${path.slice(0, 80)} is ${st.size} bytes; previews are 1 byte to ${MAX_BYTES / 1024 / 1024} MB`);
  if (!magicOk(real, ext === ".jpeg" ? ".jpg" : ext)) throw new PreviewError(`${path.slice(0, 80)} isn't really a ${ext.slice(1).toUpperCase()} image`);
  return { real, rel, size: st.size };
}

/** Newest images in the folder (not following links), at most LIST_MAX: { path, bytes, modified }. */
export function listImages(workDir, { depth = 5 } = {}) {
  const root = realpathSync(workDir);
  const out = [];
  const walk = (dir, d) => {
    if (d > depth || out.length > 2000) return;
    let names;
    try { names = readdirSync(dir, { withFileTypes: true }); } catch { return; }
    for (const e of names) {
      if (e.isSymbolicLink()) continue;
      const p = join(dir, e.name);
      if (e.isDirectory()) { if (!SKIP_DIRS.has(e.name)) walk(p, d + 1); continue; }
      if (!e.isFile() || !EXT.has(extname(e.name).toLowerCase())) continue;
      try {
        const st = statSync(p);
        if (st.size > 0 && st.size <= MAX_BYTES) out.push({ path: relative(root, p), bytes: st.size, modified: st.mtime.toISOString() });
      } catch { /* gone */ }
    }
  };
  walk(root, 0);
  return out.sort((a, b) => b.modified.localeCompare(a.modified)).slice(0, LIST_MAX);
}

/** Copy checked images into the outbox; returns the absolute outbox paths. */
export function stage(workDir, paths, outRoot, project) {
  if (!Array.isArray(paths) || paths.length === 0 || paths.length > MAX_FILES) throw new PreviewError(`pick 1 to ${MAX_FILES} images`);
  const checked = paths.map((p) => checkImage(workDir, p));
  const dir = join(outRoot, project);
  mkdirSync(dir, { recursive: true, mode: 0o700 });
  return checked.map((c) => {
    const name = c.rel.replace(/[^A-Za-z0-9._-]+/g, "_").slice(-120);
    const dest = join(dir, name);
    const tmp = `${dest}.${process.pid}.tmp`;
    copyFileSync(c.real, tmp);
    // The copy must still be what was checked (a run could swap the file between check and copy).
    if (statSync(tmp).size !== c.size || !magicOk(tmp, extname(name).toLowerCase() === ".png" ? ".png" : ".jpg")) {
      unlinkSync(tmp);
      throw new PreviewError(`${c.rel} changed while it was copied`);
    }
    renameSync(tmp, dest);
    return { from: c.rel, path: dest, name: basename(dest) };
  });
}
