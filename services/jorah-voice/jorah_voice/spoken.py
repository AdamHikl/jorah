"""Rewrite text so Kokoro says all of it. Kokoro silently drops any word missing from its word list."""

import os
import re
import unicodedata

ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
        "fifteen sixteen seventeen eighteen nineteen").split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
ORDINALS = {"one": "first", "two": "second", "three": "third", "five": "fifth", "eight": "eighth",
            "nine": "ninth", "twelve": "twelfth"}
CONTRACTIONS = {"what's": "what is", "who's": "who is", "where's": "where is", "how's": "how is",
                "when's": "when is", "why's": "why is", "there's": "there is", "here's": "here is",
                "that's": "that is"}

_TIME = re.compile(r"(?<![\d:])(\d{1,2}):([0-5]\d)(?![\d:])")
_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s?%")
_MONEY = re.compile(r"([$€£])\s?(\d+(?:\.\d+)?)")
_ORDINAL = re.compile(r"(\d+)(?:st|nd|rd|th)\b", re.IGNORECASE)
_DECIMAL = re.compile(r"(\d+)\.(\d+)")
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}\b)")
_NUMBER = re.compile(r"\d+")
_JOINER = re.compile(r"(?<=\w)[-/_](?=\w)")
_HYPHENATED = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)+")
_WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)*")
_CASE_CHANGE = re.compile(r"(?<=[a-z])(?=[A-Z])")
_MONEY_NAMES = {"$": "dollars", "€": "euros", "£": "pounds"}
_ENDINGS = {"'ll": "will", "'re": "are", "'ve": "have", "'d": "would"}
_VOICELESS = {"p", "t", "k", "f", "θ"}
_SIBILANT = {"s", "z", "ʃ", "ʒ", "ʧ", "ʤ"}
_VOWELS = "aeiou"


