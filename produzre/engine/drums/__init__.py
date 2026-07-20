"""Produzre drums engine (package entrypoint).

This package is a first-class engine target.

Engine import contract:
- `engines.yml` / project YAML may point `drums.engine` to `.engine.drums`
- Importing that path must provide a callable `render_into_timeline(...)`

Implementation notes:
- `groove.py` defines declarative groove templates
- `patterns` package turns templates into idealized DrumEvents
- `humanize.py` applies timing/velocity humanization deterministically

This module only orchestrates those pieces and writes notes into the Timeline.
"""

from __future__ import annotations

from typing import Any, Mapping

import random

from ...rng import make_instrument_rng, stable_seed_int
from ...rhythm_features import extract_rhythm_features
from ...orchestrate import EngineCoordinator
from ...orchestrate.energy import resolve_section_energy
from .fills import add_fills
from .groove import groove_template, resolve_groove_id, steps_per_bar_for_meter
from .humanize import humanize_events
from .ornaments import add_ornaments
from .patterns import DrumEvent, events_for_section_from_template



def _get_mapping(obj: Any) -> Mapping[str, Any]:
    """Best-effort: treat dict-like configs uniformly."""

    if isinstance(obj, dict):
        return obj
    return {}


def _get_attr_or_key(obj: Any, name: str, default: Any = None) -> Any:
    """Read `name` from obj.name if present, else from obj[name] if dict-like."""

    if hasattr(obj, name):
        return getattr(obj, name)
    m = _get_mapping(obj)
    if name in m:
        return m[name]
    return default



def _derive_rng(base_rng: random.Random, label: str) -> random.Random:
    """Derive a deterministic sub-RNG from the current base RNG state.

    This does NOT advance `base_rng`. It hashes the current RNG state with a
    label to create an independent random stream.

    Purpose: keep features like `fill_chatter` from perturbing phrase-end fills
    when toggled on/off.
    """

    state_repr = repr(base_rng.getstate())
    seed = stable_seed_int("derive", state_repr, label)
    return random.Random(seed)


# Musician-friendly placement helper
def _ghost_placements_to_steps(
    placements: Any,
    beats_per_bar: float,
    steps_per_bar: int,
    logger: Any,
) -> list[int]:
    """Convert musician-friendly placements (e.g. '2&', '4e', 2.5) into step indices.

    Placements are interpreted as beat positions within a bar where 1.0 is the downbeat.
    Supported suffixes:
      - '&' => +0.5 beat (eighth offbeat)
      - 'e' => +0.25 beat (16th early)
      - 'a' => +0.75 beat (16th late)

    This is an alias for internal `ghost_steps`.
    """

    def _to_beat(x: Any) -> float:
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip()
        if not s:
            raise ValueError("empty placement")
        suffix = s[-1]
        if suffix in ("&", "e", "a"):
            base = float(s[:-1])
            if suffix == "&":
                return base + 0.5
            if suffix == "e":
                return base + 0.25
            return base + 0.75
        return float(s)

    seq = placements if isinstance(placements, (list, tuple)) else [placements]
    steps: list[int] = []
    for p in seq:
        try:
            beat = _to_beat(p)
        except Exception:
            if logger is not None:
                logger.debug("Ignoring invalid ghost placement: %r", p)
            continue

        frac = (beat - 1.0) / max(1e-9, float(beats_per_bar))
        step = int(round(frac * float(steps_per_bar)))
        if 0 <= step < int(steps_per_bar):
            steps.append(step)

    # De-dupe while preserving order
    out: list[int] = []
    seen: set[int] = set()
    for s in steps:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def contribute_plan(*args: Any, **kwargs: Any) -> None:
    """Export rhythm.grid and rhythm.accents to the PerformancePlan (Phase N6).

    This function is called before render_into_timeline to allow drums to
    provide authoritative rhythm data that other engines can lock to.

    Exports to plan:
        - rhythm.grid: Step grid information (16th note cells per bar)
        - rhythm.accents: Accent beat timestamps (kick, snare, crash positions)

    Expected kwargs:
        plan: PerformancePlan object for writing shared data
        section_ctx: Dict with section metadata (rhythm_grid, section, etc.)
        rng: random.Random for deterministic generation
        logger: logging.Logger for debug output
    """
    if args:
        raise TypeError("drums.contribute_plan only supports keyword arguments")

    plan = kwargs.get("plan")
    section_ctx = kwargs.get("section_ctx", {})
    rng = kwargs.get("rng")
    logger = kwargs.get("logger")

    if plan is None:
        if logger:
            logger.debug("drums.contribute_plan: no plan provided, skipping")
        return

    # Extract section context
    rhythm_grid = section_ctx.get("rhythm_grid")
    section = section_ctx.get("section")

    # Get beats_per_bar and total_beats from rhythm_grid
    beats_per_bar = float(_get_attr_or_key(rhythm_grid, "beats_per_bar", 4.0))
    total_beats = float(_get_attr_or_key(rhythm_grid, "total_beats", 0.0))

    # Calculate step grid. The renderer derives its grid from the meter
    # (4 steps per quarter-note beat: 16 in 4/4, 12 in 3/4, see
    # groove.steps_per_bar_for_meter), so publish that same grid here.
    # Step duration is always 0.25 beats (one 16th note).
    bpb_safe = beats_per_bar if beats_per_bar > 0 else 4.0
    steps_per_bar = steps_per_bar_for_meter(bpb_safe)
    steps_per_beat = steps_per_bar / bpb_safe
    total_steps = int(round((total_beats / bpb_safe) * steps_per_bar))

    # Build rhythm.grid data structure
    rhythm_grid_data = {
        "beats_per_bar": beats_per_bar,
        "total_beats": total_beats,
        "steps_per_beat": steps_per_beat,
        "steps_per_bar": steps_per_bar,
        "total_steps": total_steps,
        "step_duration_beats": bpb_safe / steps_per_bar,
    }

    # Store rhythm.grid in plan
    plan.set("rhythm.grid", rhythm_grid_data)

    # For rhythm.accents, we generate a lightweight preview of where strong
    # beats occur. This is a simplified preview - not the full drum pattern.

    # Build accent beat list based on meter characteristics
    # Accents typically occur on:
    # - Downbeats (beat 1 of each bar)
    # - Backbeats (beats 2 and 4 in 4/4 time)
    # - Kick pattern strong beats
    # - Crash cymbals at phrase boundaries

    accent_beats = []
    num_bars = int(total_beats / beats_per_bar)

    for bar in range(num_bars):
        bar_start_beat = bar * beats_per_bar

        # Downbeat (beat 1) is always an accent
        accent_beats.append(bar_start_beat)

        # Backbeats (snare accents), meter-aware. Mirrors the convention in
        # groove.groove_template:
        #   bpb >= 4 -> beats 2 and 4; bpb == 6 -> beat 4; bpb < 4 -> beat 2.
        if abs(beats_per_bar - 6.0) < 1e-6:
            accent_beats.append(bar_start_beat + 3.0)  # Beat 4
        elif beats_per_bar >= 4.0:
            accent_beats.append(bar_start_beat + 1.0)  # Beat 2
            accent_beats.append(bar_start_beat + 3.0)  # Beat 4
        elif beats_per_bar >= 2.0:
            accent_beats.append(bar_start_beat + 1.0)  # Beat 2

        # First and last bars often have crashes
        if bar == 0 or bar == num_bars - 1:
            # Add crash on downbeat (already added above, but mark as strong)
            pass

    # Remove duplicates and sort
    accent_beats = sorted(set(accent_beats))

    # Store rhythm.accents in plan
    rhythm_accents_data = {
        "accent_beats": accent_beats,
        "num_accents": len(accent_beats),
        "source": "drums_preview",  # Indicates this is from drums contribute_plan
    }

    plan.set("rhythm.accents", rhythm_accents_data)

    if logger:
        logger.debug(
            f"[DRUMS_PLAN] Exported rhythm.grid: {steps_per_bar} steps/bar, "
            f"{total_steps} total steps"
        )
        logger.debug(
            f"[DRUMS_PLAN] Exported rhythm.accents: {len(accent_beats)} accent beats"
        )


