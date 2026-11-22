"""Gateway WebSocket approvals client for jorah-voice (protocol v4).

Connects on loopback using the shared Gateway token with role `operator`, scopes
`operator.admin`, `operator.approvals` and `operator.read`, and capability `plugin-approvals`.

Why admin (Adam's yes, 2026-11-22, ADR 0010): OpenClaw 2026.10.9 shows a card raised in a Chat
Completions turn (every spoken turn) only to admin connections, so without it a voice card has no
approval route and is closed at once (measured 13:42:36, "no approval route"). The shared token
already allows admin; this connection only asks for it. It then sees every card on the Gateway, and
`session.py` keeps only cards from its own voice turns.
Only `allow-once` and `deny` are ever sent to `plugin.approval.resolve`.
"""

from abc import ABC, abstractmethod
import asyncio
import json
from urllib.parse import urlsplit
import uuid

from .brain import GATEWAY_URL, TOKEN_FILE, read_gateway_token

ALLOWED_DECISIONS = frozenset(("allow-once", "deny"))
LOOPBACK_HOSTS = frozenset(("127.0.0.1", "localhost", "::1"))


class ApprovalsError(RuntimeError):
    def __init__(self, message, *, refused=False, code=None):
        super().__init__(message)
        self.refused = refused
        self.code = code


def gateway_ws_url(gateway_url=GATEWAY_URL):
    parts = urlsplit(gateway_url)
    host = parts.hostname or ""
    if host not in LOOPBACK_HOSTS:
        raise ValueError(f"approvals client only connects on loopback, got {host!r}")
    scheme = {"http": "ws", "https": "wss", "ws": "ws", "wss": "wss"}.get(parts.scheme)
    if not scheme:
        raise ValueError(f"unsupported Gateway URL scheme: {parts.scheme!r}")
    netloc = f"[{host}]" if ":" in host else host
    if parts.port:
        netloc = f"{netloc}:{parts.port}"
    return f"{scheme}://{netloc}"


