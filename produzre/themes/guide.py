"""Build the shared melody guide from realized theme notes (design §4.3).

When a song defines themes, the guide that engines consume
(``melody.guide.<sec_id>``) is derived from the section's realized MELODY
theme instead of the sinusoidal contour in ``melody.build_melody_guide``.
The public guide shape (``MelodyGuide`` / ``guide_pitch_at``) is unchanged,
so existing engines inherit themed melodies without modification.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

from ..melody import MelodyGuide, MelodyTarget
from .model import Theme
from .realize import RealizedNote, realize_theme
from .transform import apply_transform


def realize_for_section(
    theme: Theme,
    transform_name: str,
    transform_params: Optional[dict],
    chord_slots: Sequence,
    *,
    key: str,
    mode: str,
    genre: str = "",
    total_beats: Optional[float] = None,
) -> List[RealizedNote]:
    """Apply the section's transform, then realize over the chord slots."""
    developed = apply_transform(theme, transform_name, **(transform_params or {}))
    return realize_theme(
        developed,
        chord_slots,
        key=key,
        mode=mode,
        genre=genre,
        total_beats=total_beats,
    )


def build_themed_guide(
    theme: Theme,
    chord_slots: Sequence,
    *,
    key: str,
    mode: str,
    genre: str = "",
    total_beats: Optional[float] = None,
    transform_name: str = "quote",
    transform_params: Optional[dict] = None,
) -> MelodyGuide:
    """Return a MelodyGuide whose targets are the realized theme notes.

    Target semantics map onto the theme structure:
      - ``phrase_index`` is the theme occurrence (each loop = one phrase).
      - ``cadence`` marks the last sounded note of each occurrence, so
        consumers that lean on cadence points still get phrase-boundary
        resolution.
    """
    section_id = str(getattr(chord_slots, "section_id", "") or "")
    slots = getattr(chord_slots, "chord_slots", chord_slots)
    notes = realize_for_section(
        theme, transform_name, transform_params, slots,
        key=key, mode=mode, genre=genre, total_beats=total_beats,
    )
    low, high = theme.base_register

    # Mark the last note of each occurrence as the cadence target.
    last_per_occurrence = {}
    for n in notes:
        last_per_occurrence[n.occurrence] = n
    cadence_ids = {id(n) for n in last_per_occurrence.values()}

    targets = tuple(
        MelodyTarget(
            beat=n.beat,
            pitch=n.pitch,
            chord_index=n.chord_index,
            role="theme",
            phrase_index=n.occurrence,
            cadence=id(n) in cadence_ids,
        )
        for n in notes
    )
    return MelodyGuide(section_id, low, high, targets)


def realized_to_dicts(notes: Sequence[RealizedNote]) -> List[dict]:
    """Serialize realized notes for plan storage / engine consumption."""
    return [
        {
            "beat": n.beat,
            "duration_beats": n.duration_beats,
            "pitch": n.pitch,
            "degree": n.degree_label,
            "numeral": n.numeral,
            "occurrence": n.occurrence,
        }
        for n in notes
    ]
