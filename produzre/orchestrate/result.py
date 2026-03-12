from __future__ import annotations

"""Build result data structures.

This module defines the structured output returned by the orchestration layer.

`BuildResult` is designed to be consumed by:
- CLI commands (to print summaries and locate export artifacts)
- External Python scripts (to integrate Produzre into larger toolchains)

It intentionally contains only lightweight, serializable information plus an
optional reference to the in-memory `BuildPlan` for advanced callers.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from ..timeline import SectionTiming

if TYPE_CHECKING:
    from .plan import BuildPlan, PerformancePlan


@dataclass(frozen=True)
class BuildResult:
    """Structured summary of a completed build.

    A build run includes planning, rendering (into per-instrument timelines),
    and optional exporting to disk.

    Fields:
        song_name: Effective song title used for export naming.
        dry_run: True when the build performed planning/rendering only and did
            not write any files.
        total_beats: Total song length in quarter-note beats.
        export_root: Filesystem path to the per-run export directory (string),
            or None when `dry_run` is True.

        section_timings: Ordered list of section timing windows used for the
            build (song-relative beats).
        instruments_used: Instruments in deterministic export/track order.
        events_per_instrument: Per-instrument note event counts after rendering.

        plan: Optional in-memory `BuildPlan` used during orchestration. This is
            provided primarily for callers who want to inspect the planned
            harmony/rhythm scaffolding without recomputing it.
        performance_plan: Optional in-memory `PerformancePlan` used for engine
            coordination. This contains shared derived data like groove cues,
            transitions, and other engine-to-engine communication (Phase N1).
    """
    song_name: str
    dry_run: bool
    total_beats: float
    export_root: Optional[str]

    section_timings: list[SectionTiming]
    instruments_used: list[str]
    events_per_instrument: dict[str, int]

    plan: Optional["BuildPlan"] = None
    performance_plan: Optional["PerformancePlan"] = None
