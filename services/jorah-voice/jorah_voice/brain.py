"""The thinking step: each thing Adam says goes to Jorah's main session through the Gateway.

Jorah keeps the conversation, the memory and the tools, so this sends only the latest words and
streams the reply back. It uses the Gateway's Chat Completions endpoint, which must be switched
on with `gateway.http.endpoints.chatCompletions.enabled`, and the Gateway's own token.
"""

import http.client
import json
import threading
from pathlib import Path
from urllib.parse import urlsplit

GATEWAY_URL = "http://127.0.0.1:43181/v1/chat/completions"
SESSION_KEY = "agent:main:main"
TOKEN_FILE = Path.home() / ".config" / "jorah-voice" / "gateway-token"

VOICE_NOTE = """Adam is talking to you out loud, and your reply is read aloud.
Keep it short enough to say in one breath unless Adam asks for more: one to three sentences.
Use plain sentences with no lists, markdown, links, code or emoji.
Adam's words come from speech recognition, so a strange word was probably misheard. If a reply depends on it, ask."""


class BrainError(RuntimeError):
    pass


def read_gateway_token(path=TOKEN_FILE):
    path = Path(path)
    try:
        if path.stat().st_mode & 0o077:
            raise BrainError(f"{path} must be readable by its owner only")
        token = path.read_text().strip()
    except OSError as error:
        raise BrainError(f"can't read the Gateway token: {error.strerror}") from None
    if not token:
        raise BrainError(f"{path} is empty")
    return token


def build_request(text, token, session_key=SESSION_KEY):
    """Return the headers and body for one spoken turn."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "x-openclaw-session-key": session_key,
    }
    body = {
        "model": "openclaw/main",
        "stream": True,
        "messages": [{"role": "system", "content": VOICE_NOTE}, {"role": "user", "content": text}],
    }
    return headers, json.dumps(body).encode()


def sse_text(line):
    """Return the reply text in one SSE line, None for anything else. Raises on a streamed error."""
    if not line.startswith("data:"):
        return None
    data = line[5:].strip()
    if not data or data == "[DONE]":
        return None
    try:
        event = json.loads(data)
    except ValueError:
        return None
    if "error" in event:
        error = event["error"]
        raise BrainError(error.get("message", "Gateway error") if isinstance(error, dict) else str(error))
    for choice in event.get("choices") or []:
        content = (choice.get("delta") or {}).get("content")
        if isinstance(content, str) and content:
            return content
    return None


class JorahBrain:
    def __init__(self, url=GATEWAY_URL, token_file=TOKEN_FILE, session_key=SESSION_KEY,
                 connect_seconds=5, reply_seconds=300):
        self._url = urlsplit(url)
        self._token_file = token_file
        self._session_key = session_key
        self._connect_seconds = connect_seconds
        self._reply_seconds = reply_seconds
        self._socket = None
        self._lock = threading.Lock()
        self._cancelled = False

    def stream(self, text):
        """Yield Jorah's reply as it arrives. Closing the connection stops the run on the Gateway."""
        headers, body = build_request(text, read_gateway_token(self._token_file), self._session_key)
        connection = http.client.HTTPConnection(self._url.hostname, self._url.port or 80,
                                                timeout=self._connect_seconds)
        self._cancelled = False
        try:
            connection.request("POST", self._url.path, body=body, headers=headers)
            # Kept here because http.client lets go of it once the response says it will close.
            with self._lock:
                self._socket = connection.sock
            connection.sock.settimeout(self._reply_seconds)
            response = connection.getresponse()
            if response.status != 200:
                raise BrainError(f"Gateway answered {response.status}")
            for raw in response:
                if self._cancelled:
                    return
                text_part = sse_text(raw.decode("utf-8", "replace").rstrip("\r\n"))
                if text_part:
                    yield text_part
        except (OSError, http.client.HTTPException) as error:
            if not self._cancelled:
                raise BrainError(f"can't reach the Gateway: {type(error).__name__}") from None
        finally:
            with self._lock:
                self._socket = None
            connection.close()

    def cancel(self):
        with self._lock:
            sock, self._cancelled = self._socket, True
        if sock is not None:
            try:
                sock.shutdown(2)
            except OSError:
                pass
