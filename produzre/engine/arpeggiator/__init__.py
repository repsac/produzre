"""Phrase-aware arpeggiator with voice-led melodic apex notes."""

from collections.abc import Mapping
from typing import Any, Optional
import logging

from ...melody import chord_pitch_classes, guide_pitch_at

# Module-level defaults (used if not specified in engines.yml)
ENGINE_DEFAULT_PRIORITY = 6
ENGINE_DEFAULT_CHANNEL = 6
ENGINE_DEFAULT_PROGRAM = 1  # GM Bright Acoustic Piano


def render_into_timeline(*args: Any, **kwargs: Any) -> None:
    """Render arpeggios as evolving phrases rather than repeated triad loops.

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

    # Fail fast on a missing RNG instead of crashing mid-render.
    if rng is None:
        raise TypeError(
            "arpeggiator.render_into_timeline requires an 'rng' (random.Random); got None"
        )

    # Check if we have harmony to arpeggiate
    if harmony_plan is None or not harmony_plan.chord_slots:
        if logger:
            logger.debug("arpeggiator: no harmony plan, skipping")
        return

    # Get configuration parameters. The orchestrator may deliver either an
    # InstrumentConfig dataclass or a plain dict (e.g. merged _effective
    # configs) — support both like other engines.
    if isinstance(instrument_cfg, Mapping):
        intensity = instrument_cfg.get("intensity")
        extra = instrument_cfg.get("extra") or instrument_cfg.get("params") or {}
        if not isinstance(extra, Mapping):
            extra = {}
    else:
        intensity = getattr(instrument_cfg, "intensity", None)
        extra = getattr(instrument_cfg, "extra", {}) or {}
        if not isinstance(extra, Mapping):
            extra = {}

    intensity = float(intensity) if intensity is not None else 0.5

    pattern = str(extra.get("pattern", "phrase")).lower()
    note_duration_beats = max(0.125, float(extra.get("note_duration", 0.5)))
    rest_probability = max(0.0, min(0.65, float(extra.get("rest_probability", 0.08))))
    octave_range = max(1, min(3, int(extra.get("octave_range", 2))))
    legacy_pattern = pattern in {"up", "down", "up_down"}
    if legacy_pattern and "rest_probability" not in extra:
        rest_probability = 0.0

    # Calculate velocity from intensity
    base_velocity = int(60 + (intensity * 40))  # 60-100 range

    event_count = 0
    previous_pitch = None
    plan = kwargs.get("plan")
    melody_guide = None
    if plan is not None and hasattr(plan, "get"):
        section_id = getattr(section, "id", "")
        melody_guide = plan.get(f"melody.guide.{section_id}") or plan.get("melody.guide")

    # Resolve key/mode with section overrides falling back to song defaults.
    key = getattr(section, "key", None) or cfg.song.key
    mode = getattr(section, "mode", None) or cfg.song.mode

    # Process each chord slot
    for slot_index, slot in enumerate(harmony_plan.chord_slots):
        # Get chord tones for this slot
        chord_tones = _get_chord_tones_from_numeral(
            slot.numeral,
            key,
            mode,
        )

        expanded = sorted({tone + 12 * octave for tone in chord_tones for octave in range(octave_range)})
        slot_pattern = pattern
        if pattern in {"phrase", "cinematic"}:
            slot_pattern = ("up", "up_down", "down", "up_down")[slot_index % 4]
        arpeggio_notes = _create_arpeggio_pattern(expanded, slot_pattern)
        if pattern == "ostinato":
            arpeggio_notes = [expanded[0], expanded[min(2, len(expanded) - 1)], expanded[1], expanded[-1]]

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

            # Every cycle's apex follows the shared melody. Other notes retain
            # the chordal pattern, making this a countermoving texture rather
            # than a doubled lead line.
            is_apex = note_idx == len(arpeggio_notes) - 1
            if is_apex and melody_guide is not None:
                guided = guide_pitch_at(
                    melody_guide, local_beat, min(expanded), max(expanded) + 7,
                    previous=previous_pitch or pitch,
                )
                if guided is not None:
                    pitch = guided

            phrase_edge = i == num_notes - 1
            if not phrase_edge and rng.random() < rest_probability:
                continue

            # Accented bass arrivals and softer upper notes create a hand-like
            # dynamic hierarchy instead of independent random velocities.
            if note_idx == 0:
                velocity += 8
            elif is_apex:
                velocity += 3
            velocity = max(35, min(112, velocity))
            gate = 0.82 if pattern in {"ostinato", "cinematic"} else 0.9

            # Add note to timeline
            timeline.add_note(
                start_beat=section_start_beat + local_beat,
                duration_beats=min(note_duration_beats * gate, slot.end_beat - local_beat),
                pitch=pitch,
                velocity=velocity,
                kind="arpeggio_apex" if is_apex else "arpeggio",
            )
            event_count += 1
            previous_pitch = pitch

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
    """Extract mode-aware chord tones (MIDI note numbers) from a numeral.

    Args:
        numeral: Roman numeral (e.g., "I", "bVII", "vi")
        key: Song key (e.g., "C", "E")
        mode: Song mode (e.g., "ionian", "dorian")

    Returns:
        List of MIDI note numbers for the chord (root, third, fifth)
    """
    # Simple key-to-MIDI mapping (bass register).
    # Keys are normalized: note letter uppercased, accidental lowercased, so
    # flat keys like "Eb"/"eb"/"EB" all resolve correctly.
    KEY_TO_MIDI = {
        "C": 48, "C#": 49, "Db": 49,
        "D": 50, "D#": 51, "Eb": 51,
        "E": 52,
        "F": 53, "F#": 54, "Gb": 54,
        "G": 55, "G#": 56, "Ab": 56,
        "A": 57, "A#": 58, "Bb": 58,
        "B": 59,
    }

    # Get tonic MIDI note (normalize "eb"/"EB" -> "Eb").
    key_norm = str(key or "").strip()
    if key_norm:
        key_norm = key_norm[0].upper() + key_norm[1:].lower()
    tonic = KEY_TO_MIDI.get(key_norm, 48)
    pcs = chord_pitch_classes(numeral, key_norm, mode or "major")
    root = tonic + ((pcs[0] - tonic) % 12)
    return [root + ((pc - pcs[0]) % 12) for pc in pcs]


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


def contribute_plan(*args: Any, **kwargs: Any) -> None:
    """Publish arpeggiator texture intent for ensemble coordination."""
    if args:
        raise TypeError("arpeggiator.contribute_plan only supports keyword arguments")
    plan = kwargs.get("plan")
    section_ctx = kwargs.get("section_ctx", {})
    if plan is None:
        return
    section = section_ctx.get("section")
    instrument_cfg = section_ctx.get("instrument_cfg")
    if section is None:
        return
    if isinstance(instrument_cfg, Mapping):
        extra = instrument_cfg.get("extra") or instrument_cfg.get("params") or {}
    else:
        extra = getattr(instrument_cfg, "extra", {}) or {}
    payload = {
        "pattern": str(extra.get("pattern", "phrase")),
        "note_duration": float(extra.get("note_duration", 0.5)),
        "role": "moving_texture",
    }
    plan.set(f"arpeggiator.pattern.{section.id}", payload)
    plan.set("arpeggiator.pattern", payload)
