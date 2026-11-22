"""The PC side of talking to Jorah. Listens on loopback only; Tailscale Serve is the way in."""

import argparse
import asyncio
import json
import os
from pathlib import Path

from . import models
from .core import LastFullMessage, TurnEnd, parse_hello, session_log_label
from .identity import CENTROIDS_FILE, DEFAULT_VOICEPRINT_DIR, THRESHOLDS_FILE, SherpaExtractor, SpeakerCheck
from .passphrase import PhraseStore

DEFAULT_PORT = 43210
HELLO_SECONDS = 5
SETTINGS_IDLE_SECONDS = 30
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


def resolve_voice_confirm(voiceprint_dir, *, voice_confirm_flag=True, expected_sha256=None):
    """Decide whether voice confirmation starts enabled, and why if not."""
    if not voice_confirm_flag:
        return False, "voice confirmation off (--no-voice-confirm); cards require a click"
    vp_dir = Path(voiceprint_dir)
    if not (vp_dir / CENTROIDS_FILE).is_file():
        return False, f"voice confirmation off (no {CENTROIDS_FILE} in {vp_dir}); cards require a click"
    if not (vp_dir / THRESHOLDS_FILE).is_file():
        return False, f"voice confirmation off (no {THRESHOLDS_FILE} in {vp_dir}); cards require a click"
    sha = models.EXPECTED_SHA256 if expected_sha256 is None else expected_sha256
    if sha is None:
        return False, "voice confirmation off (speaker model SHA-256 not pinned); cards require a click"
    return True, None


async def handle_phrase_message(msg, phrase_store, send_json):
    """Handle phrase_status_request, phrase_set, and phrase_clear without ever logging the phrase."""
    kind = msg.get("type")
    if kind == "phrase_status_request":
        await send_json({"type": "phrase_status", **phrase_store.status()})
        return True
    if kind == "phrase_set":
        phrase = msg.get("phrase")
        if not isinstance(phrase, str):
            await send_json({"type": "phrase_error", "reason": "Use at least 3 words or 6 digits."})
            return True
        try:
            status = phrase_store.set(phrase)
        except ValueError as err:
            await send_json({"type": "phrase_error", "reason": str(err)})
            return True
        await send_json({"type": "phrase_status", **status})
        return True
    if kind == "phrase_clear":
        await send_json({"type": "phrase_status", **phrase_store.clear()})
        return True
    return False


async def run_settings_connection(ws, phrase_store, sample_rate, *, idle_seconds=SETTINGS_IDLE_SECONDS):
    """Serve a settings-only WebSocket connection (protocol.md)."""
    async def send_json(message):
        await ws.send(json.dumps(message))

    await send_json({"type": "ready", "sample_rate": sample_rate})
    while True:
        try:
            raw = await asyncio.wait_for(ws.recv(), idle_seconds)
        except asyncio.TimeoutError:
            await ws.close(1000, "settings idle")
            return
        if isinstance(raw, bytes):
            continue
        try:
            msg = json.loads(raw)
        except ValueError:
            continue
        if isinstance(msg, dict):
            await handle_phrase_message(msg, phrase_store, send_json)


