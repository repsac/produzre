"""Transition handling for rhythm guitar (Phase RG5).

This module handles section transitions and turnarounds to make section changes
feel less static by using transitions.map data from the performance plan.

Transition types:
- Build: Increase density or add pickup before high-energy sections
- Downshift: Start sparse and ramp up when coming from high-energy
- Turnaround: Distinctive cadence pattern in the last bar
"""

from __future__ import annotations

import random
from typing import Optional, Dict, Any

from .types import GtrPattern


def get_transition_directive(
    plan: Dict[str, Any],
    section_id: str,
) -> Optional[Dict[str, Any]]:
    """Extract transition directive for a section from the plan.

    Args:
        plan: Performance plan containing transitions.map
        section_id: Section identifier

    Returns:
        dict: Transition directive or None if not found
    """
    if not plan:
        return None

    transitions_map = plan.get("transitions.map")
    if not transitions_map:
        return None

    return transitions_map.get(section_id)


def should_apply_build(transition: Optional[Dict[str, Any]]) -> bool:
    """Check if this section should build into the next.

    A "build" increases energy/density toward the end of the section.

    Args:
        transition: Transition directive

    Returns:
        bool: True if should build
    """
    if not transition:
        return False

    # Build if energy or density ramps up
    energy_ramp = transition.get("energy_ramp", 0.0)
    density_ramp = transition.get("density_ramp", 0.0)

    return energy_ramp > 0.3 or density_ramp > 0.3


def should_apply_downshift(transition: Optional[Dict[str, Any]]) -> bool:
    """Check if the next section should start with a downshift.

    A "downshift" means starting sparse and ramping up.

    Args:
        transition: Transition directive

    Returns:
        bool: True if should downshift
    """
    if not transition:
        return False

    # Downshift if energy or density ramps down significantly
    energy_ramp = transition.get("energy_ramp", 0.0)
    density_ramp = transition.get("density_ramp", 0.0)

    return energy_ramp < -0.3 or density_ramp < -0.3


def get_turnaround_intensity(transition: Optional[Dict[str, Any]]) -> str:
    """Get turnaround intensity for the section.

    Args:
        transition: Transition directive

    Returns:
        str: "none", "light", or "heavy"
    """
    if not transition:
        return "none"

    return transition.get("turnaround_hint", "none")


def should_add_pickup(transition: Optional[Dict[str, Any]]) -> bool:
    """Check if pickup notes should be added before transition.

    Args:
        transition: Transition directive

    Returns:
        bool: True if should add pickup
    """
    if not transition:
        return False

    return transition.get("pickup_hint", False)


def get_lead_in_bars(transition: Optional[Dict[str, Any]]) -> int:
    """Get number of bars before transition to start ramping.

    Args:
        transition: Transition directive

    Returns:
        int: Number of lead-in bars (typically 1-2)
    """
    if not transition:
        return 1

    return transition.get("lead_in_bars", 1)


def apply_build_to_pattern(
    pattern: GtrPattern,
    build_intensity: float,
    bar_position: float,
    beats_per_bar: float,
    rng: Optional[random.Random] = None,
) -> GtrPattern:
    """Apply build effect to a pattern (increase density/accents).

    Args:
        pattern: Original pattern
        build_intensity: How much to build (0.0-1.0)
        bar_position: Position within lead-in (0.0 = start, 1.0 = end)
        beats_per_bar: Beats per bar
        rng: Random generator

    Returns:
        GtrPattern: Modified pattern with build applied
    """
    if rng is None:
        rng = random.Random()

    if build_intensity <= 0.0:
        return pattern

    # Scale build intensity by bar position (ramps up toward end)
    scaled_intensity = build_intensity * bar_position

    # Add extra hits based on build intensity
    hits = list(pattern.hits)
    subdivision = pattern.subdivision
    total_slots = int(beats_per_bar * subdivision)

    # Add off-beat hits to increase density
    for i in range(total_slots):
        if i not in hits and rng.random() < (scaled_intensity * 0.5):
            hits.append(i)

    hits = sorted(hits)

    # Add more accents during build
    accents = list(pattern.accents)
    for hit in hits:
        if hit not in accents and rng.random() < (scaled_intensity * 0.6):
            accents.append(hit)

    accents = sorted(accents)

    # Recompute strum directions from slot parity: the original directions list
    # is positional (one per hit) and misaligns once hits are added.
    directions = ["down" if (h % subdivision) == 0 else "up" for h in hits]

    return GtrPattern(
        name=f"{pattern.name}_build",
        subdivision=pattern.subdivision,
        hits=hits,
        accents=accents,
        palm_mutes=pattern.palm_mutes,
        strum_directions=directions,
        density=pattern.density,
    )


