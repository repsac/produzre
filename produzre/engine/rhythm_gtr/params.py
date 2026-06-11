"""Parameter resolution for rhythm guitar (Phase RG3).

This module handles parameter resolution and section-type-aware defaults for
the rhythm guitar engine. It provides a clean interface for merging:
- Engine-level defaults
- Section-type defaults (verse vs chorus vs bridge)
- User-specified overrides

The `section_contrast` knob controls how strongly section types differ from
each other. Higher values make choruses brighter/denser and verses darker/sparser.
"""

from __future__ import annotations

from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass


@dataclass
class RhythmGuitarParams:
    """Resolved parameters for rhythm guitar rendering.

    All parameters are resolved from defaults + section type + user overrides.
    """
    # Pattern generation
    style: str = "auto"  # "chug", "strum", "syncopated", "half_time", "auto"
    strum_style: str = "balanced"  # "balanced", "downbeat_heavy", "upbeat_heavy"
    density: float = 0.6  # 0.0-1.0
    palm_mute: float = 0.06  # 0.0-1.0 (MIDI analysis: avg=0.06 across 116 genres)

    # Voicing selection
    voicing: str = "auto"  # "power", "triad", "shell", "octaves", "auto"
    register: str = "mid"  # "low", "mid", "high"
    register_min: Optional[int] = None  # Explicit MIDI range (overrides register)
    register_max: Optional[int] = None

    # Expression
    accent_strength: float = 0.5  # 0.0-1.0
    strum_ms: float = 15.0  # Strum spread in milliseconds

    # Groove/timing
    swing: float = 0.0  # 0.0-1.0 (swing feel)
    push_pull: float = 0.0  # Timing offset in beats (±0.05 typical)
    groove: str = "tight"  # "tight", "laid_back", "pushed", "loose"

    # Humanization (Phase RG4)
    chuck_rate: float = 0.0  # 0.0-1.0 (dead note probability)
    humanize_velocity: float = 0.1  # 0.0-1.0 (velocity variation)
    humanize_timing: float = 0.05  # 0.0-1.0 (timing variation)
    downbeat_boost: float = 0.2  # 0.0-1.0 (downbeat emphasis)
    sustain_cut_rate: float = 0.0  # 0.0-1.0 (probability of staccato stab instead of ring)

    # Meta parameters
    section_contrast: float = 0.7  # 0.0-1.0 (how much sections differ)
    use_patterns: bool = False  # Enable Phase RG2 pattern-based rendering


# Default parameter values by section type
SECTION_TYPE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "intro": {
        "style": "auto",
        "density": 0.4,
        "palm_mute": 0.3,
        "voicing": "shell",  # Sparse, jazzy
        "register": "mid",
        "accent_strength": 0.4,
        "strum_ms": 20.0,  # Slower, more deliberate
        "swing": 0.0,
        "push_pull": 0.0,
        "groove": "tight",
        "chuck_rate": 0.0,
        "humanize_velocity": 0.08,
        "humanize_timing": 0.03,
        "downbeat_boost": 0.15,
    },
    "verse": {
        "style": "auto",  # Will choose straight_8s or syncopated
        "density": 0.5,
        "palm_mute": 0.6,  # More palm muting in verses
        "voicing": "auto",  # Will choose triad or power
        "register": "mid",
        "accent_strength": 0.5,
        "strum_ms": 15.0,
        "swing": 0.0,
        "push_pull": 0.0,
        "groove": "tight",
        "chuck_rate": 0.05,  # Occasional chucks in verse
        "humanize_velocity": 0.1,
        "humanize_timing": 0.05,
        "downbeat_boost": 0.2,
    },
    "prechorus": {
        "style": "auto",
        "density": 0.65,
        "palm_mute": 0.4,
        "voicing": "auto",
        "register": "mid",
        "accent_strength": 0.6,
        "strum_ms": 12.0,
        "swing": 0.0,
        "push_pull": 0.0,
        "groove": "tight",
        "chuck_rate": 0.0,
        "humanize_velocity": 0.1,
        "humanize_timing": 0.05,
        "downbeat_boost": 0.25,
    },
    "chorus": {
        "style": "auto",  # Will choose chugs or power chords
        "density": 0.8,
        "palm_mute": 0.2,  # Less palm muting, more ring
        "voicing": "power",  # Aggressive, driving
        "register": "high",  # Brighter
        "accent_strength": 0.7,
        "strum_ms": 10.0,  # Tighter, more aggressive
        "swing": 0.0,
        "push_pull": 0.0,
        "groove": "tight",
        "chuck_rate": 0.0,  # No chucks in chorus (full chords)
        "humanize_velocity": 0.12,  # Slightly more variation
        "humanize_timing": 0.04,  # Tighter timing
        "downbeat_boost": 0.3,  # Strong downbeats
    },
    "bridge": {
        "style": "syncopated",
        "density": 0.6,
        "palm_mute": 0.06,
        "voicing": "auto",  # Will choose shell or triad
        "register": "mid",
        "accent_strength": 0.5,
        "strum_ms": 15.0,
        "swing": 0.0,
        "push_pull": 0.0,
        "groove": "tight",
        "chuck_rate": 0.1,  # More chucks for texture
        "humanize_velocity": 0.1,
        "humanize_timing": 0.06,
        "downbeat_boost": 0.2,
    },
    "solo": {
        "style": "auto",
        "density": 0.7,
        "palm_mute": 0.3,
        "voicing": "shell",  # Leave space for lead
        "register": "mid",
        "accent_strength": 0.6,
        "strum_ms": 15.0,
        "swing": 0.0,
        "push_pull": 0.0,
        "groove": "tight",
        "chuck_rate": 0.0,
        "humanize_velocity": 0.09,
        "humanize_timing": 0.05,
        "downbeat_boost": 0.15,
    },
    "breakdown": {
        "style": "half_time",
        "density": 0.3,
        "palm_mute": 0.7,
        "voicing": "power",
        "register": "low",  # Heavy, dark
        "accent_strength": 0.8,  # Strong accents on sparse hits
        "strum_ms": 5.0,  # Tight, punchy
        "swing": 0.0,
        "push_pull": 0.0,
        "groove": "tight",
        "chuck_rate": 0.15,  # Lots of percussive chucks
        "humanize_velocity": 0.08,
        "humanize_timing": 0.03,
        "downbeat_boost": 0.4,  # Very strong downbeats
        "sustain_cut_rate": 0.3,  # Punchy stabs suit breakdown sparseness
    },
    "outro": {
        "style": "auto",
        "density": 0.3,
        "palm_mute": 0.4,
        "voicing": "shell",
        "register": "mid",
        "accent_strength": 0.4,
        "strum_ms": 20.0,
        "swing": 0.0,
        "push_pull": 0.0,
        "groove": "tight",
        "chuck_rate": 0.0,
        "humanize_velocity": 0.07,
        "humanize_timing": 0.04,
        "downbeat_boost": 0.15,
    },
}

