# produzre/rhythm.py
from __future__ import annotations

"""Rhythm scaffolding primitives.

Produzre uses a lightweight "rhythm grid" during planning/rendering to provide
engines with a shared temporal scaffold for placing note events.

The rhythm grid is intentionally simple:
- It is beat-based (quarter-note beats).
- It can be subdivided (e.g., 1.0 beats, 0.5 beats, 0.25 beats).
- It marks downbeats (bar starts) using the section's effective meter.
- It carries arbitrary string tags that engines can read/write (e.g.,
  "kick", "snare", "accent", "chug", "pickup").

The grid is not intended to encode full drum notation; instead it provides a
shared place for rhythmic intent and coordination between engines.
"""

from dataclasses import dataclass, field
from typing import List, Set

from .harmony import Meter


@dataclass
class RhythmCell:
    """A single grid position in section beat space.

    Attributes:
        beat: Song-relative beat offset within the section (quarter-note beats).
        is_downbeat: True when this cell is at a bar boundary.
        tags: Arbitrary string tags attached by engines.

    Notes:
        Cells are created by `create_basic_rhythm_grid()` at a fixed subdivision.
        Engines may interpret tags however they like; tags are for coordination
        rather than strict semantics.
    """

    beat: float
    is_downbeat: bool = False
    tags: Set[str] = field(default_factory=set)


@dataclass
class RhythmGrid:
    """Rhythmic scaffold for one section.

    A rhythm grid contains an ordered list of `RhythmCell` entries spanning the
    section from beat 0 up to (but not including) `total_beats`.

    Attributes:
        meter: Section meter used to determine bar boundaries.
        beats_per_bar: Beats-per-bar expressed in quarter-note beats.
        total_beats: Total section length in quarter-note beats.
        cells: Ordered grid cells at the chosen subdivision.

    Notes:
        The grid may be annotated by multiple engines. Tagging is additive.
    """

    meter: Meter
    beats_per_bar: float
    total_beats: float
    cells: List[RhythmCell] = field(default_factory=list)

    def add_tag(self, beat: float, tag: str) -> None:
        """Attach a tag to the grid cell nearest a beat position.

        This is a convenience method for engines that want to annotate the grid
        without having to search for the nearest cell themselves.

        Current behavior:
            - Uses a simple nearest-cell search (O(n)).
            - If the grid has no cells, it is a no-op.

        Args:
            beat: Beat offset within the section.
            tag: Tag to add (e.g., "kick", "snare", "accent").

        Returns:
            None
        """
        # Very simple nearest-cell approach for now.
        if not self.cells:
            return
        nearest = min(self.cells, key=lambda c: abs(c.beat - beat))
        nearest.tags.add(tag)


def create_basic_rhythm_grid(
    meter: Meter,
    total_beats: float,
    subdivision: float = 1.0,
) -> RhythmGrid:
    """Create a basic rhythm grid for a section.

    The returned grid starts at beat 0 and advances by `subdivision` until it
    reaches `total_beats`.

    Downbeats:
        A cell is marked as a downbeat when its beat offset falls on a bar
        boundary given the meter-derived `beats_per_bar`.

    Args:
        meter: Section meter used to compute beats-per-bar.
        total_beats: Section length in quarter-note beats.
        subdivision: Step size between cells in beats. Examples:
            - 1.0: quarter-note grid (common default)
            - 0.5: eighth-note grid
            - 0.25: sixteenth-note grid

    Returns:
        RhythmGrid: Populated rhythm grid. If `total_beats <= 0`, returns an
        empty grid with `total_beats=0.0`.
    """
    if total_beats <= 0:
        return RhythmGrid(
            meter=meter,
            beats_per_bar=meter.beats_per_bar,
            total_beats=0.0,
            cells=[],
        )

    bpb = meter.beats_per_bar
    cells: List[RhythmCell] = []

    # Compute each beat as idx * subdivision instead of accumulating, so
    # float error does not drift across long sections.
    idx = 0
    eps = 1e-6
    while True:
        beat = idx * subdivision
        if beat >= total_beats - eps:
            break
        # Downbeat if at (or very near) a bar boundary. beat_in_bar can
        # approach bpb from below due to float error (e.g. 3.9999999), which
        # is also a bar boundary.
        beat_in_bar = beat % bpb
        is_down = beat_in_bar < eps or (bpb - beat_in_bar) < eps
        cells.append(RhythmCell(beat=beat, is_downbeat=is_down))
        idx += 1

    return RhythmGrid(
        meter=meter,
        beats_per_bar=bpb,
        total_beats=total_beats,
        cells=cells,
    )
