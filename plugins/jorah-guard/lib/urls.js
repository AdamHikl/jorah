// URL helpers for the guard's egress rule (p5-plan 4.2): find URLs, normalise them, and refuse
// local or private addresses whatever the session state.

// "…" ends a URL: the guard's own refusals shorten URLs with it, and a shortened URL must never
// come back as a new, seen one.
const URL_RE = /\b(?:https?|file|data|javascript|ftp|ws|wss):[^\s"'<>`\\\u2026]+/gi;

export function findUrls(text) {
  if (typeof text !== "string" || text.length === 0) return [];
  return (text.match(URL_RE) ?? []).map((u) => u.replace(/[),.;:!?\]}>]+$/, ""));
}

// Every string anywhere inside a value, for scanning tool arguments and results.
export function strings(value, out = [], depth = 0) {
  if (depth > 8 || out.length > 5000) return out;
  if (typeof value === "string") out.push(value);
  else if (Array.isArray(value)) for (const v of value) strings(v, out, depth + 1);
  else if (value && typeof value === "object") for (const v of Object.values(value)) strings(v, out, depth + 1);
  return out;
}

export function urlsIn(value) {
  return strings(value).flatMap(findUrls);
}

// Canonical form for comparing: lower-case scheme and host, no default port, no trailing slash
// on a bare host, and no fragment unless keepHash. A fragment never reaches the server in a fetch,
// but a page's own script reads it in the browser, and so does the page Adam opens from a link,
// so the browser and Telegram compare with it. Anything unparseable returns null, never "seen".
export function normalise(raw, { keepHash = false } = {}) {
  try {
    const u = new URL(raw);
    if (!keepHash || u.hash === "#") u.hash = "";
    u.hostname = u.hostname.toLowerCase();
    if ((u.protocol === "https:" && u.port === "443") || (u.protocol === "http:" && u.port === "80")) u.port = "";
    let s = u.toString();
    if (u.pathname === "/" && !u.search) s = s.replace(/\/$/, "");
    return s;
  } catch {
    return null;
  }
}

// Addresses that must never be fetched: Jorah's own loopback services, the LAN, link-local,
// the tailnet, and non-web schemes.
export function forbidden(raw) {
  let u;
  try { u = new URL(raw); } catch { return "not a valid URL"; }
  if (u.protocol !== "http:" && u.protocol !== "https:") return `scheme ${u.protocol} is not allowed`;
  if (u.username || u.password) return "URLs with credentials are not allowed";
  const h = u.hostname.toLowerCase().replace(/^\[|\]$/g, "");
  if (h === "localhost" || h.endsWith(".localhost") || h.endsWith(".local") || h.endsWith(".internal")) return "local host";
  if (h.endsWith(".ts.net")) return "tailnet host";
  if (/^\d+$/.test(h) || /^0x[0-9a-f]+$/i.test(h)) return "numeric host";
  const v4 = h.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (v4) {
    const [a, b] = [Number(v4[1]), Number(v4[2])];
    if (a === 127 || a === 10 || a === 0 || (a === 169 && b === 254) || (a === 172 && b >= 16 && b <= 31) ||
        (a === 192 && b === 168) || (a === 100 && b >= 64 && b <= 127) || a >= 224) return "private or local address";
  }
  if (h.includes(":")) {
    if (h === "::1" || h === "::" || /^f[cd]/.test(h) || /^fe[89ab]/.test(h) || h.startsWith("::ffff:")) return "private or local address";
  }
  return null;
}

// A short list of sites Adam approved: host, or host plus path prefix ("github.com/AdamHikl").
export function onSiteAllowlist(raw, allowlist = []) {
  let u;
  try { u = new URL(raw); } catch { return false; }
  if (u.protocol !== "https:") return false;
  const host = u.hostname.toLowerCase();
  const path = u.pathname;
  return allowlist.some((entry) => {
    const [h, ...rest] = String(entry).toLowerCase().split("/");
    const prefix = rest.length ? `/${rest.join("/")}` : "";
    if (host !== h) return false;
    return prefix === "" || path.toLowerCase() === prefix || path.toLowerCase().startsWith(`${prefix}/`);
  });
}

// Both forms a seen URL is stored under: without the fragment (for fetches), and with it.
export function seenForms(raw) {
  return [...new Set([normalise(raw), normalise(raw, { keepHash: true })].filter(Boolean))];
}

const safeDecode = (s) => { try { return decodeURIComponent(s.replace(/\+/g, " ")); } catch { return s; } };

