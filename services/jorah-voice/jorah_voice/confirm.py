"""Pure decision logic for voice confirmation of approval cards (ADR 0010)."""

from dataclasses import dataclass
import re
import unicodedata

CONFIRM_WINDOW_SECONDS = 20.0
MIN_CONFIRM_SPEECH_SECONDS = 1.5
MAX_RETRIES = 2

ALLOWED_LINE = "Done."
DENIED_LINE = "Okay, I won't."
GIVE_UP_LINE = "I'll leave it on the HUD for you to tap."
PHRASE_MISSING_LINE = "I need your phrase for this one. Tap it in the HUD."
LOCKED_LINE = "Voice confirmation is paused. Tap it in the HUD."
UNAVAILABLE_LINE = "I can't check voices right now, so please tap it."

RETRY_LINES = (
    "Sorry, I didn't quite catch that. Could you say 'yes, go ahead'?",
    "I want to be sure it's you. Say 'yes, confirm' for me?",
    "Once more, a little slower: 'yes, go ahead'.",
    "I couldn't tell that was you. Try again, or tap it in the HUD.",
)

PHRASE_RETRY_LINES = (
    "I need your phrase with that one. Say yes and your phrase.",
    "Almost: add your phrase after the yes.",
    "Don't forget your phrase with the yes, or tap it in the HUD.",
    "I still need your phrase for that. Say yes with your phrase, or tap it.",
)

_NO_PATTERNS = (
    r"\bno\b",
    r"\bnope\b",
    r"\bdon'?t\b",
    r"\bdo not\b",
    r"\bdeny\b",
    r"\bcancel\b",
    r"\bstop\b",
    r"\bnot now\b",
    r"\bnie\b",
    r"\bzru[sš]\b",
)

_YES_PATTERNS = (
    r"\byes\b",
    r"\byeah\b",
    r"\byep\b",
    r"\bconfirmed?\b",
    r"\bgo ahead\b",
    r"\bdo it\b",
    r"\ballow it\b",
    r"\bsure\b",
    r"\bapprove\b",
    r"\b[aá]no\b",
    r"\bpotvr[dď]\b",
    r"\bpokra[cč]uj\b",
)

_NON_ANSWER_EXCLUSIONS = (
    r"\b(?:make|are you|not) sure\b",
    r"\bhow (?:do|can|to) i do it\b",
    r"\bwhat should i do\b",
)

_NO_RE = re.compile("|".join(_NO_PATTERNS))
_YES_RE = re.compile("|".join(_YES_PATTERNS))
_EXCLUSION_RE = re.compile("|".join(_NON_ANSWER_EXCLUSIONS))


def is_leaving_pc(severity):
    """Treat any severity other than 'warning' or 'info' as leaving the PC (fail closed)."""
    return severity not in ("warning", "info")


def _clean_for_match(text):
    norm = unicodedata.normalize("NFKC", str(text or "")).lower()
    # Keep apostrophes inside contractions ("don't") while turning other punctuation into spaces.
    cleaned = re.sub(r"[^\w\s']", " ", norm)
    return re.sub(r"\s+", " ", cleaned).strip()


def classify_answer(transcript):
    """Return 'deny', 'allow', or 'none' for a spoken turn while a card is pending.

    'No' always wins over 'yes' in the same turn.
    """
    text = _clean_for_match(transcript)
    if not text:
        return "none"
    if _NO_RE.search(text):
        return "deny"
    stripped = _EXCLUSION_RE.sub(" ", text)
    if _YES_RE.search(stripped):
        return "allow"
    return "none"


@dataclass(frozen=True)
class ConfirmResult:
    outcome: str  # "allow", "deny", "retry", "give_up", "not_an_answer"
    line: str
    phrase_failed: bool = False


def decide(
    *,
    leaves_pc,
    seconds_since_asked,
    transcript,
    verdict_kind,
    speech_seconds,
    phrase_set,
    phrase_matches,
    phrase_locked,
    attempts,
    retry_index=None,
):
    """Decide what a spoken turn does to a pending approval card."""
    intent = classify_answer(transcript)
    if intent == "deny":
        return ConfirmResult(outcome="deny", line=DENIED_LINE)
    if intent == "none" and not phrase_matches:
        return ConfirmResult(outcome="not_an_answer", line="")

    # Yes-like answer (explicit yes word, or the confirmation phrase itself).
    if seconds_since_asked > CONFIRM_WINDOW_SECONDS:
        return ConfirmResult(outcome="give_up", line=GIVE_UP_LINE)
    if phrase_locked:
        return ConfirmResult(outcome="give_up", line=LOCKED_LINE)
    if verdict_kind == "unavailable":
        return ConfirmResult(outcome="give_up", line=UNAVAILABLE_LINE)
    if leaves_pc and not phrase_set:
        return ConfirmResult(outcome="give_up", line=PHRASE_MISSING_LINE)

    speaker_ok = verdict_kind == "adam" and float(speech_seconds) >= MIN_CONFIRM_SPEECH_SECONDS
    if not speaker_ok:
        if attempts >= MAX_RETRIES:
            return ConfirmResult(outcome="give_up", line=GIVE_UP_LINE)
        idx = attempts if retry_index is None else retry_index
        return ConfirmResult(outcome="retry", line=RETRY_LINES[idx % len(RETRY_LINES)])

    if leaves_pc and not phrase_matches:
        if attempts >= MAX_RETRIES:
            return ConfirmResult(outcome="give_up", line=GIVE_UP_LINE, phrase_failed=True)
        idx = attempts if retry_index is None else retry_index
        return ConfirmResult(outcome="retry", line=PHRASE_RETRY_LINES[idx % len(PHRASE_RETRY_LINES)], phrase_failed=True)

    return ConfirmResult(outcome="allow", line=ALLOWED_LINE)
