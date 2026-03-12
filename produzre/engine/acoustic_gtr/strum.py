"""Strumming hit generation for acoustic guitar.

Generates per-string note events for strummed chord hits across a bar.
Quarter-note beat positions are filtered by density; chord-change downbeats
are always included. Strum spread staggers each string by a small time offset
to simulate the natural sweep of a pick or thumb across the strings.
"""

from __future__ import annotations

import random
from typing import List, Tuple

from .articulation import strum_spread_offsets

# Total time from lowest to highest string in one strum sweep (~12ms at 100BPM)
_STRUM_SPREAD_BEATS = 0.020

# Muted hit characteristics
_MUTE_DUR_FRACTION = 0.18   # Very short — just the percussive chop
_MUTE_VEL_FRACTION = 0.82   # Slightly softer than open hit

# Probability of choosing an up-strum (otherwise down)
_UP_STRUM_PROBABILITY = 0.22


def place_strum_hits(
    voicing_pitches: List[int],
    beats_per_bar: float,
    bar_start_beat: float,      # Section-local offset of this bar's downbeat
    strum_density: float,       # 0.0-1.0 — probability of non-change beats firing
    mute_ratio: float,          # 0.0-1.0 — probability of a hit being palm-muted
    base_vel: int,
    is_chord_change: bool,      # True = first bar of a new chord slot
    rng: random.Random,
) -> List[Tuple[float, int, int, float]]:
    """Generate strummed note events for one bar.

    Quarter-note positions (0, 1, 2, 3 in 4/4) form the candidate grid.
    The chord-change downbeat is always played; other positions fire with
    probability ``strum_density``.

    Each fired position emits one note per pitch in the voicing, offset by
    the strum spread so they arrive in a slight sweep rather than a block.

    Args:
        voicing_pitches:  Sorted MIDI pitches (lowest first) for the chord.
        beats_per_bar:    Number of beats per bar (4.0 for 4/4, 3.0 for 3/4).
        bar_start_beat:   Section-local beat of the first beat of this bar.
        strum_density:    Fraction of non-change positions to include (0.0-1.0).
        mute_ratio:       Probability that any given hit is palm-muted.
        base_vel:         Instrument base velocity.
        is_chord_change:  If True, beat 0 is always included regardless of density.
        rng:              Seeded RNG for deterministic variation.

    Returns:
        List of ``(section_local_beat, pitch, velocity, duration_beats)`` tuples,
        one per pitch per strum hit. Sorted by section_local_beat.
    """
    if not voicing_pitches:
        return []

    n = len(voicing_pitches)
    events: List[Tuple[float, int, int, float]] = []

    n_beats = max(1, int(beats_per_bar))

    for beat_idx in range(n_beats):
        beat_pos = float(beat_idx)
        is_downbeat = (beat_idx == 0)

        # Decide whether to fire this beat position
        if is_downbeat and is_chord_change:
            fire = True
        elif rng.random() < strum_density:
            fire = True
        else:
            fire = False

        if not fire:
            continue

        # Muting decision
        is_muted = rng.random() < mute_ratio

        # Strum direction: mostly down; occasional up for variety
        direction = "up" if rng.random() < _UP_STRUM_PROBABILITY else "down"
        offsets = strum_spread_offsets(n, direction, _STRUM_SPREAD_BEATS)

        # Velocity: accent downbeats; small humanization
        v = base_vel + (5 if is_downbeat else 0)
        v += rng.randint(-7, 7)
        if is_muted:
            v = int(v * _MUTE_VEL_FRACTION)
        v = max(25, min(127, v))

        # Sustain: open notes ring until next beat (1 beat); mutes are very short
        base_dur = 1.0 if not is_muted else _MUTE_DUR_FRACTION
        # Small duration variation between hits keeps them from sounding identical
        base_dur += rng.uniform(-0.06, 0.06)
        base_dur = max(0.08, base_dur)

        for pitch, offset in zip(voicing_pitches, offsets):
            abs_beat = bar_start_beat + beat_pos + offset
            events.append((abs_beat, pitch, v, base_dur))

    return events
