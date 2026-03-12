from __future__ import annotations

"""Harmony planning (timing + Roman numeral structure).

This module produces a section-scoped *harmony plan* that describes when each
Roman numeral chord is active across the section timeline.

Scope:
- Timing only. No pitch spelling, voicings, or instrument-specific realization.
- A plan is created per section because meters, lengths, and harmonic rhythm
  may vary across sections.

Inputs:
- Global defaults from `RootConfig.song` (mode, default meter, etc.).
- Per-section overrides from `SectionConfig` (meter, harmony block, bars/beats).

Outputs:
- `HarmonySectionPlan` containing a list of `ChordSlot` entries.

Downstream usage:
- Instrument engines consult chord slots to choose chord tones, bass roots,
  scale degrees, and rhythmic accompaniment patterns.
"""

from dataclasses import dataclass, field
from typing import List, Optional

import logging

from ..model import RootConfig, SectionConfig
from .meter import Meter
from .presets import choose_progression_for_section
from .utils import resolve_section_meter, resolve_total_beats, split_progression


@dataclass
class ChordSlot:
    """A single chord placement within a section.

    A chord slot is defined purely by:
      - its ordinal index within the section
      - a Roman numeral string (e.g., "i", "bVII", "V")
      - a start and end time expressed in quarter-note beats

    Slots are contiguous and non-overlapping within a `HarmonySectionPlan`.

    Attributes:
        index: Sequential slot index starting at 0.
        numeral: Roman numeral label for this slot.
        start_beat: Slot start time in quarter-note beats.
        end_beat: Slot end time in quarter-note beats (exclusive).
    """

    index: int
    numeral: str
    start_beat: float
    end_beat: float


@dataclass
class HarmonySectionPlan:
    """Harmony timing plan for a section.

    The plan is a lightweight structural description of harmony over time.
    It intentionally does not encode pitches; it only states which Roman numeral
    chord is active over which beat range.

    Attributes:
        section_id: Identifier of the section this plan applies to.
        meter: Effective meter for the section.
        total_beats: Total section length in quarter-note beats.
        chord_rate: Harmonic rhythm in beats per chord slot.
        chord_slots: Ordered list of chord slots spanning the section.
    """

    section_id: str
    meter: Meter
    total_beats: float
    chord_rate: float
    chord_slots: List[ChordSlot] = field(default_factory=list)


