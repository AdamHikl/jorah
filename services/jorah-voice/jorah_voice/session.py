"""One conversation, from audio arriving to audio going back. Knows nothing about the network."""

import asyncio
from dataclasses import dataclass
import json
import threading
import time
from contextlib import aclosing

from . import confirm
from .approvals import ALLOWED_DECISIONS, ApprovalsError
from .brain import BrainError, SESSION_KEY
from .core import (FollowUp, IdleClock, LastFullMessage, MIC_RATE, OverviewSplit, Resampler,
                   SentenceChunker, TurnEnd, clean_for_speech, classify, join_waiting, percentile,
                   resolve_session_key, session_log_label, speakable_sentences)
from .identity import Verdict

BLOCK_SECONDS = 0.1
# After the far end has played the last audio, wait this much longer before listening again: the
# network, the client's own buffer, and the room's echo of Jorah's voice.
ECHO_TAIL_SECONDS = 0.3
BYTES_PER_SAMPLE = 2
FAILURE_LINE = "I can't reach my brain right now."
EMPTY_LINE = "I didn't get an answer. Try me again."
STAY_LINE = "I'm here."
# Said once when no reply text has come for a while, which mostly means Jorah is using a tool
# (2026-11-11: GitHub turns took 7 to 21 s to the first word), so the quiet isn't a dead line.
FILLER_LINE = "One moment."
# A long reply is spoken only up to about this many words, about 15 s, and shown or read in full on
# request (Adam, 2026-11-19: "always the most important stuff, maybe 5-15 seconds max").
SPOKEN_WORDS = 45
ON_SCREEN_LINE = "The full message is on your screen."
READ_ALL_HINT = "Say 'read the whole message' for the rest."
NO_FULL_LINE = "There's no longer message to read."
APPROVALS_UNAVAILABLE_LINE = "I can't see approval cards from here, so please tap the card in the HUD."
PHRASE_ONLY_LINE = "There's nothing waiting for a yes right now."
PHRASE_CHECK_ERROR_LINE = "Something went wrong, say that again?"
CARD_AFTER_TURN_WINDOW_MS = 5000


STAY_WARNING = "I'll stop listening in half a minute."


class Filler(str):
    """A line Jorah says while waiting: not the reply, so it isn't timed or joined to it."""


# Longest piece of text spoken in one go, after the first sentence of a reply.
SPOKEN_CHUNK_CHARS = 300


@dataclass
class PendingCard:
    id: str
    raw_title: str
    raw_description: str
    leaves_pc: bool
    expires_at_ms: int | float | None
    needs_phrase: bool
    phrase_set: bool
    voice_active: bool
    attempts: int = 0
    asked_at: float | None = None


def _join_segments(held):
    if len(held) == 1:
        return held[0]
    first = held[0]
    if hasattr(first, "shape"):
        import numpy as np
        return np.concatenate(held)
    if isinstance(first, (bytes, bytearray)):
        return b"".join(held)
    if isinstance(first, list):
        out = []
        for item in held:
            out.extend(item)
        return out
    return held


def _card_question_lines(card, *, locked=False):
    title = clean_for_speech(card.raw_title) or "Approval needed."
    if title[-1:] not in ".?!":
        title = f"{title}."
    if not card.voice_active:
        return [title, "Tap it in the HUD."]
    if locked:
        return [title, confirm.LOCKED_LINE]
    if card.needs_phrase and not card.phrase_set:
        return [title, confirm.PHRASE_MISSING_LINE]
    if card.needs_phrase:
        return [title, "Say 'yes, go ahead' with your phrase, or tap it."]
    return [title, "Say 'yes, go ahead' or tap it."]


