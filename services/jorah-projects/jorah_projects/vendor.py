"""Vendor files for a project (issue #17): datasheets (PDF), 3D models (STEP, STL) and KiCad symbol
and footprint files, which a run can't download from its sandbox.

A run that needs one writes `<state_dir>/vendor/requests/<name>.json`:

    {"v": 1, "url": "https://datasheets.raspberrypi.com/camera/camera-module-3-product-brief.pdf",
     "name": "camera-module-3-brief.pdf", "kind": "pdf", "why": "lens position and board size"}

After the run, the runner (as jorah, outside the sandbox) takes at most MAX_REQUESTS of them. Rules:

- Only projects with web research on (`web: true`): a project without web has no way out, and this
  must not become one.
- https only, port 443, no login in the URL, no credential-like parameters, at most 400 characters.
  The host must resolve only to public addresses, and the connection goes to the address that was
  checked (no second lookup, so DNS rebinding can't reach Jorah's own services). Redirects are
  followed by hand, at most 3, each checked the same way.
- The bytes must be the kind asked for (magic bytes; never HTML), within that kind's size cap.
  Written mode 644 (never executable) under `<state_dir>/vendor/`, never through a link.
- A PDF's text is extracted offline with `pdftotext -layout` when it is installed (a timeout, no
  network, capped output) beside it as `<name>.txt`; otherwise its text is "unknown".
- Each file is recorded in `<state_dir>/vendor/MANIFEST.json` and in the runner's own state with its
  source URL, final URL, date, size and SHA-256, and `provenance: "unverified"`.
- `vendor/.gitignore` keeps the files themselves out of git (vendors' licences rarely allow
  redistribution); the manifest is committed, so anyone can fetch the same files again.

Nothing here is run, unpacked or parsed beyond the magic bytes. Archives (zip) are refused.
"""

import hashlib
import http.client
import ipaddress
import json
import os
import re
import shutil
import socket
import ssl
import subprocess
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit, parse_qsl

from . import fsio

MAX_REQUESTS = 10
MAX_TOTAL = 150 * 1024 * 1024
MAX_URL = 400
MAX_REDIRECTS = 3
TIMEOUT = 60
TEXT_TIMEOUT = 60
TEXT_MAX = 2 * 1024 * 1024
CAPS = {"pdf": 25, "step": 50, "stl": 50, "kicad_sym": 5, "kicad_mod": 2}  # MB
EXTENSIONS = {"pdf": (".pdf",), "step": (".step", ".stp"), "stl": (".stl",), "kicad_sym": (".kicad_sym",), "kicad_mod": (".kicad_mod",)}
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
REQUEST_FILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}\.json$")
CREDENTIAL = re.compile(r"(^|[_-])(token|key|apikey|api_key|secret|password|passwd|pwd|auth|session|sid|sig|signature|credential|jwt)$", re.I)
GITIGNORE = b"# Vendor files stay local: their licences rarely allow redistribution. MANIFEST.json says where each came from.\n*\n!.gitignore\n!MANIFEST.json\n"


class Refused(Exception):
    pass


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def check_url(url):
    """The URL's parts if it may be fetched at all (before DNS). Raises Refused."""
    if not isinstance(url, str) or not url or len(url) > MAX_URL:
        raise Refused(f"the URL must be 1 to {MAX_URL} characters")
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise Refused("only https")
    if parts.username or parts.password or "@" in parts.netloc:
        raise Refused("no login in the URL")
    if parts.port not in (None, 443):
        raise Refused("only the standard https port")
    host = (parts.hostname or "").lower()
    if not host or host == "localhost" or host.endswith((".localhost", ".local", ".internal", ".ts.net", ".lan", ".home")):
        raise Refused("not a public host")
    try:
        ipaddress.ip_address(host)
        raise Refused("a host name, not an address")
    except ValueError:
        pass
    for key, _ in parse_qsl(parts.query, keep_blank_values=True):
        if CREDENTIAL.search(key):
            raise Refused(f"a \"{key[:20]}\" parameter looks like a credential")
    return parts


def public_address(host, resolve=socket.getaddrinfo):
    """One public address for host; refuses if any address it resolves to isn't public."""
    try:
        infos = resolve(host, 443, type=socket.SOCK_STREAM)
    except (socket.gaierror, OSError, UnicodeError):
        raise Refused(f"{host} doesn't resolve") from None
    addresses = []
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        if not ip.is_global or ip.is_multicast:
            raise Refused(f"{host} resolves to a private or local address")
        addresses.append(str(ip))
    if not addresses:
        raise Refused(f"{host} doesn't resolve")
    return addresses[0]


