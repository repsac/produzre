"""Snare drum event generation (backbeat and ghost notes).

This module handles all snare-related event generation including backbeat hits
and ghost notes with intelligent defaults near backbeats.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Sequence, Set, Tuple

from .utils import vel_for

__all__ = ["default_ghost_steps", "generate_snare_events"]


def default_ghost_steps(steps_per_bar: int, backbeats: Sequence[int]) -> Tuple[int, ...]:
    """Return sensible default ghost-note steps near backbeats.

    When a template enables ghost notes but doesn't specify explicit ghost steps,
    we infer a small set of placements a drummer commonly uses:

    - Just before the backbeat ("a" or "and")
    - Occasionally just after the backbeat

    This keeps ghosts musical on common grids (e.g. 16-step 4/4) without needing
    template authors to hard-code step numbers.

    Parameters
    ----------
    steps_per_bar : int
        Number of steps per bar.
    backbeats : Sequence[int]
        Backbeat step indices.

    Returns
    -------
    Tuple[int, ...]
        Inferred ghost step indices near backbeats.
    """
    spb = max(1, int(steps_per_bar))
    bb = [int(x) for x in backbeats]
    if not bb:
        return tuple()

    candidates: Set[int] = set()

    # Offsets around each backbeat step.
    # Prefer -1/-2 (pre-ghosts); include +1 (post-ghost) sparingly.
    for b in bb:
        for off in (-2, -1, 1):
            s = int(b) + int(off)
            if 0 <= s < spb and s != int(b):
                candidates.add(s)

    # Favor off-step positions on common grids (odd indices on 16-step grids).
    if spb >= 8:
        candidates = {s for s in candidates if (s % 2 == 1) or (spb % 2 != 0)}

    return tuple(sorted(candidates))


def generate_snare_events(
    *,
    bar_i: int,
    bars: int,
    bar_start: float,
    spb: int,
    sb: float,
    backbeats: Tuple[int, ...],
    ghost_steps: Optional[Sequence[int]],
    effective_ghost_rate: float,
    base_velocity: int,
    accent_strength: float,
    ghost_velocity_bias: Optional[int],
    rng: random.Random,
    pitches: Dict[str, int],
    density_multiplier: float = 1.0,
) -> List:
    """Generate snare drum events for a single bar.

    Combines backbeat snare hits and ghost notes with intelligent defaults
    near backbeats.

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
    backbeats : Tuple[int, ...]
        Backbeat step indices for snare hits.
    ghost_steps : Optional[Sequence[int]]
        Optional override for ghost placement steps. If None, uses defaults.
    effective_ghost_rate : float
        Ghost rate from template or override (0..1).
    base_velocity : int
        Base velocity for the section.
    accent_strength : float
        Accent influence (0.0 to 1.0).
    ghost_velocity_bias : Optional[int]
        Velocity bias specifically for ghost notes (e.g., -10 to make them softer).
    rng : random.Random
        Deterministic RNG for this section.
    pitches : Dict[str, int]
        Pitch mapping with required key 'snare'.
    density_multiplier : float
        Multiplier applied to ghost_rate (0.5-1.5 typical). Defaults to 1.0.

    Returns
    -------
    List[DrumEvent]
        Generated snare events.

    Notes
    -----
    This function is designed to be called once per bar by the orchestration layer.
    The RNG must be passed to maintain deterministic output.
    """
    # Import DrumEvent locally to avoid circular dependency
    from .kit import DrumEvent

    snare = int(pitches["snare"])
    events: List[DrumEvent] = []

    # Snare backbeat
    for step_i in backbeats:
        step_i = int(step_i)
        if 0 <= step_i < spb:
            beat = bar_start + float(step_i) * sb
            vel = vel_for(
                base_vel=base_velocity,
                accent_strength=accent_strength,
                kind="snare",
                downbeat=False,
                rng=rng,
            )
            events.append(DrumEvent(beat=beat, duration_beats=0.25, pitch=snare, velocity=vel, kind="snare"))

    # Snare ghosts
    if effective_ghost_rate > 0.0:
        base_rate = float(effective_ghost_rate) * float(density_multiplier)
        bb_set = set(backbeats)

        # If explicit ghost placements are not provided (template or override),
        # infer defaults near the backbeat so ghosts work out-of-the-box.
        if ghost_steps is None:
            ghost_steps_eff = tuple()
        else:
            ghost_steps_eff = tuple(int(x) for x in ghost_steps)

        ghost_steps_eff = ghost_steps_eff if ghost_steps_eff else default_ghost_steps(spb, backbeats)

        # Gentle contour across the section: slightly more chatter late in the section.
        section_pos = 0.0 if bars <= 1 else float(bar_i) / float(max(1, bars - 1))
        contour = 0.85 + 0.35 * section_pos  # 0.85 .. 1.20
        rate = base_rate * contour
        if rate > 1.0:
            rate = 1.0

        for step_i in ghost_steps_eff:
            step_i = int(step_i)
            if not (0 <= step_i < spb):
                continue
            if step_i in bb_set:
                continue
            if rng.random() < rate:
                beat = bar_start + float(step_i) * sb
                vel = vel_for(
                    base_vel=base_velocity,
                    accent_strength=accent_strength,
                    kind="snare_ghost",
                    downbeat=False,
                    rng=rng,
                )
                # Apply ghost velocity bias if specified
                if ghost_velocity_bias is not None:
                    from .utils import clamp_int
                    vel = clamp_int(vel + int(ghost_velocity_bias), 1, 127)

                events.append(
                    DrumEvent(
                        beat=beat,
                        duration_beats=0.25,
                        pitch=snare,
                        velocity=vel,
                        kind="snare_ghost",
                    )
                )

    return events
