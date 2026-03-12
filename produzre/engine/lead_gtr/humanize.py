"""Simple humanisation for lead guitar (Phase LG5).

Applies small deterministic timing jitter and velocity variance so the
lead line sounds less rigid while remaining fully reproducible.

Jitter and variance magnitudes scale with intensity:

    low intensity  → very subtle  (±0.02 beats, ±4 velocity)
    mid intensity  → gentle       (±0.04 beats, ±6 velocity)
    high intensity → moderate     (±0.06 beats, ±8 velocity)

These are intentionally small — the goal is "feels alive", not "sounds
sloppy".  Positive timing jitter slightly shortens duration so notes
don't creep into the next event's window.
"""

from __future__ import annotations

import random
from typing import Tuple


# Max jitter (beats) and velocity variance by intensity band.
_JITTER_LOW  = 0.02
_JITTER_MID  = 0.04
_JITTER_HIGH = 0.06

_VELVAR_LOW  = 4
_VELVAR_MID  = 6
_VELVAR_HIGH = 8


def _get_params(intensity: float) -> Tuple[float, int]:
    """Return (max_jitter_beats, max_vel_variance) for the given intensity."""
    if intensity < 0.4:
        return _JITTER_LOW, _VELVAR_LOW
    if intensity < 0.7:
        return _JITTER_MID, _VELVAR_MID
    return _JITTER_HIGH, _VELVAR_HIGH


def humanize_note(
    beat: float,
    duration: float,
    velocity: int,
    rng: random.Random,
    intensity: float,
) -> Tuple[float, float, int]:
    """Apply timing jitter and velocity variance to a single note.

    Args:
        beat: Original start beat (section-local or song-local).
        duration: Original duration in beats.
        velocity: Original MIDI velocity (1–127).
        rng: Seeded RNG for determinism.
        intensity: 0.0–1.0 section intensity (scales effect magnitude).

    Returns:
        Tuple of (jittered_beat, adjusted_duration, varied_velocity).
        Duration is slightly shortened when jitter is positive so notes
        don't overlap the next event.
    """
    max_jitter, max_vel_var = _get_params(intensity)

    # Timing jitter: symmetric random offset.
    jitter = (rng.random() - 0.5) * 2.0 * max_jitter
    new_beat = beat + jitter

    # Shorten duration when jittered forward to avoid overlap.
    dur_shrink = max(0.0, jitter)
    new_duration = max(0.05, duration - dur_shrink)

    # Velocity variance: symmetric random offset.
    vel_offset = int((rng.random() - 0.5) * 2.0 * max_vel_var)
    new_velocity = max(20, min(127, velocity + vel_offset))

    return new_beat, new_duration, new_velocity
