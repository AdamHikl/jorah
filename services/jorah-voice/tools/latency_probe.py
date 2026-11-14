"""Time Jorah's brain the way a spoken turn reaches it, on a session of its own. Prints timings, never replies.

Run on the PC as jorah, from services/jorah-voice (so `jorah_voice` imports):
  python3 tools/latency_probe.py --think default low off --repeat 3
  python3 tools/latency_probe.py --tool

Each turn goes to the Gateway's Chat Completions endpoint exactly as jorah-voice sends it (same system
note, same headers), but on `agent:main:voice-probe` unless told otherwise, so Adam's conversation is never
touched. It costs one short Haiku turn each, about $0.003. Prints one JSON line per turn: seconds from
sending to the response headers, the first SSE event, the first text, the first whole sentence and the end,
how many characters came back, and the token counts the Gateway reports.
"""

import argparse
import http.client
import json
import re
import time
from urllib.parse import urlsplit

from jorah_voice.brain import GATEWAY_URL, TOKEN_FILE, build_request, read_gateway_token, sse_text

SIMPLE = [
    "What's two plus two?",
    "Give me one tip for sleeping better.",
    "Say good morning to me in one short sentence.",
    "What's the capital of Slovakia?",
    "How many minutes are there in three hours?",
]
# Answered from Jorah's own notes, so it needs a tool but nothing outside the PC.
TOOL = ["What did we decide about the case fans on the PC? Check your notes."]
# Long enough to show whether text streams in as it is written or arrives in one piece.
LONG = ["Explain in five sentences how a heat pump heats a house."]
SENTENCE_END = re.compile(r"[.!?][\"')\]]*\s")


def usage_of(line):
    if not line.startswith("data:"):
        return None
    try:
        event = json.loads(line[5:].strip())
    except ValueError:
        return None
    usage = event.get("usage") if isinstance(event, dict) else None
    return usage if isinstance(usage, dict) else None


def one_turn(url, token, session_key, text, think):
    spoken = text if think == "default" else f"/think:{think} {text}"
    headers, body = build_request(spoken, token, session_key)
    request = json.loads(body)
    request["stream_options"] = {"include_usage": True}
    body = json.dumps(request).encode()
    marks = {}
    reply = ""
    usage = None
    started = time.monotonic()
    connection = http.client.HTTPConnection(url.hostname, url.port or 80, timeout=300)
    try:
        connection.request("POST", url.path, body=body, headers=headers)
        response = connection.getresponse()
        marks["headers"] = time.monotonic() - started
        if response.status != 200:
            return {"think": think, "error": f"HTTP {response.status}"}
        for raw in response:
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            if line.startswith("data:"):
                marks.setdefault("first_event", time.monotonic() - started)
            usage = usage_of(line) or usage
            part = sse_text(line)
            if part:
                marks.setdefault("first_text", time.monotonic() - started)
                reply += part
                if "first_sentence" not in marks and SENTENCE_END.search(reply):
                    marks["first_sentence"] = time.monotonic() - started
    finally:
        connection.close()
    marks["end"] = time.monotonic() - started
    marks.setdefault("first_sentence", marks["end"] if reply else None)
    return {"think": think, **{k: round(v, 2) if v is not None else None for k, v in marks.items()},
            "reply_chars": len(reply), "usage": usage}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=GATEWAY_URL)
    parser.add_argument("--token-file", default=str(TOKEN_FILE))
    parser.add_argument("--session-key", default="agent:main:voice-probe")
    parser.add_argument("--think", nargs="+", default=["default"], help="default, or levels such as low and off")
    parser.add_argument("--repeat", type=int, default=1, help="rounds over the simple questions")
    parser.add_argument("--tool", action="store_true", help="ask the question that needs a tool instead")
    parser.add_argument("--long", action="store_true", help="ask for a five-sentence answer instead")
    parser.add_argument("--pause", type=float, default=1.0, help="seconds between turns")
    args = parser.parse_args()
    if args.session_key == "agent:main:main":
        raise SystemExit("refusing Adam's own session: pick another --session-key")
    token = read_gateway_token(args.token_file)
    url = urlsplit(args.url)
    questions = TOOL if args.tool else LONG if args.long else SIMPLE
    for round_number in range(args.repeat):
        for index, text in enumerate(questions):
            for think in args.think:
                result = one_turn(url, token, args.session_key, text, think)
                kind = "tool" if args.tool else "long" if args.long else "simple"
                print(json.dumps({"round": round_number, "question": index, "kind": kind, **result}), flush=True)
                time.sleep(args.pause)


if __name__ == "__main__":
    main()