def apply_downshift_to_pattern(
    pattern: GtrPattern,
    downshift_intensity: float,
    bar_position: float,
    beats_per_bar: float,
    rng: Optional[random.Random] = None,
) -> GtrPattern:
    """Apply downshift effect to a pattern (reduce density at start).

    Args:
        pattern: Original pattern
        downshift_intensity: How much to downshift (0.0-1.0)
        bar_position: Position within downshift (0.0 = start, 1.0 = normal)
        beats_per_bar: Beats per bar

    Returns:
        GtrPattern: Modified pattern with downshift applied
    """
    if downshift_intensity <= 0.0 or bar_position >= 1.0:
        return pattern
    if rng is None:
        rng = random.Random()

    # Scale downshift by position (reduces from start to normal)
    scaled_intensity = downshift_intensity * (1.0 - bar_position)

    # Thin out hits based on downshift intensity
    if scaled_intensity <= 0.0:
        return pattern

    # Keep only strong beats at high downshift
    keep_probability = 1.0 - scaled_intensity
    hits = []
    subdivision = pattern.subdivision

    for hit in pattern.hits:
        # Always keep beat 1
        if hit == 0:
            hits.append(hit)
            continue

        # Keep strong beats (downbeats)
        beat_pos = hit / subdivision
        is_downbeat = abs(beat_pos - round(beat_pos)) < 0.1

        if is_downbeat:
            hits.append(hit)
        elif rng.random() < keep_probability:
            hits.append(hit)

    # Reduce accents during downshift
    accents = [a for a in pattern.accents if a in hits and a == 0]

    # Keep palm mutes only for hits we kept
    palm_mutes = [pm for pm in pattern.palm_mutes if pm in hits]

    # Recompute strum directions from slot parity (positional list misaligns
    # after hits were removed).
    directions = ["down" if (h % subdivision) == 0 else "up" for h in hits]

    return GtrPattern(
        name=f"{pattern.name}_downshift",
        subdivision=pattern.subdivision,
        hits=hits,
        accents=accents,
        palm_mutes=palm_mutes,
        strum_directions=directions,
        density=pattern.density * (1.0 - scaled_intensity),
    )


