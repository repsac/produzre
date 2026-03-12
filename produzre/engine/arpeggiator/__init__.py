"""Example arpeggiator engine for Produzre.

This is a simple example engine that demonstrates:
- Reading harmony plan for chord structure
- Using rhythm grid for timing
- Deterministic RNG for variations
- Proper timeline event generation
- Engine configuration parameters

The arpeggiator plays ascending/descending patterns through chord tones
based on the harmony plan.
"""

from typing import Any, Optional
import logging

# Module-level defaults (used if not specified in engines.yml)
ENGINE_DEFAULT_PRIORITY = 6
ENGINE_DEFAULT_CHANNEL = 6
ENGINE_DEFAULT_PROGRAM = 1  # GM Bright Acoustic Piano


def render_into_timeline(*args: Any, **kwargs: Any) -> None:
    """Render arpeggiator patterns based on harmony plan.

    Plays ascending or descending arpeggios through chord tones at
    16th note resolution.

    Args (all via kwargs):
        cfg: RootConfig - Global configuration
        section: SectionConfig - Current section
        instrument_cfg: InstrumentConfig - Per-section settings
        harmony_plan: Optional[HarmonySectionPlan] - Chord structure
        rhythm_grid: RhythmGrid - Beat subdivision grid
        section_start_beat: float - Song-relative start beat
        rng: random.Random - Deterministic RNG
        timeline: InstrumentTimeline - Timeline to add events to
        logger: logging.Logger - For debug output
    """
    if args:
        raise TypeError("arpeggiator.render_into_timeline only supports keyword arguments")

    # Extract parameters
    cfg = kwargs.get("cfg")
    section = kwargs.get("section")
    harmony_plan = kwargs.get("harmony_plan")
    rhythm_grid = kwargs.get("rhythm_grid")
    section_start_beat = kwargs.get("section_start_beat", 0.0)
    timeline = kwargs.get("timeline")
    instrument_cfg = kwargs.get("instrument_cfg")
    rng = kwargs.get("rng")
    logger = kwargs.get("logger")

    # Check if we have harmony to arpeggiate
    if harmony_plan is None or not harmony_plan.chord_slots:
        if logger:
            logger.debug("arpeggiator: no harmony plan, skipping")
        return

    # Get configuration parameters
    intensity = float(getattr(instrument_cfg, "intensity", 0.5))

    # Get extra params for arpeggiator-specific settings
    extra = getattr(instrument_cfg, "extra", {})
    pattern = extra.get("pattern", "up")  # "up", "down", "up_down"
    note_duration_beats = float(extra.get("note_duration", 0.25))  # 16th note default

    # Calculate velocity from intensity
    base_velocity = int(60 + (intensity * 40))  # 60-100 range

    event_count = 0

    # Process each chord slot
    for slot in harmony_plan.chord_slots:
        # Get chord tones for this slot
        chord_tones = _get_chord_tones_from_numeral(
            slot.numeral,
            cfg.song.key,
            cfg.song.mode,
        )

        # Determine arpeggio pattern
        arpeggio_notes = _create_arpeggio_pattern(chord_tones, pattern)

        # Calculate how many notes fit in this chord slot
        slot_duration = slot.end_beat - slot.start_beat
        num_notes = int(slot_duration / note_duration_beats)

        # Generate arpeggio events
        for i in range(num_notes):
            note_idx = i % len(arpeggio_notes)
            pitch = arpeggio_notes[note_idx]

            # Add slight velocity variation using deterministic RNG
            velocity_variation = int((rng.random() - 0.5) * 10)
            velocity = max(40, min(100, base_velocity + velocity_variation))

            # Calculate beat position
            local_beat = slot.start_beat + (i * note_duration_beats)

            # Add note to timeline
            timeline.add_note(
                start_beat=section_start_beat + local_beat,
                duration_beats=note_duration_beats * 0.9,  # Slight gap between notes
                pitch=pitch,
                velocity=velocity,
            )
            event_count += 1

    if logger:
        logger.info(
            f"arpeggiator: generated {event_count} events "
            f"(intensity={intensity:.2f}, pattern={pattern})"
        )