class ApprovalsClient(ABC):
    """Minimal approvals interface so VoiceSession can be tested with a fake."""

    @property
    @abstractmethod
    def available(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def refused(self):
        raise NotImplementedError

    @abstractmethod
    def set_handlers(self, *, on_requested=None, on_resolved=None, on_refused=None):
        raise NotImplementedError

    @abstractmethod
    async def list(self):
        raise NotImplementedError

    @abstractmethod
    async def resolve(self, approval_id, decision):
        raise NotImplementedError


def _is_refusal(code, message):
    code_s = str(code or "").upper()
    msg_s = str(message or "").lower()
    if any(tok in code_s for tok in ("FORBIDDEN", "UNAUTHORIZED", "PAIRING", "NOT_PAIRED", "AUTH_", "PERMISSION")):
        return True
    return any(tok in msg_s for tok in ("missing scope", "forbidden", "not paired", "unauthorized", "permission"))


class GatewayApprovalsClient(ApprovalsClient):
    """Async WebSocket client to OpenClaw Gateway on loopback."""

    def __init__(
        self,
        gateway_url=GATEWAY_URL,
        token_file=TOKEN_FILE,
        *,
        connect_fn=None,
        sleep=asyncio.sleep,
        request_timeout=15.0,
        max_backoff=30.0,
    ):
        self._ws_url = gateway_ws_url(gateway_url)
        self._token_file = token_file
        self._connect_fn = connect_fn
        self._sleep = sleep
        self._request_timeout = request_timeout
        self._max_backoff = max_backoff

        self._ws = None
        self._connected = False
        self._refused = False
        self._last_seq = None
        self._pending = {}
        self._on_requested = None
        self._on_resolved = None
        self._on_refused = None
        self._runner = None
        self._stopped = False

    @property
    def available(self):
        return self._connected and not self._refused

    @property
    def refused(self):
        return self._refused

    def set_handlers(self, *, on_requested=None, on_resolved=None, on_refused=None):
        self._on_requested = on_requested
        self._on_resolved = on_resolved
        self._on_refused = on_refused

    def start(self):
        if self._runner is None or self._runner.done():
            self._stopped = False
            self._runner = asyncio.create_task(self._run_loop())

    async def close(self):
        self._stopped = True
        if self._runner and not self._runner.done():
            self._runner.cancel()
            await asyncio.gather(self._runner, return_exceptions=True)
        await self._drop_socket("closed")

    async def _drop_socket(self, reason):
        self._connected = False
        ws, self._ws = self._ws, None
        pending = dict(self._pending)
        self._pending.clear()
        for fut in pending.values():
            if not fut.done():
                fut.set_exception(ApprovalsError(reason))
        if ws is not None:
            try:
                await ws.close()
            except Exception:
                pass

    async def _default_connect(self, url):
        from websockets.asyncio.client import connect as ws_connect
        return await ws_connect(url)

    async def _run_loop(self):
        attempt = 0
        while not self._stopped:
            try:
                await self._connect_once()
                attempt = 0
            except asyncio.CancelledError:
                raise
            except ApprovalsError as err:
                if err.refused:
                    self._refused = True
                    if self._on_refused:
                        await self._dispatch(self._on_refused, str(err))
                    return
            except Exception:
                pass
            finally:
                await self._drop_socket("disconnected")
            if self._stopped:
                return
            delay = min(self._max_backoff, 2**attempt)
            attempt += 1
            await self._sleep(delay)

    async def _connect_once(self):
        token = read_gateway_token(self._token_file)
        connector = self._connect_fn or self._default_connect
        ws = await connector(self._ws_url)
        self._ws = ws
        self._last_seq = None

        # Wait for connect.challenge, then send connect.
        raw = await asyncio.wait_for(ws.recv(), timeout=self._request_timeout)
        frame = json.loads(raw)
        if frame.get("type") != "event" or frame.get("event") != "connect.challenge":
            raise ApprovalsError("expected connect.challenge")

        connect_id = uuid.uuid4().hex
        connect_frame = {
            "type": "req",
            "id": connect_id,
            "method": "connect",
            "params": {
                "minProtocol": 4,
                "maxProtocol": 4,
                "client": {
                    "id": "gateway-client",
                    "displayName": "Jorah Voice",
                    "version": "0.1.0",
                    "platform": "linux",
                    "mode": "backend",
                },
                "role": "operator",
                "scopes": ["operator.admin", "operator.approvals", "operator.read"],
                "caps": ["plugin-approvals"],
                "commands": [],
                "permissions": {},
                "auth": {"token": token},
                "userAgent": "jorah-voice/0.1.0",
            },
        }
        await ws.send(json.dumps(connect_frame))

        hello_raw = await asyncio.wait_for(ws.recv(), timeout=self._request_timeout)
        hello = json.loads(hello_raw)
        if hello.get("type") != "res" or hello.get("id") != connect_id:
            raise ApprovalsError("unexpected connect reply")
        if not hello.get("ok"):
            err = hello.get("error") or {}
            details = err.get("details") or {}
            code = details.get("code") or err.get("code")
            msg = err.get("message") or "connect refused"
            raise ApprovalsError(msg, refused=_is_refusal(code, msg), code=code)

        granted = ((hello.get("payload") or {}).get("auth") or {}).get("scopes") or []
        if "operator.approvals" not in granted:
            raise ApprovalsError("missing scope: operator.approvals", refused=True, code="MISSING_SCOPE")

        self._connected = True
        self._refused = False

        while not self._stopped:
            try:
                raw_msg = await ws.recv()
            except Exception:
                return
            if isinstance(raw_msg, bytes):
                raw_msg = raw_msg.decode("utf-8", "replace")
            try:
                msg = json.loads(raw_msg)
            except ValueError:
                continue
            await self._handle_frame(msg)

    async def _handle_frame(self, msg):
        kind = msg.get("type")
        if kind == "res":
            req_id = msg.get("id")
            fut = self._pending.pop(req_id, None)
            if fut and not fut.done():
                if msg.get("ok"):
                    fut.set_result(msg.get("payload"))
                else:
                    err = msg.get("error") or {}
                    details = err.get("details") or {}
                    code = details.get("code") or err.get("code")
                    message = err.get("message") or "request failed"
                    fut.set_exception(ApprovalsError(message, refused=_is_refusal(code, message), code=code))
            return

        if kind == "event":
            seq = msg.get("seq")
            if isinstance(seq, int):
                if self._last_seq is not None and seq > self._last_seq + 1:
                    # Event gap: drop and reconnect so list() resyncs cleanly.
                    if self._ws is not None:
                        await self._ws.close()
                    return
                self._last_seq = seq
            event_name = msg.get("event")
            payload = msg.get("payload") or {}
            if event_name == "plugin.approval.requested" and self._on_requested:
                await self._dispatch(self._on_requested, payload)
            elif event_name == "plugin.approval.resolved" and self._on_resolved:
                await self._dispatch(self._on_resolved, payload)

    async def _dispatch(self, fn, *args):
        res = fn(*args)
        if asyncio.iscoroutine(res):
            await res

    async def _request(self, method, params=None):
        if not self._connected or self._ws is None:
            raise ApprovalsError("not connected")
        req_id = uuid.uuid4().hex
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        self._pending[req_id] = fut
        try:
            await self._ws.send(json.dumps({
                "type": "req",
                "id": req_id,
                "method": method,
                "params": params or {},
            }))
            return await asyncio.wait_for(fut, timeout=self._request_timeout)
        except ApprovalsError as err:
            if err.refused:
                self._refused = True
                if self._on_refused:
                    await self._dispatch(self._on_refused, str(err))
            raise
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise ApprovalsError(f"{method} timed out") from None

    async def list(self):
        payload = await self._request("plugin.approval.list", {})
        return list(payload) if isinstance(payload, list) else []

    async def resolve(self, approval_id, decision):
        if decision not in ALLOWED_DECISIONS:
            raise ValueError(f"unsupported approval decision: {decision!r}")
        if not isinstance(approval_id, str) or not approval_id:
            raise ValueError("approval_id is required")
        return await self._request("plugin.approval.resolve", {"id": approval_id, "decision": decision})
