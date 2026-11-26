#!/usr/bin/env python3
"""Drives the Jorah HUD from a command line while Adam has drive mode on (docs/adr/0012).

Adam switches it on with the ⌨ CLAUDE CODE button in the HUD's top bar. Until Adam switches it
off, this talks to the HUD's private socket and can do only what the HUD lets it:

    python3 -I scripts/mac/jorah_hud_drive.py status
    python3 -I scripts/mac/jorah_hud_drive.py send "/jorah-status"        # waits for Jorah's answer
    python3 -I scripts/mac/jorah_hud_drive.py read -n 8
    python3 -I scripts/mac/jorah_hud_drive.py cards
    python3 -I scripts/mac/jorah_hud_drive.py deny plugin:abc123
    python3 -I scripts/mac/jorah_hud_drive.py wait --timeout 60

There is no command to allow a card, pair, pause or resume the PC, switch the brain or model, or
open another conversation, and the HUD refuses them if asked. Only Adam allows, in the HUD.

Exit codes: 0 done, 1 refused or failed, 2 timed out, 3 a card is waiting (only Adam can allow it).
JORAH_HUD_PROFILE picks the same test profile the HUD uses.
"""

import argparse
import json
import os
import socket
import sys
from pathlib import Path

DONE, FAILED, TIMEOUT, CARD = 0, 1, 2, 3
MAX_TEXT = 4000
OFF_HINT = ("The HUD's drive socket isn't there: drive mode is off. Adam switches it on with the "
            "⌨ CLAUDE CODE button in the HUD's top bar.")


def profile_name(environ=os.environ):
    """The HUD's own rule: 1-20 letters, digits or '-', otherwise the everyday profile."""
    raw = environ.get("JORAH_HUD_PROFILE", "")
    if raw and len(raw) <= 20 and all(c.isascii() and (c.isalnum() or c == "-") for c in raw):
        return raw
    return None


def socket_path(environ=os.environ, home=None):
    name = profile_name(environ)
    folder = "JorahHUD-" + name if name else "JorahHUD"
    base = Path(home) if home else Path.home()
    return str(base / "Library" / "Application Support" / folder / "drive.sock")


class DriveError(Exception):
    pass


def call(path, request, timeout):
    """One request, one answer: a JSON line each way."""
    data = json.dumps(request, ensure_ascii=False).encode() + b"\n"
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(timeout)
            conn.connect(path)
            conn.sendall(data)
            chunks = []
            while True:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
                if chunk.endswith(b"\n"):
                    break
    except (FileNotFoundError, ConnectionRefusedError):
        raise DriveError(OFF_HINT) from None
    except socket.timeout:
        raise DriveError("The HUD didn't answer in time.") from None
    except OSError as error:
        raise DriveError(f"Couldn't reach the HUD: {error.strerror or error}") from None
    try:
        reply = json.loads(b"".join(chunks).decode())
    except ValueError:
        raise DriveError("The HUD's answer wasn't JSON (it may have quit mid-answer).") from None
    if not isinstance(reply, dict):
        raise DriveError("The HUD's answer wasn't a JSON object.")
    return reply


def same_text(line, sent):
    a, b = (line or "").strip(), (sent or "").strip()
    return bool(b) and (a == b or a.endswith(b))


def after_sent(lines, sent):
    """The lines after the last one Adam's side sent with this text."""
    for index in range(len(lines) - 1, -1, -1):
        if lines[index].get("role") == "user" and same_text(lines[index].get("text"), sent):
            return lines[index + 1:]
    return []


def clock(iso):
    return iso[11:16] if isinstance(iso, str) and len(iso) >= 16 else "--:--"


def format_line(line):
    who = {"user": "ADAM", "assistant": "JORAH", "notice": "NOTE"}.get(line.get("role"), "?")
    if line.get("viaDrive"):
        who += " (typed by Claude Code)"
    marks = " (still writing)" if line.get("streaming") else ""
    pictures = line.get("pictures") or 0
    text = line.get("text") or ""
    if pictures:
        text = f"[{pictures} picture{'s' if pictures != 1 else ''}] " + text
    return f"{who} · {clock(line.get('at'))}{marks}\n{text}"


def format_card(card):
    out = [f"CARD {card.get('id')}: {card.get('title')}"]
    if card.get("description"):
        out.append(f"  {card['description']}")
    for field in card.get("fields") or []:
        out.append(f"  {field.get('name')}: {field.get('value')}")
    left = card.get("secondsLeft")
    out.append(f"  decisions: {', '.join(card.get('allowedDecisions') or [])}"
               + (f"; {left} s left" if isinstance(left, int) else ""))
    if card.get("canDeny"):
        out.append(f"  deny with: jorah_hud_drive.py deny {card.get('id')}   (only Adam can allow, in the HUD)")
    else:
        out.append("  this card can't be denied from here; only Adam can answer it, in the HUD")
    return "\n".join(out)


def request_for(args):
    if args.command == "status":
        return {"cmd": "status"}
    if args.command == "send":
        return {"cmd": "send", "text": args.text}
    if args.command == "read":
        return {"cmd": "read", "limit": args.n}
    if args.command == "cards":
        return {"cmd": "cards"}
    if args.command == "deny":
        return {"cmd": "deny", "id": args.id}
    if args.command == "wait":
        request = {"cmd": "wait", "seconds": args.timeout}
        if args.sent:
            request["sent"] = args.sent
        return request
    raise DriveError(f"Unknown command {args.command!r}")


