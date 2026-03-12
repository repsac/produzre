"""Kick drum event generation (base, extra, double-kick).

This module handles all kick-related event generation including base kicks from
the template, extra kicks for syncopation with bar-level contour, and double-kick
bursts near the bar end.
"""

from __future__ import annotations

import random
from typing import Dict, List, Set, Tuple

from ..groove import GrooveTemplate
from .utils import is_near, limit_per_beat, vel_for

__all__ = ["eligible_syncopation_steps", "eligible_double_kick_steps", "generate_kick_events"]


def eligible_syncopation_steps(steps_per_bar: int) -> Tuple[int, ...]:
    """Return step indices that commonly work for kick syncopation.

    On a 16-step grid these are the "e" and "a" positions of each beat.

    Parameters
    ----------
    steps_per_bar : int
        Number of steps per bar.

    Returns
    -------
    Tuple[int, ...]
        Step indices eligible for syncopation (odd indices on 16-step grid).
    """
    spb = max(1, int(steps_per_bar))
    # 16th grid: 1,3,5,7,...
    return tuple(i for i in range(1, spb) if i % 2 == 1)


def eligible_double_kick_steps(steps_per_bar: int) -> Tuple[int, ...]:
    """Return step indices near the bar end for double-kick feel.

    Parameters
    ----------
    steps_per_bar : int
        Number of steps per bar.

    Returns
    -------
    Tuple[int, ...]
        Step indices in the last 4 steps of the bar.
    """
    spb = max(1, int(steps_per_bar))
    start = max(0, spb - 4)
    return tuple(range(start, spb))


def generate_kick_events(
    *,
    bar_i: int,
    bars: int,
    bar_start: float,
    spb: int,
    sb: float,
    template: GrooveTemplate,
    sync_steps: Tuple[int, ...],
    dbl_steps: Tuple[int, ...],
    backbeats: Set[int],
    base_velocity: int,
    accent_strength: float,
    rng: random.Random,
    pitches: Dict[str, int],
    density_multiplier: float = 1.0,
) -> Tuple[List, Set[int]]:
    """Generate kick drum events for a single bar.

    Combines base kicks (from template), extra kicks (syncopation with bar contour),
    and double-kick bursts. Returns both events and the set of occupied steps
    for collision detection.

    Parameters
    ----------
    bar_i : int
        Current bar index (0-based).
    bars : int
        Total bars in section.
    bar_start : float
        Beat position of bar start.
    spb : int
        Steps per bar.
    sb : float
        Beat duration of one step.
    template : GrooveTemplate
        Groove template with kick parameters.
    sync_steps : Tuple[int, ...]
        Eligible syncopation step indices.
    dbl_steps : Tuple[int, ...]
        Eligible double-kick step indices.
    backbeats : Set[int]
        Snare backbeat step indices to avoid.
    base_velocity : int
        Base velocity for the section.
    accent_strength : float
        Accent influence (0.0 to 1.0).
    rng : random.Random
        Deterministic RNG for this section.
    pitches : Dict[str, int]
        Pitch mapping with required key 'kick'.
    density_multiplier : float
        Multiplier applied to kick_extra_rate and double_kick_rate (0.5-1.5 typical). Defaults to 1.0.

    Returns
    -------
    events : List[DrumEvent]
        Generated kick events.
    kicks_in_bar : Set[int]
        Step indices occupied by kicks (for collision detection).

    Notes
    -----
    This function is designed to be called once per bar by the orchestration layer.
    The RNG must be passed to maintain deterministic output.
    """
    # Import DrumEvent locally to avoid circular dependency
    from .kit import DrumEvent

    kick = int(pitches["kick"])
    events: List[DrumEvent] = []
    kicks_in_bar: Set[int] = set()

    # Base kicks
    for step_i in template.kick_base:
        step_i = int(step_i)
        if 0 <= step_i < spb:
            kicks_in_bar.add(step_i)
            beat = bar_start + float(step_i) * sb
            vel = vel_for(
                base_vel=base_velocity,
                accent_strength=accent_strength,
                kind="kick",
                downbeat=(step_i == 0),
                rng=rng,
            )
            events.append(DrumEvent(beat=beat, duration_beats=0.25, pitch=kick, velocity=vel, kind="kick"))

    # Extra kicks: add syncopation with bar-level contour.
    #
    # Deterministic "phrase" feel:
    # - Early bars: conservative
    # - Later bars: slightly more adventurous
    # - Avoid stepping on snare backbeats unless intensity is high
    if template.kick_extra_rate > 0.0:
        base_rate = float(template.kick_extra_rate) * float(density_multiplier)

        # Bar contour: more syncopation later in the section.
        section_pos = 0.0 if bars <= 1 else float(bar_i) / float(max(1, bars - 1))
        contour = 0.85 + 0.35 * section_pos  # 0.85 .. 1.20

        # Respect half-time: avoid cluttering around the single backbeat.
        backbeat_set = set(backbeats)

        # Per-beat density: keep kick from becoming a machinegun.
        max_per_beat = 2 if template.double_kick_rate > 0.0 else 1

        for step_i in sync_steps:
            step_i = int(step_i)
            if step_i in kicks_in_bar:
                continue
            if limit_per_beat(step_i=step_i, steps_per_bar=spb, occupied_steps=kicks_in_bar, max_per_beat=max_per_beat):
                continue

            # Avoid landing on/near backbeat unless we're driving hard.
            if is_near(step_i, backbeat_set, tol=0) and float(template.double_kick_rate) < 0.35:
                continue

            rate = base_rate * contour

            if rng.random() < rate:
                kicks_in_bar.add(step_i)
                beat = bar_start + float(step_i) * sb
                vel = vel_for(
                    base_vel=base_velocity,
                    accent_strength=accent_strength,
                    kind="kick_extra",
                    downbeat=False,
                    rng=rng,
                )
                events.append(
                    DrumEvent(
                        beat=beat,
                        duration_beats=0.25,
                        pitch=kick,
                        velocity=vel,
                        kind="kick_extra",
                    )
                )

    # Double-kick feel: prefer short bursts near the bar end.
    if template.double_kick_rate > 0.0:
        rate = float(template.double_kick_rate) * float(density_multiplier)

        # Pick a burst anchor among the last 4 steps.
        if dbl_steps and rng.random() < rate:
            anchor = int(rng.choice(list(dbl_steps)))

            # A 2-hit burst: anchor and the next off-step (if available).
            burst_steps = [anchor]
            if anchor + 1 < spb:
                burst_steps.append(anchor + 1)
            elif anchor - 1 >= 0:
                burst_steps.append(anchor - 1)

            for step_i in burst_steps:
                # Avoid exact duplicates with existing kicks.
                if step_i in kicks_in_bar:
                    continue
                kicks_in_bar.add(step_i)
                beat = bar_start + float(step_i) * sb
                vel = vel_for(
                    base_vel=base_velocity,
                    accent_strength=accent_strength,
                    kind="kick_double",
                    downbeat=False,
                    rng=rng,
                )
                events.append(
                    DrumEvent(
                        beat=beat,
                        duration_beats=0.25,
                        pitch=kick,
                        velocity=vel,
                        kind="kick_double",
                    )
                )

    return events, kicks_in_bar