def render_into_timeline(*args: Any, **kwargs: Any) -> None:
    """Render drums into a timeline.

    This is the package-level engine entrypoint required by the dynamic engine
    loader.

    The implementation is kwargs-friendly to remain resilient as the
    orchestration layer evolves.

    Expected kwargs (best-effort):
        cfg: RootConfig-like object
        section: SectionPlan-like object
        section_start_beat: float
        rhythm_grid: RhythmGrid-like object (expects beats_per_bar + total_beats)
        timeline: Timeline-like object (expects add_note)
        rng: random.Random
        logger: logging.Logger

    Optional kwargs:
        instrument: per-section instrument config for drums (merged)
    """

    if args:
        raise TypeError("drums.render_into_timeline only supports keyword arguments")

    cfg = kwargs.get("cfg")
    section = kwargs.get("section")
    timeline = kwargs.get("timeline")
    rhythm_grid = kwargs.get("rhythm_grid")

    # Deterministic RNG is required for any probabilistic drum logic.
    # The orchestrator is responsible for creating per-section RNGs and passing
    # them into engines.
    rng = (
        kwargs.get("rng")
        or kwargs.get("section_rng")
        or kwargs.get("section_random")
        or kwargs.get("random")
    )
    if rng is None:
        raise TypeError(
            "drums.render_into_timeline requires a deterministic RNG. "
            "Expected kwarg 'rng' (provided by orchestrate/render.py)."
        )

    logger = kwargs.get("logger")
    transition_context = kwargs.get("transition_context")

    section_start_beat = float(kwargs.get("section_start_beat", 0.0))

    # Meter / duration
    beats_per_bar = float(_get_attr_or_key(rhythm_grid, "beats_per_bar", 4.0))
    total_beats = float(_get_attr_or_key(rhythm_grid, "total_beats", 0.0))

    # Internal step grid: 4 steps per quarter-note beat (one 16th note per
    # step, step duration 0.25 beats). 16 steps in 4/4, 12 in 3/4 (and 6/8,
    # which Meter.beats_per_bar normalizes to 3.0 quarter beats per bar).
    steps_per_bar = steps_per_bar_for_meter(beats_per_bar)

    # Section metadata
    section_type = str(_get_attr_or_key(section, "type", "verse"))
    section_id = str(_get_attr_or_key(section, "id", section_type))
    instrument_name = str(kwargs.get("instrument_name", "drums"))
    intensity = float(_get_attr_or_key(section, "intensity", 0.5))

    # Create instrument-specific RNG from section RNG.
    # This ensures each instrument in the section gets an independent RNG stream,
    # following the deterministic RNG hierarchy: section → instrument → voice → event
    instrument_rng = make_instrument_rng(rng, instrument_name)

    # Use instrument_rng for all instrument-level decisions from here forward.
    # The original section rng is no longer used to avoid coupling between instruments.
    rng = instrument_rng

    # Section intent: bridge/break contrast patterns (Phase 15).
    # Defines specific orchestration feels for bridges and breaks.
    # Values: "drop", "half_time", "build", "stomp", "open", or None (default)
    section_intent = _get_attr_or_key(section, "intent", None)
    if section_intent is not None:
        section_intent = str(section_intent).strip().lower()
        if section_intent not in ("drop", "half_time", "build", "stomp", "open"):
            if logger is not None:
                logger.warning(
                    "Section '%s': unknown intent '%s', ignoring (valid: drop, half_time, build, stomp, open)",
                    section_id,
                    section_intent,
                )
            section_intent = None
        else:
            # Always log intent when present (INFO level)
            import logging
            log = logger if logger is not None else logging.getLogger("produzre.drums")
            log.info("Section '%s': applying intent='%s'", section_id, section_intent)

    energy = resolve_section_energy(_get_attr_or_key(section, "energy", None), section_type)

    # Per-instrument merged config (preferred) or instrument under section.instruments["drums"].
    inst = kwargs.get("instrument")
    if inst is None:
        insts = _get_attr_or_key(section, "instruments", {})
        inst = _get_mapping(insts).get("drums")

    inst_m = _get_mapping(inst)
    persona = str(inst_m.get("persona") or "tight")

    # Params may come from either a plain mapping (inst["params"]) or an
    # InstrumentConfig dataclass field (inst.params). Some parsers also stash
    # unknown YAML keys under `extra`, so we additionally merge `extra.params`
    # on top (section overrides win).
    params = inst_m.get("params")
    if params is None and hasattr(inst, "params"):
        params = getattr(inst, "params")
    params_m = dict(_get_mapping(params))

    # Track which params_m keys were explicitly set by the user (vs sourced
    # from a persona). Recipes sit between them (persona < recipe < user), so
    # the recipe merge below must know which keys it may override.
    _user_set_keys: set = set(params_m)
    _persona_sourced_keys: set = set()

    # Inherit global/default instrument params when orchestration passes only
    # section overrides. Global effective defaults may be stored on cfg under
    # `_effective`.
    eff = _get_attr_or_key(cfg, "_effective", None)
    eff_m = _get_mapping(eff)
    eff_insts = _get_mapping(eff_m.get("instruments"))
    eff_drums = _get_mapping(eff_insts.get("drums"))
    # Voice-level params (optional). We treat voices as a shallow map like:
    #   voices:
    #     snare:
    #       params: { ghost_rate: 0.35 }
    # Config parsers may also stash unknown YAML keys under `extra`, so we also
    # read voices from `extra.voices`.
    voices_m: dict[str, Any] = {}

    def _merge_voice_entry(existing: Any, incoming: Any) -> dict[str, Any]:
        """Merge a single voice mapping (e.g., snare/hats) with nested concept blocks."""
        ex = dict(_get_mapping(existing))
        inc = dict(_get_mapping(incoming))

        # Merge nested dicts (params and all concept blocks).
        # This ensures section-level config properly combines with instrument-level config.
        concept_blocks = ("params", "syncopation", "double", "ghosts", "articulation", "pattern", "open", "opens", "pedal", "accents", "velocity", "groove", "fills")
        for key in concept_blocks:
            ex_val = _get_mapping(ex.get(key))
            inc_val = _get_mapping(inc.get(key))
            if ex_val or inc_val:
                ex[key] = {**dict(ex_val), **dict(inc_val)}

        # Merge any other keys at top-level (incoming wins).
        for k, v in inc.items():
            if k in concept_blocks:
                continue
            ex[k] = v
        return ex

    def _merge_voices_map(incoming_map: Any) -> None:
        vmap = _get_mapping(incoming_map)
        if not vmap:
            return
        for voice_name, voice_cfg in vmap.items():
            if voice_name in voices_m:
                voices_m[voice_name] = _merge_voice_entry(voices_m.get(voice_name), voice_cfg)
            else:
                voices_m[voice_name] = dict(_get_mapping(voice_cfg))

    def _merge_voices_from(mapping_like: Any) -> None:
        m = _get_mapping(mapping_like)
        if not m:
            return
        _merge_voices_map(m.get("voices"))
        _merge_voices_map(_get_mapping(m.get("extra")).get("voices"))

    # Global defaults first.
    _merge_voices_from(eff_drums)

    eff_params = _get_mapping(eff_drums.get("params"))
    if eff_params:
        # Global defaults first, then per-section params override.
        params_m = {**dict(eff_params), **params_m}
        _eff_persona_keys = set(eff_drums.get("persona_keys") or [])
        _persona_sourced_keys |= _eff_persona_keys & set(eff_params)
        # Global instrument params not tagged as persona-sourced are user-set.
        _user_set_keys |= set(eff_params) - _eff_persona_keys

    # Then per-section instrument config.
    _merge_voices_from(inst_m)

    extra = inst_m.get("extra")
    if extra is None and hasattr(inst, "extra"):
        extra = getattr(inst, "extra")
    extra_m = _get_mapping(extra)

    # Config loaders may double-nest extra content under extra.extra.
    # Unwrap one level if needed.
    if "extra" in extra_m and not ("params" in extra_m or "voices" in extra_m):
        extra_m = _get_mapping(extra_m.get("extra"))

    extra_params = extra_m.get("params")
    if extra_params is not None:
        _extra_params_m = _get_mapping(extra_params)
        params_m.update(_extra_params_m)
        _user_set_keys |= set(_extra_params_m)
        _persona_sourced_keys -= set(_extra_params_m)

    # Section-level voice overrides may be stored under extra.voices.
    extra_voices = extra_m.get("voices")
    if extra_voices is not None:
        _merge_voices_map(extra_voices)

    # Also support shorthand where params are placed at top level of the
    # instrument block (section `drums: {params: {...}}` is folded into
    # `extra` by the config parser, so these keys arrive via extra_m).
    # Persona-sourced extra keys (tagged `_persona_keys` by the orchestrator
    # merge) are NOT user overrides and stay recipe-overridable.
    _extra_persona_keys = set(_get_mapping(extra_m).get("_persona_keys") or [])
    for k in (
        "fill_rate",
        "fill_chatter",
        "swing",
        "swing_16th",
        "timing_jitter_ms",
        "push_pull",
        "velocity_humanize",
    ):
        if k in inst_m:
            params_m[k] = inst_m[k]
            _user_set_keys.add(k)
            _persona_sourced_keys.discard(k)
        elif hasattr(inst, "extra") and k in extra_m:
            params_m[k] = extra_m[k]
            if k in _extra_persona_keys:
                _persona_sourced_keys.add(k)
            else:
                _user_set_keys.add(k)
                _persona_sourced_keys.discard(k)

    # Persona/params (conservative defaults)
    accent_strength = float(params_m.get("accent_strength", 0.1))
    hat_density = float(params_m.get("hat_density", 1.0))
    kick_density = float(params_m.get("kick_density", 1.0))
    snare_density = float(params_m.get("snare_density", 1.0))

    # Hats voice overrides (optional).
    # Musician-friendly concept blocks:
    #   voices.hats.pattern: { rate: 1.0, placements: [1, 2, 3, 4] }
    #   voices.hats.open: { rate: 0.3, placements: ["4&"] }
    #   voices.hats.pedal: { rate: 0.25, placements: [4] }
    #   voices.hats.accents: { rate: 0.4, placements: ["2&", "4&"], boost: 14, bias: -10 }
    #   voices.hats.velocity: { bias: -10 }
    hats_voice = _get_mapping(voices_m.get("hats"))
    hats_voice_params = hats_voice.get("params")

    # Allow shorthand voices.hats.density / voices.hats.open_rate (legacy)
    if hats_voice_params is None and (
        "density" in hats_voice
        or "open_rate" in hats_voice
        or "open_hat_rate" in hats_voice
        or "pedal_rate" in hats_voice
        or "accent_rate" in hats_voice
    ):
        hats_voice_params = {
            "density": hats_voice.get("density"),
            "open_rate": hats_voice.get("open_rate", hats_voice.get("open_hat_rate")),
            "pedal_rate": hats_voice.get("pedal_rate"),
            "accent_rate": hats_voice.get("accent_rate"),
        }
    hats_voice_params_m = _get_mapping(hats_voice_params)

    # Musician-friendly concept blocks (new structure)
    # Pattern (density)
    hats_pattern_m = _get_mapping(hats_voice.get("pattern"))
    if hats_pattern_m.get("rate") is not None:
        hats_voice_params_m = {**dict(hats_voice_params_m), "density": hats_pattern_m.get("rate")}
    if hats_pattern_m.get("placements") is not None:
        hats_voice_params_m = {**dict(hats_voice_params_m), "pattern_placements": hats_pattern_m.get("placements")}

    # Open hats
    hats_open_m = _get_mapping(hats_voice.get("open") or hats_voice.get("opens"))
    if hats_open_m.get("rate") is not None:
        hats_voice_params_m = {**dict(hats_voice_params_m), "open_rate": hats_open_m.get("rate")}
    if hats_open_m.get("placements") is not None:
        hats_voice_params_m = {**dict(hats_voice_params_m), "open_placements": hats_open_m.get("placements")}

    # Pedal hats
    hats_pedal_m = _get_mapping(hats_voice.get("pedal"))
    if hats_pedal_m.get("rate") is not None:
        hats_voice_params_m = {**dict(hats_voice_params_m), "pedal_rate": hats_pedal_m.get("rate")}
    if hats_pedal_m.get("placements") is not None:
        hats_voice_params_m = {**dict(hats_voice_params_m), "pedal_placements": hats_pedal_m.get("placements")}

    # Accents
    hats_accents_m = _get_mapping(hats_voice.get("accents"))
    if hats_accents_m.get("rate") is not None:
        hats_voice_params_m = {**dict(hats_voice_params_m), "accent_rate": hats_accents_m.get("rate")}
    if hats_accents_m.get("placements") is not None:
        hats_voice_params_m = {**dict(hats_voice_params_m), "accent_placements": hats_accents_m.get("placements")}
    if hats_accents_m.get("boost") is not None:
        hats_voice_params_m = {**dict(hats_voice_params_m), "accent_boost": hats_accents_m.get("boost")}
    if hats_accents_m.get("bias") is not None:
        hats_voice_params_m = {**dict(hats_voice_params_m), "accent_bias": hats_accents_m.get("bias")}

    # Velocity
    hats_velocity_m = _get_mapping(hats_voice.get("velocity"))
    if hats_velocity_m.get("bias") is not None:
        hats_voice_params_m = {**dict(hats_voice_params_m), "velocity_bias": hats_velocity_m.get("bias")}

    # Extract final values
    hats_density_raw = hats_voice_params_m.get("density", None)
    hats_density = None if hats_density_raw is None else float(hats_density_raw)

    hats_open_rate_raw = hats_voice_params_m.get("open_rate", hats_voice_params_m.get("open_hat_rate", None))
    hats_open_rate = None if hats_open_rate_raw is None else float(hats_open_rate_raw)

    hats_pedal_rate_raw = hats_voice_params_m.get("pedal_rate", None)
    hats_pedal_rate = None if hats_pedal_rate_raw is None else float(hats_pedal_rate_raw)

    hats_accent_rate_raw = hats_voice_params_m.get("accent_rate", None)
    hats_accent_rate = None if hats_accent_rate_raw is None else float(hats_accent_rate_raw)

    # Kick voice overrides (optional).
    # Musician-friendly concept blocks:
    #   voices.kick.syncopation: { rate: 0.5, placements: ["1&", "3&"] }
    #   voices.kick.double: { rate: 0.3, placements: ["4e", "4&"] }
    kick_voice = _get_mapping(voices_m.get("kick"))
    kick_voice_params = kick_voice.get("params")
    kick_voice_params_m = _get_mapping(kick_voice_params)

    # Syncopation (extra kicks)
    kick_syncopation_m = _get_mapping(kick_voice.get("syncopation"))
    if kick_syncopation_m.get("rate") is not None:
        kick_voice_params_m = {**dict(kick_voice_params_m), "syncopation_rate": kick_syncopation_m.get("rate")}
    if kick_syncopation_m.get("placements") is not None:
        kick_voice_params_m = {**dict(kick_voice_params_m), "syncopation_placements": kick_syncopation_m.get("placements")}

    # Double-kick
    kick_double_m = _get_mapping(kick_voice.get("double"))
    if kick_double_m.get("rate") is not None:
        kick_voice_params_m = {**dict(kick_voice_params_m), "double_kick_rate": kick_double_m.get("rate")}
    if kick_double_m.get("placements") is not None:
        kick_voice_params_m = {**dict(kick_voice_params_m), "double_kick_placements": kick_double_m.get("placements")}

    # Extract final values
    kick_syncopation_rate_raw = kick_voice_params_m.get("syncopation_rate", None)
    kick_syncopation_rate = None if kick_syncopation_rate_raw is None else float(kick_syncopation_rate_raw)

    kick_double_kick_rate_raw = kick_voice_params_m.get("double_kick_rate", None)
    kick_double_kick_rate = None if kick_double_kick_rate_raw is None else float(kick_double_kick_rate_raw)

    # Apply energy-based orchestration defaults (only if not explicitly set by user).
    # Energy drives arrangement-level contrast: verse (low) vs chorus (high) vs bridge (mid).
    # Low energy: closed hats, minimal crashes, sparse kicks
    # High energy: ride/crash, more accents, syncopated kicks, doubles
    if hats_open_rate is None:
        # Map energy to open hat probability
        if energy <= 0.4:
            hats_open_rate = 0.1  # Low energy: mostly closed
        elif energy >= 0.7:
            hats_open_rate = 0.35  # High energy: frequent opens
        else:
            hats_open_rate = 0.2  # Mid energy: moderate

    if hats_accent_rate is None:
        # Map energy to accent frequency
        if energy <= 0.4:
            hats_accent_rate = 0.2  # Low energy: subtle accents
        elif energy >= 0.7:
            hats_accent_rate = 0.5  # High energy: frequent accents
        else:
            hats_accent_rate = 0.35  # Mid energy: moderate

    if kick_syncopation_rate is None:
        # Map energy to kick syncopation
        if energy <= 0.4:
            kick_syncopation_rate = 0.1  # Low energy: sparse syncopation
        elif energy >= 0.7:
            kick_syncopation_rate = 0.35  # High energy: active syncopation
        else:
            kick_syncopation_rate = 0.2  # Mid energy: moderate

    if kick_double_kick_rate is None:
        # Map energy to double kick patterns
        if energy <= 0.4:
            kick_double_kick_rate = 0.0  # Low energy: no doubles
        elif energy >= 0.7:
            kick_double_kick_rate = 0.25  # High energy: occasional doubles
        else:
            kick_double_kick_rate = 0.1  # Mid energy: rare doubles

    # Ghost notes (snare) – optional overrides.
    # Precedence (highest -> lowest):
    #   voices.snare.params.ghost_rate (section override) -> params.ghost_rate -> template.ghost_rate
    snare_voice = _get_mapping(voices_m.get("snare"))
    snare_voice_params = snare_voice.get("params")

    # Allow shorthand voices.snare.ghost_rate / voices.snare.ghost_steps
    if snare_voice_params is None and (
        "ghost_rate" in snare_voice or "ghost_steps" in snare_voice
    ):
        snare_voice_params = {
            "ghost_rate": snare_voice.get("ghost_rate"),
            "ghost_steps": snare_voice.get("ghost_steps"),
        }

    snare_voice_params_m = _get_mapping(snare_voice_params)

    # Musician-friendly alias: voices.snare.ghosts
    # Example:
    #   voices:
    #     snare:
    #       ghosts:
    #         rate: 0.2
    #         placements: ["2&", "4&"]
    #         velocity_bias: -10
    snare_ghosts_m = _get_mapping(snare_voice.get("ghosts"))
    if snare_ghosts_m:
        # Merge into params view (ghosts wins).
        if snare_ghosts_m.get("rate") is not None:
            snare_voice_params_m = {**dict(snare_voice_params_m), "ghost_rate": snare_ghosts_m.get("rate")}
        if snare_ghosts_m.get("placements") is not None:
            snare_voice_params_m = {**dict(snare_voice_params_m), "ghost_placements": snare_ghosts_m.get("placements")}
        if snare_ghosts_m.get("subdiv") is not None:
            snare_voice_params_m = {**dict(snare_voice_params_m), "ghost_subdiv": snare_ghosts_m.get("subdiv")}
        if snare_ghosts_m.get("velocity_bias") is not None:
            snare_voice_params_m = {**dict(snare_voice_params_m), "ghost_velocity_bias": snare_ghosts_m.get("velocity_bias")}

    # Snare articulation: voices.snare.articulation
    # Example:
    #   voices:
    #     snare:
    #       articulation: { default: rimshot }
    snare_articulation_m = _get_mapping(snare_voice.get("articulation"))
    snare_articulation = "normal"  # default
    if snare_articulation_m.get("default") is not None:
        snare_articulation = str(snare_articulation_m.get("default")).strip().lower()

    ghost_rate_raw = snare_voice_params_m.get("ghost_rate", params_m.get("ghost_rate", None))
    ghost_rate = None if ghost_rate_raw is None else float(ghost_rate_raw)

    # Prefer voice-specific ghost steps, then placements, then fall back to global params.
    ghost_steps_src = "template"
    ghost_steps_raw = snare_voice_params_m.get("ghost_steps", None)
    ghost_placements_raw = snare_voice_params_m.get("ghost_placements", None)
    ghost_subdiv_raw = snare_voice_params_m.get("ghost_subdiv", None)

    if ghost_steps_raw is not None:
        ghost_steps_src = "snare"
    elif ghost_placements_raw is not None:
        ghost_steps_src = "snare_placements"
        # Use the engine's internal meter-derived step grid by default
        # (16 in 4/4, 12 in 3/4), unless overridden via ghost_subdiv.
        try:
            subdiv = int(ghost_subdiv_raw) if ghost_subdiv_raw is not None else steps_per_bar
        except Exception:
            subdiv = steps_per_bar
        ghost_grid_spb = int(subdiv) if subdiv > 0 else steps_per_bar
        ghost_steps_raw = _ghost_placements_to_steps(
            ghost_placements_raw,
            beats_per_bar=float(beats_per_bar),
            steps_per_bar=ghost_grid_spb,
            logger=logger,
        )
    else:
        ghost_steps_raw = params_m.get("ghost_steps", None)
        if ghost_steps_raw is not None:
            ghost_steps_src = "global"

    # Allow YAML to specify a list of step indices; if empty list is provided,
    # patterns.py will infer sensible defaults near backbeats when ghost_rate > 0.
    ghost_steps = None
    if ghost_steps_raw is not None:
        if isinstance(ghost_steps_raw, (list, tuple)):
            ghost_steps = [int(x) for x in ghost_steps_raw]
        else:
            # Be forgiving: single scalar -> one-step list
            ghost_steps = [int(ghost_steps_raw)]

    # If no explicit override was provided, pass None so patterns.py can use
    # template settings and/or infer defaults.
    if ghost_steps is None:
        ghost_steps_src = "template"

    # Extract ghost velocity bias
    ghost_velocity_bias_raw = snare_voice_params_m.get("ghost_velocity_bias", None)
    ghost_velocity_bias = None if ghost_velocity_bias_raw is None else int(ghost_velocity_bias_raw)

    # Tom voice overrides (optional).
    # Musician-friendly concept blocks:
    #   voices.toms.groove: { rate: 0.2 }
    #   voices.toms.fills: { rate: 0.8 }
    toms_voice = _get_mapping(voices_m.get("toms"))
    toms_voice_params = toms_voice.get("params")
    toms_voice_params_m = _get_mapping(toms_voice_params)

    # Groove toms
    toms_groove_m = _get_mapping(toms_voice.get("groove"))
    if toms_groove_m.get("rate") is not None:
        toms_voice_params_m = {**dict(toms_voice_params_m), "groove_rate": toms_groove_m.get("rate")}

    # Fill toms
    toms_fills_m = _get_mapping(toms_voice.get("fills"))
    if toms_fills_m.get("rate") is not None:
        toms_voice_params_m = {**dict(toms_voice_params_m), "fills_rate": toms_fills_m.get("rate")}

    # Extract final values
    groove_tom_rate_raw = toms_voice_params_m.get("groove_rate", None)
    groove_tom_rate = 0.0 if groove_tom_rate_raw is None else float(groove_tom_rate_raw)

    fill_tom_rate_raw = toms_voice_params_m.get("fills_rate", None)
    fill_tom_rate = 0.0 if fill_tom_rate_raw is None else float(fill_tom_rate_raw)

    # Cymbal voice overrides (optional).
    # Musician-friendly concept blocks:
    #   voices.crash: { rate: 0.8, placements: [0] }
    #   voices.ride: { bell_rate: 0.2 }
    #   voices.cymbals: { splash_rate: 0.1, china_rate: 0.05 }
    cymbals_voice = _get_mapping(voices_m.get("cymbals"))
    crash_voice = _get_mapping(voices_m.get("crash"))
    ride_voice = _get_mapping(voices_m.get("ride"))

    # Crash overrides.
    # If the user did not set an explicit rate, keep None so the pattern layer
    # falls back to the recipe/template's crash_phrase_end_rate instead of an
    # engine-side energy default permanently overriding trained values.
    # (Hardcoded templates already derive crash_phrase_end_rate from intensity.)
    crash_rate_raw = crash_voice.get("rate", None)
    crash_rate = None if crash_rate_raw is None else float(crash_rate_raw)

    crash_placements_raw = crash_voice.get("placements", None)
    crash_placements = None
    if crash_placements_raw is not None:
        crash_placements = _ghost_placements_to_steps(
            crash_placements_raw,
            beats_per_bar=beats_per_bar,
            steps_per_bar=steps_per_bar,
            logger=logger,
        )

    # Ride bell
    ride_bell_rate_raw = ride_voice.get("bell_rate", cymbals_voice.get("ride_bell_rate", None))
    ride_bell_rate = 0.0 if ride_bell_rate_raw is None else float(ride_bell_rate_raw)

    # Splash and china
    splash_rate_raw = cymbals_voice.get("splash_rate", None)
    splash_rate = 0.0 if splash_rate_raw is None else float(splash_rate_raw)

    china_rate_raw = cymbals_voice.get("china_rate", None)
    china_rate = 0.0 if china_rate_raw is None else float(china_rate_raw)

    # Fills: phrase-end fills by default, with optional "chatter".
    fill_rate = float(params_m.get("fill_rate", 0.25))
    fill_chatter = float(params_m.get("fill_chatter", 0.0))
    fill_length_raw = params_m.get("fill_length", "medium")
    fill_length = str(fill_length_raw).strip().lower() if fill_length_raw else "medium"

    # Transitions: section boundary effects (pickups, downbeat punctuation).
    pickup_rate = float(params_m.get("pickup_rate", 0.7))
    downbeat_rate = float(params_m.get("downbeat_rate", 0.8))

    # Phrasing: musical phrase boundaries for fill placement.
    # Default phrase length varies by meter: 4 bars in 4/4, 2-4 bars in 6/8.
    phrase_len_bars_raw = params_m.get("phrase_len_bars")
    if phrase_len_bars_raw is None:
        # Auto-detect based on meter
        if abs(beats_per_bar - 6.0) < 0.1 or abs(beats_per_bar - 3.0) < 0.1:
            phrase_len_bars = 2  # 6/8 or 3/4: shorter phrases
        else:
            phrase_len_bars = 4  # 4/4: standard 4-bar phrases
    else:
        phrase_len_bars = int(phrase_len_bars_raw)
        phrase_len_bars = max(1, phrase_len_bars)  # At least 1 bar

    # Emphasis for final phrase (section end) - makes last phrase fill bigger/longer
    phrase_end_emphasis = float(params_m.get("phrase_end_emphasis", 1.5))

    # Performance ornaments: realism beyond notes (chokes, flams, drags).
    choke_rate = float(params_m.get("choke_rate", 0.0))
    flam_rate = float(params_m.get("flam_rate", 0.0))
    drag_rate = float(params_m.get("drag_rate", 0.0))

    # Apply intent-based ornament modulation (Phase 15 + Phase 16 integration)
    # Ornament rates respond to section intent for cohesive feel
    if section_intent:
        if section_intent == "drop":
            # Drop: Minimal ornaments for sparse, minimal feel
            choke_rate *= 0.3
            flam_rate *= 0.2
            drag_rate *= 0.1
        elif section_intent == "build":
            # Build: Increase flams/drags for building intensity
            flam_rate *= 1.3
            drag_rate *= 1.5
        elif section_intent == "stomp":
            # Stomp: Increase all ornaments for aggressive feel
            choke_rate *= 1.5
            flam_rate *= 1.4
            drag_rate *= 1.2
        elif section_intent == "half_time":
            # Half-time: Moderate reduction for deliberate feel
            choke_rate *= 0.7
            flam_rate *= 0.8
        elif section_intent == "open":
            # Open: Reduce chokes to let cymbals ring
            choke_rate *= 0.3

    # --- Groove recipe resolution ---
    # Recipes provide genre-aware groove defaults. They are resolved AFTER
    # persona/params merging so user overrides always win.
    _recipe_groove = None
    _all_recipes: dict = {}
    if hasattr(cfg, "raw") and isinstance(getattr(cfg, "raw", None), dict):
        _all_recipes = cfg.raw.get("_recipes", {}).get("drums", {})

    if _all_recipes:
        from ...config.recipes import resolve_recipe_name as _resolve_recipe

        _song = _get_attr_or_key(cfg, "song", None)
        _song_genre = _get_attr_or_key(_song, "genre", None) if _song else None
        _bpm = float(_get_attr_or_key(_song, "bpm", 120.0)) if _song else 120.0
        _meter = str(_get_attr_or_key(_song, "meter", "4/4")) if _song else "4/4"

        # Read explicit recipe: from section instrument, then global instrument.
        _section_recipe = inst_m.get("recipe")
        if _section_recipe is None and hasattr(inst, "recipe"):
            _section_recipe = getattr(inst, "recipe", None)
        _global_inst_recipe = None
        _inst_genre = None
        if isinstance(cfg.raw.get("instruments"), dict):
            _gi = cfg.raw["instruments"].get("drums")
            if isinstance(_gi, dict):
                _global_inst_recipe = _gi.get("recipe")
                _inst_genre = _gi.get("genre")

        # Per-instrument genre: section → global instrument → song
        _sect_genre = inst_m.get("genre")
        if _sect_genre is None and hasattr(inst, "genre"):
            _sect_genre = getattr(inst, "genre", None)
        if _sect_genre is not None:
            _inst_genre = _sect_genre
        _genre = _inst_genre if _inst_genre is not None else _song_genre

        _recipe_name = _resolve_recipe(
            instrument="drums",
            genre=_genre,
            section_type=section_type,
            intensity=intensity,
            bpm=_bpm,
            time_signature=_meter,
            instrument_recipe=_global_inst_recipe,
            section_recipe=_section_recipe,
            recipes=_all_recipes,
        )

        if _recipe_name and _recipe_name in _all_recipes:
            _recipe = _all_recipes[_recipe_name]
            _recipe_groove = _recipe.get("groove") or None

            # Merge recipe params honoring persona < recipe < user: keys the
            # user explicitly set always win, but persona-sourced defaults
            # (e.g. swing: 0.0 from the default 'tight' persona) yield to the
            # recipe (see config.recipes.merge_recipe_params).
            _rp = _recipe.get("params", {})
            if _rp:
                from ...config.recipes import merge_recipe_params as _merge_recipe_params

                _tagged = dict(params_m)
                _pk = sorted(
                    k for k in params_m
                    if k in _persona_sourced_keys and k not in _user_set_keys
                )
                if _pk:
                    _tagged["_persona_keys"] = _pk
                params_m = _merge_recipe_params(_tagged, _rp)
                params_m.pop("_persona_keys", None)

            # Merge recipe voices UNDER existing voices_m.
            _rv = _recipe.get("voices", {})
            if _rv:
                _merge_voices_map(_rv)

            if logger:
                logger.info(
                    "Drums: using recipe '%s' (genre=%s, section=%s)",
                    _recipe_name, _genre, section_type,
                )

    # Build groove template: recipe groove overrides hardcoded templates.
    if _recipe_groove:
        from .groove import groove_template_from_recipe
        groove_id = f"recipe:{_recipe_name}"
        template = groove_template_from_recipe(_recipe_groove, beats_per_bar)
    else:
        groove_id = resolve_groove_id(
            section_type=section_type,
            intensity=intensity,
            params=params_m,
        )
        template = groove_template(
            groove_id,
            section_type=section_type,
            intensity=intensity,
            beats_per_bar=beats_per_bar,
        )

    # Standard GM drum pitches
    # Snare articulation: normal (38), rimshot (40), crossstick (37)
    snare_pitch = 38  # default
    if snare_articulation == "rimshot":
        snare_pitch = 40
    elif snare_articulation == "crossstick":
        snare_pitch = 37

    pitches = {
        "kick": 36,
        "snare": snare_pitch,
        "hat_closed": 42,
        "hat_open": 46,
        "hat_pedal": 44,
        "ride": 51,
        "ride_bell": 53,
        "crash": 49,
        "splash": 55,
        "china": 52,
        "tom_high": 50,
        "tom_mid": 47,
        "tom_low": 45,
    }

    # Base velocity
    base_velocity = 72 if persona == "tight" else 68

    # Apply kick voice overrides and energy-based orchestration to template
    template_updates = {}

    # Kick voice overrides
    if kick_syncopation_rate is not None:
        template_updates["kick_extra_rate"] = float(kick_syncopation_rate)
    if kick_double_kick_rate is not None:
        template_updates["double_kick_rate"] = float(kick_double_kick_rate)

    # Energy-based use_ride override (only if not already set by groove)
    # High energy sections (chorus, solo) should use ride cymbal instead of closed hats
    # unless the template explicitly sets use_ride already
    if energy >= 0.7 and not template.use_ride:
        # High energy: switch to ride cymbal for "opening up" the sound
        template_updates["use_ride"] = True
    elif energy <= 0.4 and template.use_ride:
        # Low energy: force closed hats even if template suggests ride
        template_updates["use_ride"] = False

    # Intent-based orchestration overrides (Phase 15: Bridge + Break Logic)
    # These create intentional contrast feels for bridges and breaks
    if section_intent == "drop":
        # Drop: Reduce density, minimal hats, simple kick/snare
        # Creates space and contrast, often used at bridge starts
        template_updates["kick_extra_rate"] = 0.0  # No syncopated kicks
        template_updates["double_kick_rate"] = 0.0  # No double kicks
        template_updates["use_ride"] = False  # Closed hats only
        # Reduce hat density (only when not explicitly set by user config)
        if hats_density_raw is None:
            hats_density = 0.5  # Sparse hats
        if hats_open_rate_raw is None:
            hats_open_rate = 0.0  # No open hats
    elif section_intent == "half_time":
        # Half-time: lone snare at the bar midpoint (beat 3 in 4/4), slower feel.
        # The midpoint step is meter-derived: spb//2 == step 8 on the 16-step
        # 4/4 grid, step 6 on the 12-step 3/4 grid, etc.
        template_updates["snare_backbeat_steps"] = (steps_per_bar // 2,)
        template_updates["half_time"] = True  # Mark as half-time feel
        template_updates["kick_extra_rate"] = 0.1  # Minimal syncopation
        template_updates["double_kick_rate"] = 0.0  # No double kicks
    elif section_intent == "build":
        # Build: Increase density over time, tom builds, crescendo
        # This is handled via fill_rate and fill configuration
        fill_rate = 1.0  # Fill at every phrase end
        if "fill_length" not in params_m:
            params_m["fill_length"] = "long"  # Longer fills for build effect
            fill_length = "long"  # Update local (already extracted above)
        template_updates["kick_extra_rate"] = 0.3  # More syncopation for energy
    elif section_intent == "stomp":
        # Stomp: Heavy kick pattern, minimal cymbals, powerful backbeat
        template_updates["kick_extra_rate"] = 0.4  # More kicks for stomp feel
        template_updates["use_ride"] = False  # Closed hats only
        if hats_density_raw is None:
            hats_density = 1.0  # Steady hats for stomp pulse
        if hats_open_rate_raw is None:
            hats_open_rate = 0.0  # No open hats
        # Increase snare velocity for powerful backbeat (will use base_velocity boost)
        base_velocity = max(base_velocity, 80)
    elif section_intent == "open":
        # Open: Ride cymbal instead of hats, spacious feel
        template_updates["use_ride"] = True  # Switch to ride
        template_updates["kick_extra_rate"] = 0.15  # Moderate syncopation
        template_updates["double_kick_rate"] = 0.0  # No double kicks for spacious feel
        if hats_density_raw is None:
            hats_density = 0.75  # Slightly reduced ride density

    if template_updates:
        from dataclasses import replace
        if logger and section_intent:
            logger.debug(
                "Section '%s': applying intent '%s' with updates: %s",
                section_id,
                section_intent,
                {k: v for k, v in template_updates.items()},
            )
        template = replace(template, **template_updates)

    # Augment transition_context with transition params if context exists.
    effective_transition_context = None
    if transition_context is not None:
        effective_transition_context = {
            **transition_context,
            "pickup_rate": pickup_rate,
            "downbeat_rate": downbeat_rate,
        }

    events: list[DrumEvent] = events_for_section_from_template(
        template=template,
        total_beats=total_beats,
        beats_per_bar=beats_per_bar,
        rng=rng,
        pitches=pitches,
        base_velocity=base_velocity,
        accent_strength=accent_strength,
        hat_density=hat_density,
        steps_per_bar=steps_per_bar,
        kick_density=kick_density,
        snare_density=snare_density,
        ghost_rate=ghost_rate,
        ghost_steps=ghost_steps,
        ghost_velocity_bias=ghost_velocity_bias,
        hats_density=hats_density,
        hats_open_rate=hats_open_rate,
        hats_pedal_rate=hats_pedal_rate,
        hats_accent_rate=hats_accent_rate,
        groove_tom_rate=groove_tom_rate,
        fill_tom_rate=fill_tom_rate,
        crash_rate=crash_rate,
        crash_placements=crash_placements,
        ride_bell_rate=ride_bell_rate,
        splash_rate=splash_rate,
        china_rate=china_rate,
        transition_context=effective_transition_context,
    )

    # Add fills before humanization so fills are humanized too.
    # Phase S3: Boost fill rate at section transitions (Rule 3: Fill at transitions)
    plan = kwargs.get("plan")
    if plan is not None and fill_rate > 0.0:
        try:
            coordinator = EngineCoordinator(plan, logger=logger)
            # Calculate section length in bars
            section_bars = int(total_beats / beats_per_bar)
            # Check each bar to find if any are near the boundary
            is_at_boundary = False
            for bar_idx in range(section_bars):
                if coordinator.is_section_boundary(bar_idx, section.id, lead_in_bars=1):
                    is_at_boundary = True
                    break

            if is_at_boundary:
                # Boost fill probability at transitions (MIDI analysis: 80% at boundaries)
                transition_fill_prob = coordinator.get_fill_probability_for_transition(section.id)
                original_fill_rate = fill_rate
                fill_rate = max(fill_rate, transition_fill_prob)

                if logger and abs(fill_rate - original_fill_rate) > 0.01:
                    logger.debug(
                        f"[COORDINATION] Section '{section.id}' at boundary: "
                        f"fill_rate {original_fill_rate:.2f} -> {fill_rate:.2f}"
                    )
        except Exception as e:
            # Silently fail coordination to avoid breaking drum rendering
            if logger:
                logger.debug(f"[COORDINATION] Fill coordination failed: {e}")

    if fill_rate > 0.0 or fill_chatter > 0.0:
        # Split RNG streams so enabling chatter doesn't reshuffle phrase-end fills.
        rng_fill = _derive_rng(rng, "drums.fill")
        rng_chatter = _derive_rng(rng, "drums.chatter")

        events = add_fills(
            events=events,
            total_beats=total_beats,
            beats_per_bar=beats_per_bar,
            rng=rng,
            rng_fill=rng_fill,
            rng_chatter=rng_chatter,
            pitches=pitches,
            base_velocity=base_velocity,
            fill_rate=fill_rate,
            fill_chatter=fill_chatter,
            fill_length=fill_length,
            persona=persona,
            steps_per_bar=steps_per_bar,
            phrase_len_bars=phrase_len_bars,
            phrase_end_emphasis=phrase_end_emphasis,
            genre=str(_get_attr_or_key(_get_attr_or_key(cfg, "song", None), "genre", "") or ""),
        )

    # Add performance ornaments (chokes, flams, drags) before humanization.
    # Ornaments get humanized timing/velocity like all other events.
    if choke_rate > 0.0 or flam_rate > 0.0 or drag_rate > 0.0:
        rng_ornaments = _derive_rng(rng, "drums.ornaments")
        events = add_ornaments(
            events=events,
            rng=rng_ornaments,
            pitches=pitches,
            choke_rate=choke_rate,
            flam_rate=flam_rate,
            drag_rate=drag_rate,
            persona=persona,
            beats_per_bar=beats_per_bar,
        )

    song = _get_attr_or_key(cfg, "song")
    bpm = float(_get_attr_or_key(song, "bpm", 120.0))

    # Apply limb constraints (2 hands + 2 feet realism) before humanization
    constraints_m = _get_mapping(params_m.get("constraints"))
    constraints_enabled = bool(constraints_m.get("enabled", True))
    constraints_max_hand_hits = int(constraints_m.get("max_hand_hits", 2))
    constraints_max_foot_hits = int(constraints_m.get("max_foot_hits", 2))
    constraints_kick_density_limit = float(constraints_m.get("kick_density_hihat_pedal_limit", 0.6))
    constraints_fill_duck_hats = bool(constraints_m.get("fill_duck_hats", True))

    if constraints_enabled:
        from .constraints import apply_constraints

        events = apply_constraints(
            events=events,
            beats_per_bar=beats_per_bar,
            max_hand_hits=constraints_max_hand_hits,
            max_foot_hits=constraints_max_foot_hits,
            kick_density_hihat_pedal_limit=constraints_kick_density_limit,
            fill_duck_hats=constraints_fill_duck_hats,
            logger=logger,
        )

    # Humanization params (defaults are persona/tight-friendly).
    timing_jitter_ms = float(params_m.get("timing_jitter_ms", 0.0))
    swing = float(params_m.get("swing", 0.0))
    push_pull = float(params_m.get("push_pull", 0.0))
    velocity_humanize = float(params_m.get("velocity_humanize", 0.05))

    # Publish the resolved humanize params (persona < recipe < user merged)
    # so the orchestrator's shared groove clock (produzre.groove) can swing
    # the rest of the band to the same feel. Drums stay the reference clock.
    _groove_plan = kwargs.get("plan")
    if _groove_plan is not None:
        _groove_payload: dict = {
            "swing": swing,
            "timing_jitter_ms": timing_jitter_ms,
            "push_pull": push_pull,
            "velocity_humanize": velocity_humanize,
            "source": "drums.params",
        }
        _swing_16th_raw = params_m.get("swing_16th")
        if _swing_16th_raw is not None:
            try:
                _groove_payload["swing_16th"] = float(_swing_16th_raw)
            except (TypeError, ValueError):
                pass
        try:
            _groove_plan.set(f"groove.humanize.{section_id}", _groove_payload)
        except Exception:
            pass

    notes = humanize_events(
        events=events,
        section_start_beat=section_start_beat,
        beats_per_bar=beats_per_bar,
        bpm=bpm,
        timing_jitter_ms=timing_jitter_ms,
        swing=swing,
        push_pull=push_pull,
        velocity_humanize=velocity_humanize,
        rng=rng,
    )

    for start_beat, duration_beats, pitch, vel, kind in notes:
        timeline.add_note(
            start_beat=float(start_beat),
            duration_beats=float(duration_beats),
            pitch=int(pitch),
            velocity=int(vel),
            kind=kind,
        )

    if logger is not None:
        ghost_events = sum(1 for e in events if getattr(e, "kind", "") == "snare_ghost")
        effective_ghost_rate = float(template.ghost_rate) if ghost_rate is None else float(ghost_rate)
        used_snare_override = "ghost_rate" in snare_voice_params_m
        used_hats_override = (
            ("density" in hats_voice_params_m)
            or ("open_rate" in hats_voice_params_m)
            or ("open_hat_rate" in hats_voice_params_m)
            or ("pedal_rate" in hats_voice_params_m)
            or ("accent_rate" in hats_voice_params_m)
        )
        logger.debug(
            "Drums rendered: section=%s groove=%s persona=%s fill_rate=%.3f fill_chatter=%.3f ghost_rate=%.3f ghost_steps=%s ghost_steps_src=%s ghost_events=%d snare_override=%s hats_density=%s hats_open_rate=%s hats_pedal_rate=%s hats_accent_rate=%s hats_override=%s events=%d",
            str(_get_attr_or_key(section, "id", section_type)),
            groove_id,
            persona,
            float(fill_rate),
            float(fill_chatter),
            effective_ghost_rate,
            ghost_steps if ghost_steps is not None else "",
            ghost_steps_src,
            int(ghost_events),
            "yes" if used_snare_override else "no",
            "" if hats_density is None else f"{float(hats_density):.3f}",
            "" if hats_open_rate is None else f"{float(hats_open_rate):.3f}",
            "" if hats_pedal_rate is None else f"{float(hats_pedal_rate):.3f}",
            "" if hats_accent_rate is None else f"{float(hats_accent_rate):.3f}",
            "yes" if used_hats_override else "no",
            len(notes),
        )

    # Export rhythm features for cross-instrument coupling (bass, guitar).
    # Other instruments can read these features to lock into the drum groove.
    rhythm_features_map = kwargs.get("rhythm_features")
    if rhythm_features_map is not None:
        section_id = str(_get_attr_or_key(section, "id", section_type))
        features = extract_rhythm_features(
            events=events,
            total_beats=total_beats,
            beats_per_bar=beats_per_bar,
            pitches=pitches,
            section_id=section_id,
            instrument="drums",
        )
        rhythm_features_map["drums"] = features

        # Rule 2 + Rule 4: Write kick beats and accent beats to the plan so
        # bass and other instruments can read them via the coordinator.
        plan = kwargs.get("plan")
        if plan is not None:
            if features.strong_beats:
                plan.set(f"groove.kick_beats.{section_id}", sorted(features.strong_beats))
            if features.accent_beats:
                plan.set(f"groove.accent_beats.{section_id}", sorted(features.accent_beats))

        if logger is not None:
            logger.debug(
                "Drums rhythm features: section=%s strong_beats=%d accent_beats=%d fill_windows=%d syncopation_beats=%d",
                section_id,
                len(features.strong_beats),
                len(features.accent_beats),
                len(features.fill_windows),
                len(features.syncopation_beats),
            )
