"""Acoustic guitar engine for Produzre.

Steel-string acoustic guitar (GM program 25). Supports four playing techniques:

  fingerpicking  — arpeggiated patterns (Travis, PIMA, broken chord, waltz, roll)
  strumming      — chord sweeps with beat-grid density filtering
  hybrid         — fingerpicking in bar's first half, strum on second half
  percussive     — body taps + sparse chord stabs (breakdowns, spacious sections)

Technique is auto-selected by section type but overridable via instrument extra
params. Open-string voicings simulate 6-string resonance with octave doublings.

Public API:
    ENGINE_DEFAULT_PRIORITY, ENGINE_DEFAULT_CHANNEL, ENGINE_DEFAULT_PROGRAM
    ENGINE_REQUIRES, ENGINE_PROVIDES, ENGINE_ROLES
    contribute_plan()
    render_into_timeline()
"""

from __future__ import annotations

import logging
import random
from typing import Dict, Optional, Any

from ..bass import _get_mode_scale_offsets, _parse_roman_numeral
from ...model import RootConfig, SectionConfig
from ...harmony import HarmonySectionPlan
from ...rhythm import RhythmGrid
from ...timeline import InstrumentTimeline

from .defaults import (
    ENGINE_DEFAULT_PRIORITY,
    ENGINE_DEFAULT_CHANNEL,
    ENGINE_DEFAULT_PROGRAM,
    ENGINE_REQUIRES,
    ENGINE_PROVIDES,
    ENGINE_ROLES,
)
from .params import AcousticGuitarParams, resolve_params
from .voicings import choose_acoustic_voicing
from ...instruments.chord_shapes import ResolvedVoicing
from .patterns import get_pattern
from .articulation import (
    apply_finger_attack,
    calc_pick_duration,
    emit_body_tap,
    strum_spread_offsets,
)
from .strum import place_strum_hits


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


# ---------------------------------------------------------------------------
# MIDI root resolution (mirrors rhythm_gtr logic)
# ---------------------------------------------------------------------------

_KEY_TO_MIDI_ROOT: Dict[str, int] = {
    "C": 48, "C#": 49, "Db": 49, "D": 50, "D#": 51, "Eb": 51,
    "E": 52, "F": 53, "F#": 54, "Gb": 54, "G": 55, "G#": 56,
    "Ab": 56, "A": 57, "A#": 58, "Bb": 58, "B": 59,
}


def _resolve_root(cfg, section, numeral: str, instrument_cfg) -> int:
    """Compute root MIDI note for a chord numeral in guitar register."""
    key = (getattr(section, "key", None) or cfg.song.key or "C").strip()
    key = key.replace("♭", "b").replace("♯", "#")
    tonic_midi = _KEY_TO_MIDI_ROOT.get(key, 48)

    offsets = _get_mode_scale_offsets(getattr(cfg.song, "mode", None))
    degree_index, accidental = _parse_roman_numeral(numeral)
    if offsets:
        degree_index = max(0, min(degree_index, len(offsets) - 1))
        semitone = offsets[degree_index] + accidental
    else:
        semitone = 0

    return tonic_midi + semitone


def _slot_for_beat(harmony_plan: HarmonySectionPlan, beat: float):
    """Return the ChordSlot covering the given section-local beat position."""
    for cs in harmony_plan.chord_slots:
        if cs.start_beat <= beat < cs.end_beat:
            return cs
    # Past the last slot — return the final slot as a fallback
    if harmony_plan.chord_slots:
        return harmony_plan.chord_slots[-1]
    return None


def _pitch_for_pattern_hit(rv: ResolvedVoicing, hit) -> Optional[int]:
    """Map a PickHit's logical string index to a sounding MIDI pitch.

    Pattern string indices are LOGICAL positions on a fully-played 6-string
    chord (0 = lowest, 5 = highest). Real voicings mute strings (C/A/D
    shapes), so indices are remapped onto the PLAYED strings:

      - bass hits (``is_bass``) count up from the lowest played string, so
        Travis-style thumb alternation lands on the root and the next-lowest
        played string (root/5th alternation) instead of repeating the root;
      - treble (finger) hits count down from the highest played string
        (logical 5 = highest played, 4 = second-highest, ...).
    """
    played = rv.played_strings
    if not played:
        return None
    n = len(played)
    if hit.is_bass:
        s = played[min(max(0, hit.string_idx), n - 1)]
    else:
        from_top = max(0, 5 - hit.string_idx)
        s = played[max(0, n - 1 - from_top)]
    return rv.pitch_for_string(s)


