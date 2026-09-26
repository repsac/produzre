from __future__ import annotations

"""Rendering phase for Produzre orchestration.

This module executes instrument engines against the precomputed build plan.

Responsibilities:
- Initialize one empty `InstrumentTimeline` per registered engine.
- Determine which instruments are actually used based on section declarations.
- For each section, call the appropriate engine to render notes into its
  timeline at the correct song-relative start beat.
- Sort timeline events after rendering to ensure deterministic MIDI output.

This layer does not write MIDI files. Exporting is handled by the export
subsystem once timelines are fully rendered.
"""

import logging
import random
from collections.abc import Mapping
from dataclasses import fields
from typing import Any, Optional, List

from ..model import RootConfig
from ..rng import make_instrument_rng, stable_seed_int
from ..timeline import InstrumentTimeline
from ..config.errors import ConfigError
from ..groove import apply_feel, effective_params_dict, resolve_groove_feel
from .negotiation import create_feedback_collector, EngineFeedback
from .ensemble import build_ensemble_section_plan
from ..melody import build_melody_guide


def _find_providers_for_requirement(cfg: RootConfig, requirement: str) -> list[str]:
    """Find all engines that provide a given requirement.

    Phase N3: Used to generate actionable error messages when dependencies are missing.

    Args:
        cfg: Root configuration containing engine registry.
        requirement: Requirement string to search for (e.g., "harmony.plan", "groove.cues").

    Returns:
        list[str]: Engine names that provide this requirement.
    """
    providers = []
    for engine_name, engine in cfg.engines.items():
        if requirement in engine.provides:
            providers.append(engine_name)
    return providers


def _validate_engine_dependencies(
    engine_name: str,
    engine,
    performance_plan: Optional[object],
    cfg: RootConfig,
    logger: logging.Logger,
) -> None:
    """Validate that all required dependencies are available before rendering.

    Phase N3: Checks that the performance plan contains all data required by
    an engine before execution. If dependencies are missing, raises a clear
    error with suggestions for which engines provide the missing data.

    Args:
        engine_name: Name of the engine to validate.
        engine: Engine object with requires/provides fields.
        performance_plan: Performance plan containing shared data.
        cfg: Root configuration for finding providers.
        logger: Logger for debug output.

    Raises:
        ConfigError: If required dependencies are missing from the performance plan.
    """
    if not engine.requires:
        # No dependencies, nothing to validate
        return

    if performance_plan is None:
        # No performance plan available - can't validate
        logger.debug(
            f"Engine '{engine_name}': no performance plan available, skipping dependency validation"
        )
        return

    missing_requirements = []
    for requirement in engine.requires:
        if not performance_plan.has(requirement):
            missing_requirements.append(requirement)

    if missing_requirements:
        # Build actionable error message with provider suggestions
        error_lines = [
            f"Engine '{engine_name}' has unsatisfied dependencies:",
        ]

        for req in missing_requirements:
            providers = _find_providers_for_requirement(cfg, req)
            if providers:
                providers_str = ", ".join(f"'{p}'" for p in providers)
                error_lines.append(
                    f"  - Missing '{req}' (provided by: {providers_str})"
                )
            else:
                error_lines.append(
                    f"  - Missing '{req}' (no known providers in engines.yml)"
                )

        error_lines.append("")
        error_lines.append("Possible solutions:")
        error_lines.append("  1. Ensure engines that provide these requirements run before this engine")
        error_lines.append("  2. Adjust engine priorities so providers run first")
        error_lines.append("  3. Enable any disabled engines that provide these requirements")

        raise ConfigError("\n".join(error_lines))


def _get_global_instrument_cfg(cfg: RootConfig, inst_name: str) -> Any:
    """Return the global/default InstrumentConfig for an instrument, if present.

    Different versions of the config model may store global instrument defaults
    either on `RootConfig` or under `cfg.song`. This helper keeps the render
    layer tolerant while the config model evolves.

    Phase B1+: Prioritizes `_effective.instruments` which contains merged persona params.

    Args:
        cfg: Parsed root config.
        inst_name: Instrument key (e.g. "drums").

    Returns:
        The global/default InstrumentConfig for the instrument, or None.
    """

    # Phase B1+: Load persona params from _effective.instruments (if any).
    effective_cfg = None
    if hasattr(cfg, "raw") and isinstance(cfg.raw, dict):
        effective = cfg.raw.get("_effective", {})
        if isinstance(effective, dict):
            effective_instruments = effective.get("instruments", {})
            if isinstance(effective_instruments, dict):
                effective_cfg = effective_instruments.get(inst_name)

    # Find the base InstrumentConfig from root/song level.
    base_cfg = None
    for attr in ("instruments", "instrument_defaults", "instrument_configs"):
        mapping = getattr(cfg, attr, None)
        if isinstance(mapping, dict):
            base_cfg = mapping.get(inst_name)
            if base_cfg is not None:
                break

    if base_cfg is None:
        song = getattr(cfg, "song", None)
        if song is not None:
            for attr in ("instruments", "instrument_defaults", "instrument_configs"):
                mapping = getattr(song, attr, None)
                if isinstance(mapping, dict):
                    base_cfg = mapping.get(inst_name)
                    if base_cfg is not None:
                        break

    if base_cfg is None and hasattr(cfg, "raw") and isinstance(cfg.raw, dict):
        # RootConfig has no parsed global-instruments field; recover the
        # top-level `instruments:` block (intensity, register, recipe, genre,
        # ...) from the raw YAML so global scalars aren't silently dropped.
        raw_instruments = cfg.raw.get("instruments")
        if isinstance(raw_instruments, dict):
            data = raw_instruments.get(inst_name)
            if isinstance(data, dict):
                from ..config.parse import _parse_instrument_config
                # `persona` is resolved by the loader into _effective; keep it
                # out of extra.
                data = {k: v for k, v in data.items() if k != "persona"}
                base_cfg = _parse_instrument_config(inst_name, data)

    if effective_cfg is None:
        return base_cfg

    persona_params = effective_cfg.get("params", {}) or {}
    # Keys whose value came from the persona (not the user). Recipes are
    # allowed to override these later (persona < recipe < user); see
    # produzre.config.recipes.merge_recipe_params.
    persona_keys = list(effective_cfg.get("persona_keys", []) or [])

    if base_cfg is not None and hasattr(base_cfg, "extra"):
        # Merge persona params into InstrumentConfig.extra (persona < user)
        if persona_params:
            existing_extra = base_cfg.extra if base_cfg.extra else {}
            if isinstance(existing_extra, dict):
                merged = {**persona_params, **existing_extra}
                remaining = [k for k in persona_keys if k not in existing_extra]
                if remaining:
                    merged["_persona_keys"] = remaining
                base_cfg = type(base_cfg)(
                    **{f.name: (merged if f.name == "extra" else getattr(base_cfg, f.name))
                       for f in fields(base_cfg)}
                )
        return base_cfg

    if base_cfg is None:
        # No InstrumentConfig: wrap persona params in one so engines get a
        # proper dataclass with .intensity / .extra.
        from ..model import InstrumentConfig
        extra = dict(persona_params)
        if persona_keys:
            extra["_persona_keys"] = list(persona_keys)
        return InstrumentConfig(extra=extra)

    return effective_cfg

