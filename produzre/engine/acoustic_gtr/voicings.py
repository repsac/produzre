"""Acoustic guitar chord voicing — thin adapter over the instruments library.

Delegates all voicing logic to `produzre.instruments.chord_shapes.select_voicing()`,
which uses physics-based CAGED chord shapes instead of piano-style interval templates.
This produces physically playable chords with correct open-string positions and muted
strings, matching how a steel-string guitar actually sounds.

Profile:
    GUITAR_STANDARD — 6-string, E2-A2-D3-G3-B3-E4

Return type changed from List[int] to ResolvedVoicing. Callers that only need
MIDI pitches use the .pitches property (backward compatible). Fingerpicking
patterns use pitch_for_string() to correctly address physical strings including
handling muted strings.
"""

from __future__ import annotations

import random
from typing import Optional

from ...instruments.chord_shapes import ResolvedVoicing, select_voicing
from ...instruments.profile import GUITAR_STANDARD

# The instrument profile for this engine — change to GUITAR_7STRING, GUITAR_DADGAD, etc.
ENGINE_INSTRUMENT_PROFILE = GUITAR_STANDARD


def _parse_quality(numeral: str) -> str:
    """Map Roman numeral to a chord quality key for the shape library."""
    n = numeral.strip()
    has_lower = any(c.islower() for c in n.lstrip("b#♭♯"))
    has_dim   = "dim" in n.lower() or "°" in n
    has_aug   = "aug" in n.lower() or "+" in n
    has_7     = "7" in n
    has_maj7  = "maj7" in n.lower()
    has_m7    = has_lower and has_7 and not has_maj7
    has_dom7  = (not has_lower) and has_7 and not has_maj7
    has_sus4  = "sus4" in n.lower()
    has_sus2  = "sus2" in n.lower()

    if has_dim:   return "diminished"
    if has_aug:   return "augmented"
    if has_sus4:  return "sus4"
    if has_sus2:  return "sus2"
    if has_maj7:  return "major7"
    if has_m7:    return "minor7"
    if has_dom7:  return "dominant7"
    if has_lower: return "minor"
    return "major"


def choose_acoustic_voicing(
    root_midi: int,
    numeral: str,
    voicing_style: str,                       # "open" | "barre" | "auto"
    prev_voicing: Optional[ResolvedVoicing],  # for voice-leading
    _rng: Optional[random.Random] = None,     # reserved for future variation
    capo: int = 0,
) -> ResolvedVoicing:
    """Return a ResolvedVoicing for this chord.

    Args:
        root_midi:    Root note MIDI pitch (concert pitch, pre-capo).
        numeral:      Roman numeral string ("I", "iv", "bVII", "V7", ...).
        voicing_style: "open" → prefer open shapes; "barre" → movable only;
                       "auto" → open when available, barre otherwise.
        prev_voicing: Previous chord's ResolvedVoicing (for smooth voice-leading).
        rng:          Seeded RNG (reserved, unused currently).
        capo:         Capo fret position.

    Returns:
        ResolvedVoicing with .pitches, .pitch_for_string(), .played_strings, etc.
    """
    quality = _parse_quality(numeral)
    prefer_open = (voicing_style != "barre")

    return select_voicing(
        root_midi=root_midi,
        quality=quality,
        profile=ENGINE_INSTRUMENT_PROFILE,
        capo=capo,
        prev_voicing=prev_voicing,
        prefer_open=prefer_open,
    )
