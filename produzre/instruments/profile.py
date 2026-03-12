"""Instrument profile definitions for stringed instruments.

An InstrumentProfile captures the physical properties of a stringed instrument:
open string tuning, fret count, max comfortable finger span, and whether the
instrument can play barre chords (movable shapes across multiple strings).

Adding a new instrument requires only adding a new profile constant — no engine
code changes are needed. The chord_shapes library uses the profile to validate
and generate physically playable voicings.

Standard profiles provided:
    GUITAR_STANDARD  — 6-string, E standard (E2-A2-D3-G3-B3-E4)
    GUITAR_7STRING   — 7-string, B standard (B1-E2-A2-D3-G3-B3-E4)
    GUITAR_DADGAD    — 6-string, DADGAD alternate tuning
    GUITAR_12STRING  — 12-string (same open tuning as standard; courses handled as unison)
    BASS_4STRING     — 4-string bass (E1-A1-D2-G2)
    BASS_5STRING     — 5-string bass (B0-E1-A1-D2-G2)
    UKULELE          — 4-string ukulele (G4-C4-E4-A4, reentrant)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class InstrumentProfile:
    """Physical description of a stringed instrument.

    Attributes:
        name:          Human-readable identifier (used for debugging/logging).
        open_tuning:   MIDI pitches of each open string, lowest string first.
                       E.g. standard guitar = (40, 45, 50, 55, 59, 64).
        num_frets:     Number of frets on the instrument.
        max_fret_span: Maximum comfortable finger span in frets (typically 4 for
                       guitar in open position, 3 in higher positions).
        barre_capable: Whether movable barre chord shapes are applicable.
                       Bass instruments typically set this to False.
    """
    name: str
    open_tuning: Tuple[int, ...]
    num_frets: int = 22
    max_fret_span: int = 4
    barre_capable: bool = True

    @property
    def num_strings(self) -> int:
        return len(self.open_tuning)


# ---------------------------------------------------------------------------
# Standard instrument profiles
# ---------------------------------------------------------------------------

# 6-string guitar, standard E tuning: E2-A2-D3-G3-B3-E4
GUITAR_STANDARD = InstrumentProfile(
    name="guitar_standard",
    open_tuning=(40, 45, 50, 55, 59, 64),
)

# 7-string guitar, B standard: B1-E2-A2-D3-G3-B3-E4
GUITAR_7STRING = InstrumentProfile(
    name="guitar_7string",
    open_tuning=(35, 40, 45, 50, 55, 59, 64),
)

# 6-string DADGAD alternate tuning: D2-A2-D3-G3-A3-D4
GUITAR_DADGAD = InstrumentProfile(
    name="guitar_dadgad",
    open_tuning=(38, 45, 50, 55, 57, 62),
)

# 12-string guitar (modeled as 6-course; chorus/unison doubling handled by mixer)
GUITAR_12STRING = InstrumentProfile(
    name="guitar_12string",
    open_tuning=(40, 45, 50, 55, 59, 64),
)

# 4-string bass: E1-A1-D2-G2
BASS_4STRING = InstrumentProfile(
    name="bass_4string",
    open_tuning=(28, 33, 38, 43),
    barre_capable=False,
)

# 5-string bass: B0-E1-A1-D2-G2
BASS_5STRING = InstrumentProfile(
    name="bass_5string",
    open_tuning=(23, 28, 33, 38, 43),
    barre_capable=False,
)

# 4-string ukulele, reentrant G tuning: G4-C4-E4-A4
UKULELE = InstrumentProfile(
    name="ukulele",
    open_tuning=(67, 60, 64, 69),
    num_frets=15,
    max_fret_span=3,
    barre_capable=True,
)
