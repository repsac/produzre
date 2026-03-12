

from __future__ import annotations

"""ASCII grid formatting for Produzre analysis exports.

This module contains the *canonical* implementation for rendering a text-based grid from
note events. It is used in two places:

- `produzre.export.textdump`: exports an analysis grid directly from Produzre’s
  internal Timeline ("timeline -> grid").
- `produzre.analysis.tsv_events`: regenerates a grid from an exported TSV event stream
  ("TSV -> grid"), enabling diffing and debugging across runs.

Design goals
------------
- Stable, deterministic formatting: the same event stream should always produce the same
  grid text.
- One-character-per-step cells to preserve alignment in monospace fonts.
- Minimal dependencies: no MIDI parsing and no reliance on Timeline internals.
- Duck-typed input: callers provide simple row objects with a small set of attributes.

Expected row attributes
-----------------------
Rows are event-like objects with these attributes (duck-typed):

- `instrument` (str): instrument key, e.g. "drums".
- `start_beat_abs` (float): absolute start time in beats.
- `duration_beats` (float): duration in beats.
- `pitch` (int): MIDI pitch (for drums, this is the GM drum note number).
- `velocity` (int): MIDI velocity 0–127.
- `note` (str): optional note label for non-drum instruments.

Notes
-----
- The grid is a visualization only. It does not affect MIDI generation.
- Drum rows use a small GM mapping for readability; unknown pitches are shown as "P<NN>".
"""

import math
from typing import Any, Dict, List, Optional, Sequence

#
# Minimal GM drum-name mapping used for grid row labels. Unknown pitches fall back to "P<NN>".
GM_DRUM_NAMES: Dict[int, str] = {
    35: "KICK",
    36: "KICK",
    37: "SNARE",  # Crossstick
    38: "SNARE",  # Normal
    40: "SNARE",  # Rimshot
    42: "HAT_C",
    44: "HAT_P",
    46: "HAT_O",
    49: "CRASH",
    51: "RIDE",
    45: "TOM_L",
    47: "TOM_M",
    50: "TOM_H",
}


def make_step_header(steps_per_bar: int, beats_per_bar: float) -> str:
    """Return a one-character-per-step header for a single bar.

    The header is intended to sit above each bar’s grid cells to help humans interpret
    positions within the bar. It always returns a string of length `steps_per_bar`.

    Examples (4/4):
      - 16 steps/bar -> ``1e&a2e&a3e&a4e&a`` (16th-note grid)
      - 8 steps/bar  -> ``1&2&3&4&``         (8th-note grid)
      - 12 steps/bar -> ``1ta2ta3ta4ta``     (triplet-ish labeling)

    If a clean mapping cannot be derived (e.g., non-integer beats per bar, or a step
    count that does not divide evenly into beats), the function falls back to a simple
    dot-based header ("1....").

    Important:
        This function intentionally uses *single characters per step* to keep the grid
        aligned. If beat numbers would exceed a single character (>= 10), it also falls
        back to dot format.
    """
    beats_int = int(round(beats_per_bar))
    if abs(beats_per_bar - float(beats_int)) > 1e-6 or beats_int <= 0:
        return "1" + "." * max(0, steps_per_bar - 1)

    if steps_per_bar <= 0:
        return ""

    if steps_per_bar % beats_int != 0:
        return "1" + "." * max(0, steps_per_bar - 1)

    steps_per_beat = steps_per_bar // beats_int

    if steps_per_beat == 4:
        tail = ["e", "&", "a"]
        out: List[str] = []
        for b in range(1, beats_int + 1):
            if b >= 10:
                return "1" + "." * max(0, steps_per_bar - 1)
            out.append(str(b))
            out.extend(tail)
        return "".join(out)[:steps_per_bar]

    if steps_per_beat == 2:
        out: List[str] = []
        for b in range(1, beats_int + 1):
            if b >= 10:
                return "1" + "." * max(0, steps_per_bar - 1)
            out.append(str(b))
            out.append("&")
        return "".join(out)[:steps_per_bar]

    if steps_per_beat == 3:
        out: List[str] = []
        for b in range(1, beats_int + 1):
            if b >= 10:
                return "1" + "." * max(0, steps_per_bar - 1)
            out.append(str(b))
            out.append("t")
            out.append("a")
        return "".join(out)[:steps_per_bar]

    return "1" + "." * max(0, steps_per_bar - 1)



def _velocity_symbol_default(velocity: int) -> str:
    """Map velocity to a default glyph.

    This is the baseline velocity→symbol mapping shared by all instruments unless a
    row-specific override is applied via `velocity_symbol_for_row`.

    Returns:
        A single character ("X", "^", "x", or ".").
    """
    v = int(velocity)
    if v >= 110:
        return "X"
    if v >= 92:
        return "^"
    if v >= 70:
        return "x"
    return "."


def velocity_symbol_for_row(instrument: str, row_label: str, velocity: int) -> str:
    """Map a note’s velocity to a single-character glyph for the ASCII grid.

    The grid aims to be readable at a glance. Purely using '.' for low velocities makes
    subtle articulations (ghost notes) hard to see, so we apply small drum-specific
    tweaks:

    - SNARE: hits below the normal threshold are rendered as 'g' to indicate ghosts.
    - HAT_*: accent thresholds are slightly lower so '^' appears more often.

    Args:
        instrument: Instrument key (e.g., "drums").
        row_label: The grid row label (e.g., "SNARE", "HAT_C").
        velocity: MIDI velocity (0–127).

    Returns:
        A single character used in the grid cell.

    Note:
        This affects *only* analysis output. It does not influence MIDI generation.
    """
    inst = str(instrument or "")
    lbl = str(row_label or "")
    v = int(velocity)

    if inst == "drums":
        # Make snare ghosts visible.
        if lbl == "SNARE":
            if v <= 0:
                return "-"
            if v < 70:
                return "g"
            return _velocity_symbol_default(v)

        # Make hat accents easier to see in the grid.
        if lbl.startswith("HAT_"):
            if v >= 105:
                return "X"
            if v >= 85:
                return "^"
            if v >= 55:
                return "x"
            return "."

    return _velocity_symbol_default(v)


