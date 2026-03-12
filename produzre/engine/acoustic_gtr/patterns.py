"""Fingerpicking pattern library for acoustic guitar.

Each pattern describes which strings to pluck and when (relative to bar start).
Patterns are defined in 4/4 by default; WALTZ is 3/4.

String indices reference the sorted voicing pitches list:
  0 = lowest (bass/6th string),  1 = 5th string,  2 = 4th string
  3 = 3rd string,                4 = 2nd string,  5 = 1st string (treble)

PickHit fields:
  beat       — beat within bar (0.0 = bar downbeat)
  string_idx — index into voicing pitches (clamped to actual chord length)
  vel_ratio  — velocity multiplier relative to base_vel
  is_bass    — True = thumb stroke (warmer, louder), False = finger stroke
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class PickHit:
    beat:       float  # Beat within bar, 0.0 = bar start
    string_idx: int    # Index into chord pitches list (0 = lowest)
    vel_ratio:  float  # Velocity multiplier (1.0 = base_vel)
    is_bass:    bool   # True = P (thumb), False = I/M/A (finger)


@dataclass(frozen=True)
class PickPattern:
    name:          str
    beats_per_bar: int                # 4 for common time, 3 for waltz
    hits:          Tuple[PickHit, ...]


# =============================================================================
# Travis Picking (most common folk/country pattern)
#
# Classic alternating-bass pattern. Thumb alternates between bass strings
# (strings 0 and 1) while fingers pick treble strings on the off-beats.
# 8 hits per bar at 8th-note intervals.
#
#   Beat: 0.0   0.5   1.0   1.5   2.0   2.5   3.0   3.5
#   Hand: P     I     P     M     P     I     P     M
#   Str:  0     3     1     4     0     3     1     4
# =============================================================================

TRAVIS = PickPattern(
    name="travis",
    beats_per_bar=4,
    hits=(
        PickHit(0.0, 0, 1.00, True),   # P — bass root (strong downbeat)
        PickHit(0.5, 3, 0.78, False),  # I — mid-treble
        PickHit(1.0, 1, 0.88, True),   # P — bass 5th
        PickHit(1.5, 4, 0.75, False),  # M — upper treble
        PickHit(2.0, 0, 0.95, True),   # P — bass root (beat 3)
        PickHit(2.5, 3, 0.78, False),  # I — mid-treble
        PickHit(3.0, 1, 0.85, True),   # P — bass 5th
        PickHit(3.5, 4, 0.75, False),  # M — upper treble
    ),
)


# =============================================================================
# PIMA — Classical fingerstyle
#
# One pluck per beat. Thumb (P) on bass, then ascending finger strokes
# Index (I), Middle (M), Ring (A) on treble strings.
# Creates a stately, classical feel. 4 hits per bar.
#
#   Beat: 0     1     2     3
#   Hand: P     I     M     A
#   Str:  0     2     3     4
# =============================================================================

PIMA = PickPattern(
    name="pima",
    beats_per_bar=4,
    hits=(
        PickHit(0.0, 0, 1.00, True),   # P — bass root
        PickHit(1.0, 2, 0.80, False),  # I — mid string
        PickHit(2.0, 3, 0.78, False),  # M — upper-mid string
        PickHit(3.0, 4, 0.75, False),  # A — treble string
    ),
)


# =============================================================================
# Broken Chord (arpeggiated, low→high)
#
# Steady 8th-note arpeggio climbing from bass to treble and back.
# Creates a flowing, harp-like texture common in ballads and folk.
# 8 hits per bar.
#
#   Beat: 0.0  0.5  1.0  1.5  2.0  2.5  3.0  3.5
#   Str:  0    1    2    3    4    3    2    1
# =============================================================================

BROKEN_CHORD = PickPattern(
    name="broken_chord",
    beats_per_bar=4,
    hits=(
        PickHit(0.0, 0, 1.00, True),   # bass (P)
        PickHit(0.5, 1, 0.82, True),   # bass-mid
        PickHit(1.0, 2, 0.80, False),  # mid (I)
        PickHit(1.5, 3, 0.78, False),  # upper-mid (M)
        PickHit(2.0, 4, 0.76, False),  # treble peak (A)
        PickHit(2.5, 3, 0.76, False),  # descending upper-mid
        PickHit(3.0, 2, 0.78, False),  # descending mid
        PickHit(3.5, 1, 0.80, True),   # descending bass-mid
    ),
)


# =============================================================================
# Waltz (3/4 time)
#
# Classic bass-chord-chord pattern. Thumb hits bass string on beat 1,
# two-finger chord on beats 2 and 3.
# 3 hits per bar (each beat).
#
#   Beat: 0     1     2
#   Hand: P     IM    IM
#   Str:  0    3+4   3+4   (simultaneous treble pair on beats 2 & 3)
# Note: beat 1 and 2 emit TWO simultaneous notes each (strings 3 and 4).
# =============================================================================

WALTZ = PickPattern(
    name="waltz",
    beats_per_bar=3,
    hits=(
        PickHit(0.0, 0, 1.00, True),   # P — bass root
        PickHit(1.0, 3, 0.78, False),  # I — mid-treble chord
        PickHit(1.0, 4, 0.75, False),  # M — treble chord (simultaneous)
        PickHit(2.0, 3, 0.76, False),  # I — mid-treble chord
        PickHit(2.0, 4, 0.73, False),  # M — treble chord (simultaneous)
    ),
)


# =============================================================================
# Roll — 16th-note ascending arpeggio
#
# Continuous rolling arpeggio at 16th-note resolution, for building energy
# or prechorus tension. 16 hits per bar (dense).
#
#   Str cycle: 0, 1, 2, 3, 4, 3, 2, 1 (repeat x2)
# =============================================================================

_ROLL_CYCLE = [0, 1, 2, 3, 4, 3, 2, 1]
_ROLL_VEL   = [1.00, 0.82, 0.80, 0.78, 0.76, 0.76, 0.78, 0.80]  # matched to cycle

ROLL = PickPattern(
    name="roll",
    beats_per_bar=4,
    hits=tuple(
        PickHit(
            beat=i * 0.25,
            string_idx=_ROLL_CYCLE[i % len(_ROLL_CYCLE)],
            vel_ratio=_ROLL_VEL[i % len(_ROLL_VEL)],
            is_bass=(i % len(_ROLL_CYCLE) < 2),  # first two of each cycle = bass
        )
        for i in range(16)
    ),
)


# =============================================================================
# Pattern registry
# =============================================================================

PATTERNS: Dict[str, PickPattern] = {
    "travis":       TRAVIS,
    "pima":         PIMA,
    "broken_chord": BROKEN_CHORD,
    "waltz":        WALTZ,
    "roll":         ROLL,
}


def get_pattern(name: str, beats_per_bar: int) -> PickPattern:
    """Return the named pattern, adapting for time signature.

    Falls back to TRAVIS for unknown names.
    Forces WALTZ when beats_per_bar == 3.
    """
    if beats_per_bar == 3:
        return WALTZ

    pattern = PATTERNS.get(name)
    if pattern is None:
        return TRAVIS

    # If the pattern is WALTZ but we're in 4/4, use TRAVIS instead
    if pattern is WALTZ and beats_per_bar != 3:
        return TRAVIS

    return pattern
