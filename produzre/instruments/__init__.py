"""Shared instrument physics library for stringed instruments.

Provides tuning profiles and physics-based chord shape resolution for any
stringed instrument. Used by acoustic_gtr, rhythm_gtr, bass, and any future
custom string engine.

Quick imports:
    from produzre.instruments import InstrumentProfile, select_voicing
    from produzre.instruments.profile import GUITAR_STANDARD, BASS_4STRING
    from produzre.instruments.chord_shapes import ResolvedVoicing
"""

from .profile import InstrumentProfile
from .chord_shapes import select_voicing, resolve_pitches_to_voicing, ResolvedVoicing

__all__ = [
    "InstrumentProfile",
    "select_voicing",
    "resolve_pitches_to_voicing",
    "ResolvedVoicing",
]