def row_label_for_note(instrument: str, pitch: int, note: str) -> str:
    """Return the grid row label for an event.

    - For drums, we map MIDI pitches to short GM-based labels (e.g., 42→"HAT_C").
    - For non-drums, we prefer the provided `note` label and fall back to the pitch.

    Args:
        instrument: Instrument key ("drums", "bass", ...).
        pitch: MIDI pitch.
        note: Optional human label.

    Returns:
        A row label used to group events into grid lanes.
    """
    if instrument == "drums":
        return GM_DRUM_NAMES.get(int(pitch), f"P{int(pitch)}")
    return note or str(pitch)


def grid_text_from_rows(
    rows: Sequence[Any],
    *,
    beats_per_bar: float = 4.0,
    subdiv: int = 16,
    instrument: Optional[str] = None,
    bars_total: Optional[int] = None,
) -> str:
    """Render a multi-bar ASCII grid from event-like rows.

    The grid is similar to a simplified piano-roll view where each row is an instrument
    lane (or drum voice) and each column is a fixed subdivision within the bar.

    Args:
        rows:
            Sequence of objects with the attributes documented at module level.
        beats_per_bar:
            Beats per bar for the rendered grid (e.g., 4.0 for 4/4).
        subdiv:
            Number of grid cells per bar (e.g., 16 for 16th-note resolution in 4/4).
        instrument:
            Optional override for the instrument key used for labeling.
        bars_total:
            If provided, forces the number of bars rendered. If omitted, the number of
            bars is derived from the maximum event end time.

    Returns:
        A multi-line string containing a header plus one block per bar.

    Raises:
        ValueError: if `subdiv` is not positive.

    Notes:
        - Only event start times are plotted (durations are not expanded into held cells).
        - Rows are sorted alphabetically by label for stable diffs.
    """
    if subdiv <= 0:
        raise ValueError("subdiv must be > 0")

    steps_per_bar = int(subdiv)
    # Duration of a single grid cell in beats.
    step_beats = float(beats_per_bar) / float(steps_per_bar)

    if not rows:
        inst = instrument or ""
        header = make_step_header(steps_per_bar, beats_per_bar)
        label_width = max(7, len("BAR 1"))
        return (
            f"INSTRUMENT: {inst}\n"
            f"METER: {beats_per_bar:.2f} beats/bar   SUBDIV: {steps_per_bar} steps/bar\n\n"
            f"{('BAR 1'):<{label_width}} |{header}|\n\n"
        )

    inst = instrument or str(getattr(rows[0], "instrument", ""))

    if bars_total is None:
        max_end = 0.0
        for r in rows:
            s = float(getattr(r, "start_beat_abs"))
            d = float(getattr(r, "duration_beats", 0.0))
            max_end = max(max_end, s + d)
        bars_total = int(math.ceil(max_end / float(beats_per_bar))) if max_end > 0 else 1

    row_labels = sorted(
        {
            row_label_for_note(
                inst,
                int(getattr(r, "pitch")),
                str(getattr(r, "note", "")),
            )
            for r in rows
        }
    )

    label_width = max(
        7,
        len(f"BAR {bars_total}"),
        max((len(x) for x in row_labels), default=0),
    )

    # Pre-flatten rows into (start, pitch, velocity) tuples for fast per-bar scanning.
    events = [
        (
            float(getattr(r, "start_beat_abs")),
            int(getattr(r, "pitch")),
            int(getattr(r, "velocity", 100)),
        )
        for r in rows
    ]

    label_to_pitches: Dict[str, set[int]] = {}
    for r in rows:
        lbl = row_label_for_note(inst, int(getattr(r, "pitch")), str(getattr(r, "note", "")))
        label_to_pitches.setdefault(lbl, set()).add(int(getattr(r, "pitch")))

    lines: List[str] = []
    lines.append(f"INSTRUMENT: {inst}")
    lines.append(f"METER: {beats_per_bar:.2f} beats/bar   SUBDIV: {steps_per_bar} steps/bar")
    lines.append("")

    header = make_step_header(steps_per_bar, beats_per_bar)

    for bar_idx in range(1, int(bars_total) + 1):
        bar_start = (bar_idx - 1) * float(beats_per_bar)
        bar_end = bar_start + float(beats_per_bar)

        lines.append(f"{('BAR ' + str(bar_idx)):<{label_width}} |{header}|")

        for lbl in row_labels:
            cells = ["-"] * steps_per_bar
            pitches = label_to_pitches.get(lbl, set())

            for start, pitch, vel in events:
                if pitch not in pitches:
                    continue
                if start < bar_start or start >= bar_end:
                    continue

                step = int(math.floor((start - bar_start) / step_beats + 1e-9))
                if 0 <= step < steps_per_bar:
                    cells[step] = velocity_symbol_for_row(inst, lbl, vel)

            lines.append(f"{lbl:<{label_width}} |{''.join(cells)}|")

        lines.append("")

    return "\n".join(lines) + "\n"
