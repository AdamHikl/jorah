import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jorah_voice.approvals import ApprovalsError, GatewayApprovalsClient, gateway_ws_url


class FakeGatewayWS:
    def __init__(self, *, grant_approvals=True, list_refused=False):
        self.sent = []
        self.incoming = asyncio.Queue()
        self.grant_approvals = grant_approvals
        self.list_refused = list_refused
        self.closed = False
        self.incoming.put_nowait(json.dumps({
            "type": "event",
            "event": "connect.challenge",
            "payload": {"nonce": "n1", "ts": 1737264000000},
        }))

    async def send(self, text):
        frame = json.loads(text)
        self.sent.append(frame)
        if frame.get("method") == "connect":
            scopes = ["operator.read", "operator.approvals"] if self.grant_approvals else ["operator.read"]
            self.incoming.put_nowait(json.dumps({
                "type": "res",
                "id": frame["id"],
                "ok": True,
                "payload": {"type": "hello-ok", "protocol": 4, "auth": {"role": "operator", "scopes": scopes}},
            }))
        elif frame.get("method") == "plugin.approval.list":
            if self.list_refused:
                self.incoming.put_nowait(json.dumps({
                    "type": "res",
                    "id": frame["id"],
                    "ok": False,
                    "error": {"code": "FORBIDDEN", "message": "missing scope: operator.approvals"},
                }))
            else:
                self.incoming.put_nowait(json.dumps({
                    "type": "res",
                    "id": frame["id"],
                    "ok": True,
                    "payload": [{"id": "plugin:1", "request": {"title": "T"}}],
                }))
        elif frame.get("method") == "plugin.approval.resolve":
            self.incoming.put_nowait(json.dumps({
                "type": "res",
                "id": frame["id"],
                "ok": True,
                "payload": {"ok": True},
            }))

    async def recv(self):
        item = await self.incoming.get()
        if item is None:
            raise ConnectionError("closed")
        return item

    async def close(self):
        self.closed = True
        self.incoming.put_nowait(None)


class ApprovalsProtocol(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.token_file = Path(self.tmp.name) / "gateway-token"
        self.token_file.write_text("gateway-secret-token-for-test-only")
        os.chmod(self.token_file, 0o600)

    def tearDown(self):
        self.tmp.cleanup()

    def test_loopback_only_ws_url(self):
        self.assertEqual(gateway_ws_url("http://127.0.0.1:43181/v1/chat/completions"), "ws://127.0.0.1:43181")
        self.assertEqual(gateway_ws_url("http://localhost:43181/"), "ws://localhost:43181")
        with self.assertRaises(ValueError):
            gateway_ws_url("http://100.115.240.14:43181/")

    async def test_handshake_list_resolve_and_events(self):
        ws = FakeGatewayWS()
        requested = []
        resolved = []
        client = GatewayApprovalsClient(
            "http://127.0.0.1:43181/v1/chat/completions",
            self.token_file,
            connect_fn=lambda _url: asyncio.sleep(0, result=ws),
            sleep=lambda _s: asyncio.sleep(0),
        )
        client.set_handlers(on_requested=requested.append, on_resolved=resolved.append)
        client.start()
        for _ in range(20):
            if client.available:
                break
            await asyncio.sleep(0.01)
        self.assertTrue(client.available)

        connect_req = ws.sent[0]
        self.assertEqual(connect_req["method"], "connect")
        params = connect_req["params"]
        self.assertEqual(params["role"], "operator")
        self.assertEqual(params["scopes"], ["operator.admin", "operator.approvals", "operator.read"])
        self.assertIn("plugin-approvals", params["caps"])
        self.assertEqual(params["auth"], {"token": "gateway-secret-token-for-test-only"})

        rows = await client.list()
        self.assertEqual(len(rows), 1)
        await client.resolve("plugin:1", "allow-once")
        with self.assertRaises(ValueError):
            await client.resolve("plugin:1", "allow-always")

        await ws.incoming.put(json.dumps({
            "type": "event",
            "seq": 1,
            "event": "plugin.approval.requested",
            "payload": {"id": "plugin:2"},
        }))
        await ws.incoming.put(json.dumps({
            "type": "event",
            "seq": 2,
            "event": "plugin.approval.resolved",
            "payload": {"id": "plugin:2", "decision": "deny"},
        }))
        for _ in range(20):
            if requested and resolved:
                break
            await asyncio.sleep(0.01)
        self.assertEqual(requested, [{"id": "plugin:2"}])
        self.assertEqual(resolved, [{"id": "plugin:2", "decision": "deny"}])
        await client.close()

    async def test_refusal_marks_refused_and_fires_callback(self):
        ws = FakeGatewayWS(grant_approvals=False)
        refused_calls = []
        client = GatewayApprovalsClient(
            "http://127.0.0.1:43181/v1/chat/completions",
            self.token_file,
            connect_fn=lambda _url: asyncio.sleep(0, result=ws),
            sleep=lambda _s: asyncio.sleep(0),
        )
        client.set_handlers(on_refused=refused_calls.append)
        client.start()
        for _ in range(20):
            if client.refused:
                break
            await asyncio.sleep(0.01)
        self.assertTrue(client.refused)
        self.assertFalse(client.available)
        self.assertEqual(len(refused_calls), 1)
        await client.close()

        ws2 = FakeGatewayWS(grant_approvals=True, list_refused=True)
        client2 = GatewayApprovalsClient(
            "http://127.0.0.1:43181/v1/chat/completions",
            self.token_file,
            connect_fn=lambda _url: asyncio.sleep(0, result=ws2),
            sleep=lambda _s: asyncio.sleep(0),
        )
        client2.start()
        for _ in range(20):
            if client2.available:
                break
            await asyncio.sleep(0.01)
        with self.assertRaises(ApprovalsError) as ctx:
            await client2.list()
        self.assertTrue(ctx.exception.refused)
        self.assertTrue(client2.refused)
        await client2.close()


if __name__ == "__main__":
    unittest.main()
