from __future__ import annotations

"""Build planning for Produzre orchestration.

This module contains two planning systems:

1. BuildPlan: Pre-rendering scaffolding (harmony + rhythm grids, section timing)
   - Created once during orchestration setup
   - Used by render phase to avoid recomputing section scaffolding

2. PerformancePlan: Runtime negotiation state (engine-to-engine communication)
   - Created once per build, passed to all engines
   - Shared data store for derived information (groove cues, transitions, etc.)
   - Enables engine coordination without direct coupling

Time units:
- All timing values are expressed in quarter-note beats.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from ..model import RootConfig
from ..timeline import SectionTiming
from .scaffold import build_section_scaffold as _build_section_scaffold


# Reserved plan key constants for common slots (Phase N1)
PLAN_KEY_RHYTHM_GRID = "rhythm.grid"
PLAN_KEY_RHYTHM_ACCENTS = "rhythm.accents"
PLAN_KEY_HARMONY_PLAN = "harmony.plan"
PLAN_KEY_TRANSITIONS_MAP = "transitions.map"
PLAN_KEY_GROOVE_CUES = "groove.cues"
PLAN_KEY_FILL_WINDOWS = "groove.fill_windows"


@dataclass
class SectionMeta:
    """Metadata for a single section (Phase N1).

    Lightweight section info for PerformancePlan, separate from full SectionConfig.

    Attributes:
        id: Section identifier (e.g., "verse", "chorus").
        type: Section type label (e.g., "verse", "chorus", "bridge").
        start_beat: Section start position in song timeline (beats).
        end_beat: Section end position in song timeline (beats).
        length_beats: Section duration in beats.
        beats_per_bar: Beats per bar for this section.
        meter: Meter string (e.g., "4/4", "7/8").
        key: Key string (e.g., "C", "E").
        mode: Mode string (e.g., "ionian", "dorian").
    """
    id: str
    type: str
    start_beat: float
    end_beat: float
    length_beats: float
    beats_per_bar: float
    meter: str
    key: str
    mode: str


@dataclass
class PerformancePlan:
    """Central negotiation state for engine coordination (Phase N1).

    This object is created once per build and passed to all engines.
    It serves as a shared data store for derived information like:
    - Rhythm grids and accent patterns
    - Harmony plans (chord slots)
    - Transition maps
    - Groove cues from drums

    Engines can read from and write to the plan using a namespaced key system.
    Reserved keys are defined as constants (e.g., PLAN_KEY_RHYTHM_GRID).

    Attributes:
        bpm: Song tempo in beats per minute.
        meter: Default meter string (e.g., "4/4").
        key: Default key string (e.g., "C").
        mode: Default mode string (e.g., "ionian").
        beats_per_bar: Default beats per bar.
        total_beats: Total song duration in beats.
        sections: List of section metadata in arrangement order.
        data: Namespaced data store for engine communication.
            Keys should be dot-separated (e.g., "rhythm.grid", "harmony.plan").
    """
    bpm: float
    meter: str
    key: str
    mode: str
    beats_per_bar: float
    total_beats: float
    sections: list[SectionMeta] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)

    def has(self, key: str) -> bool:
        """Check if a plan key exists.

        Args:
            key: Namespaced key string (e.g., "rhythm.grid").

        Returns:
            bool: True if key exists in plan data.
        """
        return key in self.data

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the plan data.

        Args:
            key: Namespaced key string (e.g., "rhythm.grid").
            default: Default value if key doesn't exist.

        Returns:
            Any: Value stored at key, or default if not found.
        """
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a value in the plan data.

        Args:
            key: Namespaced key string (e.g., "rhythm.grid").
            value: Value to store.

        Returns:
            None
        """
        self.data[key] = value

    def merge(self, key: str, value: Any, strategy: str = "replace") -> None:
        """Merge a value into the plan data.

        Supports multiple merge strategies:
        - "replace": Replace existing value (default, same as set()).
        - "extend": If existing value is a list, extend it with new value (must also be list).
        - "deepmerge": If existing value is a dict, recursively merge with new value (must also be dict).

        Args:
            key: Namespaced key string.
            value: Value to merge.
            strategy: Merge strategy ("replace", "extend", "deepmerge").

        Returns:
            None

        Raises:
            ValueError: If strategy is invalid or value types don't match strategy requirements.
        """
        if strategy == "replace":
            self.data[key] = value
        elif strategy == "extend":
            if key not in self.data:
                self.data[key] = value if isinstance(value, list) else [value]
            else:
                existing = self.data[key]
                if not isinstance(existing, list):
                    raise ValueError(f"Cannot extend non-list value at key '{key}'")
                if not isinstance(value, list):
                    raise ValueError(f"Cannot extend with non-list value at key '{key}'")
                existing.extend(value)
        elif strategy == "deepmerge":
            if key not in self.data:
                self.data[key] = value
            else:
                existing = self.data[key]
                if not isinstance(existing, dict):
                    raise ValueError(f"Cannot deepmerge non-dict value at key '{key}'")
                if not isinstance(value, dict):
                    raise ValueError(f"Cannot deepmerge with non-dict value at key '{key}'")
                self._deepmerge_dict(existing, value)
        else:
            raise ValueError(f"Invalid merge strategy: {strategy}")

    def _deepmerge_dict(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        """Recursively merge source dict into target dict (in-place).

        Args:
            target: Target dict to merge into (modified in-place).
            source: Source dict to merge from.

        Returns:
            None
        """
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deepmerge_dict(target[key], value)
            else:
                target[key] = value

    def get_section(self, section_id: str) -> Optional[SectionMeta]:
        """Get section metadata by ID.

        Args:
            section_id: Section identifier.

        Returns:
            Optional[SectionMeta]: Section metadata if found, None otherwise.
        """
        for section in self.sections:
            if section.id == section_id:
                return section
        return None


@dataclass(frozen=True)
class PlannedSection:
    """Planned representation of one section in the arrangement.

    This object bundles the original `SectionConfig` plus computed scaffolding
    and resolved timing.

    Attributes:
        sec_id: The arrangement key referencing the section (e.g., "verse1").
        sec: The parsed section configuration object.
        timing: Song-relative timing window for the section.
        harmony_plan: Optional harmony plan for the section, if harmony is
            enabled/available.
        rhythm_grid: The resolved rhythm grid used by engines for event
            placement.
    """

    sec_id: str
    sec: object
    timing: SectionTiming
    harmony_plan: Optional[object]
    rhythm_grid: object


@dataclass(frozen=True)
class BuildPlan:
    """Complete build plan derived from configuration.

    The plan is a pure planning artifact:
      - It contains section scaffolding (harmony + rhythm grids).
      - It contains resolved song-relative section timing.
      - It contains the total song length in beats.

    It is designed to be passed to rendering and exporting without requiring
    those phases to inspect the raw config structure.

    Attributes:
        song_name: Sanitized/effective song name used for export naming.
        planned_sections: Ordered tuple of planned sections.
        section_timings: Ordered tuple of timing windows matching the
            arrangement order.
        total_beats: Total song length in quarter-note beats.
    """

    song_name: str
    planned_sections: tuple[PlannedSection, ...]
    section_timings: tuple[SectionTiming, ...]
    total_beats: float


def plan_song(*, cfg: RootConfig, logger: logging.Logger) -> BuildPlan:
    """Compute a `BuildPlan` from configuration.

    This function is responsible for:
      - Determining the effective song name (`cfg.get_effective_song_name()`).
      - Iterating `cfg.arrangement` in order.
      - For each section:
          * building scaffolding via `build_section_scaffold()`
          * computing the absolute start/end beat window for the section
          * recording the section's effective beats-per-bar

    The function logs a brief per-section summary (type + grid size) to help
    users validate timing and scaffolding during dry runs.

    Args:
        cfg: Parsed and validated root configuration.
        logger: Logger used for informational output.

    Returns:
        BuildPlan: Planned sections, timing windows, and total song length.

    Raises:
        KeyError: If an arrangement entry references a missing section.
    """
    song_name = cfg.get_effective_song_name()

    song_beat_cursor = 0.0
    planned_sections: list[PlannedSection] = []
    section_timings: list[SectionTiming] = []

    for sec_id in cfg.arrangement:
        sec = cfg.sections[sec_id]
        logger.info("Section '%s' (type=%s)", sec.id, sec.type)

        hplan, section_meter, rgrid, total_beats = _build_section_scaffold(cfg, sec, logger)

        logger.info(
            "  Rhythm grid: %d cells (beats_per_bar=%.2f)",
            len(rgrid.cells),
            rgrid.beats_per_bar,
        )

        section_start = song_beat_cursor
        section_end = section_start + float(total_beats)

        timing = SectionTiming(
            id=sec.id,
            type=sec.type,
            start_beat=section_start,
            end_beat=section_end,
            beats_per_bar=section_meter.beats_per_bar,
        )

        section_timings.append(timing)
        planned_sections.append(
            PlannedSection(
                sec_id=sec_id,
                sec=sec,
                timing=timing,
                harmony_plan=hplan,
                rhythm_grid=rgrid,
            )
        )

        song_beat_cursor = section_end

    return BuildPlan(
        song_name=song_name,
        planned_sections=tuple(planned_sections),
        section_timings=tuple(section_timings),
        total_beats=song_beat_cursor,
    )
