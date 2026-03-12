"""Humanization for rhythm guitar (Phase RG4).

This module adds subtle variations to make MIDI output sound more human:
- Velocity humanization (slight random variation)
- Timing humanization (microtiming variations)
- Velocity curves based on intensity and dynamics

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


def apply_velocity_curve(
    velocity: int,
    intensity: float,
    curve_type: str = "linear",
) -> int:
    """Apply a velocity curve based on intensity.

    Different curve types create different dynamics:
    - "linear": Direct mapping (no curve)
    - "exponential": Soft → loud falls off quickly
    - "logarithmic": More gradual soft → loud
    - "compressed": Narrow dynamic range (easier to mix)

    Args:
        velocity: Base velocity
        intensity: Overall intensity (0.0-2.0)
        curve_type: Type of velocity curve to apply

    Returns:
        int: Velocity with curve applied
    """
    # Normalize velocity to 0-1 range
    vel_norm = velocity / 127.0

    if curve_type == "exponential":
        # Exponential curve: quiet notes stay quiet, loud notes get louder
        vel_norm = vel_norm ** 1.5
    elif curve_type == "logarithmic":
        # Logarithmic curve: more gradual, wider dynamic range
        import math
        vel_norm = math.log(1 + vel_norm * 9) / math.log(10)
    elif curve_type == "compressed":
        # Compression: narrow the dynamic range
        # Map 0.0-1.0 → 0.4-1.0 (narrower range)
        vel_norm = 0.4 + (vel_norm * 0.6)
    # else: linear (no change)

    # Apply intensity scaling
    vel_norm *= intensity

    # Convert back to MIDI range
    new_velocity = int(vel_norm * 127)
    return max(1, min(127, new_velocity))


def apply_dynamic_swell(
    velocity: int,
    position_in_phrase: float,
    swell_amount: float = 0.3,
) -> int:
    """Apply a dynamic swell across a phrase.

    Creates a natural crescendo/decrescendo within a musical phrase.

    Args:
        velocity: Base velocity
        position_in_phrase: Position within phrase (0.0-1.0)
        swell_amount: Intensity of the swell (0.0-1.0)

    Returns:
        int: Velocity with swell applied
    """
    if swell_amount <= 0.0:
        return velocity

    # Create a bell curve centered at 0.5
    # Start quiet, swell to middle, decay at end
    import math
    center = 0.5
    width = 0.4

    # Gaussian-like curve
    distance_from_center = abs(position_in_phrase - center)
    swell_factor = math.exp(-(distance_from_center ** 2) / (2 * width ** 2))

    # Apply swell
    # At peak (center): +30% velocity (with swell_amount=1.0)
    # At edges: -10% velocity
    base_mult = 0.9
    peak_mult = 1.0 + (swell_amount * 0.3)
    multiplier = base_mult + (peak_mult - base_mult) * swell_factor

    new_velocity = int(velocity * multiplier)
    return max(1, min(127, new_velocity))


def apply_downbeat_emphasis(
    velocity: int,
    beat_position: float,
    beats_per_bar: float,
    emphasis_amount: float = 0.2,
) -> int:
    """Apply velocity emphasis to downbeats.

    This is similar to beat_position_velocity in articulation.py,
    but focuses purely on velocity modification for humanization.

    Args:
        velocity: Base velocity
        beat_position: Position within the bar
        beats_per_bar: Beats per bar
        emphasis_amount: Amount of emphasis (0.0-1.0)

    Returns:
        int: Velocity with downbeat emphasis
    """
    if emphasis_amount <= 0.0:
        return velocity

    beat_in_bar = beat_position % beats_per_bar

    # Check if on a strong beat
    distance_to_beat = beat_in_bar % 1.0
    is_on_beat = distance_to_beat < 0.1 or distance_to_beat > 0.9

    if is_on_beat:
        # Determine beat strength
        if abs(beat_in_bar) < 0.1:
            # Beat 1: strongest
            multiplier = 1.0 + emphasis_amount
        elif abs(beat_in_bar - int(beats_per_bar / 2)) < 0.1:
            # Beat 3 (in 4/4): secondary
            multiplier = 1.0 + (emphasis_amount * 0.6)
        else:
            # Other beats: slight boost
            multiplier = 1.0 + (emphasis_amount * 0.3)
    else:
        # Off-beats: slight reduction
        multiplier = 1.0 - (emphasis_amount * 0.2)

    new_velocity = int(velocity * multiplier)
    return max(1, min(127, new_velocity))


def apply_groove_swing(
    beat_position: float,
    swing_amount: float,
    subdivision: int = 2,
) -> float:
    """Apply swing timing to create groove.

    Swing delays the off-beats slightly, creating a "shuffled" feel.

    Args:
        beat_position: Original beat position
        swing_amount: Amount of swing (0.0-1.0)
        subdivision: Subdivision level (2=8ths, 4=16ths)

    Returns:
        float: Swing-adjusted beat position
    """
    if swing_amount <= 0.0:
        return beat_position

    # Find position within subdivision
    grid_size = 1.0 / subdivision
    position_in_grid = beat_position % grid_size
    grid_index = int(beat_position / grid_size)

    # Swing affects off-beats (odd subdivisions)
    if grid_index % 2 == 1:
        # Delay the off-beat by swing amount
        # Full swing (1.0) → delay by 1/3 of grid_size (triplet feel)
        delay = swing_amount * (grid_size / 3.0)
        return beat_position + delay

    return beat_position


def create_velocity_envelope(
    num_hits: int,
    start_velocity: int,
    end_velocity: int,
    envelope_shape: str = "linear",
) -> list[int]:
    """Create a velocity envelope across multiple hits.

    Useful for creating dynamics across a bar or phrase.

    Args:
        num_hits: Number of hits in the envelope
        start_velocity: Starting velocity
        end_velocity: Ending velocity
        envelope_shape: "linear", "exponential", "logarithmic"

    Returns:
        list[int]: Velocity values for each hit
    """
    if num_hits <= 0:
        return []

    if num_hits == 1:
        return [start_velocity]

    velocities = []
    for i in range(num_hits):
        # Position in envelope (0.0-1.0)
        t = i / (num_hits - 1)

        if envelope_shape == "exponential":
            # Exponential curve
            t = t ** 2
        elif envelope_shape == "logarithmic":
            # Logarithmic curve
            import math
            t = math.sqrt(t)
        # else: linear

        # Interpolate
        velocity = int(start_velocity + (end_velocity - start_velocity) * t)
        velocities.append(max(1, min(127, velocity)))

    return velocities
