"""Hi-hat and ride cymbal event generation.

This module handles top cymbal (hi-hat or ride) with complex open-hat intent tracking,
pedal hat (foot chick), and accent logic.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Set, Tuple

from ..groove import GrooveTemplate
from .utils import clamp_int, vel_for

__all__ = ["generate_top_cymbal_events"]


def generate_top_cymbal_events(
    *,
    bar_i: int,
    bars: int,
    bar_start: float,
    spb: int,
    sb: float,
    bpb: float,
    template: GrooveTemplate,
    hat_steps: Tuple[int, ...],
    backbeats: Tuple[int, ...],
    prev_bar_open_hat: bool,
    hat_density: float,
    hats_density: Optional[float],
    hats_open_rate: Optional[float],
    hats_pedal_rate: Optional[float],
    hats_accent_rate: Optional[float],
    base_velocity: int,
    accent_strength: float,
    rng: random.Random,
    pitches: Dict[str, int],
) -> Tuple[List, bool, Set[int]]:
    """Generate top cymbal (hat/ride) and pedal hat events for a single bar.

    Handles hi-hat or ride patterns with complex open-hat intent tracking across bars,
    pedal hat (foot chick) on backbeats, and optional accent logic.

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
    template : GrooveTemplate
        Groove template with hat/ride parameters.
    hat_steps : Tuple[int, ...]
        Eligible step indices for hat/ride placement.
    backbeats : Tuple[int, ...]
        Snare backbeat step indices to avoid for open hats.
    prev_bar_open_hat : bool
        Whether previous bar ended with an open hat (for close-on-downbeat).
    hat_density : float
        Default top cymbal density (0..1).
    hats_density : Optional[float]
        Optional override for top-cymbal density (0..1).
    hats_open_rate : Optional[float]
        Optional override for open-hat probability (0..1).
    hats_pedal_rate : Optional[float]
        Optional override for pedal-hat probability (0..1).
    hats_accent_rate : Optional[float]
        Optional override for additional hat accent probability (0..1).
    base_velocity : int
        Base velocity for the section.
    accent_strength : float
        Accent influence (0.0 to 1.0).
    rng : random.Random
        Deterministic RNG for this section.
    pitches : Dict[str, int]
        Pitch mapping with required keys: 'hat_closed', 'hat_open', 'ride', 'hat_pedal'.

    Returns
    -------
    events : List[DrumEvent]
        Generated top cymbal and pedal hat events.
    open_hat_in_this_bar : bool
        Whether this bar ended with an open hat (for next bar's intent).
    top_in_bar : Set[int]
        Step indices occupied by top cymbal (for future use).

    Notes
    -----
    This function is designed to be called once per bar by the orchestration layer.
    The RNG must be passed to maintain deterministic output.
    """
    # Import DrumEvent locally to avoid circular dependency
    from .kit import DrumEvent

    hat_closed = int(pitches["hat_closed"])
    hat_open = int(pitches["hat_open"])
    hat_pedal = int(pitches.get("hat_pedal", 44))
    ride = int(pitches["ride"])

    events: List[DrumEvent] = []
    open_hat_in_this_bar = False
    is_phrase_end_bar = (bar_i == max(0, bars - 1))
    top_in_bar: Set[int] = set()

    # Top cymbal: hat or ride
    top_pitch = ride if template.use_ride else hat_closed
    density_src = hat_density if hats_density is None else hats_density
    density = float(density_src)
    density = 0.0 if density < 0.0 else 1.0 if density > 1.0 else density

    open_rate_src = template.open_hat_rate if hats_open_rate is None else hats_open_rate
    open_rate = float(open_rate_src)
    open_rate = 0.0 if open_rate < 0.0 else 1.0 if open_rate > 1.0 else open_rate

    pedal_rate = 0.0 if hats_pedal_rate is None else float(hats_pedal_rate)
    pedal_rate = 0.0 if pedal_rate < 0.0 else 1.0 if pedal_rate > 1.0 else pedal_rate

    accent_rate = 0.0 if hats_accent_rate is None else float(hats_accent_rate)
    accent_rate = 0.0 if accent_rate < 0.0 else 1.0 if accent_rate > 1.0 else accent_rate

    # Intent rules for open hats:
    # - We treat open hats as an "intent" that can be applied on eligible hat steps.
    # - Eligibility defaults to musical places that won't surprise users:
    #   * never on the bar downbeat
    #   * avoid snare backbeats
    #   * prefer offbeats ("and" positions) and the bar-end pickup
    # - Phrase end: slightly higher probability on the final bar of the section.
    # - Close-on-downbeat: if we opened on the previous bar-end, ensure a closed hat on the next downbeat.
    #
    # NOTE: We do NOT force placement if density gating skips the step.
    # However, once a step is placed, open_rate==1.0 will force that placed step to be open when eligible.
    if hat_steps:
        bar_end_step = max(int(s) for s in hat_steps if 0 <= int(s) < spb)
    else:
        bar_end_step = max(0, spb - 1)

    phrase_open_rate = open_rate
    if is_phrase_end_bar and phrase_open_rate > 0.0:
        phrase_open_rate = min(1.0, phrase_open_rate * 1.35)

    # Precompute eligible open-hat steps for this bar.
    # We only ever open hats when using hats (not ride) and open_rate > 0.
    eligible_open_steps: Set[int] = set()
    if (not template.use_ride) and open_rate > 0.0:
        # Always allow bar-end pickup if it's not the downbeat.
        if bar_end_step != 0:
            eligible_open_steps.add(int(bar_end_step))

        # For the common case: 4/4 with a 16-step grid, open hats can happen on offbeats.
        if spb == 16 and abs(bpb - 4.0) < 1e-6:
            eligible_open_steps.update({2, 6, 10, 14})
        else:
            # Generic fallback: prefer off-steps on the active hat grid.
            eligible_open_steps.update({int(s) for s in hat_steps if int(s) % 2 == 1})

        # Never open on downbeat or on exact snare backbeats.
        eligible_open_steps.discard(0)
        eligible_open_steps.difference_update({int(x) for x in backbeats})

    close_on_downbeat = (not template.use_ride) and prev_bar_open_hat

    for step_i in range(spb):
        if step_i not in hat_steps:
            continue

        # If the previous bar ended with an open hat, intentionally "close" it on the downbeat.
        # We bypass density gating here to make the musical gesture reliable, but we do not add
        # extra hits beyond the downbeat.
        if close_on_downbeat and step_i == 0:
            close_on_downbeat = False
            top_in_bar.add(step_i)
            beat = bar_start + float(step_i) * sb
            kind = "hat_close"
            vel = vel_for(
                base_vel=base_velocity,
                accent_strength=accent_strength,
                kind="hat",
                downbeat=True,
                rng=rng,
            )
            dur = 0.25
            events.append(
                DrumEvent(
                    beat=beat,
                    duration_beats=dur,
                    pitch=hat_closed,
                    velocity=vel,
                    kind=kind,
                )
            )
            continue

        if density < 1.0 and rng.random() >= density:
            continue

        top_in_bar.add(step_i)

        # Open hat intent: apply on eligible steps (offbeats + bar-end pickup), phrase-end boost.
        pitch = top_pitch
        kind = "ride" if template.use_ride else "hat"

        if (not template.use_ride) and open_rate > 0.0 and (step_i in eligible_open_steps):
            # If the user sets open_rate to 1.0, treat it as a hard intent:
            # every eligible step becomes an open hat (subject only to density gating).
            if open_rate >= 0.999:
                pitch = hat_open
                kind = "open_hat"
                open_hat_in_this_bar = True
            else:
                # Phrase-end boost is strongest on the bar-end pickup, but still applies elsewhere.
                p = phrase_open_rate if is_phrase_end_bar and step_i == bar_end_step else open_rate

                # Slightly bias non-pickup opens to be a bit rarer unless user cranks open_rate.
                if step_i != bar_end_step:
                    p = min(1.0, p * 0.85)

                if rng.random() < p:
                    pitch = hat_open
                    kind = "open_hat"
                    open_hat_in_this_bar = True

        beat = bar_start + float(step_i) * sb
        vel = vel_for(
            base_vel=base_velocity,
            accent_strength=accent_strength,
            kind=kind,
            downbeat=(step_i == 0 or (spb == 16 and step_i in (4, 8, 12))),
            rng=rng,
        )
        # Small built-in offbeat hat lift for common 4/4 16th grids.
        if spb == 16 and abs(bpb - 4.0) < 1e-6 and step_i in (2, 6, 10, 14):
            vel = clamp_int(vel + 3, 1, 127)

        # Optional additional accents on common offbeats / bar-end pickup.
        if accent_rate > 0.0 and not template.use_ride:
            eligible = (step_i == bar_end_step) or (spb == 16 and abs(bpb - 4.0) < 1e-6 and step_i in (2, 6, 10, 14))
            if eligible and rng.random() < accent_rate:
                vel = clamp_int(vel + 8, 1, 127)

        dur = 0.5 if kind in ("open_hat", "ride") else 0.25
        events.append(DrumEvent(beat=beat, duration_beats=dur, pitch=pitch, velocity=vel, kind=kind))

    # Optional pedal hat (foot chick) on common backbeats (e.g., 2 and 4 in 4/4).
    if pedal_rate > 0.0 and not template.use_ride:
        # Determine "backbeat" beats for the current meter.
        pedal_steps: Tuple[int, ...] = tuple()
        bpb_i = int(round(bpb))
        if bpb_i >= 4 and spb % bpb_i == 0:
            spb_per_beat = max(1, spb // bpb_i)
            pedal_steps = (1 * spb_per_beat, 3 * spb_per_beat)
        elif bpb_i >= 2 and spb % bpb_i == 0:
            spb_per_beat = max(1, spb // bpb_i)
            pedal_steps = (1 * spb_per_beat,)

        for s in pedal_steps:
            s = int(s)
            if not (0 <= s < spb):
                continue
            if rng.random() < pedal_rate:
                beat = bar_start + float(s) * sb
                vel = vel_for(
                    base_vel=base_velocity,
                    accent_strength=accent_strength,
                    kind="hat",
                    downbeat=False,
                    rng=rng,
                )
                vel = clamp_int(vel + 6, 1, 127)
                events.append(
                    DrumEvent(
                        beat=beat,
                        duration_beats=0.25,
                        pitch=hat_pedal,
                        velocity=vel,
                        kind="hat_pedal",
                    )
                )

    return events, open_hat_in_this_bar, top_in_bar
