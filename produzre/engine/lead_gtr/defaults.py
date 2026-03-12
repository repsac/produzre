"""Default parameters for lead guitar engine (Phase LG0).

Conservative defaults for lead guitar rendering focused on modest,
melodic lines with motif repetition and chord-tone bias.
"""

from __future__ import annotations

from typing import Dict, Any


# Engine metadata
ENGINE_DEFAULT_PRIORITY = 40  # After drums (10), bass (20), rhythm_gtr (30)
ENGINE_DEFAULT_CHANNEL = 2  # MIDI channel 2
ENGINE_DEFAULT_PROGRAM = 29  # GM: Overdriven Guitar

ENGINE_REQUIRES = ["harmony.plan", "rhythm.grid", "rhythm.accents"]
ENGINE_PROVIDES = ["lead_gtr.phrases"]
ENGINE_ROLES = ["lead"]


# Register ranges for lead guitar (MIDI note numbers)
REGISTER_RANGES: Dict[str, tuple[int, int]] = {
    "low": (52, 67),    # E3-G4 (lower melodic range)
    "mid": (60, 76),    # C4-E5 (comfortable melodic range)
    "high": (67, 84),   # G4-C6 (upper melodic range, still playable)
    "very_high": (72, 91),  # C5-G6 (extreme high, use sparingly)
    "full": (52, 88),   # E3-E6 (full shred range, ~3 octaves)
}

DEFAULT_REGISTER = "mid"


# Phrase density targets by section type (0.0-1.0)
# Lower density = more rests, more space
PHRASE_DENSITY_TARGETS: Dict[str, float] = {
    "intro": 0.3,        # Sparse, establishing
    "verse": 0.4,        # Moderate, supportive
    "prechorus": 0.5,    # Building
    "chorus": 0.6,       # Active, melodic hook
    "bridge": 0.5,       # Contrasting, interesting
    "solo": 0.8,         # Busiest, most active
    "breakdown": 0.2,    # Very sparse, dramatic
    "outro": 0.3,        # Winding down
}


# Motif repeat rate by section type (0.0-1.0)
# Higher repeat rate = more exact repetition of motifs
MOTIF_REPEAT_RATE: Dict[str, float] = {
    "intro": 0.7,        # Establish motif through repetition
    "verse": 0.6,        # Moderate repetition
    "prechorus": 0.5,    # More variation building up
    "chorus": 0.8,       # Strong repetition for memorability
    "bridge": 0.3,       # More varied, contrasting
    "solo": 0.4,         # More improvisational
    "breakdown": 0.5,    # Moderate
    "outro": 0.7,        # Return to familiar motifs
}


# Rest rate by section type (0.0-1.0)
# Probability of inserting rests between phrases
REST_RATE: Dict[str, float] = {
    "intro": 0.6,        # Spacious
    "verse": 0.5,        # Balanced
    "prechorus": 0.4,    # Less space, building energy
    "chorus": 0.3,       # Active, fewer rests
    "bridge": 0.4,       # Moderate
    "solo": 0.1,         # Continuous, flowing
    "breakdown": 0.7,    # Very spacious, dramatic pauses
    "outro": 0.6,        # Spacious ending
}


# Chord-tone bias (0.0-1.0)
# How strongly to prefer chord tones vs. passing tones
# 1.0 = only chord tones, 0.5 = balanced, 0.0 = chromatic
CHORD_TONE_BIAS: Dict[str, float] = {
    "intro": 0.8,        # Safe, consonant
    "verse": 0.7,        # Mostly consonant
    "prechorus": 0.6,    # Some tension
    "chorus": 0.8,       # Clear, memorable melody
    "bridge": 0.5,       # More chromatic interest
    "solo": 0.6,         # Balance between melody and interest
    "breakdown": 0.7,    # Clear, powerful
    "outro": 0.8,        # Resolve clearly
}


# Phrase length in bars by section type
PHRASE_LENGTH_BARS: Dict[str, float] = {
    "intro": 2.0,
    "verse": 2.0,
    "prechorus": 1.0,
    "chorus": 2.0,
    "bridge": 2.0,
    "solo": 4.0,
    "breakdown": 2.0,
    "outro": 2.0,
}


# Neutral defaults (when section type not found)
NEUTRAL_DEFAULTS: Dict[str, Any] = {
    "register": "mid",
    "density": 0.5,
    "motif_repeat_rate": 0.5,
    "rest_rate": 0.5,
    "chord_tone_bias": 0.7,
    "phrase_length_bars": 2.0,
    "velocity_base": 85,
    "velocity_variation": 15,
}


def get_section_defaults(section_type: str) -> Dict[str, Any]:
    """Get default parameters for a section type.

    Args:
        section_type: Section type (verse, chorus, etc.)

    Returns:
        dict: Default parameters for the section
    """
    section_type_lower = section_type.lower()

    return {
        "register": DEFAULT_REGISTER,
        "density": PHRASE_DENSITY_TARGETS.get(section_type_lower, 0.5),
        "motif_repeat_rate": MOTIF_REPEAT_RATE.get(section_type_lower, 0.5),
        "rest_rate": REST_RATE.get(section_type_lower, 0.5),
        "chord_tone_bias": CHORD_TONE_BIAS.get(section_type_lower, 0.7),
        "phrase_length_bars": PHRASE_LENGTH_BARS.get(section_type_lower, 2.0),
        "velocity_base": 85,
        "velocity_variation": 15,
    }
