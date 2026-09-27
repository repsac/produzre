"""Phrase-aware arpeggiator with voice-led melodic apex notes."""

from collections.abc import Mapping
from typing import Any, Optional
import logging
import math

from ...harmony.spelling import _parse_numeral, chord_intervals
from ...melody import chord_pitch_classes, guide_pitch_at

# Module-level defaults (used if not specified in engines.yml)
ENGINE_DEFAULT_PRIORITY = 6
ENGINE_DEFAULT_CHANNEL = 6
ENGINE_DEFAULT_PROGRAM = 1  # GM Bright Acoustic Piano

# Patterns whose cycle apex follows the shared melody guide. `phrase` and
# `cinematic` are the evolving, phrase-shaped figures; `up`, `down`,
# `up_down` and `ostinato` are fixed figures and keep their own shape.
_GUIDED_PATTERNS = {"phrase", "cinematic"}


def _flat_params(instrument_cfg: Any) -> dict:
    """Engine params from either config shape, flattening one nested level.

    The loader can nest the user's params under ``extra.extra`` (persona keys
    then sit at the top); the user's nested values win.
    """
    if isinstance(instrument_cfg, Mapping):
        raw = instrument_cfg.get("extra") or instrument_cfg.get("params") or {}
    else:
        raw = getattr(instrument_cfg, "extra", {}) or {}
    if not isinstance(raw, Mapping):
        return {}
    out = {k: v for k, v in raw.items() if k != "extra"}
    if isinstance(raw.get("extra"), Mapping):
        out.update(raw["extra"])
    return out


def _base_velocity(intensity: float) -> int:
    """Velocity for an intensity: about 65 at 0.5, 93 at 0.9, 100 at 1.

    The range is as wide as the lead's, so a quiet verse and a full chorus
    sound different (the old 60-100 mapping left 0.55 and 0.9 about 14
    velocity units apart).
    """
    return int(round(30 + 70 * max(0.0, min(float(intensity), 1.25))))


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
    # configs): support both like other engines.
    if isinstance(instrument_cfg, Mapping):
        intensity = instrument_cfg.get("intensity")
    else:
        intensity = getattr(instrument_cfg, "intensity", None)
    extra = _flat_params(instrument_cfg)

    # Instrument intensity overrides the section's resolved intensity (which
    # carries the section type's level and the rise on repeats).
    if intensity is None:
        intensity = getattr(section, "intensity", None)
    intensity = float(intensity) if intensity is not None else 0.5

    pattern = str(extra.get("pattern", "phrase")).lower()
    note_duration_beats = max(0.125, float(extra.get("note_duration", 0.5)))
    rest_probability = max(0.0, min(0.65, float(extra.get("rest_probability", 0.08))))
    octave_range = max(1, min(3, int(extra.get("octave_range", 2))))
    legacy_pattern = pattern in {"up", "down", "up_down"}
    if legacy_pattern and "rest_probability" not in extra:
        rest_probability = 0.0

    base_velocity = _base_velocity(intensity)
    beats_per_bar = float(getattr(rhythm_grid, "beats_per_bar", None)
                          or getattr(getattr(harmony_plan, "meter", None), "beats_per_bar", None)
                          or 4.0)
    groups = None
    if cfg is not None and section is not None:
        try:
            from ...composer.song import section_groups

            groups = section_groups(cfg, section, getattr(harmony_plan, "meter", None))
        except Exception:
            groups = None
    from ...composer.theory import metric_weight

    event_count = 0
    previous_pitch = None
    plan = kwargs.get("plan")
    melody_guide = None
    if plan is not None and hasattr(plan, "get") and pattern in _GUIDED_PATTERNS:
        section_id = getattr(section, "id", "")
        melody_guide = plan.get(f"melody.guide.{section_id}") or plan.get("melody.guide")

    # Resolve key/mode with section overrides falling back to song defaults.
    key = getattr(section, "key", None) or cfg.song.key
    mode = getattr(section, "mode", None) or cfg.song.mode

    # Process each chord slot
    for slot_index, slot in enumerate(harmony_plan.chord_slots):
        # Every chord tone the harmony names: triad, seventh, and extensions.
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
        # The apex is the cycle's highest note, wherever the figure puts it
        # (the middle of up_down, the head of down).
        apex_idx = arpeggio_notes.index(max(arpeggio_notes))

        # Calculate how many notes fit in this chord slot
        slot_duration = slot.end_beat - slot.start_beat
        num_notes = max(0, math.ceil(slot_duration / note_duration_beats - 1e-9))

        # Generate arpeggio events
        for i in range(num_notes):
            note_idx = i % len(arpeggio_notes)
            pitch = arpeggio_notes[note_idx]

            # Add slight velocity variation using deterministic RNG
            velocity_variation = int((rng.random() - 0.5) * 10)
            velocity = base_velocity + velocity_variation

            # Calculate beat position
            local_beat = slot.start_beat + (i * note_duration_beats)

            # In the guided patterns every cycle's apex follows the shared
            # melody. Other notes retain the chordal pattern, making this a
            # countermoving texture rather than a doubled lead line.
            is_apex = note_idx == apex_idx
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
            # dynamic hierarchy, and the bar's strong beats lean in the way a
            # player's hand does.
            if note_idx == 0:
                velocity += 8
            elif is_apex:
                velocity += 3
            if beats_per_bar > 0:
                mw = metric_weight(local_beat % beats_per_bar, beats_per_bar, groups)
                velocity += int(round(8 * (mw - 0.5)))
            velocity = max(20, min(120, velocity))
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


