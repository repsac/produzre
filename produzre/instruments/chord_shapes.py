"""Physics-based chord shape library for stringed instruments.

Chord voicings are expressed as fret positions on individual strings, not as
piano-style interval templates. This produces physically playable chords that
respect the guitar's CAGED system: open position shapes for common keys, plus
movable barre forms for any key.

Public API:
    select_voicing(root_midi, quality, profile, capo, prev_voicing, prefer_open)
        -> ResolvedVoicing

    ResolvedVoicing
        .pitches           -> List[int]          # sorted MIDI pitches
        .pitch_for_string(idx) -> Optional[int]  # None if muted
        .played_strings    -> List[int]           # non-muted string indices
        .fret_center       -> float               # avg fret (voice-leading key)

Internal structure:
    GuitarShape  — open position chord (standard tuning, absolute frets)
    ChordForm    — movable barre form (any tuning, frets relative to root)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .profile import InstrumentProfile, GUITAR_STANDARD

logger = logging.getLogger(__name__)


# ===========================================================================
# Data structures
# ===========================================================================

@dataclass(frozen=True)
class GuitarShape:
    """Open-position chord shape for a specific tuning.

    Frets are absolute (what the player fingers), -1 means muted.
    Open strings are fret 0.
    """
    name: str
    quality: str
    frets: Tuple[int, ...]          # one entry per string, -1 = muted
    profile: InstrumentProfile


@dataclass(frozen=True)
class ChordForm:
    """Movable barre chord form (tuning-agnostic).

    rel_frets are relative to the root fret. -1 means muted.
    root_string is the string index (0 = lowest) that carries the root note.
    """
    name: str
    quality: str
    root_string: int                # string index carrying the root
    rel_frets: Tuple[int, ...]      # relative frets from root; -1 = muted
    min_strings: int = 4            # minimum non-muted strings required


@dataclass
class ResolvedVoicing:
    """A fully resolved chord voicing for a specific instrument and capo.

    frets: absolute fret positions per string (after capo), -1 = muted.
    Sounding pitch = open_tuning[i] + frets[i] + capo  (for frets[i] >= 0).
    """
    profile: InstrumentProfile
    frets: Tuple[int, ...]
    capo: int
    shape_name: str

    @property
    def pitches(self) -> List[int]:
        """Sorted MIDI pitches for all non-muted strings."""
        result = []
        for i, f in enumerate(self.frets):
            if f >= 0:
                result.append(self.profile.open_tuning[i] + f + self.capo)
        return sorted(result)

    def pitch_for_string(self, string_idx: int) -> Optional[int]:
        """MIDI pitch for a physical string index, or None if muted.

        string_idx 0 = lowest string (bass E on standard guitar).
        """
        if string_idx < 0 or string_idx >= len(self.frets):
            return None
        f = self.frets[string_idx]
        if f < 0:
            return None
        return self.profile.open_tuning[string_idx] + f + self.capo

    @property
    def played_strings(self) -> List[int]:
        """Indices of non-muted strings (ascending)."""
        return [i for i, f in enumerate(self.frets) if f >= 0]

    @property
    def fret_center(self) -> float:
        """Average fret position of non-muted, non-open strings.

        Used for voice-leading: compare fret_center values to find the
        nearest-position chord shape across a progression.
        """
        played_frets = [f for f in self.frets if f > 0]  # exclude open (0) and muted (-1)
        if not played_frets:
            return 0.0
        return sum(played_frets) / len(played_frets)


# ===========================================================================
# Open chord shapes — standard guitar tuning (E2-A2-D3-G3-B3-E4)
# ===========================================================================
# Keyed by (root_pitch_class, quality).
# root_pitch_class: 0=C, 1=C#/Db, 2=D, 3=D#/Eb, 4=E, 5=F, 6=F#/Gb,
#                   7=G, 8=G#/Ab, 9=A, 10=A#/Bb, 11=B
#
# Fret arrays: one per string in order (low E → high E)
# -1 = muted, 0 = open string, N = finger on fret N
#
# Shapes verified against standard guitar chord diagrams.

_OPEN_SHAPES_RAW: List[Tuple[int, str, Tuple[int, ...], str]] = [
    # (root_pc, quality, frets, shape_name)

    # --- E major family ---
    (4,  "major",     (0, 2, 2, 1, 0, 0),   "E_major"),
    (4,  "minor",     (0, 2, 2, 0, 0, 0),   "Em"),
    (4,  "dominant7", (0, 2, 0, 1, 0, 0),   "E7"),
    (4,  "minor7",    (0, 2, 0, 0, 0, 0),   "Em7"),
    (4,  "major7",    (0, 2, 1, 1, 0, 0),   "Emaj7"),
    (4,  "sus4",      (0, 2, 2, 2, 0, 0),   "Esus4"),

    # --- A major family ---
    (9,  "major",     (-1, 0, 2, 2, 2, 0),  "A_major"),
    (9,  "minor",     (-1, 0, 2, 2, 1, 0),  "Am"),
    (9,  "dominant7", (-1, 0, 2, 0, 2, 0),  "A7"),
    (9,  "minor7",    (-1, 0, 2, 0, 1, 0),  "Am7"),
    (9,  "major7",    (-1, 0, 2, 1, 2, 0),  "Amaj7"),
    (9,  "sus2",      (-1, 0, 2, 2, 0, 0),  "Asus2"),
    (9,  "sus4",      (-1, 0, 2, 2, 3, 0),  "Asus4"),

    # --- D major family ---
    (2,  "major",     (-1, -1, 0, 2, 3, 2), "D_major"),
    (2,  "minor",     (-1, -1, 0, 2, 3, 1), "Dm"),
    (2,  "dominant7", (-1, -1, 0, 2, 1, 2), "D7"),
    (2,  "major7",    (-1, -1, 0, 2, 2, 2), "Dmaj7"),
    (2,  "sus2",      (-1, -1, 0, 2, 3, 0), "Dsus2"),
    (2,  "sus4",      (-1, -1, 0, 2, 3, 3), "Dsus4"),

    # --- G major family ---
    (7,  "major",     (3, 2, 0, 0, 0, 3),   "G_major"),
    (7,  "dominant7", (3, 2, 0, 0, 0, 1),   "G7"),
    (7,  "major7",    (3, 2, 0, 0, 0, 2),   "Gmaj7"),
    (7,  "minor",     (3, 5, 5, 3, 3, 3),   "Gm_barre"),  # barre at 3rd fret E-form

    # --- C major family ---
    (0,  "major",     (-1, 3, 2, 0, 1, 0),  "C_major"),
    (0,  "dominant7", (-1, 3, 2, 3, 1, 0),  "C7"),
    (0,  "major7",    (-1, 3, 2, 0, 0, 0),  "Cmaj7"),
    (0,  "minor",     (-1, 3, 5, 5, 4, 3),  "Cm_barre"),  # barre at 3rd fret A-form

    # --- B chord ---
    (11, "minor",     (-1, 2, 4, 4, 3, 2),  "Bm"),
    (11, "diminished",(-1, 2, 3, 4, 3, -1), "Bdim"),

    # --- Other open-position specials ---
    (7,  "augmented", (3, 2, 1, 0, 0, -1),  "Gaug"),
]

# Build the lookup dict. Only shapes for standard tuning are included here.
# The select_voicing() function falls through to movable forms for other profiles.
_OPEN_SHAPES: Dict[Tuple[int, str], GuitarShape] = {
    (root_pc, quality): GuitarShape(
        name=name,
        quality=quality,
        frets=frets,
        profile=GUITAR_STANDARD,
    )
    for root_pc, quality, frets, name in _OPEN_SHAPES_RAW
}


# ===========================================================================
# Movable barre forms (tuning-agnostic, relative frets from root)
# ===========================================================================

_MOVABLE_FORMS: List[ChordForm] = [
    # E-form shapes (root on lowest string, string 0)
    ChordForm("E-form_major",    "major",     0, (0, 2, 2, 1, 0, 0), min_strings=5),
    ChordForm("E-form_minor",    "minor",     0, (0, 2, 2, 0, 0, 0), min_strings=5),
    ChordForm("E-form_dom7",     "dominant7", 0, (0, 2, 0, 1, 0, 0), min_strings=5),
    ChordForm("E-form_min7",     "minor7",    0, (0, 2, 0, 0, 0, 0), min_strings=5),
    ChordForm("E-form_maj7",     "major7",    0, (0, 2, 1, 1, 0, 0), min_strings=5),

    # A-form shapes (root on string 1)
    ChordForm("A-form_major",    "major",     1, (-1, 0, 2, 2, 2, 0), min_strings=4),
    ChordForm("A-form_minor",    "minor",     1, (-1, 0, 2, 2, 1, 0), min_strings=4),
    ChordForm("A-form_dom7",     "dominant7", 1, (-1, 0, 2, 0, 2, 0), min_strings=4),
    ChordForm("A-form_min7",     "minor7",    1, (-1, 0, 2, 0, 1, 0), min_strings=4),
    ChordForm("A-form_sus2",     "sus2",      1, (-1, 0, 2, 2, 0, 0), min_strings=4),
    ChordForm("A-form_sus4",     "sus4",      1, (-1, 0, 2, 2, 3, 0), min_strings=4),

    # D-form shapes (root on string 2)
    ChordForm("D-form_major",    "major",     2, (-1, -1, 0, 2, 2, 1), min_strings=4),
    ChordForm("D-form_minor",    "minor",     2, (-1, -1, 0, 2, 2, 0), min_strings=4),
]


# ===========================================================================
# Quality alias map — normalise extended quality names to keys used above
# ===========================================================================

_QUALITY_ALIASES: Dict[str, str] = {
    "maj":    "major",
    "min":    "minor",
    "m":      "minor",
    "dom7":   "dominant7",
    "7":      "dominant7",
    "maj7":   "major7",
    "min7":   "minor7",
    "m7":     "minor7",
    "dim":    "diminished",
    "°":      "diminished",
    "aug":    "augmented",
    "+":      "augmented",
    "sus2":   "sus2",
    "sus4":   "sus4",
}

# Qualities with no open/movable shape → map to nearest playable quality
_QUALITY_FALLBACK: Dict[str, str] = {
    "diminished": "minor",
    "augmented":  "major",
    "minor7":     "minor",
    "major7":     "major",
    "sus2":       "major",
    "sus4":       "major",
    "dominant7":  "major",
}


def _normalize_quality(quality: str) -> str:
    """Normalize quality string to a key used in shape dicts."""
    q = quality.strip().lower()
    return _QUALITY_ALIASES.get(q, q)


# ===========================================================================
# Chord tone helper (for fallback voicing)
# ===========================================================================

_QUALITY_INTERVALS: Dict[str, Tuple[int, ...]] = {
    "major":     (0, 4, 7),
    "minor":     (0, 3, 7),
    "dominant7": (0, 4, 7, 10),
    "major7":    (0, 4, 7, 11),
    "minor7":    (0, 3, 7, 10),
    "sus2":      (0, 2, 7),
    "sus4":      (0, 5, 7),
    "diminished":(0, 3, 6),
    "augmented": (0, 4, 8),
}


def _chord_tone_pcs(root_pc: int, quality: str) -> Tuple[int, ...]:
    """Pitch classes for all notes in the chord (mod 12)."""
    intervals = _QUALITY_INTERVALS.get(quality, (0, 4, 7))
    return tuple((root_pc + iv) % 12 for iv in intervals)


# ===========================================================================
# Validation helpers
# ===========================================================================

def _fret_span(frets: Tuple[int, ...]) -> int:
    """Max fret minus min non-zero fret (span the fingers must cover)."""
    played = [f for f in frets if f > 0]
    if len(played) < 2:
        return 0
    return max(played) - min(played)


def _is_valid_shape(frets: Tuple[int, ...], profile: InstrumentProfile) -> bool:
    """Return True if frets are physically playable on this instrument."""
    if len(frets) != profile.num_strings:
        return False
    played = [f for f in frets if f >= 0]
    if not played:
        return False
    if any(f > profile.num_frets for f in played):
        return False
    if _fret_span(frets) > profile.max_fret_span:
        return False
    return True


# ===========================================================================
# Open shape lookup
# ===========================================================================

def _try_open_shape(
    root_pc: int,
    quality: str,
    profile: InstrumentProfile,
) -> Optional[ResolvedVoicing]:
    """Return a ResolvedVoicing for an open-position shape, or None."""
    # Open shapes are only defined for standard tuning
    if profile.open_tuning != GUITAR_STANDARD.open_tuning:
        return None

    shape = _OPEN_SHAPES.get((root_pc, quality))
    if shape is None:
        return None

    # Validate (open shapes are pre-validated, but check span for safety)
    if not _is_valid_shape(shape.frets, profile):
        return None

    return ResolvedVoicing(
        profile=profile,
        frets=shape.frets,
        capo=0,
        shape_name=shape.name,
    )


# ===========================================================================
# Movable shape resolution
# ===========================================================================

def _resolve_movable(
    root_midi: int,
    quality: str,
    profile: InstrumentProfile,
    capo: int,
) -> Optional[ResolvedVoicing]:
    """Find a movable barre form that fits this root and quality."""
    if not profile.barre_capable:
        return None

    # Find forms matching quality, trying E-form first, then A-form, then D-form
    candidates = [f for f in _MOVABLE_FORMS if f.quality == quality]

    # Also try quality fallback if no exact match
    if not candidates:
        fallback_q = _QUALITY_FALLBACK.get(quality)
        if fallback_q:
            candidates = [f for f in _MOVABLE_FORMS if f.quality == fallback_q]

    for form in candidates:
        if form.root_string >= profile.num_strings:
            continue
        if len(form.rel_frets) > profile.num_strings:
            continue

        # Root fret: how far up the neck to place the root
        root_fret = root_midi - capo - profile.open_tuning[form.root_string]
        if root_fret < 1:  # can't play open strings as a barre
            continue
        if root_fret > profile.num_frets - profile.max_fret_span:
            continue

        # Build absolute fret array, padding muted strings for shorter forms
        n = profile.num_strings
        abs_frets_list: List[int] = []
        for i in range(n):
            if i < len(form.rel_frets):
                rel = form.rel_frets[i]
                abs_frets_list.append(-1 if rel == -1 else root_fret + rel)
            else:
                abs_frets_list.append(-1)  # extra strings are muted
        abs_frets = tuple(abs_frets_list)

        # Validate
        if not _is_valid_shape(abs_frets, profile):
            continue

        # Check min_strings constraint
        played = [f for f in abs_frets if f >= 0]
        if len(played) < form.min_strings:
            continue

        return ResolvedVoicing(
            profile=profile,
            frets=abs_frets,
            capo=capo,
            shape_name=f"{form.name}@fret{root_fret}",
        )

    return None


# ===========================================================================
# Fallback voicing (greedy chord tone assignment)
# ===========================================================================

def _fallback_voicing(
    root_midi: int,
    quality: str,
    profile: InstrumentProfile,
    capo: int,
) -> ResolvedVoicing:
    """Last-resort voicing: assign chord tones to strings greedily.

    Walks strings from lowest to highest. For each string, finds the lowest
    fret that produces a chord tone, within max_fret_span of the lowest
    assigned fret (or any fret for the first string).
    """
    root_pc = root_midi % 12
    tone_pcs = _chord_tone_pcs(root_pc, quality)

    frets_list = [-1] * profile.num_strings
    min_fret_used: Optional[int] = None
    notes_placed = 0

    for i, open_pitch in enumerate(profile.open_tuning):
        effective_open = open_pitch + capo
        # Find lowest fret giving a chord tone
        for fret in range(0, profile.num_frets + 1):
            pitch_pc = (effective_open + fret) % 12
            if pitch_pc in tone_pcs:
                # Check fret span constraint
                if min_fret_used is None or fret == 0:
                    frets_list[i] = fret
                    if fret > 0 and min_fret_used is None:
                        min_fret_used = fret
                    elif fret > 0:
                        min_fret_used = min(min_fret_used, fret)
                    notes_placed += 1
                    break
                else:
                    max_allowed = min_fret_used + profile.max_fret_span
                    if fret <= max_allowed:
                        frets_list[i] = fret
                        min_fret_used = min(min_fret_used, fret)
                        notes_placed += 1
                        break
                # If fret exceeds span, leave this string muted

    # Ensure at least root is present (place root on lowest string if nothing)
    if notes_placed == 0:
        # Place root on first string at whatever fret is needed
        target_pc = root_pc
        for fret in range(0, profile.num_frets + 1):
            if (profile.open_tuning[0] + capo + fret) % 12 == target_pc:
                frets_list[0] = fret
                break

    return ResolvedVoicing(
        profile=profile,
        frets=tuple(frets_list),
        capo=capo,
        shape_name=f"fallback_{quality}",
    )


# ===========================================================================
# Voice leading
# ===========================================================================

def _apply_voice_leading(
    candidate: ResolvedVoicing,
    prev_voicing: Optional[ResolvedVoicing],
) -> ResolvedVoicing:
    """Prefer the octave transposition of candidate closest to prev_voicing.

    For movable shapes (no open strings), shifting the shape by ±12 semitones
    (one octave) moves it to a different neck position. This selects the
    position nearest to where the player's hand already is.
    """
    if prev_voicing is None:
        return candidate

    # Check if candidate has any open strings — open shapes can't be transposed
    has_open = any(f == 0 for f in candidate.frets if f >= 0)
    if has_open:
        return candidate

    prev_center = prev_voicing.fret_center
    cand_center = candidate.fret_center
    best = candidate
    best_dist = abs(cand_center - prev_center)

    profile = candidate.profile

    # Try shifting the shape by ±12 semitones (±12 = one string step on guitar ≈ 5 frets)
    # In practice: shift frets by ±5 (perfect fourth interval between adjacent strings)
    # A 12-semitone shift on a single-string instrument = 12 frets up/down
    # On guitar: different root string needed, so we try ±5 fret shifts as approximation
    for delta in (-12, +12):
        # Convert semitone delta to fret delta (same for all strings: 1 semitone = 1 fret)
        fret_delta = delta
        new_frets = tuple(
            f + fret_delta if f > 0 else f  # don't move muted (-1) or open (0) strings
            for f in candidate.frets
        )
        # Validate
        if not _is_valid_shape(new_frets, profile):
            continue
        # All frets must be positive (no accidental open strings)
        if any(0 < f + fret_delta < 1 for f in candidate.frets if f > 0):
            continue

        test = ResolvedVoicing(
            profile=profile,
            frets=new_frets,
            capo=candidate.capo,
            shape_name=candidate.shape_name + f"_oct{'+' if delta>0 else ''}{delta}",
        )
        dist = abs(test.fret_center - prev_center)
        if dist < best_dist:
            best_dist = dist
            best = test

    return best


# ===========================================================================
# Main public API
# ===========================================================================

def select_voicing(
    root_midi: int,
    quality: str,
    profile: InstrumentProfile = GUITAR_STANDARD,
    capo: int = 0,
    prev_voicing: Optional[ResolvedVoicing] = None,
    prefer_open: bool = True,
) -> ResolvedVoicing:
    """Select a physically playable chord voicing for the given parameters.

    Resolution order:
      1) Open-position shape (if prefer_open and root_pc has a known shape)
      2) Movable barre form (E-form, A-form, or D-form)
      3) Fallback greedy assignment (always succeeds)

    Voice leading is applied at the end: for movable shapes, the nearest
    neck position to prev_voicing is preferred.

    Args:
        root_midi:    Root note as MIDI pitch (concert pitch, before capo).
        quality:      Chord quality: "major", "minor", "dominant7", etc.
        profile:      Instrument profile (tuning, fret count, etc.).
        capo:         Capo fret position (0 = no capo).
        prev_voicing: Previous chord's ResolvedVoicing for voice-leading.
        prefer_open:  If True, try open shapes first (for "open" and "auto" styles).

    Returns:
        ResolvedVoicing with fret positions and all pitch/string helpers.
    """
    quality = _normalize_quality(quality)

    # Pre-capo root pitch class: what the player sees on the nut/fretboard
    effective_root = root_midi - capo
    root_pc = effective_root % 12

    result: Optional[ResolvedVoicing] = None

    # Step 1: Open shapes (only when preferred and we have a shape for this key)
    if prefer_open:
        result = _try_open_shape(root_pc, quality, profile)
        if result is None and quality in _QUALITY_FALLBACK:
            fallback_q = _QUALITY_FALLBACK[quality]
            result = _try_open_shape(root_pc, fallback_q, profile)

    # Step 2: Movable barre forms
    if result is None:
        result = _resolve_movable(root_midi, quality, profile, capo)

    # Step 3: Greedy fallback (always succeeds)
    if result is None:
        logger.debug(
            "chord_shapes: using fallback voicing for root_pc=%d quality=%s",
            root_pc, quality,
        )
        result = _fallback_voicing(root_midi, quality, profile, capo)

    # Apply voice leading
    result = _apply_voice_leading(result, prev_voicing)

    return result


def resolve_pitches_to_voicing(
    pitches: List[int],
    root_midi: int,
    profile: InstrumentProfile = GUITAR_STANDARD,
    capo: int = 0,
) -> ResolvedVoicing:
    """Reverse-map MIDI pitches to string/fret positions on an instrument.

    Given a set of MIDI pitches (as produced by pitch-based voicing engines
    like rhythm_gtr), find the best-fit fret assignment per string. This
    enables tab rendering and string-aware analysis for any instrument engine.

    The algorithm finds the assignment that minimizes fret span across all
    notes, producing compact neck positions like a real guitarist would play.
    For chords with 6 or fewer notes, all valid assignments are evaluated.

    Args:
        pitches:    MIDI pitches to place on the instrument.
        root_midi:  Root note (used for shape_name only).
        profile:    Instrument profile with tuning and fret info.
        capo:       Capo fret position (0 = no capo).

    Returns:
        ResolvedVoicing with fret positions per string (-1 = muted).
    """
    sorted_pitches = sorted(pitches)
    n = profile.num_strings

    if not sorted_pitches:
        return ResolvedVoicing(
            profile=profile,
            frets=tuple([-1] * n),
            capo=capo,
            shape_name=f"resolved@root{root_midi}",
        )

    # Build candidates: for each pitch, list of (string_index, fret) options
    candidates: List[List[Tuple[int, int]]] = []
    for pitch in sorted_pitches:
        options = []
        for s in range(n):
            fret = pitch - profile.open_tuning[s] - capo
            if 0 <= fret <= profile.num_frets:
                options.append((s, fret))
        candidates.append(options)

    # Find the best assignment using recursive search with pruning.
    # With at most 6 pitches and ~6 string options each, the search space
    # is small enough for exhaustive evaluation.
    best_frets: Optional[List[int]] = None
    best_score = float("inf")

    def _full_span(frets: List[int]) -> int:
        """Span including open strings — prevents open+high-fret combos."""
        active = [f for f in frets if f >= 0]
        if len(active) < 2:
            return 0
        return max(active) - min(active)

    def _search(
        pitch_idx: int,
        current_frets: List[int],
        used_strings: set,
    ) -> None:
        nonlocal best_frets, best_score

        if pitch_idx == len(sorted_pitches):
            # Score: full span (including open strings) + average fret
            span = _full_span(current_frets)
            avg_fret = sum(f for f in current_frets if f >= 0) / max(1, sum(1 for f in current_frets if f >= 0))
            # Primary: minimize span; secondary: prefer lower positions
            score = span * 100 + avg_fret
            if score < best_score:
                best_score = score
                best_frets = list(current_frets)
            return

        for s, fret in candidates[pitch_idx]:
            if s in used_strings:
                continue
            # Prune: check full span (including open strings)
            test_frets = list(current_frets)
            test_frets[s] = fret
            if _full_span(test_frets) > profile.max_fret_span:
                continue

            current_frets[s] = fret
            used_strings.add(s)
            _search(pitch_idx + 1, current_frets, used_strings)
            current_frets[s] = -1
            used_strings.remove(s)

    _search(0, [-1] * n, set())

    if best_frets is None:
        # Fallback: greedy assignment (should not normally happen)
        best_frets = [-1] * n
        assigned: set = set()
        for pitch in sorted_pitches:
            for s in range(n):
                if s in assigned:
                    continue
                fret = pitch - profile.open_tuning[s] - capo
                if 0 <= fret <= profile.num_frets:
                    best_frets[s] = fret
                    assigned.add(s)
                    break

    return ResolvedVoicing(
        profile=profile,
        frets=tuple(best_frets),
        capo=capo,
        shape_name=f"resolved@root{root_midi}",
    )
