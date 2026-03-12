from __future__ import annotations

"""TSV event utilities for Produzre analysis exports.

This module reads and manipulates the per-instrument event dumps written by
`produzre.export.textdump` (files typically named `*.events.tsv`).

Primary use cases
-----------------
- Load `*.events.tsv` into structured `EventRow` objects.
- Filter/group events by instrument, section, and bar.
- Generate an ASCII grid ("TSV -> grid") via `analysis.grid_format`, which is useful for
  regression testing and diff-based debugging.

Design goals
------------
- No heavy dependencies (no pandas required).
- Stable and machine-parseable outputs.
- Friendly for unit tests (deterministic comparisons when the input file is identical).
- Forward compatible: additional TSV columns may appear; unknown columns are ignored.

Expected TSV schema
-------------------
A header row is required. The current canonical columns are:

    instrument\tsection_id\tbar\tbeat\tstart_beat_abs\tduration_beats\tpitch\tnote\tvelocity\tchannel\tprogram

Notes
-----
- "bar" is 1-based.
- "beat" is 1-based (float for sub-beat precision).
- "start_beat_abs" is absolute time in beats from song start.
- For drums, `program` is typically 0 and `pitch` is a GM drum note number.
"""

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
from .grid_format import grid_text_from_rows


@dataclass(frozen=True)
class EventRow:
    """A single note event row from a Produzre `*.events.tsv` export.

    Attributes:
        instrument: Produzre instrument name (e.g., "drums", "bass", "rhythm_gtr").
        section_id: Section identifier if known; empty string if section mapping was unavailable.
        bar: 1-based bar index.
        beat: 1-based beat position within the bar (float for sub-beat precision).
        start_beat_abs: Absolute start time in beats from song start.
        duration_beats: Event duration in beats.
        pitch: MIDI pitch number (0-127).
        note: Note name as exported (e.g., "C4").
        velocity: MIDI velocity (0-127).
        channel: MIDI channel (0-15).
        program: MIDI program number (0-127). For drums this may be 0.
        kind: Determinism debugging tag (e.g., "kick", "snare_ghost", "fill").
            Empty string if not provided by the engine. Optional field for backward compatibility.
    """

    instrument: str
    section_id: str
    bar: int
    beat: float
    start_beat_abs: float
    duration_beats: float
    pitch: int
    note: str
    velocity: int
    channel: int
    program: int
    kind: str = ""  # Optional determinism tag (added in Phase 13)


def load_events_tsv(path: Path) -> List[EventRow]:
    """Load a Produzre `*.events.tsv` file into `EventRow` objects.

    The reader enforces a minimal required set of columns and ignores any additional
    columns to remain forward compatible.

    Args:
        path: Path to a TSV file exported by `export.textdump`.

    Returns:
        A list of `EventRow` in the same order as the file.

    Raises:
        FileNotFoundError: If `path` does not exist.
        ValueError: If the TSV is missing a header or required columns.

    Implementation notes:
        - Numeric fields are parsed defensively: values may be serialized as ints or floats.
        - `bar` is parsed as an int; `beat` remains a float.
    """
    p = Path(path)
    with p.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        if reader.fieldnames is None:
            raise ValueError(f"TSV has no header: {p}")

        # Required columns for core analysis features (grid rendering, grouping, and summaries).
        required = {
            "instrument",
            "section_id",
            "bar",
            "beat",
            "start_beat_abs",
            "duration_beats",
            "pitch",
            "note",
            "velocity",
            "channel",
            "program",
        }
        missing = sorted(required.difference(set(reader.fieldnames)))
        if missing:
            raise ValueError(f"Missing required TSV columns {missing} in {p}")

        # Parse rows in file order (callers may sort/group as needed).
        out: List[EventRow] = []
        for row in reader:
            out.append(
                EventRow(
                    instrument=str(row.get("instrument", "")),
                    section_id=str(row.get("section_id", "")),
                    bar=int(float(row.get("bar", "0") or 0)),
                    beat=float(row.get("beat", "0") or 0.0),
                    start_beat_abs=float(row.get("start_beat_abs", "0") or 0.0),
                    duration_beats=float(row.get("duration_beats", "0") or 0.0),
                    pitch=int(float(row.get("pitch", "0") or 0)),
                    note=str(row.get("note", "")),
                    velocity=int(float(row.get("velocity", "0") or 0)),
                    channel=int(float(row.get("channel", "0") or 0)),
                    program=int(float(row.get("program", "0") or 0)),
                    kind=str(row.get("kind", "")),  # Optional field (Phase 13+)
                )
            )

    return out


def filter_instrument(rows: Sequence[EventRow], instrument: str) -> List[EventRow]:
    """Filter events to a single instrument.

    Args:
        rows: Event rows.
        instrument: Instrument name to match (exact match after stripping whitespace).

    Returns:
        A list containing only rows whose `instrument` equals the requested value.
    """
    inst = instrument.strip()
    return [r for r in rows if r.instrument == inst]


def filter_section(rows: Sequence[EventRow], section_id: str) -> List[EventRow]:
    """Filter events to a single section id.

    Args:
        rows: Event rows.
        section_id: Section identifier to match (exact match after stripping whitespace).

    Returns:
        A list containing only rows whose `section_id` equals the requested value.
    """
    sid = section_id.strip()
    return [r for r in rows if r.section_id == sid]