def _merge_extra(base_extra: Any, override_extra: Any) -> Any:
    """Deep-merge two `extra` dicts (override keys win).

    Maintains the `_persona_keys` tag: a key explicitly set by the override
    is no longer persona-sourced, so recipes must not clobber it later.
    """
    if not isinstance(base_extra, dict) or not isinstance(override_extra, dict):
        return override_extra if override_extra else base_extra
    merged = {**base_extra, **override_extra}
    persona_keys = [
        k for k in (base_extra.get("_persona_keys") or [])
        if k not in override_extra
    ]
    if persona_keys:
        merged["_persona_keys"] = persona_keys
    else:
        merged.pop("_persona_keys", None)
    return merged


def _merge_instrument_config(base: Any, override: Any) -> Any:
    """Merge two InstrumentConfig dataclass instances.

    Semantics:
      - `override` wins when it explicitly sets a field to a non-None value.
      - `extra`/`params` are deep-merged key-by-key (override keys replace
        base keys); a section declaring `bass: {}` must NOT wipe global or
        persona params that live in the base `extra`.
      - If `base` is None, return `override`.
      - If `override` is None, return `base`.

    Phase B1+: Also handles when base is a dict (from _effective).

    This supports the intended contract:
      - If a section declares an instrument as `{}`, it inherits global defaults.
      - If a section provides `params`, only those keys override.
    """

    if base is None:
        return override
    if override is None:
        return base

    # Phase B1+: If base is a dict (from _effective), merge dicts directly
    if isinstance(base, dict) and not hasattr(base, "__dataclass_fields__"):
        # Base is a dict (from _effective.instruments)
        merged = dict(base)  # Start with base

        # Override can be dict or dataclass
        if isinstance(override, dict):
            # Both are dicts - simple merge (extra/params deep-merged below)
            for key, val in override.items():
                if val is not None and key not in ("extra", "params"):
                    merged[key] = val
            # Deep-merge params and extra
            base_params = base.get("params", {}) or {}
            override_params = override.get("params", {}) or {}
            merged["params"] = {**dict(base_params), **dict(override_params)}
            merged["extra"] = _merge_extra(
                base.get("extra", {}) or {}, override.get("extra", {}) or {}
            )
        else:
            # Override is dataclass - extract fields (extra deep-merged below)
            for f in fields(override):
                if f.name == "extra":
                    continue
                val = getattr(override, f.name)
                if val is not None:
                    merged[f.name] = val
            # Deep-merge params and extra
            base_params = base.get("params", {}) or {}
            override_params = getattr(override, "params", None) or {}
            merged["params"] = {**dict(base_params), **dict(override_params)}
            merged["extra"] = _merge_extra(
                base.get("extra", {}) or {}, getattr(override, "extra", None) or {}
            )

        return merged

    # Section overrides may be parsed as plain dicts. Normalize to a dict of field
    # names so we can merge into the dataclass shape.
    override_map: dict[str, Any] | None = None
    if isinstance(override, Mapping) and not hasattr(override, "__dataclass_fields__"):
        override_map = dict(override)

    # Start from base values.
    merged: dict[str, Any] = {}
    for f in fields(base):
        merged[f.name] = getattr(base, f.name)

    # Apply overrides (non-None) on top. `extra` is deep-merged, never
    # replaced: a section override like `bass: {}` (or one that only sets a
    # couple of keys) must not wipe global/persona params held in base.extra.
    base_extra = getattr(base, "extra", None) or {}
    if override_map is None:
        for f in fields(override):
            if f.name == "extra":
                continue
            val = getattr(override, f.name)
            if val is not None:
                merged[f.name] = val
        override_params = getattr(override, "params", None) or {}
        merged["extra"] = _merge_extra(base_extra, getattr(override, "extra", None) or {})
    else:
        for f in fields(base):
            if f.name == "extra":
                continue
            if f.name in override_map and override_map[f.name] is not None:
                merged[f.name] = override_map[f.name]
        override_params = override_map.get("params", {}) or {}
        merged["extra"] = _merge_extra(base_extra, override_map.get("extra", {}) or {})

    # Deep-merge params into extra (InstrumentConfig uses 'extra', not 'params').
    base_params = getattr(base, "params", None) or {}
    if base_params or override_params:
        merged_params = {**dict(base_params), **dict(override_params)}
        if "params" in merged:
            # InstrumentConfig doesn't have a 'params' field: fold into extra
            del merged["params"]
        merged["extra"] = {**merged_params, **(merged.get("extra", {}) or {})}

    # A section override wins even when the global and section settings use
    # different representations (a config field versus nested params).
    own_extra = (override_map.get("extra", {}) if override_map is not None
                 else getattr(override, "extra", None)) or {}
    own_nested = own_extra.get("extra") if isinstance(own_extra.get("extra"), dict) else {}
    own_params = {**{k: v for k, v in own_extra.items() if k != "extra"},
                  **override_params, **own_nested}
    persona_keys = set(own_extra.get("_persona_keys") or [])
    merged["extra"] = dict(merged.get("extra") or {})
    nested = merged["extra"].get("extra")
    if isinstance(nested, dict):
        merged["extra"]["extra"] = dict(nested)
    for f in fields(base):
        if f.name == "extra":
            continue
        own_field = override_map.get(f.name) if override_map is not None else getattr(override, f.name, None)
        if own_field is not None:
            merged["extra"].pop(f.name, None)
            if isinstance(nested, dict):
                merged["extra"]["extra"].pop(f.name, None)
        elif own_params.get(f.name) is not None and (f.name in own_nested or f.name not in persona_keys):
            merged[f.name] = own_params[f.name]

    # Only pass fields that the dataclass actually accepts
    valid_fields = {f.name for f in fields(base)}
    filtered = {k: v for k, v in merged.items() if k in valid_fields}

    return type(base)(**filtered)


def init_timelines(cfg: RootConfig, instruments_to_init: Optional[list[str]] = None) -> dict[str, InstrumentTimeline]:
    """Create empty per-instrument timelines for specified instruments.

    Phase N2: Only creates timelines for active instruments (those actually used
    in sections) rather than all registered engines. This ensures unused
    instruments don't appear in exports or summaries.

    Args:
        cfg: Parsed root config containing the engine registry.
        instruments_to_init: Optional list of instrument names to initialize.
            If None, initializes timelines for all registered engines (backward
            compatibility).

    Returns:
        dict[str, InstrumentTimeline]: Mapping of instrument name -> empty
        timeline instance.
    """
    if instruments_to_init is None:
        # Backward compatibility: initialize all engines
        instruments_to_init = list(cfg.engines.keys())

    return {
        name: InstrumentTimeline(
            instrument=name,
            default_channel=_engine_channel(cfg, name),
        )
        for name in instruments_to_init
    }


def _engine_channel(cfg: RootConfig, inst_name: str) -> Optional[int]:
    """Return the engine-spec MIDI channel for an instrument, if registered.

    Sources `engines.yml` (and project overrides) via the engine registry so
    the configured `channel:` is actually applied to emitted events.
    """
    engine = getattr(cfg, "engines", {}).get(inst_name) if getattr(cfg, "engines", None) else None
    ch = getattr(engine, "channel", None) if engine is not None else None
    try:
        return int(ch) if ch is not None else None
    except Exception:
        return None


