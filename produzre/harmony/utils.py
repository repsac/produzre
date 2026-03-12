from __future__ import annotations

"""Utility functions for harmony planning.

This module contains small helpers used by the harmony planning pipeline to
resolve section timing inputs into a consistent internal representation.

Conventions:
- Produzre's internal time unit is the quarter-note beat.
- Meters are parsed from "N/D" strings into a `Meter` dataclass.
- Sections may specify length either explicitly in beats or implicitly via bars.

These helpers are intentionally conservative and do not attempt to infer complex
musical intent; they primarily standardize inputs for downstream planning.
"""

from typing import List

from ..model import RootConfig, SectionConfig
from .meter import Meter, parse_meter


def resolve_section_meter(cfg: RootConfig, section: SectionConfig) -> Meter:
    """Resolve a section's effective meter (time signature).

    Sections may override the global meter. This helper chooses the effective
    meter for the section and parses it into a `Meter` instance.

    Resolution order:
      1) `section.meter` if provided (e.g., "7/8")
      2) `cfg.song.meter` as the global fallback

    Args:
        cfg: Root configuration providing the global song meter.
        section: Section configuration that may override `meter`.

    Returns:
        Meter: Parsed meter dataclass representing the section's time signature.

    Raises:
        ValueError: If the resolved meter string is not in valid "N/D" form.
    """
    meter_str = section.meter or cfg.song.meter
    return parse_meter(meter_str)


def resolve_total_beats(cfg: RootConfig, section: SectionConfig, meter: Meter) -> float:
    """Resolve a section's total length in quarter-note beats.

    Sections can specify duration in two ways:
      - `section.beats`: an explicit beat length (float/int)
      - `section.bars`: bar count, converted to beats using a beats-per-bar value

    Current conversion behavior:
      - Uses `cfg.song.beats_per_bar` when converting bars to beats.

    Note:
      - The `meter` argument is currently unused in the conversion and is passed
        in to make future meter-derived bar-length support straightforward.
        For example, in the future we may derive beats-per-bar from
        `meter.beats_per_bar` instead of relying on `cfg.song.beats_per_bar`.

    Priority order:
      1) If `section.beats` is not None: return `float(section.beats)`.
      2) Else if `section.bars` is not None: return `section.bars * cfg.song.beats_per_bar`.
      3) Else: return 0.0.

    Args:
        cfg: Root configuration providing global beats-per-bar.
        section: Section configuration providing beats and/or bars.
        meter: Effective meter for the section (reserved for future use).

    Returns:
        float: Section length in quarter-note beats.
    """
    if section.beats is not None:
        return float(section.beats)

    bpb = cfg.song.beats_per_bar
    if section.bars is not None:
        return float(section.bars * bpb)

    return 0.0


def split_progression(prog: str) -> List[str]:
    """Split a Roman numeral progression string into normalized tokens.

    This helper is used for explicit progression overrides provided as strings.

    Behavior:
      - Splits on whitespace.
      - Trims each token.
      - Drops empty tokens.

    Example:
        "i  bVII   VI  i" -> ["i", "bVII", "VI", "i"]

    Args:
        prog: Progression string containing Roman numeral tokens.

    Returns:
        List[str]: Ordered list of Roman numeral tokens.
    """
    return [p.strip() for p in prog.split() if p.strip()]
