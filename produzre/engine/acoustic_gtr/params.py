"""Parameter resolution for acoustic guitar engine.

Neutral defaults → section-type defaults → intensity scaling → user overrides.
Same nested-extra unwrap pattern as rhythm_gtr/legacy_params.py.
"""

from __future__ import annotations

from dataclasses import dataclass

from .defaults import (
    TECHNIQUE_DEFAULTS,
    TECHNIQUE_DEFAULT_FALLBACK,
    VALID_TECHNIQUES,
    STRUM_DENSITY,
    STRUM_DENSITY_DEFAULT,
    PICKING_PATTERN_DEFAULTS,
    PICKING_PATTERN_DEFAULT_FALLBACK,
    VELOCITY_BASE,
    VELOCITY_BASE_DEFAULT,
    VELOCITY_INTENSITY_RANGE,
    VEL_VARIATION_DEFAULT,
    TIMING_VARIATION_DEFAULT,
)


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(val, hi))


@dataclass
class AcousticGuitarParams:
    """Fully resolved parameters for one section render."""

    # Technique
    technique:        str    # "fingerpicking" | "strumming" | "hybrid" | "percussive"
    picking_pattern:  str    # "travis" | "pima" | "broken_chord" | "waltz" | "roll"
    strum_density:    float  # 0.0-1.0 — fraction of quarter-note positions to strum
    mute_ratio:       float  # 0.0-1.0 — probability of dampened strum hit
    body_tap_ratio:   float  # 0.0-1.0 — probability of body percussion per bar

    # Voicing
    voicing_style:    str    # "open" | "barre" | "auto"
    capo:             int    # 0-12 fret (shifts all pitches up by this many semitones)

    # Dynamics
    intensity:        float
    base_vel:         int
    vel_variation:    int    # ±velocity units for humanization

    # Timing
    timing_variation: float  # ±beats for per-note timing humanization
    offset_beats:     float  # Section-level beat offset

    # Section context
    section_type:     str
    beats_per_bar:    float


def resolve_params(section, instrument_cfg, rhythm_grid) -> AcousticGuitarParams:
    """Parse and validate all acoustic guitar parameters.

    Priority order:
      1. Neutral/fallback defaults
      2. Section-type specific defaults
      3. User overrides from instrument_cfg.extra
      4. Intensity scaling for velocity
    """
    sec_type = (section.type or "").strip().lower()
    bpb = rhythm_grid.beats_per_bar

    # Extract intensity and offset from instrument config
    intensity = 1.0
    offset_beats = 0.0
    if instrument_cfg is not None:
        intensity = float(getattr(instrument_cfg, "intensity", 1.0))
        offset_beats = float(getattr(instrument_cfg, "offset_beats", 0.0))
    intensity = _clamp(intensity, 0.0, 2.0)

    # Unwrap nested extra dict (config loader wraps section extra params)
    extra: dict = {}
    if instrument_cfg is not None:
        raw_extra = getattr(instrument_cfg, "extra", {}) or {}
        if isinstance(raw_extra, dict) and "extra" in raw_extra:
            raw_extra = raw_extra["extra"]
        if isinstance(raw_extra, dict):
            extra = raw_extra

    # ---- Technique ----
    technique = extra.get("technique", None)
    if technique is None:
        technique = TECHNIQUE_DEFAULTS.get(sec_type, TECHNIQUE_DEFAULT_FALLBACK)
    if isinstance(technique, str):
        technique = technique.strip().lower()
    if technique not in VALID_TECHNIQUES:
        technique = TECHNIQUE_DEFAULT_FALLBACK

    # ---- Picking pattern ----
    picking_pattern = extra.get("picking_pattern", None)
    if picking_pattern is None:
        picking_pattern = PICKING_PATTERN_DEFAULTS.get(sec_type, PICKING_PATTERN_DEFAULT_FALLBACK)
    if isinstance(picking_pattern, str):
        picking_pattern = picking_pattern.strip().lower()

    # ---- Strum density ----
    strum_density = extra.get("strum_density", None)
    if strum_density is None:
        strum_density = STRUM_DENSITY.get(sec_type, STRUM_DENSITY_DEFAULT)
    try:
        strum_density = float(strum_density)
    except (TypeError, ValueError):
        strum_density = STRUM_DENSITY_DEFAULT
    strum_density = _clamp(strum_density * intensity, 0.05, 1.0)

    # ---- Mute ratio ----
    mute_ratio = extra.get("mute_ratio", 0.08)
    try:
        mute_ratio = float(mute_ratio)
    except (TypeError, ValueError):
        mute_ratio = 0.08
    mute_ratio = _clamp(mute_ratio, 0.0, 0.5)

    # ---- Body tap ratio ----
    body_tap_ratio = extra.get("body_tap_ratio", 0.0)
    try:
        body_tap_ratio = float(body_tap_ratio)
    except (TypeError, ValueError):
        body_tap_ratio = 0.0
    body_tap_ratio = _clamp(body_tap_ratio, 0.0, 0.5)

    # ---- Voicing style ----
    voicing_style = extra.get("voicing_style", "auto")
    if isinstance(voicing_style, str):
        voicing_style = voicing_style.strip().lower()
    if voicing_style not in ("open", "barre", "auto"):
        voicing_style = "auto"

    # ---- Capo ----
    capo = extra.get("capo", 0)
    try:
        capo = int(capo)
    except (TypeError, ValueError):
        capo = 0
    capo = max(0, min(capo, 12))

    # ---- Velocity ----
    section_base_vel = VELOCITY_BASE.get(sec_type, VELOCITY_BASE_DEFAULT)
    base_vel = int(section_base_vel + VELOCITY_INTENSITY_RANGE * _clamp(intensity, 0.0, 1.0))
    base_vel = max(30, min(110, base_vel))

    # ---- Humanization ----
    vel_variation = extra.get("vel_variation", VEL_VARIATION_DEFAULT)
    try:
        vel_variation = int(vel_variation)
    except (TypeError, ValueError):
        vel_variation = VEL_VARIATION_DEFAULT
    vel_variation = max(0, min(vel_variation, 20))

    timing_variation = extra.get("timing_variation", TIMING_VARIATION_DEFAULT)
    try:
        timing_variation = float(timing_variation)
    except (TypeError, ValueError):
        timing_variation = TIMING_VARIATION_DEFAULT
    timing_variation = _clamp(timing_variation, 0.0, 0.05)

    return AcousticGuitarParams(
        technique=technique,
        picking_pattern=picking_pattern,
        strum_density=strum_density,
        mute_ratio=mute_ratio,
        body_tap_ratio=body_tap_ratio,
        voicing_style=voicing_style,
        capo=capo,
        intensity=intensity,
        base_vel=base_vel,
        vel_variation=vel_variation,
        timing_variation=timing_variation,
        offset_beats=offset_beats,
        section_type=sec_type,
        beats_per_bar=bpb,
    )
