"""Default configuration values for rhythm guitar engine (Phase RG0).

This module defines default parameters that control the rhythm guitar engine's
behavior. These can be overridden via section-level configuration or extra
parameters in the song YAML.
"""

from typing import Dict

# =============================================================================
# Strum Timing
# =============================================================================

# Default strum spread in milliseconds (time between notes in a chord)
# 0 = block chord (all notes together)
# Typical values: 10-30ms for natural strumming
STRUM_SPREAD_MS_DEFAULT = 15.0
STRUM_SPREAD_MS_MIN = 0.0
STRUM_SPREAD_MS_MAX = 50.0

# Strum spread multipliers by direction
STRUM_SPREAD_DOWN = 1.0  # Normal speed for downstrokes
STRUM_SPREAD_UP = 1.2    # Slightly slower for upstrokes

# Humanization ranges (applied with RNG)
STRUM_TIMING_JITTER_MS = 5.0  # +/- milliseconds
STRUM_SPREAD_VARIATION = 0.15  # +/- 15% variation in spread


# =============================================================================
# Palm Mute Configuration
# =============================================================================

# Palm mute bias by section type (0.0 = never, 1.0 = always)
# These control how often palm muting is applied in different sections
PALM_MUTE_BIAS: Dict[str, float] = {
    "intro": 0.3,      # Light palm muting in intros
    "verse": 0.6,      # Heavy palm muting in verses for space
    "pre_chorus": 0.4, # Moderate in pre-chorus
    "prechorus": 0.4,
    "chorus": 0.2,     # Minimal palm muting in chorus (open up)
    "bridge": 0.5,     # Moderate in bridge
    "solo": 0.3,       # Light during solos (let lead shine)
    "breakdown": 0.7,  # Heavy palm muting in breakdown
    "interlude": 0.4,  # Moderate
    "outro": 0.5,      # Moderate in outro
}

# Default palm mute bias if section type not in map
PALM_MUTE_BIAS_DEFAULT = 0.4

# Velocity reduction for palm muted notes (multiplier)
PALM_MUTE_VELOCITY_FACTOR = 0.75


# =============================================================================
# Density Targets by Section Type
# =============================================================================

# Target density (0.0-1.0) controls how many strums per bar
# Higher density = more frequent strumming
# These are base values that get modulated by intensity
DENSITY_TARGET: Dict[str, float] = {
    "intro": 0.4,      # Sparse in intro
    "verse": 0.5,      # Moderate density in verses
    "pre_chorus": 0.7, # Build density in pre-chorus
    "prechorus": 0.7,
    "chorus": 0.8,     # High density in chorus (driving)
    "bridge": 0.6,     # Moderate in bridge
    "solo": 0.5,       # Moderate during solos (support, not compete)
    "breakdown": 0.3,  # Very sparse in breakdown
    "interlude": 0.5,  # Moderate
    "outro": 0.4,      # Sparse in outro (winding down)
}

# Default density if section type not in map
DENSITY_TARGET_DEFAULT = 0.5

# Density modulation by intensity
# Final density = base_density * (1.0 + INTENSITY_DENSITY_BOOST * intensity)
INTENSITY_DENSITY_BOOST = 0.4  # Up to 40% increase at max intensity


# =============================================================================
# Velocity Configuration
# =============================================================================

# Base velocity ranges by section type
VELOCITY_BASE: Dict[str, int] = {
    "intro": 60,
    "verse": 70,
    "pre_chorus": 75,
    "prechorus": 75,
    "chorus": 85,
    "bridge": 75,
    "solo": 70,
    "breakdown": 55,
    "interlude": 65,
    "outro": 60,
}

# Default velocity if section type not in map
VELOCITY_BASE_DEFAULT = 70

# Velocity range modulation by intensity
# velocity = base + (intensity * VELOCITY_INTENSITY_RANGE)
VELOCITY_INTENSITY_RANGE = 25

# Accent velocity boost
VELOCITY_ACCENT_BOOST = 15


# =============================================================================
# Pattern Configuration
# =============================================================================

# Subdivision for rhythm patterns (steps per beat)
PATTERN_SUBDIVISION = 4  # 16th notes

# Minimum time between chord changes (beats)
# Prevents overly rapid chord switching
MIN_CHORD_DURATION = 0.5

# Default note duration as fraction of inter-onset interval
# E.g., 0.9 = 90% of the time until next strum
NOTE_DURATION_FACTOR = 0.85


# =============================================================================
# Engine Metadata
# =============================================================================

# These are used if not specified in engines.yml
ENGINE_DEFAULT_PRIORITY = 3
ENGINE_DEFAULT_CHANNEL = 2
ENGINE_DEFAULT_PROGRAM = 29  # GM Overdriven Guitar
ENGINE_DEFAULT_ENABLED = True

# Plan keys this engine requires
ENGINE_REQUIRES = ["harmony.plan", "rhythm.grid", "rhythm.accents"]

# Plan keys this engine provides
ENGINE_PROVIDES = ["rhythm.texture", "rhythm.chords"]

# Musical roles
ENGINE_ROLES = ["rhythm", "pad"]
