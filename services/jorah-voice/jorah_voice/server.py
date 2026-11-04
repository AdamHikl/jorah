"""The PC side of talking to Jorah. Listens on loopback only; Tailscale Serve is the way in."""

import argparse
import asyncio
import json
import os
from pathlib import Path

from .core import parse_hello

DEFAULT_PORT = 43210
HELLO_SECONDS = 5


def read_token(path):
    token = Path(path).read_text().strip()
    if len(token) < 32:
        raise SystemExit(f"{path} doesn't hold a token")
    if Path(path).stat().st_mode & 0o077:
        raise SystemExit(f"{path} must be readable by its owner only")
    return token


async def serve(args):
    from websockets.asyncio.server import serve as ws_serve
    from websockets.exceptions import ConnectionClosed

    from . import models
    from .brain import ClaudeBrain
    from .session import VoiceSession
    from .speech import Ears, Listener, Speaker

    token = read_token(args.token_file)
    root = models.ensure()
    print("Loading speech models", flush=True)
    listener = Listener(root, args.provider)
    speaker = Speaker(root, args.provider, voice=args.voice, speed=args.speed)
    one_at_a_time = asyncio.Lock()

    async def handler(ws):
        try:
            hello = parse_hello(await asyncio.wait_for(ws.recv(), HELLO_SECONDS), token)
        except (asyncio.TimeoutError, ConnectionClosed):
            return
        if hello is None:
            print("refused a client: bad hello or token", flush=True)
            await ws.close(4401, "not allowed")
            return
        if one_at_a_time.locked():
            await ws.close(4409, "another session is open")
            return
        async with one_at_a_time:
            session = VoiceSession(
                Ears(root), listener, speaker, ClaudeBrain(args.model),
                send_json=lambda message: ws.send(json.dumps(message)),
                send_audio=ws.send,
                on_close=ws.close,
                barge_in=hello["barge_in"],
                idle_seconds=args.idle,
            )
            await ws.send(json.dumps({"type": "ready", "sample_rate": speaker.sample_rate}))
            watcher = asyncio.create_task(session.watch())
            print("session open", flush=True)
            try:
                async for message in ws:
                    if isinstance(message, bytes):
                        await session.feed(message)
                    elif json.loads(message).get("type") == "interrupt":
                        await session.interrupt()
            except (ConnectionClosed, ValueError):
                pass
            finally:
                session.closed = True
                await session.interrupt(quiet=True)
                watcher.cancel()
                # Timing only. What was said is never logged.
                print(f"session closed: {json.dumps(session.summary())}", flush=True)

    async with ws_serve(handler, "127.0.0.1", args.port, max_size=256 * 1024):
        print(f"Listening on 127.0.0.1:{args.port}", flush=True)
        await asyncio.Future()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--token-file", default=os.path.expanduser("~/.config/jorah-voice/token"))
    parser.add_argument("--provider", default="cpu", help="cpu, or cuda once the GPU spike passes")
    parser.add_argument("--voice", default="michael")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--model", default="claude-haiku-5-5")
    parser.add_argument("--idle", type=int, default=60, help="seconds of quiet before the session closes")
    asyncio.run(serve(parser.parse_args()))


if __name__ == "__main__":
    main()
