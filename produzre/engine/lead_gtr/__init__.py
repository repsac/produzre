"""Lead guitar engine for Produzre (Phase LG6).

This engine generates modest melodic lead guitar lines with:
- Harmony-driven pitch selection (chord tones + safe scale neighbours)
- Motif-based phrase generation (repeating ideas with light variation)
- Rhythm-grid-aware note placement that breathes with the groove
- Accent avoidance so the lead doesn't double-hit drums / rhythm guitar
- Register management: octave wrapping keeps notes in a playable range
- Chorus lift: first phrase of a chorus shifts up an octave when possible
- Simple articulations: sustain, staccato, slide_hint
- Humanisation: small timing jitter + velocity variance for life
- Solo mode: higher density, wider leaps, longer phrases when solo=True
- Stepwise voice-leading within phrases
- Call-and-response phrasing for bridge sections

Public API:
    - ENGINE_DEFAULT_PRIORITY: Execution priority (after rhythm section)
    - ENGINE_DEFAULT_CHANNEL: MIDI channel
    - ENGINE_DEFAULT_PROGRAM: GM program number
    - ENGINE_REQUIRES: Dependencies on other plan data
    - ENGINE_PROVIDES: Plan data provided by this engine
    - ENGINE_ROLES: Engine roles
    - contribute_plan(): Optional plan contribution
    - render_into_timeline(): Main rendering function
"""

from __future__ import annotations

import logging
import hashlib
import random
from typing import Optional, List, Dict, Any

from ...model import RootConfig, SectionConfig
from ...harmony import HarmonySectionPlan
from ...rhythm import RhythmGrid
from ...timeline import InstrumentTimeline

# Phase LG0: Import defaults and types
from .defaults import (
    ENGINE_DEFAULT_PRIORITY,
    ENGINE_DEFAULT_CHANNEL,
    ENGINE_DEFAULT_PROGRAM,
    ENGINE_REQUIRES,
    ENGINE_PROVIDES,
    ENGINE_ROLES,
    DEFAULT_REGISTER,
)

# Phase LG1: Harmony-driven pitch selection
from .pitch import allowed_pitches_for_slot

# Phase LG2: Motif-based phrase generation
from .phrasing import make_motif, develop_motif, realize_phrase

# Phase LG3: Rhythm-aware note placement
from .rhythm import choose_note_starts

# Phase LG4: Register + range management
from .register import get_register_bounds, octave_wrap_if_needed, apply_lift

# Phase LG5: Articulation + humanisation
from .articulation import choose_articulation, apply_articulation
from .humanize import humanize_note

logger = logging.getLogger(__name__)


# Phase LG0: Export engine metadata
__all__ = [
    "ENGINE_DEFAULT_PRIORITY",
    "ENGINE_DEFAULT_CHANNEL",
    "ENGINE_DEFAULT_PROGRAM",
    "ENGINE_REQUIRES",
    "ENGINE_PROVIDES",
    "ENGINE_ROLES",
    "contribute_plan",
    "render_into_timeline",
]


def _stable_u32(text: str) -> int:
    """Return a stable 32-bit integer hash for a string (cross-run stable)."""
    return int.from_bytes(hashlib.md5(text.encode("utf-8")).digest()[:4], "little")






def _group_slots_by_phrase(chord_slots, phrase_len_beats):
    """Group chord slots into phrase-length windows.

    Returns list of (phrase_start, phrase_end, [slots_in_phrase]).
    """
    if not chord_slots:
        return []

    section_end = chord_slots[-1].end_beat
    phrases = []
    phrase_idx = 0

    while phrase_idx * phrase_len_beats < section_end:
        p_start = phrase_idx * phrase_len_beats
        p_end = p_start + phrase_len_beats
        slots_in = [cs for cs in chord_slots if cs.start_beat < p_end and cs.end_beat > p_start]
        if slots_in:
            phrases.append((p_start, min(p_end, section_end), slots_in))
        phrase_idx += 1
        if phrase_idx > 200:  # safety against infinite loop
            break

    return phrases