def create_turnaround_pattern(
    style: str,
    turnaround_intensity: str,
    beats_per_bar: float,
    base_pattern: Optional[GtrPattern] = None,
) -> GtrPattern:
    """Create a turnaround pattern for the last bar of a section.

    Turnarounds are distinctive cadence patterns that signal section endings.

    Contract: the returned pattern's hits are BAR-ABSOLUTE slot indices in the
    pattern's own subdivision (slot = beat_in_bar * subdivision). They must be
    overlaid onto a base pattern with ``merge_patterns`` (which rescales them
    into the base subdivision) — do NOT shift them by an additional offset.

    Args:
        style: Pattern style (straight_8s, chugs, etc.)
        turnaround_intensity: "none", "light", or "heavy"
        beats_per_bar: Beats per bar
        base_pattern: Optional base pattern to modify

    Returns:
        GtrPattern: Turnaround pattern
    """
    if turnaround_intensity == "none":
        return base_pattern if base_pattern else GtrPattern(
            name="no_turnaround",
            subdivision=2,
            hits=[],
            accents=[],
            palm_mutes=[],
            strum_directions=[],
            density=0.0,
        )

    subdivision = 4  # Use 16th notes for turnarounds

    if turnaround_intensity == "light":
        # Light turnaround: hits on beats 3 and 4
        hits = [
            int(2 * subdivision),  # Beat 3
            int(3 * subdivision),  # Beat 4
        ]
        accents = hits.copy()

    else:  # "heavy"
        # Heavy turnaround: rapid hits leading to beat 1 of next bar
        hits = [
            int(2 * subdivision),      # Beat 3
            int(2.5 * subdivision),    # Beat 3.5
            int(3 * subdivision),      # Beat 4
            int(3.5 * subdivision),    # Beat 4.5
        ]
        accents = [hits[0], hits[-1]]  # Accent first and last

    # All downstrokes for power
    directions = ["down"] * len(hits)

    return GtrPattern(
        name=f"turnaround_{turnaround_intensity}",
        subdivision=subdivision,
        hits=hits,
        accents=accents,
        palm_mutes=[],
        strum_directions=directions,
        density=len(hits) / (beats_per_bar * subdivision),
    )


def create_pickup_pattern(
    beats_per_bar: float,
    pickup_style: str = "eighth",
) -> GtrPattern:
    """Create a pickup pattern for the last beat before transition.

    Contract: hits are BAR-ABSOLUTE slot indices in this pattern's own
    subdivision (slot = beat_in_bar * subdivision); merge them with
    ``merge_patterns`` without any extra offset.

    Args:
        beats_per_bar: Beats per bar
        pickup_style: "eighth" or "sixteenth"

    Returns:
        GtrPattern: Pickup pattern
    """
    subdivision = 4 if pickup_style == "sixteenth" else 2

    if pickup_style == "sixteenth":
        # 16th note pickups on beat 4
        hits = [
            int((beats_per_bar - 0.5) * subdivision),
            int((beats_per_bar - 0.25) * subdivision),
        ]
    else:  # eighth
        # Single eighth note pickup on the "and" of beat 4
        hits = [int((beats_per_bar - 0.5) * subdivision)]

    # All upstrokes for pickups
    directions = ["up"] * len(hits)

    return GtrPattern(
        name=f"pickup_{pickup_style}",
        subdivision=subdivision,
        hits=hits,
        accents=[],
        palm_mutes=[],
        strum_directions=directions,
        density=len(hits) / (beats_per_bar * subdivision),
    )