// A URL without its scheme and trailing slash, lower case, as written and percent-decoded:
// what a page or tool would show if it echoed the URL back.
export function urlCores(url) {
  const c = String(url).toLowerCase().replace(/^[a-z][a-z0-9+.-]*:\/\//, "").replace(/\/$/, "");
  return [...new Set([c, safeDecode(c)])].filter((x) => x.length >= 4);
}

// Address-like words in text the model wrote (tool arguments): anything with a dot between
// letters or digits, lower case, as written and percent-decoded. A result URL contained in one of
// them came from the model, not from the outside, so it never counts as seen (laundering, 2026-11-19).
export function writtenTokens(value) {
  const out = new Set();
  for (const s of strings(value)) {
    for (const v of new Set([s, safeDecode(s)])) {
      for (const t of v.toLowerCase().split(/[\s"'<>`\\]+/)) {
        if (t.length >= 4 && /[a-z0-9-]\.[a-z0-9-]/.test(t)) out.add(t.replace(/[),.;:!?\]}>]+$/, "").slice(0, 4096));
      }
    }
  }
  return [...out];
}

// Link hygiene for chats that have read outside text (research recommendation 7, after
// Anthropic's hosted web_fetch): no long URLs, and nothing that looks like a credential. Returns a
// short reason, or null.
const CREDENTIAL_PARAMS = ["token", "access_token", "refresh_token", "id_token", "auth", "auth_token", "authorization",
  "apikey", "api_key", "api-key", "key", "secret", "client_secret", "password", "passwd", "pwd", "pass", "session",
  "sessionid", "session_id", "sid", "sig", "signature", "credential", "credentials", "jwt", "bearer", "code_verifier",
  "x-amz-credential", "x-amz-signature", "x-amz-security-token", "x-goog-credential", "x-goog-signature"];
const CREDENTIAL_SUFFIX = /[_-](?:token|secret|password|passwd|apikey|api_key|key|signature)$/;
const TOKEN_SHAPE = /(?:^|[^a-z0-9])(?:sk-[a-z0-9_-]{16,}|sk_live_|rk_live_|ghp_|gho_|ghu_|ghs_|ghr_|github_pat_|glpat-|xox[abprs]-|akia[0-9a-z]{16}|aiza[0-9a-z_-]{30,}|eyj[a-z0-9_-]{10,}\.eyj[a-z0-9_-]{10,})/i;

export function linkHygiene(raw, { maxChars = 250, credentialParams = CREDENTIAL_PARAMS } = {}) {
  const text = String(raw);
  if (text.length > maxChars) return `longer than ${maxChars} characters`;
  let u;
  try { u = new URL(text); } catch { return null; }
  if (u.username || u.password) return "it carries a login";
  const names = new Set(credentialParams.map((n) => String(n).toLowerCase()));
  const params = [...u.searchParams.keys()];
  if (u.hash.includes("=")) params.push(...new URLSearchParams(u.hash.slice(1)).keys());
  const bad = params.find((k) => names.has(k.toLowerCase()) || CREDENTIAL_SUFFIX.test(k.toLowerCase()));
  if (bad) return `it has a "${bad.slice(0, 20)}" parameter, which looks like a credential`;
  if (TOKEN_SHAPE.test(safeDecode(text))) return "it carries what looks like a key or token";
  return null;
}

// OpenClaw puts quoted messages, the chat window and other context in front of Adam's typed text.
// Each such block has a header line ending in this marker (OpenClaw 2026.10.9,
// src/auto-reply/reply/inbound-context-marker.ts); the Telegram reply quote has none but is one
// "[Replying to: ...]" line. Those blocks can hold Jorah's own earlier words, so they are cut
// before Adam's text is used. Forging the marker only cuts the forger's own text.
const CTX_MARKER = "\u27E6openclaw:ctx\u27E7";

export function ownTypedText(prompt) {
  const lines = String(prompt ?? "").split("\n");
  const out = [];
  for (let i = 0; i < lines.length; i++) {
    const t = lines[i].trim();
    if (t.length > 14 && t.endsWith(CTX_MARKER)) {
      if (t.startsWith("Context:")) break; // the channel context block runs to the end
      if (lines[i + 1]?.trim() === "```json") {
        i += 2;
        while (i < lines.length && lines[i].trim() !== "```") i++;
      } else {
        while (i + 1 < lines.length && lines[i + 1].trim() !== "") i++;
      }
      continue;
    }
    if (/^\[Replying to: .*\]$/.test(t) || t === "Current message:") continue;
    if (t === "<active_memory_plugin>") {
      while (i < lines.length && lines[i].trim() !== "</active_memory_plugin>") i++;
      continue;
    }
    out.push(lines[i]);
  }
  return out.join("\n").trim();
}
