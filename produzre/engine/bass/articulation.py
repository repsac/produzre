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


def articulate_written_note(
    articulation_style: str,
    *,
    duration: float,
    velocity: int,
    strong: bool,
    offbeat: bool,
    octave_up: bool,
    rng,
    slap_pop_rate: float = 0.4,
    slap_thumb_rate: float = 0.9,
    ghost_perc_rate: float = 0.0,
    slap_velocity_floor: int = 70,
    pop_velocity_boost: int = 15,
    final: bool = False,
) -> tuple[float, int, str]:
    """Play a composer-written bass note (a role, a riff double, a device hit)
    with the bass's articulation. Returns (duration, velocity, kind suffix).

    Written parts already have their own note lengths, so finger keeps them;
    pick shortens and sharpens, mute dampens to a short thud, and slap turns
    strong beats into thumb hits and octave or offbeat notes into pops.
    A ``final`` note (the song's ending hit) is a real note: slapped with the
    thumb at its written length, never a ghost or a clipped pop.
    """
    from .slap import apply_slap_duration, apply_slap_velocity, determine_slap_technique

    style = str(articulation_style or "finger").lower()
    if style == "pick":
        return max(0.1, duration * 0.8), max(1, min(127, int(max(velocity, 65) * 1.05))), ""
    if style == "mute":
        return max(0.1, min(duration * 0.45, 0.45)), max(1, int(velocity * 0.85)), "_mute"
    if style == "slap" and final:
        return max(0.1, duration), apply_slap_velocity(velocity, "thumb", slap_velocity_floor,
                                                        pop_velocity_boost), "_slap_thumb"
    if style == "slap":
        technique = determine_slap_technique(
            is_strong_beat=strong, is_offbeat=offbeat or octave_up,
            slap_pop_rate=1.0 if octave_up else slap_pop_rate,
            slap_thumb_rate=slap_thumb_rate, ghost_perc_rate=ghost_perc_rate, rng=rng)
        dur = apply_slap_duration(min(duration, 1.0), technique)
        vel = apply_slap_velocity(velocity, technique, slap_velocity_floor, pop_velocity_boost)
        return max(0.08, dur), vel, "" if technique == "normal" else f"_slap_{technique}"
    return duration, velocity, ""