def _get_chord_tones_from_numeral(
    numeral: str,
    key: str,
    mode: Optional[str] = None,
) -> list[int]:
    """Extract chord tones (MIDI note numbers) from a Roman numeral.

    This is a simplified implementation for demonstration purposes.
    Production code should use produzre.engine.bass.harmony for full
    mode support and proper voice leading.

    Args:
        numeral: Roman numeral (e.g., "I", "bVII", "vi")
        key: Song key (e.g., "C", "E")
        mode: Song mode (e.g., "ionian", "dorian")

    Returns:
        List of MIDI note numbers for the chord (root, third, fifth)
    """
    # Simple key-to-MIDI mapping (bass register)
    KEY_TO_MIDI = {
        "C": 48, "C#": 49, "Db": 49,
        "D": 50, "D#": 51, "Eb": 51,
        "E": 52,
        "F": 53, "F#": 54, "Gb": 54,
        "G": 55, "G#": 56, "Ab": 56,
        "A": 57, "A#": 58, "Bb": 58,
        "B": 59,
    }

    # Major scale degree offsets
    DEGREE_OFFSETS = [0, 2, 4, 5, 7, 9, 11]

    # Parse Roman numeral to degree (simplified)
    numeral_clean = numeral.strip().upper().lstrip("B#")
    roman_map = {"I": 0, "II": 1, "III": 2, "IV": 3,
                 "V": 4, "VI": 5, "VII": 6}

    degree_index = roman_map.get(numeral_clean, 0)

    # Get tonic MIDI note
    tonic = KEY_TO_MIDI.get(key.strip().upper(), 48)

    # Calculate root pitch
    root = tonic + DEGREE_OFFSETS[degree_index]

    # Determine chord quality (major/minor)
    is_minor = numeral.strip().lower() == numeral.strip()
    third_offset = 3 if is_minor else 4

    # Build triad
    chord_tones = [
        root,
        root + third_offset,  # Third
        root + 7,             # Fifth
    ]

    return chord_tones


def _create_arpeggio_pattern(chord_tones: list[int], pattern: str) -> list[int]:
    """Create arpeggio pattern from chord tones.

    Args:
        chord_tones: List of MIDI note numbers
        pattern: "up", "down", or "up_down"

    Returns:
        List of MIDI notes in arpeggio order
    """
    if pattern == "down":
        return sorted(chord_tones, reverse=True)
    elif pattern == "up_down":
        ascending = sorted(chord_tones)
        descending = sorted(chord_tones, reverse=True)[1:-1]  # Exclude endpoints
        return ascending + descending
    else:  # "up" (default)
        return sorted(chord_tones)


# Example contribute_plan function (optional - not used by arpeggiator)
# Uncomment to see how to export structural data

# def contribute_plan(*args: Any, **kwargs: Any) -> None:
#     """Example: Export arpeggio pattern info to plan (optional).
#
#     This demonstrates how to share data with other engines via
#     the PerformancePlan.
#     """
#     if args:
#         raise TypeError("arpeggiator.contribute_plan only supports keyword arguments")
#
#     plan = kwargs.get("plan")
#     section_ctx = kwargs.get("section_ctx", {})
#     logger = kwargs.get("logger")
#
#     if plan is None:
#         return
#
#     # Extract section info
#     section = section_ctx.get("section")
#     section_id = section.id if section else "unknown"
#
#     # Export pattern info for other engines
#     plan.set(f"arpeggiator.pattern.{section_id}", {
#         "pattern": "up",
#         "note_duration": 0.25,
#     })
#
#     if logger:
#         logger.debug(f"[ARPEGGIATOR] Exported pattern info for section '{section_id}'")
