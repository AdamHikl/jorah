import asyncio
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jorah_voice.approvals import ApprovalsClient, ApprovalsError
from jorah_voice.core import parse_hello
from jorah_voice.identity import Verdict
from jorah_voice.passphrase import PASSPHRASE_FILE, PhraseStore
from jorah_voice.server import handle_phrase_message, resolve_voice_confirm, run_settings_connection
from jorah_voice.session import (
    APPROVALS_UNAVAILABLE_LINE,
    PHRASE_CHECK_ERROR_LINE,
    PHRASE_ONLY_LINE,
    VoiceSession,
)


class FakeEars:
    def __init__(self):
        self.accepted = []
        self.pending = []
        self.speech = False
        self.quiet = 10.0

    def accept(self, pcm):
        self.accepted.append(pcm)

    def speech_now(self):
        return self.speech

    def quiet_seconds(self):
        return self.quiet

    def segments(self):
        found, self.pending = self.pending, []
        return found


class FakeListener:
    def __init__(self, text):
        self.text = text

    def transcribe(self, *pieces):
        return self.text(pieces) if callable(self.text) else self.text


class FakeSpeaker:
    sample_rate = 24000

    def __init__(self):
        self.lines = []

    def synthesize(self, text):
        self.lines.append(text)
        return b"\0\0" * 2400


class FakeBrain:
    def __init__(self, deltas=(), *, gate=None):
        self.deltas = list(deltas)
        self.gate = gate
        self.prompts = []
        self.session_keys = []
        self.cancelled = False

    def stream(self, prompt, session_key=None):
        self.prompts.append(prompt)
        self.session_keys.append(session_key)
        if self.gate:
            self.gate.wait(5)
        for delta in self.deltas:
            yield delta

    def cancel(self):
        self.cancelled = True
        if self.gate:
            self.gate.set()


class FakeSpeakerCheck:
    def __init__(self, verdict=Verdict("adam", 2.0, ">=0.7")):
        self._verdict = verdict
        self.calls = 0

    def verdict(self, samples, sample_rate):
        self.calls += 1
        return self._verdict(samples, sample_rate) if callable(self._verdict) else self._verdict


class FakeApprovals(ApprovalsClient):
    def __init__(self, *, available=True, refused=False, list_error=None):
        self._available = available
        self._refused = refused
        self._list_error = list_error
        self.on_requested = None
        self.on_resolved = None
        self.on_refused = None
        self.listed = []
        self.resolved_calls = []

    @property
    def available(self):
        return self._available

    @property
    def refused(self):
        return self._refused

    def set_handlers(self, *, on_requested=None, on_resolved=None, on_refused=None):
        self.on_requested = on_requested
        self.on_resolved = on_resolved
        self.on_refused = on_refused

    async def list(self):
        if self._list_error:
            raise self._list_error
        return list(self.listed)

    async def resolve(self, approval_id, decision):
        self.resolved_calls.append((approval_id, decision))
        return {"ok": True}

    async def push_request(self, record):
        if self.on_requested:
            await self.on_requested(record)

    async def push_resolved(self, payload):
        if self.on_resolved:
            await self.on_resolved(payload)


def make_card(card_id="plugin:1", *, title="Jorah wants to save to memory", severity="warning",
              session_key="agent:main:main", channel="voice", created_at_ms=1001000, expires_at_ms=1300000):
    return {
        "id": card_id,
        "createdAtMs": created_at_ms,
        "expiresAtMs": expires_at_ms,
        "request": {
            "title": title,
            "description": "Say 'yes, go ahead' or tap here.\nAsked by voice",
            "severity": severity,
            "sessionKey": session_key,
            "turnSourceChannel": channel,
        },
    }