def chord_intervals_with_extensions(numeral: str) -> tuple[int, ...]:
    """Semitones above the root for every tone a numeral names.

    The shared spelling (``harmony.spelling.chord_intervals``) gives the
    triad and seventh. This adds what an arpeggio can spell out: sixths
    (``6``, ``69``), ninths (``9``, ``add9``, ``b9``, ``#9``), elevenths
    (``11``, ``#11``), thirteenths (``13``, ``b13``) and a flat fifth
    (``7b5``). A 9, 11 or 13 without ``add`` (or the 6 of a 6/9) implies
    the seventh, as in chord symbols; a major or dominant 11 drops the third it would clash
    with. Extensions sit above the octave (a ninth is 14, not 2), the way a
    keyboard player voices them.
    """
    _, _, roman, suffix = _parse_numeral(numeral)
    base = list(chord_intervals(numeral))
    s = suffix.replace("♭", "b").replace("♯", "#")
    added = "add" in s
    # Strip the numbers that belong to the seventh or alterations before
    # looking for plain extensions ("maj7#11" has no plain 7-free 11).
    has13 = "13" in s
    has11 = "11" in s
    rest = s.replace("13", "").replace("11", "")
    has9 = "9" in rest
    has6 = "6" in rest.replace("69", "6")
    if (has9 or has11 or has13) and not (added or has6) and len(base) == 3:
        base.append(11 if "maj" in s else 10)
    if "b5" in s and 7 in base:
        base[base.index(7)] = 6
    ext: list[int] = []
    if has6:
        ext.append(9)
    if has9 or has11 or has13:
        if "b9" in s:
            ext.append(13)
        elif "#9" in s:
            ext.append(15)
        elif has9 or (has11 and not added) or (has13 and not added):
            ext.append(14)
    if has11:
        ext.append(18 if "#11" in s else 17)
        if "#11" not in s and not roman.islower() and 4 in base:
            base.remove(4)  # a major or dominant 11 is voiced without the third
    if has13:
        ext.append(20 if "b13" in s else 21)
    return tuple(sorted(set(base) | set(ext)))


def _get_chord_tones_from_numeral(
    numeral: str,
    key: str,
    mode: Optional[str] = None,
) -> list[int]:
    """Extract mode-aware chord tones (MIDI note numbers) from a numeral.

    Args:
        numeral: Roman numeral (e.g., "I", "bVII", "vi", "V7", "ii9")
        key: Song key (e.g., "C", "E")
        mode: Song mode (e.g., "ionian", "dorian")

    Returns:
        MIDI note numbers for the chord, root first: the triad, then the
        seventh and any extensions the numeral names (see
        ``chord_intervals_with_extensions``).
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
    return [root + interval for interval in chord_intervals_with_extensions(numeral)]


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
    extra = _flat_params(instrument_cfg)
    payload = {
        "pattern": str(extra.get("pattern", "phrase")),
        "note_duration": float(extra.get("note_duration", 0.5)),
        "role": "moving_texture",
    }
    plan.set(f"arpeggiator.pattern.{section.id}", payload)
    plan.set("arpeggiator.pattern", payload)