def contribute_plan(
    cfg: Optional[RootConfig] = None,
    section: Optional[SectionConfig] = None,
    instrument_name: Optional[str] = None,
    instrument_cfg = None,
    harmony_plan: Optional[HarmonySectionPlan] = None,
    rhythm_grid: Optional[RhythmGrid] = None,
    logger: Optional[logging.Logger] = None,
    **kwargs,
) -> Optional[Dict[str, Any]]:
    """Contribute plan data for lead guitar (Sprint 4 - rest ratio for coordination).

    Analyzes lead guitar configuration to estimate rest ratio and contribute it
    to the PerformancePlan. This allows rhythm engine to implement inverse density
    coordination (Rule 1: when lead rests, rhythm fills).

    Args:
        cfg: Root configuration
        section: Section configuration
        instrument_name: Instrument name
        instrument_cfg: Instrument configuration
        harmony_plan: Harmony plan for the section
        rhythm_grid: Rhythm grid for the section
        logger: Logger instance
        **kwargs: Additional arguments (includes 'plan' for PerformancePlan)

    Returns:
        Optional dict of plan contributions (None in Phase LG0)
    """
    if logger is None:
        logger = logging.getLogger("produzre.lead_gtr")

    # Sprint 4: Contribute rest_ratio for inverse density coordination
    plan = kwargs.get("plan")
    if plan is not None and section is not None and instrument_cfg is not None:
        ensemble = plan.get(f"ensemble.{section.id}", {})
        planned_rest = ensemble.get("lead_rest_ratio") if isinstance(ensemble, dict) else None
        # Read rest_probability from config (same logic as render)
        rest_probability = getattr(instrument_cfg, "rest_probability", None)
        if rest_probability is None:
            rest_probability = instrument_cfg.extra.get("rest_probability", None)

        # Use rest_probability as a proxy for rest_ratio
        # This is the configured "target" rest ratio that lead will aim for
        rest_probability = planned_rest if planned_rest is not None else rest_probability
        if rest_probability is not None:
            try:
                rest_ratio = float(rest_probability)
                rest_ratio = max(0.0, min(rest_ratio, 0.85))

                # Store in plan for rhythm engine to read
                plan_key = f"lead_rest_ratio.{section.id}"
                plan.set(plan_key, rest_ratio)

                if logger:
                    logger.debug(
                        f"[LEAD_PLAN] Section '{section.id}': rest_ratio={rest_ratio:.2f} "
                        f"(from rest_probability config)"
                    )
            except Exception as e:
                if logger:
                    logger.debug(
                        f"[LEAD_PLAN] Failed to parse rest_probability for '{section.id}': {e}"
                    )

    return None