def filter_bars(rows: Sequence[EventRow], bar_start: int, bar_end: int) -> List[EventRow]:
    """Filter events to a bar range (inclusive).

    Args:
        rows: Event rows.
        bar_start: Start bar (1-based).
        bar_end: End bar (1-based).

    Returns:
        Rows whose `bar` is within `[bar_start, bar_end]` (order preserved).

    Note:
        If `bar_end < bar_start`, the endpoints are swapped.
    """
    a = int(bar_start)
    b = int(bar_end)
    if b < a:
        a, b = b, a
    return [r for r in rows if a <= r.bar <= b]


def group_by_bar(rows: Sequence[EventRow]) -> Dict[int, List[EventRow]]:
    """Group events by bar index.

    The returned groups are sorted by `(start_beat_abs, pitch)` for stable diffs.

    Args:
        rows: Event rows.

    Returns:
        Mapping of `bar -> [EventRow, ...]`.
    """
    out: Dict[int, List[EventRow]] = {}
    for r in rows:
        out.setdefault(r.bar, []).append(r)
    for k in out:
        out[k].sort(key=lambda x: (x.start_beat_abs, x.pitch))
    return out


def group_by_section(rows: Sequence[EventRow]) -> Dict[str, List[EventRow]]:
    """Group events by section id.

    The empty string key ("") represents "unknown section" when the exporter could not
    map an event to a section.

    Groups are sorted by `(start_beat_abs, pitch)` for stable diffs.

    Args:
        rows: Event rows.

    Returns:
        Mapping of `section_id -> [EventRow, ...]`.
    """
    out: Dict[str, List[EventRow]] = {}
    for r in rows:
        out.setdefault(r.section_id, []).append(r)
    for k in out:
        out[k].sort(key=lambda x: (x.start_beat_abs, x.pitch))
    return out


@dataclass(frozen=True)
class EventsSummary:
    """Compact summary statistics for a set of events.

    Intended for smoke tests and regression checks where you want a quick signal without
    diffing entire TSV/grid files.
    """

    n_events: int
    bars: Tuple[int, int]
    start_beat_range: Tuple[float, float]
    pitch_range: Tuple[int, int]
    velocity_range: Tuple[int, int]


def summarize(rows: Sequence[EventRow]) -> EventsSummary:
    """Compute lightweight range statistics over events.

    Args:
        rows: Event rows.

    Returns:
        An `EventsSummary` including bar range, absolute start-beat range, and pitch/velocity
        ranges. If `rows` is empty, all ranges are zeroed.
    """
    if not rows:
        return EventsSummary(
            n_events=0,
            bars=(0, 0),
            start_beat_range=(0.0, 0.0),
            pitch_range=(0, 0),
            velocity_range=(0, 0),
        )

    bars = (min(r.bar for r in rows), max(r.bar for r in rows))
    sb = (min(r.start_beat_abs for r in rows), max(r.start_beat_abs for r in rows))
    pr = (min(r.pitch for r in rows), max(r.pitch for r in rows))
    vr = (min(r.velocity for r in rows), max(r.velocity for r in rows))

    return EventsSummary(
        n_events=len(rows),
        bars=bars,
        start_beat_range=sb,
        pitch_range=pr,
        velocity_range=vr,
    )


def count_events_per_bar(rows: Sequence[EventRow]) -> Dict[int, int]:
    """Count events per bar.

    Args:
        rows: Event rows.

    Returns:
        Mapping of `bar -> count`.
    """
    out: Dict[int, int] = {}
    for r in rows:
        out[r.bar] = out.get(r.bar, 0) + 1
    return out


def grid_text_from_events(
    rows: Sequence[EventRow],
    *,
    beats_per_bar: float = 4.0,
    subdiv: int = 16,
    instrument: Optional[str] = None,
    bars_total: Optional[int] = None,
) -> str:
    """Render an ASCII grid from `EventRow` objects.

    This is a thin wrapper around `analysis.grid_format.grid_text_from_rows`.

    Args:
        rows: Event rows.
        beats_per_bar: Beats per bar (e.g., 4.0 for 4/4).
        subdiv: Grid cells per bar (e.g., 16 for 16ths in 4/4).
        instrument: Optional override for the instrument key used for labeling.
        bars_total: Optional forced bar count.

    Returns:
        Multi-line grid text.
    """
    return grid_text_from_rows(
        rows,
        beats_per_bar=beats_per_bar,
        subdiv=subdiv,
        instrument=instrument,
        bars_total=bars_total,
    )


def write_grid_from_events_tsv(
    events_tsv: Path,
    *,
    grid_path: Optional[Path] = None,
    beats_per_bar: float = 4.0,
    subdiv: int = 16,
    bars_total: Optional[int] = None,
) -> Path:
    """Generate a `*.grid.txt` file from an exported `*.events.tsv` file.

    This enables "TSV -> grid" regeneration for debugging and regression testing.

    Args:
        events_tsv: Path to the TSV file.
        grid_path: Optional explicit output path. Defaults to `<events_tsv>.grid.txt`.
        beats_per_bar: Beats per bar for rendering.
        subdiv: Steps per bar.
        bars_total: Optional forced bar count.

    Returns:
        The output path written.
    """
    p = Path(events_tsv)
    rows = load_events_tsv(p)

    # Default output naming: strip ".tsv" and write a sibling ".grid.txt" file.
    out = Path(grid_path) if grid_path is not None else p.with_suffix("").with_suffix(".grid.txt")
    out.parent.mkdir(parents=True, exist_ok=True)

    txt = grid_text_from_events(
        rows,
        beats_per_bar=beats_per_bar,
        subdiv=subdiv,
        instrument=rows[0].instrument if rows else "",
        bars_total=bars_total,
    )

    out.write_text(txt, encoding="utf-8")
    return out