"""Guitar chord voicing for rhythm guitar — adapter over shared physics library.

Delegates voicing to ``produzre.instruments.chord_shapes.select_voicing()``
which uses CAGED-system shapes and fret-span validation to produce physically
playable chords. This replaces the previous interval-math approach that could
generate impossible fret positions.

Voicing styles supported:
- power:   Root + fifth on 2-3 adjacent low strings (direct construction)
- triad:   Full CAGED chord shape (open or barre)
- shell:   Root + third + seventh on upper strings (jazz comping)
- octaves: Root note in two octaves on non-adjacent strings
- auto:    Section-type heuristic selects one of the above
"""

from __future__ import annotations

import random
from typing import Optional

from ...instruments.chord_shapes import ResolvedVoicing, select_voicing
from ...instruments.profile import GUITAR_STANDARD, InstrumentProfile

from .types import ChordShape

# Guitar standard tuning — open string MIDI pitches (low to high)
_PROFILE = GUITAR_STANDARD


# ---------------------------------------------------------------------------
# Quality parsing (shared with acoustic_gtr — duplicated for decoupling)
# ---------------------------------------------------------------------------

def _parse_quality(numeral: str) -> str:
    """Map a Roman numeral string to a chord quality key."""
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


# ---------------------------------------------------------------------------
# Power chord construction (direct, no shared library needed)
# ---------------------------------------------------------------------------

def _build_power_chord(
    root_midi: int,
    profile: InstrumentProfile,
    prev_voicing: Optional[ResolvedVoicing] = None,
) -> ResolvedVoicing:
    """Build a 2-3 string power chord rooted on the lowest suitable string.

    Power chords are root + fifth + optional octave on adjacent strings.
    We find the string where the root falls at a comfortable fret, then
    add the fifth (+2 frets on the next string) and octave (+2 frets, +1 string).

    Shape patterns:
      E-string root: (N, N+2, N+2, -1, -1, -1)   strings 0-1-2
      A-string root: (-1, N, N+2, N+2, -1, -1)    strings 1-2-3
      D-string root: (-1, -1, N, N+2, N+2, -1)    strings 2-3-4 (rare but valid)
    """
    n = profile.num_strings
    best: Optional[ResolvedVoicing] = None
    best_score = -1.0

    # Try rooting on each of the lower strings (0, 1, 2 for 6-string guitar)
    for root_string in range(min(3, n - 2)):
        root_fret = root_midi - profile.open_tuning[root_string]
        if root_fret < 0 or root_fret > profile.num_frets:
            continue

        # Fifth is +2 frets on next string (works for standard tuning intervals)
        # Actually: 5th = root + 7 semitones. On adjacent string (5 semitones apart),
        # the 5th is at root_fret + 2.
        fifth_string = root_string + 1
        if fifth_string >= n:
            continue
        fifth_fret = (root_midi + 7) - profile.open_tuning[fifth_string]
        if fifth_fret < 0 or fifth_fret > profile.num_frets:
            continue

        # Octave on the string after that
        octave_string = root_string + 2
        octave_fret = -1
        if octave_string < n:
            oct_fret = (root_midi + 12) - profile.open_tuning[octave_string]
            if 0 <= oct_fret <= profile.num_frets:
                octave_fret = oct_fret

        # Build fret array
        frets = [-1] * n
        frets[root_string] = root_fret
        frets[fifth_string] = fifth_fret
        if octave_fret >= 0:
            frets[octave_string] = octave_fret

        # Check fret span
        played = [f for f in frets if f > 0]
        if len(played) >= 2 and (max(played) - min(played)) > profile.max_fret_span:
            continue

        # Score: prefer lower frets, prefer low strings for heavy sound
        fret_avg = sum(f for f in frets if f >= 0) / max(1, sum(1 for f in frets if f >= 0))
        score = 100 - fret_avg - root_string * 5  # lower fret and lower string = better

        # Voice leading: prefer position near previous chord
        if prev_voicing is not None:
            prev_center = prev_voicing.fret_center
            dist = abs(fret_avg - prev_center)
            score -= dist * 2  # penalize large jumps

        if score > best_score:
            best_score = score
            best = ResolvedVoicing(
                profile=profile,
                frets=tuple(frets),
                capo=0,
                shape_name=f"power@fret{root_fret}",
            )

    # Fallback: if nothing works (e.g., root too low), try open power chord
    if best is None:
        # Place root on lowest string at whatever fret
        root_fret = root_midi - profile.open_tuning[0]
        # Shift into range
        while root_fret < 0:
            root_fret += 12
        while root_fret > profile.num_frets:
            root_fret -= 12
        root_fret = max(0, root_fret)

        fifth_fret = root_fret + 2
        if fifth_fret > profile.num_frets:
            fifth_fret = root_fret  # degenerate but safe

        frets = [-1] * n
        frets[0] = root_fret
        frets[1] = fifth_fret
        best = ResolvedVoicing(
            profile=profile,
            frets=tuple(frets),
            capo=0,
            shape_name=f"power_fallback@fret{root_fret}",
        )

    return best


