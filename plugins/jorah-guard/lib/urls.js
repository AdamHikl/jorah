// URL helpers for the guard's egress rule (p5-plan 4.2): find URLs, normalise them, and refuse
// local or private addresses whatever the session state.

const URL_RE = /\b(?:https?|file|data|javascript|ftp|ws|wss):[^\s"'<>`\\]+/gi;

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

// Canonical form for comparing: lower-case scheme and host, no fragment, no default port,
// no trailing slash on a bare host. Anything unparseable returns null and is never "seen".
export function normalise(raw) {
  try {
    const u = new URL(raw);
    u.hash = "";
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
