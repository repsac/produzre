from __future__ import annotations

"""Section scaffolding helpers.

This module builds the per-section "scaffold" used by the orchestration plan:

- Harmony plan: Roman-numeral chord slots across the section timeline.
- Meter: The section's effective time signature.
- Rhythm grid: A simple beat subdivision grid used for event placement.
- Total beats: The section duration expressed in quarter-note beats.

The scaffold is intentionally generic:
- `hplan` is typed as `object` to avoid tight coupling to harmony internals.
- `rhythm_grid` is typed as `object` to avoid tight coupling to rhythm internals.

Time units:
- All timing values are expressed in quarter-note beats.
"""

import logging
from typing import Optional

from ..harmony import build_harmony_plan, parse_meter, Meter
from ..rhythm import create_basic_rhythm_grid
from ..model import RootConfig


def build_section_scaffold(
    cfg: RootConfig,
    sec,
    logger: logging.Logger,
) -> tuple[Optional[object], Meter, object, float]:
    """Build harmony + rhythm scaffolding for a single section.

    This helper is used by the planning phase to compute reusable, per-section
    structural data.

    Behavior:
      - Calls `build_harmony_plan(cfg, sec, logger)`.
      - If harmony is disabled/absent (hplan is None):
          * Logs that no harmony exists for the section.
          * Computes `total_beats` using `sec.total_beats(cfg.song.beats_per_bar)`.
          * Resolves the meter from `sec.meter` (falling back to `cfg.song.meter`).
          * Creates a basic rhythm grid from (meter, total_beats).
      - If harmony exists:
          * Uses the harmony plan's `meter` and `total_beats`.
          * Logs a compact harmony summary (slot count, chord_rate, meter).
          * Creates a basic rhythm grid from (meter, total_beats).

    Error handling:
      - If meter parsing fails in the no-harmony path, defaults to 4/4.

    Args:
        cfg: Root configuration (song defaults and mode).
        sec: Section configuration object.
        logger: Logger used for informational output.

    Returns:
        tuple[Optional[object], Meter, object, float]:
            - hplan: Harmony plan object, or None when harmony is disabled/absent.
            - section_meter: Effective meter for the section.
            - rhythm_grid: Rhythm grid object for beat/subdivision placement.
            - total_beats: Total section duration in quarter-note beats.
    """
    hplan = build_harmony_plan(cfg, sec, logger)

    section_meter: Meter
    if hplan is None:
        logger.info("  No harmony defined for this section.")
        total_beats = sec.total_beats(cfg.song.beats_per_bar)
        try:
            section_meter = parse_meter(sec.meter or cfg.song.meter)
        except ValueError:
            section_meter = Meter(numerator=4, denominator=4)

        logger.info(
            "  Length: %.2f beats (meter %d/%d)",
            total_beats,
            section_meter.numerator,
            section_meter.denominator,
        )
        rgrid = create_basic_rhythm_grid(section_meter, total_beats)
        return None, section_meter, rgrid, total_beats

    logger.info(
        "  Harmony: %d chord slots, chord_rate=%.2f, total_beats=%.2f, meter=%d/%d",
        len(hplan.chord_slots),
        hplan.chord_rate,
        hplan.total_beats,
        hplan.meter.numerator,
        hplan.meter.denominator,
    )

    section_meter = hplan.meter
    total_beats = hplan.total_beats
    rgrid = create_basic_rhythm_grid(section_meter, total_beats)
    return hplan, section_meter, rgrid, total_beats
