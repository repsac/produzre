# produzre/engine/bass/groove.py
"""Groove personality features for bass (octave jumps, fifth drops, pedal tones, accents)."""


def apply_octave_jump(
    pitch: int,
    octave_jump_rate: float,
    register_low: int,
    register_high: int,
    rng,
    is_downbeat: bool = False,
    is_chord_change: bool = False,
) -> int:
    """Apply octave jump to a pitch with probability.

    Octave jumps are most musical at structurally important positions
    (downbeats, chord changes). They are suppressed on inner beats to
    avoid random leaps that disrupt phrase continuity.

    Direction is biased by register position: notes in the lower half
    of the range prefer jumping up (adding energy), notes in the upper
    half prefer jumping down (grounding the phrase).

    Args:
        pitch: Original MIDI pitch
        octave_jump_rate: Base probability of octave jump
        register_low: Lowest allowed MIDI note
        register_high: Highest allowed MIDI note
        rng: Random number generator
        is_downbeat: True if this is the bar downbeat
        is_chord_change: True if this is the first note of a new chord

    Returns:
        Pitch after potential octave jump (clamped to register)
    """
    if octave_jump_rate <= 0:
        return pitch

    # Scale probability by beat position: structural beats get full rate,
    # inner beats get a 30% reduced rate to avoid mid-phrase lurches.
    if is_downbeat or is_chord_change:
        effective_rate = octave_jump_rate
    else:
        effective_rate = octave_jump_rate * 0.30

    if rng.random() >= effective_rate:
        return pitch

    # Register-aware direction: bias toward jumping "toward the middle"
    register_range = max(1, register_high - register_low)
    position = (pitch - register_low) / register_range  # 0.0 = bottom, 1.0 = top
    # Lower half → prefer up (70%), upper half → prefer down (70%)
    up_prob = 0.70 if position < 0.5 else 0.30

    if rng.random() < up_prob:
        new_pitch = pitch + 12
        if new_pitch <= register_high:
            return new_pitch
    else:
        new_pitch = pitch - 12
        if new_pitch >= register_low:
            return new_pitch

    return pitch


def should_use_pedal_tone(
    pedal_rate: float,
    is_chord_change: bool,
    rng,
) -> bool:
    """Check if we should use a pedal tone (hold previous root across chord change).

    Args:
        pedal_rate: Probability of pedal tone
        is_chord_change: True if this is the first note of a new chord
        rng: Random number generator

    Returns:
        True if pedal tone should be used
    """
    if not is_chord_change or pedal_rate <= 0:
        return False

    return rng.random() < pedal_rate


def should_use_fifth_drop(
    fifth_jump_rate: float,
    is_chord_change: bool,
    is_downbeat: bool,
    rng,
) -> bool:
    """Check if we should use the fifth instead of root on a chord change.

    Fifth drops are common on chord changes, especially on downbeats.

    Args:
        fifth_jump_rate: Probability of using fifth
        is_chord_change: True if this is the first note of a new chord
        is_downbeat: True if this is a downbeat
        rng: Random number generator

    Returns:
        True if fifth should be used
    """
    if not is_chord_change or fifth_jump_rate <= 0:
        return False

    # Higher probability on downbeats
    effective_rate = fifth_jump_rate * (1.5 if is_downbeat else 1.0)

    return rng.random() < effective_rate


def apply_accent(
    velocity: int,
    is_accent: bool,
    accent_strength: float,
) -> int:
    """Apply accent to velocity.

    Args:
        velocity: Base velocity
        is_accent: True if this note should be accented
        accent_strength: Velocity multiplier for accents

    Returns:
        Accented velocity (clamped to MIDI range)
    """
    if not is_accent or accent_strength <= 1.0:
        return velocity

    accented_velocity = int(velocity * accent_strength)
    return min(127, max(1, accented_velocity))