def number_words(value):
    """Say a whole number. Very long ones are read digit by digit, like a phone number."""
    if value >= 10**9:
        return " ".join(ONES[int(digit)] for digit in str(value))
    if value < 20:
        return ONES[value]
    if value < 100:
        return TENS[value // 10] + (f" {ONES[value % 10]}" if value % 10 else "")
    if value < 1000:
        rest = f" {number_words(value % 100)}" if value % 100 else ""
        return f"{ONES[value // 100]} hundred{rest}"
    for size, name in ((10**6, "million"), (1000, "thousand")):
        if value >= size:
            rest = f" {number_words(value % size)}" if value % size else ""
            return f"{number_words(value // size)} {name}{rest}"
    raise AssertionError(value)


def _ordinal(value):
    words = number_words(value).split()
    last = words[-1]
    if last in ORDINALS:
        words[-1] = ORDINALS[last]
    elif last.endswith("y"):
        words[-1] = last[:-1] + "ieth"
    else:
        words[-1] = last + "th"
    return " ".join(words)


def _decimal(whole, fraction):
    return f"{number_words(int(whole))} point {' '.join(ONES[int(d)] for d in fraction)}"


def _clock(match):
    hour, minute = int(match[1]), int(match[2])
    if minute == 0:
        return f"{number_words(hour)} hundred" if hour > 12 else number_words(hour)
    minutes = number_words(minute) if minute >= 10 else f"oh {number_words(minute)}"
    return f"{number_words(hour)} {minutes}"


def _amount(text):
    return _decimal(*text.split(".")) if "." in text else number_words(int(text))


def say_numbers(text):
    text = _TIME.sub(_clock, text)
    text = _THOUSANDS.sub("", text)
    text = _PERCENT.sub(lambda m: f"{_amount(m[1])} percent", text)
    text = _MONEY.sub(lambda m: f"{_amount(m[2])} {_MONEY_NAMES[m[1]]}", text)
    text = _ORDINAL.sub(lambda m: f" {_ordinal(int(m[1]))} ", text)
    text = _DECIMAL.sub(lambda m: f" {_decimal(m[1], m[2])} ", text)
    return _NUMBER.sub(lambda m: f" {number_words(int(m[0]))} ", text)


def _split_known(word, known):
    """Split a word into the fewest known pieces of three or more letters, as "tail scale"."""
    lower = word.lower()
    best = {0: []}
    for end in range(3, len(lower) + 1):
        options = [best[start] + [lower[start:end]] for start in range(end - 2)
                   if start in best and lower[start:end] in known]
        if options:
            best[end] = min(options, key=len)
    found = best.get(len(lower))
    return found if found and len(found) <= 3 else None


def _spell(word, known):
    return " ".join(letter for letter in word if letter.lower() in known)


def say_word(word, known):
    """Return something Kokoro can say for one word."""
    lower = word.lower()
    if lower in known:
        return word
    if lower in CONTRACTIONS:
        return CONTRACTIONS[lower]
    for ending, full in _ENDINGS.items():
        if lower.endswith(ending):
            return f"{say_word(word[:-len(ending)], known)} {full}"
    if lower.endswith("'s"):
        said = say_word(word[:-2], known).split()
        plural = said[-1].lower() + "s" if said else ""
        return " ".join(said[:-1] + [plural]) if plural in known else " ".join(said + ["s"])
    if "'" in word:
        return say_word(word.replace("'", ""), known)
    plain = "".join(c for c in unicodedata.normalize("NFKD", word) if not unicodedata.combining(c))
    if plain != word:
        return say_word(plain, known)
    if word.isupper():
        return _spell(word, known)
    pieces = _CASE_CHANGE.split(word)
    if len(pieces) > 1:
        return " ".join(say_word(piece, known) for piece in pieces)
    found = _split_known(word, known)
    return " ".join(found) if found else _spell(word.upper(), known)


def rewrite(text, known):
    text = text.replace("’", "'").replace("&", " and ").replace("+", " plus ").replace("@", " at ")
    text = _HYPHENATED.sub(lambda m: m[0].replace("-", "") if m[0].replace("-", "").lower() in known else m[0], text)
    text = _JOINER.sub(" ", say_numbers(text))
    text = _WORD.sub(lambda m: say_word(m[0], known), text)
    return re.sub(r"\s+([.,!?;:])", r"\1", re.sub(r"\s+", " ", text)).strip()


def inflected(word, phonemes):
    """The -s and -ed forms of a word with their sounds. Kokoro's list lacks many, like "opened"."""
    last = phonemes[-1]
    ends_in_y = word.endswith("y") and word[-2] not in _VOWELS
    plural = word[:-1] + "ies" if ends_in_y else word + ("es" if word.endswith(("s", "x", "z", "ch", "sh")) else "s")
    past = word[:-1] + "ied" if ends_in_y else word + ("d" if word.endswith("e") else "ed")
    if last in _SIBILANT:
        plural_sound = ["ᵻ", "z"]
    else:
        plural_sound = ["s"] if last in _VOICELESS else ["z"]
    if last in ("t", "d"):
        past_sound = ["ᵻ", "d"]
    else:
        past_sound = ["t"] if last in _VOICELESS | {"s", "ʃ", "ʧ"} else ["d"]
    return [(plural, phonemes + plural_sound), (past, phonemes + past_sound)]


def write_inflections(lexicon, target):
    """Write the forms missing from a word list, once. Sounds are built from each base word's own."""
    if os.path.exists(target):
        return target
    entries = {}
    with open(lexicon, encoding="utf-8") as handle:
        for line in handle:
            parts = line.split()
            if len(parts) >= 2:
                entries.setdefault(parts[0].lower(), parts[1:])
    extra = {}
    for word, phonemes in entries.items():
        if len(word) >= 3 and word.isalpha() and word.isascii():
            for form, sound in inflected(word, phonemes):
                if form not in entries:
                    extra.setdefault(form, sound)
    partial = f"{target}.part"
    with open(partial, "w", encoding="utf-8") as handle:
        for form, sound in extra.items():
            handle.write(f"{form} {' '.join(sound)}\n")
    os.replace(partial, target)
    return target


def load_words(*paths):
    words = set()
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            words.update(line.split(maxsplit=1)[0].lower() for line in handle if line.strip())
    return words
