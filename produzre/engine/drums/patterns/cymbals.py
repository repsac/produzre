"""Cymbal event generation (crash, ride bell, splash, china).

This module handles crash cymbal placement at section start and phrase ends,
plus optional ride bell, splash, and china accents with arrangement awareness.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Sequence, Set

from ..groove import GrooveTemplate
from .utils import vel_for

__all__ = ["generate_crash_events", "generate_ride_bell_events", "generate_splash_china_events"]


def generate_crash_events(
    *,
    bar_i: int,
    bars: int,
    bar_start: float,
    spb: int,
    sb: float,
    template: GrooveTemplate,
    crash_rate: Optional[float],
    crash_placements: Optional[Sequence[int]],
    base_velocity: int,
    accent_strength: float,
    rng: random.Random,
    pitches: Dict[str, int],
) -> List:
    """Generate crash cymbal events for a single bar.

    Handles crash placement at section start and phrase ends based on template settings
    and optional config overrides.

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
        Groove template with crash parameters.
    crash_rate : Optional[float]
        Optional override for crash probability at phrase ends (0..1).
    crash_placements : Optional[Sequence[int]]
        Optional explicit crash step placements (overrides default logic).
    base_velocity : int
        Base velocity for the section.
    accent_strength : float
        Accent influence (0.0 to 1.0).
    rng : random.Random
        Deterministic RNG for this section.
    pitches : Dict[str, int]
        Pitch mapping with required key 'crash'.

    Returns
    -------
    List[DrumEvent]
        Generated crash events.

    Notes
    -----
    This function is designed to be called once per bar by the orchestration layer.
    The RNG must be passed to maintain deterministic output.
    """
    # Import DrumEvent locally to avoid circular dependency
    from .kit import DrumEvent

    crash = int(pitches["crash"])
    events: List[DrumEvent] = []

    # If explicit placements are provided, use them directly
    if crash_placements is not None:
        placements = [int(x) for x in crash_placements]
        for step_i in placements:
            if 0 <= step_i < spb:
                beat = bar_start + float(step_i) * sb
                vel = vel_for(
                    base_vel=base_velocity,
                    accent_strength=accent_strength,
                    kind="crash",
                    downbeat=(step_i == 0),
                    rng=rng,
                )
                events.append(DrumEvent(beat=beat, duration_beats=0.5, pitch=crash, velocity=vel, kind="crash"))
        return events

    # Default logic: crash at section start
    if template.crash_start and bar_i == 0:
        vel = vel_for(
            base_vel=base_velocity,
            accent_strength=accent_strength,
            kind="crash",
            downbeat=True,
            rng=rng,
        )
        events.append(DrumEvent(beat=bar_start, duration_beats=0.5, pitch=crash, velocity=vel, kind="crash"))

    # Crash at phrase end (probabilistic)
    effective_rate = crash_rate if crash_rate is not None else float(template.crash_phrase_end_rate)
    if effective_rate > 0.0 and bar_i == max(0, bars - 1):
        if rng.random() < effective_rate:
            vel = vel_for(
                base_vel=base_velocity,
                accent_strength=accent_strength,
                kind="crash",
                downbeat=True,
                rng=rng,
            )
            events.append(DrumEvent(beat=bar_start, duration_beats=0.5, pitch=crash, velocity=vel, kind="crash"))

    return events


def generate_ride_bell_events(
    *,
    bar_start: float,
    spb: int,
    sb: float,
    ride_bell_rate: float,
    top_in_bar: Set[int],
    backbeats: Set[int],
    base_velocity: int,
    accent_strength: float,
    rng: random.Random,
    pitches: Dict[str, int],
) -> List:
    """Generate ride bell events for occasional accents.

    Ride bell is used sparingly on top of ride patterns for accents and variety.

    Parameters
    ----------
    bar_start : float
        Beat position of bar start.
    spb : int
        Steps per bar.
    sb : float
        Beat duration of one step.
    ride_bell_rate : float
        Probability of placing ride bell accents (0..1).
    top_in_bar : Set[int]
        Steps occupied by top cymbal (ride) to ensure placement alignment.
    backbeats : Set[int]
        Snare backbeat steps to avoid.
    base_velocity : int
        Base velocity for the section.
    accent_strength : float
        Accent influence (0.0 to 1.0).
    rng : random.Random
        Deterministic RNG for this section.
    pitches : Dict[str, int]
        Pitch mapping with required key 'ride_bell'.

    Returns
    -------
    List[DrumEvent]
        Generated ride bell events.
    """
    from .kit import DrumEvent

    events: List[DrumEvent] = []

    if ride_bell_rate <= 0.0:
        return events

    ride_bell = int(pitches.get("ride_bell", 53))

    # Eligible steps: downbeat + beat 3, avoid backbeats
    eligible = [0, spb // 2]  # Typically steps 0 and 8 on 16-step grid
    eligible = [s for s in eligible if s not in backbeats and s in top_in_bar]

    if not eligible:
        return events

    # Pick 0-1 ride bell hits per bar based on rate
    if rng.random() < ride_bell_rate:
        step_i = rng.choice(eligible)
        beat = bar_start + float(step_i) * sb
        vel = vel_for(
            base_vel=base_velocity,
            accent_strength=accent_strength,
            kind="crash",  # Ride bell has similar volume to crash
            downbeat=(step_i == 0),
            rng=rng,
        )

        events.append(
            DrumEvent(
                beat=beat,
                duration_beats=0.25,
                pitch=ride_bell,
                velocity=vel,
                kind="ride_bell",
            )
        )

    return events


def generate_splash_china_events(
    *,
    bar_i: int,
    bars: int,
    bar_start: float,
    spb: int,
    sb: float,
    splash_rate: float,
    china_rate: float,
    occupied_steps: Set[int],
    backbeats: Set[int],
    base_velocity: int,
    accent_strength: float,
    rng: random.Random,
    pitches: Dict[str, int],
) -> List:
    """Generate splash and china cymbal events with strict constraints.

    Splash and china are accent cymbals used sparingly for color and emphasis.

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
    splash_rate : float
        Probability of placing splash accents (0..1).
    china_rate : float
        Probability of placing china accents (0..1).
    occupied_steps : Set[int]
        Steps already occupied by other voices to avoid clutter.
    backbeats : Set[int]
        Snare backbeat steps to avoid.
    base_velocity : int
        Base velocity for the section.
    accent_strength : float
        Accent influence (0.0 to 1.0).
    rng : random.Random
        Deterministic RNG for this section.
    pitches : Dict[str, int]
        Pitch mapping with keys 'splash', 'china'.

    Returns
    -------
    List[DrumEvent]
        Generated splash and china events.
    """
    from .kit import DrumEvent

    events: List[DrumEvent] = []

    # Splash cymbal: light accent on offbeats
    if splash_rate > 0.0:
        splash = int(pitches.get("splash", 55))

        # Eligible steps: offbeats, not on backbeats or occupied steps
        eligible_splash = []
        for step_i in range(1, spb, 2):  # Odd steps (offbeats)
            if step_i not in occupied_steps and step_i not in backbeats:
                eligible_splash.append(step_i)

        # Very conservative: max 1 splash per section
        if eligible_splash and bar_i < bars and rng.random() < splash_rate * 0.5:
            step_i = rng.choice(eligible_splash)
            beat = bar_start + float(step_i) * sb
            vel = vel_for(
                base_vel=base_velocity,
                accent_strength=accent_strength,
                kind="crash",
                downbeat=False,
                rng=rng,
            )
            events.append(
                DrumEvent(
                    beat=beat,
                    duration_beats=0.25,
                    pitch=splash,
                    velocity=vel,
                    kind="splash",
                )
            )

    # China cymbal: heavy accent, very rare
    if china_rate > 0.0:
        china = int(pitches.get("china", 52))

        # Eligible steps: downbeat or beat 3, not on backbeats
        eligible_china = [s for s in [0, spb // 2] if s not in backbeats]

        # Extremely rare: only on last bar of section, low probability
        is_last_bar = (bar_i == bars - 1)
        if eligible_china and is_last_bar and rng.random() < china_rate * 0.3:
            step_i = rng.choice(eligible_china)
            beat = bar_start + float(step_i) * sb
            vel = vel_for(
                base_vel=base_velocity,
                accent_strength=accent_strength,
                kind="crash",
                downbeat=(step_i == 0),
                rng=rng,
            )
            events.append(
                DrumEvent(
                    beat=beat,
                    duration_beats=0.5,
                    pitch=china,
                    velocity=vel,
                    kind="china",
                )
            )

    return events