# ---------------------------------------------------------------------------
# contribute_plan
# ---------------------------------------------------------------------------

def contribute_plan(
    cfg=None,
    section=None,
    instrument_name=None,
    instrument_cfg=None,
    harmony_plan=None,
    rhythm_grid=None,
    logger=None,
    **kwargs,
) -> Optional[Dict[str, Any]]:
    """Publish acoustic guitar density so other engines can apply inverse density.

    Contributes ``acoustic_rest_ratio.<section_id>`` to the PerformancePlan
    (Rule 1: when acoustic strums densely, rhythm/bass engines should thin out).
    """
    if logger is None:
        logger = logging.getLogger("produzre.acoustic_gtr")

    plan = kwargs.get("plan")
    if plan is None or section is None or instrument_cfg is None:
        return None

    try:
        params = resolve_params(section, instrument_cfg, rhythm_grid or _NullGrid())
        rest_ratio = max(0.0, min(0.95, 1.0 - params.strum_density))
        plan.set(f"acoustic_rest_ratio.{section.id}", rest_ratio)
        logger.debug(
            "[ACOUSTIC_PLAN] Section '%s': rest_ratio=%.2f technique=%s",
            section.id, rest_ratio, params.technique,
        )
    except Exception as exc:
        logger.debug("[ACOUSTIC_PLAN] Could not contribute plan for '%s': %s", section.id, exc)

    return None


class _NullGrid:
    """Minimal stub so resolve_params doesn't crash when rhythm_grid is None."""
    beats_per_bar = 4.0
    step_beats = 1.0


# ---------------------------------------------------------------------------
# render_into_timeline — public entry point
# ---------------------------------------------------------------------------