# Neutral defaults (used when section type not found)
NEUTRAL_DEFAULTS: Dict[str, Any] = {
    "style": "auto",
    "strum_style": "balanced",
    "density": 0.6,
    "palm_mute": 0.06,
    "voicing": "auto",
    "register": "mid",
    "accent_strength": 0.5,
    "strum_ms": 15.0,
    "swing": 0.0,
    "push_pull": 0.0,
    "groove": "tight",
    "chuck_rate": 0.0,
    "humanize_velocity": 0.1,
    "humanize_timing": 0.05,
    "downbeat_boost": 0.2,
    "sustain_cut_rate": 0.0,
    "section_contrast": 0.7,
    "use_patterns": False,
}


def resolve_params(
    section_type: str,
    intensity: float = 0.7,
    extra: Optional[Dict[str, Any]] = None,
    section_contrast: Optional[float] = None,
) -> RhythmGuitarParams:
    """Resolve effective parameters for rhythm guitar in a section.

    Resolution order:
    1. Start with neutral defaults
    2. Apply section-type defaults (blended by section_contrast)
    3. Apply user overrides from extra dict

    Args:
        section_type: Section type (verse, chorus, bridge, etc.)
        intensity: Section intensity (0.0-1.0+), affects density
        extra: User parameter overrides from YAML
        section_contrast: Override for section contrast (0.0-1.0)

    Returns:
        RhythmGuitarParams: Fully resolved parameters
    """
    if extra is None:
        extra = {}

    # Get base defaults
    base = NEUTRAL_DEFAULTS.copy()

    # Get section-type-specific defaults
    section_defaults = SECTION_TYPE_DEFAULTS.get(
        section_type.lower(),
        NEUTRAL_DEFAULTS
    )

    # Resolve section_contrast (user override or default)
    contrast = section_contrast
    if contrast is None:
        contrast = extra.get("section_contrast", NEUTRAL_DEFAULTS["section_contrast"])
    contrast = max(0.0, min(1.0, float(contrast)))

    # Blend base with section defaults based on contrast
    blended = {}
    for key, base_val in base.items():
        section_val = section_defaults.get(key, base_val)

        # Blend numeric values
        if isinstance(base_val, (int, float)) and isinstance(section_val, (int, float)):
            blended[key] = _lerp(base_val, section_val, contrast)
        else:
            # For non-numeric, use section default if contrast > 0.5, else base
            blended[key] = section_val if contrast > 0.5 else base_val

    # Apply user overrides
    for key in blended.keys():
        if key in extra:
            blended[key] = extra[key]

    # Apply intensity scaling to density
    density_base = blended.get("density", 0.6)
    intensity_clamped = max(0.0, min(2.0, intensity))
    # Scale density: intensity 1.0 = no change, <1.0 reduces, >1.0 increases
    blended["density"] = density_base * intensity_clamped

    # Clamp all numeric values to valid ranges
    blended["density"] = max(0.0, min(1.0, blended["density"]))
    blended["palm_mute"] = max(0.0, min(1.0, blended.get("palm_mute", 0.5)))
    blended["accent_strength"] = max(0.0, min(1.0, blended.get("accent_strength", 0.5)))
    blended["strum_ms"] = max(0.0, min(100.0, blended.get("strum_ms", 15.0)))
    blended["swing"] = max(0.0, min(1.0, blended.get("swing", 0.0)))
    blended["push_pull"] = max(-0.1, min(0.1, blended.get("push_pull", 0.0)))

    # Clamp humanization parameters (Phase RG4)
    blended["chuck_rate"] = max(0.0, min(1.0, blended.get("chuck_rate", 0.0)))
    blended["humanize_velocity"] = max(0.0, min(1.0, blended.get("humanize_velocity", 0.1)))
    blended["humanize_timing"] = max(0.0, min(1.0, blended.get("humanize_timing", 0.05)))
    blended["downbeat_boost"] = max(0.0, min(1.0, blended.get("downbeat_boost", 0.2)))
    # sustain_cut_rate: user override takes precedence
    blended["sustain_cut_rate"] = max(0.0, min(1.0, float(extra.get("sustain_cut_rate", blended.get("sustain_cut_rate", 0.0)))))

    # Handle register ranges
    register_min = extra.get("register_min")
    register_max = extra.get("register_max")
    if register_min is not None:
        register_min = int(register_min)
    if register_max is not None:
        register_max = int(register_max)

    # Phase 1.4: Parse strum_style — user override takes precedence over blended
    strum_style = str(extra.get("strum_style", blended.get("strum_style", "balanced"))).strip().lower()
    if strum_style not in ("balanced", "downbeat_heavy", "upbeat_heavy"):
        strum_style = "balanced"

    # Create params object
    return RhythmGuitarParams(
        style=str(blended.get("style", "auto")),
        strum_style=strum_style,
        density=float(blended["density"]),
        palm_mute=float(blended["palm_mute"]),
        voicing=str(blended.get("voicing", "auto")),
        register=str(blended.get("register", "mid")),
        register_min=register_min,
        register_max=register_max,
        accent_strength=float(blended["accent_strength"]),
        strum_ms=float(blended["strum_ms"]),
        swing=float(blended["swing"]),
        push_pull=float(blended["push_pull"]),
        groove=str(blended.get("groove", "tight")),
        chuck_rate=float(blended["chuck_rate"]),
        humanize_velocity=float(blended["humanize_velocity"]),
        humanize_timing=float(blended["humanize_timing"]),
        downbeat_boost=float(blended["downbeat_boost"]),
        sustain_cut_rate=float(blended["sustain_cut_rate"]),
        section_contrast=contrast,
        use_patterns=bool(blended.get("use_patterns", False)),
    )


