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
        # No InstrumentConfig — wrap persona params in one so engines get a
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
            # InstrumentConfig doesn't have a 'params' field — fold into extra
            del merged["params"]
        merged["extra"] = {**merged_params, **(merged.get("extra", {}) or {})}

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
    groove_inst_params = {
        name: effective_params_dict(c) for name, c in effective_cfgs.items()
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
            # instrument params (persona/global/section, without recipe).
            drum_params = groove_inst_params.get("drums")
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
    if performance_plan is not None and hplan is not None:
        guide_dict = None

        # Theme-driven guide (design: docs/design/theme-bank-architecture.md).
        # When the song defines themes, the guide is built from the realized
        # MELODY theme under this section's arc treatment, and realized notes
        # for every role are published so engines can quote them directly.
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
            total_beats = float(getattr(hplan, "total_beats", 0.0) or 0.0)
            for theme in theme_bank.themes.values():
                t_name, t_params = treatment_for(theme, sec_type_key, occurrence)
                notes = realize_for_section(
                    theme, t_name, t_params, hplan.chord_slots,
                    key=sec_key, mode=sec_mode, genre=sec_genre,
                    total_beats=total_beats,
                )
                realized_payload[theme.role.value] = realized_to_dicts(notes)
                if theme.role is ThemeRole.MELODY and guide_dict is None:
                    guide_dict = build_themed_guide(
                        theme, hplan,
                        key=sec_key, mode=sec_mode, genre=sec_genre,
                        total_beats=total_beats,
                        transform_name=t_name, transform_params=t_params,
                    ).to_dict()
                    logger.info(
                        "Section '%s': melody guide from theme '%s' "
                        "(%s, occurrence %d, %d notes)",
                        sec.id, theme.name, t_name, occurrence + 1, len(notes),
                    )
            performance_plan.set(f"themes.realized.{sec.id}", realized_payload)

        if guide_dict is None:
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
        performance_plan.set(f"melody.guide.{sec.id}", guide_dict)
        performance_plan.set("melody.guide", guide_dict)

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

        # Shared groove clock: post-process the newly added events with the
        # section's resolved feel. Drums are excluded — they already swing
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
                    )

        new_events = timeline.events[events_before:]
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