def render_into_timeline(
    cfg: Optional[RootConfig] = None,
    section: Optional[SectionConfig] = None,
    instrument_name: Optional[str] = None,
    instrument_cfg=None,
    harmony_plan: Optional[HarmonySectionPlan] = None,
    rhythm_grid: Optional[RhythmGrid] = None,
    section_start_beat: Optional[float] = None,
    timeline: Optional[InstrumentTimeline] = None,
    logger: Optional[logging.Logger] = None,
    **kwargs,
) -> None:
    """Render acoustic guitar into the section timeline.

    Dispatches to the appropriate technique renderer based on params.technique.
    Applies orchestration coordination (Rule 1 inverse density, Rule 4 accent
    velocity boost) when a PerformancePlan is available in kwargs.
    """
    # Support both positional and kwargs calling conventions
    if cfg is None:            cfg = kwargs.get("cfg")
    if section is None:        section = kwargs.get("section")
    if instrument_name is None: instrument_name = kwargs.get("instrument_name", "acoustic_gtr")
    if instrument_cfg is None:  instrument_cfg = kwargs.get("instrument_cfg") or kwargs.get("instrument")
    if harmony_plan is None:   harmony_plan = kwargs.get("harmony_plan")
    if rhythm_grid is None:    rhythm_grid = kwargs.get("rhythm_grid")
    if section_start_beat is None:
        section_start_beat = float(kwargs.get("section_start_beat", 0.0))
    if timeline is None:       timeline = kwargs.get("timeline")
    if logger is None:
        logger = kwargs.get("logger") or logging.getLogger("produzre.acoustic_gtr")

    rng: random.Random = kwargs.get("rng") or random.Random(42)
    plan = kwargs.get("plan")

    # --- Guard conditions ---
    if instrument_cfg is None or getattr(instrument_cfg, "enabled", None) is False:
        logger.debug("acoustic_gtr: disabled or missing config for section '%s'; skipping.",
                     section.id if section else "?")
        return

    if harmony_plan is None or not harmony_plan.chord_slots:
        logger.debug("acoustic_gtr: no harmony plan for section '%s'; skipping.",
                     section.id if section else "?")
        return

    if timeline is None:
        logger.warning("acoustic_gtr: no timeline provided; skipping.")
        return

    if rhythm_grid is None:
        rhythm_grid = _NullGrid()

    # --- Resolve params ---
    params = resolve_params(section, instrument_cfg, rhythm_grid)

    # --- Orchestration coordination ---
    coordinated_accent_beats: set = set()
    if plan is not None and section is not None:
        try:
            from ...orchestrate import EngineCoordinator
            coordinator = EngineCoordinator(plan, logger=logger)
            coordinated_accent_beats = coordinator.get_accent_beats(section.id)
            vel_adjustment = (
                coordinator.get_rhythm_intensity_adjustment(section.id)
                * coordinator.get_rhythm_simplification_factor(section.id)
            )
            vel_adjustment = max(0.4, min(vel_adjustment, 1.5))
            params.base_vel = max(20, min(110, int(params.base_vel * vel_adjustment)))
        except Exception as exc:
            logger.debug("[ACOUSTIC] Coordination error: %s", exc)

    # --- Pre-generate chord voicings (one per unique chord slot) ---
    chord_voicings: Dict[str, ResolvedVoicing] = {}
    prev_voicing: Optional[ResolvedVoicing] = None
    for cs in harmony_plan.chord_slots:
        root_midi = _resolve_root(cfg, section, cs.numeral, instrument_cfg)
        rv = choose_acoustic_voicing(
            root_midi=root_midi,
            numeral=cs.numeral,
            voicing_style=params.voicing_style,
            prev_voicing=prev_voicing,
            capo=params.capo,
        )
        chord_voicings[cs.numeral] = rv
        prev_voicing = rv

    # --- Section length ---
    bpb = params.beats_per_bar
    section_bars = max(1, getattr(section, "bars", 4) or 4)
    total_beats = float(bpb * section_bars)

    logger.debug(
        "acoustic_gtr: section='%s' technique='%s' pattern='%s' bars=%d density=%.2f vel=%d",
        section.id if section else "?",
        params.technique, params.picking_pattern, section_bars,
        params.strum_density, params.base_vel,
    )

    # --- Dispatch ---
    if params.technique == "fingerpicking":
        _render_fingerpicking(
            params, harmony_plan, chord_voicings,
            section_start_beat, total_beats, bpb,
            timeline, rng, coordinated_accent_beats,
        )
    elif params.technique == "strumming":
        _render_strumming(
            params, harmony_plan, chord_voicings,
            section_start_beat, total_beats, bpb,
            timeline, rng, coordinated_accent_beats,
        )
    elif params.technique == "hybrid":
        _render_hybrid(
            params, harmony_plan, chord_voicings,
            section_start_beat, total_beats, bpb,
            timeline, rng, coordinated_accent_beats,
        )
    elif params.technique == "percussive":
        _render_percussive(
            params, harmony_plan, chord_voicings,
            section_start_beat, total_beats, bpb,
            timeline, rng,
        )


# ---------------------------------------------------------------------------
# Technique renderers
# ---------------------------------------------------------------------------

