"""Tom drum event generation (groove toms and fill runs).

This module handles tom-related event generation including groove toms for
section texture and fill tom runs for phrase endings and transitions.
"""

from __future__ import annotations

import random
from typing import Dict, List, Set

from .utils import vel_for

__all__ = ["generate_tom_events", "generate_tom_fill_run"]


def generate_tom_events(
    *,
    bar_i: int,
    bars: int,
    bar_start: float,
    spb: int,
    sb: float,
    bpb: float,
    groove_tom_rate: float,
    occupied_steps: Set[int],
    base_velocity: int,
    accent_strength: float,
    rng: random.Random,
    pitches: Dict[str, int],
) -> List:
    """Generate groove tom events for a single bar.

    Adds occasional tom hits during the section for texture and variation.
    Avoids colliding with kick/snare/hat events.

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
    bpb : float
        Beats per bar.
    groove_tom_rate : float
        Probability of placing groove tom hits (0..1).
    occupied_steps : Set[int]
        Steps already occupied by other voices.
    base_velocity : int
        Base velocity for the section.
    accent_strength : float
        Accent influence (0.0 to 1.0).
    rng : random.Random
        Deterministic RNG for this section.
    pitches : Dict[str, int]
        Pitch mapping with required keys: tom_high, tom_mid, tom_low.

    Returns
    -------
    List[DrumEvent]
        Generated tom events.
    """
    from .kit import DrumEvent

    events: List[DrumEvent] = []

    if groove_tom_rate <= 0.0:
        return events

    tom_high = int(pitches.get("tom_high", 50))
    tom_mid = int(pitches.get("tom_mid", 47))
    tom_low = int(pitches.get("tom_low", 45))

    # Eligible steps: prefer offbeats and bar-end pickups
    # On 16-step grid: 2, 6, 10, 14 (just before backbeats and downbeats)
    eligible = []
    for step_i in range(spb):
        if step_i in occupied_steps:
            continue
        # Prefer steps just before beat boundaries
        if (step_i + 2) % 4 == 0:  # 2, 6, 10, 14 on 16-step grid
            eligible.append(step_i)

    if not eligible:
        return events

    # Pick 0-2 tom hits per bar based on rate
    max_hits = 2 if groove_tom_rate > 0.5 else 1
    num_hits = 0

    for step_i in eligible:
        if num_hits >= max_hits:
            break
        if rng.random() < groove_tom_rate:
            # Choose tom pitch: prefer mid, occasionally high or low
            tom_choice = rng.random()
            if tom_choice < 0.5:
                pitch = tom_mid
                kind = "tom_mid"
            elif tom_choice < 0.75:
                pitch = tom_high
                kind = "tom_high"
            else:
                pitch = tom_low
                kind = "tom_low"

            beat = bar_start + float(step_i) * sb
            vel = vel_for(
                base_vel=base_velocity,
                accent_strength=accent_strength,
                kind="tom",
                downbeat=False,
                rng=rng,
            )

            events.append(
                DrumEvent(
                    beat=beat,
                    duration_beats=0.25,
                    pitch=pitch,
                    velocity=vel,
                    kind=kind,
                )
            )
            num_hits += 1

    return events


def generate_tom_fill_run(
    *,
    bar_i: int,
    bars: int,
    bar_start: float,
    spb: int,
    sb: float,
    bpb: float,
    fill_tom_rate: float,
    base_velocity: int,
    accent_strength: float,
    rng: random.Random,
    pitches: Dict[str, int],
) -> List:
    """Generate tom fill run for phrase endings.

    Creates descending runs (high → mid → low) or around-the-kit patterns
    for phrase-end fills and section transitions.

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
    bpb : float
        Beats per bar.
    fill_tom_rate : float
        Probability of placing fill runs (0..1).
    base_velocity : int
        Base velocity for the section.
    accent_strength : float
        Accent influence (0.0 to 1.0).
    rng : random.Random
        Deterministic RNG for this section.
    pitches : Dict[str, int]
        Pitch mapping with required keys: tom_high, tom_mid, tom_low.

    Returns
    -------
    List[DrumEvent]
        Generated tom fill events.
    """
    from .kit import DrumEvent

    events: List[DrumEvent] = []

    if fill_tom_rate <= 0.0:
        return events

    # Only add fill runs on the last bar of the section
    is_last_bar = (bar_i == bars - 1)
    if not is_last_bar:
        return events

    if rng.random() >= fill_tom_rate:
        return events

    tom_high = int(pitches.get("tom_high", 50))
    tom_mid = int(pitches.get("tom_mid", 47))
    tom_low = int(pitches.get("tom_low", 45))

    # Fill runs start at beat 3.5 or 4 and continue to bar end
    # On 16-step grid, this is steps 14-15 (beat 4)
    fill_start_step = int(spb * 0.875)  # 14 on 16-step grid (beat 3.5)

    # Choose fill pattern
    pattern_choice = rng.random()

    if pattern_choice < 0.6:
        # Descending run: high → mid → low
        fill_pattern = [
            (fill_start_step, tom_high, "tom_high"),
            (fill_start_step + 1, tom_mid, "tom_mid"),
            (fill_start_step + 2 if fill_start_step + 2 < spb else fill_start_step + 1, tom_low, "tom_low"),
        ]
    elif pattern_choice < 0.8:
        # Around-the-kit: high → low → mid
        fill_pattern = [
            (fill_start_step, tom_high, "tom_high"),
            (fill_start_step + 1, tom_low, "tom_low"),
            (fill_start_step + 2 if fill_start_step + 2 < spb else fill_start_step + 1, tom_mid, "tom_mid"),
        ]
    else:
        # Quick doubles on one tom
        tom_pitch = tom_mid if rng.random() < 0.7 else tom_low
        kind = "tom_mid" if tom_pitch == tom_mid else "tom_low"
        fill_pattern = [
            (fill_start_step, tom_pitch, kind),
            (fill_start_step + 1, tom_pitch, kind),
        ]

    for step_i, pitch, kind in fill_pattern:
        if step_i >= spb:
            continue
        beat = bar_start + float(step_i) * sb
        vel = vel_for(
            base_vel=base_velocity,
            accent_strength=accent_strength,
            kind="tom_fill",
            downbeat=False,
            rng=rng,
        )

        events.append(
            DrumEvent(
                beat=beat,
                duration_beats=0.25,
                pitch=pitch,
                velocity=vel,
                kind=kind,
            )
        )

    return events
