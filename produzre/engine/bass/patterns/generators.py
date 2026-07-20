# produzre/engine/bass/patterns/generators.py
"""Rhythm pattern generators for bass engine."""


def get_rhythm_pattern_anchor(
    slots: list[float],
    beats_per_bar: float,
    subdivisions_per_beat: int = 4,
    walking_quarters: bool = False,
) -> set[float]:
    """Anchor pattern: mostly downbeats (beats 1, 3 in 4/4).

    For walking bass (walking_quarters=True), returns all quarter notes.

    Returns set of eligible beat positions for note placement.
    """
    eligible = set()

    for slot in slots:
        beat_in_bar = slot % beats_per_bar
        subdivision_in_beat = (slot * subdivisions_per_beat) % subdivisions_per_beat

        # Only on beat boundaries (not subdivisions)
        if abs(subdivision_in_beat) < 1e-6:
            # Walking bass: all quarter notes (beats 1, 2, 3, 4 in 4/4)
            if walking_quarters:
                # Check if this is a quarter note boundary
                beat_number = round(beat_in_bar)
                if abs(beat_in_bar - beat_number) < 1e-6:
                    eligible.add(slot)
            else:
                # Standard anchor: downbeat (beat 1)
                if abs(beat_in_bar) < 1e-6:
                    eligible.add(slot)
                # Beat 3 in 4/4
                elif beats_per_bar >= 4.0 and abs(beat_in_bar - 2.0) < 1e-6:
                    eligible.add(slot)
                # 3/4 (waltz): add beat 2 so bars aren't downbeat-only
                elif abs(beats_per_bar - 3.0) < 1e-6 and abs(beat_in_bar - 1.0) < 1e-6:
                    eligible.add(slot)
                # 6/8 counted in 6: second dotted quarter (beat 4)
                elif abs(beats_per_bar - 6.0) < 1e-6 and abs(beat_in_bar - 3.0) < 1e-6:
                    eligible.add(slot)

    return eligible


def get_rhythm_pattern_push(
    slots: list[float],
    beats_per_bar: float,
    chord_changes: list[float],
    subdivisions_per_beat: int = 4,
) -> set[float]:
    """Push pattern: anticipations into chord changes (e.g., 8th note before change).

    Args:
        slots: All subdivision slots
        beats_per_bar: Beats per bar
        chord_changes: List of beat positions where chords change
        subdivisions_per_beat: Subdivisions per beat

    Returns:
        Set of eligible beat positions
    """
    eligible = set()
    anticipation_offset = 0.5  # Half beat before chord change (8th note)

    for slot in slots:
        beat_in_bar = slot % beats_per_bar
        subdivision_in_beat = (slot * subdivisions_per_beat) % subdivisions_per_beat

        # Downbeats
        if abs(beat_in_bar) < 1e-6 and abs(subdivision_in_beat) < 1e-6:
            eligible.add(slot)

        # Anticipations before chord changes
        for chord_beat in chord_changes:
            anticipation_beat = chord_beat - anticipation_offset
            if abs(slot - anticipation_beat) < 1e-6:
                eligible.add(slot)

    return eligible


def get_rhythm_pattern_drive(
    slots: list[float],
    beats_per_bar: float,
    subdivisions_per_beat: int = 4,
) -> set[float]:
    """Drive pattern: 8ths or 16ths with controlled gaps.

    Returns set of eligible beat positions (8th notes, some 16ths).
    """
    eligible = set()

    for slot in slots:
        subdivision_in_beat = (slot * subdivisions_per_beat) % subdivisions_per_beat

        # All 8th notes (subdivisions 0 and 2 of each beat)
        if abs(subdivision_in_beat) < 1e-6 or abs(subdivision_in_beat - 2.0) < 1e-6:
            eligible.add(slot)

        # Some 16th notes (subdivisions 1 and 3) - will be controlled by density
        elif abs(subdivision_in_beat - 1.0) < 1e-6 or abs(subdivision_in_beat - 3.0) < 1e-6:
            eligible.add(slot)

    return eligible


def get_rhythm_pattern_syncopated(
    slots: list[float],
    beats_per_bar: float,
    subdivisions_per_beat: int = 4,
) -> set[float]:
    """Syncopated pattern: offbeat emphasis.

    Returns set of eligible beat positions (offbeats preferred).
    """
    eligible = set()

    for slot in slots:
        beat_in_bar = slot % beats_per_bar
        subdivision_in_beat = (slot * subdivisions_per_beat) % subdivisions_per_beat

        # Downbeat (always include)
        if abs(beat_in_bar) < 1e-6 and abs(subdivision_in_beat) < 1e-6:
            eligible.add(slot)

        # Offbeats: "and" of each beat (subdivision 2)
        if abs(subdivision_in_beat - 2.0) < 1e-6:
            eligible.add(slot)

        # 16th note offbeats (subdivisions 1 and 3)
        if abs(subdivision_in_beat - 1.0) < 1e-6 or abs(subdivision_in_beat - 3.0) < 1e-6:
            eligible.add(slot)

    return eligible


def get_rhythm_pattern_rock_riff(
    slots: list[float], beats_per_bar: float, subdivisions_per_beat: int = 4
) -> set[float]:
    """Two-bar rock cell with pedal anchors and anticipations."""
    first_bar = {0.0, 0.5, 1.5, 2.0, 3.5}
    second_bar = {0.0, 1.0, 1.5, 2.5, 3.0, 3.5}
    eligible = set()
    for slot in slots:
        bar = int(slot // beats_per_bar)
        position = round(slot % beats_per_bar, 3)
        if position in (first_bar if bar % 2 == 0 else second_bar):
            eligible.add(slot)
    return eligible


def get_rhythm_pattern_funk_16ths(
    slots: list[float], beats_per_bar: float, subdivisions_per_beat: int = 4
) -> set[float]:
    """Two-bar syncopated funk cell with deliberate holes around backbeats."""
    first_bar = {0.0, 0.75, 1.5, 2.25, 3.5}
    second_bar = {0.0, 0.5, 1.75, 2.75, 3.25}
    eligible = set()
    for slot in slots:
        bar = int(slot // beats_per_bar)
        position = round(slot % beats_per_bar, 3)
        if position in (first_bar if bar % 2 == 0 else second_bar):
            eligible.add(slot)
    return eligible
