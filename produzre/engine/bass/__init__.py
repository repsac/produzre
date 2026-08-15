# produzre/engine/bass/__init__.py
from __future__ import annotations

import logging
from collections import namedtuple
from typing import Optional, Dict

# Lightweight drum-event view used to feed apply_drum_locking from
# RhythmFeatures (which publishes beat sets, not event objects).
_DrumHit = namedtuple("_DrumHit", ["beat", "kind"])

from ...model import (
    RootConfig,
    SectionConfig,
    RhythmIntent,
    InstrumentNegotiationFeatures,
)
from ...harmony import HarmonySectionPlan
from ...rhythm import RhythmGrid
from ...timeline import InstrumentTimeline

# Import from patterns subpackage
from .patterns import (
    create_subdivision_slots,
    get_rhythm_pattern_anchor,
    get_rhythm_pattern_push,
    get_rhythm_pattern_drive,
    get_rhythm_pattern_syncopated,
    get_rhythm_pattern_rock_riff,
    get_rhythm_pattern_funk_16ths,
    apply_density_filter,
    apply_rest_filter,
    apply_drum_locking,
    apply_motif_repetition,
)

# Import from harmony module
from .harmony import (
    KEY_TO_MIDI_ROOT,
    MODE_SCALE_OFFSETS,
    ROMAN_TO_DEGREE,
    get_mode_scale_offsets,
    parse_roman_numeral,
    bass_root_for_numeral,
    resolve_bass_root_midi,
    get_chord_tones,
)

# Import from voicing module
from .voicing import (
    clamp_to_register,
    select_chord_tone_with_voice_leading,
)

# Import from articulation module
from .articulation import (
    get_style_pattern_bias,
    apply_style_velocity,
    apply_style_duration,
)

# Import from approach module
from .approach import (
    is_strong_beat,
    get_diatonic_approach,
    get_chromatic_approach,
    should_allow_passing_tone,
)

# Import from groove module
from .groove import (
    apply_octave_jump,
    should_use_pedal_tone,
    should_use_fifth_drop,
    apply_accent,
)

# Import from slap module
from .slap import (
    determine_slap_technique,
    apply_slap_velocity,
    apply_slap_duration,
)


def _effective_bass_params(instrument_cfg) -> dict:
    """Extract the effective params dict from an instrument config.

    The orchestrated path delivers an InstrumentConfig dataclass whose
    engine params live in `.extra` (there is no `.params` field on the
    dataclass). Raw dicts (tests, legacy callers) may carry either a
    `params` or an `extra` key. Unwraps the loader's nested-`extra`
    wrapping like the other engines do.
    """
    params: dict = {}
    if instrument_cfg is None:
        return params
    if isinstance(instrument_cfg, dict):
        params = instrument_cfg.get("params") or instrument_cfg.get("extra") or {}
    elif getattr(instrument_cfg, "params", None):
        params = instrument_cfg.params
    elif hasattr(instrument_cfg, "extra"):
        params = instrument_cfg.extra or {}
    if isinstance(params, dict) and "extra" in params and isinstance(params["extra"], dict):
        params = params["extra"]
    return params if isinstance(params, dict) else {}

# Import from fills module
from .fills import (
    is_fill_zone,
    should_generate_fill,
    generate_fill_run_to_root,
    generate_fill_octave_climb,
    generate_fill_rhythmic_pickup,
)


# =============================================================================
# Phase B2: Harmony Constants (moved to harmony.py)
# =============================================================================

# Backwards compatibility alias (moved to harmony.py)
_KEY_TO_MIDI_ROOT = KEY_TO_MIDI_ROOT


# Backwards compatibility alias (moved to harmony.py)
_MODE_SCALE_OFFSETS = MODE_SCALE_OFFSETS


# Backwards compatibility alias (moved to harmony.py)
_ROMAN_TO_DEGREE = ROMAN_TO_DEGREE

# Backwards compatibility alias (moved to harmony.py)
_get_mode_scale_offsets = get_mode_scale_offsets


# Backwards compatibility alias (moved to harmony.py)
_parse_roman_numeral = parse_roman_numeral


# Backwards compatibility alias (moved to harmony.py)
_bass_root_for_numeral = bass_root_for_numeral


# Backwards compatibility alias (moved to harmony.py)
_resolve_bass_root_midi = resolve_bass_root_midi


# Backwards compatibility alias (moved to harmony.py)
_get_chord_tones = get_chord_tones


# =============================================================================
# Phase B2: Voice Leading (moved to voicing.py)
# =============================================================================

# Backwards compatibility alias (moved to voicing.py)
_clamp_to_register = clamp_to_register


# Backwards compatibility wrapper (moved to voicing.py, but needs approach function injection)
def _select_chord_tone_with_voice_leading(
    chord_tones: Dict[str, int],
    prev_pitch: Optional[int],
    is_downbeat: bool,
    is_cadence: bool,
    approach_rate: float,
    next_root: Optional[int],
    register_low: int,
    register_high: int,
    rng,
    chromatic_rate: float = 0.0,
    mode_offsets: Optional[list[int]] = None,
    key_root: int = 60,
    motion_style: str = "stepwise",
    root_bias: Optional[float] = None,
) -> tuple[int, str]:
    """Wrapper for backwards compatibility - injects approach functions."""
    # Inject approach functions (defined later in this file)
    return select_chord_tone_with_voice_leading(
        chord_tones=chord_tones,
        prev_pitch=prev_pitch,
        is_downbeat=is_downbeat,
        is_cadence=is_cadence,
        approach_rate=approach_rate,
        next_root=next_root,
        register_low=register_low,
        register_high=register_high,
        rng=rng,
        chromatic_rate=chromatic_rate,
        mode_offsets=mode_offsets,
        key_root=key_root,
        get_chromatic_approach=_get_chromatic_approach,
        get_diatonic_approach=_get_diatonic_approach,
        motion_style=motion_style,
        root_bias=root_bias,
    )


# =============================================================================
# Phase B3: Rhythm Pattern Generators
# =============================================================================

# Backwards compatibility alias (moved to patterns.utils)
_create_subdivision_slots = create_subdivision_slots


# Backwards compatibility alias (moved to patterns.generators)
_get_rhythm_pattern_anchor = get_rhythm_pattern_anchor


# Backwards compatibility alias (moved to patterns.generators)
_get_rhythm_pattern_push = get_rhythm_pattern_push


# Backwards compatibility alias (moved to patterns.generators)
_get_rhythm_pattern_drive = get_rhythm_pattern_drive


# Backwards compatibility alias (moved to patterns.generators)
_get_rhythm_pattern_syncopated = get_rhythm_pattern_syncopated


# Backwards compatibility alias (moved to patterns.filters)
_apply_density_filter = apply_density_filter


# Backwards compatibility alias (moved to patterns.filters)
_apply_rest_filter = apply_rest_filter


# Backwards compatibility alias (moved to patterns.filters)
_apply_drum_locking = apply_drum_locking


def contribute_plan(*args, **kwargs) -> None:
    """Publish the bass role selected by the ensemble prepass."""
    if args:
        raise TypeError("bass.contribute_plan only supports keyword arguments")
    plan = kwargs.get("plan")
    section_ctx = kwargs.get("section_ctx") or {}
    section = section_ctx.get("section")
    if plan is None or section is None:
        return
    ensemble = plan.get(f"ensemble.{section.id}", {})
    role_data = ensemble.get("roles", {}).get("bass", {}) if isinstance(ensemble, dict) else {}
    payload = {
        "section_id": section.id,
        "role": role_data.get("role", "anchor"),
        "density_multiplier": role_data.get("density_multiplier", 1.0),
        "fill_owner": ensemble.get("fill_owner") if isinstance(ensemble, dict) else None,
    }
    plan.set("bass.foundation", payload)
    plan.set("bass.line", {"section_id": section.id, "status": "planned"})


# =============================================================================
# Phase B4: Articulation Style Engine (moved to articulation.py)
# =============================================================================

# Backwards compatibility alias (moved to articulation.py)
_get_style_pattern_bias = get_style_pattern_bias

# Backwards compatibility alias (moved to articulation.py)
_apply_style_velocity = apply_style_velocity

# Backwards compatibility alias (moved to articulation.py)
_apply_style_duration = apply_style_duration


# =============================================================================
# Phase B5: Passing Tones & Approach Notes (moved to approach.py)
# =============================================================================

