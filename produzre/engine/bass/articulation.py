# produzre/engine/bass/articulation.py
"""Articulation style engine for bass (finger, pick, slap, mute)."""


def get_style_pattern_bias(articulation_style: str) -> str:
    """Get rhythm pattern preference based on articulation style.

    Args:
        articulation_style: finger | pick | slap | mute

    Returns:
        Preferred rhythm pattern (anchor | push | drive | syncopated)
    """
    style_lower = articulation_style.lower()

    if style_lower == "pick":
        # Pick favors steady 8ths (drive pattern)
        return "drive"
    elif style_lower == "mute":
        # Mute favors syncopation and short notes
        return "syncopated"
    elif style_lower == "slap":
        # Slap favors syncopation (funk style)
        return "syncopated"
    else:  # finger or default
        # Finger favors pocket + rests (anchor pattern)
        return "anchor"


def apply_style_velocity(
    base_velocity: int,
    articulation_style: str,
    is_downbeat: bool,
    rng,
) -> int:
    """Apply articulation style to velocity.

    Args:
        base_velocity: Base velocity value
        articulation_style: finger | pick | slap | mute
        is_downbeat: Whether this note is on a downbeat
        rng: Random number generator

    Returns:
        Modified velocity value
    """
    style_lower = articulation_style.lower()

    if style_lower == "finger":
        # Finger: round velocities, gentle accents
        # Slight variation, softer overall
        variation = int((rng.random() - 0.5) * 10)  # ±5
        velocity = base_velocity + variation
        # Downbeat accent (subtle)
        if is_downbeat:
            velocity += 5
        # Round/soften
        velocity = int(velocity * 0.95)

    elif style_lower == "pick":
        # Pick: sharper attacks, higher velocity floor, consistent
        # Less variation, brighter/harder
        variation = int((rng.random() - 0.5) * 6)  # ±3
        velocity = base_velocity + variation
        # Higher floor
        velocity = max(velocity, 65)
        # Downbeat accent (moderate)
        if is_downbeat:
            velocity += 8
        # Sharper (slightly higher)
        velocity = int(velocity * 1.05)

    elif style_lower == "slap":
        # Slap: very dynamic, high velocities, strong accents
        variation = int((rng.random() - 0.5) * 15)  # ±7.5
        velocity = base_velocity + variation
        # Strong downbeat accent
        if is_downbeat:
            velocity += 12
        # Higher overall
        velocity = int(velocity * 1.1)

    elif style_lower == "mute":
        # Mute: lower velocity, more percussive/consistent
        variation = int((rng.random() - 0.5) * 4)  # ±2
        velocity = base_velocity + variation
        # Subtle accent
        if is_downbeat:
            velocity += 3
        # Lower overall (percussive)
        velocity = int(velocity * 0.85)

    else:
        # Default: minimal modification
        velocity = base_velocity

    # Clamp to MIDI range
    return max(1, min(127, velocity))


def apply_style_duration(
    base_duration: float,
    articulation_style: str,
    is_downbeat: bool,
) -> float:
    """Apply articulation style to note duration.

    Args:
        base_duration: Base duration in beats
        articulation_style: finger | pick | slap | mute
        is_downbeat: Whether this note is on a downbeat

    Returns:
        Modified duration in beats
    """
    style_lower = articulation_style.lower()

    if style_lower == "finger":
        # Finger: medium durations, sustained feel
        # Slightly longer for warmth
        duration = base_duration * 0.9
        # Downbeats slightly longer
        if is_downbeat:
            duration = base_duration * 0.95

    elif style_lower == "pick":
        # Pick: tighter durations, staccato feel
        # Shorter, more separated
        duration = base_duration * 0.7
        # Downbeats also tight
        if is_downbeat:
            duration = base_duration * 0.75

    elif style_lower == "slap":
        # Slap: short, percussive bursts
        # Very short for pop
        duration = base_duration * 0.5
        # Downbeats slightly longer for groove
        if is_downbeat:
            duration = base_duration * 0.6

    elif style_lower == "mute":
        # Mute: very short, muted/dampened
        # Shortest durations
        duration = base_duration * 0.4
        # All notes short (even downbeats)
        if is_downbeat:
            duration = base_duration * 0.45

    else:
        # Default: use base duration
        duration = base_duration

    # Ensure minimum duration
    return max(0.1, duration)
