"""Default configuration for acoustic guitar engine.

Steel-string acoustic guitar: fingerpicking, strumming, hybrid, percussive.
All values are overridable via section config or instrument extra params.
"""

from typing import Dict

# =============================================================================
# Engine metadata
# =============================================================================

ENGINE_DEFAULT_PRIORITY = 4    # After rhythm_gtr (3), alongside lead_gtr (4)
ENGINE_DEFAULT_CHANNEL   = 4   # Channel 4 (rhythm_gtr=2, lead_gtr=3 are taken)
ENGINE_DEFAULT_PROGRAM   = 25  # GM 0-indexed: Acoustic Steel Guitar

ENGINE_REQUIRES = ["harmony.plan", "rhythm.grid", "rhythm.accents"]
ENGINE_PROVIDES = ["acoustic_gtr.texture"]
ENGINE_ROLES    = ["rhythm", "texture"]


# =============================================================================
# Technique auto-selection by section type
# =============================================================================

TECHNIQUE_DEFAULTS: Dict[str, str] = {
    "intro":      "fingerpicking",
    "verse":      "fingerpicking",
    "prechorus":  "hybrid",
    "pre_chorus": "hybrid",
    "chorus":     "strumming",
    "hook":       "strumming",
    "refrain":    "strumming",
    "bridge":     "fingerpicking",
    "breakdown":  "percussive",
    "solo":       "strumming",   # sparse support chords under lead
    "interlude":  "fingerpicking",
    "outro":      "fingerpicking",
}
TECHNIQUE_DEFAULT_FALLBACK = "hybrid"

# Valid technique names
VALID_TECHNIQUES = frozenset(("fingerpicking", "strumming", "hybrid", "percussive"))


# =============================================================================
# Strumming density by section type (fraction of quarter-note grid to hit)
# =============================================================================

STRUM_DENSITY: Dict[str, float] = {
    "intro":      0.35,
    "verse":      0.50,
    "prechorus":  0.65,
    "pre_chorus": 0.65,
    "chorus":     0.80,
    "hook":       0.80,
    "refrain":    0.75,
    "bridge":     0.55,
    "breakdown":  0.20,
    "solo":       0.45,
    "interlude":  0.40,
    "outro":      0.35,
}
STRUM_DENSITY_DEFAULT = 0.50


# =============================================================================
# Fingerpicking pattern preference by section type
# =============================================================================

PICKING_PATTERN_DEFAULTS: Dict[str, str] = {
    "intro":      "broken_chord",
    "verse":      "travis",
    "prechorus":  "roll",
    "pre_chorus": "roll",
    "bridge":     "pima",
    "solo":       "broken_chord",
    "interlude":  "broken_chord",
    "outro":      "broken_chord",
}
PICKING_PATTERN_DEFAULT_FALLBACK = "travis"


# =============================================================================
# Velocity base by section type
# =============================================================================

VELOCITY_BASE: Dict[str, int] = {
    "intro":      55,
    "verse":      62,
    "prechorus":  68,
    "pre_chorus": 68,
    "chorus":     78,
    "hook":       78,
    "refrain":    75,
    "bridge":     65,
    "breakdown":  48,
    "solo":       60,
    "interlude":  58,
    "outro":      52,
}
VELOCITY_BASE_DEFAULT = 65

# Velocity scaling from intensity (0-1 → multiplier)
VELOCITY_INTENSITY_RANGE = 20   # additional vel at intensity=1.0


# =============================================================================
# Humanization defaults
# =============================================================================

VEL_VARIATION_DEFAULT   = 8    # ±velocity units per hit
TIMING_VARIATION_DEFAULT = 0.018  # ±beats timing jitter (~10ms at 90BPM)


# =============================================================================
# Body tap parameters (percussive technique)
# =============================================================================

BODY_TAP_PITCH    = 40    # E2 — dead note for body percussion
BODY_TAP_VEL_LO   = 45
BODY_TAP_VEL_HI   = 65
BODY_TAP_DURATION = 0.07  # beats — very short, percussive
