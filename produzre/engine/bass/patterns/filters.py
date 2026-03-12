# produzre/engine/bass/patterns/filters.py
"""Rhythm pattern filters for bass engine."""


def apply_density_filter(
    eligible_slots: set[float],
    density: float,
    rng,
) -> set[float]:
    """Apply density filtering: randomly select from eligible slots.

    Args:
        eligible_slots: Set of beat positions eligible for notes
        density: Probability (0.0-1.0) of placing a note at an eligible slot
        rng: Random number generator

    Returns:
        Set of selected beat positions
    """
    selected = set()

    for slot in eligible_slots:
        if rng.random() < density:
            selected.add(slot)

    return selected


def apply_rest_filter(
    selected_slots: set[float],
    rest_rate: float,
    rng,
) -> set[float]:
    """Apply rest filtering: randomly remove notes to create gaps.

    Args:
        selected_slots: Set of beat positions with notes
        rest_rate: Probability (0.0-1.0) of removing a note
        rng: Random number generator

    Returns:
        Set of remaining beat positions after rests
    """
    remaining = set()

    for slot in selected_slots:
        if rng.random() >= rest_rate:  # Keep note if random > rest_rate
            remaining.add(slot)

    return remaining


def apply_drum_locking(
    slots: set[float],
    drum_events: list,
    lock_to_kick: float,
    lock_to_snare: float,
    lock_to_hat: float,
    subdivisions_per_beat: int,
    rng,
) -> set[float]:
    """Apply drum locking: add bass notes at drum hit times based on lock parameters.

    Args:
        slots: Current set of bass note slots
        drum_events: List of drum events with .beat and .kind attributes
        lock_to_kick: Probability (0.0-1.0) of adding bass note at kick positions
        lock_to_snare: Probability of adding bass note at snare positions
        lock_to_hat: Probability of adding bass note at hat/ride positions
        subdivisions_per_beat: Subdivisions per beat for quantization
        rng: Random number generator

    Returns:
        Set of beat positions with drum locking applied
    """
    locked_slots = set(slots)  # Start with existing slots

    if not drum_events:
        return locked_slots

    for event in drum_events:
        beat = getattr(event, "beat", None)
        kind = getattr(event, "kind", "")

        if beat is None:
            continue

        # Quantize drum event to nearest subdivision
        subdivision_duration = 1.0 / subdivisions_per_beat
        quantized_beat = round(beat / subdivision_duration) * subdivision_duration

        # Determine lock probability based on drum voice
        lock_prob = 0.0
        if "kick" in kind.lower():
            lock_prob = lock_to_kick
        elif "snare" in kind.lower():
            lock_prob = lock_to_snare
        elif "hat" in kind.lower() or "ride" in kind.lower():
            lock_prob = lock_to_hat

        # Add bass note at this position with given probability
        if lock_prob > 0 and rng.random() < lock_prob:
            locked_slots.add(quantized_beat)

    return locked_slots