# Backwards compatibility alias (moved to approach.py)
_is_strong_beat = is_strong_beat

# Backwards compatibility alias (moved to approach.py)
_get_diatonic_approach = get_diatonic_approach

# Backwards compatibility alias (moved to approach.py)
_get_chromatic_approach = get_chromatic_approach

# Backwards compatibility alias (moved to approach.py)
_should_allow_passing_tone = should_allow_passing_tone


# =============================================================================
# Phase B6: Octave Jumps, Fifth Drops, and Accents (moved to groove.py)
# =============================================================================

# Backwards compatibility alias (moved to groove.py)
_apply_octave_jump = apply_octave_jump

# Backwards compatibility alias (moved to groove.py)
_should_use_pedal_tone = should_use_pedal_tone

# Backwards compatibility alias (moved to groove.py)
_should_use_fifth_drop = should_use_fifth_drop

# Backwards compatibility alias (moved to groove.py)
_apply_accent = apply_accent


# =============================================================================
# Phase B7: Slap Technique (moved to slap.py)
# =============================================================================

# Backwards compatibility alias (moved to slap.py)
_determine_slap_technique = determine_slap_technique

# Backwards compatibility alias (moved to slap.py)
_apply_slap_velocity = apply_slap_velocity

# Backwards compatibility alias (moved to slap.py)
_apply_slap_duration = apply_slap_duration


# =============================================================================
# Phase B9: Bass Fills & Transitions (moved to fills.py)
# =============================================================================

# Backwards compatibility alias (moved to fills.py)
_is_fill_zone = is_fill_zone

# Backwards compatibility alias (moved to fills.py)
_should_generate_fill = should_generate_fill

# Backwards compatibility alias (moved to fills.py)
_generate_fill_run_to_root = generate_fill_run_to_root

# Backwards compatibility alias (moved to fills.py)
_generate_fill_octave_climb = generate_fill_octave_climb

# Backwards compatibility alias (moved to fills.py)
_generate_fill_rhythmic_pickup = generate_fill_rhythmic_pickup


def render_into_timeline(
    cfg: Optional[RootConfig] = None,
    section: Optional[SectionConfig] = None,
    harmony_plan: Optional[HarmonySectionPlan] = None,
    rhythm_grid: Optional[RhythmGrid] = None,
    section_start_beat: Optional[float] = None,
    timeline: Optional[InstrumentTimeline] = None,
    logger: Optional[logging.Logger] = None,
    rhythm_intent: Optional["RhythmIntent"] = None,
    **kwargs,
) -> Optional["InstrumentNegotiationFeatures"]:
    """Render bass line for a section into the given timeline.

    Supports two modes:
    1. Legacy mode (explicit parameters) - uses rhythm grid cells
    2. Rhythm lock mode (kwargs with rhythm_features) - follows drum kicks

    Phase B11: Negotiation hooks
        rhythm_intent: Optional orchestrator guidance for rhythm and emphasis.
            When provided, bass will align more strongly to specified accents
            and respect space_budget density constraints.
        Returns: InstrumentNegotiationFeatures with onset_map, accent_map,
            fill_windows_used, and register_profile for orchestration.

    Rhythm lock mode parameters (from kwargs):
        rhythm_features: Dict with 'drums' key containing RhythmFeatures
        instrument_cfg: Bass configuration with params:
            - lock_to_kicks: Follow kick strong beats (default False for legacy compat)
            - avoid_fills: Simplify during drum fills (default True)
            - octave: Bass octave (default 2)
        rng: Deterministic RNG for variation
    """
    # Handle both legacy and new kwargs-based calling conventions
    if cfg is None:
        cfg = kwargs.get("cfg")
    if section is None:
        section = kwargs.get("section")
    if harmony_plan is None:
        harmony_plan = kwargs.get("harmony_plan")
    if rhythm_grid is None:
        rhythm_grid = kwargs.get("rhythm_grid")
    if section_start_beat is None:
        section_start_beat = float(kwargs.get("section_start_beat", 0.0))
    if timeline is None:
        timeline = kwargs.get("timeline")
    if logger is None:
        logger = kwargs.get("logger") or logging.getLogger("produzre.bass")

    rhythm_features_map = kwargs.get("rhythm_features", {})
    rng = kwargs.get("rng")
    plan = kwargs.get("plan")

    # Check if rhythm locking is enabled
    instrument_cfg = kwargs.get("instrument_cfg") or kwargs.get("instrument")

    # --- Groove recipe resolution (same pattern as drums/rhythm_gtr) ---
    # Recipes provide genre-aware groove defaults merged UNDER user params.
    _all_recipes: dict = {}
    if cfg is not None and hasattr(cfg, "raw") and isinstance(getattr(cfg, "raw", None), dict):
        _all_recipes = cfg.raw.get("_recipes", {}).get("bass", {})

    if _all_recipes:
        from ...config.recipes import resolve_recipe_name as _resolve_bass_recipe

        _song = getattr(cfg, "song", None)
        _song_genre = getattr(_song, "genre", None) if _song else None
        _bpm = float(getattr(_song, "bpm", 120.0)) if _song else 120.0
        _meter = str(getattr(_song, "meter", "4/4")) if _song else "4/4"

        _section_type = getattr(section, "type", None) or "default" if section else "default"
        _bass_cfg = getattr(section, "instruments", {}).get("bass") if section else None
        _intensity = None
        if instrument_cfg is not None:
            if isinstance(instrument_cfg, dict):
                _intensity = instrument_cfg.get("intensity")
            else:
                _intensity = getattr(instrument_cfg, "intensity", None)
        if _intensity is None and _bass_cfg is not None:
            _intensity = getattr(_bass_cfg, "intensity", None)
        if _intensity is None:
            _intensity = 1.0

        # Read explicit recipe from section or global instrument config
        _section_recipe = None
        _global_inst_recipe = None
        _inst_genre = None
        if _bass_cfg is not None:
            _section_recipe = getattr(_bass_cfg, "recipe", None)
        if isinstance(instrument_cfg, dict):
            _global_inst_recipe = instrument_cfg.get("recipe")
            _inst_genre = instrument_cfg.get("genre")
        elif instrument_cfg is not None:
            _global_inst_recipe = getattr(instrument_cfg, "recipe", None)
            _inst_genre = getattr(instrument_cfg, "genre", None)

        _genre = _inst_genre if _inst_genre is not None else _song_genre

        _recipe_name = _resolve_bass_recipe(
            instrument="bass",
            genre=_genre,
            section_type=_section_type,
            intensity=_intensity,
            bpm=_bpm,
            time_signature=_meter,
            instrument_recipe=_global_inst_recipe,
            section_recipe=_section_recipe,
            recipes=_all_recipes,
        )

        if _recipe_name and _recipe_name in _all_recipes:
            from ...config.recipes import merge_recipe_params as _merge_recipe_params

            _recipe = _all_recipes[_recipe_name]
            _rp = _recipe.get("params", {})
            if _rp:
                # Merge honoring persona < recipe < user (see merge_recipe_params)
                if isinstance(instrument_cfg, dict):
                    existing = instrument_cfg.get("params") or instrument_cfg.get("extra") or {}
                    instrument_cfg["params"] = _merge_recipe_params(existing, _rp)
                elif instrument_cfg is not None and hasattr(instrument_cfg, "extra"):
                    # Orchestrated path: InstrumentConfig holds params in .extra
                    existing = instrument_cfg.extra or {}
                    if isinstance(existing, dict) and "extra" in existing:
                        existing = existing["extra"]
                    if isinstance(existing, dict):
                        instrument_cfg.extra = _merge_recipe_params(existing, _rp)
                elif instrument_cfg is not None and hasattr(instrument_cfg, "params"):
                    existing = instrument_cfg.params or {}
                    if isinstance(existing, dict):
                        instrument_cfg.params = _merge_recipe_params(existing, _rp)

    params = _effective_bass_params(instrument_cfg)

    lock_to_kicks = False
    if isinstance(params, dict):
        lock_to_kicks = params.get("lock_to_kicks", False)
    elif hasattr(params, "lock_to_kicks"):
        lock_to_kicks = getattr(params, "lock_to_kicks", False)

    # If rhythm locking is enabled and we have drum features, use rhythm lock mode
    drum_features = rhythm_features_map.get("drums") if rhythm_features_map else None
    if rhythm_intent is None and plan is not None and section is not None:
        try:
            from ...orchestrate import EngineCoordinator
            coordinator = EngineCoordinator(plan, logger=logger)
            rhythm_intent = RhythmIntent(
                accent_beats=coordinator.get_accent_beats(section.id),
                space_budget=None,
                fill_windows=list(getattr(drum_features, "fill_windows", []) or []),
                extra={
                    "role": coordinator.get_instrument_role(section.id, "bass"),
                },
            )
        except Exception:
            rhythm_intent = None
    # Theme coupling (M3): resolve riff onsets and lock strength before dispatch.
    riff_onsets: list = []
    if plan is not None and section is not None:
        from ...themes.coupling import get_theme_onsets

        riff_onsets = get_theme_onsets(plan, section.id, "riff")

    lock_to_riff = None
    if isinstance(params, dict):
        lock_to_riff = params.get("lock_to_riff")
    if lock_to_riff is None:
        lock_to_riff = getattr(params, "lock_to_riff", None)
    if lock_to_riff is None:
        lock_to_riff = 0.5 if riff_onsets else 0.0
    try:
        lock_to_riff = max(0.0, min(float(lock_to_riff), 1.0))
    except (TypeError, ValueError):
        lock_to_riff = 0.5 if riff_onsets else 0.0

    # Riff attacks count as accent targets so placed notes punch with the theme.
    if riff_onsets and rhythm_intent is not None:
        rhythm_intent.accent_beats = set(rhythm_intent.accent_beats or set()) | set(
            riff_onsets
        )

    if lock_to_kicks and drum_features is not None and rng is not None:
        return _render_rhythm_locked_bass(
            cfg=cfg,
            section=section,
            harmony_plan=harmony_plan,
            rhythm_grid=rhythm_grid,
            section_start_beat=section_start_beat,
            timeline=timeline,
            drum_features=drum_features,
            instrument_cfg=instrument_cfg,
            rng=rng,
            rhythm_intent=rhythm_intent,
            riff_onsets=riff_onsets,
            lock_to_riff=lock_to_riff,
            logger=logger,
        )

    # Fall back to legacy rhythm grid mode
    return _render_legacy_bass(
        cfg=cfg,
        section=section,
        harmony_plan=harmony_plan,
        rhythm_grid=rhythm_grid,
        section_start_beat=section_start_beat,
        timeline=timeline,
        instrument_cfg=instrument_cfg,
        rng=rng,
        rhythm_intent=rhythm_intent,
        drum_features=drum_features,  # Rule 2: kick-bass alignment
        riff_onsets=riff_onsets,
        lock_to_riff=lock_to_riff,
        logger=logger,
    )


