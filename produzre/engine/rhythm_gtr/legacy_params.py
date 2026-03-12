"""Parameter resolution for legacy rhythm guitar rendering.

This module extracts and validates all configuration parameters for the legacy
(grid-based) rhythm guitar renderer, including section-type defaults, user knobs,
and strategy presets.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from ...model import SectionConfig
from ...rhythm import RhythmGrid


def _clamp(val: float, lo: float, hi: float) -> float:
    """Clamp a value to [lo, hi]."""
    return max(lo, min(val, hi))


def _lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation between a and b by t (0..1)."""
    return a + (b - a) * t


def _truthy(val) -> bool:
    """Convert various truthy values to bool."""
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        s = val.strip().lower()
        return s in ("true", "yes", "1", "on")
    return bool(val)


@dataclass
class LegacyGuitarParams:
    """Resolved parameters for legacy rhythm guitar rendering."""

    # Intensity & velocity
    intensity: float
    base_vel: int

    # Voicing & style
    voicing: str  # "tight" or "open"
    playstyle: Optional[str]  # "pmute", etc.
    play_pattern: Optional[str]  # "gallop", "syncopated", etc.

    # Density control
    density_scale: float  # Combined section default + user knob
    contrast: float  # How strongly section defaults apply (0..1)
    density_knob: float  # User multiplier (0.25..2.0)

    # Mute control
    mute_amount: float  # Final mute amount (0..1)
    mute_knob: Optional[float]  # User override

    # Style preset
    style: Optional[str]  # "chug", etc.

    # Strum emphasis (Phase 1.4)
    strum_style: str  # "balanced", "downbeat_heavy", "upbeat_heavy"

    # Sustain mode (Phase 4.3)
    sustain_mode: bool
    sustain_duration: float

    # Strum feel
    strum_amt: float  # Strum amount (0..1)
    strum_beats: float  # Strum spread in beats
    strum_dir: str  # "down", "up", "alt"

    # Retrigger policy
    retrigger: str  # "all", "beat", "bar", "chord", "accent", "none"
    user_retrigger_specified: bool

    # Re-attack shaping
    reattack_vel: float  # Velocity multiplier for re-attacks
    reattack_dur: float  # Duration multiplier for re-attacks
    reattack_strum: float  # Strum amount for re-attacks

    # Hit strategy
    hit_strategy: str  # "sustain", "stabs", "chops", "chug"
    stab_beats: Optional[float]  # Duration for stabs

    # Voice leading
    voice_leading: bool
    vl_lo: int  # Voice range low (MIDI note)
    vl_hi: int  # Voice range high (MIDI note)

    # Effective intensity (after density scaling)
    eff_intensity: float

    # Rhythm grid basics
    beats_per_bar: float
    step_beats: float

    # Section info
    section_type: str
    offset_beats: float


