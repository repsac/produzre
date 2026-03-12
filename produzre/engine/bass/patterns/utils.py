# produzre/engine/bass/patterns/utils.py
"""Rhythm pattern utilities for bass engine."""


def create_subdivision_slots(total_beats: float, subdivisions_per_beat: int = 4) -> list[float]:
    """Create a list of subdivision time points (e.g., 16th notes).

    Args:
        total_beats: Total beats in the section
        subdivisions_per_beat: Number of subdivisions per beat (4 = 16th notes, 2 = 8th notes)

    Returns:
        List of beat positions for each subdivision slot
    """
    slots = []
    num_subdivisions = int(total_beats * subdivisions_per_beat)
    subdivision_duration = 1.0 / subdivisions_per_beat

    for i in range(num_subdivisions):
        beat_position = i * subdivision_duration
        slots.append(beat_position)

    return slots