class _PinnedHTTPS(http.client.HTTPSConnection):
    """HTTPS to a checked address, with the host name for SNI and the certificate check."""

    def __init__(self, host, address, **kwargs):
        super().__init__(host, 443, timeout=TIMEOUT, context=ssl.create_default_context(), **kwargs)
        self._address = address

    def connect(self):
        sock = socket.create_connection((self._address, 443), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def https_get(url, cap, resolve=socket.getaddrinfo, connection=_PinnedHTTPS):
    """(final URL, bytes, content type) for url, following up to MAX_REDIRECTS checked redirects."""
    for _ in range(MAX_REDIRECTS + 1):
        parts = check_url(url)
        address = public_address(parts.hostname, resolve)
        conn = connection(parts.hostname, address)
        try:
            path = parts.path or "/"
            conn.request("GET", path + (f"?{parts.query}" if parts.query else ""), headers={"User-Agent": "jorah-projects-vendor/1", "Accept": "*/*"})
            response = conn.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader("Location")
                if not location:
                    raise Refused(f"redirect {response.status} without a location")
                url = urljoin(url, location)
                continue
            if response.status != 200:
                raise Refused(f"the server answered {response.status}")
            length = response.getheader("Content-Length")
            if length and length.isdigit() and int(length) > cap:
                raise Refused(f"{int(length) // (1024 * 1024)} MB is over the {cap // (1024 * 1024)} MB limit")
            data = response.read(cap + 1)
            if len(data) > cap:
                raise Refused(f"over the {cap // (1024 * 1024)} MB limit")
            return url, data, (response.getheader("Content-Type") or "").lower()
        except (OSError, http.client.HTTPException, ssl.SSLError) as error:
            raise Refused(f"couldn't download: {type(error).__name__}") from None
        finally:
            conn.close()
    raise Refused(f"more than {MAX_REDIRECTS} redirects")


def is_kind(kind, data):
    head = data[:64].lstrip(b"\xef\xbb\xbf \t\r\n")
    low = head.lower()
    if low.startswith((b"<!doctype", b"<html", b"<?xml", b"pk\x03\x04")):
        return False
    if kind == "pdf":
        return data.startswith(b"%PDF-")
    if kind == "step":
        return head.startswith(b"ISO-10303-21;")
    if kind == "kicad_sym":
        return head.startswith(b"(kicad_symbol_lib")
    if kind == "kicad_mod":
        return head.startswith((b"(footprint", b"(module"))
    if kind == "stl":
        if len(data) >= 84 and 84 + 50 * int.from_bytes(data[80:84], "little") == len(data):
            return True
        return low.startswith(b"solid") and b"facet" in data[:4096].lower()
    return False


def pdf_text(path, out, which=shutil.which, run=subprocess.run):
    """Write the PDF's text beside it; returns the text file's name or None when it can't."""
    tool = which("pdftotext")
    if not tool:
        return None
    try:
        done = run([tool, "-layout", "-enc", "UTF-8", "-q", str(path), "-"], capture_output=True, timeout=TEXT_TIMEOUT,
                   env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}, stdin=subprocess.DEVNULL, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if done.returncode != 0:
        return None
    fsio.write_bytes(out[0], out[1], done.stdout[:TEXT_MAX], mode=0o644)
    return os.path.basename(out[1])


def read_request(raw):
    """The checked request (url, name, kind, why). Raises Refused."""
    try:
        req = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise Refused("not JSON") from None
    if not isinstance(req, dict) or req.get("v") != 1:
        raise Refused("needs \"v\": 1")
    extra = set(req) - {"v", "url", "name", "kind", "why"}
    if extra:
        raise Refused(f"unknown fields: {', '.join(sorted(extra))[:80]}")
    kind, name = req.get("kind"), req.get("name")
    if kind not in CAPS:
        raise Refused(f"kind must be one of {', '.join(CAPS)}")
    if not isinstance(name, str) or not NAME.match(name) or not name.lower().endswith(EXTENSIONS[kind]) or name.lower().endswith(".txt") or name == "MANIFEST.json":
        raise Refused(f"name must be a plain file name ending in {' or '.join(EXTENSIONS[kind])}")
    why = req.get("why")
    if not isinstance(why, str) or not 3 <= len(why) <= 300:
        raise Refused("why must say in a sentence what the file is for")
    check_url(req.get("url"))
    return {"url": req["url"], "name": name, "kind": kind, "why": why}


def collect(project, repo_root, own_state, get=https_get, text=pdf_text, now=_now):
    """Take the run's vendor requests. Returns {fetched, refused} for the run record and the outbox."""
    out = {"fetched": [], "refused": []}
    base = f"{project.state_dir}/vendor"
    try:
        names = sorted(os.listdir(fsio.safe_path(repo_root, f"{base}/requests", must_exist=True)))
    except (FileNotFoundError, NotADirectoryError):
        return out
    except fsio.Unsafe as error:
        return {"fetched": [], "refused": [{"file": "requests", "why": str(error)[:160]}]}
    requests = [n for n in names if n.endswith(".json")]
    if not requests:
        return out
    if not project.web:
        for n in requests[:MAX_REQUESTS]:
            out["refused"].append({"file": n[:80], "why": "this project has no web research, so nothing is downloaded for it (project_set_capabilities)"})
        return out
    manifest = _read_manifest(repo_root, base)
    total = 0
    for n in requests[:MAX_REQUESTS]:
        rel = f"{base}/requests/{n}"
        try:
            if not REQUEST_FILE.match(n):
                raise Refused("request file names are plain names ending in .json")
            raw = fsio.read_bytes(repo_root, rel)
            if raw is None:
                continue
            req = read_request(raw)
            cap = CAPS[req["kind"]] * 1024 * 1024
            if MAX_TOTAL - total <= 0:
                raise Refused(f"this run's downloads reached {MAX_TOTAL // (1024 * 1024)} MB; it stays for the next run")
            final, data, ctype = get(req["url"], min(cap, MAX_TOTAL - total))
            if "text/html" in ctype or not is_kind(req["kind"], data):
                raise Refused(f"the download isn't a {req['kind']} file")
            total += len(data)
            sha = hashlib.sha256(data).hexdigest()
            old = manifest.get(req["name"])
            if old and old.get("sha256") != sha and old.get("url") != req["url"]:
                raise Refused(f"vendor/{req['name']} already holds another file; pick another name")
            fsio.write_bytes(repo_root, f"{base}/.gitignore", GITIGNORE, mode=0o644)
            fsio.write_bytes(repo_root, f"{base}/{req['name']}", data, mode=0o644)
            txt = None
            if req["kind"] == "pdf":
                txt = text(fsio.safe_path(repo_root, f"{base}/{req['name']}"), (repo_root, f"{base}/{req['name']}.txt"))
            entry = {"url": req["url"], "finalUrl": final, "kind": req["kind"], "why": req["why"], "fetchedAt": now(),
                     "bytes": len(data), "sha256": sha, "provenance": "unverified", "text": txt if txt else ("unknown" if req["kind"] == "pdf" else None)}
            manifest[req["name"]] = entry
            out["fetched"].append({"name": req["name"], **entry})
            fsio.remove(repo_root, rel)
        except Refused as why:
            out["refused"].append({"file": n[:80], "why": str(why)[:200]})
            _move_bad(repo_root, base, n, str(why))
        except (OSError, fsio.Unsafe) as error:
            out["refused"].append({"file": n[:80], "why": f"couldn't write: {str(error)[:160]}"})
    for n in requests[MAX_REQUESTS:]:
        out["refused"].append({"file": n[:80], "why": f"only {MAX_REQUESTS} downloads per run; it stays for the next run"})
    if out["fetched"]:
        body = json.dumps(manifest, indent=2, sort_keys=True).encode() + b"\n"
        fsio.write_bytes(repo_root, f"{base}/MANIFEST.json", body, mode=0o644)
        fsio.write_private_json(own_state / "vendor.json", manifest)
    return out


def _read_manifest(repo_root, base):
    try:
        raw = fsio.read_bytes(repo_root, f"{base}/MANIFEST.json")
        value = json.loads(raw.decode("utf-8")) if raw else {}
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, UnicodeDecodeError, fsio.Unsafe):
        return {}


def _move_bad(repo_root, base, name, why):
    """A refused request moves to requests/bad/ with the reason beside it, so the next run can fix it."""
    try:
        raw = fsio.read_bytes(repo_root, f"{base}/requests/{name}")
        if raw is None or not REQUEST_FILE.match(name):
            return
        fsio.write_bytes(repo_root, f"{base}/requests/bad/{name}", raw, mode=0o644)
        fsio.write_bytes(repo_root, f"{base}/requests/bad/{name}.why.txt", why.encode()[:400] + b"\n", mode=0o644)
        fsio.remove(repo_root, f"{base}/requests/{name}")
    except (OSError, fsio.Unsafe):
        pass