class VoiceSession:
    def __init__(self, ears, listener, speaker, brain, send_json, send_audio, on_close, *,
                 barge_in=False, idle_seconds=60, max_seconds=1800,
                 clock=time.monotonic, sleep=asyncio.sleep, lead=0.2, turn_end=None,
                 follow_up=False, input_rate=16000, filler_seconds=None, client_ends=False,
                 stream_speech=True, log=None, shows_full=False, full_store=None, spoken_words=SPOKEN_WORDS,
                 speaker_check=None, phrase_store=None, approvals=None, voice_confirm=True,
                 session_key=SESSION_KEY, wall_clock=time.time):
        self._ears = ears
        self._listener = listener
        self._speaker = speaker
        self._brain = brain
        self._send_json = send_json
        self._send_audio = send_audio
        self._on_close = on_close
        self._barge_in = barge_in
        self._idle_seconds = idle_seconds
        self._max_seconds = max_seconds
        self._clock = clock
        self._sleep = sleep
        self._lead = lead
        # When the far end will have played all audio sent so far, on `clock`. One clock for the
        # session, so the far end never runs more than `lead` ahead however the audio is split up.
        self._plays_until = clock()
        self._turn_end = turn_end or TurnEnd(0.6, 0.6)
        # Speech segments of the turn in progress, held until a long enough pause ends the turn.
        self._held = []
        self._heard = None
        self._hearing = None
        self._version = 0
        self._idle = IdleClock(idle_seconds, now=clock)
        self._started = clock()
        self._turn = None
        # Short windows from voice plan 04 5.3, for clients that open per conversation.
        self._follow_up = FollowUp(clock()) if follow_up else None
        self._resampler = Resampler(input_rate)
        self._filler_seconds = filler_seconds
        self._client_ends = client_ends
        # Speakers that can (Qwen3-TTS) send a sentence's audio as it's made, not when it's done.
        self._stream_speech = stream_speech
        self._log = log or (lambda line: print(line, flush=True))
        # Long replies: the client shows `full_reply` (the HUD), and the last full message is kept
        # for "read the whole message", shared across sessions by the server.
        self._shows_full = shows_full
        self._full_store = full_store if full_store is not None else LastFullMessage()
        self._spoken_words = spoken_words

        # Voice confirmation state.
        self._speaker_check = speaker_check
        self._phrase_store = phrase_store
        self._approvals = approvals
        self._voice_confirm = bool(voice_confirm)
        self._session_key = resolve_session_key(session_key)
        self._wall_clock = wall_clock

        self._turn_in_flight = False
        self._turn_session_key = None
        self._turn_started_ms = None
        self._turn_ended_ms = None
        self._pending_card = None
        self._closed_cards = set()
        self._waiting_for_card = False
        self._speech_idle = asyncio.Event()
        self._speech_idle.set()
        self._speak_lock = asyncio.Lock()
        self._ask_task = None
        self._confirm_task = None
        self._retry_counter = 0
        self._resolving_id = None
        self._approvals_refused = False
        self._told_tap_card = False

        if self._approvals is not None:
            self._approvals.set_handlers(
                on_requested=self._on_approval_requested,
                on_resolved=self._on_approval_resolved,
                on_refused=self._on_approvals_refused,
            )
            if self._approvals.refused:
                self._approvals_refused = True

        # On standby, audio is dropped unheard until the client hangs up.
        self.standby = False
        self.closed = False
        self.numbers = {"transcribe": [], "end_pause": [], "first_token": [], "first_sentence": [], "first_audio": []}

    def busy(self):
        if self._confirm_task is not None and not self._confirm_task.done():
            return True
        if self._ask_task is not None and not self._ask_task.done():
            return True
        if self._turn is not None and not self._turn.done():
            return not self._waiting_for_card
        return False

    async def feed(self, pcm):
        """Take mic audio. While Jorah is busy it is ignored, unless talking over him is switched on."""
        if self.closed or self.standby:
            return
        if self.busy() and not self._barge_in:
            self._idle.touch()
            return
        self._ears.accept(self._resampler.convert(pcm))
        speaking = self._ears.speech_now()
        if self.busy() and speaking:
            await self.interrupt()
        segments = self._ears.segments()
        if self._follow_up and (speaking or segments):
            self._follow_up.heard(self._clock())
        if segments:
            self._held.extend(segments)
            self._listen()
        await self._maybe_end()

    def _listen(self):
        """Transcribe everything held so far. A newer segment makes an older transcript stale."""
        self._version += 1
        self._heard = None
        self._hearing = asyncio.create_task(self._hear(self._version, list(self._held)))

    def _check_phrase(self, text):
        """Check whether `text` contains the confirmation phrase, failing closed on any error."""
        try:
            if self._phrase_store.matches_within(text):
                return "matched"
            is_healthy = getattr(self._phrase_store, "is_healthy", None)
            if callable(is_healthy) and not is_healthy():
                return "error"
            return "none"
        except Exception:
            return "error"

    async def _hear(self, version, held):
        started = self._clock()
        if self._speaker_check is not None and self._voice_confirm:
            samples = _join_segments(held)
            text, verdict = await asyncio.gather(
                asyncio.to_thread(self._listener.transcribe, *held),
                self._safe_verdict(samples),
            )
        else:
            text = await asyncio.to_thread(self._listener.transcribe, *held)
            verdict = None
        if version != self._version or self.closed:
            return
        phrase_state = "none"
        # Even with voice confirmation off (no voiceprint yet), a set phrase must never be sent on.
        if self._phrase_store is not None:
            phrase_state = await asyncio.to_thread(self._check_phrase, text)
            if version != self._version or self.closed:
                return
        self._heard = (text, self._clock() - started, verdict, phrase_state)
        await self._maybe_end()

    async def _safe_verdict(self, samples):
        try:
            return await asyncio.to_thread(self._speaker_check.verdict, samples, MIC_RATE)
        except Exception:
            return Verdict("unavailable", 0.0, None)

    async def _maybe_end(self):
        """Start Jorah's turn once the transcript is in and the pause is long enough for it."""
        if self._heard is None:
            return
        text, seconds, verdict, phrase_state = self._heard
        quiet = self._ears.quiet_seconds()
        if not self._turn_end.done(text, quiet, self._ears.speech_now()):
            return
        self._held, self._heard = [], None
        self._version += 1
        self.numbers["transcribe"].append(seconds)
        self.numbers["end_pause"].append(quiet)
        marks = {"end_pause": round(quiet, 2), "transcribe": round(seconds, 2)}
        if self._pending_card is not None:
            await self._interrupt_confirm_only()
            self._confirm_task = asyncio.create_task(
                self._handle_turn_with_pending_card(text, marks, verdict, phrase_state)
            )
            return
        await self.interrupt(quiet=True)
        self._turn = asyncio.create_task(
            self._run_turn(text, marks, verdict=verdict, phrase_state=phrase_state)
        )

    async def _interrupt_confirm_only(self):
        if self._ask_task and not self._ask_task.done():
            self._ask_task.cancel()
            await asyncio.gather(self._ask_task, return_exceptions=True)
        if self._confirm_task and not self._confirm_task.done():
            self._confirm_task.cancel()
            await asyncio.gather(self._confirm_task, return_exceptions=True)
        self._idle.touch()

    async def interrupt(self, quiet=False):
        """Stop thinking and speaking at once."""
        did_cut = False
        if self._ask_task and not self._ask_task.done():
            self._ask_task.cancel()
            await asyncio.gather(self._ask_task, return_exceptions=True)
            did_cut = True
        if self._confirm_task and not self._confirm_task.done():
            self._confirm_task.cancel()
            await asyncio.gather(self._confirm_task, return_exceptions=True)
            did_cut = True
        if self._turn and not self._turn.done() and not self._waiting_for_card:
            self._brain.cancel()
            self._turn.cancel()
            await asyncio.gather(self._turn, return_exceptions=True)
            did_cut = True
        if not did_cut:
            return
        self._idle.touch()
        if not quiet:
            await self._send_json({"type": "cut"})
            # The client empties its player on "cut", so nothing is left playing.
            self._plays_until = self._clock()
            await self._state("listening")

    async def _cancel_all_tasks(self):
        if self._ask_task and not self._ask_task.done():
            self._ask_task.cancel()
            await asyncio.gather(self._ask_task, return_exceptions=True)
        if self._confirm_task and not self._confirm_task.done():
            self._confirm_task.cancel()
            await asyncio.gather(self._confirm_task, return_exceptions=True)
        if self._turn and not self._turn.done():
            self._brain.cancel()
            self._turn.cancel()
            await asyncio.gather(self._turn, return_exceptions=True)

    async def watch(self):
        """Close the session after a quiet stretch or at the hard limit, so the mic can't stay open."""
        while not self.closed:
            await self._sleep(1)
            if self._clock() - self._started >= self._max_seconds:
                await self._cancel_all_tasks()
                await self.close(f"{self._max_seconds // 60} minute limit")
            elif self.busy() or self._waiting_for_card or self._held or self.standby or self._client_ends:
                # A client that ends the session itself keeps it open through quiet:
                # Adam ends Talk with its control, or by saying goodbye or thanks.
                continue
            elif self._follow_up:
                verdict = self._follow_up.check(self._clock())
                if verdict and verdict[0] == "close":
                    await self.end(verdict[1])
                elif verdict:
                    self._turn = asyncio.create_task(self._say_only(STAY_WARNING))
            elif self._idle.expired():
                await self.end(f"{self._idle_seconds}s of quiet")

    async def end(self, reason):
        """End the conversation: close it, or go on standby if only the client may close it."""
        if not self._client_ends:
            await self.close(reason)
            return
        if self.standby or self.closed:
            return
        self.standby = True
        self._held, self._heard = [], None
        self._version += 1
        await self._send_json({"type": "standby", "reason": reason})
        await self._state("standby")

    async def close(self, reason):
        if self.closed:
            return
        self.closed = True
        await self._send_json({"type": "closed", "reason": reason, "numbers": self.summary()})
        await self._on_close()

    def summary(self):
        out = {}
        for name, values in self.numbers.items():
            out[name] = {
                "median": percentile(values, 0.5),
                "p90": percentile(values, 0.9),
                "turns": len(values),
            }
        return out

    async def _state(self, state):
        await self._send_json({"type": "state", "state": state})

    def _matches_turn(self, record):
        if not isinstance(record, dict):
            return False
        card_id = record.get("id")
        if not isinstance(card_id, str) or not card_id or card_id in self._closed_cards:
            return False
        if self._pending_card is not None and self._pending_card.id == card_id:
            return False
        req = record.get("request")
        if not isinstance(req, dict):
            return False
        if self._turn_session_key is None or req.get("sessionKey") != self._turn_session_key:
            return False
        if req.get("turnSourceChannel") not in ("voice", "webchat"):
            return False
        created = record.get("createdAtMs")
        if not isinstance(created, (int, float)) or self._turn_started_ms is None:
            return False
        if self._turn_in_flight:
            return created >= self._turn_started_ms
        if self._turn_ended_ms is None:
            return False
        return self._turn_started_ms <= created <= self._turn_ended_ms + CARD_AFTER_TURN_WINDOW_MS

    async def _on_approvals_refused(self, _reason=None):
        self._approvals_refused = True
        if self.closed or self._told_tap_card or self._turn_in_flight:
            return
        self._told_tap_card = True
        await self._speak_lines([APPROVALS_UNAVAILABLE_LINE], self._clock(), record=False)
        if not self.busy():
            self._idle.touch()
            self._replied("")
            await self._state("listening")

    async def _on_approval_requested(self, record):
        if self.closed or not self._matches_turn(record):
            return
        req = record.get("request") or {}
        leaves_pc = confirm.is_leaving_pc(req.get("severity"))
        phrase_set = self._phrase_store.is_set() if self._phrase_store is not None else False
        card = PendingCard(
            id=record["id"],
            raw_title=str(req.get("title") or "Approval needed"),
            raw_description=str(req.get("description") or ""),
            leaves_pc=leaves_pc,
            expires_at_ms=record.get("expiresAtMs"),
            needs_phrase=leaves_pc,
            phrase_set=phrase_set,
            voice_active=self._voice_confirm,
        )
        self._pending_card = card
        await self._send_json({
            "type": "card",
            "id": card.id,
            "title": card.raw_title,
            "description": card.raw_description,
            "leaves_pc": card.leaves_pc,
            "expires_at_ms": card.expires_at_ms,
            "needs_phrase": card.needs_phrase,
            "phrase_set": card.phrase_set,
        })
        if self._ask_task and not self._ask_task.done():
            self._ask_task.cancel()
        self._ask_task = asyncio.create_task(self._ask_card(card))

    async def _on_approval_resolved(self, payload):
        if self.closed or not isinstance(payload, dict):
            return
        card_id = payload.get("id")
        if not isinstance(card_id, str) or card_id in self._closed_cards:
            return
        if self._resolving_id == card_id:
            return
        if self._pending_card is None or self._pending_card.id != card_id:
            return
        self._clear_pending_card(card_id)
        if self._ask_task and not self._ask_task.done():
            self._ask_task.cancel()
        decision = payload.get("decision")
        reason = payload.get("terminalReason")
        outcome = "expired" if (decision is None or reason == "expired") else "elsewhere"
        await self._send_json({"type": "card_closed", "id": card_id, "outcome": outcome})
        if not self._turn_in_flight:
            await self._state("listening")

    def _clear_pending_card(self, card_id):
        self._closed_cards.add(card_id)
        if self._pending_card is not None and self._pending_card.id == card_id:
            self._pending_card = None
        self._waiting_for_card = False

    def refresh_pending_phrase_status(self):
        if self._pending_card is not None and self._phrase_store is not None:
            self._pending_card.phrase_set = self._phrase_store.is_set()

    async def _ask_card(self, card):
        try:
            # Wait for any current reply speech to finish playing before speaking the card's question.
            await self._speech_idle.wait()
            if self._turn and not self._turn.done() and not self._turn_in_flight:
                await asyncio.gather(self._turn, return_exceptions=True)
            else:
                remaining = max(0.0, self._plays_until - self._clock())
                if remaining > 0:
                    await self._sleep(remaining + ECHO_TAIL_SECONDS)
            if self.closed or self._pending_card is None or self._pending_card.id != card.id:
                return
            self._waiting_for_card = True
            locked = self._phrase_store.locked if self._phrase_store is not None else False
            lines = _card_question_lines(card, locked=locked)
            await self._speak_lines(lines, self._clock(), record=False)
            if self.closed or self._pending_card is None or self._pending_card.id != card.id:
                return
            card.asked_at = self._clock()
            self._idle.touch()
            self._replied(" ".join(lines))
            await self._state("listening")
        except asyncio.CancelledError:
            pass

    async def handle_session_message(self, msg):
        if self.closed:
            return
        raw_key = msg.get("session_key")
        if isinstance(raw_key, str) and resolve_session_key(raw_key) == raw_key:
            self._session_key = raw_key
            self._log(f"session: {session_log_label(raw_key)}")
            await self._send_json({"type": "session", "session_key": raw_key, "ok": True})
        else:
            self._log("session: refused")
            await self._send_json({"type": "session", "session_key": raw_key, "ok": False})

    async def handle_card_decision(self, msg):
        card_id = msg.get("id")
        decision = msg.get("decision")
        if not isinstance(card_id, str) or not card_id or decision not in ALLOWED_DECISIONS:
            return
        if self._approvals is None:
            return
        self._resolving_id = card_id
        outcome = "allowed" if decision == "allow-once" else "denied"
        try:
            await self._approvals.resolve(card_id, decision)
        except ApprovalsError as err:
            if "already resolved" in str(err).lower():
                outcome = "elsewhere"
            else:
                if err.refused:
                    await self._on_approvals_refused(str(err))
                return
        finally:
            self._resolving_id = None

        if self._phrase_store is not None:
            was_locked = self._phrase_store.locked
            self._phrase_store.unlock()
            if was_locked:
                await self._send_json({"type": "phrase_status", **self._phrase_store.status()})

        if self._pending_card is not None and self._pending_card.id == card_id:
            if self._ask_task and not self._ask_task.done():
                self._ask_task.cancel()
            self._clear_pending_card(card_id)
            await self._send_json({"type": "card_closed", "id": card_id, "outcome": outcome})
            if not self._turn_in_flight:
                await self._state("listening")

    async def _resolve_pending_from_voice(self, card, decision, spoken_line):
        if self._approvals is None:
            return
        self._resolving_id = card.id
        outcome = "allowed" if decision == "allow-once" else "denied"
        try:
            await self._approvals.resolve(card.id, decision)
        except ApprovalsError as err:
            if "already resolved" in str(err).lower():
                outcome = "elsewhere"
                spoken_line = ""
            elif err.refused:
                self._clear_pending_card(card.id)
                await self._send_json({"type": "card_closed", "id": card.id, "outcome": "elsewhere"})
                await self._on_approvals_refused(str(err))
                return
            else:
                await self._speak_lines([confirm.GIVE_UP_LINE], self._clock(), record=False)
                return
        finally:
            self._resolving_id = None

        self._clear_pending_card(card.id)
        await self._send_json({"type": "card_closed", "id": card.id, "outcome": outcome})
        if spoken_line:
            await self._speak_lines([spoken_line], self._clock(), record=False)
        self._idle.touch()
        self._replied(spoken_line)
        if not self._turn_in_flight:
            await self._state("listening")

    async def _handle_turn_with_pending_card(self, text, marks, verdict, phrase_state="none"):
        card = self._pending_card
        if card is None:
            await self._run_turn(text, marks, verdict=verdict, phrase_state=phrase_state)
            return

        if phrase_state == "error":
            self._log("confirm: phrase_error")
            await self._speak_lines([PHRASE_CHECK_ERROR_LINE], self._clock(), record=False)
            self._idle.touch()
            self._replied(PHRASE_CHECK_ERROR_LINE)
            await self._state("listening")
            return

        if phrase_state != "matched":
            kind = classify(text)
            if kind == "empty":
                await self._state("listening")
                return
            if kind == "stop":
                self._replied("")
                await self._state("listening")
                return
            if kind == "end":
                await self._cancel_all_tasks()
                await self._speak_lines(["Talk soon."], self._clock(), record=False)
                await self.end("said goodbye")
                return
            if kind == "end_quietly":
                await self._cancel_all_tasks()
                await self.end("said thanks")
                return
            if kind == "read_all":
                full = self._full_store.get()
                await self._speak_lines(speakable_sentences(full) if full else [NO_FULL_LINE], self._clock(), record=False)
                self._replied("")
                await self._state("listening")
                return
            if kind == "stay":
                if self._follow_up:
                    self._follow_up.stay(self._clock())
                await self._speak_lines([STAY_LINE], self._clock(), record=False)
                self._replied("")
                await self._state("listening")
                return
            if kind == "cancel":
                self._log("confirm: deny")
                await self._resolve_pending_from_voice(card, "deny", confirm.DENIED_LINE)
                return

        if not card.voice_active:
            intent = confirm.classify_answer(text)
            if intent == "deny":
                self._log("confirm: deny")
                await self._resolve_pending_from_voice(card, "deny", confirm.DENIED_LINE)
                return
            if intent == "allow" or phrase_state == "matched":
                self._log("confirm: give_up")
                await self._speak_lines([confirm.GIVE_UP_LINE], self._clock(), record=False)
                await self._state("listening")
                return
            await self._handoff_to_brain(text, marks, verdict, phrase_state=phrase_state)
            return

        phrase_status = (
            self._phrase_store.status()
            if self._phrase_store is not None
            else {"set": False, "words": None, "locked": False}
        )
        seconds_since = 0.0 if card.asked_at is None else max(0.0, self._clock() - card.asked_at)
        verdict_kind = verdict.kind if verdict is not None else "unavailable"
        speech_seconds = verdict.speech_seconds if verdict is not None else 0.0
        phrase_matches = phrase_state == "matched"

        result = confirm.decide(
            leaves_pc=card.leaves_pc,
            seconds_since_asked=seconds_since,
            transcript=text,
            verdict_kind=verdict_kind,
            speech_seconds=speech_seconds,
            phrase_set=phrase_status["set"],
            phrase_matches=phrase_matches,
            phrase_locked=phrase_status["locked"],
            attempts=card.attempts,
            retry_index=self._retry_counter,
        )

        if result.outcome == "not_an_answer":
            await self._handoff_to_brain(text, marks, verdict, phrase_state=phrase_state)
            return

        if result.phrase_failed and self._phrase_store is not None:
            just_locked = self._phrase_store.record_failure()
            if just_locked:
                await self._send_json({"type": "phrase_status", **self._phrase_store.status()})
                self._log("confirm: give_up")
                await self._speak_lines([confirm.LOCKED_LINE], self._clock(), record=False)
                self._idle.touch()
                self._replied(confirm.LOCKED_LINE)
                await self._state("listening")
                return

        self._log(f"confirm: {result.outcome}")

        if result.outcome == "allow":
            if card.leaves_pc and self._phrase_store is not None:
                self._phrase_store.record_success()
            await self._resolve_pending_from_voice(card, "allow-once", result.line)
            return

        if result.outcome == "deny":
            await self._resolve_pending_from_voice(card, "deny", result.line)
            return

        if result.outcome == "retry":
            card.attempts += 1
            self._retry_counter += 1
            await self._speak_lines([result.line], self._clock(), record=False)
            card.asked_at = self._clock()
            self._idle.touch()
            self._replied(result.line)
            await self._state("listening")
            return

        await self._speak_lines([result.line], self._clock(), record=False)
        self._idle.touch()
        self._replied(result.line)
        await self._state("listening")

    async def _handoff_to_brain(self, text, marks, verdict, *, phrase_state="none"):
        if phrase_state != "none":
            await self._run_turn(text, marks, verdict=verdict, phrase_state=phrase_state)
            return
        if self._turn and not self._turn.done():
            self._brain.cancel()
            self._turn.cancel()
            await asyncio.gather(self._turn, return_exceptions=True)
        self._waiting_for_card = False
        self._turn = asyncio.create_task(self._run_turn(text, marks, verdict=verdict, phrase_state=phrase_state))

    async def _run_turn(self, text, marks=None, *, verdict=None, phrase_state="none"):
        turn_key = self._session_key
        await self._state("thinking")
        heard_at = self._clock()
        if phrase_state == "error":
            self._idle.touch()
            self._log("confirm: phrase_error")
            await self._speak_lines([PHRASE_CHECK_ERROR_LINE], heard_at, record=False)
            self._replied(PHRASE_CHECK_ERROR_LINE)
            await self._state("listening")
            return
        if phrase_state == "matched":
            self._idle.touch()
            self._log("confirm: phrase_only")
            await self._speak_lines([PHRASE_ONLY_LINE], heard_at, record=False)
            self._replied(PHRASE_ONLY_LINE)
            await self._state("listening")
            return
        kind = classify(text)
        if kind == "empty":
            await self._state("listening")
            return
        self._idle.touch()
        await self._send_json({"type": "heard", "text": text})
        if kind in ("stop", "cancel"):
            self._replied("")
            await self._state("listening")
            return
        if kind == "end":
            await self._speak_lines(["Talk soon."], heard_at, record=False)
            await self.end("said goodbye")
            return
        if kind == "end_quietly":
            await self.end("said thanks")
            return
        if kind == "read_all":
            full = self._full_store.get()
            await self._speak_lines(speakable_sentences(full) if full else [NO_FULL_LINE], heard_at, record=False)
            self._replied("")
            await self._state("listening")
            return
        if kind == "stay":
            if self._follow_up:
                self._follow_up.stay(self._clock())
            await self._speak_lines([STAY_LINE], heard_at, record=False)
            self._replied("")
            await self._state("listening")
            return
        marks = dict(marks or {})
        if verdict is not None:
            marks["speaker"] = verdict.kind
            if verdict.bucket is not None:
                marks["bucket"] = verdict.bucket
        self._turn_in_flight = True
        self._turn_session_key = turn_key
        self._turn_started_ms = self._wall_clock() * 1000.0
        self._turn_ended_ms = None
        try:
            reply = await self._reply(text, heard_at, marks, session_key=turn_key)
        finally:
            self._turn_in_flight = False
            self._turn_ended_ms = self._wall_clock() * 1000.0
            # Timing and verdict/bucket only, one line a turn. What was said is never logged.
            self._log(f"turn: {json.dumps(marks)}")
        await self._poll_approvals_once()
        if self._approvals_refused and not self._told_tap_card and not self.closed:
            self._told_tap_card = True
            await self._speak_lines([APPROVALS_UNAVAILABLE_LINE], self._clock(), record=False)
        self._idle.touch()
        self._replied(reply)
        await self._state("listening")

    async def _poll_approvals_once(self):
        if self._approvals is None or self._approvals_refused or not self._approvals.available:
            return
        try:
            records = await self._approvals.list()
        except ApprovalsError as err:
            if err.refused:
                await self._on_approvals_refused(str(err))
            return
        for record in records:
            if self._matches_turn(record):
                await self._on_approval_requested(record)
                break

    def _replied(self, text):
        if self._follow_up:
            self._follow_up.replied(self._clock(), text)

    async def _say_only(self, line):
        """Speak a line of Jorah's own, such as a warning, without a turn from Adam."""
        await self._speak_lines([line], self._clock(), record=False)
        self._idle.touch()
        self._replied("")
        await self._state("listening")

    async def _reply(self, text, heard_at, marks=None, *, session_key=None):
        """Stream Jorah's answer and speak it. Fills `marks` with seconds from `heard_at`."""
        marks = {} if marks is None else marks
        sentences = asyncio.Queue()
        speaking = asyncio.create_task(self._speak_queue(sentences, heard_at, record=True, marks=marks))
        chunker = SentenceChunker()
        split = OverviewSplit()
        reply = []
        spoken = []
        held = False  # part of the reply went unspoken: over the word limit
        got_text = asyncio.Event()

        def since_heard():
            return round(self._clock() - heard_at, 2)

        def queue_sentence(sentence):
            """Speak the overview, up to the word limit. The first sentence is always spoken."""
            nonlocal held
            words = len(sentence.split())
            if held or (spoken and sum(len(s.split()) for s in spoken) + words > self._spoken_words):
                held = True
                return
            spoken.append(sentence)
            if "first_sentence" not in marks:
                marks["first_sentence"] = since_heard()
                self.numbers["first_sentence"].append(marks["first_sentence"])
            sentences.put_nowait(sentence)

        async def filler():
            await self._sleep(self._filler_seconds)
            if not got_text.is_set() and self._pending_card is None:
                marks["filler"] = since_heard()
                sentences.put_nowait(Filler(FILLER_LINE))

        waiting = asyncio.create_task(filler()) if self._filler_seconds else None
        try:
            first_token = None
            async for delta in self._stream(text, session_key=session_key):
                if first_token is None:
                    got_text.set()
                    if waiting:
                        waiting.cancel()
                    first_token = self._clock()
                    self.numbers["first_token"].append(first_token - heard_at)
                    marks["first_token"] = round(first_token - heard_at, 2)
                reply.append(delta)
                for sentence in chunker.feed(split.feed(delta)):
                    queue_sentence(sentence)
            marks["reply_done"] = since_heard()
            for sentence in chunker.feed(split.finish()) + chunker.flush():
                queue_sentence(sentence)
            full = (split.full or "").strip()
            if full and not spoken:
                # The overview was missing: speak the start of the full message instead.
                for sentence in speakable_sentences(full):
                    queue_sentence(sentence)
            elif held and not full:
                full = "".join(reply).strip()  # no "Full message:" line, and too long to say
            if full:
                # Shown on screen (the HUD) while the overview is spoken, and kept for "read the whole message".
                await self._send_json({"type": "full_reply", "text": full})
                self._full_store.keep(full)
                marks["full_chars"] = len(full)
                if not self._shows_full:
                    sentences.put_nowait(Filler(READ_ALL_HINT))
                elif held:
                    sentences.put_nowait(Filler(ON_SCREEN_LINE))
            if not reply:
                sentences.put_nowait(EMPTY_LINE)
            sentences.put_nowait(None)
            await speaking
            marks["reply_chars"] = sum(len(part) for part in reply)
            marks["spoken_words"] = sum(len(s.split()) for s in spoken)
            return " ".join(spoken)
        except BrainError as error:
            print(f"brain failed: {error}", flush=True)
            marks["brain_failed"] = since_heard()
            sentences.put_nowait(FAILURE_LINE)
            sentences.put_nowait(None)
            await speaking
            return FAILURE_LINE
        except asyncio.CancelledError:
            marks["cut"] = since_heard()
            if waiting:
                waiting.cancel()
            speaking.cancel()
            await asyncio.gather(speaking, return_exceptions=True)
            raise

    async def _stream(self, text, *, session_key=None):
        """Run the blocking brain call on a thread and hand its text to this loop."""
        loop = asyncio.get_running_loop()
        items = asyncio.Queue()
        key = self._session_key if session_key is None else session_key

        def pump():
            try:
                for delta in self._brain.stream(text, session_key=key):
                    loop.call_soon_threadsafe(items.put_nowait, ("text", delta))
                loop.call_soon_threadsafe(items.put_nowait, ("end", None))
            except Exception as error:
                loop.call_soon_threadsafe(items.put_nowait, ("error", error))

        loop.run_in_executor(None, pump)
        while True:
            kind, value = await items.get()
            if kind == "text":
                yield value
            elif kind == "end":
                return
            else:
                raise BrainError(str(value))

    async def _speak_lines(self, lines, heard_at, record):
        sentences = asyncio.Queue()
        for line in lines:
            sentences.put_nowait(line)
        sentences.put_nowait(None)
        await self._speak_queue(sentences, heard_at, record)

    async def _speak_queue(self, sentences, heard_at, record, marks=None):
        first = True
        ended = False
        while not ended:
            sentence = await sentences.get()
            if sentence is None:
                break
            async with self._speak_lock:
                self._speech_idle.clear()
                try:
                    if isinstance(sentence, Filler):
                        await self._send_json({"type": "reply", "text": str(sentence)})
                        async with aclosing(self._sound(str(sentence))) as sound:
                            async for pcm in sound:
                                await self._send_paced(pcm)
                    else:
                        if not first:
                            # Kokoro shapes tone within one piece of text only, so sentences that are already
                            # waiting are spoken together. The first stays alone, to start speaking sooner.
                            limit = getattr(self._speaker, "chunk_chars", SPOKEN_CHUNK_CHARS)
                            sentence, ended = join_waiting(sentence, sentences, limit)
                        await self._send_json({"type": "reply", "text": sentence})
                        async with aclosing(self._sound(sentence)) as sound:
                            async for pcm in sound:
                                if first:
                                    first = False
                                    if record:
                                        self.numbers["first_audio"].append(self._clock() - heard_at)
                                        if marks is not None:
                                            marks["first_audio"] = round(self._clock() - heard_at, 2)
                                    await self._state("speaking")
                                await self._send_paced(pcm)
                finally:
                    if sentences.empty():
                        self._speech_idle.set()
        # What's already sent is still playing at the far end: listen again only once it's done.
        async with self._speak_lock:
            self._speech_idle.clear()
            try:
                await self._sleep(max(0.0, self._plays_until - self._clock()) + ECHO_TAIL_SECONDS)
            finally:
                self._speech_idle.set()

    async def _sound(self, text):
        """Yield the audio for one piece of text: in pieces as it's made when the speaker can stream,
        otherwise all at once. Stopping early (Adam talks over Jorah) stops the speaker too."""
        stream = getattr(self._speaker, "stream", None) if self._stream_speech else None
        if stream is None:
            yield await asyncio.to_thread(self._speaker.synthesize, text)
            return
        loop = asyncio.get_running_loop()
        pieces = asyncio.Queue()
        stop = threading.Event()

        def pump():
            source = stream(text)
            try:
                for pcm in source:
                    if stop.is_set():
                        break
                    loop.call_soon_threadsafe(pieces.put_nowait, ("audio", pcm))
                loop.call_soon_threadsafe(pieces.put_nowait, ("end", None))
            except Exception as error:
                loop.call_soon_threadsafe(pieces.put_nowait, ("error", error))
            finally:
                source.close()

        loop.run_in_executor(None, pump)
        try:
            while True:
                kind, value = await pieces.get()
                if kind == "audio":
                    yield value
                elif kind == "end":
                    return
                else:
                    raise value
        finally:
            stop.set()

    async def _send_paced(self, pcm):
        """Send at about playing speed, at most `lead` ahead of the far end, so a cut-off is heard straight
        away and the mic stays shut until he's done.

        The play-out clock is the session's, not this call's. Until 2026-11-20 each call started its own,
        so every streamed piece (about 0.64 s) let the far end run `lead` further ahead: seconds by the end
        of a long reply, and the mic reopened while Jorah was still talking.
        """
        bytes_per_second = self._speaker.sample_rate * BYTES_PER_SAMPLE
        block = int(self._speaker.sample_rate * BLOCK_SECONDS) * BYTES_PER_SAMPLE
        for offset in range(0, len(pcm), block):
            piece = pcm[offset : offset + block]
            # A gap with nothing to play (Jorah still thinking) leaves nothing queued.
            self._plays_until = max(self._plays_until, self._clock()) + len(piece) / bytes_per_second
            await self._send_audio(piece)
            delay = self._plays_until - self._lead - self._clock()
            if delay > 0:
                await self._sleep(delay)
