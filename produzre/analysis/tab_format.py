"""ASCII guitar tablature formatting for Produzre analysis exports.

Renders standard guitar tab from note events. Pitches are reverse-mapped to
string/fret positions using the shared instruments library.

Expected row attributes (duck-typed, same contract as grid_format):
    - instrument (str)
    - start_beat_abs (float)
    - duration_beats (float)
    - pitch (int)
    - velocity (int)
    - note (str): optional note label

Design goals:
    - Standard tab notation: horizontal lines (one per string), fret numbers
    - High E at top, low E at bottom (standard guitar tab orientation)
    - Bar-by-bar rendering with bar number headers
    - Reverse-maps MIDI pitches to fret positions via InstrumentProfile
    - Handles any string count or tuning
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

from ..instruments.chord_shapes import resolve_pitches_to_voicing
from ..instruments.profile import InstrumentProfile, GUITAR_STANDARD, BASS_4STRING


# ---------------------------------------------------------------------------
# Guitar instrument detection
# ---------------------------------------------------------------------------

_ENGINE_PROFILES: Dict[str, InstrumentProfile] = {
    "rhythm_gtr": GUITAR_STANDARD,
    "acoustic_gtr": GUITAR_STANDARD,
    "lead_gtr": GUITAR_STANDARD,
    "bass": BASS_4STRING,
}

# Standard 6-string labels (high string first = standard tab orientation)
_STANDARD_LABELS_6 = ("e", "B", "G", "D", "A", "E")


def is_guitar_instrument(instrument: str) -> bool:
    """Return True if the instrument name corresponds to a guitar engine."""
    inst = instrument.strip().lower()
    return any(inst == key or inst.startswith(key) for key in _ENGINE_PROFILES)


def profile_for_instrument(instrument: str) -> Optional[InstrumentProfile]:
    """Return the InstrumentProfile for a guitar instrument, or None."""
    inst = instrument.strip().lower()
    for key, profile in _ENGINE_PROFILES.items():
        if inst == key or inst.startswith(key):
            return profile
    return None


# ---------------------------------------------------------------------------
# Event grouping
# ---------------------------------------------------------------------------

def _group_events_by_step(
    rows: Sequence[Any],
    bar_start: float,
    beats_per_bar: float,
    steps_per_bar: int,
) -> Dict[int, List[int]]:
    """Group events into subdivision steps.

    Returns {step_index: [pitch, ...]}.
    Only events in [bar_start, bar_start + beats_per_bar) are included.
    """
    step_beats = beats_per_bar / steps_per_bar
    result: Dict[int, List[int]] = {}

    for r in rows:
        start = float(getattr(r, "start_beat_abs"))
        if start < bar_start - 1e-9 or start >= bar_start + beats_per_bar - 1e-9:
            continue
        step = int(math.floor((start - bar_start) / step_beats + 1e-9))
        step = max(0, min(step, steps_per_bar - 1))
        pitch = int(getattr(r, "pitch"))
        result.setdefault(step, []).append(pitch)

    return result


def _pitches_to_fret_map(
    pitches: List[int],
    profile: InstrumentProfile,
    capo: int = 0,
) -> Dict[int, int]:
    """Map simultaneous pitches to {string_index: fret_number}.

    Uses resolve_pitches_to_voicing() from the instruments library.
    Returns only assigned strings (fret >= 0).
    """
    if not pitches:
        return {}
    root = min(pitches)
    rv = resolve_pitches_to_voicing(pitches, root, profile, capo)
    return {s: f for s, f in enumerate(rv.frets) if f >= 0}


# ---------------------------------------------------------------------------
# String labels
# ---------------------------------------------------------------------------

def _string_labels(profile: InstrumentProfile) -> List[str]:
    """Return string labels from highest to lowest (tab display order)."""
    n = profile.num_strings
    if n == 6 and profile.open_tuning == GUITAR_STANDARD.open_tuning:
        return list(_STANDARD_LABELS_6)
    # Generic labels: note names from tuning, reversed for tab order
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    labels = []
    for midi in reversed(profile.open_tuning):
        labels.append(names[midi % 12])
    return labels


# ---------------------------------------------------------------------------
# Main tab rendering
# ---------------------------------------------------------------------------

def tab_text_from_rows(
    rows: Sequence[Any],
    *,
    beats_per_bar: float = 4.0,
    subdiv: int = 16,
    instrument: Optional[str] = None,
    bars_total: Optional[int] = None,
    profile: Optional[InstrumentProfile] = None,
    capo: int = 0,
) -> str:
    """Render multi-bar ASCII guitar tablature from event-like rows.

    Args:
        rows:          Sequence of objects with start_beat_abs, pitch, etc.
        beats_per_bar: Beats per bar (e.g. 4.0 for 4/4).
        subdiv:        Grid cells per bar (e.g. 16 for 16th-note resolution).
        instrument:    Instrument name (for header and profile lookup).
        bars_total:    Forced bar count (derived from events if omitted).
        profile:       InstrumentProfile override. None = lookup from instrument.
        capo:          Capo fret position.

    Returns:
        Multi-line string containing ASCII tab.
    """
    inst = instrument or ""

    if profile is None:
        profile = profile_for_instrument(inst)
    if profile is None:
        profile = GUITAR_STANDARD

    n_strings = profile.num_strings
    steps_per_bar = int(subdiv)
    labels = _string_labels(profile)
    label_w = max(len(lbl) for lbl in labels)

    # Determine bar count
    if bars_total is None:
        if rows:
            max_end = max(
                float(getattr(r, "start_beat_abs")) + float(getattr(r, "duration_beats", 0.0))
                for r in rows
            )
            bars_total = int(math.ceil(max_end / beats_per_bar)) if max_end > 0 else 1
        else:
            bars_total = 1

    lines: List[str] = []
    lines.append(f"{inst.upper()} TAB")
    lines.append(
        f"METER: {int(beats_per_bar)}/4   SUBDIV: {steps_per_bar} steps/bar"
    )
    lines.append("")

    for bar_idx in range(1, bars_total + 1):
        bar_start = (bar_idx - 1) * beats_per_bar

        # Group pitches by subdivision step
        step_pitches = _group_events_by_step(rows, bar_start, beats_per_bar, steps_per_bar)

        # Resolve each step's pitches to fret maps
        step_frets: Dict[int, Dict[int, int]] = {}
        for step, plist in step_pitches.items():
            step_frets[step] = _pitches_to_fret_map(plist, profile, capo)

        # Bar header
        lines.append(f"Bar {bar_idx}")

        # Render each string line (labels are already in high-to-low order)
        for display_idx, label in enumerate(labels):
            # Map display index to physical string index
            string_idx = n_strings - 1 - display_idx

            padded_label = label.rjust(label_w)
            cells: List[str] = []

            for step in range(steps_per_bar):
                fret_map = step_frets.get(step)
                if fret_map is not None and string_idx in fret_map:
                    fret_str = str(fret_map[string_idx])
                    cells.append(fret_str)
                else:
                    cells.append("-")

            # Join cells with dashes for readability
            line_body = "-".join(cells)
            lines.append(f"{padded_label}|{line_body}|")

        lines.append("")

    return "\n".join(lines) + "\n"
