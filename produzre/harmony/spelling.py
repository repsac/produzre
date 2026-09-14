"""Shared key-relative Roman numeral spelling for every pitched engine."""
import re

_KEY_PCS = {
    "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3,
    "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8,
    "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11,
}
_MODE_OFFSETS = {
    "ionian": (0, 2, 4, 5, 7, 9, 11),
    "major": (0, 2, 4, 5, 7, 9, 11),
    "dorian": (0, 2, 3, 5, 7, 9, 10),
    "phrygian": (0, 1, 3, 5, 7, 8, 10),
    "lydian": (0, 2, 4, 6, 7, 9, 11),
    "mixolydian": (0, 2, 4, 5, 7, 9, 10),
    "aeolian": (0, 2, 3, 5, 7, 8, 10),
    "minor": (0, 2, 3, 5, 7, 8, 10),
    "locrian": (0, 1, 3, 5, 6, 8, 10),
}
_ROMAN_DEGREES = {"I": 0, "II": 1, "III": 2, "IV": 3, "V": 4, "VI": 5, "VII": 6}


def _parse_numeral(numeral: str) -> tuple[int, int, str, str]:
    raw = str(numeral or "I").strip()
    match = re.match(r"^([b#]*)([ivIV]+)(.*)$", raw)
    if not match:
        return 0, 0, "I", ""
    accidental, roman, suffix = match.groups()
    return (
        _ROMAN_DEGREES.get(roman.upper(), 0),
        accidental.count("#") - accidental.count("b"),
        roman,
        suffix.lower(),
    )


def _normalize_key(key: str) -> str:
    raw = str(key or "C").strip().replace("♭", "b").replace("♯", "#")
    return raw[:1].upper() + raw[1:].lower() if raw else "C"


def root_offset(numeral: str, mode: str) -> int:
    degree, accidental, _, _ = _parse_numeral(numeral)
    scale = _MODE_OFFSETS.get(str(mode or "major").lower(), _MODE_OFFSETS["major"])
    if accidental:
        scale = _MODE_OFFSETS["major"]
    return scale[degree] + accidental


def chord_intervals(numeral: str) -> tuple[int, ...]:
    _, _, roman, suffix = _parse_numeral(numeral)
    half_dim = "ø" in suffix
    diminished = half_dim or any(s in suffix for s in ("dim", "o", "°"))
    third = (2 if "sus2" in suffix else 5) if "sus" in suffix else (3 if diminished or roman.islower() else 4)
    fifth = 6 if diminished else (8 if "aug" in suffix or "+" in suffix else 7)
    result = (0, third, fifth)
    if "7" in suffix or half_dim:
        seventh = 11 if "maj7" in suffix else (9 if diminished and not half_dim else 10)
        result += (seventh,)
    return result