def merge_patterns(
    base_pattern: GtrPattern,
    overlay_pattern: GtrPattern,
    beats_per_bar: float = 4.0,
) -> GtrPattern:
    """Merge two patterns, overlaying one on top of the other.

    Contract: hits in BOTH patterns are bar-absolute slot indices expressed
    in each pattern's OWN subdivision (slot = beat_in_bar * subdivision).
    Overlay hits are rescaled into the output subdivision — no positional
    offset is applied (turnaround/pickup hits already encode their bar
    position). The output uses the finer of the two subdivisions so 16th-note
    overlays survive merging into an 8th-note base. All merged slots are
    clamped to the bar (< beats_per_bar * subdivision).

    Args:
        base_pattern: Base pattern
        overlay_pattern: Pattern to overlay (e.g., pickup or turnaround)
        beats_per_bar: Beats per bar (defines the bar boundary for clamping)

    Returns:
        GtrPattern: Merged pattern
    """
    base_sub = max(1, int(base_pattern.subdivision))
    overlay_sub = max(1, int(overlay_pattern.subdivision))
    # Output at the finer grid so rescaled slots stay integral.
    out_sub = base_sub
    while out_sub % overlay_sub != 0 or out_sub % base_sub != 0:
        out_sub += 1
    total_slots = max(1, int(beats_per_bar * out_sub))

    def _rescale(slots, sub):
        factor = out_sub // sub
        return [h * factor for h in slots if 0 <= h * factor < total_slots]

    merged_hits = sorted(
        set(_rescale(base_pattern.hits, base_sub))
        | set(_rescale(overlay_pattern.hits, overlay_sub))
    )
    merged_accents = sorted(
        set(_rescale(base_pattern.accents, base_sub))
        | set(_rescale(overlay_pattern.accents, overlay_sub))
    )
    merged_palm_mutes = sorted(
        set(_rescale(base_pattern.palm_mutes, base_sub))
        | set(_rescale(overlay_pattern.palm_mutes, overlay_sub))
    )

    # Recompute strum directions from slot parity — positional direction lists
    # from either source pattern no longer line up after merging.
    merged_directions = [
        "down" if (h % out_sub) == 0 else "up" for h in merged_hits
    ]

    return GtrPattern(
        name=f"{base_pattern.name}_merged",
        subdivision=out_sub,
        hits=merged_hits,
        accents=merged_accents,
        palm_mutes=merged_palm_mutes,
        strum_directions=merged_directions,
        density=len(merged_hits) / total_slots,
    )


def adjust_pattern_for_transition(
    pattern: GtrPattern,
    bar_idx: int,
    total_bars: int,
    transition: Optional[Dict[str, Any]],
    beats_per_bar: float,
    rng: Optional[random.Random] = None,
) -> GtrPattern:
    """Adjust a pattern based on transition context.

    This is the main entry point for applying transition effects.

    Args:
        pattern: Original pattern for the bar
        bar_idx: Current bar index (0-based)
        total_bars: Total number of bars in section
        transition: Transition directive from plan
        beats_per_bar: Beats per bar
        rng: Random generator

    Returns:
        GtrPattern: Adjusted pattern
    """
    if not transition:
        return pattern

    if rng is None:
        rng = random.Random()

    lead_in_bars = get_lead_in_bars(transition)
    is_last_bar = (bar_idx == total_bars - 1)
    is_first_bar = (bar_idx == 0)

    # Calculate bar position within lead-in window
    bars_from_end = total_bars - bar_idx - 1
    is_in_lead_in = bars_from_end < lead_in_bars

    # Apply build transition (last bars of section)
    if is_in_lead_in and should_apply_build(transition):
        # bar_position: 0.0 at start of lead-in, 1.0 at end
        bar_position = 1.0 - (bars_from_end / lead_in_bars)
        energy_ramp = transition.get("energy_ramp", 0.0)
        density_ramp = transition.get("density_ramp", 0.0)
        build_intensity = max(energy_ramp, density_ramp)
        pattern = apply_build_to_pattern(
            pattern, build_intensity, bar_position, beats_per_bar, rng
        )

    # Apply turnaround (last bar only)
    if is_last_bar:
        turnaround_intensity = get_turnaround_intensity(transition)
        if turnaround_intensity != "none":
            turnaround = create_turnaround_pattern(
                style=pattern.name.split("_")[0],  # Extract base style
                turnaround_intensity=turnaround_intensity,
                beats_per_bar=beats_per_bar,
                base_pattern=pattern,
            )
            # Turnaround hits are bar-absolute; merge without extra offset.
            pattern = merge_patterns(pattern, turnaround, beats_per_bar)

        # Add pickup notes before transition
        if should_add_pickup(transition):
            pickup = create_pickup_pattern(beats_per_bar, pickup_style="eighth")
            pattern = merge_patterns(pattern, pickup, beats_per_bar)

    # Apply downshift transition (first bars of section coming from high energy)
    # Note: This requires looking at the PREVIOUS section's transition
    # For now, we'll skip this as it requires more context
    # TODO: Implement downshift by looking at previous section in higher-level function

    return pattern
