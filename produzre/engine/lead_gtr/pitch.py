"""Harmony-driven pitch selection for lead guitar (Phase LG1).

Constructs per-chord-slot pitch pools with chord tones prioritised
and scale-tone neighbours for safe passing motion.  Provides stepwise
pitch selection with configurable leap limits.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple

from .defaults import REGISTER_RANGES, DEFAULT_REGISTER


# Mode scale intervals (semitones from tonic)
_MODE_INTERVALS: Dict[str, List[int]] = {
    "major":      [0, 2, 4, 5, 7, 9, 11],
    "minor":      [0, 2, 3, 5, 7, 8, 10],
    "dorian":     [0, 2, 3, 5, 7, 9, 10],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "lydian":     [0, 2, 4, 6, 7, 9, 11],
    "phrygian":   [0, 1, 3, 5, 7, 8, 10],
    "locrian":    [0, 1, 3, 5, 6, 8, 10],
}

_KEY_TO_MIDI: Dict[str, int] = {
    "C": 60, "C#": 61, "Db": 61,
    "D": 62, "D#": 63, "Eb": 63,
    "E": 64, "F": 65,
    "F#": 66, "Gb": 66,
    "G": 67, "G#": 68, "Ab": 68,
    "A": 69, "A#": 70, "Bb": 70,
    "B": 71,
}


@dataclass(frozen=True)
class PitchPool:
    """Allowed pitches for a chord slot, tiered by priority.

    chord_tones: Triad tones within register (highest selection weight)
    scale_tones: Safe mode-scale neighbours suitable for passing motion
    """

    chord_tones: Tuple[int, ...]
    scale_tones: Tuple[int, ...]

    @property
    def all_tones(self) -> List[int]:
        """All pitches, chord tones first (deduped, order preserved)."""
        seen: set = set()
        result: List[int] = []
        for p in (*self.chord_tones, *self.scale_tones):
            if p not in seen:
                seen.add(p)
                result.append(p)
        return result


def _resolve_key_midi(key: str) -> int:
    """Resolve key string to MIDI root note number."""
    k = (key or "C").strip().replace("\u266d", "b").replace("\u266f", "#")
    return _KEY_TO_MIDI.get(k, 60)


def _parse_numeral(numeral: str) -> Tuple[int, int, bool, bool]:
    """Parse roman numeral to (degree_0based, accidental, is_minor, is_dim).

    Examples:
        "i"    -> (0, 0, True, False)
        "bVII" -> (6, -1, False, False)
        "iv"   -> (3, 0, True, False)
    """
    n = (numeral or "i").strip()

    # Accidental prefix
    acc = 0
    if n.startswith(("b", "\u266d")):
        acc = -1
        n = n[1:]
    elif n.startswith(("#", "\u266f")):
        acc = 1
        n = n[1:]

    n_lower = n.lower()
    is_dim = "dim" in n_lower or ("o" in n_lower and "do" not in n_lower)

    # First alpha char determines major/minor
    is_minor = False
    for ch in n:
        if ch.isalpha():
            is_minor = ch.islower()
            break

    # Strip suffixes for degree lookup
    clean = n_lower
    for suf in ("dim", "aug", "sus4", "sus2", "maj7", "7", "+", "o"):
        clean = clean.replace(suf, "")

    degree_map = {"i": 0, "ii": 1, "iii": 2, "iv": 3, "v": 4, "vi": 5, "vii": 6}
    degree = degree_map.get(clean, 0)

    return degree, acc, is_minor, is_dim


def _triad_semitones(is_minor: bool, is_dim: bool) -> List[int]:
    """Return [0, third, fifth] semitone offsets for triad quality."""
    if is_dim:
        return [0, 3, 6]
    if is_minor:
        return [0, 3, 7]
    return [0, 4, 7]


def allowed_pitches_for_slot(
    numeral: str,
    key: str,
    mode: str,
    register: str = "mid",
) -> PitchPool:
    """Build pitch pool for a chord slot: chord tones + safe scale neighbours.

    Chord tones (triad) span the register at multiple octaves.
    Scale tones fill in mode-scale pitches that are *not* chord tones,
    providing safe passing-tone options that stay diatonic.

    Args:
        numeral: Chord numeral (e.g. "i", "bVII", "IV")
        key: Song key string (e.g. "E")
        mode: Scale mode (e.g. "minor", "major")
        register: Register name matching REGISTER_RANGES

    Returns:
        PitchPool with prioritised chord_tones and scale_tones
    """
    low, high = REGISTER_RANGES.get(register, REGISTER_RANGES[DEFAULT_REGISTER])
    tonic = _resolve_key_midi(key)
    intervals = _MODE_INTERVALS.get((mode or "minor").lower(), _MODE_INTERVALS["minor"])

    degree, acc, is_minor, is_dim = _parse_numeral(numeral)
    degree = max(0, min(degree, len(intervals) - 1))
    chord_root = tonic + intervals[degree] + acc

    # Shift root into register
    while chord_root < low:
        chord_root += 12
    while chord_root > high:
        chord_root -= 12

    # Chord tones across register
    triad = _triad_semitones(is_minor, is_dim)
    ct: List[int] = []
    for octave in (-1, 0, 1):
        for semi in triad:
            p = chord_root + octave * 12 + semi
            if low <= p <= high:
                ct.append(p)
    chord_tones = sorted(set(ct))

    # Scale tones in register (excluding chord tones)
    ct_set = set(chord_tones)
    st: List[int] = []
    for octave_off in range(-24, 25, 12):
        for semi in intervals:
            p = tonic + octave_off + semi
            if low <= p <= high and p not in ct_set:
                st.append(p)
    scale_tones = sorted(set(st))

    return PitchPool(chord_tones=tuple(chord_tones), scale_tones=tuple(scale_tones))


def choose_pitch(
    prev_pitch: Optional[int],
    pool: PitchPool,
    leap_limit: int = 7,
    rng: Optional[random.Random] = None,
) -> int:
    """Select a pitch favouring stepwise motion and chord tones.

    Strategy:
    - Restrict candidates to within *leap_limit* semitones of prev_pitch
    - Weight chord tones 3x over scale tones
    - Weight by inverse distance (closer = preferred)
    - Avoid unison unless unavoidable
    - First note (prev_pitch is None): pick middle chord tone

    Args:
        prev_pitch: Previous note (None for phrase start)
        pool: PitchPool from allowed_pitches_for_slot
        leap_limit: Max semitone interval from prev_pitch
        rng: Seeded Random for determinism

    Returns:
        Selected MIDI pitch
    """
    if rng is None:
        rng = random.Random()

    all_tones = pool.all_tones
    if not all_tones:
        return prev_pitch if prev_pitch is not None else 64

    if prev_pitch is None:
        # Phrase opener: pick chord tone nearest register centre
        tones = pool.chord_tones or tuple(all_tones)
        mid = (tones[0] + tones[-1]) / 2.0
        return min(tones, key=lambda p: (abs(p - mid), p))

    chord_set = set(pool.chord_tones)

    # Reachable within leap limit
    reachable = [p for p in all_tones if abs(p - prev_pitch) <= leap_limit]
    if not reachable:
        # Fallback: closest available pitch
        return min(all_tones, key=lambda p: abs(p - prev_pitch))

    # Score: stepwise preference * tone-tier weight
    scores: List[Tuple[float, int]] = []
    for p in reachable:
        dist = abs(p - prev_pitch)
        step_w = 1.0 / (dist + 0.5)
        tier_w = 3.0 if p in chord_set else 1.0
        unison_pen = 0.05 if (p == prev_pitch and len(reachable) > 1) else 1.0
        scores.append((step_w * tier_w * unison_pen, p))

    # Weighted random pick
    total = sum(s for s, _ in scores)
    roll = rng.random() * total
    cum = 0.0
    for score, pitch in scores:
        cum += score
        if roll <= cum:
            return pitch

    return scores[-1][1]
