"""Turns one health upload into one row for the day, by fixed rules (docs/contracts/jorah-phone-v1.md).

No sample is kept: the caller stores only what summarize() returns. Missing data stays None,
never zero.
"""

from datetime import datetime, time, timedelta
from statistics import median

from .schema import parse_date_time

WORKOUT_TYPES = ("walking", "running", "cycling", "strength", "swimming", "hiking", "yoga", "hiit", "other")
# Health's workout names, English and Slovak, by substring of the lower-cased name. First match wins.
WORKOUT_WORDS = (
    ("hiit", ("hiit", "high intensity", "intervalov")),
    ("walking", ("walk", "chôdz", "chodz", "prechádz", "prechadz")),
    ("running", ("run", "jog", "beh")),
    ("cycling", ("cycl", "bike", "bicyk", "cyklist")),
    ("strength", ("strength", "weight", "functional", "posil", "silov")),
    ("swimming", ("swim", "pláv", "plav")),
    ("hiking", ("hik", "turist")),
    ("yoga", ("yoga", "joga", "jóga")),
)


def workout_type(name):
    lowered = str(name).lower()
    for kind, words in WORKOUT_WORDS:
        if any(word in lowered for word in words):
            return kind
    return "other"


def _intervals(items, start_key="start", end_key="end"):
    out = []
    for item in items:
        start, end = parse_date_time(item.get(start_key)), parse_date_time(item.get(end_key))
        if start is not None and end is not None and end > start:
            out.append((start, end))
    return out


def _merge(intervals):
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            if end > merged[-1][1]:
                merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return merged


def summarize(payload, tz):
    """Return {day, bed, wake, asleep_min, hrv_ms, resting_bpm, workouts} for a validated upload."""
    sent = parse_date_time(payload["sent_at"])
    day = sent.astimezone(tz).date()
    window_start = datetime.combine(day - timedelta(days=1), time(18, 0), tzinfo=tz)
    window_end = datetime.combine(day, time(14, 0), tzinfo=tz)

    night = _merge([(s, e) for s, e in _intervals(payload.get("sleep", [])) if window_start <= e <= window_end])
    bed = wake = asleep_min = None
    if night:
        bed, wake = night[0][0], night[-1][1]
        asleep_min = min(1440, round(sum((e - s).total_seconds() for s, e in night) / 60))

    hrv_from, hrv_to = (bed - timedelta(hours=1), wake + timedelta(hours=1)) if night else (sent - timedelta(hours=24), sent)
    hrv_values = [h["ms"] for h in payload.get("hrv", []) if (at := parse_date_time(h["at"])) is not None and hrv_from <= at <= hrv_to]
    hrv_ms = min(400, max(1, round(median(hrv_values)))) if hrv_values else None

    resting = [(at, r["bpm"]) for r in payload.get("resting_hr", [])
               if (at := parse_date_time(r["at"])) is not None and sent - timedelta(hours=36) <= at <= sent + timedelta(minutes=5)]
    resting_bpm = min(250, max(20, round(max(resting)[1]))) if resting else None

    workouts = []
    for item in payload.get("workouts", []):
        start, end = parse_date_time(item["start"]), parse_date_time(item["end"])
        if start is None or end is None or end <= start or start.astimezone(tz).date() != day:
            continue
        workouts.append({"type": workout_type(item["type"]), "minutes": min(1440, round((end - start).total_seconds() / 60))})

    return {
        "day": day.isoformat(),
        "bed": bed.astimezone(tz).isoformat(timespec="seconds") if bed else None,
        "wake": wake.astimezone(tz).isoformat(timespec="seconds") if wake else None,
        "asleep_min": asleep_min,
        "hrv_ms": hrv_ms,
        "resting_bpm": resting_bpm,
        "workouts": workouts[:30],
    }