class ConfirmSessionFlow(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vp = Path(self.tmp.name) / "vp"
        self.phrases = PhraseStore(self.vp, scrypt_n=2**10)

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, *, text="Save that plant needs water.", deltas=("Saving it.",), gate=None,
              speaker_verdict=Verdict("adam", 2.0, ">=0.7"), approvals=None, voice_confirm=True,
              session_key="agent:main:main"):
        self.sent = []
        self.logs = []
        self.now = [10.0]
        self.wall = [1000.0]
        self.ears = FakeEars()
        self.listener = FakeListener(text)
        self.speaker = FakeSpeaker()
        self.brain = FakeBrain(deltas, gate=gate)
        self.checker = FakeSpeakerCheck(speaker_verdict)
        self.approvals = approvals or FakeApprovals()

        async def send_json(msg):
            self.sent.append(msg)

        async def send_audio(_pcm):
            pass

        async def on_close():
            pass

        async def no_wait(_s):
            await asyncio.sleep(0)

        self.session = VoiceSession(
            self.ears, self.listener, self.speaker, self.brain,
            send_json, send_audio, on_close,
            clock=lambda: self.now[0],
            wall_clock=lambda: self.wall[0],
            sleep=no_wait,
            log=self.logs.append,
            speaker_check=self.checker,
            phrase_store=self.phrases,
            approvals=self.approvals,
            voice_confirm=voice_confirm,
            session_key=session_key,
        )
        return self.session

    async def say(self, text=None, *, seg=None):
        if text is not None:
            self.listener.text = text
        self.ears.pending = [seg if seg is not None else [0.1] * 32000]
        await self.session.feed(b"\0\0")

    async def settle(self):
        for _ in range(10):
            tasks = [t for t in (self.session._hearing, self.session._turn, self.session._ask_task, self.session._confirm_task) if t is not None and not t.done()]
            if not tasks:
                break
            await asyncio.gather(*tasks, return_exceptions=True)

    async def test_card_question_spoken_after_reply_then_yes_allows_without_reaching_brain(self):
        self.build()
        await self.say()
        await self.settle()
        self.assertEqual(len(self.brain.prompts), 1)
        self.assertEqual(self.speaker.lines, ["Saving it."])

        await self.approvals.push_request(make_card(created_at_ms=1000500))
        await self.settle()
        cards = [m for m in self.sent if m["type"] == "card"]
        self.assertEqual(len(cards), 1)
        self.assertFalse(cards[0]["leaves_pc"])
        self.assertEqual(self.speaker.lines[-2:], ["Jorah wants to save to memory.", "Say 'yes, go ahead' or tap it."])

        self.now[0] += 2.0
        await self.say("Yes, go ahead.")
        await self.settle()
        # Confirming transcript never reached the brain, never went in `heard`, and never in logs.
        self.assertEqual(len(self.brain.prompts), 1)
        self.assertNotIn({"type": "heard", "text": "Yes, go ahead."}, self.sent)
        self.assertEqual(self.approvals.resolved_calls, [("plugin:1", "allow-once")])
        self.assertIn({"type": "card_closed", "id": "plugin:1", "outcome": "allowed"}, self.sent)
        self.assertEqual(self.speaker.lines[-1], "Done.")
        self.assertIn("confirm: allow", self.logs)
        self.assertFalse(any("go ahead" in line for line in self.logs))

    async def test_blocked_gateway_turn_opens_mic_for_confirmation_and_resumes(self):
        gate = threading.Event()
        self.build(deltas=("All saved.",), gate=gate)
        await self.say("Remember the plant needs water.")
        for _ in range(30):
            if self.session._turn_in_flight:
                break
            await asyncio.sleep(0.01)
        self.assertTrue(self.session._turn_in_flight)

        await self.approvals.push_request(make_card(created_at_ms=1000500))
        for _ in range(30):
            if self.session._pending_card and self.session._pending_card.asked_at is not None:
                break
            await asyncio.sleep(0.01)
        self.assertFalse(self.session.busy())

        await self.say("Yes, go ahead.")
        for _ in range(30):
            if self.approvals.resolved_calls:
                break
            await asyncio.sleep(0.01)
        self.assertEqual(self.approvals.resolved_calls, [("plugin:1", "allow-once")])
        self.assertFalse(self.brain.cancelled)

        gate.set()
        await self.settle()
        self.assertIn("All saved.", self.speaker.lines)

    async def test_no_and_cancel_deny_from_anyone_and_stop_keeps_working(self):
        self.build(speaker_verdict=Verdict("someone_else", 0.5, "<0.3"))
        await self.say()
        await self.settle()
        await self.approvals.push_request(make_card(created_at_ms=1000500))
        await self.settle()

        await self.say("No.")
        await self.settle()
        self.assertEqual(self.approvals.resolved_calls, [("plugin:1", "deny")])
        self.assertIn({"type": "card_closed", "id": "plugin:1", "outcome": "denied"}, self.sent)
        self.assertEqual(self.speaker.lines[-1], "Okay, I won't.")

        # "cancel" while a card is pending denies it too; "stop" does not.
        await self.approvals.push_request(make_card(card_id="plugin:2", created_at_ms=1000600))
        await self.settle()
        await self.say("Stop.")
        await self.settle()
        self.assertEqual(len(self.approvals.resolved_calls), 1)
        await self.say("Cancel.")
        await self.settle()
        self.assertEqual(self.approvals.resolved_calls[-1], ("plugin:2", "deny"))

    async def test_leaves_pc_phrase_three_failures_lockout_and_hud_click_unlocks(self):
        self.phrases.set("copper river oak")
        self.build()
        await self.say()
        await self.settle()
        await self.approvals.push_request(make_card(card_id="plugin:push", severity="critical", created_at_ms=1000500))
        await self.settle()
        card_msg = [m for m in self.sent if m["type"] == "card"][0]
        self.assertTrue(card_msg["leaves_pc"])
        self.assertTrue(card_msg["needs_phrase"])
        self.assertTrue(card_msg["phrase_set"])
        self.assertIn("with your phrase", self.speaker.lines[-1])

        # 3 wrong phrases in a row lock out voice confirmation and emit phrase_status.
        for _ in range(3):
            await self.say("Yes, go ahead, wrong words here.")
            await self.settle()
        self.assertTrue(self.phrases.locked)
        self.assertEqual(self.approvals.resolved_calls, [])
        self.assertIn({"type": "phrase_status", "set": True, "words": 3, "locked": True}, self.sent)
        self.assertFalse(any("copper" in line.lower() for line in self.logs))
        self.assertFalse(any("wrong words" in line.lower() for line in self.logs))

        # HUD click resolves card, clears lockout, emits phrase_status and card_closed.
        await self.session.handle_card_decision({"type": "card_decision", "id": "plugin:push", "decision": "allow-once"})
        self.assertFalse(self.phrases.locked)
        self.assertEqual(self.approvals.resolved_calls, [("plugin:push", "allow-once")])
        self.assertIn({"type": "phrase_status", "set": True, "words": 3, "locked": False}, self.sent)
        self.assertIn({"type": "card_closed", "id": "plugin:push", "outcome": "allowed"}, self.sent)

    async def test_resolved_elsewhere_stops_asking_and_ignores_non_matching_cards(self):
        self.build()
        await self.say()
        await self.settle()

        # Non-matching cards are ignored.
        await self.approvals.push_request(make_card(card_id="wrong-session", session_key="agent:other:main", created_at_ms=1000500))
        await self.approvals.push_request(make_card(card_id="wrong-channel", channel="telegram", created_at_ms=1000500))
        await self.approvals.push_request(make_card(card_id="too-old", created_at_ms=999000))
        await self.approvals.push_request(make_card(card_id="too-late", created_at_ms=1006000))
        await self.settle()
        self.assertEqual([m for m in self.sent if m["type"] == "card"], [])

        # Matching card resolved elsewhere (e.g. Telegram).
        await self.approvals.push_request(make_card(card_id="plugin:tg", created_at_ms=1004000))
        await self.settle()
        await self.approvals.push_resolved({"id": "plugin:tg", "decision": "allow-once"})
        await self.settle()
        self.assertIsNone(self.session._pending_card)
        self.assertIn({"type": "card_closed", "id": "plugin:tg", "outcome": "elsewhere"}, self.sent)

    async def test_card_matching_accepts_webchat_and_voice_in_window_and_rejects_outside_window(self):
        self.build()
        await self.say()
        await self.settle()

        # webchat card outside the 5 s post-turn window is ignored.
        await self.approvals.push_request(make_card(card_id="webchat-too-late", channel="webchat", created_at_ms=1006000))
        await self.settle()
        self.assertEqual([m for m in self.sent if m["type"] == "card"], [])

        # webchat card inside the window matches.
        await self.approvals.push_request(make_card(card_id="plugin:webchat", channel="webchat", created_at_ms=1004000))
        await self.settle()
        cards = [m for m in self.sent if m["type"] == "card"]
        self.assertEqual([c["id"] for c in cards], ["plugin:webchat"])
        await self.approvals.push_resolved({"id": "plugin:webchat", "decision": "allow-once"})
        await self.settle()

        # voice channel still matches inside the window (old clients).
        await self.approvals.push_request(make_card(card_id="plugin:voice", channel="voice", created_at_ms=1004500))
        await self.settle()
        cards = [m for m in self.sent if m["type"] == "card"]
        self.assertEqual([c["id"] for c in cards], ["plugin:webchat", "plugin:voice"])

    async def test_refused_approvals_falls_back_once_and_no_voice_confirm_still_sends_cards(self):
        approvals = FakeApprovals(list_error=ApprovalsError("missing scope", refused=True))
        self.build(approvals=approvals)
        await self.say()
        await self.settle()
        self.assertEqual(self.speaker.lines.count(APPROVALS_UNAVAILABLE_LINE), 1)
        await self.say()
        await self.settle()
        self.assertEqual(self.speaker.lines.count(APPROVALS_UNAVAILABLE_LINE), 1)

        # --no-voice-confirm: card is still sent to HUD, yes asks to tap HUD.
        self.build(voice_confirm=False)
        await self.say()
        await self.settle()
        await self.approvals.push_request(make_card(card_id="plugin:noc", created_at_ms=1000500))
        await self.settle()
        self.assertEqual(len([m for m in self.sent if m["type"] == "card"]), 1)
        await self.say("Yes, go ahead.")
        await self.settle()
        self.assertEqual(self.approvals.resolved_calls, [])

    async def test_phrase_alone_with_pending_leaves_pc_card_allows_and_never_reaches_brain(self):
        self.phrases.set("copper river oak")
        self.build()
        await self.say("Push this branch.")
        await self.settle()
        await self.approvals.push_request(make_card(card_id="plugin:push", severity="critical", created_at_ms=1000500))
        await self.settle()

        self.now[0] += 2.0
        await self.say("Copper river oak.")
        await self.settle()

        self.assertEqual(len(self.brain.prompts), 1)
        self.assertEqual([m for m in self.sent if m["type"] == "heard"], [{"type": "heard", "text": "Push this branch."}])
        self.assertEqual(self.approvals.resolved_calls, [("plugin:push", "allow-once")])
        self.assertIn({"type": "card_closed", "id": "plugin:push", "outcome": "allowed"}, self.sent)
        self.assertEqual(self.speaker.lines[-1], "Done.")
        self.assertIn("confirm: allow", self.logs)
        self.assertFalse(any("copper" in line.lower() for line in self.logs))

    async def test_phrase_alone_with_pending_local_card_allows_and_speaker_fail_retries(self):
        self.phrases.set("copper river oak")
        self.build()
        await self.say("Save that.")
        await self.settle()
        await self.approvals.push_request(make_card(card_id="plugin:local", severity="warning", created_at_ms=1000500))
        await self.settle()

        self.now[0] += 2.0
        await self.say("Copper river oak.")
        await self.settle()
        self.assertEqual(len(self.brain.prompts), 1)
        self.assertEqual(self.approvals.resolved_calls, [("plugin:local", "allow-once")])

        # Speaker failure on phrase-only turn retries and never forwards to brain.
        self.build(speaker_verdict=Verdict("someone_else", 2.0, "<0.3"))
        await self.say("Push it.")
        await self.settle()
        await self.approvals.push_request(make_card(card_id="plugin:push2", severity="critical", created_at_ms=1000500))
        await self.settle()
        await self.say("Copper river oak.")
        await self.settle()
        self.assertEqual(len(self.brain.prompts), 1)
        self.assertEqual(self.approvals.resolved_calls, [])
        self.assertIn("confirm: retry", self.logs)

    async def test_phrase_in_sentence_with_no_card_never_reaches_brain_or_heard(self):
        self.phrases.set("copper river oak")
        self.build()
        await self.say("By the way my secret is copper river oak and hello.")
        await self.settle()

        self.assertEqual(self.brain.prompts, [])
        self.assertEqual([m for m in self.sent if m["type"] == "heard"], [])
        self.assertIn("confirm: phrase_only", self.logs)
        self.assertFalse(any("copper" in line.lower() for line in self.logs))
        self.assertEqual(self.speaker.lines[-1], PHRASE_ONLY_LINE)

    async def test_phrase_never_reaches_brain_with_voice_confirm_off(self):
        self.phrases.set("copper river oak")
        self.build(voice_confirm=False)
        await self.say("By the way my secret is copper river oak and hello.")
        await self.settle()

        self.assertEqual(self.brain.prompts, [])
        self.assertEqual([m for m in self.sent if m["type"] == "heard"], [])
        self.assertFalse(any("copper" in line.lower() for line in self.logs))

    async def test_phrase_check_error_or_unreadable_file_fails_closed(self):
        self.phrases.set("copper river oak")
        self.build()
        with mock.patch.object(self.phrases, "matches_within", side_effect=RuntimeError("boom")):
            await self.say("Copper river oak.")
            await self.settle()

        self.assertEqual(self.brain.prompts, [])
        self.assertEqual([m for m in self.sent if m["type"] == "heard"], [])
        self.assertEqual(self.speaker.lines[-1], PHRASE_CHECK_ERROR_LINE)

        # Unreadable passphrase.json also fails closed without forwarding.
        path = self.vp / PASSPHRASE_FILE
        path.chmod(0o000)
        try:
            self.build()
            await self.say("Copper river oak.")
            await self.settle()
            self.assertEqual(self.brain.prompts, [])
            self.assertEqual([m for m in self.sent if m["type"] == "heard"], [])
            self.assertEqual(self.speaker.lines[-1], PHRASE_CHECK_ERROR_LINE)
        finally:
            path.chmod(0o600)

    async def test_normal_turn_with_phrase_set_reaches_brain(self):
        self.phrases.set("copper river oak")
        self.build()
        await self.say("What is the weather in Bratislava?")
        await self.settle()

        self.assertEqual(self.brain.prompts, ["What is the weather in Bratislava?"])
        self.assertIn({"type": "heard", "text": "What is the weather in Bratislava?"}, self.sent)
        self.assertEqual(self.speaker.lines, ["Saving it."])

    async def test_card_matching_uses_the_turns_actual_session_key(self):
        dash1 = "agent:main:dashboard:01234567-89ab-cdef-0123-456789abcdef"
        dash2 = "agent:main:dashboard:aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        self.build(session_key=dash1)
        await self.say("Save that.")
        await self.settle()
        self.assertEqual(self.brain.session_keys, [dash1])

        # Switch to dash2 before the card for turn 1 arrives (still within the 5s post-turn window).
        await self.session.handle_session_message({"type": "session", "session_key": dash2})

        # Cards for main or the new key (dash2) must not match turn 1, which actually used dash1.
        await self.approvals.push_request(make_card(card_id="wrong-main", session_key="agent:main:main", created_at_ms=1000500))
        await self.approvals.push_request(make_card(card_id="wrong-next", session_key=dash2, created_at_ms=1000500))
        await self.settle()
        self.assertEqual([m for m in self.sent if m["type"] == "card"], [])

        # Card for dash1 (the key turn 1 actually used) matches.
        await self.approvals.push_request(make_card(card_id="plugin:dash1", session_key=dash1, created_at_ms=1000500))
        await self.settle()
        cards = [m for m in self.sent if m["type"] == "card"]
        self.assertEqual([c["id"] for c in cards], ["plugin:dash1"])


