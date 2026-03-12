
from __future__ import annotations

"""Song build orchestration.

This module is the main entry point for turning a parsed `RootConfig` into a
planned and rendered song.

Pipeline:
1) Planning (`plan_song`)
   - Resolves song title and export naming.
   - Computes section timings (start/end beats) and total duration.
   - Builds per-section harmony plans and rhythm grids.

2) Rendering (engine execution)
   - Initializes one `InstrumentTimeline` per engine in the registry.
   - Iterates planned sections in order and calls each engine's
     `render_into_timeline(...)` via the render dispatcher.

3) Summary + export
   - Logs section timings and per-instrument event counts.
   - Optionally writes the full multi-track MIDI, stems, per-section MIDIs,
     pattern MIDIs, and per-instrument sequencer YAML.

This layer intentionally does not parse CLI args or configure logging; callers
(typically the CLI command handlers) provide the effective `RootConfig` and an
optional logger.
"""

import logging
from typing import Optional

from ..model import RootConfig
from ..rng import make_section_rng, stable_seed_int
from .export_ops import export_all as _export_all
from .logging_summary import (
    log_instrument_summary as _log_instrument_summary,
    log_section_timings as _log_section_timings,
)
from .render import (
    compute_instruments_used as _compute_instruments_used,
    init_timelines as _init_timelines,
    render_section_instruments as _render_section_instruments,
    sort_used_timelines as _sort_used_timelines,
)
from .result import BuildResult
from .plan import plan_song, PerformancePlan, SectionMeta, PLAN_KEY_TRANSITIONS_MAP
from .transitions import (
    evaluate_transitions,
    apply_transition_plan,
    build_section_transitions_map,
    serialize_section_transitions_map,
)
from .negotiation import (
    NegotiationState,
    apply_feedback_for_section,
)


def _create_performance_plan(
    cfg: RootConfig,
    plan: object,  # BuildPlan
    logger: logging.Logger,
) -> PerformancePlan:
    """Create a PerformancePlan from BuildPlan (Phase N1).

    This helper extracts song-level and section-level metadata from the
    BuildPlan and RootConfig and packages it into a PerformancePlan object
    that engines can use for coordination.

    Args:
        cfg: Root configuration.
        plan: BuildPlan with section scaffolding and timing.
        logger: Logger for debug output.

    Returns:
        PerformancePlan: Central negotiation state for engine coordination.
    """
    # Extract song-level metadata
    bpm = float(cfg.song.bpm)
    meter = str(cfg.song.meter)
    key = str(cfg.song.key)
    mode = str(cfg.song.mode)
    beats_per_bar = float(cfg.song.beats_per_bar)
    total_beats = float(plan.total_beats)

    # Build section metadata from plan
    sections: list[SectionMeta] = []
    for ps in plan.planned_sections:
        section = SectionMeta(
            id=ps.sec_id,
            type=ps.sec.type,
            start_beat=ps.timing.start_beat,
            end_beat=ps.timing.end_beat,
            length_beats=ps.timing.length_beats,
            beats_per_bar=ps.timing.beats_per_bar,
            meter=getattr(ps.sec, "meter", meter),
            key=getattr(ps.sec, "key", key),
            mode=getattr(ps.sec, "mode", mode),
        )
        sections.append(section)

    performance_plan = PerformancePlan(
        bpm=bpm,
        meter=meter,
        key=key,
        mode=mode,
        beats_per_bar=beats_per_bar,
        total_beats=total_beats,
        sections=sections,
        data={},  # Empty data store initially
    )

    logger.debug(
        f"[PERFORMANCE_PLAN] Created plan with {len(sections)} sections, "
        f"total_beats={total_beats:.2f}, bpm={bpm}"
    )

    # Phase N5: Build section-level transition directives
    transitions_map = build_section_transitions_map(
        plan.planned_sections,
        logger=logger,
    )
    serialized_transitions = serialize_section_transitions_map(transitions_map)
    performance_plan.set(PLAN_KEY_TRANSITIONS_MAP, serialized_transitions)

    logger.debug(
        f"[PERFORMANCE_PLAN] Added transitions map with {len(transitions_map)} section directives"
    )

    return performance_plan