def _render_legacy_bass(
    cfg: RootConfig,
    section: SectionConfig,
    harmony_plan: Optional[HarmonySectionPlan],
    rhythm_grid: RhythmGrid,
    section_start_beat: float,
    timeline: InstrumentTimeline,
    instrument_cfg,
    rng,
    rhythm_intent: Optional[RhythmIntent],
    logger: logging.Logger,
    drum_features=None,  # Rule 2: RhythmFeatures from drums for kick alignment
    riff_onsets=None,    # M3: section-relative riff attack beats (theme coupling)
    lock_to_riff: float = 0.0,
) -> InstrumentNegotiationFeatures:
    """Legacy bass rendering using rhythm grid cells (original implementation).

    Phase B11: Returns negotiation features for orchestration.
    """
    if logger is None:
        logger = logging.getLogger("produzre.bass")

    # Phase B11: Initialize negotiation tracking
    onset_map: Dict[float, int] = {}
    accent_map: Dict[float, float] = {}
    fill_windows_used: list[tuple[float, float]] = []
    pitches_rendered: list[int] = []

    if harmony_plan is None or not harmony_plan.chord_slots:
        logger.debug("Section '%s': no harmony plan; skipping bass.", section.id)
        # Return empty features
        return InstrumentNegotiationFeatures(
            onset_map=onset_map,
            accent_map=accent_map,
            fill_windows_used=fill_windows_used,
            register_profile={},
            event_count=0,
        )

    # Resolve bass config from the merged instrument config (global/persona +
    # section overrides), falling back to the raw section block.
    bass_cfg = section.instruments.get("bass")
    intensity = None
    register = None
    if instrument_cfg is not None and not isinstance(instrument_cfg, dict):
        intensity = getattr(instrument_cfg, "intensity", None)
        register = getattr(instrument_cfg, "register", None)
    elif isinstance(instrument_cfg, dict):
        intensity = instrument_cfg.get("intensity")
        register = instrument_cfg.get("register")
    if intensity is None and bass_cfg is not None:
        intensity = getattr(bass_cfg, "intensity", None)
    if register is None and bass_cfg is not None:
        register = getattr(bass_cfg, "register", None)
    # Macro-dynamics: fall back to the section's resolved intensity (set by
    # orchestrate.plan.resolve_section_intensity) before the engine default.
    if intensity is None:
        intensity = getattr(section, "intensity", None)
    intensity = 1.0 if intensity is None else intensity
    register = register or "low"
    base_vel = int(70 * max(0.1, min(intensity, 2.0)))  # clamp to a reasonable range

    # Effective params: persona + recipe + user, resolved via .extra
    effective_params = _effective_bass_params(instrument_cfg)

    # Extract persona-driven parameters with defaults
    if isinstance(effective_params, dict):
        register_low = effective_params.get("register_low", 28)  # E1
        register_high = effective_params.get("register_high", 52)  # E3
        approach_rate = effective_params.get("approach_rate", 0.24)
        # Phase B3: Rhythm parameters
        density = effective_params.get("density", 0.57)
        rest_rate = effective_params.get("rest_rate", 0.24)
        rhythm_pattern = effective_params.get("rhythm_pattern", "anchor")
        lock_to_kick = effective_params.get("lock_to_kick", 0.0)
        lock_to_snare = effective_params.get("lock_to_snare", 0.0)
        lock_to_hat = effective_params.get("lock_to_hat", 0.0)
        # Phase B4: Articulation style
        articulation_style = effective_params.get("articulation_style", "finger")
        # Phase B5: Passing tones & approach notes
        chromatic_rate = effective_params.get("chromatic_rate", 0.0)
        max_passing_per_bar = effective_params.get("max_passing_per_bar", 2)
        # Phase B6: Groove personality
        octave_jump_rate = effective_params.get("octave_jump_rate", 0.15)
        fifth_jump_rate = effective_params.get("fifth_jump_rate", 0.10)
        pedal_rate = effective_params.get("pedal_rate", 0.0)
        accent_strength = effective_params.get("accent_strength", 1.0)
        # Phase B7: Slap technique
        slap_pop_rate = effective_params.get("slap_pop_rate", 0.4)
        slap_thumb_rate = effective_params.get("slap_thumb_rate", 0.9)
        ghost_perc_rate = effective_params.get("ghost_perc_rate", 0.0)
        slap_velocity_floor = effective_params.get("slap_velocity_floor", 70)
        pop_velocity_boost = effective_params.get("pop_velocity_boost", 15)
        # Phase B9: Fills & transitions
        fill_rate = effective_params.get("fill_rate", 0.0)
        fill_complexity = effective_params.get("fill_complexity", 0.5)
        fill_avoid_drums = effective_params.get("fill_avoid_drums", 0.5)
        phrase_length_bars = effective_params.get("phrase_len_bars", effective_params.get("phrase_length_bars", 4))
        # Phase B10: Solo / lead bass
        solo_density = effective_params.get("solo_density", 0.9)
        solo_register_high = effective_params.get("solo_register_high", 64)
        motif_repeat_rate = effective_params.get("motif_repeat_rate", 0.3)
        # Phase 4.2: Melodic motion style
        motion_style = effective_params.get("motion_style", "stepwise")
        section_role_variation = bool(effective_params.get("section_role_variation", False))
        # Inner-beat root inclusion probability (None = legacy default 0.65)
        root_bias = effective_params.get("root_bias", None)
    else:
        register_low = getattr(effective_params, "register_low", 28)
        register_high = getattr(effective_params, "register_high", 52)
        approach_rate = getattr(effective_params, "approach_rate", 0.24)
        # Phase B3: Rhythm parameters
        density = getattr(effective_params, "density", 0.57)
        rest_rate = getattr(effective_params, "rest_rate", 0.24)
        rhythm_pattern = getattr(effective_params, "rhythm_pattern", "anchor")
        lock_to_kick = getattr(effective_params, "lock_to_kick", 0.0)
        lock_to_snare = getattr(effective_params, "lock_to_snare", 0.0)
        lock_to_hat = getattr(effective_params, "lock_to_hat", 0.0)
        # Phase B4: Articulation style
        articulation_style = getattr(effective_params, "articulation_style", "finger")
        # Phase B5: Passing tones & approach notes
        chromatic_rate = getattr(effective_params, "chromatic_rate", 0.0)
        max_passing_per_bar = getattr(effective_params, "max_passing_per_bar", 2)
        # Phase B6: Groove personality
        octave_jump_rate = getattr(effective_params, "octave_jump_rate", 0.15)
        fifth_jump_rate = getattr(effective_params, "fifth_jump_rate", 0.10)
        pedal_rate = getattr(effective_params, "pedal_rate", 0.0)
        accent_strength = getattr(effective_params, "accent_strength", 1.0)
        # Phase B7: Slap technique
        slap_pop_rate = getattr(effective_params, "slap_pop_rate", 0.4)
        slap_thumb_rate = getattr(effective_params, "slap_thumb_rate", 0.9)
        ghost_perc_rate = getattr(effective_params, "ghost_perc_rate", 0.0)
        slap_velocity_floor = getattr(effective_params, "slap_velocity_floor", 70)
        pop_velocity_boost = getattr(effective_params, "pop_velocity_boost", 15)
        # Phase B9: Fills & transitions
        fill_rate = getattr(effective_params, "fill_rate", 0.0)
        fill_complexity = getattr(effective_params, "fill_complexity", 0.5)
        fill_avoid_drums = getattr(effective_params, "fill_avoid_drums", 0.5)
        phrase_length_bars = getattr(effective_params, "phrase_len_bars", getattr(effective_params, "phrase_length_bars", 4))
        # Phase B10: Solo / lead bass
        solo_density = getattr(effective_params, "solo_density", 0.9)
        solo_register_high = getattr(effective_params, "solo_register_high", 64)
        motif_repeat_rate = getattr(effective_params, "motif_repeat_rate", 0.3)
        # Phase 4.2: Melodic motion style
        motion_style = getattr(effective_params, "motion_style", "stepwise")
        section_role_variation = bool(getattr(effective_params, "section_role_variation", False))
        # Inner-beat root inclusion probability (None = legacy default 0.65)
        root_bias = getattr(effective_params, "root_bias", None)

    # Phase B4: Apply style-based pattern bias if rhythm_pattern wasn't explicitly set
    # (Only if user didn't override rhythm_pattern in persona or config)
    style_pattern_bias = _get_style_pattern_bias(articulation_style)
    # If rhythm_pattern is default "anchor" and style suggests different, use style bias
    # (This is subtle - we respect explicit user choices but apply style intelligence)
    if rhythm_pattern == "anchor" and articulation_style in ("pick", "mute", "slap"):
        # User didn't override pattern, so apply style bias
        rhythm_pattern = style_pattern_bias

    # Section role bias: keep verses grounded, make choruses/bridges move differently
    # when the user has not chosen a more specific rhythm pattern.
    section_type_lower = str(getattr(section, "type", "") or "").lower()
    if rhythm_pattern == "anchor" and section_role_variation:
        if section_type_lower in ("chorus", "hook", "climax") and density >= 0.35:
            rhythm_pattern = "drive"
            rest_rate = min(rest_rate, 0.12)
        elif section_type_lower in ("bridge", "breakdown", "solo"):
            rhythm_pattern = "syncopated"
            approach_rate = max(approach_rate, 0.32)

    # Phase B10: Detect solo/lead bass mode and apply overrides
    is_solo_mode = False
    if section:
        # Check for solo flag or role=lead
        section_solo = getattr(section, "solo", None)
        section_role = getattr(section, "role", None)
        is_solo_mode = (section_solo is True) or (section_role == "lead")

    if is_solo_mode:
        # Apply solo mode overrides
        density = solo_density  # Higher density for melodic lines
        register_high = solo_register_high  # Expanded range
        lock_to_kick *= 0.3  # Reduce kick locking for melodic independence
        lock_to_snare *= 0.5  # Reduce snare locking
        # Increase syncopation for more melodic phrasing
        # (Note: syncopation isn't a parameter yet, but density increase helps)

        if logger:
            logger.debug("[BASS] Solo overrides applied: density=%.2f, register_high=%d", density, register_high)

    # Phase B11: Apply space_budget constraint from rhythm_intent
    if rhythm_intent and rhythm_intent.space_budget is not None:
        # Reduce density to respect orchestrator's space budget
        original_density = density
        density = min(density, rhythm_intent.space_budget)
        if logger and density < original_density:
            logger.debug("[BASS] Space budget applied: density %.2f → %.2f", original_density, density)

    events_before = len(timeline.events)

    # Structured debug logging
    if logger:
        numerals_summary = " ".join(cs.numeral for cs in harmony_plan.chord_slots)
        mode_str = "solo" if is_solo_mode else "legacy"
        logger.info(
            "[BASS] Section '%s' (type=%s): mode=%s, intensity=%.2f, register=%s",
            section.id,
            section.type,
            mode_str,
            intensity,
            register,
        )
        logger.info(
            "[BASS]   Harmony: %d slots (%s), key=%s, mode=%s",
            len(harmony_plan.chord_slots),
            numerals_summary,
            section.key or cfg.song.key or "C",
            getattr(cfg.song, "mode", "ionian"),
        )

    # Per-section bass offset (can be used to push/pull the line slightly).
    offset_beats = getattr(bass_cfg, "offset_beats", None) if bass_cfg is not None else None
    if offset_beats is None:
        offset_beats = 0.0

    bpb = rhythm_grid.beats_per_bar

    eps = 1e-6

    # Get mode offsets for chord tone calculation
    mode_offsets = _get_mode_scale_offsets(getattr(cfg.song, "mode", None))

    # Phase B5: Get key root for diatonic approach calculations (middle C register)
    key_name = (section.key or cfg.song.key or "C").strip()
    key_name = key_name.replace("♭", "b").replace("♯", "#")
    # _KEY_TO_MIDI_ROOT is in bass register (C2 = 36), convert to middle register (C4 = 60)
    bass_key_root = _KEY_TO_MIDI_ROOT.get(key_name, 36)  # C2
    key_root = bass_key_root + 24  # Convert to C4 register (60)

    # Check if walking persona (allows passing tones on strong beats + needs all quarter notes)
    # Walking bass triggers either explicitly (rhythm_pattern: walking) or
    # heuristically on a dense anchor pattern with frequent approach tones.
    is_walking_persona = (
        rhythm_pattern == "walking"
        or (rhythm_pattern == "anchor" and density >= 0.8 and approach_rate >= 0.25)
    )

    # Track previous pitch for voice leading
    prev_pitch = None

    # Phase B5: Track passing tones per bar
    current_bar = -1
    passing_count_in_bar = 0

    # Detect if we're at section end for cadence behavior
    total_beats = harmony_plan.chord_slots[-1].end_beat if harmony_plan.chord_slots else rhythm_grid.total_beats

    # Phase B3: Create subdivision-based rhythm scaffold
    subdivisions_per_beat = 4  # 16th notes for maximum flexibility
    all_slots = _create_subdivision_slots(total_beats, subdivisions_per_beat)

    # Get chord change positions for push pattern
    chord_changes = [cs.start_beat for cs in harmony_plan.chord_slots]

    # Select rhythm pattern based on persona
    # Walking bass (is_walking_persona) needs all quarter notes, not just beats 1 and 3
    if rhythm_pattern in ("anchor", "walking"):
        eligible_slots = _get_rhythm_pattern_anchor(all_slots, bpb, subdivisions_per_beat, walking_quarters=is_walking_persona)
    elif rhythm_pattern == "push":
        eligible_slots = _get_rhythm_pattern_push(all_slots, bpb, chord_changes, subdivisions_per_beat)
    elif rhythm_pattern == "drive":
        eligible_slots = _get_rhythm_pattern_drive(all_slots, bpb, subdivisions_per_beat)
    elif rhythm_pattern == "syncopated":
        eligible_slots = _get_rhythm_pattern_syncopated(all_slots, bpb, subdivisions_per_beat)
    elif rhythm_pattern == "rock_riff":
        eligible_slots = get_rhythm_pattern_rock_riff(all_slots, bpb, subdivisions_per_beat)
    elif rhythm_pattern == "funk_16ths":
        eligible_slots = get_rhythm_pattern_funk_16ths(all_slots, bpb, subdivisions_per_beat)
    else:
        # Default to anchor pattern
        eligible_slots = _get_rhythm_pattern_anchor(all_slots, bpb, subdivisions_per_beat, walking_quarters=is_walking_persona)

    # Apply density filtering
    selected_slots = _apply_density_filter(eligible_slots, density, rng)

    # Apply rest filtering
    selected_slots = _apply_rest_filter(selected_slots, rest_rate, rng)

    if rhythm_pattern in ("rock_riff", "funk_16ths"):
        selected_slots = apply_motif_repetition(
            selected_slots,
            beats_per_bar=bpb,
            total_beats=total_beats,
            repeat_rate=float(motif_repeat_rate),
            rng=rng,
        )

    # Drum locking: pull bass onto drum hits per lock_to_kick / lock_to_snare /
    # lock_to_hat. RhythmFeatures exposes kick strong beats and snare/crash
    # accent beats; hat positions aren't published, so lock_to_hat only fires
    # if richer drum events ever flow through here.
    if (
        drum_features is not None
        and rng is not None
        and (lock_to_kick > 0 or lock_to_snare > 0 or lock_to_hat > 0)
    ):
        _drum_events = [
            _DrumHit(beat=b, kind="kick")
            for b in sorted(getattr(drum_features, "strong_beats", set()) or set())
        ] + [
            _DrumHit(beat=b, kind="snare")
            for b in sorted(getattr(drum_features, "accent_beats", set()) or set())
        ]
        if _drum_events:
            selected_slots = _apply_drum_locking(
                slots=selected_slots,
                drum_events=_drum_events,
                lock_to_kick=lock_to_kick,
                lock_to_snare=lock_to_snare,
                lock_to_hat=lock_to_hat,
                subdivisions_per_beat=subdivisions_per_beat,
                rng=rng,
            )

    # Rule 2: Bass-kick alignment (per kick beat not already covered).
    # MIDI analysis showed 60% bass-kick coincidence on strong beats; the
    # lock_to_kick param overrides that default when set.
    if drum_features is not None and drum_features.strong_beats and rng is not None:
        kick_alignment_prob = lock_to_kick if lock_to_kick > 0 else 0.6
        eligible_set = set(round(b, 3) for b in eligible_slots)
        selected_set = set(round(b, 3) for b in selected_slots)
        additions: set = set()
        for kick_beat in sorted(drum_features.strong_beats):
            kb_r = round(kick_beat, 3)
            # Only re-add if the kick beat is a valid eligible position (not completely
            # filtered by the pattern) and wasn't already kept by density/rest pass.
            if kb_r in eligible_set and kb_r not in selected_set:
                if rng.random() < kick_alignment_prob:
                    additions.add(kick_beat)
        if additions:
            selected_slots = selected_slots | additions
            if logger:
                logger.debug(
                    "[COORDINATION] Section '%s': kick-bass alignment added %d beats",
                    section.id,
                    len(additions),
                )

    # Theme coupling (M3): like kick alignment, but for the song's riff
    # attacks — bass notes are re-added at riff onsets the density pass dropped.
    if riff_onsets and rng is not None and lock_to_riff > 0:
        eligible_set = set(round(b, 3) for b in eligible_slots)
        selected_set = set(round(b, 3) for b in selected_slots)
        riff_adds: set = set()
        for onset in riff_onsets:
            draw = rng.random()  # unconditional: stream independent of placement
            o_r = round(float(onset), 3)
            if o_r in eligible_set and o_r not in selected_set and draw < lock_to_riff:
                riff_adds.add(float(onset))
        if riff_adds:
            selected_slots = set(selected_slots) | riff_adds
            if logger:
                logger.debug(
                    "[THEMES] Section '%s': riff-bass alignment added %d beats",
                    section.id,
                    len(riff_adds),
                )

    # Guarantee a cadence anchor: the density/rest filters can stochastically
    # empty the final chord span, leaving the section without resolution (and
    # root_cadence unreachable). If no selected slot falls in the final chord,
    # re-add its first eligible slot (the chord's downbeat) so the section
    # always closes on a resolved root.
    if harmony_plan.chord_slots and selected_slots is not None:
        _final_start = harmony_plan.chord_slots[-1].start_beat
        if not any(s >= _final_start for s in selected_slots):
            _final_eligible = sorted(s for s in eligible_slots if s >= _final_start)
            if not _final_eligible:
                _final_eligible = sorted(s for s in all_slots if s >= _final_start)
            if _final_eligible:
                selected_slots = set(selected_slots) | {_final_eligible[0]}

    # Sort slots for iteration. The list may be extended mid-iteration when a
    # fill is scheduled (fill notes occupy the final subdivisions of a bar).
    slots_iter = sorted(selected_slots)

    # Phase B11: Pre-round intent accent beats so membership checks don't
    # depend on exact float equality (matches kick-alignment rounding).
    intent_accent_beats: set = set()
    if rhythm_intent and rhythm_intent.accent_beats:
        intent_accent_beats = {round(b, 3) for b in rhythm_intent.accent_beats}

    # Phase B5: Track bar boundaries to reset passing tone counter
    current_bar = -1
    passing_count_in_bar = 0
    total_diatonic_approaches = 0
    total_chromatic_approaches = 0

    # Phase B6: Track chord changes for fifth drops and pedal tones
    prev_chord_slot = None
    pedal_pitch = None  # Pitch to hold for pedal tone
    total_octave_jumps = 0
    total_fifth_drops = 0
    total_pedal_tones = 0

    # Phase B7: Track slap technique usage
    total_thumb_hits = 0
    total_pop_hits = 0
    total_ghost_notes = 0

    # Phase B9: Track fills and detect fill zones
    total_fills = 0
    try:
        phrase_length_bars = max(1, int(phrase_length_bars))
    except Exception:
        phrase_length_bars = 4
    active_fill = None  # Dict mapping rounded beat -> (pitch, kind) for active fill
    fill_start_bar = -1  # Bar where current fill started
    fill_start_beat = -1.0  # Phase B11: Beat where current fill started

    # Walk the selected rhythm slots and place bass notes with harmony/voice leading
    i = -1
    while i + 1 < len(slots_iter):
        i += 1
        local_beat = slots_iter[i]
        # Phase B5: Track bar boundaries to reset passing tone counter
        bar_num = int(local_beat // bpb)
        if bar_num != current_bar:
            current_bar = bar_num
            passing_count_in_bar = 0

            # Phase B9: Check for fill zones at bar boundaries
            is_fill_zone, zone_type = _is_fill_zone(local_beat, total_beats, bpb, phrase_length_bars)

            if is_fill_zone and fill_rate > 0:
                # Avoid competing with drum fills anywhere in this bar. Drum
                # features are available because drums render before bass.
                bar_end = local_beat + bpb
                drum_fill_windows = getattr(drum_features, "fill_windows", []) if drum_features is not None else []
                is_drum_filling = any(
                    float(fill_start) < bar_end and float(fill_end) > local_beat
                    for fill_start, fill_end in drum_fill_windows
                )

                # Decide if we should generate a fill
                should_fill = _should_generate_fill(fill_rate, fill_avoid_drums, is_drum_filling, rng)

                if should_fill and active_fill is None:
                    # Generate a new fill
                    # Determine next chord root for fill target
                    next_section_chord = None
                    for cs in harmony_plan.chord_slots:
                        if cs.start_beat > local_beat:
                            next_section_chord = cs
                            break

                    if next_section_chord is not None:
                        target_root = _bass_root_for_numeral(cfg, section, next_section_chord.numeral, bass_cfg)
                    else:
                        target_root = _bass_root_for_numeral(cfg, section, harmony_plan.chord_slots[0].numeral, bass_cfg)

                    # Choose fill type based on complexity
                    effective_fill_complexity = fill_complexity
                    if zone_type == "section_end":
                        effective_fill_complexity = min(1.0, effective_fill_complexity + 0.18)
                    if effective_fill_complexity < 0.33:
                        # Simple fill: rhythmic pickup
                        fill_type = "pickup"
                        fill_notes = _generate_fill_rhythmic_pickup(
                            current_pitch=prev_pitch or target_root,
                            target_root=target_root,
                            fill_complexity=effective_fill_complexity,
                            register_low=register_low,
                            register_high=register_high,
                            rng=rng,
                        )
                    elif effective_fill_complexity < 0.66:
                        # Medium fill: scalar run
                        fill_type = "run"
                        fill_notes = _generate_fill_run_to_root(
                            current_pitch=prev_pitch or target_root,
                            target_root=target_root,
                            fill_complexity=effective_fill_complexity,
                            register_low=register_low,
                            register_high=register_high,
                            mode_offsets=mode_offsets,
                            key_root=key_root,
                            rng=rng,
                        )
                    else:
                        # Complex fill: octave climb or chromatic run
                        if rng.random() < 0.5:
                            fill_type = "octave"
                            fill_notes = _generate_fill_octave_climb(
                                current_pitch=prev_pitch or target_root,
                                fill_complexity=effective_fill_complexity,
                                register_low=register_low,
                                register_high=register_high,
                                rng=rng,
                            )
                        else:
                            fill_type = "run"
                            fill_notes = _generate_fill_run_to_root(
                                current_pitch=prev_pitch or target_root,
                                target_root=target_root,
                                fill_complexity=effective_fill_complexity,
                                register_low=register_low,
                                register_high=register_high,
                                mode_offsets=mode_offsets,
                                key_root=key_root,
                                rng=rng,
                            )

                    if fill_notes:
                        # Align the fill to the END of the bar so the final
                        # pickup/approach note lands on the last subdivision
                        # before the next downbeat (instead of consuming fill
                        # notes from the start of the fill-zone bar).
                        bar_start = bar_num * bpb
                        bar_end = bar_start + bpb
                        subdivision_duration = 1.0 / subdivisions_per_beat
                        # Cap the fill to the slots remaining after the
                        # current position in this bar.
                        max_notes = int((bar_end - local_beat - eps) // subdivision_duration)
                        if max_notes < len(fill_notes):
                            # Keep the tail (the approach note is last)
                            fill_notes = fill_notes[-max_notes:] if max_notes > 0 else []

                    if fill_notes:
                        n_fill = len(fill_notes)
                        fill_beats = [
                            round(bar_end - (n_fill - k) * subdivision_duration, 6)
                            for k in range(n_fill)
                        ]
                        active_fill = {
                            fb: fill_notes[k] for k, fb in enumerate(fill_beats)
                        }
                        # Replace any normal slots inside the fill window with
                        # the fill beats themselves.
                        fill_window_start = fill_beats[0]
                        remaining = [
                            b for b in slots_iter[i + 1:]
                            if b < fill_window_start - eps or b >= bar_end - eps
                        ]
                        slots_iter = slots_iter[: i + 1] + sorted(set(remaining) | set(fill_beats))
                        fill_start_bar = bar_num
                        fill_start_beat = fill_window_start  # Phase B11: fill window start
                        total_fills += 1

        # Compute gap to next note for legato sustain and duration capping.
        # (Computed after fill scheduling so injected fill beats are seen.)
        if i + 1 < len(slots_iter):
            _next_note_beat = slots_iter[i + 1]
        else:
            _next_note_beat = total_beats
        _note_gap = max(0.25, _next_note_beat - local_beat)  # floor at quarter note

        # Find the chord slot that covers this beat
        cs_for_cell = None
        cs_index = -1
        for idx, cs in enumerate(harmony_plan.chord_slots):
            if cs.start_beat - eps <= local_beat < cs.end_beat - eps:
                cs_for_cell = cs
                cs_index = idx
                break
        if cs_for_cell is None:
            continue

        # Determine where we are within the bar to classify the beat
        beat_in_bar = local_beat % bpb
        is_downbeat = abs(beat_in_bar - 0.0) < eps

        # Detect whether this slot is near the end of current chord span
        chord_end = cs_for_cell.end_beat
        chord_start = cs_for_cell.start_beat
        chord_duration = chord_end - chord_start
        subdivision_duration = 1.0 / subdivisions_per_beat
        # Phase B5: Approach/next-root eligibility is restricted to the LAST
        # selected slot before the chord change, so tension (approach) notes
        # resolve immediately into the next chord instead of hanging.
        is_last_slot_in_chord = _next_note_beat >= chord_end - eps

        # Compute the next chord's root (if there is a next chord) for approach tones
        next_root_midi = None
        if cs_index >= 0 and cs_index + 1 < len(harmony_plan.chord_slots):
            next_cs = harmony_plan.chord_slots[cs_index + 1]
            next_root_midi = _bass_root_for_numeral(cfg, section, next_cs.numeral, bass_cfg)

        # Phase B2: HarmonyPlan-driven note selection with voice leading
        # Compute the bass root for the chord active at this cell
        root_midi = _bass_root_for_numeral(cfg, section, cs_for_cell.numeral, bass_cfg)

        # Get chord tones for current chord
        chord_tones = _get_chord_tones(root_midi, cs_for_cell.numeral, mode_offsets)

        # Phase B6: Detect chord change for fifth drops and pedal tones
        is_chord_change = (prev_chord_slot is None or prev_chord_slot != cs_for_cell)
        if is_chord_change:
            prev_chord_slot = cs_for_cell

        # Detect cadence: the last selected (non-fill) slot within the final
        # chord slot of the section, so root_cadence resolution actually fires
        # for anchor/walking patterns (whose last slot is rarely in the final
        # subdivision of the section).
        is_cadence = False
        if cs_index == len(harmony_plan.chord_slots) - 1:
            is_cadence = True
            for _later in slots_iter[i + 1:]:
                if active_fill is None or round(_later, 6) not in active_fill:
                    # A later non-fill slot exists; this isn't the cadence.
                    is_cadence = False
                    break

        # Phase B5: Check if passing tones are allowed at this position
        allow_passing = _should_allow_passing_tone(
            beat_in_bar=beat_in_bar,
            is_walking_persona=is_walking_persona,
            passing_count_in_bar=passing_count_in_bar,
            max_passing_per_bar=max_passing_per_bar,
        )

        # Phase B9: Check if we're in an active fill and consume fill notes.
        # Fill notes are keyed by their scheduled beat (aligned to the end of
        # the fill bar); other slots fall through to normal selection.
        if active_fill is not None:
            _lb_key = round(local_beat, 6)
            if _lb_key in active_fill:
                pitch, note_kind = active_fill.pop(_lb_key)
                if not active_fill:
                    # Last fill note consumed; close the fill window
                    # Phase B11: Track fill window that was used
                    if fill_start_beat >= 0:
                        fill_windows_used.append((fill_start_beat, local_beat))
                    active_fill = None
                    fill_start_beat = -1.0
            else:
                # Not a fill beat; fall through to normal pitch selection
                pitch = None
                note_kind = None

            # If we got a pitch from fill, skip normal selection
            if pitch is not None:
                # Update previous pitch for voice leading
                prev_pitch = pitch

                # Skip to duration/velocity application
                song_beat = section_start_beat + local_beat + offset_beats
                remaining_in_chord = max(0.0, chord_end - local_beat)
                # Cap at the gap to the next note so consecutive fill notes
                # on a 16th grid never overlap.
                base_duration = min(1.0, remaining_in_chord, _note_gap)

                # Apply style to velocity and duration
                styled_velocity = _apply_style_velocity(
                    base_velocity=base_vel,
                    articulation_style=articulation_style,
                    is_downbeat=is_downbeat,
                    rng=rng,
                )
                styled_duration = _apply_style_duration(
                    base_duration=base_duration,
                    articulation_style=articulation_style,
                    is_downbeat=is_downbeat,
                )

                # Apply slap technique if needed
                slap_technique = "normal"
                if articulation_style == "slap":
                    beat_frac = (local_beat % 1.0)
                    is_offbeat = abs(beat_frac - 0.0) > eps and abs(beat_frac - 0.5) > eps
                    is_strong = is_downbeat or is_chord_change

                    slap_technique = _determine_slap_technique(
                        is_strong_beat=is_strong,
                        is_offbeat=is_offbeat,
                        slap_pop_rate=slap_pop_rate,
                        slap_thumb_rate=slap_thumb_rate,
                        ghost_perc_rate=ghost_perc_rate,
                        rng=rng,
                    )

                    styled_velocity = _apply_slap_velocity(
                        base_velocity=styled_velocity,
                        slap_technique=slap_technique,
                        slap_velocity_floor=slap_velocity_floor,
                        pop_velocity_boost=pop_velocity_boost,
                    )
                    styled_duration = _apply_slap_duration(
                        base_duration=styled_duration,
                        slap_technique=slap_technique,
                    )

                    if slap_technique != "normal":
                        note_kind = f"{note_kind}_slap_{slap_technique}"

                    if slap_technique == "thumb":
                        total_thumb_hits += 1
                    elif slap_technique == "pop":
                        total_pop_hits += 1
                    elif slap_technique == "ghost":
                        total_ghost_notes += 1

                # Apply accent (skip for ghost notes)
                is_accent = (is_downbeat or is_chord_change) and slap_technique != "ghost"

                # Phase B11: Check if rhythm_intent specifies accent at this beat
                if intent_accent_beats and round(local_beat, 3) in intent_accent_beats:
                    is_accent = True

                final_velocity = _apply_accent(styled_velocity, is_accent, accent_strength)

                timeline.add_note(
                    start_beat=song_beat,
                    duration_beats=styled_duration,
                    pitch=pitch,
                    velocity=final_velocity,
                    channel=None,
                    kind=note_kind,
                )

                # Phase B11: Track negotiation features for fill notes
                onset_map[local_beat] = onset_map.get(local_beat, 0) + 1
                if is_accent:
                    accent_map[local_beat] = accent_strength
                pitches_rendered.append(pitch)

                # Continue to next slot
                continue

        # Phase B6: Check for pedal tone (hold previous root across chord change)
        use_pedal = _should_use_pedal_tone(pedal_rate, is_chord_change, rng)

        if use_pedal and pedal_pitch is not None:
            # Use pedal tone (previous root)
            pitch = pedal_pitch
            note_kind = "pedal"
            total_pedal_tones += 1
        else:
            # Phase B6: Check for fifth drop on chord change
            use_fifth = _should_use_fifth_drop(fifth_jump_rate, is_chord_change, is_downbeat, rng)

            if use_fifth and not is_cadence:
                # Use fifth instead of root for variety
                fifth = chord_tones.get("fifth")
                if fifth:
                    pitch = _clamp_to_register(fifth, register_low, register_high)
                    note_kind = "fifth_drop"
                    total_fifth_drops += 1
                else:
                    # Fallback to normal selection if fifth not available
                    pitch, note_kind = _select_chord_tone_with_voice_leading(
                        chord_tones=chord_tones,
                        prev_pitch=prev_pitch,
                        is_downbeat=is_downbeat,
                        is_cadence=is_cadence,
                        approach_rate=0.0,  # No approach on fifth drop
                        next_root=None,
                        register_low=register_low,
                        register_high=register_high,
                        rng=rng,
                        chromatic_rate=chromatic_rate,
                        mode_offsets=mode_offsets,
                        key_root=key_root,
                        motion_style=motion_style,
                        root_bias=root_bias,
                    )
            else:
                # Normal chord tone selection with voice leading
                # Phase B5: Pass chromatic_rate, mode_offsets, key_root for approach notes
                # Only enable approach_rate on the last selected slot of the
                # chord (and where passing tones are allowed), so approach
                # tones always resolve directly into the next chord.
                effective_approach_rate = approach_rate if (is_last_slot_in_chord and allow_passing) else 0.0

                pitch, note_kind = _select_chord_tone_with_voice_leading(
                    chord_tones=chord_tones,
                    prev_pitch=prev_pitch,
                    is_downbeat=is_downbeat,
                    is_cadence=is_cadence,
                    approach_rate=effective_approach_rate,
                    next_root=next_root_midi if is_last_slot_in_chord else None,
                    register_low=register_low,
                    register_high=register_high,
                    rng=rng,
                    chromatic_rate=chromatic_rate,
                    mode_offsets=mode_offsets,
                    key_root=key_root,
                    motion_style=motion_style,
                    root_bias=root_bias,
                )

            # Update pedal pitch if this is a root note on chord change
            if is_chord_change and note_kind in ("root", "root_cadence"):
                pedal_pitch = pitch

        # Phase B6: Apply octave jump for variation (beat-aware: favour structural positions)
        original_pitch = pitch
        pitch = _apply_octave_jump(
            pitch, octave_jump_rate, register_low, register_high, rng,
            is_downbeat=is_downbeat, is_chord_change=is_chord_change,
        )
        if pitch != original_pitch:
            total_octave_jumps += 1
            # Update note kind to reflect octave jump
            note_kind = f"{note_kind}_octave"

        # Phase B5: Track passing/approach tones
        if note_kind == "approach_diatonic":
            passing_count_in_bar += 1
            total_diatonic_approaches += 1
        elif note_kind == "approach_chromatic":
            passing_count_in_bar += 1
            total_chromatic_approaches += 1
        elif note_kind == "approach":
            passing_count_in_bar += 1

        # Update previous pitch for next iteration
        prev_pitch = pitch

        song_beat = section_start_beat + local_beat + offset_beats
        # Keep note durations constrained by remaining chord span
        remaining_in_chord = max(0.0, chord_end - local_beat)
        # Legato sustain: finger/pick fill the gap to the next note so the bass
        # rings naturally. Mute/slap stay percussive (capped at one beat) but
        # are still capped at the gap so same-pitch notes never overlap on
        # 16th grids.
        if articulation_style in ("finger", "pick"):
            _max_sustain = _note_gap
        else:
            _max_sustain = min(1.0, _note_gap)
        base_duration = min(_max_sustain, remaining_in_chord)

        # Phase B4: Apply articulation style to velocity and duration
        styled_velocity = _apply_style_velocity(
            base_velocity=base_vel,
            articulation_style=articulation_style,
            is_downbeat=is_downbeat,
            rng=rng,
        )
        styled_duration = _apply_style_duration(
            base_duration=base_duration,
            articulation_style=articulation_style,
            is_downbeat=is_downbeat,
        )

        # Phase B7: Apply slap technique if articulation_style is slap
        slap_technique = "normal"  # Default for non-slap styles
        if articulation_style == "slap":
            # Determine if this is an offbeat (not on quarter note positions)
            beat_frac = (local_beat % 1.0)
            is_offbeat = abs(beat_frac - 0.0) > eps and abs(beat_frac - 0.5) > eps

            # Consider strong beats as downbeats or chord changes
            is_strong = is_downbeat or is_chord_change

            # Determine slap technique (thumb/pop/ghost)
            slap_technique = _determine_slap_technique(
                is_strong_beat=is_strong,
                is_offbeat=is_offbeat,
                slap_pop_rate=slap_pop_rate,
                slap_thumb_rate=slap_thumb_rate,
                ghost_perc_rate=ghost_perc_rate,
                rng=rng,
            )

            # Apply slap-specific velocity and duration adjustments
            styled_velocity = _apply_slap_velocity(
                base_velocity=styled_velocity,
                slap_technique=slap_technique,
                slap_velocity_floor=slap_velocity_floor,
                pop_velocity_boost=pop_velocity_boost,
            )
            styled_duration = _apply_slap_duration(
                base_duration=styled_duration,
                slap_technique=slap_technique,
            )

            # Update note kind to reflect slap technique
            if slap_technique != "normal":
                note_kind = f"{note_kind}_slap_{slap_technique}"

            # Track slap technique usage
            if slap_technique == "thumb":
                total_thumb_hits += 1
            elif slap_technique == "pop":
                total_pop_hits += 1
            elif slap_technique == "ghost":
                total_ghost_notes += 1

        # Phase B6: Apply accent to velocity
        # Skip accents for ghost notes (they should stay quiet)
        is_accent = (is_downbeat or is_chord_change) and slap_technique != "ghost"

        # Phase B11: Check if rhythm_intent specifies accent at this beat
        if intent_accent_beats and round(local_beat, 3) in intent_accent_beats:
            is_accent = True

        final_velocity = _apply_accent(styled_velocity, is_accent, accent_strength)

        timeline.add_note(
            start_beat=song_beat,
            duration_beats=styled_duration,
            pitch=pitch,
            velocity=final_velocity,
            channel=None,  # resolved by timeline (instrument-aware)
            kind=note_kind,  # Voice label for TSV analysis
        )

        # Phase B11: Track negotiation features
        onset_map[local_beat] = onset_map.get(local_beat, 0) + 1
        if is_accent:
            accent_map[local_beat] = accent_strength
        pitches_rendered.append(pitch)

    added = len(timeline.events) - events_before

    # Phase B5, B6, B7 & B9: Log groove, slap, and fill statistics
    total_approaches = total_diatonic_approaches + total_chromatic_approaches
    total_groove_features = total_octave_jumps + total_fifth_drops + total_pedal_tones
    total_slap_techniques = total_thumb_hits + total_pop_hits + total_ghost_notes

    # Build log message with groove features if any
    log_parts = [
        f"[BASS]   Generated {added} events (pattern={rhythm_pattern}, style={articulation_style}, "
        f"density={density:.2f}, rest_rate={rest_rate:.2f}, base_vel={base_vel}"
    ]

    if total_approaches > 0:
        log_parts.append(f", approaches={total_approaches} [dia={total_diatonic_approaches}, chr={total_chromatic_approaches}]")

    if total_groove_features > 0:
        log_parts.append(f", groove=[oct={total_octave_jumps}, 5th={total_fifth_drops}, pedal={total_pedal_tones}]")

    if total_slap_techniques > 0:
        log_parts.append(f", slap=[thumb={total_thumb_hits}, pop={total_pop_hits}, ghost={total_ghost_notes}]")

    if total_fills > 0:
        log_parts.append(f", fills={total_fills}")

    log_parts.append(")")
    logger.info("".join(log_parts))

    # Phase B11: Build and return negotiation features
    register_profile = {}
    if pitches_rendered:
        register_profile = {
            "min_pitch": min(pitches_rendered),
            "max_pitch": max(pitches_rendered),
            "avg_pitch": sum(pitches_rendered) / len(pitches_rendered),
            "pitch_range": max(pitches_rendered) - min(pitches_rendered),
        }

    return InstrumentNegotiationFeatures(
        onset_map=onset_map,
        accent_map=accent_map,
        fill_windows_used=fill_windows_used,
        register_profile=register_profile,
        event_count=added,
    )


def _render_rhythm_locked_bass(
    cfg: RootConfig,
    section: SectionConfig,
    harmony_plan: Optional[HarmonySectionPlan],
    rhythm_grid: RhythmGrid,
    section_start_beat: float,
    timeline: InstrumentTimeline,
    drum_features,
    instrument_cfg,
    rng,
    rhythm_intent: Optional[RhythmIntent],
    logger: logging.Logger,
    riff_onsets=None,    # M3: section-relative riff attack beats (theme coupling)
    lock_to_riff: float = 0.0,
) -> InstrumentNegotiationFeatures:
    """Render bass line that locks to drum kick patterns.

    This mode follows drum rhythm features instead of using rhythm grid cells:
    - Places bass notes on kick strong beats
    - Avoids fill windows to let drums shine
    - Uses chord root notes from harmony plan

    Phase B11: Supports rhythm_intent and returns negotiation features.
    """
    from ...rhythm_features import is_beat_in_fill

    # Phase B11: Initialize negotiation tracking
    onset_map: Dict[float, int] = {}
    accent_map: Dict[float, float] = {}
    fill_windows_used: list[tuple[float, float]] = []
    pitches_rendered: list[int] = []

    if harmony_plan is None or not harmony_plan.chord_slots:
        logger.debug("Section '%s': no harmony plan; skipping bass.", section.id)
        return InstrumentNegotiationFeatures(
            onset_map=onset_map,
            accent_map=accent_map,
            fill_windows_used=fill_windows_used,
            register_profile={},
            event_count=0,
        )

    # Extract parameters
    params = _effective_bass_params(instrument_cfg)

    avoid_fills = params.get("avoid_fills", True)
    octave = params.get("octave", 2)

    # Get intensity (instrument > resolved section intensity > engine default)
    intensity = None
    if isinstance(instrument_cfg, dict):
        intensity = instrument_cfg.get("intensity")
    elif instrument_cfg is not None:
        intensity = getattr(instrument_cfg, "intensity", None)
    if intensity is None:
        intensity = getattr(section, "intensity", None)
    if intensity is None:
        intensity = 0.7

    base_vel = int(70 + intensity * 30)

    # Get bass config for register handling
    bass_cfg = section.instruments.get("bass")

    events_before = len(timeline.events)

    # Structured debug logging
    logger.info(
        "[BASS] Section '%s' (type=%s): mode=rhythm_lock, intensity=%.2f, octave=%d, avoid_fills=%s",
        section.id,
        section.type,
        intensity,
        octave,
        avoid_fills,
    )
    logger.info(
        "[BASS]   Harmony: %d slots (%s), key=%s, mode=%s",
        len(harmony_plan.chord_slots),
        " ".join(cs.numeral for cs in harmony_plan.chord_slots),
        section.key or cfg.song.key or "C",
        getattr(cfg.song, "mode", "ionian"),
    )

    # Follow kick strong beats
    strong_beats = sorted(drum_features.strong_beats) if hasattr(drum_features, "strong_beats") else []
    logger.info(
        "[BASS]   Locking to %d kick strong beats",
        len(strong_beats),
    )

    # Theme coupling (M3): riff attacks join the lock targets so the bassline
    # doubles the song's riff even where the kick doesn't play it.
    if riff_onsets and rng is not None and lock_to_riff > 0:
        combined = set(strong_beats)
        for onset in riff_onsets:
            draw = rng.random()  # unconditional: stream independent of coverage
            if draw < lock_to_riff and not any(
                abs(float(onset) - b) <= 0.15 for b in combined
            ):
                combined.add(float(onset))
        strong_beats = sorted(combined)

    # Pre-round intent accent beats so membership checks don't depend on
    # exact float equality (matches kick-alignment rounding).
    intent_accent_beats: set = set()
    if rhythm_intent and rhythm_intent.accent_beats:
        intent_accent_beats = {round(b, 3) for b in rhythm_intent.accent_beats}

    eps = 1e-6
    for beat in strong_beats:
        # Skip if in fill window
        if avoid_fills and is_beat_in_fill(beat, drum_features):
            continue

        # Find the chord slot that covers this beat
        cs_for_beat = None
        for cs in harmony_plan.chord_slots:
            if cs.start_beat - eps <= beat < cs.end_beat - eps:
                cs_for_beat = cs
                break
        if cs_for_beat is None:
            continue

        # Get bass root for this chord
        root_midi = _bass_root_for_numeral(cfg, section, cs_for_beat.numeral, bass_cfg)

        # Apply octave adjustment (octave 2 is default, which is handled by _bass_root_for_numeral)
        # Add octave offset if different from default
        octave_offset = (octave - 2) * 12  # 2 is default octave
        root_midi += octave_offset

        # Velocity with slight variation
        velocity = max(50, min(127, base_vel + rng.randint(-5, 5)))

        # Phase B11: Check if rhythm_intent specifies accent at this beat
        is_accent = False
        if intent_accent_beats and round(beat, 3) in intent_accent_beats:
            is_accent = True
            velocity = min(127, int(velocity * 1.3))  # Boost velocity for accents

        # Duration: sustain until next event or reasonable maximum
        bpb = rhythm_grid.beats_per_bar
        duration = min(0.8, bpb / 2.0)

        song_beat = section_start_beat + beat
        timeline.add_note(
            start_beat=song_beat,
            duration_beats=duration,
            pitch=root_midi,
            velocity=velocity,
            channel=None,
            kind="locked_root",  # Voice label: bass locked to kick
        )

        # Phase B11: Track negotiation features
        onset_map[beat] = onset_map.get(beat, 0) + 1
        if is_accent:
            accent_map[beat] = 1.3  # Accent strength applied
        pitches_rendered.append(root_midi)

    added = len(timeline.events) - events_before
    logger.info(
        "[BASS]   Generated %d locked events (base_vel=%d, octave_offset=%+d)",
        added,
        base_vel,
        (octave - 2) * 12,
    )

    # Phase B11: Build and return negotiation features
    register_profile = {}
    if pitches_rendered:
        register_profile = {
            "min_pitch": min(pitches_rendered),
            "max_pitch": max(pitches_rendered),
            "avg_pitch": sum(pitches_rendered) / len(pitches_rendered),
            "pitch_range": max(pitches_rendered) - min(pitches_rendered),
        }

    return InstrumentNegotiationFeatures(
        onset_map=onset_map,
        accent_map=accent_map,
        fill_windows_used=fill_windows_used,
        register_profile=register_profile,
        event_count=added,
    )
