// On-disk cache for GitHub release API responses, keyed by URL with ETag + body + fetchedAt.
// Reduces unauthenticated API calls against GitHub's 60/hour per-IP limit: fresh entries within
// the TTL avoid a request altogether, older entries send If-None-Match (304s don't count against
// the limit), and rate-limited requests (403/429) can fall back to a cached copy under 7 days old.

import { existsSync, lstatSync, mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { writeAtomic } from "./registry.js";

export const CACHE_FILE = "github-cache.json";
export const DEFAULT_TTL_MS = 6 * 60 * 60 * 1000;
export const MAX_STALE_MS = 7 * 24 * 60 * 60 * 1000;
export const MAX_ENTRIES = 64;
const MAX_CACHE_BYTES = 8 << 20;

const isObj = (v) => v !== null && typeof v === "object" && !Array.isArray(v);
const cleanEtag = (v) => (typeof v === "string" && v.length > 0 && v.length <= 512 && !/[\r\n]/.test(v) ? v : null);

function validEntry(entry) {
  if (!isObj(entry)) return null;
  if (typeof entry.fetchedAt !== "string" || Number.isNaN(Date.parse(entry.fetchedAt))) return null;
  if (entry.body === undefined) return null;
  return { etag: cleanEtag(entry.etag), body: entry.body, fetchedAt: entry.fetchedAt };
}

function readEntries(file) {
  if (!existsSync(file)) return {};
  try {
    const st = lstatSync(file);
    if (!st.isFile() || st.size > MAX_CACHE_BYTES) return {};
    const parsed = JSON.parse(readFileSync(file, "utf8"));
    if (!isObj(parsed) || parsed.v !== 1 || !isObj(parsed.entries)) return {};
    const out = {};
    for (const [url, raw] of Object.entries(parsed.entries)) {
      if (typeof url !== "string" || !url) continue;
      const entry = validEntry(raw);
      if (entry) out[url] = entry;
    }
    return out;
  } catch {
    return {};
  }
}

function evictOldest(entries, maxEntries) {
  const keys = Object.keys(entries);
  if (keys.length <= maxEntries) return entries;
  keys.sort((a, b) => Date.parse(entries[b].fetchedAt) - Date.parse(entries[a].fetchedAt));
  const kept = {};
  for (const k of keys.slice(0, maxEntries)) kept[k] = entries[k];
  return kept;
}

/** Open or create a handle for the GitHub release response cache in `stateDir`. */
export function ghCache(stateDir, { fileName = CACHE_FILE, ttlMs = DEFAULT_TTL_MS, maxStaleMs = MAX_STALE_MS, maxEntries = MAX_ENTRIES } = {}) {
  if (!stateDir) return null;
  const file = join(stateDir, fileName);
  const ageMs = (entry, now = new Date()) => {
    const fetched = Date.parse(entry?.fetchedAt);
    const nowMs = now instanceof Date ? now.getTime() : Number(now);
    if (!Number.isFinite(fetched) || !Number.isFinite(nowMs)) return NaN;
    return nowMs - fetched;
  };
  return {
    file,
    get(url) {
      return readEntries(file)[url] ?? null;
    },
    set(url, { etag = null, body, fetchedAt }) {
      const entry = validEntry({ etag, body, fetchedAt });
      if (!entry) return;
      const entries = readEntries(file);
      entries[url] = entry;
      const capped = evictOldest(entries, maxEntries);
      mkdirSync(stateDir, { recursive: true, mode: 0o700 });
      writeAtomic(file, `${JSON.stringify({ v: 1, entries: capped }, null, 2)}\n`);
    },
    isFresh(entry, now = new Date()) {
      const age = ageMs(entry, now);
      return Number.isFinite(age) && age >= 0 && age < ttlMs;
    },
    isUsableStale(entry, now = new Date()) {
      const age = ageMs(entry, now);
      return Number.isFinite(age) && age >= 0 && age < maxStaleMs;
    },
  };
}
