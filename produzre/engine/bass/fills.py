# produzre/engine/bass/fills.py
"""Bass fills and transitions."""

from .voicing import clamp_to_register
from .approach import get_diatonic_approach, get_chromatic_approach


def is_fill_zone(
    local_beat: float,
    total_beats: float,
    beats_per_bar: float,
    phrase_length_bars: int = 4,
) -> tuple[bool, str]:
    """Check if we're in a fill zone (last bar of phrase or section).

    Args:
        local_beat: Beat position within the section
        total_beats: Total beats in the section
        beats_per_bar: Beats per bar
        phrase_length_bars: Phrase length in bars (default 4)

    Returns:
        (is_fill_zone, zone_type) where zone_type is "section_end" or "phrase_end"
    """
    eps = 1e-6
    current_bar = int(local_beat // beats_per_bar)
    total_bars = int(total_beats // beats_per_bar)

    # Check if we're in the last bar of the section
    is_last_bar = (current_bar == total_bars - 1)
    if is_last_bar:
        return (True, "section_end")

    # Check if we're at a phrase boundary (every N bars)
    if phrase_length_bars > 0:
        # Check if we're in the last bar of a phrase
        bars_into_phrase = current_bar % phrase_length_bars
        is_phrase_end_bar = (bars_into_phrase == phrase_length_bars - 1)
        if is_phrase_end_bar:
            return (True, "phrase_end")

    return (False, "")


def should_generate_fill(
    fill_rate: float,
    fill_avoid_drums: float,
    is_drum_filling: bool,
    rng,
) -> bool:
    """Check if we should generate a fill based on fill_rate and drum collision.

    Args:
        fill_rate: Base probability of fill
        fill_avoid_drums: Reduction factor when drums filling (0.0-1.0)
        is_drum_filling: True if drums are filling at this boundary
        rng: Random number generator

    Returns:
        True if we should generate a fill
    """
    if fill_rate <= 0:
        return False

    # Apply drum collision avoidance
    effective_rate = fill_rate
    if is_drum_filling and fill_avoid_drums > 0:
        # Reduce fill probability by avoidance factor
        effective_rate = fill_rate * (1.0 - fill_avoid_drums)

    return rng.random() < effective_rate


def generate_fill_run_to_root(
    current_pitch: int,
    target_root: int,
    fill_complexity: float,
    register_low: int,
    register_high: int,
    mode_offsets: list[int],
    key_root: int,
    rng,
) -> list[tuple[int, str]]:
    """Generate scalar run approaching target root.

    Args:
        current_pitch: Starting pitch
        target_root: Target root pitch to approach
        fill_complexity: Complexity (0.0=few notes, 1.0=chromatic run)
        register_low: Lowest allowed pitch
        register_high: Highest allowed pitch
        mode_offsets: Scale offsets for diatonic runs
        key_root: Key root pitch
        rng: Random number generator

    Returns:
        List of (pitch, kind) tuples for the fill
    """
    notes = []

    # Determine direction (ascending or descending)
    target_clamped = clamp_to_register(target_root, register_low, register_high)
    direction = 1 if target_clamped > current_pitch else -1

    # Calculate number of steps based on complexity
    # Low complexity = 2-3 notes, high complexity = scalar run
    interval = abs(target_clamped - current_pitch)
    if fill_complexity < 0.3:
        # Simple fill: just 2-3 approach notes
        num_steps = min(2, max(1, interval // 3))
    elif fill_complexity < 0.7:
        # Medium fill: diatonic steps
        num_steps = min(4, max(2, interval // 2))
    else:
        # Complex fill: chromatic or fast scalar run
        num_steps = min(6, max(3, interval))

    # Generate notes approaching target
    if fill_complexity >= 0.7 and rng.random() < 0.5:
        # Chromatic run for complex fills
        pitch = current_pitch
        for i in range(num_steps):
            pitch += direction
            pitch = clamp_to_register(pitch, register_low, register_high)
            notes.append((pitch, "fill_run_chromatic"))
    else:
        # Diatonic run using scale
        pitch = current_pitch
        for i in range(num_steps):
            # Get next scale degree
            approach_pitch = get_diatonic_approach(
                target_pitch=pitch + (direction * 3),  # Target next scale tone
                from_below=(direction > 0),
                mode_offsets=mode_offsets,
                key_root=key_root,
            )
            pitch = clamp_to_register(approach_pitch, register_low, register_high)
            notes.append((pitch, "fill_run_diatonic"))

    return notes


def generate_fill_octave_climb(
    current_pitch: int,
    fill_complexity: float,
    register_low: int,
    register_high: int,
    rng,
) -> list[tuple[int, str]]:
    """Generate octave climb/drop fill.

    Args:
        current_pitch: Starting pitch
        fill_complexity: Complexity (0.0=simple jump, 1.0=with passing tones)
        register_low: Lowest allowed pitch
        register_high: Highest allowed pitch
        rng: Random number generator

    Returns:
        List of (pitch, kind) tuples for the fill
    """
    notes = []

    # Determine direction (up or down)
    can_go_up = (current_pitch + 12 <= register_high)
    can_go_down = (current_pitch - 12 >= register_low)

    if not can_go_up and not can_go_down:
        # Can't do octave jump, return empty
        return notes

    # Choose direction
    if can_go_up and can_go_down:
        direction = 1 if rng.random() < 0.5 else -1
    elif can_go_up:
        direction = 1
    else:
        direction = -1

    target_pitch = current_pitch + (direction * 12)

    if fill_complexity < 0.5:
        # Simple octave jump (no passing tones)
        notes.append((target_pitch, "fill_octave"))
    else:
        # Octave climb with passing tones
        # Add 2-3 passing tones between current and target
        num_passing = 2 if fill_complexity < 0.8 else 3
        interval_step = (target_pitch - current_pitch) // (num_passing + 1)

        for i in range(1, num_passing + 1):
            passing_pitch = current_pitch + (interval_step * i)
            notes.append((passing_pitch, "fill_octave_passing"))

        # Final target octave
        notes.append((target_pitch, "fill_octave"))

    return notes


def generate_fill_rhythmic_pickup(
    current_pitch: int,
    target_root: int,
    fill_complexity: float,
    register_low: int,
    register_high: int,
    rng,
) -> list[tuple[int, str]]:
    """Generate syncopated rhythmic pickup fill.

    Args:
        current_pitch: Starting pitch
        target_root: Target root pitch
        fill_complexity: Complexity (0.0=simple, 1.0=complex syncopation)
        register_low: Lowest allowed pitch
        register_high: Highest allowed pitch
        rng: Random number generator

    Returns:
        List of (pitch, kind) tuples for the fill
    """
    notes = []

    target_clamped = clamp_to_register(target_root, register_low, register_high)

    # Number of pickup notes based on complexity
    if fill_complexity < 0.4:
        num_notes = 2  # Simple: two pickup notes
    elif fill_complexity < 0.7:
        num_notes = 3  # Medium: three notes
    else:
        num_notes = 4  # Complex: four notes

    # Generate syncopated pattern approaching target
    # Use chromatic approach for last note
    for i in range(num_notes - 1):
        # Vary pitch around current pitch for rhythmic interest
        variation = rng.choice([-2, -1, 0, 1, 2])
        pitch = clamp_to_register(current_pitch + variation, register_low, register_high)
        notes.append((pitch, "fill_pickup"))

    # Final approach note (chromatic approach to target)
    approach_pitch = get_chromatic_approach(target_clamped, from_below=True)
    approach_pitch = clamp_to_register(approach_pitch, register_low, register_high)
    notes.append((approach_pitch, "fill_pickup_approach"))

    return notes
