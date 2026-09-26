"""Cadential phrasing: turnarounds that lead one section into the next.

A looped progression treats every bar alike, so sections butt into each
other instead of arriving. Songwriters mark the arrival: in the half bar
before a section returns to the tonic, the harmony moves to a dominant (V,
V7 in blues and soul, bVII in modal rock), and the downbeat that follows
lands as a resolution.

This pass edits a finished section's chord slots in place. It only touches
the final bar, only when the next section starts on the tonic, and only when
the last chord does not already lead there. Explicit progressions are the
user's intent, so they are left alone unless the section (``harmony:
turnaround: true``) or the song (``song.turnarounds: true``) opts in;
progressions chosen from presets or recipes get turnarounds by default.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .plan import ChordSlot, HarmonySectionPlan
from .spelling import _parse_numeral

_MODAL_ROCK = ("rock", "metal", "punk", "grunge", "alt", "stoner", "doom", "emo")
_SEVENTH_GENRES = ("blues", "jazz", "soul", "gospel", "funk", "rnb", "swing", "country")
_MINORISH = ("minor", "aeolian", "dorian", "phrygian")
_FLAT_SEVEN_MODES = ("mixolydian", "dorian", "aeolian", "minor", "phrygian")


def _is_tonic(numeral: str) -> bool:
    degree, accidental, _, _ = _parse_numeral(numeral)
    return degree == 0 and accidental == 0


def _is_dominant(numeral: str) -> bool:
    """V, v, or any seventh-degree chord (bVII, VII, vii°) leads home."""
    degree, accidental, _, _ = _parse_numeral(numeral)
    return (degree == 4 and accidental == 0) or (degree == 6 and accidental in (0, -1))


def turnaround_chord(mode: str, genre: str) -> str:
    """The dominant a genre reaches for before returning home."""
    m = str(mode or "").lower()
    g = str(genre or "").lower()
    if any(t in g for t in _SEVENTH_GENRES):
        return "V7"
    if any(t in g for t in _MODAL_ROCK) and m in _FLAT_SEVEN_MODES:
        return "bVII"
    if m == "mixolydian":
        return "bVII"
    return "V"


def wants_turnaround(section: Any, cfg: Any, source: str) -> bool:
    harmony = getattr(section, "harmony", None)
    extra = getattr(harmony, "extra", None) or {}
    if "turnaround" in extra:
        return bool(extra.get("turnaround"))
    raw = getattr(cfg, "raw", None)
    song = raw.get("song", {}) if isinstance(raw, dict) else {}
    if isinstance(song, dict) and "turnarounds" in song:
        return bool(song.get("turnarounds"))
    return source != "explicit"


def apply_turnaround(
    plan: Optional[HarmonySectionPlan],
    next_plan: Optional[HarmonySectionPlan],
    *,
    mode: str,
    genre: str,
    logger: Optional[logging.Logger] = None,
) -> bool:
    """Split the final bar so its second half leads into ``next_plan``."""
    if plan is None or next_plan is None or not plan.chord_slots or not next_plan.chord_slots:
        return False
    target = next_plan.chord_slots[0].numeral
    if not _is_tonic(target):
        return False
    last = plan.chord_slots[-1]
    bpb = float(getattr(plan.meter, "beats_per_bar", 4.0) or 4.0)
    length = float(last.end_beat) - float(last.start_beat)
    if length < bpb - 1e-6 or _is_dominant(last.numeral):
        return False
    chord = turnaround_chord(mode, genre)
    if chord == last.numeral:
        return False
    half = bpb / 2.0
    split = float(last.end_beat) - half
    plan.chord_slots[-1] = ChordSlot(last.index, last.numeral, float(last.start_beat), split)
    plan.chord_slots.append(ChordSlot(last.index + 1, chord, split, float(last.end_beat)))
    if logger:
        logger.info("Section '%s': turnaround %s -> %s into %s", plan.section_id,
                    last.numeral, chord, target)
    return True