class FakeSettingsWS:
    def __init__(self, messages):
        self.incoming = list(messages)
        self.sent = []
        self.closed = False

    async def recv(self):
        if self.incoming:
            return self.incoming.pop(0)
        await asyncio.sleep(0.05)
        raise asyncio.TimeoutError()

    async def send(self, text):
        self.sent.append(json.loads(text))

    async def close(self, *_args):
        self.closed = True


class SettingsAndServerFlags(unittest.IsolatedAsyncioTestCase):
    def test_settings_hello_and_resolve_voice_confirm_flags(self):
        token = "t" * 40
        hello = parse_hello(json.dumps({"type": "hello", "token": token, "purpose": "settings"}), token)
        self.assertEqual(hello, {"purpose": "settings"})

        with tempfile.TemporaryDirectory() as tmp:
            vp = Path(tmp) / "vp"
            ok, reason = resolve_voice_confirm(vp, voice_confirm_flag=False)
            self.assertFalse(ok)
            self.assertIn("--no-voice-confirm", reason)

            ok2, reason2 = resolve_voice_confirm(vp, voice_confirm_flag=True, expected_sha256="abc")
            self.assertFalse(ok2)
            self.assertIn("centroids.json", reason2)

            vp.mkdir()
            (vp / "centroids.json").write_text("{}")
            (vp / "thresholds.json").write_text("{}")
            ok3, reason3 = resolve_voice_confirm(vp, voice_confirm_flag=True, expected_sha256=None)
            self.assertFalse(ok3)
            self.assertIn("SHA-256", reason3)

            ok4, reason4 = resolve_voice_confirm(vp, voice_confirm_flag=True, expected_sha256="abc")
            self.assertTrue(ok4)
            self.assertIsNone(reason4)

    async def test_settings_connection_handles_phrase_messages_and_idle_close(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = PhraseStore(Path(tmp) / "vp", scrypt_n=2**10)
            ws = FakeSettingsWS([
                json.dumps({"type": "phrase_status_request"}),
                json.dumps({"type": "phrase_set", "phrase": "too short"}),
                json.dumps({"type": "phrase_set", "phrase": "copper river oak"}),
                json.dumps({"type": "ignored_unknown"}),
                json.dumps({"type": "phrase_clear"}),
            ])
            await run_settings_connection(ws, store, 24000, idle_seconds=0.05)
            self.assertTrue(ws.closed)
            self.assertEqual(ws.sent[0], {"type": "ready", "sample_rate": 24000})
            self.assertEqual(ws.sent[1], {"type": "phrase_status", "set": False, "words": None, "locked": False})
            self.assertEqual(ws.sent[2]["type"], "phrase_error")
            self.assertEqual(ws.sent[3], {"type": "phrase_status", "set": True, "words": 3, "locked": False})
            self.assertEqual(ws.sent[4], {"type": "phrase_status", "set": False, "words": None, "locked": False})


if __name__ == "__main__":
    unittest.main()
