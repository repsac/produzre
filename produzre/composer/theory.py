"""Pitch and meter helpers shared by the composer.

Everything here is a pure function of key, mode, numeral, and beat. The
composer reuses the shared numeral spelling (``harmony.spelling``) so its
chord tones agree with bass, guitars, and themes.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from typing import Any, List, Optional, Sequence, Tuple

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


def _split_twos_threes(n: int) -> List[int]:
    """Split n pulses into 2s and 3s, threes last (7 -> 2+2+3, 5 -> 2+3)."""
    if n <= 3:
        return [n]
    threes = 0
    while (n - 3 * threes) % 2:
        threes += 1
    return [2] * ((n - 3 * threes) // 2) + [3] * threes


def default_groups(beats_per_bar: float) -> Tuple[float, ...]:
    """Beat grouping implied by a bar length alone (quarter-note beats).

    Whole-beat bars group in quarters (4 -> 2+2, 5 -> 3+2, 3 -> 1+1+1); bars
    with a half beat are eighth-note meters grouped in 2s and 3s
    (3.5 -> 2+2+3 eighths). Meters the bar length cannot tell apart (6/8 vs
    3/4) need ``meter_groups`` with the time signature.
    """
    bpb = float(beats_per_bar)
    if bpb <= 0:
        return (1.0,)
    if abs(bpb - round(bpb)) < 1e-6:
        n = int(round(bpb))
        if n <= 3:
            return tuple([1.0] * n)
        if n == 4:
            return (2.0, 2.0)
        if n == 5:
            return (3.0, 2.0)
        return tuple(float(g) for g in _split_twos_threes(n))
    eighths = int(round(bpb * 2))
    return tuple(g / 2.0 for g in _split_twos_threes(eighths))


def parse_grouping(text: Any, denominator: int) -> Optional[Tuple[float, ...]]:
    """``"2+2+3"`` (in the meter's denominator units) -> quarter-beat groups."""
    if text is None:
        return None
    parts = text if isinstance(text, (list, tuple)) else str(text).replace(",", "+").split("+")
    try:
        units = [float(p) for p in parts if str(p).strip()]
    except (TypeError, ValueError):
        return None
    if not units or any(u <= 0 for u in units):
        return None
    scale = 4.0 / float(denominator or 4)
    return tuple(u * scale for u in units)


def meter_groups(numerator: int, denominator: int, override: Any = None) -> Tuple[float, ...]:
    """Groups for a time signature: compound meters pulse in dotted quarters."""
    bpb = float(numerator) * 4.0 / float(denominator or 4)
    custom = parse_grouping(override, denominator)
    if custom is not None and abs(sum(custom) - bpb) < 1e-6:
        return custom
    if int(denominator) == 8 and int(numerator) % 3 == 0:
        return tuple([1.5] * (int(numerator) // 3))
    return default_groups(bpb)


def metric_weight(beat_in_bar: float, beats_per_bar: float,
                  groups: Optional[Sequence[float]] = None) -> float:
    """Metric accent of a position: 1.0 downbeat down to 0.12 for 16ths.

    Group starts are strong (0.75 for groups of 1.5 beats or more). In
    eighth-note meters the eighths inside a group are weak even when they
    fall on a quarter-note beat, so 6/8 accents 1 and 4, not 1, 2 and 3.
    4/4 (2+2), 3/4 and 2/4 weigh exactly as simple meters always have.
    """
    b = round(beat_in_bar * 4) / 4
    if abs(b) < 1e-6:
        return 1.0
    gs = tuple(groups) if groups else default_groups(beats_per_bar)
    t = 0.0
    for i in range(1, len(gs)):
        t += gs[i - 1]
        if abs(b - t) < 1e-6:
            # A group of a beat and a half or more is a real pulse (the "4"
            # of 6/8, the "+2" of 5/4, the half bar of 4/4).
            return 0.75 if gs[i] >= 1.5 else 0.55
    eighth_meter = any(abs(g - round(g)) > 1e-6 for g in gs)
    if not eighth_meter and abs(b - round(b)) < 1e-6:
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
