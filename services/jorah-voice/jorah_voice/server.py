"""The PC side of talking to Jorah. Listens on loopback only; Tailscale Serve is the way in."""

import argparse
import asyncio
import json
import os
from pathlib import Path

from .core import TurnEnd, parse_hello

DEFAULT_PORT = 43210
HELLO_SECONDS = 5
# Measured on synthetic speech: docs/evidence/voice-endpointing/README.md.
EARLY_PAUSE = 0.3
FINISHED_PAUSE = 0.65
UNFINISHED_PAUSE = 1.2


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
    from .brain import JorahBrain
    from .session import VoiceSession
    from .speech import Ears, Listener, Speaker, warm_up

    token = read_token(args.token_file)
    if not 0 < args.early_pause <= args.finished_pause <= args.unfinished_pause:
        raise SystemExit("need 0 < --early-pause <= --finished-pause <= --unfinished-pause")
    turn_end = TurnEnd(args.finished_pause, args.unfinished_pause)
    root = models.ensure()
    print("Loading speech models", flush=True)
    listener = Listener(root, args.stt_provider)
    speaker = Speaker(root, args.tts_provider, voice=args.voice, speed=args.speed)
    # The GPU's first run of each model is slow while it picks kernels, so do it before anyone talks.
    warm_up(listener, speaker)
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
                Ears(root, pauses=(args.early_pause, args.finished_pause, args.unfinished_pause)), listener, speaker, JorahBrain(args.gateway_url, args.gateway_token_file),
                send_json=lambda message: ws.send(json.dumps(message)),
                send_audio=ws.send,
                on_close=ws.close,
                barge_in=hello["barge_in"],
                idle_seconds=args.idle,
                turn_end=turn_end,
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
    parser.add_argument("--stt-provider", default="cpu", help="where speech recognition runs: cpu or cuda")
    parser.add_argument("--tts-provider", default="cuda", help="where speech is made: cuda, or cpu without the GPU")
    parser.add_argument("--voice", default="michael")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--gateway-url", default="http://127.0.0.1:43181/v1/chat/completions")
    parser.add_argument("--gateway-token-file", default=os.path.expanduser("~/.config/jorah-voice/gateway-token"))
    parser.add_argument("--idle", type=int, default=60, help="seconds of quiet before the session closes")
    parser.add_argument("--early-pause", type=float, default=EARLY_PAUSE,
                        help="seconds of quiet before transcribing starts, so the text is ready when the turn ends")
    parser.add_argument("--finished-pause", type=float, default=FINISHED_PAUSE,
                        help="seconds of quiet that end a turn whose transcript sounds finished")
    parser.add_argument("--unfinished-pause", type=float, default=UNFINISHED_PAUSE,
                        help="seconds of quiet that end any other turn, such as one ending in 'and' or 'the'")
    asyncio.run(serve(parser.parse_args()))


if __name__ == "__main__":
    main()