def render_into_timeline(
    cfg: RootConfig,
    section: SectionConfig,
    instrument_name: str,
    instrument_cfg,
    harmony_plan: Optional[HarmonySectionPlan],
    rhythm_grid: RhythmGrid,
    section_start_beat: float,
    timeline: InstrumentTimeline,
    logger: logging.Logger,
    **kwargs,
) -> None:
    """Render a simple melodic lead guitar line for a section.

    Lead behavior in this V1 implementation:

    - Only runs if a 'lead' instrument config exists and is enabled.
    - Follows the section's harmony plan (chord numerals).
    - Places 1–4 notes per chord slot depending on intensity band and solo flag.
    - Uses the rhythm grid for timing; notes are aligned to grid cells within
      each chord span.
    - Keeps pitches in a melodic register above rhythm guitar using a small
      note pool built around the chord root.
    """
    # Validate instrument configuration passed in from CLI engine dispatcher
    if instrument_cfg is None or getattr(instrument_cfg, "enabled", True) is False:
        logger.debug(
            "Section '%s': instrument '%s' disabled or missing; skipping.",
            section.id,
            instrument_name,
        )
        return

    if harmony_plan is None or not harmony_plan.chord_slots:
        logger.debug("Section '%s': no harmony plan; skipping lead guitar.", section.id)
        return

    # Effective intensity with style bias.
    raw_intensity = instrument_cfg.intensity
    style_bias = getattr(instrument_cfg, "style_bias", None)
    if raw_intensity is None:
        # Macro-dynamics: fall back to the section's resolved intensity
        # (orchestrate.plan.resolve_section_intensity) before the default.
        raw_intensity = getattr(section, "intensity", None)
    if raw_intensity is None:
        raw_intensity = 1.0
    if style_bias is None:
        style_bias = 0.0
    intensity = raw_intensity + style_bias
    intensity = max(0.0, min(intensity, 2.0))

    if intensity <= 0.33:
        intensity_band = "low"
    elif intensity <= 0.66:
        intensity_band = "mid"
    else:
        intensity_band = "high"

    offset_beats = instrument_cfg.offset_beats
    if offset_beats is None:
        offset_beats = 0.0

    register = getattr(instrument_cfg, "register", None)
    solo = bool(getattr(instrument_cfg, "solo", False))
    role = getattr(instrument_cfg, "role", None)
    if role == "lead":
        solo = True

    # Slightly boost intensity/velocity for true solo sections.
    base_vel = int(80 * max(0.3, min(intensity, 1.5)))
    if solo:
        base_vel = min(118, base_vel + 10)

    bpb = rhythm_grid.beats_per_bar
    eps = 1e-6

    # Phrase/motif controls: repeat a recognizable motif per phrase.
    # Solo sections default to longer phrases (4 bars) for more room to breathe.
    phrase_len_bars = getattr(instrument_cfg, "phrase_len_bars", None)
    if phrase_len_bars is None:
        phrase_len_bars = instrument_cfg.extra.get("phrase_len_bars", None)
    if phrase_len_bars is None:
        phrase_len_bars = 4 if solo else 2
    try:
        phrase_len_bars = int(phrase_len_bars)
    except Exception:
        phrase_len_bars = 4 if solo else 2
    phrase_len_bars = max(1, phrase_len_bars)

    # Rhythm feel controls (rests + syncopation).
    rest_probability = getattr(instrument_cfg, "rest_probability", None)
    if rest_probability is None:
        rest_probability = instrument_cfg.extra.get("rest_probability", None)
    if rest_probability is None:
        # Default: more space in verses, less space in solos.
        if solo:
            rest_probability = 0.10
        elif intensity_band == "high":
            rest_probability = 0.15
        elif intensity_band == "mid":
            rest_probability = 0.25
        else:
            rest_probability = 0.35
    try:
        rest_probability = float(rest_probability)
    except Exception:
        rest_probability = 0.25
    rest_probability = max(0.0, min(rest_probability, 0.85))

    phrase_len_beats = float(phrase_len_bars) * float(bpb)

    # Resolve key/mode and use the orchestrator's instrument RNG so take,
    # variation, arrangement occurrence, and instrument seed all participate.
    song_key = (section.key or cfg.song.key or "C").strip()
    song_mode = getattr(cfg.song, "mode", None) or "minor"
    song_seed = getattr(cfg.song, "seed", 42)
    section_rng = kwargs.get("rng") or random.Random(_stable_u32(f"lead:{section.id}:{song_seed}"))
    song_genre = str(getattr(cfg.song, "genre", "") or "")

    # Resolution behavior: encourage landing on chord tones at chord/phrase ends.
    resolution_strength = getattr(instrument_cfg, "resolution_strength", None)
    if resolution_strength is None:
        resolution_strength = instrument_cfg.extra.get("resolution_strength", None)
    if resolution_strength is None:
        resolution_strength = 0.55 if solo else 0.35
    try:
        resolution_strength = float(resolution_strength)
    except Exception:
        resolution_strength = 0.35
    resolution_strength = max(0.0, min(resolution_strength, 1.0))

    # Phase LG2: phrase-level controls.
    vary_last = resolution_strength > 0.3
    section_type = getattr(section, "type", "") or ""
    call_and_response = (section_type.lower() == "bridge")
    dur_scale = 0.78 if solo else 0.90

    # Phase LG3: extract accent beats from plan for grid-aware placement.
    plan = kwargs.get("plan", None)
    accent_beats: List[float] = []
    density_multiplier = 1.0
    if plan is not None:
        accents_data = plan.get("rhythm.accents") if hasattr(plan, "get") else {}
        if isinstance(accents_data, dict):
            accent_beats = accents_data.get("accent_beats", [])
        try:
            from ...orchestrate import EngineCoordinator
            coordinator = EngineCoordinator(plan, logger=logger)
            actual_accents = coordinator.get_accent_beats(section.id)
            if actual_accents:
                accent_beats = sorted(actual_accents)
            density_multiplier = coordinator.get_density_multiplier(section.id, "lead_gtr")
            lead_activity_windows = coordinator.get_lead_activity_windows(section.id)
        except Exception:
            lead_activity_windows = []
    else:
        lead_activity_windows = []

    # Density: how many grid positions to fill (scales with intensity).
    # Solo sections use a higher base multiplier and bigger boost.
    if solo:
        density = intensity * 0.65 + 0.25
    else:
        density = intensity * 0.55 + 0.15
    density *= density_multiplier
    density = max(0.10, min(density, 0.90))

    # prefer_offbeat: chorus / high-intensity sections contrast the downbeat grid.
    prefer_offbeat = (intensity_band == "high") or (section_type.lower() == "chorus")

    # Phase LG6: solo leap limit — wider melodic range for solo sections.
    # Can be overridden via contour_style parameter.
    contour_style = getattr(instrument_cfg, "contour_style", None)
    if contour_style is None:
        contour_style = instrument_cfg.extra.get("contour_style", None)

    # Map contour_style to leap_limit
    if contour_style == "stepwise":
        phrase_leap_limit = 3  # Small intervals, smooth voice leading
    elif contour_style == "leaping":
        phrase_leap_limit = 9  # Large intervals, wide melodic range
    elif contour_style == "balanced":
        phrase_leap_limit = 5  # Moderate intervals (default)
    else:
        # Default behavior: wider leaps in solo sections
        phrase_leap_limit = 8 if solo else 5

    # Phase LG4: resolve register bounds and chorus-lift flag.
    reg_min, reg_max = get_register_bounds(register or DEFAULT_REGISTER)
    # Chorus lift: shift first phrase up an octave if it stays in range.
    chorus_lift = (section_type.lower() == "chorus")

    if logger:
        numerals_summary = " ".join(cs.numeral for cs in harmony_plan.chord_slots)
        logger.debug(
            "Section '%s': lead guitar harmony numerals: %s",
            section.id,
            numerals_summary,
        )

    events_before = len(timeline.events)

    # Phase LG2: group chord slots into phrase-length windows.
    phrases = _group_slots_by_phrase(harmony_plan.chord_slots, phrase_len_beats)

    base_motif = make_motif(section_rng, intensity, genre=song_genre)

    for phrase_idx, (phrase_start, phrase_end, slots_in_phrase) in enumerate(phrases):
        phrase_beats = phrase_end - phrase_start
        if phrase_beats <= eps:
            continue

        # Reuse and develop a motif across phrases so the line has identity.
        motif = develop_motif(
            base_motif,
            section_rng,
            phrase_index=phrase_idx,
            is_final_phrase=(phrase_idx == len(phrases) - 1),
            intensity=intensity,
            total_phrases=len(phrases),
        )

        # Collect one pitch pool per chord slot in this phrase.
        pools = []
        for cs in slots_in_phrase:
            pool = allowed_pitches_for_slot(
                cs.numeral, song_key, song_mode, register or DEFAULT_REGISTER, genre=song_genre
            )
            pools.append(pool)

        if not pools:
            continue

        # Realize the motif across this phrase (provides pitch sequence).
        # Phase LG6: solo sections allow wider leaps between anchors.
        resolved_notes = realize_phrase(
            motif, pools, phrase_beats, section_rng,
            vary_last=vary_last,
            call_and_response=call_and_response,
            leap_limit=phrase_leap_limit,
        )

        if not resolved_notes:
            continue

        # Phase LG3: choose grid positions that breathe with the groove.
        # These are used as a MASK over the motif's own rhythm (rest/breathing
        # decisions) — the realized motif keeps its beat offsets and durations
        # so its rhythmic identity stays audible.
        note_starts = choose_note_starts(
            grid=rhythm_grid,
            accent_beats=accent_beats,
            density=density,
            rng=section_rng,
            phrase_start=phrase_start,
            phrase_end=phrase_end,
            prefer_offbeat=prefer_offbeat,
            rest_rate=rest_probability,
            genre=song_genre,
        )

        if not note_starts:
            continue

        allowed_slots = {round(s, 2) for s in note_starts}

        # Mask motif notes through the chosen grid slots. The first and last
        # notes of the phrase are always kept: the first anchors the motif,
        # the last carries the vary_last chord-tone resolution.
        emit_notes = []
        for rn_idx, rn in enumerate(resolved_notes):
            start_local = phrase_start + rn.beat_offset
            if start_local >= phrase_end - eps:
                continue
            is_edge = rn_idx == 0 or rn_idx == len(resolved_notes) - 1
            if not is_edge and round(start_local, 2) not in allowed_slots:
                continue
            emit_notes.append(rn)
        if not emit_notes:
            emit_notes = [resolved_notes[0]]

        # Phase LG4: apply chorus lift on the first phrase of a chorus section.
        is_first_phrase = (phrase_start < eps)
        lift_this_phrase = chorus_lift and is_first_phrase

        # Emit motif notes at their own beat offsets/durations within the phrase.
        for note_idx, rn in enumerate(emit_notes):
            local_beat = phrase_start + rn.beat_offset

            if lead_activity_windows and not any(
                start <= local_beat < end for start, end in lead_activity_windows
            ):
                continue

            # The motif's own duration, scaled for articulation space and
            # clamped to the phrase (and therefore section) bounds.
            duration = min(rn.duration * dur_scale, phrase_end - local_beat)
            duration = max(0.1, duration)

            song_beat = section_start_beat + local_beat + offset_beats

            # Phase LG4: register management — wrap into range, optional lift.
            pitch = rn.pitch
            if lift_this_phrase:
                pitch = apply_lift(pitch, reg_min, reg_max)
            pitch = octave_wrap_if_needed(pitch, reg_min, reg_max)

            # Phase LG5: articulation — shape duration, optional grace note.
            art = choose_articulation(section_rng, intensity)
            arted = apply_articulation(pitch, duration, art, section_rng)

            # Per-hit velocity shaping.
            vel = base_vel
            if solo and bpb > eps:
                pos_in_bar = local_beat % bpb
                is_onbeat = abs(pos_in_bar - round(pos_in_bar)) < 1e-3
                if not is_onbeat:
                    vel = int(vel * 1.06)
            if intensity_band == "low":
                vel = int(vel * 0.9)
            elif intensity_band == "high":
                if note_idx == 0:
                    vel = int(vel * 1.05)
                else:
                    vel = int(vel * 0.95)

            if solo:
                vel = int(vel * 1.05)

            vel = max(20, min(127, vel))

            # Slide grace note handling. At the register bottom there is no
            # lower neighbour to slide from — skip the slide instead of
            # octave-wrapping the grace 11 semitones ABOVE the target.
            grace_pitch = arted.grace_pitch
            main_dur = arted.duration
            if grace_pitch is not None and pitch <= reg_min:
                grace_pitch = None
                main_dur = arted.duration + arted.grace_duration
            if grace_pitch is not None:
                # Clamp (never wrap) the grace below the main note.
                grace_pitch = max(reg_min, grace_pitch)
                # The grace no longer eats into the main note's span: it is
                # played BEFORE the beat so the main note lands on the beat.
                main_dur = arted.duration + arted.grace_duration

            # Phase LG5: humanize main note timing + velocity.
            song_beat, h_dur, vel = humanize_note(
                song_beat, main_dur, vel, section_rng, intensity
            )

            # Emit the grace note leading INTO the (humanized) main note.
            if grace_pitch is not None:
                grace_start = max(section_start_beat, song_beat - arted.grace_duration)
                grace_dur = song_beat - grace_start
                if grace_dur > 0.01:
                    grace_vel = max(20, min(127, int(vel * 0.70)))
                    timeline.add_note(
                        start_beat=grace_start,
                        duration_beats=grace_dur,
                        pitch=grace_pitch,
                        velocity=grace_vel,
                        channel=None,
                    )

            timeline.add_note(
                start_beat=song_beat,
                duration_beats=h_dur,
                pitch=pitch,
                velocity=vel,
                channel=None,
            )

    added = len(timeline.events) - events_before
    logger.debug(
        "Section '%s': added %d lead guitar events (intensity=%.2f, solo=%s)",
        section.id,
        added,
        intensity,
        solo,
    )
