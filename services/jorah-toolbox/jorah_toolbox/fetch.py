"""Downloads for the installer: HTTPS only (redirects too), certificate checked, size capped, hashed
while streaming. And the one source check the installer does itself: for a GitHub release asset it
asks GitHub's API when the release was published and what digest GitHub holds for the asset, so the
7-day rule and the hash don't rest on Jorah's word alone.

No cookies, no credentials, a generic user agent. `open_url` is injectable for tests.
"""

import hashlib
import json
import re
import ssl
import urllib.error
import urllib.request
from datetime import datetime
from urllib.parse import quote, unquote, urlsplit

USER_AGENT = "jorah-toolbox/1"
TIMEOUT = 60
CHUNK = 1 << 20
GITHUB_ASSET = re.compile(r"^https://github\.com/([A-Za-z0-9-]{1,39})/([A-Za-z0-9._-]{1,100})/releases/download/([^/?#]{1,100})/([^/?#]{1,200})$")


class FetchError(RuntimeError):
    pass


class _HttpsOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).scheme != "https":
            raise FetchError(f"a redirect left https ({urlsplit(newurl).scheme or 'no scheme'})")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_HttpsOnly, urllib.request.HTTPSHandler(context=ssl.create_default_context()))


def urlopen(request, timeout):
    return _OPENER.open(request, timeout=timeout)


def _request(url, accept=None):
    if urlsplit(url).scheme != "https":
        raise FetchError("only https")
    headers = {"User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    return urllib.request.Request(url, headers=headers)


def download(url, dest, max_bytes, open_url=urlopen):
    """Stream `url` into the file `dest`. Returns (sha256 hex, bytes). Stops past `max_bytes`."""
    digest = hashlib.sha256()
    size = 0
    try:
        with open_url(_request(url), TIMEOUT) as response, open(dest, "xb") as out:
            final = response.geturl() if hasattr(response, "geturl") else url
            if urlsplit(final).scheme != "https":
                raise FetchError("the download didn't stay on https")
            while True:
                chunk = response.read(CHUNK)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise FetchError(f"the download is bigger than the {max_bytes // 1048576} MB the request allows")
                digest.update(chunk)
                out.write(chunk)
    except FetchError:
        raise
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise FetchError(f"download failed: {type(error).__name__}: {str(error)[:160]}") from None
    return digest.hexdigest(), size


def get_json(url, open_url=urlopen, max_bytes=4 << 20):
    try:
        with open_url(_request(url, "application/vnd.github+json"), TIMEOUT) as response:
            data = response.read(max_bytes + 1)
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise FetchError(f"{urlsplit(url).hostname} didn't answer: {type(error).__name__}: {str(error)[:160]}") from None
    if len(data) > max_bytes:
        raise FetchError("the answer is too big")
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise FetchError("the answer isn't JSON") from None


def github_release(url, open_url=urlopen, api="https://api.github.com"):
    """For a GitHub release asset URL: {"published": date, "tag", "asset", "digest": hex or None,
    "draft", "prerelease"}. None if the URL isn't a release asset. Raises FetchError."""
    m = GITHUB_ASSET.match(url)
    if not m:
        return None
    owner, repo, tag, asset = m.group(1), m.group(2), unquote(m.group(3)), unquote(m.group(4))
    info = get_json(f"{api}/repos/{owner}/{repo}/releases/tags/{quote(tag, safe='')}", open_url)
    if not isinstance(info, dict) or not isinstance(info.get("published_at"), str):
        raise FetchError("GitHub gave no publication date for the release")
    try:
        published = datetime.fromisoformat(info["published_at"].replace("Z", "+00:00")).date()
    except ValueError:
        raise FetchError("GitHub's publication date doesn't parse") from None
    found = None
    for item in info.get("assets") or []:
        if isinstance(item, dict) and item.get("name") == asset:
            found = item
            break
    if found is None:
        raise FetchError(f"the release {tag} has no asset named {asset[:80]}")
    digest = found.get("digest")
    hexdigest = digest[7:] if isinstance(digest, str) and re.match(r"^sha256:[0-9a-f]{64}$", digest) else None
    return {"published": published, "tag": tag, "asset": asset, "digest": hexdigest,
            "draft": bool(info.get("draft")), "prerelease": bool(info.get("prerelease"))}
