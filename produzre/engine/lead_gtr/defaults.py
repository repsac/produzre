"""Default parameters for lead guitar engine (Phase LG0).

Engine metadata only. Register presets live in ``register.py`` (the single
source of truth — a duplicate ``REGISTER_RANGES`` table previously lived here).

Note: earlier versions of this module also defined section-type tables
(``PHRASE_DENSITY_TARGETS``, ``MOTIF_REPEAT_RATE``, ``REST_RATE``,
``CHORD_TONE_BIAS``, ``PHRASE_LENGTH_BARS``, ``NEUTRAL_DEFAULTS``) and a
``get_section_defaults()`` helper. They had zero callers — the renderer in
``__init__.py`` derives density/rests/phrase length itself — so they were
removed rather than left as misleading dead configuration.
"""

from __future__ import annotations

from .register import DEFAULT_REGISTER, REGISTER_PRESETS

# Engine metadata
ENGINE_DEFAULT_PRIORITY = 40  # After drums (10), bass (20), rhythm_gtr (30)
ENGINE_DEFAULT_CHANNEL = 2  # MIDI channel 2
ENGINE_DEFAULT_PROGRAM = 29  # GM: Overdriven Guitar

ENGINE_REQUIRES = ["harmony.plan", "rhythm.grid", "rhythm.accents"]
ENGINE_PROVIDES = ["lead_gtr.phrases"]
ENGINE_ROLES = ["lead"]

# Backwards-compatible alias: register presets come from register.py.
REGISTER_RANGES = REGISTER_PRESETS

__all__ = [
    "ENGINE_DEFAULT_PRIORITY",
    "ENGINE_DEFAULT_CHANNEL",
    "ENGINE_DEFAULT_PROGRAM",
    "ENGINE_REQUIRES",
    "ENGINE_PROVIDES",
    "ENGINE_ROLES",
    "DEFAULT_REGISTER",
    "REGISTER_RANGES",
]
