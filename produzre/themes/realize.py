"""Theme realization: degrees + rhythm -> concrete pitches over harmony.

Realization is a **pure function** of (theme, chord slots, key, mode, genre):
no RNG is involved, which keeps the determinism story airtight. Engines (and
the demo tooling) call `realize_theme` per section.

Pitch policy (see design doc §5):
  1. Degree + accidental maps to a key-relative pitch class.
  2. Chord-tone snapping: if the pitch class is foreign to the active chord
     and one semitone from a chord tone, snap to it — unless the note is a
     recognized genre color tone (b3 / b5 / b7 in blues-family genres).
  3. Voice leading: octave placement prefers the smallest motion from the
     previous realized note, constrained to the theme's register.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

# NOTE: these helpers currently live in melody.py; the design doc proposes
# factoring them into a shared pitch_utils module. The prototype imports them
# to avoid duplicating the tables.
from ..melody import _KEY_PCS, _MODE_OFFSETS, _normalize_key, chord_pitch_classes, fit_pitch_to_range


# Genres where blue notes (b3 / b5 / b7 against the key) are idiomatic and
# must survive chord-tone snapping.
COLOR_GENRES = (
    "blues", "rock", "metal", "punk", "grunge", "funk", "soul", "rnb",
    "hard_rock", "alt",
)

# Degrees (with their accidental) considered color tones: (degree, accidental).
COLOR_TONES = {(3, -1), (5, -1), (7, -1)}


@dataclass(frozen=True)
class RealizedNote:
    """A concrete note produced by realizing a theme over harmony."""

    beat: float              # section-relative beat
    duration_beats: float
    pitch: int               # MIDI note number
    degree_label: str        # e.g. "b3" — provenance for inspection
    numeral: str             # chord active at this beat
    chord_index: int
    occurrence: int          # which theme loop iteration this came from
    snapped: bool = False    # True if chord-tone snapping moved the pitch


def degree_to_pitch_class(degree: int, accidental: int, key: str, mode: str) -> int:
    """Map a key-relative degree + accidental to a pitch class (0-11)."""
    tonic = _KEY_PCS.get(_normalize_key(key), 0)
    scale = _MODE_OFFSETS.get(str(mode or "").lower(), _MODE_OFFSETS["major"])
    return (tonic + scale[(degree - 1) % 7] + accidental) % 12


def _active_slot(chord_slots: Sequence, beat: float):
    """Return the chord slot active at ``beat`` (or None past the last slot)."""
    for slot in chord_slots:
        if float(slot.start_beat) <= beat < float(slot.end_beat):
            return slot
    return None


def realize_theme(
    theme,
    chord_slots: Sequence,
    *,
    key: str,
    mode: str,
    genre: str = "",
    total_beats: Optional[float] = None,
    register: Optional[Tuple[int, int]] = None,
) -> List[RealizedNote]:
    """Realize a theme over a section's chord slots.

    The theme loops on its own length until it covers ``total_beats``
    (default: end of the last chord slot). Each event is realized against the
    chord active at its beat, so a riff tracks the harmony the way a real
    player would fake it.

    Args:
        theme: The (possibly transformed) Theme to realize.
        chord_slots: HarmonySectionPlan.chord_slots for the section.
        key: Section key (already resolved with overrides).
        mode: Section mode (already resolved).
        genre: Song genre; governs whether blue-note color tones survive.
        total_beats: Section length; defaults to the last slot's end.
        register: (low, high) MIDI override; defaults to theme.base_register.

    Returns:
        Ordered list of RealizedNote, section-relative.
    """
    slots = list(chord_slots or [])
    if not slots:
        return []
    end_of_harmony = float(slots[-1].end_beat)
    limit = float(total_beats) if total_beats else end_of_harmony
    lo, hi = register or theme.base_register
    keep_color = any(tok in str(genre or "").lower() for tok in COLOR_GENRES)

    notes: List[RealizedNote] = []
    previous: Optional[int] = None
    occurrence = 0
    occ_start = 0.0

    while occ_start < limit - 1e-9:
        for ev in theme.events:
            beat = occ_start + ev.offset_beats
            if beat >= limit - 1e-9 or ev.is_rest:
                continue
            slot = _active_slot(slots, beat)
            if slot is None:
                continue

            pc = degree_to_pitch_class(ev.degree, ev.accidental, key, mode)
            chord_pcs = set(chord_pitch_classes(slot.numeral, key, mode))
            snapped = False

            if pc not in chord_pcs:
                is_color = keep_color and (ev.degree, ev.accidental) in COLOR_TONES
                if not is_color:
                    neighbors = [c for c in chord_pcs if (pc - c) % 12 in (1, 11)]
                    if neighbors:
                        # Prefer the neighbor in the direction of recent motion.
                        if previous is not None and notes:
                            prev_pc = previous % 12
                            upward = [c for c in neighbors if (c - prev_pc) % 12 <= 6]
                            target = upward[0] if upward else neighbors[0]
                        else:
                            target = neighbors[0]
                        pc = target
                        snapped = True
                    # Whole-step dissonance is left alone: passing tones are legal.

            pitch = fit_pitch_to_range(60 + pc, lo, hi, previous=previous)
            previous = pitch
            notes.append(
                RealizedNote(
                    beat=beat,
                    duration_beats=min(ev.duration_beats, limit - beat),
                    pitch=pitch,
                    degree_label=ev.degree_label(),
                    numeral=slot.numeral,
                    chord_index=int(slot.index),
                    occurrence=occurrence,
                    snapped=snapped,
                )
            )
        occurrence += 1
        occ_start += theme.length_beats

    return notes