def build_harmony_plan(
    cfg: RootConfig,
    section: SectionConfig,
    logger: logging.Logger,
) -> Optional[HarmonySectionPlan]:
    """Build a `HarmonySectionPlan` for a single section.

    This function computes a *timing grid* of chord slots across the section
    and assigns a Roman numeral to each slot.

    Progression selection:
      1) If `section.harmony.progression` is provided and contains usable tokens,
         those numerals are used as an explicit override.
      2) Otherwise, `choose_progression_for_section()` is used to select a
         preset progression based on `(cfg.song.mode, section.type)`.

    Timing resolution:
      - The effective meter is resolved via `resolve_section_meter()`.
      - The section length in beats is computed via `resolve_total_beats()`.
      - The harmonic rhythm is taken from `section.harmony.chord_rate`.
        If `chord_rate <= 0`, it is treated as "one chord for the entire section".

    Edge cases:
      - If the section has no harmony block, returns None.
      - If timing is non-positive, returns an empty plan (no slots) instead of None.
      - If no usable numerals can be resolved, returns an empty plan and logs a warning.

    Args:
        cfg: Global configuration (mode, defaults, etc.).
        section: Section configuration to plan.
        logger: Logger for informational and warning messages.

    Returns:
        Optional[HarmonySectionPlan]: A populated plan, an empty plan (no slots)
        when timing/progression is unusable, or None when harmony is disabled.
    """
    if not section.harmony:
        return None

    meter = resolve_section_meter(cfg, section)
    total_beats = resolve_total_beats(cfg, section, meter)

    chord_rate = float(section.harmony.chord_rate)
    if chord_rate <= 0:
        chord_rate = float(total_beats) if total_beats > 0 else 0.0

    # If we have no usable timing, return an empty plan rather than None.
    if total_beats <= 0 or chord_rate <= 0:
        return HarmonySectionPlan(
            section_id=section.id,
            meter=meter,
            total_beats=max(float(total_beats), 0.0),
            chord_rate=chord_rate,
            chord_slots=[],
        )

    import ast

    explicit_prog = section.harmony.progression or ""

    # Handle both string and list format for progression
    if isinstance(explicit_prog, list):
        # Already a list of numerals, use directly
        numerals = [str(n).strip() for n in explicit_prog if n]
    elif isinstance(explicit_prog, str) and explicit_prog.strip().startswith('[') and explicit_prog.strip().endswith(']'):
        # String representation of a list (e.g., "['I', 'IV', 'V']")
        # This happens when YAML list format is used but gets converted to string during config loading
        # Parse it as a Python literal to extract the actual list elements
        try:
            parsed_list = ast.literal_eval(explicit_prog)
            if isinstance(parsed_list, list):
                numerals = [str(n).strip() for n in parsed_list if n]
            else:
                # Fallback to split if literal_eval didn't return a list
                numerals = split_progression(explicit_prog)
        except (ValueError, SyntaxError):
            # If parsing fails, fall back to whitespace splitting
            numerals = split_progression(explicit_prog)
    else:
        # Regular string format, split on whitespace
        numerals = split_progression(explicit_prog)

    if numerals:
        logger.info(
            "Section '%s': using explicit harmony progression: %s",
            section.id,
            " ".join(numerals),
        )
    else:
        # --- Harmony recipe resolution ---
        _recipes: dict = {}
        if hasattr(cfg, "raw") and isinstance(getattr(cfg, "raw", None), dict):
            _recipes = cfg.raw.get("_recipes", {}).get("harmony", {})

        if _recipes:
            from ..config.recipes import resolve_recipe_name as _resolve_recipe

            _genre = getattr(cfg.song, "genre", None)
            _bpm = float(getattr(cfg.song, "bpm", 120.0))
            _meter_str = str(getattr(cfg.song, "meter", None) or "4/4")

            _recipe_name = _resolve_recipe(
                instrument="harmony",
                genre=_genre,
                section_type=section.type,
                intensity=0.5,
                bpm=_bpm,
                time_signature=_meter_str,
                instrument_recipe=None,
                section_recipe=None,
                recipes=_recipes,
            )

            if _recipe_name and _recipe_name in _recipes:
                _recipe = _recipes[_recipe_name]
                _progs = _recipe.get("progressions", {})
                _mode = (cfg.song.mode or "minor").strip().lower()
                _sec_type = section.type.strip().lower()

                _found = (
                    _progs.get(_mode, {}).get(_sec_type)
                    or _progs.get(_mode, {}).get("default")
                    or _progs.get("default", {}).get(_sec_type)
                    or _progs.get("default", {}).get("default")
                )
                if _found and isinstance(_found, list):
                    numerals = [str(n).strip() for n in _found if n]
                    logger.info(
                        "Section '%s': using harmony recipe '%s' (mode=%s, type=%s): %s",
                        section.id, _recipe_name, _mode, _sec_type,
                        " ".join(numerals),
                    )

        # Fall back to presets if no recipe matched.
        if not numerals:
            numerals = choose_progression_for_section(
                song_mode=cfg.song.mode,
                section_type=section.type,
                section_id=section.id,
                explicit=None,
                logger=logger,
            )

    if not numerals:
        logger.warning(
            "Section '%s': no usable numerals after preset resolution; returning empty harmony plan.",
            section.id,
        )
        return HarmonySectionPlan(
            section_id=section.id,
            meter=meter,
            total_beats=float(total_beats),
            chord_rate=chord_rate,
            chord_slots=[],
        )

    chord_slots: List[ChordSlot] = []
    current_beat = 0.0
    idx = 0
    num_idx = 0
    num_len = len(numerals)

    while current_beat < total_beats:
        numeral = numerals[num_idx % num_len]
        start = float(current_beat)
        end = min(start + chord_rate, float(total_beats))

        chord_slots.append(
            ChordSlot(
                index=idx,
                numeral=numeral,
                start_beat=start,
                end_beat=float(end),
            )
        )

        idx += 1
        num_idx += 1
        current_beat = float(end)

    return HarmonySectionPlan(
        section_id=section.id,
        meter=meter,
        total_beats=float(total_beats),
        chord_rate=chord_rate,
        chord_slots=chord_slots,
    )