def compute_instruments_used(cfg: RootConfig) -> list[str]:
    """Return instruments in stable order of first appearance in the arrangement.

    This helper walks the arrangement in order and records instruments the first
    time they are declared under a section.

    The resulting list is used for:
      - Deterministic track ordering when exporting MIDI.
      - Summaries that only include instruments actually present in the config.

    Args:
        cfg: Parsed root config containing `arrangement` and `sections`.

    Returns:
        list[str]: Instrument names in first-seen arrangement order.

    Raises:
        KeyError: If an arrangement entry references a missing section.
    """
    instruments_used: list[str] = []
    seen: set[str] = set()
    for sec_id in cfg.arrangement:
        for inst_name in cfg.sections[sec_id].instruments.keys():
            if inst_name not in seen:
                seen.add(inst_name)
                instruments_used.append(inst_name)
    return instruments_used


def render_section_instruments(
    *,
    cfg: RootConfig,
    sec,
    hplan: Optional[object],
    rgrid: object,
    section_start_beat: float,
    section_rng: object,
    timelines: dict[str, InstrumentTimeline],
    performance_plan: Optional[object] = None,
    transition_context: Optional[dict] = None,
    effective_variation: float = 0.0,
    logger: logging.Logger,
) -> List[EngineFeedback]:
    """Render all instruments declared in a section into their timelines.

    Phase N2: Engines are executed in priority order (ascending) rather than
    section declaration order. This ensures that dependencies are respected
    (e.g., drums exports groove cues before bass reads them).

    Phase N3: Before executing each engine, validates that all required
    dependencies (from engine.requires) are present in the performance plan.
    If dependencies are missing, raises a ConfigError with actionable suggestions.

    Phase N8: Collects negotiation feedback from engines during rendering.
    Engines can optionally provide feedback suggesting plan adjustments for
    subsequent sections. Feedback is returned to the caller for application
    at section boundaries.

    For each instrument entry under `sec.instruments`:
      - Validates engine dependencies (Phase N3).
      - Looks up the corresponding engine in `cfg.engines`.
      - Ensures the instrument's `InstrumentTimeline` exists.
      - Invokes the engine's render function with the section scaffolding and
        song-relative `section_start_beat`.

    Missing engines:
      - If a section declares an instrument with no registered engine, the
        instrument is skipped and a warning is logged.

    Args:
        cfg: Parsed root config (engine registry + song defaults).
        sec: Section configuration for the current section.
        hplan: Optional harmony plan for this section.
        rgrid: Rhythm grid for event placement in this section.
        section_start_beat: Song-relative start beat of the section.
        section_rng: Deterministic RNG for this section.
        timelines: Mapping of instrument name -> timeline (mutated in place).
        performance_plan: Optional performance plan for dependency validation (Phase N3).
        transition_context: Optional dict with prev_section_type, next_section_type,
            is_first_section, is_last_section for transition detection.
        logger: Logger for warnings and debug output.

    Returns:
        List[EngineFeedback]: Feedback collected from engines for negotiation (Phase N8).

    Raises:
        ConfigError: If an engine has unsatisfied dependencies (Phase N3).
    """
    # Phase N8: Create feedback collector for this section
    feedback_collector = create_feedback_collector(sec.id, logger)

    # `harmony.plan` is a section-scoped artifact stored under a global plan
    # key. Clear it at the start of each section so dependency validation is
    # honest: a section without harmony must not pass validation on the
    # previous section's stale entry.
    if performance_plan is not None:
        try:
            performance_plan.data.pop("harmony.plan", None)
            performance_plan.data.pop("melody.guide", None)
        except Exception:
            pass

    # Shared rhythm features: instruments can export features for others to use.
    # Key: instrument name, Value: RhythmFeatures object
    # Drums typically exports first (priority 10), bass/guitar read later (priority 20-30).
    rhythm_features: dict[str, object] = {}

    # Phase N2: Sort instruments by engine priority (ascending) before rendering
    # This ensures dependency order is respected (e.g., drums before bass)
    instruments_in_section = list(sec.instruments.keys())

    # Build list of (inst_name, inst_cfg, engine) tuples, filtering out missing engines
    instruments_with_engines = []
    for inst_name in instruments_in_section:
        engine = cfg.engines.get(inst_name)
        if engine is None:
            logger.warning(
                "Section '%s': no engine registered for instrument '%s'; skipping.",
                sec.id,
                inst_name,
            )
            continue

        # Check if engine is enabled
        if not getattr(engine, 'enabled', True):
            logger.debug(
                "Section '%s': engine '%s' is disabled; skipping.",
                sec.id,
                inst_name,
            )
            continue

        inst_cfg = sec.instruments[inst_name]
        instruments_with_engines.append((inst_name, inst_cfg, engine))

    # Sort by engine priority (ascending: lower priority renders first)
    instruments_with_engines.sort(key=lambda x: x[2].priority)

    # Merge global instrument defaults with section overrides for every
    # instrument up front. The merged configs feed both the engines and the
    # shared groove clock (which needs all instruments' params to resolve
    # per-instrument pocket offsets before later engines have rendered).
    effective_cfgs: dict[str, Any] = {}
    for inst_name, inst_cfg, _engine in instruments_with_engines:
        base_cfg = _get_global_instrument_cfg(cfg, inst_name)
        effective_cfgs[inst_name] = _merge_instrument_config(base_cfg, inst_cfg)

    # Shared groove clock state (resolved lazily once per section, after the
    # drums engine has published its merged humanize params to the plan).
    def recipe_feel_params(name, instrument_cfg):
        from ..config.recipes import resolve_recipe_name, merge_recipe_params
        params = effective_params_dict(instrument_cfg)
        raw = getattr(cfg, "raw", {}) or {}
        recipes = raw.get("_recipes", {}).get(name, {})
        song = getattr(cfg, "song", None)
        intensity = getattr(instrument_cfg, "intensity", None)
        if intensity is None:
            intensity = getattr(sec, "intensity", None)
        recipe_name = resolve_recipe_name(
            instrument=name, genre=getattr(instrument_cfg, "genre", None) or getattr(song, "genre", None),
            section_type=sec.type, intensity=.5 if intensity is None else intensity,
            bpm=getattr(song, "bpm", 120), time_signature=getattr(sec, "meter", None) or getattr(song, "meter", "4/4"),
            instrument_recipe=getattr(instrument_cfg, "recipe", None), section_recipe=params.get("recipe"),
            recipes=recipes,
        )
        explicit_keys = set(params) - set(params.get("_persona_keys") or [])
        params = merge_recipe_params(params, (recipes.get(recipe_name) or {}).get("params", {}))
        if name == "drums":
            for key, value in (raw.get("groove") or {}).items():
                if key in ("swing", "swing_16th") and key not in explicit_keys:
                    params[key] = value
        return params

    groove_inst_params = {
        name: recipe_feel_params(name, c) for name, c in effective_cfgs.items()
    }
    groove_feel = None
    groove_feel_resolved = False

    if performance_plan is not None:
        performance_plan.set(
            f"ensemble.{sec.id}",
            build_ensemble_section_plan(cfg, sec, rgrid, transition_context),
        )

    def _resolve_section_groove_feel():
        """Resolve the section's groove feel once (drums params from plan)."""
        drum_params = None
        if performance_plan is not None:
            try:
                drum_params = performance_plan.get(f"groove.humanize.{sec.id}")
            except Exception:
                drum_params = None
        if not isinstance(drum_params, dict):
            # Drums not rendered (or no plan): fall back to the merged drums
            # instrument params, including the selected recipe.
            drum_params = groove_inst_params.get("drums")
            if drum_params is None:
                drum_params = recipe_feel_params("drums", _get_global_instrument_cfg(cfg, "drums"))
        feel = resolve_groove_feel(cfg, sec, drum_params, groove_inst_params)
        if feel is not None:
            pockets = {
                k: round(v, 2)
                for k, v in sorted(feel.pocket_offsets_ms.items())
                if k in groove_inst_params
            }
            logger.info(
                "Section '%s': groove feel resolved (source=%s, swing=%.2f, "
                "swing_16th=%.2f, pockets_ms=%s)",
                sec.id,
                feel.source,
                feel.swing,
                feel.swing_16th,
                pockets,
            )
        else:
            logger.debug(
                "Section '%s': no groove indication; groove clock inactive.",
                sec.id,
            )
        return feel

    # Prepare deterministic per-instrument state, then run every planning hook
    # before rendering any MIDI. This makes current-section intent available to
    # earlier render priorities (notably rhythm guitar before lead guitar).
    prepared_engines = []
    for inst_name, inst_cfg, engine in instruments_with_engines:
        effective_cfg = effective_cfgs[inst_name]
        inst_seed = getattr(effective_cfg, "seed", None) if hasattr(effective_cfg, "seed") else (
            effective_cfg.get("seed") if isinstance(effective_cfg, dict) else None
        )
        if inst_seed is not None:
            inst_rng_seed = stable_seed_int("inst_override", inst_seed, sec.id, inst_name)
            engine_rng = random.Random(inst_rng_seed)
            logger.debug(
                "Section '%s': instrument '%s' using seed override %d",
                sec.id, inst_name, inst_seed,
            )
        else:
            engine_rng = make_instrument_rng(section_rng, inst_name)

        # Resolve effective variation for this instrument:
        # instrument.variation > section.variation > song.variation > 0.0
        inst_variation = getattr(effective_cfg, "variation", None) if hasattr(effective_cfg, "variation") else (
            effective_cfg.get("variation") if isinstance(effective_cfg, dict) else None
        )
        engine_variation = inst_variation if inst_variation is not None else effective_variation

        # Inject variation into the effective config's extra dict so engines can read it
        if engine_variation > 0.0:
            if hasattr(effective_cfg, "extra"):
                if effective_cfg.extra is None:
                    effective_cfg = type(effective_cfg)(
                        **{f.name: ({"_variation": engine_variation} if f.name == "extra" else getattr(effective_cfg, f.name))
                           for f in __import__("dataclasses").fields(effective_cfg)}
                    )
                elif isinstance(effective_cfg.extra, dict) and "_variation" not in effective_cfg.extra:
                    effective_cfg.extra["_variation"] = engine_variation
            elif isinstance(effective_cfg, dict):
                effective_cfg.setdefault("_variation", engine_variation)

        prepared_engines.append((inst_name, effective_cfg, engine, engine_rng))

    for inst_name, effective_cfg, engine, engine_rng in prepared_engines:
        _validate_engine_dependencies(inst_name, engine, performance_plan, cfg, logger)
        if engine.contribute_plan is not None:
            section_ctx = {
                "cfg": cfg,
                "section": sec,
                "instrument_name": inst_name,
                "instrument_cfg": effective_cfg,
                "harmony_plan": hplan,
                "rhythm_grid": rgrid,
                "section_start_beat": section_start_beat,
                "transition_context": transition_context,
                "rhythm_features": rhythm_features,
            }
            engine.contribute_plan(
                plan=performance_plan,
                section_ctx=section_ctx,
                rng=engine_rng,
                logger=logger,
            )

    # Derive melodic intent after harmony and all instrument planning hooks,
    # but before any engine renders.  A dedicated RNG keeps engine streams
    # stable when the melody planner evolves.
    if performance_plan is not None:
        guide_dict = None

        # Theme-driven guide (design: docs/design/theme-bank-architecture.md).
        # When the song defines themes, the guide is built from the realized
        # MELODY theme under this section's arc treatment, and realized notes
        # for every role are published so engines can quote them directly.
        # Pitched roles need the harmony plan (chord snapping), but a
        # drum_groove theme is rhythm + voice: it only needs the section
        # length, so it is published even for drums-only sections.
        theme_bank = performance_plan.get("themes.bank")
        if theme_bank is not None and getattr(theme_bank, "themes", None):
            from ..themes.arc import treatment_for
            from ..themes.guide import (
                build_themed_guide,
                realize_for_section,
                realized_to_dicts,
            )
            from ..themes.model import ThemeRole

            sec_key = getattr(sec, "key", None) or getattr(cfg.song, "key", "C")
            sec_mode = getattr(sec, "mode", None) or getattr(cfg.song, "mode", "major")
            sec_genre = str(getattr(cfg.song, "genre", "") or "")
            arrangement_index = 0
            if isinstance(transition_context, dict):
                arrangement_index = int(
                    transition_context.get("arrangement_index", 0) or 0
                )
            # Occurrence count of this section *type* up to this arrangement
            # index (drives repeat-statement escalation, e.g. chorus 2 lift).
            sec_type_key = str(getattr(sec, "type", "") or "").strip().lower()
            occurrence = sum(
                1
                for meta in list(getattr(performance_plan, "sections", []))[:arrangement_index]
                if str(getattr(meta, "type", "") or "").strip().lower() == sec_type_key
            )

            realized_payload: dict[str, list] = {}
            realized_by_name: dict[str, list] = {}
            total_beats = float(getattr(hplan, "total_beats", 0.0) or 0.0)
            if total_beats <= 0.0:
                # Drums-only section: no harmony plan, so take the length
                # from the section's bar count and the rhythm grid meter.
                beats_per_bar = float(getattr(rgrid, "beats_per_bar", 4.0) or 4.0)
                total_beats = float(getattr(sec, "bars", 0) or 0) * beats_per_bar
            for theme in theme_bank.themes.values():
                t_name, t_params = treatment_for(theme, sec_type_key, occurrence)
                if theme.role is ThemeRole.DRUM_GROOVE:
                    # Groove themes are rhythm+voice, not pitch: publish
                    # per-voice onsets for the drums engine instead of
                    # pitch-realized notes.
                    from ..themes.groove import realize_groove

                    performance_plan.set(
                        f"themes.groove.{sec.id}",
                        realize_groove(theme, t_name, t_params, total_beats),
                    )
                    logger.info(
                        "Section '%s': drum groove from theme '%s' (%s)",
                        sec.id, theme.name, t_name,
                    )
                    continue
                if hplan is None:
                    # Pitched themes snap to chord tones; without a harmony
                    # plan there is nothing meaningful to realize against.
                    continue
                notes = realize_for_section(
                    theme, t_name, t_params, hplan.chord_slots,
                    key=sec_key, mode=sec_mode, genre=sec_genre,
                    total_beats=total_beats,
                )
                realized_by_name[theme.name] = realized_to_dicts(notes)
                # The first declared theme owns its role in every consumer.
                realized_payload.setdefault(theme.role.value, realized_by_name[theme.name])
                if theme.role is ThemeRole.MELODY and guide_dict is None:
                    guide_dict = build_themed_guide(
                        theme, hplan,
                        key=sec_key, mode=sec_mode, genre=sec_genre,
                        total_beats=total_beats,
                        transform_name=t_name, transform_params=t_params,
                        realized_notes=notes,
                    ).to_dict()
                    logger.info(
                        "Section '%s': melody guide from theme '%s' "
                        "(%s, occurrence %d, %d notes)",
                        sec.id, theme.name, t_name, occurrence + 1, len(notes),
                    )
            performance_plan.set(f"themes.realized.{sec.id}", realized_payload)
            performance_plan.set(f"themes.realized_by_name.{sec.id}", realized_by_name)

        if guide_dict is None and hplan is not None:
            melody_rng = random.Random(stable_seed_int(
                "melody_guide", getattr(cfg.song, "seed", 42), sec.id,
                section_start_beat, getattr(cfg.song, "genre", ""),
            ))
            guide_dict = build_melody_guide(
                hplan,
                key=getattr(sec, "key", None) or getattr(cfg.song, "key", "C"),
                mode=getattr(sec, "mode", None) or getattr(cfg.song, "mode", "major"),
                section_type=getattr(sec, "type", ""),
                genre=getattr(cfg.song, "genre", ""),
                rng=melody_rng,
            ).to_dict()
        if guide_dict is not None:
            performance_plan.set(f"melody.guide.{sec.id}", guide_dict)
            performance_plan.set("melody.guide", guide_dict)

        # Composed lead (design: docs/design/composer-architecture.md). The
        # song composer writes this section's lead from the song DNA and its
        # memory of earlier sections; the lead engine performs it. The
        # ensemble's lead windows are replaced with where the lead actually
        # plays, so accompaniment makes room for real phrases.
        _compose_lead_for_section(
            cfg, sec, hplan, rgrid, effective_cfgs.get("lead_gtr"),
            performance_plan, transition_context, logger,
        )
        _compose_rhythm_for_section(
            cfg, sec, hplan, rgrid, effective_cfgs.get("rhythm_gtr"),
            performance_plan, transition_context, logger,
        )

    # Render instruments in priority order after the complete intent prepass.
    for inst_name, effective_cfg, engine, engine_rng in prepared_engines:
        timeline = timelines.get(inst_name)
        if timeline is None:
            timeline = InstrumentTimeline(
                instrument=inst_name,
                default_channel=_engine_channel(cfg, inst_name),
            )
            timelines[inst_name] = timeline

        logger.debug(
            "Section '%s': rendering %s (priority=%d)",
            sec.id,
            inst_name,
            engine.priority,
        )

        events_before = len(timeline.events)

        render_result = engine.render(
            cfg=cfg,
            section=sec,
            instrument_name=inst_name,
            instrument_cfg=effective_cfg,
            harmony_plan=hplan,
            rhythm_grid=rgrid,
            section_start_beat=section_start_beat,
            rng=engine_rng,
            timeline=timeline,
            transition_context=transition_context,
            rhythm_features=rhythm_features,  # Cross-instrument coupling
            feedback_collector=feedback_collector,  # Phase N8: Negotiation feedback
            plan=performance_plan,  # Phase RG2: Pass plan for rhythm.accents access
            logger=logger,
        )

        # Groove memory (produzre/composer/groove_memory.py): give the rhythm
        # section a bar form and recall established grooves. Runs before the
        # groove clock so restated bars still get this section's swing.
        _apply_groove_memory_pass(
            cfg, sec, inst_name, effective_cfg, hplan, rgrid, timeline, events_before,
            section_start_beat, performance_plan, transition_context, section_rng, logger,
        )
        _apply_bass_response_pass(
            cfg, sec, inst_name, effective_cfg, hplan, timeline, events_before,
            section_start_beat, performance_plan, logger, rhythm_features=rhythm_features, transition_context=transition_context,
        )

        # Shared groove clock: post-process the newly added events with the
        # section's resolved feel. Drums are excluded: they already swing
        # internally and are the reference clock (pocket 0 by definition).
        # apply_feel is invoked exactly once per event (this is the only call
        # site), so swing can never double-apply.
        if inst_name != "drums":
            new_events = timeline.events[events_before:]
            if new_events:
                if not groove_feel_resolved:
                    groove_feel = _resolve_section_groove_feel()
                    groove_feel_resolved = True
                if groove_feel is not None:
                    inst_params = groove_inst_params.get(inst_name, {}) or {}
                    try:
                        jitter_ms = float(inst_params.get("timing_jitter_ms", 0.0) or 0.0)
                    except (TypeError, ValueError):
                        jitter_ms = 0.0
                    try:
                        vel_humanize = float(inst_params.get("velocity_humanize", 0.0) or 0.0)
                    except (TypeError, ValueError):
                        vel_humanize = 0.0
                    song = getattr(cfg, "song", None)
                    try:
                        bpm = float(getattr(song, "bpm", 120.0) or 120.0)
                    except (TypeError, ValueError):
                        bpm = 120.0
                    beats_per_bar = float(getattr(rgrid, "beats_per_bar", 4.0) or 4.0)
                    arrangement_index = 0
                    if isinstance(transition_context, dict):
                        arrangement_index = int(
                            transition_context.get("arrangement_index", 0) or 0
                        )
                    seed_material = getattr(section_rng, "_produzre_seed", None)
                    if seed_material is None:
                        seed_material = stable_seed_int(
                            "groove_fallback", sec.id, getattr(sec, "type", "")
                        )
                    feel_seed = stable_seed_int(
                        "groove", seed_material, sec.id, arrangement_index, inst_name
                    )
                    from ..composer.song import section_groups

                    apply_feel(
                        new_events,
                        groove_feel,
                        inst_name,
                        bpm,
                        beats_per_bar,
                        feel_seed,
                        section_start_beat=float(section_start_beat),
                        timing_jitter_ms=jitter_ms,
                        velocity_humanize=vel_humanize,
                        groups=section_groups(cfg, sec, getattr(hplan, "meter", None)),
                    )

        # A lead guitar is monophonic: after feel and humanization, no note
        # may still be sounding when the next one starts (grace notes aside).
        if inst_name == "lead_gtr":
            mono = sorted(timeline.events[events_before:], key=lambda e: (e.start_beat, e.pitch))
            for cur, nxt in zip(mono, mono[1:]):
                gap = float(nxt.start_beat) - float(cur.start_beat)
                if gap > 0.02 and float(cur.duration_beats) > gap - 0.01:
                    cur.duration_beats = max(0.05, gap - 0.01)

        # Timing feel cannot move notes beyond the section being rendered.
        section_end = section_start_beat + float(getattr(rgrid, "total_beats", float("inf")))
        bounded = []
        for ev in timeline.events[events_before:]:
            ev.start_beat = max(section_start_beat, ev.start_beat)
            ev.duration_beats = min(ev.duration_beats, section_end - ev.start_beat)
            if ev.duration_beats > 0:
                bounded.append(ev)
        timeline.events[events_before:] = bounded
        new_events = bounded
        if render_result is not None:
            rhythm_features[inst_name] = render_result
        if performance_plan is not None and new_events:
            local_onsets = sorted({
                round(float(event.start_beat) - float(section_start_beat), 4)
                for event in new_events
            })
            pitches = [int(event.pitch) for event in new_events]
            performance = {
                "section_id": sec.id,
                "event_count": len(new_events),
                "onsets": local_onsets,
                "register": [min(pitches), max(pitches)],
            }
            performance_plan.set(f"performance.{inst_name}.{sec.id}", performance)
            if inst_name == "bass":
                performance_plan.set("bass.line", performance)
            elif inst_name == "rhythm_gtr":
                performance_plan.set("rhythm.texture.actual", performance)
            elif inst_name == "lead_gtr":
                performance_plan.set("melody.line", performance)
                performance_plan.set("lead.phrases", {
                    "section_id": sec.id,
                    "activity_windows": performance_plan.get(
                        f"ensemble.{sec.id}", {}
                    ).get("lead_activity_windows", []),
                })

    # Phase N8: Return collected feedback for negotiation between sections
    return feedback_collector.get_feedback()


