# produzre/engine/bass/slap.py
"""Slap technique for bass (thumb, pop, ghost)."""


def determine_slap_technique(
    is_strong_beat: bool,
    is_offbeat: bool,
    slap_pop_rate: float,
    slap_thumb_rate: float,
    ghost_perc_rate: float,
    rng,
) -> str:
    """Determine slap technique for a note (thumb/pop/ghost).

    Args:
        is_strong_beat: True if downbeat or chord change
        is_offbeat: True if on an offbeat subdivision
        slap_pop_rate: Probability of pop on offbeats
        slap_thumb_rate: Probability of thumb on strong beats
        ghost_perc_rate: Probability of ghost note
        rng: Random number generator

    Returns:
        "thumb", "pop", "ghost", or "normal"
    """
    # Ghost notes have priority (percussive ghosts can appear anywhere)
    if ghost_perc_rate > 0 and rng.random() < ghost_perc_rate:
        return "ghost"

    # Thumb hits on strong beats
    if is_strong_beat and rng.random() < slap_thumb_rate:
        return "thumb"

    # Pops on offbeats
    if is_offbeat and rng.random() < slap_pop_rate:
        return "pop"

    return "normal"


def apply_slap_velocity(
    base_velocity: int,
    slap_technique: str,
    slap_velocity_floor: int,
    pop_velocity_boost: int,
) -> int:
    """Apply slap-specific velocity adjustments.

    Args:
        base_velocity: Base velocity
        slap_technique: "thumb", "pop", "ghost", or "normal"
        slap_velocity_floor: Minimum velocity for slap hits
        pop_velocity_boost: Additional velocity for pops

    Returns:
        Adjusted velocity (clamped to MIDI range)
    """
    if slap_technique == "ghost":
        # Ghost notes are very quiet
        return max(1, min(50, base_velocity // 2))
    elif slap_technique == "pop":
        # Pops are bright and punchy
        pop_vel = base_velocity + pop_velocity_boost
        return max(slap_velocity_floor, min(127, pop_vel))
    elif slap_technique == "thumb":
        # Thumb hits have a strong floor
        return max(slap_velocity_floor, min(127, base_velocity))
    else:
        # Normal notes
        return max(1, min(127, base_velocity))


def apply_slap_duration(
    base_duration: float,
    slap_technique: str,
) -> float:
    """Apply slap-specific duration adjustments (more staccato).

    Args:
        base_duration: Base duration in beats
        slap_technique: "thumb", "pop", "ghost", or "normal"

    Returns:
        Adjusted duration
    """
    if slap_technique == "ghost":
        # Ghost notes are very short (30% of base)
        return base_duration * 0.3
    elif slap_technique == "pop":
        # Pops are short and bright (40% of base)
        return base_duration * 0.4
    elif slap_technique == "thumb":
        # Thumb hits are medium staccato (60% of base)
        return base_duration * 0.6
    else:
        # Normal notes retain original duration
        return base_duration
