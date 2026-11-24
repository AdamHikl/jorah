// Pictures Adam sent (pasted in the HUD, a Telegram photo) that Jorah decides to keep. OpenClaw
// keeps received attachments in its inbound media store only for a while; picture_save copies the
// ones worth keeping into <workspace>/files/pictures/ under a dated name and adds a line to
// INDEX.md there, so Jorah can find them later. It reads only attachments from the same chat or
// files inside the inbound-media folders (lib/media.js), takes only pictures, never overwrites, and
// writes nowhere else. The folder stays private to the PC: nothing here sends or publishes.

import { appendFileSync, chmodSync, copyFileSync, constants, existsSync, lstatSync, mkdirSync, readdirSync, realpathSync, statSync } from "node:fs";
import { join } from "node:path";

export const PICTURE_EXT = new Set(["jpg", "png", "heic", "webp", "gif"]);
export const MAX_PER_CALL = 20; // the HUD sends at most 20 pictures in one message
export const MAX_FOLDER_FILES = 5000;
export const MAX_FOLDER_BYTES = 2 * 1024 ** 3;
export const MAX_WHY = 200;
// "last" without a recorded attachment: the newest picture in the inbound folders, if it arrived
// in the last half hour, plus any that arrived within 15 seconds of it (one message).
export const RECENT_MS = 30 * 60_000;
export const BURST_MS = 15_000;
export const NAME = /^[a-z0-9][a-z0-9-]{0,59}$/;

export class PictureError extends Error {}

const extOf = (file) => {
  const m = /\.([A-Za-z0-9]{1,5})$/.exec(file);
  if (!m) return null;
  const e = m[1].toLowerCase();
  return e === "jpeg" ? "jpg" : e === "heif" ? "heic" : e;
};

/**
 * The newest pictures in the inbound-media folders: those within BURST_MS of the newest one, when
 * that one is at most RECENT_MS old. Flat folders only, regular files only, at most MAX_PER_CALL.
 * Returns { files: [{ path, ext, bytes }], newestMs } (newestMs null when there is none).
 */
export function newestInbound(roots, nowMs) {
  const found = [];
  for (const root of roots ?? []) {
    let names;
    try { names = readdirSync(root); } catch { continue; }
    for (const name of names) {
      const ext = extOf(name);
      if (!ext || !PICTURE_EXT.has(ext)) continue;
      const path = join(root, name);
      let st;
      try { st = lstatSync(path); } catch { continue; }
      if (!st.isFile() || st.size === 0) continue;
      found.push({ path, ext, bytes: st.size, mtime: st.mtimeMs });
    }
  }
  found.sort((a, b) => b.mtime - a.mtime);
  if (found.length === 0 || nowMs - found[0].mtime > RECENT_MS) return { files: [], newestMs: null };
  const newest = found[0].mtime;
  const files = found.filter((f) => newest - f.mtime <= BURST_MS).slice(0, MAX_PER_CALL)
    .map(({ path, ext, bytes }) => ({ path: realpathSync(path), ext, bytes }));
  return { files, newestMs: newest };
}

function folderUse(dir) {
  let files = 0;
  let bytes = 0;
  for (const name of readdirSync(dir)) {
    try {
      const st = lstatSync(join(dir, name));
      if (st.isFile()) { files += 1; bytes += st.size; }
    } catch { /* gone meanwhile */ }
  }
  return { files, bytes };
}

const oneLine = (s) => s.replace(/[\r\n\t]+/g, " ").replace(/\s{2,}/g, " ").trim();

/**
 * Copy checked sources ({ path, ext, bytes }) into dir as <date>-<name>[-n].<ext>, never
 * overwriting. Appends "- <file>: <why>" to dir/INDEX.md. Returns [{ from, file, path, bytes }].
 */
export function savePictures(sources, { dir, name, date, why }) {
  if (!Array.isArray(sources) || sources.length === 0) throw new PictureError("no picture to save");
  if (sources.length > MAX_PER_CALL) throw new PictureError(`at most ${MAX_PER_CALL} pictures per call`);
  if (typeof name !== "string" || !NAME.test(name)) throw new PictureError("name must be lowercase words joined by dashes, e.g. billa-receipt (at most 60 characters)");
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) throw new PictureError("bad date");
  for (const s of sources) {
    if (!PICTURE_EXT.has(s.ext)) throw new PictureError(`${s.path.split("/").pop()}: not a picture (JPEG, PNG, HEIC, WebP or GIF)`);
  }
  const note = typeof why === "string" ? oneLine(why).slice(0, MAX_WHY) : "";
  mkdirSync(dir, { recursive: true, mode: 0o700 });
  if (lstatSync(dir).isSymbolicLink() || !statSync(dir).isDirectory()) throw new PictureError("the pictures folder isn't a plain folder");
  const use = folderUse(dir);
  const adding = sources.reduce((n, s) => n + s.bytes, 0);
  if (use.files + sources.length > MAX_FOLDER_FILES) throw new PictureError(`the pictures folder already holds ${use.files} files: ask Adam to tidy it`);
  if (use.bytes + adding > MAX_FOLDER_BYTES) throw new PictureError("the pictures folder is over 2 GB: ask Adam to tidy it");
  const out = [];
  sources.forEach((s, i) => {
    const stem = `${date}-${name}${sources.length > 1 ? `-${i + 1}` : ""}`;
    let file = `${stem}.${s.ext}`;
    for (let n = 2; existsSync(join(dir, file)); n += 1) {
      if (n > 99) throw new PictureError(`too many pictures named ${stem}`);
      file = `${stem}-${n}.${s.ext}`;
    }
    const path = join(dir, file);
    copyFileSync(s.path, path, constants.COPYFILE_EXCL);
    chmodSync(path, 0o600);
    out.push({ from: s.path, file, path, bytes: s.bytes });
  });
  const lines = out.map((o) => `- ${o.file}${note ? `: ${note}` : ""}\n`).join("");
  appendFileSync(join(dir, "INDEX.md"), lines, { mode: 0o600 });
  return out;
}
