"""Humanization for rhythm guitar (Phase RG4).

This module adds subtle variations to make MIDI output sound more human:
- Velocity humanization (slight random variation)
- Timing humanization (microtiming variations)

Swing is NOT applied here: the shared groove clock (produzre.groove) swings
rhythm guitar events as an orchestrator post-process so the whole band shares
the drums' feel. (The old never-called apply_groove_swing / velocity-curve
helpers were removed by the groove-clock task.)

All humanization is deterministic given RNG seed and parameters.
"""

from __future__ import annotations

import random
from typing import Optional


def humanize_velocity(
    velocity: int,
    amount: float,
    rng: Optional[random.Random] = None,
) -> int:
    """Apply random velocity variation for human feel.

    Args:
        velocity: Base MIDI velocity
        amount: Humanization amount (0.0-1.0)
        rng: Random number generator

    Returns:
        int: Humanized velocity (1-127)
    """
    if rng is None:
        rng = random.Random()

    if amount <= 0.0:
        return velocity

    # Amount controls the range of variation
    # 0.1 → ±5 velocity points
    # 1.0 → ±20 velocity points
    max_variation = int(amount * 20)

    variation = rng.randint(-max_variation, max_variation)
    new_velocity = velocity + variation

    return max(1, min(127, new_velocity))


def humanize_timing(
    beat_position: float,
    amount: float,
    rng: Optional[random.Random] = None,
) -> float:
    """Apply random timing variation for human feel.

    Args:
        beat_position: Original beat position
        amount: Humanization amount (0.0-1.0)
        rng: Random number generator

    Returns:
        float: Humanized beat position
    """
    if rng is None:
        rng = random.Random()

    if amount <= 0.0:
        return beat_position

    # Amount controls the range of timing variation
    # 0.1 → ±0.01 beats (±10ms at 120 BPM)
    # 1.0 → ±0.05 beats (±50ms at 120 BPM)
    max_variation = amount * 0.05

    variation = rng.uniform(-max_variation, max_variation)
    new_position = beat_position + variation

    # Ensure we don't go negative
    return max(0.0, new_position)