def resolve_legacy_guitar_params(
    section: SectionConfig,
    instrument_cfg,
    rhythm_grid: RhythmGrid,
) -> LegacyGuitarParams:
    """Parse and validate all legacy rhythm guitar parameters.

    Args:
        section: Section configuration
        instrument_cfg: Instrument configuration with intensity, extra params
        rhythm_grid: Rhythm grid for beat/bar calculations

    Returns:
        Validated parameter object with all defaults applied
    """
    # Resolve section-level rhythm guitar config from the instrument_cfg
    raw_intensity = instrument_cfg.intensity if instrument_cfg is not None else 1.0
    style_bias = getattr(instrument_cfg, "style_bias", 0.0) if instrument_cfg is not None else 0.0
    intensity = raw_intensity + style_bias
    intensity = max(0.0, min(intensity, 2.0))
    base_vel = int(75 * max(0.1, min(intensity, 2.0)))

    voicing = getattr(instrument_cfg, "voicing", None) if instrument_cfg is not None else None
    playstyle = getattr(instrument_cfg, "playstyle", None) if instrument_cfg is not None else None

    # Optional pattern override from YAML (resolved below after extra is unwrapped)
    play_pattern = None

    # Default voicing per section type if not explicitly overridden
    if voicing is None:
        if section.type in ("verse", "bridge"):
            voicing = "tight"
        elif section.type in ("chorus", "hook", "refrain"):
            voicing = "open"
        else:
            voicing = "tight"  # Default fallback

    # Per-section rhythmic and placement settings
    offset_beats = instrument_cfg.offset_beats if instrument_cfg is not None else 0.0

    # Rhythm grid basics (needed for strum defaults below)
    bpb = rhythm_grid.beats_per_bar
    step_beats = getattr(rhythm_grid, "step_beats", 1.0)

    # Section type
    sec_type = (section.type or "").strip().lower()

    # User knobs (all optional)
    extra = instrument_cfg.extra if instrument_cfg is not None else {}
    # Handle nested 'extra' key if present (config loader wraps section extra params)
    if isinstance(extra, dict) and "extra" in extra:
        extra = extra["extra"]

    # Optional pattern override from YAML (now that extra is properly unwrapped)
    play_pattern = extra.get("pattern") if extra else None

    # Contrast knob
    contrast = extra.get("contrast", None)
    if contrast is None:
        contrast = 0.75  # strong, predictable defaults
    try:
        contrast = float(contrast)
    except Exception:
        contrast = 0.75
    contrast = _clamp(contrast, 0.0, 1.0)

    # Density knob
    density_knob = extra.get("density", None)
    if density_knob is None:
        density_knob = 1.0
    try:
        density_knob = float(density_knob)
    except Exception:
        density_knob = 1.0
    density_knob = _clamp(density_knob, 0.25, 2.0)

    # Mute knob
    mute_knob = extra.get("mute", None)
    if mute_knob is not None:
        try:
            mute_knob = float(mute_knob)
        except Exception:
            mute_knob = None
    if mute_knob is not None:
        mute_knob = _clamp(mute_knob, 0.0, 1.0)

    # Style preset
    style = extra.get("style", None)
    if isinstance(style, str):
        style = style.strip().lower()

    # Phase 4.3: Sustained chord mode
    sustain_mode = extra.get("sustain_mode", False)
    try:
        sustain_mode = bool(sustain_mode)
    except Exception:
        sustain_mode = False

    sustain_duration = extra.get("sustain_duration", 2.0)
    if sustain_duration is not None:
        try:
            sustain_duration = float(sustain_duration)
        except Exception:
            sustain_duration = 2.0
    sustain_duration = _clamp(sustain_duration, 0.1, 16.0)

    # Section-type defaults (blendable via contrast)
    if sec_type in ("chorus", "hook", "refrain"):
        default_density_scale = 1.10
        default_mute = 0.15
        default_voicing = "open"
    else:
        default_density_scale = 0.85
        default_mute = 0.55
        default_voicing = "tight"

    density_scale = _lerp(1.0, default_density_scale, contrast) * density_knob
    mute_amount = mute_knob if mute_knob is not None else _lerp(0.0, default_mute, contrast)

    # If voicing isn't specified, keep existing behavior but allow stronger section defaults
    if voicing is None:
        voicing = default_voicing

    # Phase 1.4: Strum style (downbeat/upbeat emphasis)
    strum_style = extra.get("strum_style", "balanced")
    if isinstance(strum_style, str):
        strum_style = strum_style.strip().lower()
    if strum_style not in ("balanced", "downbeat_heavy", "upbeat_heavy"):
        strum_style = "balanced"

    # Simple style preset: "chug" implies pmute + gallop unless user already set them
    if style == "chug":
        if playstyle is None:
            playstyle = "pmute"
        if not play_pattern:
            play_pattern = "gallop"

    # Strum feel
    strum_amt = extra.get("strum", 0.0)
    try:
        strum_amt = float(strum_amt)
    except Exception:
        strum_amt = 0.0
    strum_amt = _clamp(strum_amt, 0.0, 1.0)

    strum_beats = extra.get("strum_beats", None)
    if strum_beats is not None:
        try:
            strum_beats = float(strum_beats)
        except Exception:
            strum_beats = None

    # Default spread: up to ~1/16 note at 4/4 (0.25 beat) but much smaller
    if strum_beats is None:
        strum_beats = strum_amt * min(0.08, step_beats * 0.35)
    strum_beats = max(0.0, min(float(strum_beats), 0.12))

    strum_dir = extra.get("strum_dir", "down")
    if isinstance(strum_dir, str):
        strum_dir = strum_dir.strip().lower()
    else:
        strum_dir = "down"

    # Retrigger policy
    retrigger = extra.get("retrigger", None)
    user_retrigger_specified = retrigger is not None
    if isinstance(retrigger, str):
        retrigger = retrigger.strip().lower()
    else:
        retrigger = None

    # Default: reduce re-hits to prevent machine-gun hits
    if retrigger is None:
        retrigger = "beat"

    if retrigger not in ("all", "beat", "bar", "chord", "accent", "none"):
        retrigger = "beat"

    # Re-attack shaping within the same chord
    reattack_vel = extra.get("reattack_vel", 0.92)
    try:
        reattack_vel = float(reattack_vel)
    except Exception:
        reattack_vel = 0.92
    reattack_vel = _clamp(reattack_vel, 0.5, 1.0)

    reattack_dur = extra.get("reattack_dur", 0.75)
    try:
        reattack_dur = float(reattack_dur)
    except Exception:
        reattack_dur = 0.75
    reattack_dur = _clamp(reattack_dur, 0.25, 1.0)

    reattack_strum = extra.get("reattack_strum", 0.35)
    try:
        reattack_strum = float(reattack_strum)
    except Exception:
        reattack_strum = 0.35
    reattack_strum = _clamp(reattack_strum, 0.0, 1.0)

    # Per-section chord hit strategy
    hit_strategy = extra.get("hit_strategy", "auto")
    if isinstance(hit_strategy, str):
        hit_strategy = hit_strategy.strip().lower()
    else:
        hit_strategy = "auto"

    if hit_strategy not in ("auto", "sustain", "stabs", "chops", "chug"):
        hit_strategy = "auto"

    # Auto strategy by section type
    if hit_strategy == "auto":
        if sec_type in ("chorus", "hook", "refrain"):
            hit_strategy = "sustain"
        else:
            hit_strategy = "chops"

    stab_beats = extra.get("stab_beats", None)
    if stab_beats is not None:
        try:
            stab_beats = float(stab_beats)
        except Exception:
            stab_beats = None

    # Strategy presets that imply other settings
    if hit_strategy == "chug":
        if playstyle is None:
            playstyle = "pmute"
        if not play_pattern:
            play_pattern = "gallop"
        # Chug needs frequent retriggers; only override if user didn't specify retrigger
        if not user_retrigger_specified:
            retrigger = "all"

    # Voice-leading (octave shifts to minimize root jumps)
    voice_leading = extra.get("voice_leading", True)
    voice_leading = _truthy(voice_leading) if voice_leading is not True else True

    vl_lo = extra.get("voice_range_low", 40)   # ~E2
    vl_hi = extra.get("voice_range_high", 64)  # ~E4
    try:
        vl_lo = int(vl_lo)
    except Exception:
        vl_lo = 40
    try:
        vl_hi = int(vl_hi)
    except Exception:
        vl_hi = 64
    if vl_hi < vl_lo:
        vl_lo, vl_hi = vl_hi, vl_lo

    # Classify intensity into bands to control density
    eff_intensity = _clamp(intensity * density_scale, 0.0, 2.0)

    return LegacyGuitarParams(
        intensity=intensity,
        base_vel=base_vel,
        voicing=voicing,
        playstyle=playstyle,
        play_pattern=play_pattern,
        density_scale=density_scale,
        contrast=contrast,
        density_knob=density_knob,
        mute_amount=mute_amount,
        mute_knob=mute_knob,
        style=style,
        strum_style=strum_style,
        sustain_mode=sustain_mode,
        sustain_duration=sustain_duration,
        strum_amt=strum_amt,
        strum_beats=strum_beats,
        strum_dir=strum_dir,
        retrigger=retrigger,
        user_retrigger_specified=user_retrigger_specified,
        reattack_vel=reattack_vel,
        reattack_dur=reattack_dur,
        reattack_strum=reattack_strum,
        hit_strategy=hit_strategy,
        stab_beats=stab_beats,
        voice_leading=voice_leading,
        vl_lo=vl_lo,
        vl_hi=vl_hi,
        eff_intensity=eff_intensity,
        beats_per_bar=bpb,
        step_beats=step_beats,
        section_type=sec_type,
        offset_beats=offset_beats,
    )
