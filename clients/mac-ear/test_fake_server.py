#!/usr/bin/env python3
"""Checks mac-ear's wire behaviour against a stand-in server, with the mic off. Standard library only."""
import base64
import hashlib
import json
import math
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time

TOKEN = "t" * 40
BINARY = sys.argv[1]
results = {}


def read_exact(conn, count):
    data = b""
    while len(data) < count:
        chunk = conn.recv(count - len(data))
        if not chunk:
            raise EOFError
        data += chunk
    return data


def read_frame(conn):
    head = read_exact(conn, 2)
    opcode, length = head[0] & 15, head[1] & 127
    if length == 126:
        length = struct.unpack(">H", read_exact(conn, 2))[0]
    elif length == 127:
        length = struct.unpack(">Q", read_exact(conn, 8))[0]
    mask = read_exact(conn, 4)
    body = read_exact(conn, length)
    return opcode, bytes(b ^ mask[i % 4] for i, b in enumerate(body))


def send_frame(conn, opcode, body):
    length = len(body)
    if length < 126:
        head = bytes([0x80 | opcode, length])
    else:
        head = bytes([0x80 | opcode, 126]) + struct.pack(">H", length)
    conn.sendall(head + body)


def send_json(conn, message):
    send_frame(conn, 1, json.dumps(message).encode())


def serve(listener):
    conn, _ = listener.accept()
    request = b""
    while b"\r\n\r\n" not in request:
        request += conn.recv(4096)
    key = [l.split(b": ")[1] for l in request.split(b"\r\n") if l.lower().startswith(b"sec-websocket-key")][0]
    accept = base64.b64encode(hashlib.sha1(key + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest())
    conn.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: " + accept + b"\r\n\r\n")
    _, hello = read_frame(conn)
    results["hello"] = json.loads(hello)
    send_json(conn, {"type": "ready", "sample_rate": 24000})
    send_json(conn, {"type": "heard", "text": "hello from the stand-in"})
    send_json(conn, {"type": "reply", "text": "a very quiet tone"})
    tone = b"".join(struct.pack("<h", int(300 * math.sin(i / 20))) for i in range(4800))
    send_frame(conn, 2, tone)
    send_json(conn, {"type": "cut"})
    time.sleep(0.3)  # Enter, once the session is up.
    client.stdin.write("\n")
    client.stdin.flush()
    _, interrupt = read_frame(conn)
    results["interrupt"] = json.loads(interrupt)
    send_json(conn, {"type": "closed", "reason": "test finished", "numbers": {"first_audio": {"median": 0.5, "p90": 0.75, "turns": 2}}})
    conn.close()


listener = socket.socket()
listener.bind(("127.0.0.1", 0))
listener.listen(1)
port = listener.getsockname()[1]

with tempfile.NamedTemporaryFile("w", suffix=".token") as token_file:
    token_file.write(TOKEN)
    token_file.flush()
    client = subprocess.Popen(
        [BINARY, "--url", f"ws://127.0.0.1:{port}", "--no-mic", "--token-file", token_file.name],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    threading.Thread(target=serve, args=(listener,), daemon=True).start()
    client.wait(timeout=20)
    output, errors = client.stdout.read(), client.stderr.read()
checks = {
    "exits cleanly": client.returncode == 0,
    "sends the token": results.get("hello", {}).get("token") == TOKEN,
    "says hello with barge_in false": results.get("hello", {}).get("barge_in") is False,
    "Enter sends interrupt": results.get("interrupt", {}).get("type") == "interrupt",
    "shows what was heard": "You:   hello from the stand-in" in output,
    "shows the reply": "Jorah: a very quiet tone" in output,
    "reports timings": "first_audio: median 0.50, P90 0.75, 2 turns" in output,
    "reports a missing number as no samples": "transcribe: no samples" in output,
    "says why it closed": "MIC CLOSED (test finished)" in output,
}
refused = subprocess.run([BINARY, "--url", "ws://192.168.1.20:43210", "--token-file", "/dev/null"], capture_output=True, text=True, timeout=10)
checks["refuses a LAN address"] = refused.returncode == 1 and "Refusing" in refused.stderr
for name, passed in checks.items():
    print(f"{'ok  ' if passed else 'FAIL'} {name}")
if not all(checks.values()):
    print("exit code", client.returncode)
    print(output, errors)
    sys.exit(1)