# ---------------------------------------------------------------------------
# Shell voicing (root + 3rd + 7th on upper strings)
# ---------------------------------------------------------------------------

def _build_shell_voicing(
    root_midi: int,
    quality: str,
    profile: InstrumentProfile,
    prev_voicing: Optional[ResolvedVoicing] = None,
) -> ResolvedVoicing:
    """Build a shell voicing: root + 3rd + 7th, omitting the 5th.

    Shell voicings typically live on the middle/upper strings (D-G-B or G-B-E).
    We get a full 7th chord voicing from the shared library, then mute the
    lowest strings to isolate the shell tones.
    """
    # Ensure we request a 7th chord quality for shell voicing
    shell_quality = quality
    if quality == "major":
        shell_quality = "major7"
    elif quality == "minor":
        shell_quality = "minor7"
    elif quality not in ("dominant7", "major7", "minor7"):
        shell_quality = "dominant7"  # default to dom7 for unknown qualities

    rv = select_voicing(
        root_midi=root_midi,
        quality=shell_quality,
        profile=profile,
        capo=0,
        prev_voicing=prev_voicing,
        prefer_open=False,  # Shell voicings are typically barre/movable
    )

    # Mute the lowest 2-3 strings to create a shell texture
    frets_list = list(rv.frets)
    # Find how many strings are played
    played_count = sum(1 for f in frets_list if f >= 0)

    if played_count > 3:
        # Mute from the bottom until we have 3-4 strings
        for i in range(len(frets_list)):
            if frets_list[i] >= 0 and played_count > 4:
                frets_list[i] = -1
                played_count -= 1

    return ResolvedVoicing(
        profile=profile,
        frets=tuple(frets_list),
        capo=0,
        shape_name=f"shell_{rv.shape_name}",
    )


# ---------------------------------------------------------------------------
# Octave voicing (root in two octaves)
# ---------------------------------------------------------------------------

def _build_octave_voicing(
    root_midi: int,
    profile: InstrumentProfile,
    prev_voicing: Optional[ResolvedVoicing] = None,
) -> ResolvedVoicing:
    """Build an octave voicing: root note on two strings an octave apart.

    Common octave shapes on guitar:
      String 0 + String 2: root on E, octave on D (fret + 2)
      String 1 + String 3: root on A, octave on G (fret + 2)
      String 2 + String 4: root on D, octave on B (fret + 3, due to B string tuning)
    """
    n = profile.num_strings
    best: Optional[ResolvedVoicing] = None
    best_score = -1.0

    root_pc = root_midi % 12

    # Try pairs of strings that are 2 apart (octave pairs on guitar)
    for lo_string in range(n - 2):
        hi_string = lo_string + 2

        lo_fret = root_midi - profile.open_tuning[lo_string]
        hi_fret = (root_midi + 12) - profile.open_tuning[hi_string]

        # Also try: root on hi, lower octave on lo
        if lo_fret < 0 or lo_fret > profile.num_frets:
            # Try lower octave
            lo_fret = (root_midi - 12) - profile.open_tuning[lo_string]
            hi_fret = root_midi - profile.open_tuning[hi_string]

        if lo_fret < 0 or lo_fret > profile.num_frets:
            continue
        if hi_fret < 0 or hi_fret > profile.num_frets:
            continue

        # Check span
        played = [f for f in (lo_fret, hi_fret) if f > 0]
        if len(played) >= 2 and (max(played) - min(played)) > profile.max_fret_span:
            continue

        frets = [-1] * n
        frets[lo_string] = lo_fret
        frets[hi_string] = hi_fret

        fret_avg = (lo_fret + hi_fret) / 2.0
        score = 100 - fret_avg

        if prev_voicing is not None:
            dist = abs(fret_avg - prev_voicing.fret_center)
            score -= dist * 2

        if score > best_score:
            best_score = score
            best = ResolvedVoicing(
                profile=profile,
                frets=tuple(frets),
                capo=0,
                shape_name=f"octave@fret{lo_fret}",
            )

    if best is None:
        # Fallback: single note
        frets = [-1] * n
        fret = root_midi - profile.open_tuning[0]
        while fret < 0:
            fret += 12
        while fret > profile.num_frets:
            fret -= 12
        frets[0] = max(0, fret)
        best = ResolvedVoicing(
            profile=profile,
            frets=tuple(frets),
            capo=0,
            shape_name="octave_fallback",
        )

    return best


