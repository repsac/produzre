# produzre/engine/bass/approach.py
"""Passing tones and approach notes for bass engine."""


def is_strong_beat(beat_in_bar: float) -> bool:
    """Check if a beat is a strong beat (downbeat only for passing tones).

    For passing tone purposes, only beat 1 is considered strong.
    Beat 3 is harmonically strong in 4/4 but is acceptable for approach tones
    in non-walking bass lines.

    Args:
        beat_in_bar: Beat position within the bar (0-based)

    Returns:
        True if strong beat (downbeat only), False otherwise
    """
    eps = 1e-6

    # Only downbeat is considered strong for passing tone purposes
    if abs(beat_in_bar) < eps:
        return True

    return False


def get_diatonic_approach(
    target_pitch: int,
    from_below: bool,
    mode_offsets: list[int],
    key_root: int,
) -> int:
    """Calculate diatonic approach note to target pitch.

    Args:
        target_pitch: MIDI pitch to approach
        from_below: True to approach from below, False from above
        mode_offsets: Scale offsets for current mode (e.g., [0,2,4,5,7,9,11] for major)
        key_root: Root MIDI pitch of the key (e.g., 60 for C)

    Returns:
        MIDI pitch of diatonic approach note
    """
    # Get pitch class of target (0-11)
    target_pc = target_pitch % 12

    # Get pitch class of key root
    key_root_pc = key_root % 12

    # Find target's offset in the scale
    # Map pitch class to scale degree
    relative_pc = (target_pc - key_root_pc) % 12

    # Find which scale degree the target is on
    if relative_pc in mode_offsets:
        target_degree = mode_offsets.index(relative_pc)
    else:
        # Target is not in scale, use chromatic approach
        if from_below:
            return target_pitch - 1
        else:
            return target_pitch + 1

    # Get neighboring scale degree
    if from_below:
        approach_degree = (target_degree - 1) % len(mode_offsets)
        approach_offset = mode_offsets[approach_degree]

        # Calculate approach pitch
        # If we wrapped around (approaching from octave below), subtract 12
        if approach_degree > target_degree:
            approach_pitch = key_root + approach_offset - 12
        else:
            approach_pitch = key_root + approach_offset

        # Adjust to correct octave
        while approach_pitch > target_pitch:
            approach_pitch -= 12
        while approach_pitch < target_pitch - 12:
            approach_pitch += 12

    else:  # from above
        approach_degree = (target_degree + 1) % len(mode_offsets)
        approach_offset = mode_offsets[approach_degree]

        # Calculate approach pitch
        if approach_degree < target_degree:
            approach_pitch = key_root + approach_offset + 12
        else:
            approach_pitch = key_root + approach_offset

        # Adjust to correct octave
        while approach_pitch < target_pitch:
            approach_pitch += 12
        while approach_pitch > target_pitch + 12:
            approach_pitch -= 12

    return approach_pitch


def get_chromatic_approach(
    target_pitch: int,
    from_below: bool = True,
) -> int:
    """Calculate chromatic (half-step) approach note to target pitch.

    Args:
        target_pitch: MIDI pitch to approach
        from_below: True to approach from below, False from above

    Returns:
        MIDI pitch of chromatic approach note
    """
    if from_below:
        return target_pitch - 1
    else:
        return target_pitch + 1


def should_allow_passing_tone(
    beat_in_bar: float,
    is_walking_persona: bool,
    passing_count_in_bar: int,
    max_passing_per_bar: int,
) -> bool:
    """Check if passing tone is allowed at this position.

    Args:
        beat_in_bar: Beat position within bar
        is_walking_persona: True if using walking bass persona
        passing_count_in_bar: Number of passing tones already used in this bar
        max_passing_per_bar: Maximum passing tones allowed per bar

    Returns:
        True if passing tone is allowed
    """
    # Check bar limit
    if passing_count_in_bar >= max_passing_per_bar:
        return False

    # Check if it's a strong beat
    is_strong = is_strong_beat(beat_in_bar)

    # Walking persona allows passing tones on any beat
    if is_walking_persona:
        return True

    # Otherwise, avoid strong beats for passing tones
    return not is_strong
