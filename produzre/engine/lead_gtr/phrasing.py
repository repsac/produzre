"""Simple phrase generator for lead guitar (Phase LG2).

Provides motif-based melodic composition: short repeating ideas
with light variation for musical coherence without overwriting.

Section defaults (controlled via intensity passed in):
    Verse:   sparse motifs (2-note), generous rests
    Chorus:  standard motifs (4-note), moderate activity
    Bridge:  call-and-response phrasing (motif + space)
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .pitch import PitchPool, choose_pitch


@dataclass(frozen=True)
class Motif:
    """A short melodic shape expressed as interval steps from an anchor.

    intervals[0] is always 0 (the anchor pitch itself).
    Subsequent values are semitone offsets relative to that anchor.
    durations gives the suggested note length in beats for each interval.
    """

    intervals: Tuple[int, ...]
    durations: Tuple[float, ...]


@dataclass(frozen=True)
class ResolvedNote:
    """A concrete note produced by realizing a motif against harmony."""

    pitch: int
    beat_offset: float  # Beats from phrase start
    duration: float     # Note duration in beats


# --- Interval shape libraries ---

_SHAPES_SPARSE: List[Tuple[int, ...]] = [
    (0, 2),       # step up
    (0, -2),      # step down
    (0, 3),       # small leap up
    (0, 5),       # fourth up
    (0, -3),      # small leap down
]

_SHAPES_STANDARD: List[Tuple[int, ...]] = [
    (0, 2, 3, 2),     # up and back
    (0, -1, 2, 0),    # neighbor motion
    (0, 3, 2, -1),    # leap and descend
    (0, 2, -1, 1),    # zigzag
    (0, -2, 1, 3),    # down then up
    (0, 5, 3, 2),     # wider arc
]

_SHAPES_ACTIVE: List[Tuple[int, ...]] = [
    (0, 2, 3, 5, 3, 2),     # ascending arc
    (0, -1, 2, -2, 1, 0),   # oscillating resolve
    (0, 3, 2, 5, 3, 0),     # leap and settle
    (0, 2, -1, 3, 1, -2),   # varied direction
]

# --- Rhythm templates (durations in beats) ---

_RHYTHM_2_HALF = (2.0, 2.0)
_RHYTHM_2_LONG = (1.5, 2.5)
_RHYTHM_4_QUARTER = (1.0, 1.0, 1.0, 1.0)
_RHYTHM_4_SYNCOPATED = (0.5, 1.5, 0.5, 1.5)
_RHYTHM_6_EIGHTH = (0.5, 0.5, 1.0, 0.5, 0.5, 1.0)
_RHYTHM_6_MIXED = (1.0, 0.5, 0.5, 1.0, 0.5, 0.5)


def make_motif(rng: random.Random, intensity: float) -> Motif:
    """Generate a short melodic motif scaled to intensity.

    intensity < 0.4  -> sparse: 2-note motifs, longer durations
    intensity 0.4-0.7 -> standard: 4-note, quarter-note feel
    intensity > 0.7  -> active: 4-6 note, mixed rhythms

    Args:
        rng: Seeded Random for determinism
        intensity: 0.0-1.0 activity level

    Returns:
        Motif with matched intervals and durations
    """
    if intensity < 0.4:
        shape = _SHAPES_SPARSE[rng.randrange(len(_SHAPES_SPARSE))]
        rhythm = _RHYTHM_2_LONG if rng.random() < 0.4 else _RHYTHM_2_HALF
    elif intensity < 0.7:
        shape = _SHAPES_STANDARD[rng.randrange(len(_SHAPES_STANDARD))]
        rhythm = _RHYTHM_4_SYNCOPATED if rng.random() < 0.3 else _RHYTHM_4_QUARTER
    else:
        shape = _SHAPES_ACTIVE[rng.randrange(len(_SHAPES_ACTIVE))]
        rhythm = _RHYTHM_6_MIXED if rng.random() < 0.4 else _RHYTHM_6_EIGHTH

    # Trim rhythm to match shape length
    n = len(shape)
    rhythm = rhythm[:n] if len(rhythm) >= n else rhythm + (1.0,) * (n - len(rhythm))

    return Motif(intervals=tuple(shape), durations=tuple(rhythm))


def develop_motif(
    motif: Motif,
    rng: random.Random,
    *,
    phrase_index: int,
    is_final_phrase: bool = False,
    intensity: float = 0.5,
    total_phrases: int = 4,
) -> Motif:
    """Create a related motif variation for later phrases.

    Lead parts become more useful in a DAW when phrases sound like variations of
    an idea rather than unrelated licks. This keeps the original contour but
    applies small deterministic changes: answer phrases may invert direction,
    final phrases tighten the last interval toward resolution, and active parts
    can rotate the rhythm.  Later phrases in longer sections drift further.
    """
    if phrase_index <= 0 or not motif.intervals:
        return motif

    progress = phrase_index / max(1, total_phrases - 1)

    intervals = list(motif.intervals)
    durations = list(motif.durations)

    if phrase_index % 2 == 1 and rng.random() < 0.55:
        intervals = [0] + [-i for i in intervals[1:]]
    elif rng.random() < 0.35 + 0.20 * progress:
        intervals = [0] + [max(-7, min(7, i + rng.choice([-2, -1, 1, 2]))) for i in intervals[1:]]

    if is_final_phrase and len(intervals) > 1:
        intervals[-1] = 0 if rng.random() < 0.65 else (2 if intervals[-1] < 0 else -2)

    if intensity > 0.65 and len(durations) > 2 and rng.random() < 0.30 + 0.20 * progress:
        durations = durations[1:] + durations[:1]

    return Motif(intervals=tuple(intervals), durations=tuple(durations))


def _snap_to_pool(target: int, pool: PitchPool) -> int:
    """Snap target pitch to nearest tone in pool, preferring chord tones."""
    all_tones = pool.all_tones
    if not all_tones:
        return target

    chord_set = set(pool.chord_tones)
    best = all_tones[0]
    best_score = abs(all_tones[0] - target) + (0.1 if all_tones[0] not in chord_set else 0.0)

    for p in all_tones[1:]:
        score = abs(p - target) + (0.1 if p not in chord_set else 0.0)
        if score < best_score:
            best = p
            best_score = score

    return best


def realize_phrase(
    motif: Motif,
    pools: List[PitchPool],
    phrase_beats: float,
    rng: random.Random,
    vary_last: bool = True,
    call_and_response: bool = False,
    leap_limit: int = 5,
) -> List[ResolvedNote]:
    """Repeat motif across the phrase, resolving intervals to actual pitches.

    The motif repeats until the phrase is full. On the last repetition,
    if vary_last is True, the final note resolves to the nearest chord tone
    for phrase closure.

    If call_and_response is True (bridge sections), only the first half
    of the phrase is filled; the second half is left empty for space.

    Args:
        motif: The motif to repeat
        pools: Pitch pools, one per chord slot in the phrase
        phrase_beats: Total phrase duration in beats
        rng: Seeded RNG for determinism
        vary_last: Resolve last note to chord tone on final repetition
        call_and_response: Only fill first half of phrase
        leap_limit: Max semitone interval between consecutive anchors
                    (default 5; solo sections may use 8–10 for wider range)

    Returns:
        List of ResolvedNote sorted by beat_offset
    """
    if not pools or not motif.intervals:
        return []

    motif_duration = sum(motif.durations)
    if motif_duration <= 0:
        return []

    # Effective phrase length (half for call-and-response)
    active_beats = phrase_beats * 0.5 if call_and_response else phrase_beats

    max_reps = max(1, int(active_beats / motif_duration))

    notes: List[ResolvedNote] = []
    beat_pos = 0.0
    prev_pitch: Optional[int] = None

    for rep in range(max_reps):
        is_last_rep = (rep == max_reps - 1)

        # Pool for this beat position (tracks chord changes within phrase)
        pool_idx = min(int(beat_pos / max(phrase_beats, 0.01) * len(pools)), len(pools) - 1)
        anchor_pool = pools[pool_idx]

        # Choose anchor pitch for this repetition via voice-leading
        anchor = choose_pitch(prev_pitch, anchor_pool, leap_limit=leap_limit, rng=rng)

        for step_idx in range(len(motif.intervals)):
            if beat_pos >= active_beats:
                break

            interval = motif.intervals[step_idx]
            dur = motif.durations[step_idx]

            # Current pool (may change mid-motif as we cross chord boundaries)
            cur_pool_idx = min(
                int(beat_pos / max(phrase_beats, 0.01) * len(pools)), len(pools) - 1
            )
            cur_pool = pools[cur_pool_idx]

            # Resolve pitch: anchor + interval, snapped to current pool
            target = anchor + interval
            pitch = _snap_to_pool(target, cur_pool)

            # Variation: resolve last note of last repetition to chord tone
            if vary_last and is_last_rep and step_idx == len(motif.intervals) - 1:
                chord_tones = cur_pool.chord_tones
                if chord_tones:
                    pitch = min(chord_tones, key=lambda p: (abs(p - pitch), p))

            actual_dur = min(dur, active_beats - beat_pos)
            if actual_dur <= 0:
                break

            notes.append(ResolvedNote(
                pitch=pitch,
                beat_offset=beat_pos,
                duration=actual_dur,
            ))

            prev_pitch = pitch
            beat_pos += dur

        rep += 0  # explicit no-op; loop counter already advances

    return notes
