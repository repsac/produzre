"""Register management for lead guitar (Phase LG4).

Keeps MIDI pitches in a realistic lead guitar range with soft octave
wrapping and optional octave lifts at section boundaries (chorus entry).

Register presets map friendly names to (min_note, max_note) MIDI ranges.
The ``auto`` preset is an alias for ``mid`` and can be extended later to
pick range dynamically based on song key / section context.
"""

from __future__ import annotations

from typing import Tuple


# Register presets: (min_note, max_note) in MIDI.
REGISTER_PRESETS = {
    "low":       (52, 67),   # E3–G4  (lower melodic, below rhythm gtr)
    "mid":       (60, 76),   # C4–E5  (comfortable melodic range)
    "high":      (67, 84),   # G4–C6  (upper melodic, still playable)
    "very_high": (72, 91),   # C5–G6  (extreme high — use sparingly)
    "full":      (52, 88),   # E3–E6  (full shred range, ~3 octaves)
    "auto":      (60, 76),   # alias for mid; future: dynamic selection
}

DEFAULT_REGISTER = "mid"


def get_register_bounds(register: str) -> Tuple[int, int]:
    """Return (min_note, max_note) for a register preset name.

    Falls back to ``mid`` for unrecognised names.
    """
    return REGISTER_PRESETS.get((register or DEFAULT_REGISTER).lower(),
                                REGISTER_PRESETS[DEFAULT_REGISTER])


def clamp_pitch(pitch: int, min_note: int, max_note: int) -> int:
    """Hard-clamp *pitch* to [min_note, max_note]."""
    return max(min_note, min(pitch, max_note))


def octave_wrap_if_needed(pitch: int, min_note: int, max_note: int) -> int:
    """Wrap *pitch* into range by shifting ±12 rather than hard-clamping.

    Tries the nearest octave shift first.  Only falls back to
    ``clamp_pitch`` if no single shift brings the note into range
    (shouldn't happen for register widths ≥ 12 semitones).
    """
    if min_note <= pitch <= max_note:
        return pitch

    if pitch > max_note:
        shifted = pitch
        while shifted > max_note:
            shifted -= 12
        if shifted >= min_note:
            return shifted
        # Overshot below; hard-clamp as safety net.
        return clamp_pitch(pitch, min_note, max_note)

    # pitch < min_note
    shifted = pitch
    while shifted < min_note:
        shifted += 12
    if shifted <= max_note:
        return shifted
    # Overshot above; hard-clamp as safety net.
    return clamp_pitch(pitch, min_note, max_note)


def apply_lift(pitch: int, min_note: int, max_note: int, lift: int = 12) -> int:
    """Shift *pitch* up by *lift* semitones if the result stays in range.

    Used at chorus entries or climactic moments to push the melody higher.
    Returns the original pitch unchanged if the lift would exceed max_note.
    """
    lifted = pitch + lift
    if lifted <= max_note:
        return lifted
    return pitch