async def serve(args):
    from websockets.asyncio.server import serve as ws_serve
    from websockets.exceptions import ConnectionClosed

    from .approvals import GatewayApprovalsClient
    from .brain import JorahBrain
    from .session import VoiceSession
    from .speech import Ears, Listener, Speaker, warm_up

    token = read_token(args.token_file)
    if not 0 < args.early_pause <= args.finished_pause <= args.unfinished_pause:
        raise SystemExit("need 0 < --early-pause <= --finished-pause <= --unfinished-pause")
    turn_end = TurnEnd(args.finished_pause, args.unfinished_pause)

    voiceprint_dir = Path(args.voiceprint_dir)
    want_confirm, off_reason = resolve_voice_confirm(
        voiceprint_dir,
        voice_confirm_flag=args.voice_confirm,
    )
    if want_confirm:
        root = models.ensure()
    else:
        print(off_reason, flush=True)
        root = models.ensure_speech()

    print("Loading speech models", flush=True)
    listener = Listener(root, args.stt_provider)
    speaker = None
    if args.tts_engine == "qwen":
        from .qwen_protocol import QwenSpeaker, wait_for_qwen
        speaker = wait_for_qwen(QwenSpeaker, args.qwen_wait)
        if speaker:
            print("Speaking with Qwen3-TTS (Jorah's voice)", flush=True)
        else:
            print(f"Qwen3-TTS service unavailable after {args.qwen_wait}s, speaking with Kokoro", flush=True)
    if speaker is None:
        speaker = Speaker(root, args.tts_provider, voice=args.voice, speed=args.speed)
    # The GPU's first run of each model is slow while it picks kernels, so do it before anyone talks.
    warm_up(listener, speaker)

    speaker_check = None
    voice_confirm = False
    if want_confirm:
        try:
            extractor = SherpaExtractor(
                root / models.SPEAKER_MODEL,
                provider="cpu",
                expected_sha256=models.EXPECTED_SHA256,
            )
            check = SpeakerCheck(voiceprint_dir, extractor=extractor, model_path=root / models.SPEAKER_MODEL)
            if check.is_ready():
                speaker_check = check
                voice_confirm = True
            else:
                print("voice confirmation off (voiceprint, thresholds, or model hash invalid); cards require a click", flush=True)
        except Exception as err:
            print(f"voice confirmation off (speaker check load failed: {type(err).__name__}); cards require a click", flush=True)

    phrase_store = PhraseStore(voiceprint_dir)
    approvals = GatewayApprovalsClient(args.gateway_url, args.gateway_token_file)
    approvals.start()

    warmer = None
    if args.warm_every > 0:
        from .warm import WARMUP_SESSION, Warmer, gateway_uptime
        warmer = Warmer(lambda: JorahBrain(args.gateway_url, args.gateway_token_file, session_key=WARMUP_SESSION),
                        lambda: gateway_uptime(args.gateway_url), every=args.warm_every,
                        log=lambda line: print(line, flush=True))
        warmer.start()
    one_at_a_time = asyncio.Lock()
    # The last long reply, for "read the whole message" in this or a later session. Memory only.
    last_full = LastFullMessage()

    async def handler(ws):
        try:
            hello = parse_hello(await asyncio.wait_for(ws.recv(), HELLO_SECONDS), token)
        except (asyncio.TimeoutError, ConnectionClosed):
            return
        if hello is None:
            print("refused a client: bad hello or token", flush=True)
            await ws.close(4401, "not allowed")
            return
        if hello.get("purpose") == "settings":
            try:
                await run_settings_connection(ws, phrase_store, speaker.sample_rate)
            except ConnectionClosed:
                pass
            return
        if one_at_a_time.locked():
            await ws.close(4409, "another session is open")
            return
        async with one_at_a_time:
            if warmer:
                # Catches a Gateway that restarted since the last check, while Adam is still talking.
                warmer.poke()

            async def send_json(message):
                await ws.send(json.dumps(message))

            session = VoiceSession(
                Ears(root, pauses=(args.early_pause, args.finished_pause, args.unfinished_pause)), listener, speaker, JorahBrain(args.gateway_url, args.gateway_token_file),
                send_json=send_json,
                send_audio=ws.send,
                on_close=ws.close,
                barge_in=hello["barge_in"],
                idle_seconds=args.idle,
                turn_end=turn_end,
                follow_up=hello["follow_up"],
                input_rate=hello["input_rate"],
                filler_seconds=args.filler,
                client_ends=hello["client_ends"],
                stream_speech=args.stream_speech,
                shows_full=hello["shows_full"],
                full_store=last_full,
                speaker_check=speaker_check,
                phrase_store=phrase_store,
                approvals=approvals,
                voice_confirm=voice_confirm,
                session_key=hello["session_key"],
            )
            await ws.send(json.dumps({"type": "ready", "sample_rate": speaker.sample_rate}))
            watcher = asyncio.create_task(session.watch())
            print(f"session open (session: {session_log_label(hello['session_key'])})", flush=True)
            try:
                async for message in ws:
                    if isinstance(message, bytes):
                        await session.feed(message)
                    else:
                        msg = json.loads(message)
                        if not isinstance(msg, dict):
                            continue
                        kind = msg.get("type")
                        if kind == "interrupt":
                            await session.interrupt()
                        elif kind == "card_decision":
                            await session.handle_card_decision(msg)
                        elif kind == "session":
                            await session.handle_session_message(msg)
                        elif await handle_phrase_message(msg, phrase_store, send_json):
                            session.refresh_pending_phrase_status()
            except (ConnectionClosed, ValueError):
                pass
            finally:
                session.closed = True
                approvals.set_handlers()
                await session._cancel_all_tasks()
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
    parser.add_argument("--tts-engine", default="qwen", choices=["qwen", "kokoro"], help="qwen needs jorah-voice-qwen running; falls back to kokoro")
    parser.add_argument("--qwen-wait", type=int, default=120, help="seconds to wait for the Qwen service at start, which loads after a boot")
    parser.add_argument("--voice", default=models.DEFAULT_VOICE)
    parser.add_argument("--speed", type=float, default=models.DEFAULT_SPEED)
    parser.add_argument("--gateway-url", default="http://127.0.0.1:43181/v1/chat/completions")
    parser.add_argument("--gateway-token-file", default=os.path.expanduser("~/.config/jorah-voice/gateway-token"))
    parser.add_argument("--voiceprint-dir", default=str(DEFAULT_VOICEPRINT_DIR),
                        help="folder holding centroids.json, thresholds.json, and passphrase.json")
    parser.add_argument("--no-voice-confirm", dest="voice_confirm", action="store_false",
                        help="turn off voice confirmation of approval cards; every card needs a click")
    parser.add_argument("--filler", type=float, default=2.5, help="seconds without reply text before saying 'One moment.' once; 0 turns it off")
    parser.add_argument("--warm-every", type=float, default=20,
                        help="seconds between checks for a Gateway restart, each followed by one short warm-up turn "
                             "on its own session (about $0.003); 0 turns it off")
    parser.add_argument("--no-stream-speech", dest="stream_speech", action="store_false",
                        help="make each sentence's audio whole before sending it, instead of sending it as it's made")
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
