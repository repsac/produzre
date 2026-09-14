# produzre/engine/bass/harmony.py
"""Harmony resolution for bass engine (key, mode, chord tones)."""

from ...harmony.spelling import root_offset, chord_intervals
import re
from typing import Optional, Dict


# Very simple key → MIDI root mapping for now (bass register)
KEY_TO_MIDI_ROOT: Dict[str, int] = {
    "C": 36,   # C2
    "C#": 37,
    "Db": 37,
    "D": 38,
    "D#": 39,
    "Eb": 39,
    "E": 40,
    "F": 41,
    "F#": 42,
    "Gb": 42,
    "G": 43,
    "G#": 44,
    "Ab": 44,
    "A": 45,
    "A#": 46,
    "Bb": 46,
    "B": 47,
}


# Mode-aware scale degree offsets for major/minor/modal harmony
MODE_SCALE_OFFSETS: Dict[str, list[int]] = {
    # Ionian / major and relatives
    "ionian":      [0, 2, 4, 5, 7, 9, 11],
    "major":       [0, 2, 4, 5, 7, 9, 11],
    "dorian":      [0, 2, 3, 5, 7, 9, 10],
    "phrygian":    [0, 1, 3, 5, 7, 8, 10],
    "lydian":      [0, 2, 4, 6, 7, 9, 11],
    "mixolydian":  [0, 2, 4, 5, 7, 9, 10],
    "aeolian":     [0, 2, 3, 5, 7, 8, 10],  # natural minor
    "minor":       [0, 2, 3, 5, 7, 8, 10],
    "locrian":     [0, 1, 3, 5, 6, 8, 10],
}


ROMAN_TO_DEGREE = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
}


# Major-scale degree offsets. Borrowed-chord accidentals (bVII, bVI, bIII, ...)
# are universally spelled relative to the MAJOR scale, regardless of the
# current mode (in C aeolian, bVII is Bb, not "A flattened from aeolian").
MAJOR_SCALE_OFFSETS: list[int] = [0, 2, 4, 5, 7, 9, 11]


# Leading roman-numeral portion of a chord symbol (quality suffixes like
# "7", "maj7", "sus4", "°", "dim" follow it and must not affect the lookup).
_ROMAN_PORTION_RE = re.compile(r"([ivIV]+)")


def get_mode_scale_offsets(mode: Optional[str]) -> list[int]:
    """Return semitone offsets for the 7 scale degrees of the given mode.

    Falls back to ionian (major) if the mode is unknown or not provided.
    """
    m = (mode or "ionian").lower()
    return MODE_SCALE_OFFSETS.get(m, MODE_SCALE_OFFSETS["ionian"])


def parse_roman_numeral(numeral: str) -> tuple[int, int]:
    """Parse a Roman numeral with optional accidentals into (degree_index, accidental).

    degree_index is 0-based (0..6) and accidental is a semitone offset (-2..+2 typically).
    Quality suffixes ("V7", "ii°", "IVsus4", "Imaj7", "i7") are tolerated:
    only the leading roman portion determines the degree.
    Examples:
    - "i"   -> (0, 0)
    - "bVII"-> (6, -1)
    - "#iv" -> (3, +1)
    - "V7"  -> (4, 0)
    """
    s = (numeral or "").strip()
    if not s:
        return 0, 0

    accidental = 0
    # Consume leading accidentals like 'b', 'bb', '#', '##'
    while s and s[0] in ("b", "#"):
        if s[0] == "b":
            accidental -= 1
        elif s[0] == "#":
            accidental += 1
        s = s[1:]

    if not s:
        return 0, accidental

    # Extract only the leading roman portion so quality suffixes
    # ("7", "maj7", "sus4", "°", "dim") don't break the degree lookup.
    m = _ROMAN_PORTION_RE.match(s)
    if not m:
        return 0, accidental

    degree = ROMAN_TO_DEGREE.get(m.group(1).upper(), 1)
    # Clamp to 1..7, convert to 0-based index
    degree_index = max(1, min(degree, 7)) - 1
    return degree_index, accidental


def bass_root_for_numeral(
    cfg,
    section,
    numeral: str,
    bass_cfg,
) -> int:
    """Compute a bass root MIDI note for a given chord numeral.

    This uses:
    - song key (cfg.song.key or section.key) as the tonic,
    - song mode (cfg.song.mode) to choose the scale,
    - the Roman numeral (with accidentals) to pick the scale degree,
    - the bass register (low/mid) from the bass instrument config.
    """
    # Base tonic in a bass-friendly register
    key = (section.key or cfg.song.key or "C").strip()
    key = key.replace("♭", "b").replace("♯", "#")
    tonic_midi = KEY_TO_MIDI_ROOT.get(key, 36)  # default C2

    semitone = root_offset(numeral, getattr(section, "mode", None) or cfg.song.mode)

    pitch = tonic_midi + semitone

    # Apply simple register handling: low (default) vs mid
    register = getattr(bass_cfg, "register", None) if bass_cfg is not None else None
    if register == "mid":
        pitch += 12

    return pitch


def resolve_bass_root_midi(cfg, section) -> int:
    """Resolve a simple tonic MIDI note for the section's key.

    This is intentionally basic for now; later the full harmony engine will
    determine degree-based pitches from Roman numerals and mode.
    """
    key = (section.key or cfg.song.key or "C").strip()
    key = key.replace("♭", "b").replace("♯", "#")  # normalize symbols
    return KEY_TO_MIDI_ROOT.get(key, 36)  # default C2


def get_chord_tones(
    root_midi: int,
    numeral: str,
    mode_offsets: list[int],
) -> Dict[str, int]:
    """Get chord tones (root, 3rd, 5th, 7th) for a given chord.

    Args:
        root_midi: MIDI note number for the chord root
        numeral: Roman numeral (e.g., "i", "IV", "V7")
        mode_offsets: Scale degree offsets for the current mode

    Returns:
        Dict with keys: root, third, fifth (MIDI note numbers).
        "seventh" is only present when the numeral carries a seventh.
    """
    return dict(zip(("root", "third", "fifth", "seventh"),
                    (root_midi + interval for interval in chord_intervals(numeral))))
