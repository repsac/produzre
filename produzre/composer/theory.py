"""Pitch and meter helpers shared by the composer.

Everything here is a pure function of key, mode, numeral, and beat. The
composer reuses the shared numeral spelling (``harmony.spelling``) so its
chord tones agree with bass, guitars, and themes.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from ..harmony.spelling import _KEY_PCS, _MODE_OFFSETS, _normalize_key
from ..melody import chord_pitch_classes

_MINORISH = {"minor", "aeolian", "dorian", "phrygian", "locrian"}


def tonic_pc(key: str) -> int:
    return _KEY_PCS.get(_normalize_key(key), 0)


def mode_offsets(mode: str) -> Tuple[int, ...]:
    return _MODE_OFFSETS.get(str(mode or "major").strip().lower(), _MODE_OFFSETS["major"])


def is_minorish(mode: str) -> bool:
    return str(mode or "").strip().lower() in _MINORISH


def scale_pcs(key: str, mode: str) -> Tuple[int, ...]:
    t = tonic_pc(key)
    return tuple((t + o) % 12 for o in mode_offsets(mode))


def pentatonic_pcs(key: str, mode: str) -> Tuple[int, ...]:
    """Minor pentatonic for minor-family modes, major pentatonic otherwise."""
    t = tonic_pc(key)
    offs = (0, 3, 5, 7, 10) if is_minorish(mode) else (0, 2, 4, 7, 9)
    return tuple((t + o) % 12 for o in offs)


def pitches_in(pcs: Sequence[int], lo: int, hi: int) -> List[int]:
    pcset = set(p % 12 for p in pcs)
    return [p for p in range(lo, hi + 1) if p % 12 in pcset]


def nearest_in(pcs: Sequence[int], target: float, lo: int, hi: int) -> int:
    cands = pitches_in(pcs, lo, hi)
    if not cands:
        return int(max(lo, min(hi, round(target))))
    return min(cands, key=lambda p: (abs(p - target), p))


def metric_weight(beat_in_bar: float, beats_per_bar: float) -> float:
    """Metric accent of a position: 1.0 downbeat down to 0.1 for 16ths."""
    b = round(beat_in_bar * 4) / 4
    if abs(b) < 1e-6:
        return 1.0
    half = beats_per_bar / 2.0
    if beats_per_bar >= 4 and abs(b - half) < 1e-6 and float(half).is_integer():
        return 0.75
    if abs(b - round(b)) < 1e-6:
        return 0.55
    if abs(b * 2 - round(b * 2)) < 1e-6:
        return 0.3
    return 0.12


@dataclass(frozen=True)
class ChordSpan:
    start: float
    end: float
    numeral: str
    pcs: Tuple[int, ...]
    root_pc: int


class ChordMap:
    """Section-relative lookup of the active chord for any beat."""

    def __init__(self, chord_slots: Sequence, key: str, mode: str):
        spans: List[ChordSpan] = []
        for slot in chord_slots or []:
            pcs = tuple(chord_pitch_classes(slot.numeral, key, mode))
            spans.append(ChordSpan(float(slot.start_beat), float(slot.end_beat),
                                   str(slot.numeral), pcs, pcs[0] if pcs else tonic_pc(key)))
        self.spans = spans
        self._starts = [s.start for s in spans]
        self.key = key
        self.mode = mode
        self.total = spans[-1].end if spans else 0.0

    def at(self, beat: float) -> Optional[ChordSpan]:
        if not self.spans:
            return None
        i = bisect_right(self._starts, beat + 1e-6) - 1
        i = max(0, min(i, len(self.spans) - 1))
        return self.spans[i]

    def signature(self) -> Tuple[Tuple[float, float, str], ...]:
        return tuple((s.start, s.end, s.numeral) for s in self.spans)


def diatonic_index(pitch: int, key: str, mode: str) -> float:
    """Position of a pitch on the diatonic ladder (fractional if chromatic)."""
    t = tonic_pc(key)
    offs = mode_offsets(mode)
    octave, pc = divmod(pitch - t, 12)
    for i, o in enumerate(offs):
        if o == pc:
            return octave * 7 + i
    for i, o in enumerate(offs):
        if o > pc:
            return octave * 7 + i - 0.5
    return octave * 7 + 6.5


def diatonic_pitch(index: int, key: str, mode: str, base_octave_pitch: int) -> int:
    """Pitch of a diatonic ladder index; index 0 is the tonic at base."""
    offs = mode_offsets(mode)
    octave, deg = divmod(int(index), 7)
    return base_octave_pitch + 12 * octave + offs[deg]


def tonic_base(key: str, near: int) -> int:
    """The tonic pitch at or below ``near``."""
    t = tonic_pc(key)
    return near - ((near - t) % 12)