def _render_fingerpicking(
    params: AcousticGuitarParams,
    harmony_plan: HarmonySectionPlan,
    chord_voicings: Dict[str, ResolvedVoicing],
    section_start_beat: float,
    total_beats: float,
    bpb: float,
    timeline: InstrumentTimeline,
    rng: random.Random,
    accent_beats: set,
) -> None:
    """Render arpeggiated fingerpicking bar by bar using a PickPattern."""
    pattern = get_pattern(params.picking_pattern, int(bpb))

    bar_start = 0.0
    while bar_start < total_beats:
        cs = _slot_for_beat(harmony_plan, bar_start)
        if cs is None:
            break

        rv = chord_voicings.get(cs.numeral)
        if rv is None:
            bar_start += bpb
            continue

        n_strings = rv.profile.num_strings

        for hit in pattern.hits:
            local_beat = bar_start + hit.beat
            if local_beat >= total_beats:
                break

            # Chord boundary: if this hit crosses into the next chord, update cs
            if local_beat >= cs.end_beat:
                next_cs = _slot_for_beat(harmony_plan, local_beat)
                if next_cs is None or next_cs is cs:
                    break
                cs = next_cs
                _new_rv = chord_voicings.get(cs.numeral)
                if _new_rv is not None:
                    rv = _new_rv
                n_strings = rv.profile.num_strings

            # Map the hit's logical string index onto the voicing's PLAYED
            # strings (bass hits from the bottom, treble hits from the top)
            # so alternating-bass patterns work on shapes with muted strings.
            pitch = _pitch_for_pattern_hit(rv, hit)
            if pitch is None:
                continue

            # Legato duration: sustain until next hit on the SAME string
            next_same_beat = _next_same_string_beat(
                pattern, hit, local_beat, bar_start, bpb, n_strings,
                cs.end_beat, total_beats,
            )
            duration = calc_pick_duration(local_beat, next_same_beat, cs.end_beat, hit.is_bass)

            # Velocity: finger attack shaping
            is_downbeat = (hit.beat < 0.01)
            vel = apply_finger_attack(
                base_vel=max(20, int(params.base_vel * hit.vel_ratio)),
                is_bass=hit.is_bass,
                is_downbeat=is_downbeat,
                vel_variation=params.vel_variation,
                rng=rng,
            )

            # Rule 4: velocity boost on coordinated drum accent beats
            bar_beat_pos = round(local_beat % bpb, 2)
            if bar_beat_pos in accent_beats:
                vel = min(127, int(vel * 1.15))

            # Timing humanization
            timing_offset = rng.uniform(-params.timing_variation, params.timing_variation)
            abs_start = max(section_start_beat, section_start_beat + local_beat + timing_offset)

            timeline.add_note(
                start_beat=abs_start,
                duration_beats=max(0.05, duration),
                pitch=pitch,
                velocity=max(20, min(127, vel)),
                channel=None,
                kind="acoustic_pick",
            )

        # Occasional body tap (very rare in fingerpicking — just texture)
        if params.body_tap_ratio > 0.0 and rng.random() < params.body_tap_ratio * 0.08:
            tap_beat = bar_start + bpb * 0.625  # ~beat 2.5 in 4/4
            if tap_beat < total_beats:
                emit_body_tap(tap_beat, section_start_beat, params.base_vel, rng, timeline)

        bar_start += bpb


def _next_same_string_beat(
    pattern, current_hit, current_local_beat: float,
    bar_start: float, bpb: float,
    n_strings: int, chord_end: float, total_beats: float,
) -> float:
    """Find the next beat where the same string index is hit again."""
    current_sidx = max(0, min(current_hit.string_idx, n_strings - 1))

    # Search remaining hits in the current bar
    for future_hit in pattern.hits:
        future_local = bar_start + future_hit.beat
        if future_local > current_local_beat + 0.001:
            if max(0, min(future_hit.string_idx, n_strings - 1)) == current_sidx:
                return min(future_local, chord_end, total_beats)

    # Fall back to the same hit in the next bar
    for future_hit in pattern.hits:
        if max(0, min(future_hit.string_idx, n_strings - 1)) == current_sidx:
            next_bar_beat = bar_start + bpb + future_hit.beat
            return min(next_bar_beat, chord_end, total_beats)

    return min(chord_end, total_beats)


def _render_strumming(
    params: AcousticGuitarParams,
    harmony_plan: HarmonySectionPlan,
    chord_voicings: Dict[str, ResolvedVoicing],
    section_start_beat: float,
    total_beats: float,
    bpb: float,
    timeline: InstrumentTimeline,
    rng: random.Random,
    accent_beats: set,
) -> None:
    """Render chord strumming bar by bar using a quarter-note density grid.

    Each bar is split into chord segments so mid-bar chord changes strum the
    NEW chord from its own start beat instead of riding the bar-start chord
    through the whole bar.
    """
    prev_cs_numeral: Optional[str] = None
    eps = 1e-9

    bar_start = 0.0
    while bar_start < total_beats:
        bar_end = min(bar_start + bpb, total_beats)

        seg_start = bar_start
        while seg_start < bar_end - eps:
            cs = _slot_for_beat(harmony_plan, seg_start)
            if cs is None:
                break

            seg_end = min(bar_end, cs.end_beat)
            if seg_end <= seg_start + eps:
                seg_end = bar_end  # past the final slot — finish the bar

            _rv = chord_voicings.get(cs.numeral)
            pitches = _rv.pitches if _rv is not None else []
            is_chord_change = (cs.numeral != prev_cs_numeral)
            prev_cs_numeral = cs.numeral

            if not pitches:
                seg_start = seg_end
                continue

            events = place_strum_hits(
                voicing_pitches=pitches,
                beats_per_bar=seg_end - seg_start,
                bar_start_beat=seg_start,
                strum_density=params.strum_density,
                mute_ratio=params.mute_ratio,
                base_vel=params.base_vel,
                is_chord_change=is_chord_change,
                rng=rng,
            )

            for (abs_beat, pitch, vel, dur) in events:
                if abs_beat >= total_beats:
                    continue

                # Clamp duration to chord boundary
                max_dur = max(0.08, cs.end_beat - abs_beat)
                dur = min(dur, max_dur)

                # Rule 4: coordinated accent boost
                bar_beat_pos = round(abs_beat % bpb, 2)
                if bar_beat_pos in accent_beats:
                    vel = min(127, int(vel * 1.12))

                # Light timing humanization (strums commit to the beat more than picks)
                timing_offset = rng.uniform(
                    -params.timing_variation * 0.5,
                    params.timing_variation * 0.5,
                )
                abs_start = section_start_beat + abs_beat + timing_offset

                timeline.add_note(
                    start_beat=abs_start,
                    duration_beats=max(0.08, dur),
                    pitch=pitch,
                    velocity=max(20, min(127, vel)),
                    channel=None,
                    kind="acoustic_strum",
                )

            seg_start = seg_end

        bar_start += bpb


