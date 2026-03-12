from __future__ import annotations

"""Logging helpers for build summaries.

This module contains small, presentation-focused helpers used by orchestration
and CLI commands to log:

- Per-section timing (start/end/length)
- Total song duration in beats, approximate bars, and optional clock time
- Per-instrument event counts

These functions are intentionally side-effect free beyond writing to the
provided logger.
"""

import logging

from ..timeline import InstrumentTimeline, SectionTiming


def _format_bars_beats(beats: float, beats_per_bar: float) -> tuple[int, float]:
    """Convert a beat length into (whole_bars, remaining_beats).

    Produzre measures time internally in quarter-note beats. For reporting and
    user-facing logs, it is often helpful to express a duration as whole bars
    plus a remainder.

    Args:
        beats: Duration in quarter-note beats.
        beats_per_bar: Beats per bar (quarter-note beat units). If <= 0,
            the function returns (0, beats).

    Returns:
        tuple[int, float]:
            - whole_bars: floor(beats / beats_per_bar)
            - remaining_beats: beats - (whole_bars * beats_per_bar)

    Notes:
        Very small floating point remainders are snapped to 0.0 for cleaner logs.
    """
    if beats_per_bar <= 0:
        return 0, float(beats)
    bars = int(beats // beats_per_bar)
    rem = float(beats) - (bars * float(beats_per_bar))
    if abs(rem) < 1e-9:
        rem = 0.0
    return bars, rem


def _format_mmss(seconds: float) -> str:
    """Format seconds as "mm:ss.s" (one decimal).

    Args:
        seconds: Duration in seconds.

    Returns:
        str: Formatted duration string. Negative inputs are clamped to 0.0.
    """
    if seconds < 0:
        seconds = 0.0
    m = int(seconds // 60)
    s = seconds - (m * 60)
    return f"{m:02d}:{s:04.1f}s"


def log_section_timings(
    logger: logging.Logger,
    section_timings: list[SectionTiming],
    *,
    bpm: float | None = None,
) -> None:
    """Log per-section timing and total song length.

    This helper emits a compact timing report suitable for dry-run output and
    debugging.

    For each section, it logs:
      - section id + type
      - start and end beats (song-relative)
      - length in beats
      - length expressed as (bars + remainder beats) using that section's
        `beats_per_bar`
      - optional time estimate (mm:ss.s) when BPM is provided

    Totals:
      - `total_beats` is the sum of section lengths.
      - `total_bar_equiv` is the sum of (section_beats / section_beats_per_bar),
        which provides a useful mixed-meter-friendly "bar equivalent" measure.
      - An additional approximate (bars + beats) line is computed using the
        average beats-per-bar across sections.

    Args:
        logger: Logger used to emit INFO lines.
        section_timings: Ordered list of `SectionTiming` windows.
        bpm: Optional tempo in beats per minute; when provided, an approximate
            time estimate is logged.

    Returns:
        None
    """
    if not section_timings:
        return

    logger.info("Section timing summary:")

    total_beats = 0.0
    total_bar_equiv = 0.0

    for st in section_timings:
        length_beats = float(st.length_beats)
        total_beats += length_beats

        bpb = float(getattr(st, "beats_per_bar", 4.0) or 4.0)
        bars_whole, beats_rem = _format_bars_beats(length_beats, bpb)
        total_bar_equiv += (length_beats / bpb) if bpb > 0 else 0.0

        if bpm and bpm > 0:
            sec = (length_beats / float(bpm)) * 60.0
            logger.info(
                "  %s (%s): start=%.2f end=%.2f len=%.2f beats (%d bars + %.2f beats @ %.2f/b) ≈ %s",
                st.id, st.type, st.start_beat, st.end_beat, length_beats,
                bars_whole, beats_rem, bpb, _format_mmss(sec),
            )
        else:
            logger.info(
                "  %s (%s): start=%.2f end=%.2f len=%.2f beats (%d bars + %.2f beats @ %.2f/b)",
                st.id, st.type, st.start_beat, st.end_beat, length_beats,
                bars_whole, beats_rem, bpb,
            )

    # Totals
    avg_bpb = float(
        sum(float(getattr(st, "beats_per_bar", 4.0) or 4.0) for st in section_timings)
        / len(section_timings)
    )
    total_bars_whole, total_beats_rem = _format_bars_beats(total_beats, avg_bpb)

    if bpm and bpm > 0:
        total_sec = (total_beats / float(bpm)) * 60.0
        logger.info(
            "Total song length: %.2f beats total (≈ %.2f bar-equivalents) ≈ %s",
            total_beats, total_bar_equiv, _format_mmss(total_sec),
        )
    else:
        logger.info(
            "Total song length: %.2f beats total (≈ %.2f bar-equivalents)",
            total_beats, total_bar_equiv,
        )

    logger.info(
        "Total song length (approx bars): %d bars + %.2f beats (avg beats_per_bar=%.2f)",
        total_bars_whole, total_beats_rem, avg_bpb,
    )


def log_instrument_summary(logger: logging.Logger, timelines: dict[str, InstrumentTimeline]) -> None:
    """Log a simple per-instrument event count summary.

    Args:
        logger: Logger used to emit INFO lines.
        timelines: Mapping of instrument name -> full InstrumentTimeline.

    Returns:
        None
    """
    logger.info("Instrument event summary:")
    for inst_name, tl in timelines.items():
        logger.info("  %s: %d events", inst_name, len(tl.events))