def _lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation between a and b."""
    return a + (b - a) * t


def params_to_dict(params: RhythmGuitarParams) -> Dict[str, Any]:
    """Convert RhythmGuitarParams to a dictionary for display.

    Args:
        params: Resolved parameters

    Returns:
        dict: Parameter dictionary
    """
    result = {
        "style": params.style,
        "density": round(params.density, 2),
        "palm_mute": round(params.palm_mute, 2),
        "voicing": params.voicing,
        "register": params.register,
        "accent_strength": round(params.accent_strength, 2),
        "strum_ms": round(params.strum_ms, 1),
        "swing": round(params.swing, 2),
        "push_pull": round(params.push_pull, 3),
        "groove": params.groove,
        "chuck_rate": round(params.chuck_rate, 2),
        "humanize_velocity": round(params.humanize_velocity, 2),
        "humanize_timing": round(params.humanize_timing, 2),
        "downbeat_boost": round(params.downbeat_boost, 2),
        "sustain_cut_rate": round(params.sustain_cut_rate, 2),
        "section_contrast": round(params.section_contrast, 2),
        "use_patterns": params.use_patterns,
    }

    if params.register_min is not None:
        result["register_min"] = params.register_min
    if params.register_max is not None:
        result["register_max"] = params.register_max

    return result


def get_register_range(params: RhythmGuitarParams) -> Tuple[int, int]:
    """Get MIDI note range for the given register setting.

    Args:
        params: Resolved parameters

    Returns:
        Tuple[int, int]: (min_midi, max_midi)
    """
    # Explicit range overrides register setting
    if params.register_min is not None and params.register_max is not None:
        return (params.register_min, params.register_max)

    # Map register name to MIDI range
    register_ranges = {
        "low": (40, 55),    # E2-G3
        "mid": (48, 64),    # C3-E4
        "high": (55, 72),   # G3-C5
    }

    return register_ranges.get(params.register, register_ranges["mid"])
