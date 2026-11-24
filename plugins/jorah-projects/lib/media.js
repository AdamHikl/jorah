// Files Adam sends back for a task (photos from Telegram). They end up in the project's repo
// (field-data/) and so on GitHub, so this is the one place a wrong path could leak a file: only
// attachments OpenClaw itself received in the same chat (seen by the message_received hook), or a
// file under the configured inbound-media folders, are taken; never any other path. Each must be
// a regular file with an allowed type, at most 25 MB, at most 10 per result.

import { lstatSync, realpathSync, statSync } from "node:fs";
import { extname, isAbsolute, join, sep } from "node:path";

export const MAX_FILES = 10;
export const MAX_BYTES = 25 * 1024 * 1024;
const KEEP_MS = 24 * 3600 * 1000;
const PER_CHAT = 20;

const TYPES = {
  "image/jpeg": "jpg", "image/png": "png", "image/heic": "heic", "image/heif": "heic", "image/webp": "webp", "image/gif": "gif",
  "application/pdf": "pdf", "text/plain": "txt", "text/csv": "csv", "application/json": "json", "text/markdown": "md",
  "video/mp4": "mp4", "video/quicktime": "mov", "audio/mp4": "m4a", "audio/x-m4a": "m4a", "audio/ogg": "ogg", "audio/wav": "wav", "audio/x-wav": "wav",
};
// The runner's list (it files them into field-data/); jpeg and oga are written as jpg and ogg.
export const EXTENSIONS = new Set(["jpg", "jpeg", "png", "heic", "webp", "gif", "pdf", "txt", "csv", "json", "md", "mp4", "mov", "m4a", "wav", "ogg", "oga"]);

export class MediaError extends Error {}

/** Attachments seen per chat, newest last, kept 24 hours in memory (a restart forgets them). */
export class MediaTracker {
  constructor(now = () => Date.now()) {
    this.now = now;
    this.byChat = new Map(); // sessionKey -> [{ at, messageId, files: [{ path, contentType }] }]
  }

  record(sessionKey, media, messageId) {
    if (!sessionKey || !Array.isArray(media)) return;
    const files = media.filter((m) => m && typeof m.path === "string" && m.path.length > 0 && m.path.length < 1024)
      .map((m) => ({ path: m.path, contentType: typeof m.contentType === "string" ? m.contentType.toLowerCase().split(";")[0].trim() : null, workspaceDir: typeof m.workspaceDir === "string" ? m.workspaceDir : null }));
    if (files.length === 0) return;
    const list = (this.byChat.get(sessionKey) ?? []).filter((e) => this.now() - e.at < KEEP_MS);
    list.push({ at: this.now(), messageId: messageId ?? null, files });
    this.byChat.set(sessionKey, list.slice(-PER_CHAT));
    if (this.byChat.size > 100) this.byChat.delete(this.byChat.keys().next().value);
  }

  recent(sessionKey) {
    return (this.byChat.get(sessionKey) ?? []).filter((e) => this.now() - e.at < KEEP_MS);
  }

  /** The files of the newest message with attachments in this chat. */
  last(sessionKey) {
    const r = this.recent(sessionKey);
    return r.length ? r[r.length - 1].files : [];
  }

  /** The recorded attachment for this path in this chat, if any. */
  find(sessionKey, path) {
    for (const e of this.recent(sessionKey).reverse()) {
      for (const f of e.files) {
        if (f.path === path) return f;
        // A sandbox-relative reference (media/inbound/x.jpg) against the attachment's workspace.
        if (!isAbsolute(path) && f.workspaceDir && join(f.workspaceDir, path) === f.path) return f;
        if (!isAbsolute(path) && f.path.endsWith(`${sep}${path}`)) return f;
      }
    }
    return null;
  }
}

const inside = (p, root) => p === root || p.startsWith(root.endsWith(sep) ? root : `${root}${sep}`);

function realRoots(roots) {
  const out = [];
  for (const r of roots ?? []) {
    try { out.push(realpathSync(r)); } catch { /* a root that doesn't exist allows nothing */ }
  }
  return out;
}

function typeOf(path, contentType) {
  const fromType = contentType ? TYPES[contentType] : null;
  let ext = extname(path).slice(1).toLowerCase();
  if (ext === "jpeg") ext = "jpg";
  if (ext === "oga") ext = "ogg";
  if (EXTENSIONS.has(ext)) return ext;
  return fromType;
}

/**
 * Turn the tool's `files` into checked sources. Each entry is "last" (every attachment of the
 * newest message with attachments in this chat) or a path OpenClaw gave for an attachment.
 * Returns [{ path (real), ext, bytes }]; throws MediaError saying which entry was refused and why.
 */
export function resolveFiles(files, { sessionKey, tracker, roots, workspace, max = MAX_FILES }) {
  if (files === undefined || files === null) return [];
  if (!Array.isArray(files)) throw new MediaError("files must be a list");
  const wanted = [];
  for (const f of files) {
    if (typeof f !== "string" || f.trim() === "") throw new MediaError("each file must be a path or \"last\"");
    if (f.trim().toLowerCase() === "last") {
      const last = sessionKey ? tracker.last(sessionKey) : [];
      if (last.length === 0) throw new MediaError("there's no recent attachment in this chat: ask Adam to send the photo again");
      wanted.push(...last.map((x) => ({ given: x.path, rec: x })));
    } else {
      const p = f.trim();
      wanted.push({ given: p, rec: sessionKey ? tracker.find(sessionKey, p) : null });
    }
  }
  if (wanted.length > max) throw new MediaError(`at most ${max} files per call`);
  const allowed = realRoots(roots);
  const seen = new Set();
  const out = [];
  for (const w of wanted) {
    const candidate = w.rec?.path ?? (isAbsolute(w.given) ? w.given : workspace ? join(workspace, w.given) : null);
    if (!candidate) throw new MediaError(`${w.given}: not an attachment from this chat`);
    let real;
    try {
      real = realpathSync(candidate);
    } catch {
      throw new MediaError(`${w.given}: the file isn't there (attachments are kept only for a while: ask Adam to send it again)`);
    }
    if (!w.rec && !allowed.some((r) => inside(real, r))) throw new MediaError(`${w.given}: not an attachment from this chat`);
    const st = statSync(real);
    if (!st.isFile() || lstatSync(real).isSymbolicLink()) throw new MediaError(`${w.given}: not a regular file`);
    if (st.size === 0) throw new MediaError(`${w.given}: the file is empty`);
    if (st.size > MAX_BYTES) throw new MediaError(`${w.given}: over 25 MB`);
    const ext = typeOf(real, w.rec?.contentType ?? null);
    if (!ext) throw new MediaError(`${w.given}: not a photo, video, audio, PDF or text file`);
    if (seen.has(real)) continue;
    seen.add(real);
    out.push({ path: real, ext, bytes: st.size });
  }
  return out;
}