def parser():
    top = argparse.ArgumentParser(description="Drive the Jorah HUD while Adam has drive mode on. "
                                              "It can't allow cards: only Adam can, in the HUD.")
    top.add_argument("--socket", help="the HUD's drive socket (default: from JORAH_HUD_PROFILE)")
    top.add_argument("--json", action="store_true", help="print the HUD's raw answers")
    sub = top.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="is drive mode on, which conversation, is Jorah busy")
    send = sub.add_parser("send", help="type a message in the open conversation, as Adam, and wait")
    send.add_argument("text")
    send.add_argument("--timeout", type=float, default=120, help="seconds to wait for the answer (1-600)")
    send.add_argument("--no-wait", action="store_true", help="return as soon as it is sent")
    read = sub.add_parser("read", help="the last lines of the open conversation")
    read.add_argument("-n", type=int, default=12, help="how many lines (1-40)")
    sub.add_parser("cards", help="cards waiting for an answer")
    deny = sub.add_parser("deny", help="deny one card (there is no allow)")
    deny.add_argument("id")
    wait = sub.add_parser("wait", help="wait until Jorah is idle or a card shows")
    wait.add_argument("--timeout", type=float, default=120, help="seconds (1-600)")
    wait.add_argument("--sent", help="wait for the answer to this message")
    return top


def show(reply, as_json):
    if as_json:
        print(json.dumps(reply, ensure_ascii=False, indent=2))


def refused(reply):
    print(f"Refused: {reply.get('error') or 'no reason given'}", file=sys.stderr)
    return FAILED


def print_cards(path, as_json, out):
    reply = call(path, {"cmd": "cards"}, 30)
    show(reply, as_json)
    if not reply.get("ok"):
        print(f"Cards unknown: {reply.get('error')}", file=out)
        return
    if not as_json:
        cards = reply.get("cards") or []
        print("\n\n".join(format_card(c) for c in cards) if cards else "No cards waiting.", file=out)


def run_send(path, args):
    if len(args.text.strip()) == 0 or len(args.text.strip()) > MAX_TEXT:
        print(f"Refused: the text must be 1-{MAX_TEXT} characters.", file=sys.stderr)
        return FAILED
    sent = call(path, {"cmd": "send", "text": args.text}, 30)
    show(sent, args.json)
    if not sent.get("ok"):
        return refused(sent)
    if args.no_wait:
        if not args.json:
            print(f"Sent to {sent.get('sessionKey')}.")
        return DONE
    text = args.text.strip()
    waited = call(path, {"cmd": "wait", "seconds": args.timeout, "sent": text}, args.timeout + 15)
    show(waited, args.json)
    if not waited.get("ok"):
        return refused(waited)
    lines = call(path, {"cmd": "read", "limit": 40}, 30)
    show(lines, args.json)
    if not args.json and lines.get("ok"):
        answer = after_sent(lines.get("lines") or [], text)
        print("\n\n".join(format_line(line) for line in answer) if answer else "(no answer yet)")
    result = waited.get("result")
    if result == "card":
        print("\nA card is waiting; Jorah's run is paused on it.")
        print_cards(path, args.json, sys.stdout)
        return CARD
    if result == "timeout":
        print(f"\nStill going after {args.timeout:g} s.", file=sys.stderr)
        return TIMEOUT
    return DONE


def main(argv=None):
    args = parser().parse_args(argv)
    path = args.socket or socket_path()
    try:
        if args.command == "send":
            return run_send(path, args)
        timeout = (args.timeout + 15) if args.command == "wait" else 30
        reply = call(path, request_for(args), timeout)
        show(reply, args.json)
        if not reply.get("ok"):
            return refused(reply)
        if args.json:
            return {"card": CARD, "timeout": TIMEOUT}.get(reply.get("result"), DONE)
        if args.command == "status":
            print(f"Drive mode on since {clock(reply.get('onSince'))}; {reply.get('phase')}; "
                  f"conversation {reply.get('sessionKey')}; "
                  f"{'Jorah is working' if reply.get('running') else 'Jorah is idle'}; "
                  f"cards waiting: {reply.get('cards') if reply.get('cards') is not None else 'unknown'}")
        elif args.command == "read":
            print("\n\n".join(format_line(line) for line in reply.get("lines") or []) or "(empty)")
            if reply.get("sendError"):
                print(f"\nSend error shown in the HUD: {reply['sendError']}")
        elif args.command == "cards":
            cards = reply.get("cards") or []
            print("\n\n".join(format_card(c) for c in cards) if cards else "No cards waiting.")
        elif args.command == "deny":
            print(reply.get("note") or "Denied.")
        elif args.command == "wait":
            result = reply.get("result")
            if result == "card":
                print("A card is waiting.")
                print_cards(path, False, sys.stdout)
                return CARD
            if result == "timeout":
                print("Still going.")
                return TIMEOUT
            print("Jorah is idle.")
        return DONE
    except DriveError as error:
        print(error, file=sys.stderr)
        return FAILED


if __name__ == "__main__":
    sys.exit(main())