def _render_hybrid(
    params: AcousticGuitarParams,
    harmony_plan: HarmonySectionPlan,
    chord_voicings: Dict[str, ResolvedVoicing],
    section_start_beat: float,
    total_beats: float,
    bpb: float,
    timeline: InstrumentTimeline,
    rng: random.Random,
    accent_beats: set,
) -> None:
    """Render hybrid technique: arpeggio in first bar half, strum in second half.

    This creates the feel of a guitarist who opens each bar with a flowing
    arpeggio, then locks in with a rhythmic strum on the backbeat.
    """
    half = bpb / 2.0
    pattern = get_pattern(params.picking_pattern, int(bpb))
    prev_cs_numeral: Optional[str] = None

    bar_start = 0.0
    while bar_start < total_beats:
        cs = _slot_for_beat(harmony_plan, bar_start)
        if cs is None:
            break

        rv = chord_voicings.get(cs.numeral)
        is_chord_change = (cs.numeral != prev_cs_numeral)
        prev_cs_numeral = cs.numeral

        if rv is None or not rv.pitches:
            bar_start += bpb
            continue

        # ---- First half: fingerpicking hits that start before the bar midpoint ----
        for hit in pattern.hits:
            local_beat = bar_start + hit.beat
            if local_beat >= bar_start + half:
                break
            if local_beat >= total_beats:
                break

            # Mid-bar chord change: switch to the chord covering this hit.
            if local_beat >= cs.end_beat:
                next_cs = _slot_for_beat(harmony_plan, local_beat)
                if next_cs is not None and next_cs is not cs:
                    cs = next_cs
                    _new_rv = chord_voicings.get(cs.numeral)
                    if _new_rv is not None:
                        rv = _new_rv

            # Map the hit's logical string index onto PLAYED strings (same
            # contract as fingerpicking) — indexing the sorted pitch list with
            # a physical string index broke shapes with muted strings.
            pitch = _pitch_for_pattern_hit(rv, hit)
            if pitch is None:
                continue

            # Duration caps at the midpoint (where the strum takes over)
            next_same = bar_start + half
            duration = calc_pick_duration(local_beat, next_same, cs.end_beat, hit.is_bass)

            is_downbeat = (hit.beat < 0.01)
            vel = apply_finger_attack(
                base_vel=max(20, int(params.base_vel * hit.vel_ratio)),
                is_bass=hit.is_bass,
                is_downbeat=is_downbeat,
                vel_variation=params.vel_variation,
                rng=rng,
            )
            timing_offset = rng.uniform(-params.timing_variation, params.timing_variation)

            timeline.add_note(
                start_beat=section_start_beat + local_beat + timing_offset,
                duration_beats=max(0.05, duration),
                pitch=pitch,
                velocity=max(20, min(127, vel)),
                channel=None,
                kind="acoustic_hybrid_pick",
            )

        # ---- Second half: strum hit at the bar midpoint ----
        strum_beat = bar_start + half
        # Resolve the chord covering the strum position (it may differ from
        # the chord at the bar start when chords change mid-bar).
        cs_strum = _slot_for_beat(harmony_plan, strum_beat)
        rv_strum = chord_voicings.get(cs_strum.numeral) if cs_strum is not None else None
        if (
            strum_beat < total_beats
            and cs_strum is not None
            and strum_beat < cs_strum.end_beat
            and rv_strum is not None
            and rv_strum.pitches
        ):
            pitches = rv_strum.pitches
            n = len(pitches)
            offsets = strum_spread_offsets(n, "down", 0.020)
            strum_vel = params.base_vel + (6 if is_chord_change else 2) + rng.randint(-6, 6)
            strum_vel = max(25, min(127, strum_vel))
            remaining = max(0.08, min(half, cs_strum.end_beat - strum_beat))

            for pitch, offset in zip(pitches, offsets):
                if strum_beat + offset >= total_beats:
                    break
                dur = max(0.08, remaining - offset)
                timeline.add_note(
                    start_beat=section_start_beat + strum_beat + offset,
                    duration_beats=dur,
                    pitch=pitch,
                    velocity=strum_vel,
                    channel=None,
                    kind="acoustic_hybrid_strum",
                )

        bar_start += bpb