def _as_float(*values: Any) -> Optional[float]:
    for v in values:
        try:
            if v is not None:
                return float(v)
        except (TypeError, ValueError):
            continue
    return None


def _flag(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() not in ("false", "off", "no", "0", "none")
    return bool(value)


def _groove_signature(value):
    """Canonical configuration identity, including nested params and sets."""
    if isinstance(value, dict):
        return tuple(sorted((str(k), _groove_signature(v)) for k, v in value.items()
                            if not str(k).startswith("_")))
    if isinstance(value, (list, tuple)):
        return tuple(_groove_signature(v) for v in value)
    if isinstance(value, (set, frozenset)):
        return tuple(sorted((_groove_signature(v) for v in value), key=repr))
    return value


def _apply_groove_memory_pass(cfg, sec, inst_name, inst_cfg, hplan, rgrid, timeline,
                              events_before, section_start_beat, performance_plan,
                              transition_context, section_rng, logger) -> None:
    from ..composer.groove_memory import GROOVE_INSTRUMENTS, GrooveMemory, apply_groove_memory

    if inst_name not in GROOVE_INSTRUMENTS or performance_plan is None:
        return
    if inst_name == "rhythm_gtr" and performance_plan.get(f"composer.comp.{sec.id}"):
        return  # composed comping already has its bar form
    raw = getattr(cfg, "raw", None)
    song_raw = raw.get("song", {}) if isinstance(raw, dict) else {}
    if not _flag(song_raw.get("groove_memory") if isinstance(song_raw, dict) else None):
        return
    params = effective_params_dict(inst_cfg)
    if not _flag(params.get("groove_memory")):
        return
    # A soloing part is the foreground, not the groove.
    if getattr(inst_cfg, "solo", False) or params.get("solo") or \
            getattr(inst_cfg, "role", None) == "lead" or params.get("role") == "lead":
        return
    if inst_name == "bass" and (getattr(sec, "solo", None) is True
                                or getattr(sec, "role", None) == "lead"):
        return
    new_events = timeline.events[events_before:]
    if not new_events:
        return
    bpb = float(getattr(rgrid, "beats_per_bar", 4.0) or 4.0)
    total = float(getattr(rgrid, "total_beats", 0.0) or 0.0)
    bars = int(round(total / bpb)) if bpb > 0 else 0

    memory = performance_plan.get("composer.groove_memory")
    if memory is None:
        memory = GrooveMemory()
        performance_plan.set("composer.groove_memory", memory)
    # A section type recalls its groove only when the part is configured the
    # same way; intensity is excluded so escalating repeats still recall.
    settings = {f.name: getattr(inst_cfg, f.name) for f in fields(inst_cfg)
                if f.name not in ("extra", "intensity", "patterns")}
    raw_extra = getattr(inst_cfg, "extra", None) or {}
    settings["params"] = {k: v for k, v in {
        **{k: v for k, v in raw_extra.items() if k != "extra"}, **params
    }.items() if k != "intensity"}
    signature = _groove_signature(settings)
    persona = getattr(inst_cfg, "persona", None)
    memory_key = (inst_name, str(getattr(sec, "type", "") or "").strip().lower(), bpb,
                  stable_seed_int("groove_sig", persona, signature))
    arrangement_index = 0
    if isinstance(transition_context, dict):
        arrangement_index = int(transition_context.get("arrangement_index", 0) or 0)
    seed_material = getattr(section_rng, "_produzre_seed", None)
    seed = stable_seed_int("groove_memory", seed_material if seed_material is not None
                           else getattr(cfg.song, "seed", 0), sec.id, arrangement_index)
    replaced, report = apply_groove_memory(
        new_events,
        instrument=inst_name,
        section_start=float(section_start_beat),
        beats_per_bar=bpb,
        bars=bars,
        chord_slots=getattr(hplan, "chord_slots", None) if hplan is not None else None,
        key=getattr(sec, "key", None) or getattr(cfg.song, "key", "C"),
        mode=getattr(sec, "mode", None) or getattr(cfg.song, "mode", "major"),
        genre=str(getattr(cfg.song, "genre", "") or ""),
        bpm=float(getattr(cfg.song, "bpm", 120.0) or 120.0),
        memory=memory,
        memory_key=memory_key,
        seed=seed,
        cycle_override=params.get("groove_cycle_bars"),
        intensity=_as_float(getattr(inst_cfg, "intensity", None), getattr(sec, "intensity", None)),
    )
    if report.get("applied"):
        timeline.events[events_before:] = replaced
        logger.debug(
            "Section '%s': %s groove memory form=%s cycle=%d restated=%d%s",
            sec.id, inst_name, report["form"], report["cycle"], report["restated"],
            " (recalled)" if report["recalled"] else "",
        )


# Settings that choose a *different kind of part* (a pinned style, pattern,
# sustain mode, recipe, or the legacy generators' own phrase controls). When
# the user sets one, the composer steps aside for that part.
_RHYTHM_USER_MODES = ("style", "strum_style", "sustain_mode", "playstyle", "play_pattern",
                      "pattern", "follow_hats", "use_patterns", "recipe")
# Tuning for the legacy generators only. They do not choose a different part,
# so the composer keeps the section and the build says the setting is unused.
_RHYTHM_LEGACY_ONLY = ("phrase_len_bars", "phrase_development", "section_contrast")
_LEAD_LEGACY_ONLY = ("phrase_len_bars", "theme_quote_rate", "resolution_strength",
                     "ring_out", "ring_max_beats")
# Feel settings the composed rhythm performer honors instead of opting out.
_RHYTHM_FEEL_KEYS = ("density", "palm_mute", "chuck_rate", "voicing", "accent_strength",
                     "humanize_velocity", "downbeat_boost", "sustain_cut_rate",
                     "register_min", "register_max", "offset_beats", "style_bias", "humanize_timing", "strum_ms")


def _note_legacy_only(logger, sec, inst: str, settings: dict) -> None:
    if settings:
        logger.info(
            "Section '%s': %s %s tune the legacy generator and are unused by the "
            "composer; set `composer: false` on %s to use them.",
            sec.id, inst, ", ".join(sorted(settings)), inst,
        )


def _explicit_settings(inst_cfg, extra: dict, keys) -> dict:
    """User-set values for ``keys``: config fields plus non-persona params.

    Recipe defaults are merged later inside the engines, so they never count
    as the user's choice here.
    """
    persona_keys = set(extra.get("_persona_keys") or [])
    raw = getattr(inst_cfg, "extra", None)
    # The loader nests the user's own params one level down; a key there is
    # the user's even when the persona tag still lists the persona's value.
    nested = raw.get("extra") if isinstance(raw, dict) and isinstance(raw.get("extra"), dict) else {}
    out = {}
    for k in keys:
        v = getattr(inst_cfg, k, None)
        if v is not None and not isinstance(v, dict):
            out[k] = v
        if k in extra and extra[k] is not None and (k in nested or k not in persona_keys):
            out[k] = extra[k]
    return out


_HEAVY_COMP = ("metal", "punk", "grunge", "hard_rock", "thrash")


def _compose_rhythm_for_section(cfg, sec, hplan, rgrid, rhythm_cfg, performance_plan,
                                transition_context, logger) -> None:
    """Publish ``composer.comp.<section>`` for the rhythm engine to perform."""
    if performance_plan is None or rhythm_cfg is None or hplan is None:
        return
    performance_plan.data.pop(f"composer.comp.{sec.id}", None)
    composer = performance_plan.get("composer.song")
    if composer is None or not getattr(hplan, "chord_slots", None):
        return
    raw_extra = getattr(rhythm_cfg, "extra", None)
    extra: dict = {}
    if isinstance(raw_extra, dict):
        extra = {k: v for k, v in raw_extra.items() if k != "extra"}
        if isinstance(raw_extra.get("extra"), dict):
            extra.update(raw_extra["extra"])
    if not _flag(extra.get("composer")) or getattr(rhythm_cfg, "enabled", True) is False:
        return
    if _explicit_settings(rhythm_cfg, extra, _RHYTHM_USER_MODES):
        return
    feel = _explicit_settings(rhythm_cfg, extra, _RHYTHM_FEEL_KEYS)
    _note_legacy_only(logger, sec, "rhythm_gtr", _explicit_settings(rhythm_cfg, extra,
                                                                     _RHYTHM_LEGACY_ONLY))
    try:
        if float(extra.get("lock_to_riff", 0) or 0) > 0:
            return
    except (TypeError, ValueError):
        pass

    from ..composer.comping import plan_comp_section
    from ..composer.song import section_groups

    arrangement_index = 0
    if isinstance(transition_context, dict):
        arrangement_index = int(transition_context.get("arrangement_index", 0) or 0)
    sections = list(getattr(performance_plan, "sections", []) or [])
    sec_type = str(getattr(sec, "type", "") or "").strip().lower()
    occurrence = sum(1 for m in sections[:arrangement_index]
                     if str(getattr(m, "type", "") or "").strip().lower() == sec_type)
    is_final = not any(str(getattr(m, "type", "") or "").strip().lower() == sec_type
                       for m in sections[arrangement_index + 1:])
    bpb = float(getattr(rgrid, "beats_per_bar", 4.0) or 4.0)
    total = float(getattr(hplan, "total_beats", 0.0) or 0.0)
    bars = int(round(total / bpb)) if bpb > 0 else 0
    nxt = (transition_context or {}).get("next_section_type")
    if isinstance(transition_context, dict) and transition_context.get("is_last_section"):
        nxt = None
    events, riff, ring = plan_comp_section(
        composer.comp_dna(),
        section_type=sec_type, occurrence=occurrence, is_final_of_type=is_final,
        bars=bars, beats_per_bar=bpb, chord_slots=hplan.chord_slots,
        key=getattr(sec, "key", None) or getattr(cfg.song, "key", "C"),
        mode=getattr(sec, "mode", None) or getattr(cfg.song, "mode", "major"),
        next_section_type=nxt if nxt else (None if (transition_context or {}).get(
            "is_last_section") else "verse"),
        hook_onsets=composer.hook_onsets(bpb, section_groups(cfg, sec, getattr(hplan, "meter", None))),
        groups=section_groups(cfg, sec, getattr(hplan, "meter", None)),
    )
    if not events:
        return
    genre = str(getattr(cfg.song, "genre", "") or "").lower()
    performance_plan.set(f"composer.comp.{sec.id}", {
        "riff": riff, "ring": ring, "heavy": any(t in genre for t in _HEAVY_COMP),
        "user": feel,
        "events": [{"beat": e.beat, "dur": e.dur, "kind": e.kind, "accent": e.accent,
                    "direction": e.direction, "arp_index": e.arp_index,
                    "target_pc": e.target_pc, "tag": e.tag} for e in events],
    })
    logger.info("Composer: %s rhythm guitar plays '%s'", sec.id, riff)


def _apply_bass_response_pass(cfg, sec, inst_name, inst_cfg, hplan, timeline, events_before,
                              section_start_beat, performance_plan, logger,
                              rhythm_features=None, transition_context=None) -> None:
    """Opt-in (bass ``hook_response: true``): answer the lead's holes with the hook."""
    if inst_name != "bass" or performance_plan is None or hplan is None:
        return
    raw_extra = getattr(inst_cfg, "extra", None) or {}
    params = {**{k: v for k, v in raw_extra.items() if k != "extra"},
              **(raw_extra.get("extra") or {})}
    response_mode = params.get("hook_response")
    if not _flag(response_mode, default=False):
        return
    composer = performance_plan.get("composer.song")
    lead = performance_plan.get(f"composer.lead.{sec.id}")
    if composer is None or not lead or not getattr(hplan, "chord_slots", None):
        return
    from ..composer.bass_response import align_to_kicks, lead_holes, phrase_holes, respond
    from ..composer.theory import ChordMap

    total = float(getattr(hplan, "total_beats", 0.0) or 0.0)
    bpb = float(getattr(hplan.meter, "beats_per_bar", 4.0) or 4.0)
    holes = phrase_holes(lead_holes([(float(n["beat"]), float(n["duration_beats"]))
                                     for n in lead], total), bpb, total)
    kicks = getattr((rhythm_features or {}).get("drums"), "strong_beats", None)
    if kicks:
        holes = align_to_kicks(holes, [float(t) for t in kicks])
    new_events = timeline.events[events_before:]
    if not holes or not new_events:
        return
    key = getattr(sec, "key", None) or getattr(cfg.song, "key", "C")
    mode = getattr(sec, "mode", None) or getattr(cfg.song, "mode", "major")
    pitches = sorted(e.pitch for e in new_events)
    reference = pitches[len(pitches) // 2]
    from ..composer.song import section_groups

    dna = composer._dna_for(bpb, section_groups(cfg, sec, hplan.meter))
    index = int((transition_context or {}).get("arrangement_index", 0))
    sections = list(getattr(performance_plan, "sections", ()) or ())
    occurrence = sum(getattr(s, "type", None) == getattr(sec, "type", None) for s in sections[:index])
    answer = respond(dna.hook, holes, ChordMap(hplan.chord_slots, key, mode),
                     key=key, mode=mode, reference=reference,
                     lo=int(params.get("register_low", 28)), hi=int(params.get("register_high", 55)),
                     develop=str(response_mode).lower() == "develop", occurrence=occurrence,
                     answer=dna.hook_answer)
    if not answer:
        return
    used = [h for h in holes if any(h[0] - 1e-6 <= n.beat < h[1] for n in answer)]
    velocities = sorted(e.velocity for e in new_events)
    velocity = min(127, int(velocities[len(velocities) // 2] * 1.05))
    template = new_events[0]
    kept = []
    for ev in new_events:
        local = float(ev.start_beat) - float(section_start_beat)
        if any(a - 0.02 <= local < b for a, b in used):
            continue  # the groove steps aside for the answer
        for a, _ in used:
            if local < a and local + ev.duration_beats > a:
                ev.duration_beats = max(0.05, a - local - 0.02)
        kept.append(ev)
    from dataclasses import replace as _replace

    for n in answer:
        kept.append(_replace(template, start_beat=float(section_start_beat) + n.beat,
                             duration_beats=n.dur, pitch=n.pitch, velocity=velocity,
                             kind="hook_response", expression=None))
    kept.sort(key=lambda e: (e.start_beat, e.pitch))
    timeline.events[events_before:] = kept
    logger.info("Section '%s': bass answers the lead in %d hole(s) with the hook's rhythm",
                sec.id, len(used))


def _compose_lead_for_section(cfg, sec, hplan, rgrid, lead_cfg, performance_plan,
                              transition_context, logger) -> None:
    """Publish ``composer.lead.<section>`` for the lead engine to perform."""
    if performance_plan is None or lead_cfg is None or hplan is None:
        return
    if not getattr(hplan, "chord_slots", None):
        return
    composer = performance_plan.get("composer.song")
    if composer is None:
        return
    raw_extra = getattr(lead_cfg, "extra", None)
    extra: dict = {}
    if isinstance(raw_extra, dict):
        # Persona keys sit at the top level, user params may nest one level.
        extra = {k: v for k, v in raw_extra.items() if k != "extra"}
        if isinstance(raw_extra.get("extra"), dict):
            extra.update(raw_extra["extra"])
    shaping = _explicit_settings(lead_cfg, extra, ("rest_probability", "contour_style"))
    opt = extra.get("composer", True)
    if isinstance(opt, str):
        opt = opt.strip().lower() not in ("false", "off", "no", "legacy", "0")
    if not opt or getattr(lead_cfg, "enabled", True) is False:
        performance_plan.data.pop(f"composer.lead.{sec.id}", None)
        return
    _note_legacy_only(logger, sec, "lead_gtr",
                      _explicit_settings(lead_cfg, extra, _LEAD_LEGACY_ONLY))

    from ..composer.lead import LeadContext
    from ..composer.song import lead_register, section_groups
    from .ensemble import _lead_foreground_mode

    arrangement_index = 0
    if isinstance(transition_context, dict):
        arrangement_index = int(transition_context.get("arrangement_index", 0) or 0)
    sections = list(getattr(performance_plan, "sections", []) or [])
    sec_type = str(getattr(sec, "type", "") or "").strip().lower()
    solo_flag = bool(getattr(lead_cfg, "solo", False) or extra.get("solo", False)
                     or getattr(lead_cfg, "role", None) == "lead")
    comp_type = "solo" if solo_flag else sec_type
    occurrence = sum(1 for meta in sections[:arrangement_index]
                     if str(getattr(meta, "type", "") or "").strip().lower() == sec_type)
    is_final = not any(str(getattr(meta, "type", "") or "").strip().lower() == sec_type
                       for meta in sections[arrangement_index + 1:])
    bpb = float(getattr(rgrid, "beats_per_bar", 4.0) or 4.0)
    total = float(getattr(hplan, "total_beats", 0.0) or 0.0)
    bars = int(round(total / bpb)) if bpb > 0 else 0
    intensity = getattr(lead_cfg, "intensity", None)
    if intensity is None:
        intensity = getattr(sec, "intensity", None)
    ctx = LeadContext(
        section_id=sec.id,
        section_type=comp_type,
        occurrence=occurrence,
        is_final_of_type=is_final,
        bars=bars,
        beats_per_bar=bpb,
        total_beats=total,
        key=getattr(sec, "key", None) or getattr(cfg.song, "key", "C"),
        mode=getattr(sec, "mode", None) or getattr(cfg.song, "mode", "major"),
        chord_slots=hplan.chord_slots,
        intensity=float(intensity if intensity is not None else 0.7),
        foreground=_lead_foreground_mode(cfg, sec),
        next_section_type=(transition_context or {}).get("next_section_type"),
        register=lead_register(cfg, lead_cfg),
        rest_probability=_as_float(shaping.get("rest_probability")),
        contour=str(shaping.get("contour_style") or "balanced").strip().lower(),
        groups=section_groups(cfg, sec, getattr(hplan, "meter", None)),
        strict_register=isinstance(extra.get("register", getattr(lead_cfg, "register", None)),
                                   (list, tuple)),
    )
    notes = composer.compose_lead(ctx)
    payload = [
        {"beat": n.beat, "duration_beats": n.dur, "pitch": n.pitch, "accent": n.accent,
         "tech": None if ctx.strict_register and n.tech == "slide"
         and n.pitch - 2 < ctx.register[0] else n.tech, "role": n.role}
        for n in notes
    ]
    performance_plan.set(f"composer.lead.{sec.id}", payload)
    if composer.log:
        logger.info("Composer: %s", composer.log[-1])

    # Advertise the lead's real phrases to the band.
    windows: list[list[float]] = []
    for n in notes:
        start, end = n.beat, n.beat + n.dur
        if windows and start - windows[-1][1] < 1.0:
            windows[-1][1] = max(windows[-1][1], end)
        else:
            windows.append([start, end])
    ens = performance_plan.get(f"ensemble.{sec.id}")
    if isinstance(ens, dict):
        ens = dict(ens)
        ens["lead_activity_windows"] = [tuple(w) for w in windows]
        active = sum(e - s for s, e in windows)
        ens["lead_rest_ratio"] = round(1.0 - min(1.0, active / max(total, 1e-6)), 4)
        performance_plan.set(f"ensemble.{sec.id}", ens)
        performance_plan.set(f"lead_rest_ratio.{sec.id}", ens["lead_rest_ratio"])


def sort_used_timelines(timelines: dict[str, InstrumentTimeline], instruments_used: list[str]) -> None:
    """Sort events for all instruments used by the song.

    Engines may append events in any order during rendering. Sorting ensures:
      - Deterministic exports.
      - Correct note-off ordering when events share start times.

    Args:
        timelines: Mapping of instrument name -> `InstrumentTimeline`.
        instruments_used: Ordered list of instrument names to sort.

    Returns:
        None
    """
    for inst_name in instruments_used:
        timelines[inst_name].sort_events()