# ---------------------------------------------------------------------------
# Conversion helper
# ---------------------------------------------------------------------------

def _resolved_to_chord_shape(
    rv: ResolvedVoicing,
    root_midi: int,
    numeral: str,
    voicing_name: str,
) -> ChordShape:
    """Convert a ResolvedVoicing to the rhythm_gtr ChordShape type."""
    is_major = not any(c.islower() for c in numeral.strip().lstrip("b#♭♯") if c.isalpha())

    return ChordShape(
        root_midi=root_midi,
        pitches=rv.pitches,
        numeral=numeral,
        is_major=is_major,
        inversion=0,
        voicing_name=voicing_name,
        resolved=rv,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def choose_voicing(
    root_midi: int,
    numeral: str,
    voicing_style: str,
    prev_chord_shape: Optional[ChordShape] = None,
    register_min: Optional[int] = None,
    register_max: Optional[int] = None,
    rng: Optional[random.Random] = None,
) -> ChordShape:
    """Choose a physically playable guitar chord voicing.

    Delegates to the shared instruments library for CAGED-system chord shapes
    with fret-span validation and voice leading.

    Args:
        root_midi: Root note MIDI number
        numeral: Roman numeral (e.g., "I", "iv", "V7")
        voicing_style: "power", "triad", "shell", "octaves"
        prev_chord_shape: Previous chord for voice leading
        register_min: Ignored (kept for API compat)
        register_max: Ignored (kept for API compat)
        rng: Random number generator (reserved)

    Returns:
        ChordShape with physically playable voicing and ResolvedVoicing attached
    """
    quality = _parse_quality(numeral)
    prev_rv = prev_chord_shape.resolved if prev_chord_shape else None

    if voicing_style == "power":
        rv = _build_power_chord(root_midi, _PROFILE, prev_rv)
        voicing_name = "power"

    elif voicing_style == "shell":
        rv = _build_shell_voicing(root_midi, quality, _PROFILE, prev_rv)
        voicing_name = "shell"

    elif voicing_style == "octaves":
        rv = _build_octave_voicing(root_midi, _PROFILE, prev_rv)
        voicing_name = "octaves"

    elif voicing_style == "triad":
        rv = select_voicing(
            root_midi=root_midi,
            quality=quality,
            profile=_PROFILE,
            capo=0,
            prev_voicing=prev_rv,
            prefer_open=True,
        )
        voicing_name = rv.shape_name

    else:
        # Default to full chord shape
        rv = select_voicing(
            root_midi=root_midi,
            quality=quality,
            profile=_PROFILE,
            capo=0,
            prev_voicing=prev_rv,
            prefer_open=True,
        )
        voicing_name = rv.shape_name

    return _resolved_to_chord_shape(rv, root_midi, numeral, voicing_name)


def choose_voicing_for_section_type(
    root_midi: int,
    numeral: str,
    section_type: str,
    intensity: float,
    prev_chord_shape: Optional[ChordShape] = None,
    register_min: Optional[int] = None,
    register_max: Optional[int] = None,
    rng: Optional[random.Random] = None,
) -> ChordShape:
    """Choose voicing style automatically based on section type and intensity.

    Args:
        root_midi: Root note MIDI number
        numeral: Roman numeral (e.g., "I", "iv")
        section_type: Section type (e.g., "verse", "chorus", "bridge")
        intensity: Intensity level (0.0-1.0)
        prev_chord_shape: Previous chord for voice leading
        register_min: Ignored (kept for API compat)
        register_max: Ignored (kept for API compat)
        rng: Random number generator

    Returns:
        ChordShape with appropriate voicing
    """
    section_type_lower = section_type.lower()

    if section_type_lower in ("intro", "outro", "breakdown"):
        voicing_style = "octaves" if intensity < 0.5 else "shell"
    elif section_type_lower == "verse":
        voicing_style = "power" if intensity > 0.6 else "triad"
    elif section_type_lower in ("chorus", "hook"):
        voicing_style = "power"
    elif section_type_lower in ("bridge", "prechorus", "pre_chorus"):
        voicing_style = "shell" if intensity < 0.7 else "triad"
    elif section_type_lower == "solo":
        voicing_style = "shell"
    else:
        voicing_style = "power"

    return choose_voicing(
        root_midi=root_midi,
        numeral=numeral,
        voicing_style=voicing_style,
        prev_chord_shape=prev_chord_shape,
        rng=rng,
    )
