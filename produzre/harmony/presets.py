from __future__ import annotations

"""Harmony progression preset library.

This module defines a small built-in library of Roman-numeral progressions that
can be used when a section does not provide an explicit progression override.

Preset selection is driven by:
- `song_mode` (e.g., "ionian", "dorian", "aeolian")
- `section_type` (e.g., "verse", "chorus", "bridge")

Both parts of the key are case-insensitive and whitespace-tolerant. Common
mode aliases are accepted ("major" -> ionian, "minor" -> aeolian). Unknown
modes fall back mode-aware: major-ish modes use the ionian presets, minor-ish
modes use the aeolian presets.

The presets are intentionally minimal to keep early behavior predictable.
Users can override progressions per section via `section.harmony.progression`.

Data structure:
- `PROGRESSION_PRESETS` maps `(mode, section_type)` -> list[str] of numerals.
- The special keys ("*", "generic") and ("*_major", "generic") are fallbacks.
"""

# Small preset library.
# Keys: (mode, section_type) — both lowercase.
PROGRESSION_PRESETS: dict[tuple[str, str], list[str]] = {
    # Ionian (major) examples
    ("ionian", "verse"): ["I", "V", "vi", "IV"],
    ("ionian", "chorus"): ["I", "IV", "V", "I"],
    ("ionian", "bridge"): ["vi", "IV", "I", "V"],

    # Dorian examples
    ("dorian", "verse"): ["i", "bVII", "VI", "i"],
    ("dorian", "chorus"): ["i", "VI", "bVII", "i"],
    ("dorian", "bridge"): ["bIII", "IV", "i", "i"],

    # Aeolian examples
    ("aeolian", "verse"): ["i", "bVII", "VI", "bVII"],
    ("aeolian", "chorus"): ["i", "VI", "bVII", "i"],

    # Fallback generic "rock" loop (minor)
    ("*", "generic"): ["i", "bVII", "VI", "i"],
    # Fallback generic major loop
    ("*_major", "generic"): ["I", "V", "vi", "IV"],
}

# Direct mode aliases (normalized form -> canonical preset mode).
_MODE_ALIASES: dict[str, str] = {
    "major": "ionian",
    "maj": "ionian",
    "minor": "aeolian",
    "min": "aeolian",
    "natural_minor": "aeolian",
}

# Mode classification used for the mode-aware fallback when a mode has no
# presets of its own. Major-ish modes have a major third above the tonic.
_MAJOR_ISH_MODES = {"ionian", "lydian", "mixolydian", "major", "maj"}
_MINOR_ISH_MODES = {
    "aeolian", "dorian", "phrygian", "locrian",
    "minor", "min", "natural_minor", "harmonic_minor", "melodic_minor",
}


def _normalize_mode(song_mode: str | None) -> str:
    """Normalize a mode string: lowercase, stripped, aliases resolved."""
    mode = str(song_mode or "").strip().lower()
    return _MODE_ALIASES.get(mode, mode)


def _is_major_ish(mode: str) -> bool:
    """Return True when `mode` (normalized) is major-flavored."""
    if mode in _MAJOR_ISH_MODES:
        return True
    if mode in _MINOR_ISH_MODES:
        return False
    # Unknown mode: default to minor-ish (legacy behavior leaned minor).
    return False


def choose_progression_for_section(
    *,
    song_mode: str,
    section_type: str,
    section_id: str,
    explicit: str | None,
    logger,
) -> list[str]:
    """Choose the Roman-numeral progression for a section.

    This function returns a list of Roman numeral strings that describe the
    section's harmonic loop. It supports explicit per-section overrides and a
    small built-in preset library.

    Priority order:
      1) Explicit override (`explicit`) if provided (space-separated numerals)
      2) Preset match for normalized (`song_mode`, `section_type`)
         ("major" maps to ionian, "minor" to aeolian; case-insensitive)
      3) Mode-aware fallback: major-ish modes use the ionian presets,
         minor-ish/unknown modes use the aeolian presets
      4) Generic fallback preset (major or minor flavored)
      5) Hardcoded minimal fallback

    Args:
        song_mode: Global song mode (e.g., "ionian", "dorian", "aeolian").
        section_type: Section type (e.g., "verse", "chorus").
        section_id: Section identifier used in logs.
        explicit: Optional explicit progression override string. When present,
            it is split on whitespace to produce numeral tokens.
        logger: Logger used for informational/warning messages.

    Returns:
        list[str]: Ordered list of Roman numeral tokens.
    """
    if explicit:
        degrees = explicit.split()
        logger.info(
            "Section '%s': using explicit progression override: %s",
            section_id,
            " ".join(degrees),
        )
        return degrees

    mode = _normalize_mode(song_mode)
    stype = str(section_type or "").strip().lower()

    key = (mode, stype)
    if key in PROGRESSION_PRESETS:
        degrees = PROGRESSION_PRESETS[key]
        logger.info(
            "Section '%s': using preset progression for mode=%s type=%s: %s",
            section_id,
            mode,
            stype,
            " ".join(degrees),
        )
        return degrees

    # Mode-aware fallback: unknown/uncovered modes borrow from the closest
    # canonical mode family instead of always defaulting to minor.
    fallback_mode = "ionian" if _is_major_ish(mode) else "aeolian"
    fallback_key = (fallback_mode, stype)
    if fallback_key in PROGRESSION_PRESETS:
        degrees = PROGRESSION_PRESETS[fallback_key]
        logger.info(
            "Section '%s': no preset for mode=%s; using %s preset for type=%s: %s",
            section_id,
            mode,
            fallback_mode,
            stype,
            " ".join(degrees),
        )
        return degrees

    generic_key = ("*_major", "generic") if _is_major_ish(mode) else ("*", "generic")
    if generic_key in PROGRESSION_PRESETS:
        degrees = PROGRESSION_PRESETS[generic_key]
        logger.info(
            "Section '%s': using generic progression (no specific preset for mode=%s type=%s): %s",
            section_id,
            mode,
            stype,
            " ".join(degrees),
        )
        return degrees

    degrees = ["I", "V", "vi", "IV"] if _is_major_ish(mode) else ["i", "bVII", "VI", "i"]
    logger.warning(
        "Section '%s': no progression presets found; falling back to %s",
        section_id,
        " ".join(degrees),
    )
    return degrees
