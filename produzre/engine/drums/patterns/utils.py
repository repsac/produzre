"""Shared utility functions used across voice modules.

This module provides cross-cutting utilities for velocity calculation,
clamping, proximity checks, and density limiting used by all voice modules.
"""

from __future__ import annotations

import random
from typing import Set

__all__ = ["clamp_int", "vel_for", "is_near", "limit_per_beat"]


def clamp_int(x: int, lo: int, hi: int) -> int:
    """Clamp integer x to range [lo, hi].

    Parameters
    ----------
    x : int
        Value to clamp.
    lo : int
        Minimum value.
    hi : int
        Maximum value.

    Returns
    -------
    int
        Clamped value.
    """
    return lo if x < lo else hi if x > hi else x


def vel_for(
    *,
    base_vel: int,
    accent_strength: float,
    kind: str,
    downbeat: bool,
    rng: random.Random,
) -> int:
    """Compute a nominal velocity for an event kind.

    Parameters
    ----------
    base_vel : int
        Base velocity before kind-specific adjustments.
    accent_strength : float
        Accent influence (0.0 to 1.0).
    kind : str
        Event kind: "kick", "kick_extra", "kick_double", "snare", "snare_ghost",
        "hat", "ride", "open_hat", "crash", "hat_pedal".
    downbeat : bool
        Whether this event is on a downbeat.
    rng : random.Random
        Deterministic RNG for velocity wiggle.

    Returns
    -------
    int
        Computed velocity (1-127).

    Notes
    -----
    Adds a small deterministic wiggle (-2 to +2) to avoid dead-flat velocities
    while maintaining reproducibility.
    """
    v = int(base_vel)
    a = float(accent_strength)

    if kind in ("kick", "kick_extra", "kick_double"):
        v += 8 + int(10 * a)
        if kind != "kick":
            v -= 4
    elif kind == "snare":
        v += 6 + int(14 * a)
    elif kind == "snare_ghost":
        v = max(1, int(v * 0.35))
    elif kind in ("hat", "ride"):
        v += int(6 * a)
        if downbeat:
            v += 6
    elif kind == "open_hat":
        v += 10 + int(6 * a)
    elif kind == "crash":
        v += 20 + int(8 * a)
    elif kind in ("tom", "tom_high", "tom_mid", "tom_low", "tom_fill"):
        v += 10 + int(12 * a)
        if kind == "tom_fill":
            v += 4  # Fill toms slightly louder

    # Small deterministic wiggle to avoid dead-flat velocities (still reproducible).
    v += rng.randint(-2, 2)

    return clamp_int(v, 1, 127)


def is_near(step_i: int, targets: Set[int], tol: int = 1) -> bool:
    """Return True if step_i is within tol steps of any target.

    Parameters
    ----------
    step_i : int
        Step index to check.
    targets : Set[int]
        Set of target step indices.
    tol : int, optional
        Tolerance in steps (default: 1).

    Returns
    -------
    bool
        True if step_i is within tol of any target.
    """
    if not targets:
        return False
    for t in targets:
        if abs(int(step_i) - int(t)) <= int(tol):
            return True
    return False


def limit_per_beat(
    *,
    step_i: int,
    steps_per_bar: int,
    occupied_steps: Set[int],
    max_per_beat: int,
) -> bool:
    """Return True if placing on step_i would exceed per-beat density.

    We consider steps_per_beat = steps_per_bar / beats_per_bar for typical grids;
    since beats_per_bar isn't available here, we approximate by grouping every 4
    steps on a 16-step grid. This still works sensibly on common grids like 12.

    Parameters
    ----------
    step_i : int
        Step index to check.
    steps_per_bar : int
        Total steps per bar.
    occupied_steps : Set[int]
        Set of already occupied step indices.
    max_per_beat : int
        Maximum events allowed per beat bucket.

    Returns
    -------
    bool
        True if density limit is exceeded.
    """
    spb = max(1, int(steps_per_bar))
    beat_bucket = int(step_i) // max(1, spb // 4)
    lo = beat_bucket * max(1, spb // 4)
    hi = min(spb - 1, lo + max(1, spb // 4) - 1)
    count = 0
    for s in occupied_steps:
        if lo <= int(s) <= hi:
            count += 1
    return count >= int(max_per_beat)
