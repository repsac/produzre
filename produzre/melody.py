from __future__ import annotations

"""Shared melodic intent for pitched instrument engines.

The planner deliberately stops short of emitting notes.  It supplies a small
set of voice-led targets that instrument engines can interpret as bends and
phrases (lead guitar), a moving top voice (fingerstyle), or an arpeggio apex.
"""

from dataclasses import asdict, dataclass
import math
import random
import re
from typing import Any, Iterable, Optional


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


@dataclass(frozen=True)
class MelodyTarget:
    beat: float
    pitch: int
    chord_index: int
    role: str
    phrase_index: int
    cadence: bool = False


@dataclass(frozen=True)
class MelodyGuide:
    section_id: str
    low: int
    high: int
    targets: tuple[MelodyTarget, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "section_id": self.section_id,
            "low": self.low,
            "high": self.high,
            "targets": [asdict(target) for target in self.targets],
        }


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


def chord_pitch_classes(numeral: str, key: str, mode: str) -> tuple[int, ...]:
    """Return pitch classes for a Roman-numeral chord, including common suffixes."""
    degree, accidental, roman, suffix = _parse_numeral(numeral)
    tonic = _KEY_PCS.get(_normalize_key(key), 0)
    scale = _MODE_OFFSETS.get(str(mode or "").lower(), _MODE_OFFSETS["major"])
    root = (tonic + scale[degree] + accidental) % 12
    diminished = "dim" in suffix or "o" in suffix or "°" in suffix
    suspended = "sus" in suffix
    third = 5 if "sus4" in suffix else (2 if suspended else (3 if roman.islower() else 4))
    fifth = 6 if diminished else 7
    pcs = [root, (root + third) % 12, (root + fifth) % 12]
    if "7" in suffix:
        pcs.append((root + (9 if diminished else 10)) % 12)
    return tuple(pcs)


def harmonic_function(numeral: str) -> str:
    degree, _, _, _ = _parse_numeral(numeral)
    if degree in (0, 2, 5):
        return "tonic"
    if degree in (1, 3):
        return "predominant"
    if degree in (4, 6):
        return "dominant"
    return "color"


def build_melody_guide(
    harmony_plan: Any,
    *,
    key: str,
    mode: str,
    section_type: str,
    genre: str,
    rng: random.Random,
    low: int = 62,
    high: int = 81,
) -> MelodyGuide:
    """Build two melodic landmarks per chord with a phrase-scale contour."""
    slots = list(getattr(harmony_plan, "chord_slots", []) or [])
    section_id = str(getattr(harmony_plan, "section_id", "") or "")
    if not slots:
        return MelodyGuide(section_id, low, high, ())

    section_name = str(section_type or "").lower()
    genre_name = str(genre or "").lower()
    phrase_size = 4 if len(slots) >= 4 else max(1, len(slots))
    center = (low + high) / 2.0
    span = min(7.0, (high - low) * 0.32)
    if section_name in {"chorus", "hook", "solo"}:
        center += 2.0
    if any(token in genre_name for token in ("cinematic", "ambient", "post-rock")):
        span += 1.5

    targets: list[MelodyTarget] = []
    previous: Optional[int] = None
    for index, slot in enumerate(slots):
        start = float(slot.start_beat)
        end = float(slot.end_beat)
        duration = max(0.0, end - start)
        pcs = chord_pitch_classes(slot.numeral, key, mode)
        phrase_index = index // phrase_size
        position = (index % phrase_size) / max(1, phrase_size - 1)
        arc = math.sin(math.pi * position)
        if phrase_index % 2:
            arc *= -0.65
        contour = center + span * arc + rng.uniform(-1.4, 1.4)

        # Prefer thirds/fifths internally; roots are strongest at cadences.
        roles = ("root", "third", "fifth", "seventh")
        role_index = 1 if index % 3 == 0 else 2
        first = _choose_pitch(pcs, contour, previous, low, high, role_index)
        targets.append(MelodyTarget(start, first, index, roles[role_index], phrase_index))
        previous = first

        is_phrase_end = ((index + 1) % phrase_size == 0) or index == len(slots) - 1
        late_beat = start + duration * (0.62 if duration >= 1.0 else 0.5)
        if late_beat > start + 0.05:
            late_role = 0 if is_phrase_end else (1 if index % 2 else 2)
            late_contour = center + span * math.sin(math.pi * min(1.0, position + 0.22))
            second = _choose_pitch(pcs, late_contour, previous, low, high, late_role)
            targets.append(MelodyTarget(
                late_beat, second, index, roles[late_role], phrase_index, is_phrase_end,
            ))
            previous = second

    return MelodyGuide(section_id, low, high, tuple(targets))


def guide_pitch_at(
    guide: Any,
    beat: float,
    low: int,
    high: int,
    *,
    previous: Optional[int] = None,
) -> Optional[int]:
    """Resolve the current guide landmark into an instrument register."""
    if not isinstance(guide, dict):
        return None
    targets = guide.get("targets")
    if not isinstance(targets, list) or not targets:
        return None
    target = min(targets, key=lambda item: abs(float(item.get("beat", 0.0)) - beat))
    try:
        pitch = int(target["pitch"])
    except (KeyError, TypeError, ValueError):
        return None
    return fit_pitch_to_range(pitch, low, high, previous=previous)


def fit_pitch_to_range(
    pitch: int, low: int, high: int, *, previous: Optional[int] = None,
) -> int:
    candidates = [p for p in range(low, high + 1) if p % 12 == pitch % 12]
    if not candidates:
        return max(low, min(high, pitch))
    reference = previous if previous is not None else pitch
    return min(candidates, key=lambda value: (abs(value - reference), abs(value - pitch)))


def _choose_pitch(
    pcs: Iterable[int], contour: float, previous: Optional[int], low: int, high: int,
    preferred_role: int,
) -> int:
    pcs = tuple(pcs)
    candidates = [p for p in range(low, high + 1) if p % 12 in pcs]
    def score(pitch: int) -> float:
        role = pcs.index(pitch % 12)
        movement = abs(pitch - previous) if previous is not None else 0.0
        leap_penalty = max(0.0, movement - 7.0) * 3.0
        repeat_penalty = 1.8 if previous == pitch else 0.0
        return abs(pitch - contour) + movement * 0.55 + leap_penalty + repeat_penalty + (0 if role == preferred_role else 1.6)
    return min(candidates, key=score)


def _normalize_key(key: str) -> str:
    raw = str(key or "C").strip().replace("♭", "b").replace("♯", "#")
    return raw[:1].upper() + raw[1:].lower() if raw else "C"
