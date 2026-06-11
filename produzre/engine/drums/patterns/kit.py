"""Drum kit orchestration and main pattern generation API.

This module owns the DrumEvent dataclass and the main events_for_section_from_template()
function, which orchestrates all voice modules to generate a complete drum pattern.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from ..groove import GrooveTemplate, hat_steps_for_mode
from .cymbals import generate_crash_events, generate_ride_bell_events, generate_splash_china_events
from .grid import bars_total, step_beats
from .hats import generate_top_cymbal_events
from .kick import eligible_double_kick_steps, eligible_syncopation_steps, generate_kick_events
from .snare import generate_snare_events
from .toms import generate_tom_events, generate_tom_fill_run

__all__ = ["DrumEvent", "events_for_section_from_template"]


def _apply_transition_effects(
    *,
    events: List[DrumEvent],
    transition_context: Dict[str, Any],
    total_beats: float,
    sb: float,
    base_velocity: int,
    accent_strength: float,
    rng: random.Random,
    pitches: Dict[str, int],
) -> List[DrumEvent]:
    """Apply transition effects (pickups, downbeat punctuation) based on section boundaries.

    Args:
        events: Current drum events for the section.
        transition_context: Dict with prev_section_type, next_section_type, is_first_section, is_last_section.
        total_beats: Section duration in beats.
        sb: Step duration in beats.
        base_velocity: Base velocity for new events.
        accent_strength: Accent strength for velocity calculation.
        rng: Deterministic RNG.
        pitches: Pitch mapping.

    Returns:
        Modified event list with transition effects applied.
    """
    section_type = transition_context.get("section_type")
    prev_section_type = transition_context.get("prev_section_type")
    next_section_type = transition_context.get("next_section_type")
    is_first_section = transition_context.get("is_first_section", False)
    pickup_rate = float(transition_context.get("pickup_rate", 0.7))
    downbeat_rate = float(transition_context.get("downbeat_rate", 0.8))
    current_energy = transition_context.get("current_energy")
    prev_energy = transition_context.get("prev_energy")
    next_energy = transition_context.get("next_energy")
    try:
        energy_delta_next = float(next_energy) - float(current_energy)
    except Exception:
        energy_delta_next = 0.0
    try:
        energy_delta_in = float(current_energy) - float(prev_energy)
    except Exception:
        energy_delta_in = 0.0

    new_events = list(events)

    # Downbeat punctuation: Add crash + kick on first beat when section type changes.
    # Skip first section (no previous to transition from).
    # Controlled by downbeat_rate parameter.
    if (not is_first_section
        and prev_section_type is not None
        and prev_section_type != section_type
        and rng.random() < downbeat_rate):
        # Detect if there's already a crash at beat 0
        has_crash_at_start = any(e.beat < 0.01 and e.pitch == pitches.get("crash", 49) for e in events)
        has_kick_at_start = any(e.beat < 0.01 and e.pitch == pitches.get("kick", 36) for e in events)

        if not has_crash_at_start:
            # Add crash on downbeat
            crash_velocity = int(base_velocity + accent_strength * 20 + abs(energy_delta_in) * 18)
            crash_velocity = max(60, min(127, crash_velocity))
            new_events.append(
                DrumEvent(
                    beat=0.0,
                    duration_beats=0.5,
                    pitch=pitches.get("crash", 49),
                    velocity=crash_velocity,
                    kind="crash_transition",
                )
            )

        if not has_kick_at_start:
            # Add kick on downbeat for emphasis
            kick_velocity = int(base_velocity + accent_strength * 15 + abs(energy_delta_in) * 18)
            kick_velocity = max(70, min(127, kick_velocity))
            new_events.append(
                DrumEvent(
                    beat=0.0,
                    duration_beats=0.125,
                    pitch=pitches.get("kick", 36),
                    velocity=kick_velocity,
                    kind="kick_transition",
                )
            )

    # Pickup window: Add fill-like events in the last 1-2 beats before transitioning to different section type.
    # Only apply if transitioning to a different section type (not last section).
    # Controlled by pickup_rate parameter.
    if (next_section_type is not None
        and next_section_type != section_type
        and rng.random() < pickup_rate):
        # Energy lifts deserve longer fills; drops are shorter and leave space.
        if energy_delta_next >= 0.35:
            pickup_lengths = [1.0, 1.5, 2.0, 2.0]
            pickup_style = rng.choice(["snare_toms", "tom_run", "kick_snare"])
        elif energy_delta_next <= -0.25:
            pickup_lengths = [0.5, 1.0, 1.0]
            pickup_style = rng.choice(["snare_toms", "stop_time"])
        else:
            pickup_lengths = [0.5, 1.0, 1.0, 1.5, 2.0]
            pickup_style = rng.choice(["snare_toms", "tom_run", "kick_snare"])
        pickup_length = rng.choice(pickup_lengths)
        pickup_window_start = max(0.0, total_beats - pickup_length)

        # 16th-note subdivisions within the window.
        # `sb` is already one 16th-note step (bar / 16-step grid), so use it
        # directly. Dividing again would produce 64th-note machine-gun pickups.
        step_16th = sb
        num_16ths = max(1, int(pickup_length / step_16th))
        tom_cycle = [
            pitches.get("tom_high", pitches.get("snare", 38)),
            pitches.get("tom_mid", pitches.get("snare", 38)),
            pitches.get("tom_low", pitches.get("snare", 38)),
            pitches.get("snare", 38),
        ]

        for i in range(num_16ths):
            pickup_beat = pickup_window_start + (i * step_16th)
            if pickup_beat >= total_beats:
                break

            if pickup_style == "stop_time" and i < num_16ths - 1:
                # Short drop transitions: let the last hit breathe into the next section.
                if i % 2 == 1:
                    continue
                pitch = pitches.get("snare", 38)
                kind = "snare_pickup"
            elif pickup_style == "tom_run":
                pitch = tom_cycle[min(len(tom_cycle) - 1, int(i / max(1, num_16ths / len(tom_cycle))))]
                kind = "tom_pickup" if pitch != pitches.get("snare", 38) else "snare_pickup"
            elif pickup_style == "kick_snare":
                pitch = pitches.get("kick", 36) if i % 4 in (0, 3) else pitches.get("snare", 38)
                kind = "kick_pickup" if pitch == pitches.get("kick", 36) else "snare_pickup"
            else:
                pitch = tom_cycle[i % len(tom_cycle)] if i >= num_16ths // 2 else pitches.get("snare", 38)
                kind = "tom_pickup" if pitch != pitches.get("snare", 38) else "snare_pickup"

            # Exponential crescendo: quiet start, loud finish
            velocity_factor = ((i + 1) / num_16ths) ** 1.6
            lift_boost = 8 if energy_delta_next >= 0.35 else 0
            pickup_velocity = int(base_velocity - 18 + velocity_factor * (28 + lift_boost))
            pickup_velocity = max(45, min(127, pickup_velocity))

            # Micro-timing jitter: natural hand acceleration feel
            jitter = rng.uniform(-0.004, 0.004)

            new_events.append(
                DrumEvent(
                    beat=pickup_beat + jitter,
                    duration_beats=step_16th,
                    pitch=pitch,
                    velocity=pickup_velocity,
                    kind=kind,
                )
            )

        if energy_delta_next >= 0.35:
            final_crash_beat = max(0.0, total_beats - step_16th)
            if rng.random() < 0.45:
                new_events.append(
                    DrumEvent(
                        beat=final_crash_beat,
                        duration_beats=0.25,
                        pitch=pitches.get("crash", 49),
                        velocity=max(70, min(127, int(base_velocity + 18))),
                        kind="crash_pickup",
                    )
                )

    return new_events


@dataclass(frozen=True)
class DrumEvent:
    """A single drum note event, relative to a section.

    Attributes:
        beat: Start time in beats, relative to the section start (0.0 == section downbeat).
        duration_beats: Duration in beats (engine may override per-instrument).
        pitch: MIDI pitch (GM drum note).
        velocity: Nominal velocity before humanization.
        kind: A short label useful for debugging and analysis dumps.
    """

    beat: float
    duration_beats: float
    pitch: int
    velocity: int
    kind: str


def events_for_section_from_template(
    *,
    template: GrooveTemplate,
    total_beats: float,
    beats_per_bar: float,
    rng: random.Random,
    pitches: Dict[str, int],
    base_velocity: int,
    accent_strength: float,
    hat_density: float,
    steps_per_bar: int | None = None,
    kick_density: float = 1.0,
    snare_density: float = 1.0,
    ghost_rate: Optional[float] = None,
    ghost_steps: Optional[Sequence[int]] = None,
    ghost_velocity_bias: Optional[int] = None,
    hats_density: Optional[float] = None,
    hats_open_rate: Optional[float] = None,
    hats_pedal_rate: Optional[float] = None,
    hats_accent_rate: Optional[float] = None,
    groove_tom_rate: float = 0.0,
    fill_tom_rate: float = 0.0,
    crash_rate: Optional[float] = None,
    crash_placements: Optional[Sequence[int]] = None,
    ride_bell_rate: float = 0.0,
    splash_rate: float = 0.0,
    china_rate: float = 0.0,
    transition_context: Optional[Dict[str, Any]] = None,
) -> List[DrumEvent]:
    """Render DrumEvents for a section using a groove template.

    Args:
        template: Declarative groove template.
        total_beats: Section duration in beats.
        beats_per_bar: Meter beats per bar for the section.
        rng: Deterministic RNG for the section.
        pitches: Mapping with required keys:
            kick, snare, hat_closed, hat_open, ride, crash
        base_velocity: Base velocity for the section before accents.
        accent_strength: 0..1 accent influence.
        hat_density: 0..1 probability for placing top cymbal steps.
        steps_per_bar: Internal step grid resolution. Defaults to the
            meter-derived grid (4 steps per quarter-note beat: 16 in 4/4,
            12 in 3/4).
        kick_density: Multiplier for kick drum density (0.5-1.5 typical). Defaults to 1.0.
        snare_density: Multiplier for snare drum density (0.5-1.5 typical). Defaults to 1.0.
        ghost_rate: Optional override for ghost probability (0..1). If None, uses template.ghost_rate.
        ghost_steps: Optional override for ghost placement steps. If None, uses template.ghost_steps.
            If provided as an empty sequence and ghost_rate > 0, defaults will be inferred near backbeats.
        hats_density: Optional override for top-cymbal density (0..1). If None, uses hat_density.
        hats_open_rate: Optional override for open-hat probability (0..1). If None, uses template.open_hat_rate.
        hats_pedal_rate: Optional override for pedal-hat (foot chick) probability (0..1). If None, defaults to 0.0.
        hats_accent_rate: Optional override for additional hat accent probability on eligible offbeats (0..1). If None, defaults to 0.0.
        transition_context: Optional dict with prev_section_type, next_section_type for detecting section boundaries.

    Returns:
        List of DrumEvent sorted by (beat, pitch).
    """
    if rng is None:
        raise TypeError(
            "events_for_section_from_template requires a non-None RNG. "
            "The drums engine entrypoint must pass the per-section RNG into patterns."
        )
    bpb = float(beats_per_bar)

    # Default to the meter-derived grid (4 steps per quarter-note beat:
    # 16 in 4/4, 12 in 3/4 and 6/8) when no explicit resolution is given.
    if steps_per_bar is None:
        from ..groove import steps_per_bar_for_meter

        spb = steps_per_bar_for_meter(bpb)
    else:
        spb = int(steps_per_bar)
    spb = max(1, spb)

    sb = step_beats(bpb, steps_per_bar=spb)
    bars = bars_total(float(total_beats), bpb)

    hat_steps = hat_steps_for_mode(template.hat_mode, steps_per_bar=spb)
    sync_steps = eligible_syncopation_steps(spb)
    dbl_steps = eligible_double_kick_steps(spb)

    events: List[DrumEvent] = []
    # Intent rules: track if previous bar ended with an open hat.
    prev_bar_open_hat = False

    # Decide which backbeats apply if half-time is enabled.
    # Standard half-time puts the lone snare on beat 3 (the bar midpoint),
    # matching the half_time section intent in the engine entrypoint.
    backbeats: tuple[int, ...] = tuple(template.snare_backbeat_steps)
    if template.half_time and backbeats:
        backbeats = (spb // 2,)

    # Resolve ghost rate and steps
    effective_ghost_rate = template.ghost_rate if ghost_rate is None else float(ghost_rate)

    # Handle ghost_steps override
    if ghost_steps is None:
        ghost_steps_for_snare = tuple(int(x) for x in template.ghost_steps)
    else:
        ghost_steps_for_snare = tuple(int(x) for x in ghost_steps)

    for bar_i in range(bars):
        bar_start = float(bar_i) * bpb

        # 1. Crash events (lines 272-292 in original)
        crash_events = generate_crash_events(
            bar_i=bar_i,
            bars=bars,
            bar_start=bar_start,
            spb=spb,
            sb=sb,
            template=template,
            crash_rate=crash_rate,
            crash_placements=crash_placements,
            base_velocity=base_velocity,
            accent_strength=accent_strength,
            rng=rng,
            pitches=pitches,
        )
        events.extend(crash_events)

        # 2. Kick events (lines 294-401 in original)
        kick_events, kicks_in_bar = generate_kick_events(
            bar_i=bar_i,
            bars=bars,
            bar_start=bar_start,
            spb=spb,
            sb=sb,
            template=template,
            sync_steps=sync_steps,
            dbl_steps=dbl_steps,
            backbeats=set(backbeats),
            base_velocity=base_velocity,
            accent_strength=accent_strength,
            rng=rng,
            pitches=pitches,
            density_multiplier=kick_density,
        )
        events.extend(kick_events)

        # 3. Snare events (lines 403-462 in original)
        snare_events = generate_snare_events(
            bar_i=bar_i,
            bars=bars,
            bar_start=bar_start,
            spb=spb,
            sb=sb,
            backbeats=backbeats,
            ghost_steps=ghost_steps_for_snare,
            effective_ghost_rate=effective_ghost_rate,
            base_velocity=base_velocity,
            accent_strength=accent_strength,
            ghost_velocity_bias=ghost_velocity_bias,
            rng=rng,
            pitches=pitches,
            density_multiplier=snare_density,
        )
        events.extend(snare_events)

        # 4. Top cymbal + pedal hat (lines 464-636 in original)
        hat_events, open_hat_in_this_bar, top_in_bar = generate_top_cymbal_events(
            bar_i=bar_i,
            bars=bars,
            bar_start=bar_start,
            spb=spb,
            sb=sb,
            bpb=bpb,
            template=template,
            hat_steps=hat_steps,
            backbeats=backbeats,
            prev_bar_open_hat=prev_bar_open_hat,
            hat_density=hat_density,
            hats_density=hats_density,
            hats_open_rate=hats_open_rate,
            hats_pedal_rate=hats_pedal_rate,
            hats_accent_rate=hats_accent_rate,
            base_velocity=base_velocity,
            accent_strength=accent_strength,
            rng=rng,
            pitches=pitches,
        )
        events.extend(hat_events)

        # 5. Groove toms (occasional texture)
        if groove_tom_rate > 0.0:
            occupied_steps = kicks_in_bar.union(set(backbeats))
            tom_events = generate_tom_events(
                bar_i=bar_i,
                bars=bars,
                bar_start=bar_start,
                spb=spb,
                sb=sb,
                bpb=bpb,
                groove_tom_rate=groove_tom_rate,
                occupied_steps=occupied_steps,
                base_velocity=base_velocity,
                accent_strength=accent_strength,
                rng=rng,
                pitches=pitches,
            )
            events.extend(tom_events)

        # 6. Tom fill runs (phrase endings)
        if fill_tom_rate > 0.0:
            fill_events = generate_tom_fill_run(
                bar_i=bar_i,
                bars=bars,
                bar_start=bar_start,
                spb=spb,
                sb=sb,
                bpb=bpb,
                fill_tom_rate=fill_tom_rate,
                base_velocity=base_velocity,
                accent_strength=accent_strength,
                rng=rng,
                pitches=pitches,
            )
            events.extend(fill_events)

        # 7. Ride bell (only when using ride cymbal)
        if ride_bell_rate > 0.0 and template.use_ride:
            ride_bell_events = generate_ride_bell_events(
                bar_start=bar_start,
                spb=spb,
                sb=sb,
                ride_bell_rate=ride_bell_rate,
                top_in_bar=top_in_bar,
                backbeats=set(backbeats),
                base_velocity=base_velocity,
                accent_strength=accent_strength,
                rng=rng,
                pitches=pitches,
            )
            events.extend(ride_bell_events)

        # 8. Splash and china (very rare accent cymbals)
        if splash_rate > 0.0 or china_rate > 0.0:
            occupied_steps = kicks_in_bar.union(set(backbeats)).union(top_in_bar)
            splash_china_events = generate_splash_china_events(
                bar_i=bar_i,
                bars=bars,
                bar_start=bar_start,
                spb=spb,
                sb=sb,
                splash_rate=splash_rate,
                china_rate=china_rate,
                occupied_steps=occupied_steps,
                backbeats=set(backbeats),
                base_velocity=base_velocity,
                accent_strength=accent_strength,
                rng=rng,
                pitches=pitches,
            )
            events.extend(splash_china_events)

        # Update prev_bar_open_hat for next bar's intent rules.
        prev_bar_open_hat = bool(open_hat_in_this_bar)

    # Apply transition effects (pickups and downbeat punctuation) if context provided.
    if transition_context is not None:
        events = _apply_transition_effects(
            events=events,
            transition_context=transition_context,
            total_beats=total_beats,
            sb=sb,
            base_velocity=base_velocity,
            accent_strength=accent_strength,
            rng=rng,
            pitches=pitches,
        )

    # Trim any events that exceed total_beats due to last-bar rounding.
    trimmed = [e for e in events if e.beat < float(total_beats) - 1e-9]

    trimmed.sort(key=lambda e: (e.beat, e.pitch, e.kind))
    return trimmed
