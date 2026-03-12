from __future__ import annotations

"""Harmony progression preset library.

This module defines a small built-in library of Roman-numeral progressions that
can be used when a section does not provide an explicit progression override.

Preset selection is driven by:
- `song_mode` (e.g., "dorian", "aeolian")
- `section_type` (e.g., "verse", "chorus", "bridge")

The presets are intentionally minimal to keep early behavior predictable.
Users can override progressions per section via `section.harmony.progression`.

Data structure:
- `PROGRESSION_PRESETS` maps `(mode, section_type)` -> list[str] of numerals.
- The special key ("*", "generic") is used as a fallback.
"""

# Very small initial preset library.
# Keys: (mode, section_type)
PROGRESSION_PRESETS: dict[tuple[str, str], list[str]] = {
    # Dorian examples
    ("dorian", "verse"): ["i", "bVII", "VI", "i"],
    ("dorian", "chorus"): ["i", "VI", "bVII", "i"],
    ("dorian", "bridge"): ["bIII", "IV", "i", "i"],

    # Aeolian examples
    ("aeolian", "verse"): ["i", "bVII", "VI", "bVII"],
    ("aeolian", "chorus"): ["i", "VI", "bVII", "i"],

    # Fallback generic "rock" loop
    ("*", "generic"): ["i", "bVII", "VI", "i"],
}


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
      2) Preset match for (`song_mode`, `section_type`)
      3) Generic fallback preset ("*", "generic")
      4) Hardcoded minimal fallback ["i", "bVII", "VI", "i"]

    Logging:
      - Emits an INFO message indicating which source was used.
      - Emits a WARNING only when no preset entries exist at all.

    Args:
        song_mode: Global song mode (e.g., "dorian", "aeolian").
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

    key = (song_mode, section_type)
    if key in PROGRESSION_PRESETS:
        degrees = PROGRESSION_PRESETS[key]
        logger.info(
            "Section '%s': using preset progression for mode=%s type=%s: %s",
            section_id,
            song_mode,
            section_type,
            " ".join(degrees),
        )
        return degrees

    if ("*", "generic") in PROGRESSION_PRESETS:
        degrees = PROGRESSION_PRESETS[("*", "generic")]
        logger.info(
            "Section '%s': using generic progression (no specific preset for mode=%s type=%s): %s",
            section_id,
            song_mode,
            section_type,
            " ".join(degrees),
        )
        return degrees

    degrees = ["i", "bVII", "VI", "i"]
    logger.warning(
        "Section '%s': no progression presets found; falling back to %s",
        section_id,
        " ".join(degrees),
    )
    return degrees