def _render_percussive(
    params: AcousticGuitarParams,
    harmony_plan: HarmonySectionPlan,
    chord_voicings: Dict[str, ResolvedVoicing],
    section_start_beat: float,
    total_beats: float,
    bpb: float,
    timeline: InstrumentTimeline,
    rng: random.Random,
) -> None:
    """Render sparse percussive texture: downbeat stab + body tap + optional strum.

    Simulates a guitarist providing rhythmic texture with muted chops and body
    percussion rather than full chordal playing. Appropriate for breakdowns and
    spacious arrangement sections.
    """
    bar_start = 0.0
    while bar_start < total_beats:
        cs = _slot_for_beat(harmony_plan, bar_start)
        if cs is None:
            break

        _rv = chord_voicings.get(cs.numeral)
        pitches = _rv.pitches if _rv is not None else []

        # Sparse downbeat chord stab (always — the anchor hit)
        if pitches and bar_start < cs.end_beat:
            vel = max(20, min(127, int(params.base_vel * 0.65) + rng.randint(-5, 5)))
            n = len(pitches)
            offsets = strum_spread_offsets(n, "down", 0.018)
            stab_dur = max(0.08, min(bpb * 0.22, cs.end_beat - bar_start))

            for pitch, offset in zip(pitches, offsets):
                if bar_start + offset >= total_beats:
                    break
                timeline.add_note(
                    start_beat=section_start_beat + bar_start + offset,
                    duration_beats=stab_dur,
                    pitch=pitch,
                    velocity=vel,
                    channel=None,
                    kind="acoustic_perc_chord",
                )

        # Body tap on the backbeat (beat 2.5 in 4/4, or 60% through the bar)
        tap_beat = bar_start + min(2.5, bpb * 0.62)
        if tap_beat < total_beats:
            emit_body_tap(tap_beat, section_start_beat, params.base_vel, rng, timeline)

        # Optional strum near beat 3 / 75% (40% probability for variety)
        strum_beat = bar_start + min(3.0, bpb * 0.75)
        if strum_beat < total_beats and rng.random() < 0.40:
            # Resolve the chord covering the strum position (mid-bar changes)
            cs_strum = _slot_for_beat(harmony_plan, strum_beat)
            rv_strum = chord_voicings.get(cs_strum.numeral) if cs_strum is not None else None
            strum_pitches = rv_strum.pitches if rv_strum is not None else []
            if strum_pitches and cs_strum is not None and strum_beat < cs_strum.end_beat:
                vel = max(20, min(127, int(params.base_vel * 0.75) + rng.randint(-5, 5)))
                n = len(strum_pitches)
                offsets = strum_spread_offsets(n, "down", 0.018)
                # Ring until the end of the bar (or chord), whichever is sooner
                remaining = max(
                    0.08,
                    min(bpb - (strum_beat - bar_start), cs_strum.end_beat - strum_beat),
                )

                for pitch, offset in zip(strum_pitches, offsets):
                    if strum_beat + offset >= total_beats:
                        break
                    timeline.add_note(
                        start_beat=section_start_beat + strum_beat + offset,
                        duration_beats=remaining,
                        pitch=pitch,
                        velocity=vel,
                        channel=None,
                        kind="acoustic_perc_strum",
                    )

        bar_start += bpb