def build_song(
    *,
    cfg: RootConfig,
    dry_run: bool,
    export_sections: bool,
    export_patterns: bool,
    sections_absolute_timing: bool,
    logger: Optional[logging.Logger] = None,
) -> BuildResult:
    """Build a song from a loaded `RootConfig`.

    This function performs orchestration only:
      - It assumes configuration has already been loaded and validated.
      - It does not mutate the caller's CLI args or perform any YAML parsing.
      - It uses the provided `logger` (or a module logger) for all output.

    Args:
        cfg: Fully parsed configuration including engine registry.
        dry_run: If True, performs planning + rendering into timelines but does
            not write any MIDI/YAML exports.
        export_sections: If True, export per-section MIDI clips per instrument.
        export_patterns: If True, export unique repeating patterns and write a
            per-instrument sequencer (`sequence.yaml`).
        sections_absolute_timing: If True, section MIDI exports keep song-relative
            timing so they align on an absolute timeline; otherwise each section
            export is re-based to start at beat 0.
        logger: Optional logger for status and debug output.

    Returns:
        BuildResult: A structured summary of the build including the plan,
        total beats, section timings, instruments used, and export root (if any).

    Notes:
        - When `dry_run` is True, `export_root` in the result is None.
        - If no instruments are defined in any section, the function returns a
          result without exporting MIDI and emits a warning.
    """
    logger = logger or logging.getLogger(__name__)

    # Plan first (scaffolding + timing), then render, then export.
    plan = plan_song(cfg=cfg, logger=logger)
    song_name = plan.song_name

    # Base seeds used to derive deterministic per-section RNGs.
    # These are owned by the orchestrator so all engines share a consistent
    # randomness source.
    runtime = getattr(cfg, "runtime", None)
    project_seed_raw = getattr(runtime, "project_seed", 0) if runtime is not None else 0
    if not project_seed_raw and runtime is not None:
        project_seed_raw = getattr(runtime, "seed", 0)

    try:
        project_seed = int(project_seed_raw)
    except Exception:
        project_seed = 0

    try:
        song_seed = int(getattr(cfg.song, "seed", 0))
    except Exception:
        song_seed = 0

    try:
        take = int(getattr(cfg.song, "take", 0))
    except Exception:
        take = 0

    # Phase N2: Determine active instruments from song configuration
    # Only instruments used in sections will be rendered and exported
    instruments_used = _compute_instruments_used(cfg)
    logger.debug(f"Active instruments: {instruments_used}")

    # Initialize per-instrument timelines only for active instruments (Phase N2)
    timelines = _init_timelines(cfg, instruments_used)

    # Phase N1: Create PerformancePlan (central negotiation state)
    # This object will be used by engines to share derived data (groove cues, transitions, etc.)
    performance_plan = _create_performance_plan(cfg, plan, logger)

    # Phase N8: Create negotiation state for feedback loop
    negotiation_state = NegotiationState()
    accumulated_feedback = []  # Collect feedback from all sections

    total_sections = len(plan.planned_sections)
    prev_energy = None  # Track energy of previous section for lift/drop detection

    for idx, ps in enumerate(plan.planned_sections):
        # Deterministic per-section RNG (shared across instruments in that section).
        sec_id = getattr(ps.sec, "id", "")
        sec_type = getattr(ps.sec, "type", "")

        # Section-level seed override: if the section declares its own seed,
        # use it instead of the song seed so users can re-roll individual sections.
        section_seed_override = getattr(ps.sec, "seed", None)
        effective_song_seed = section_seed_override if section_seed_override is not None else song_seed

        # Incorporate arrangement index so repeated sections (same sec_id appearing
        # multiple times in the arrangement) produce different output.
        effective_take = stable_seed_int(take, idx)

        section_rng = make_section_rng(project_seed, effective_song_seed, effective_take, sec_id, sec_type)

        # Calculate current section energy (for lift/drop detection)
        # This mirrors the energy detection logic in the drums engine
        energy_raw = getattr(ps.sec, "energy", None)
        if energy_raw is None:
            # Auto-detect from section type
            sec_type_lower = sec_type.lower()
            if sec_type_lower in ("verse", "intro", "outro"):
                current_energy = 0.3  # Low
            elif sec_type_lower in ("chorus", "hook"):
                current_energy = 0.9  # High
            elif sec_type_lower in ("bridge", "prechorus", "pre-chorus"):
                current_energy = 0.6  # Mid
            elif sec_type_lower in ("solo", "breakdown"):
                current_energy = 0.7  # Mid-high
            else:
                current_energy = 0.5  # Default
        else:
            # Parse explicit energy
            if isinstance(energy_raw, str):
                energy_str = str(energy_raw).strip().lower()
                if energy_str == "low":
                    current_energy = 0.3
                elif energy_str in ("mid", "medium"):
                    current_energy = 0.6
                elif energy_str == "high":
                    current_energy = 0.9
                else:
                    try:
                        current_energy = float(energy_raw)
                        current_energy = max(0.0, min(1.0, current_energy))
                    except ValueError:
                        current_energy = 0.5
            else:
                current_energy = float(energy_raw)
                current_energy = max(0.0, min(1.0, current_energy))

        # Build transition context for section boundaries (pickups, downbeat punctuation, lifts).
        # Prev/next section types are used by engines to detect arrangement changes.
        prev_section_type = None
        next_section_type = None
        if idx > 0:
            prev_section_type = getattr(plan.planned_sections[idx - 1].sec, "type", None)
        if idx < total_sections - 1:
            next_section_type = getattr(plan.planned_sections[idx + 1].sec, "type", None)

        transition_context = {
            "section_type": sec_type,
            "prev_section_type": prev_section_type,
            "next_section_type": next_section_type,
            "is_first_section": idx == 0,
            "is_last_section": idx == total_sections - 1,
            "prev_energy": prev_energy,  # For energy lift/drop detection
        }

        # Update prev_energy for next iteration
        prev_energy = current_energy

        # Phase N8: Apply accumulated feedback before rendering this section
        # Feedback from previous sections can influence plan data for this section
        if accumulated_feedback and idx > 0:
            # Apply feedback targeting this section
            applied_count = apply_feedback_for_section(
                feedback_items=accumulated_feedback,
                performance_plan=performance_plan,
                target_section_id=ps.sec.id,
                negotiation_state=negotiation_state,
                logger=logger,
            )
            if applied_count > 0:
                logger.debug(
                    f"[NEGOTIATION] Applied {applied_count} feedback item(s) for section '{ps.sec.id}'"
                )

        # Resolve effective variation for this section:
        # section.variation > song.variation > 0.0
        section_variation = getattr(ps.sec, "variation", None)
        effective_variation = section_variation if section_variation is not None else cfg.song.variation

        # Render section instruments and collect feedback
        section_feedback = _render_section_instruments(
            cfg=cfg,
            sec=ps.sec,
            hplan=ps.harmony_plan,
            rgrid=ps.rhythm_grid,
            section_start_beat=ps.timing.start_beat,
            section_rng=section_rng,
            timelines=timelines,
            performance_plan=performance_plan,
            transition_context=transition_context,
            effective_variation=effective_variation,
            logger=logger,
        )

        # Phase N8: Accumulate feedback for application to subsequent sections
        if section_feedback:
            accumulated_feedback.extend(section_feedback)
            logger.debug(
                f"[NEGOTIATION] Collected {len(section_feedback)} feedback item(s) from section '{ps.sec.id}'"
            )

    # Phase 3: Transition-aware arranging - evaluate and apply
    # Analyze energy profiles between sections and generate transition plans.
    transition_plans = evaluate_transitions(cfg, plan, timelines, logger)

    # Apply transition plans to timelines (Phase 3: ramp_up, ramp_down)
    for transition_plan in transition_plans:
        if transition_plan.recipe.kind != "none":
            apply_transition_plan(
                timelines[transition_plan.instrument],
                transition_plan.instrument,
                transition_plan,
                logger
            )

    _log_section_timings(logger, list(plan.section_timings), bpm=float(cfg.song.bpm))
    _log_instrument_summary(logger, timelines)

    section_timings = list(plan.section_timings)

    # Sort timelines for deterministic export (Phase N2: reuse active instruments list)
    _sort_used_timelines(timelines, instruments_used)

    events_per_instrument = {k: len(v.events) for k, v in timelines.items()}

    if dry_run:
        logger.info("Dry run requested; not generating MIDI yet.")
        return BuildResult(
            song_name=song_name,
            dry_run=True,
            total_beats=float(plan.total_beats),
            plan=plan,
            performance_plan=performance_plan,
            export_root=None,
            section_timings=section_timings,
            instruments_used=instruments_used,
            events_per_instrument=events_per_instrument,
        )

    if not instruments_used:
        logger.warning("No instruments defined in any section; skipping MIDI export.")
        return BuildResult(
            song_name=song_name,
            dry_run=False,
            total_beats=float(plan.total_beats),
            plan=plan,
            performance_plan=performance_plan,
            export_root=None,
            section_timings=section_timings,
            instruments_used=instruments_used,
            events_per_instrument=events_per_instrument,
        )

    # Do exports
    export_root = _export_all(
        cfg=cfg,
        export_sections=export_sections,
        export_patterns=export_patterns,
        sections_absolute_timing=sections_absolute_timing,
        instruments_used=instruments_used,
        timelines=timelines,
        plan=plan,
        logger=logger,
    )

    return BuildResult(
        song_name=song_name,
        dry_run=False,
        total_beats=float(plan.total_beats),
        plan=plan,
        performance_plan=performance_plan,
        export_root=str(export_root),
        section_timings=section_timings,
        instruments_used=instruments_used,
        events_per_instrument=events_per_instrument,
    )
