"""Rhythm pattern generation for rhythm guitar (Phase RG2).

This module generates guitar strumming patterns based on rhythm grid data,
accent positions, and style preferences. It supports multiple playing styles:
- straight_8s: Rock-style eighth note strumming
- chugs: Metal-style palm-muted 16th notes
- syncopated: Off-beat emphasis patterns
- half_time: Sparse, heavy hits for choruses

Pattern generation is deterministic given RNG and parameters.
"""

from __future__ import annotations

import random
from typing import List, Optional, Set

from .types import GtrPattern
from .defaults import DENSITY_TARGET, PALM_MUTE_BIAS


def build_bar_pattern(
    section_type: str,
    style: str = "auto",
    density: Optional[float] = None,
    accent_beats: Optional[List[float]] = None,
    beats_per_bar: float = 4.0,
    rng: Optional[random.Random] = None,
) -> GtrPattern:
    """Build a rhythm guitar pattern for one bar.

    Args:
        section_type: Section type (verse, chorus, bridge, etc.)
        style: Pattern style ("auto", "straight_8s", "chugs", "syncopated", "half_time")
        density: Pattern density override (0.0-1.0), or None to use section default
        accent_beats: List of accent beat positions within the bar (0.0-4.0 for 4/4)
        beats_per_bar: Beats per bar (typically 4.0 for 4/4 time)
        rng: Random generator for deterministic pattern variations

    Returns:
        GtrPattern: Guitar pattern with hits, accents, palm mutes, and directions
    """
    if rng is None:
        rng = random.Random()

    # Resolve density from section type if not specified
    if density is None:
        density = DENSITY_TARGET.get(section_type, 0.5)
    density = max(0.0, min(1.0, density))

    # Map user-friendly strum_style names to internal style names
    style_mapping = {
        "downbeat_heavy": "straight_8s",
        "upbeat_heavy": "syncopated",
        "balanced": "auto",
    }
    if style in style_mapping:
        style = style_mapping[style]

    # Auto-select style based on section type if needed
    if style == "auto":
        style = _choose_style_for_section(section_type, density, rng)

    # Build pattern based on style
    if style == "straight_8s":
        pattern = _build_straight_8s(density, beats_per_bar, rng)
    elif style == "chugs":
        pattern = _build_chugs(density, beats_per_bar, rng)
    elif style == "syncopated":
        pattern = _build_syncopated(density, beats_per_bar, rng)
    elif style == "half_time":
        pattern = _build_half_time(density, beats_per_bar, rng)
    else:
        # Fallback to straight_8s for unknown styles
        pattern = _build_straight_8s(density, beats_per_bar, rng)

    # Apply accent integration from rhythm.accents
    if accent_beats:
        pattern = _apply_accents(pattern, accent_beats, beats_per_bar)

    # Apply palm mute bias based on section type
    pm_bias = PALM_MUTE_BIAS.get(section_type, 0.5)
    pattern = _apply_palm_mutes(pattern, pm_bias, rng)

    return pattern


def develop_bar_pattern(
    pattern: GtrPattern,
    *,
    bar_idx: int,
    total_bars: int,
    phrase_len_bars: int = 4,
    section_type: str = "verse",
    density: float = 0.5,
    beats_per_bar: float = 4.0,
    rng: Optional[random.Random] = None,
) -> GtrPattern:
    """Apply phrase-level rhythm guitar variation to a one-bar pattern."""
    if rng is None:
        rng = random.Random()

    if not pattern.hits:
        return pattern

    subdivision = int(pattern.subdivision)
    total_slots = max(1, int(float(beats_per_bar) * subdivision))
    phrase_len = max(1, int(phrase_len_bars))
    phrase_pos = bar_idx % phrase_len
    is_phrase_end = phrase_pos == phrase_len - 1 or bar_idx == total_bars - 1
    is_section_end = bar_idx == total_bars - 1

    hits = set(int(h) for h in pattern.hits if 0 <= int(h) < total_slots)
    accents = set(int(a) for a in pattern.accents if int(a) in hits)
    palm_mutes = set(int(pm) for pm in pattern.palm_mutes if int(pm) in hits)

    # Leave air after phrase starts, especially in verses and lower-density parts.
    if phrase_pos == 1 and density < 0.75:
        removable = [h for h in sorted(hits) if h != 0 and (h % subdivision) != 0]
        for h in removable:
            if rng.random() < (0.18 + (0.20 * (1.0 - min(1.0, density)))):
                hits.discard(h)
                accents.discard(h)
                palm_mutes.discard(h)

    # Phrase endings answer with a small pickup or syncopated push.
    if is_phrase_end:
        last_beat = max(0, int((beats_per_bar - 1.0) * subdivision))
        candidates = [
            last_beat,
            min(total_slots - 1, last_beat + max(1, subdivision // 2)),
            min(total_slots - 1, total_slots - 1),
        ]
        add_prob = 0.45 + (0.35 * min(1.0, density))
        for h in candidates:
            if rng.random() < add_prob:
                hits.add(h)
                if h >= last_beat:
                    accents.add(h)

        # Cadences often cut the last offbeat so the next downbeat lands harder.
        if is_section_end and rng.random() < 0.45:
            late_weak = [h for h in hits if h >= total_slots - subdivision and h not in accents]
            if late_weak:
                h = rng.choice(sorted(late_weak))
                hits.discard(h)
                palm_mutes.discard(h)

    # Bridges and breakdowns should not just clone verse/chorus comping.
    st = (section_type or "").lower()
    if st in ("bridge", "breakdown", "solo") and total_slots > subdivision:
        sync_hits = [
            min(total_slots - 1, subdivision + subdivision // 2),
            min(total_slots - 1, (2 * subdivision) + subdivision // 2),
        ]
        for h in sync_hits:
            if rng.random() < 0.38 + (density * 0.25):
                hits.add(h)
                accents.add(h)

    hits_list = sorted(hits)
    directions = ["down" if (h % subdivision) == 0 else "up" for h in hits_list]

    return GtrPattern(
        name=f"{pattern.name}_dev{bar_idx % phrase_len}",
        subdivision=pattern.subdivision,
        hits=hits_list,
        accents=sorted(a for a in accents if a in hits),
        palm_mutes=sorted(pm for pm in palm_mutes if pm in hits),
        strum_directions=directions,
        density=pattern.density,
    )


def _choose_style_for_section(
    section_type: str,
    density: float,
    rng: random.Random,
) -> str:
    """Auto-select pattern style based on section type and density.

    Args:
        section_type: Section type (verse, chorus, etc.)
        density: Pattern density (0.0-1.0)
        rng: Random generator for tie-breaking

    Returns:
        str: Style name ("straight_8s", "chugs", "syncopated", "half_time")
    """
    # High-energy sections tend toward power patterns
    if section_type in ("chorus", "climax", "shout"):
        if density > 0.75:
            return "chugs"  # Heavy, driving
        elif density > 0.5:
            return "straight_8s"  # Solid, rock
        else:
            return "half_time"  # Sparse, impactful

    # Verse sections use more variety
    elif section_type in ("verse", "prechorus"):
        if density > 0.6:
            return "syncopated"  # Rhythmic interest
        else:
            return "straight_8s"  # Steady foundation

    # Bridge/breakdown sections favor complexity
    elif section_type in ("bridge", "breakdown", "solo"):
        if density > 0.7:
            return rng.choice(["chugs", "syncopated"])
        else:
            return "syncopated"

    # Intro/outro sections favor simplicity
    elif section_type in ("intro", "outro", "interlude"):
        if density < 0.4:
            return "half_time"
        else:
            return "straight_8s"

    # Default: straight_8s
    return "straight_8s"


def _build_straight_8s(
    density: float,
    beats_per_bar: float,
    rng: random.Random,
) -> GtrPattern:
    """Build a straight eighth-note rock pattern.

    Typical pattern: downstroke on downbeats, upstroke on upbeats.
    Density controls how many eighth notes are played.

    Args:
        density: Pattern density (0.0-1.0)
        beats_per_bar: Beats per bar
        rng: Random generator

    Returns:
        GtrPattern: Eighth-note pattern
    """
    subdivision = 2  # 2 subdivisions per beat (eighth notes)
    total_slots = int(beats_per_bar * subdivision)

    # Start with all downbeat eighth notes
    hits = [i for i in range(total_slots) if i % 2 == 0]

    # Add upbeats based on density
    upbeat_probability = density
    for i in range(total_slots):
        if i % 2 == 1:  # Upbeat
            if rng.random() < upbeat_probability:
                hits.append(i)

    hits = sorted(hits)

    # Strum directions: down on downbeats, up on upbeats
    directions = ["down" if i % 2 == 0 else "up" for i in hits]

    # Accent first beat of each bar and strong beats
    accents = [i for i in hits if i % (subdivision * 2) == 0]  # Every 2 beats

    return GtrPattern(
        name=f"straight_8s_d{int(density*100)}",
        subdivision=subdivision,
        hits=hits,
        accents=accents,
        palm_mutes=[],
        strum_directions=directions,
        density=density,
    )


def _build_chugs(
    density: float,
    beats_per_bar: float,
    rng: random.Random,
) -> GtrPattern:
    """Build a metal-style palm-muted 16th note chug pattern.

    Typical pattern: rapid 16th notes with heavy palm muting and accents.
    Density controls pattern complexity.

    Args:
        density: Pattern density (0.0-1.0)
        beats_per_bar: Beats per bar
        rng: Random generator

    Returns:
        GtrPattern: Chug pattern with palm mutes
    """
    subdivision = 4  # 4 subdivisions per beat (16th notes)
    total_slots = int(beats_per_bar * subdivision)

    # Base pattern: downbeat 16ths
    hits = []
    for i in range(total_slots):
        # Always hit beat 1 and 3 in 4/4
        beat_pos = i / subdivision
        if abs(beat_pos - int(beat_pos)) < 0.01:  # On the beat
            hits.append(i)
        elif density > 0.5 and i % 2 == 0:  # Eighth notes at medium density
            hits.append(i)
        elif density > 0.75 and rng.random() < 0.7:  # More 16ths at high density
            hits.append(i)

    hits = sorted(set(hits))

    # All downstrokes for chugs (aggressive)
    directions = ["down"] * len(hits)

    # Accent strong beats (1 and 3)
    accents = [i for i in hits if i % (subdivision * 2) == 0]

    # Most hits are palm muted for chugs (will be refined by _apply_palm_mutes)
    palm_mutes = hits.copy()

    return GtrPattern(
        name=f"chugs_d{int(density*100)}",
        subdivision=subdivision,
        hits=hits,
        accents=accents,
        palm_mutes=palm_mutes,
        strum_directions=directions,
        density=density,
    )


def _build_syncopated(
    density: float,
    beats_per_bar: float,
    rng: random.Random,
) -> GtrPattern:
    """Build a syncopated off-beat pattern.

    Emphasizes upbeats and the "and" of beats for rhythmic interest.
    Density controls how sparse or busy the pattern is.

    Args:
        density: Pattern density (0.0-1.0)
        beats_per_bar: Beats per bar
        rng: Random generator

    Returns:
        GtrPattern: Syncopated pattern
    """
    subdivision = 4  # 16th notes for syncopation
    total_slots = int(beats_per_bar * subdivision)

    hits = []
    # Always hit beat 1 (downbeat)
    hits.append(0)

    # Add "and" of beats (eighth note upbeats)
    for beat in range(int(beats_per_bar)):
        and_pos = beat * subdivision + 2  # The "and" of the beat
        if and_pos < total_slots:
            if density > 0.3 or beat == 0:  # More likely on beat 1
                hits.append(and_pos)

    # Add some 16th note syncopation at higher density
    if density > 0.6:
        for i in range(total_slots):
            if i not in hits and i % 4 == 3:  # "e-and-a" positions
                if rng.random() < (density - 0.6):
                    hits.append(i)

    hits = sorted(set(hits))

    # Directions: down on strong positions, up on weak
    directions = []
    for hit in hits:
        if hit % 4 == 0:  # On the beat
            directions.append("down")
        else:  # Off-beat
            directions.append("up")

    # Accent the off-beats for syncopation feel
    accents = [i for i in hits if i % 4 == 2]  # "and" positions

    return GtrPattern(
        name=f"syncopated_d{int(density*100)}",
        subdivision=subdivision,
        hits=hits,
        accents=accents,
        palm_mutes=[],
        strum_directions=directions,
        density=density,
    )


def _build_half_time(
    density: float,
    beats_per_bar: float,
    rng: random.Random,
) -> GtrPattern:
    """Build a sparse half-time feel pattern.

    Fewer hits with more space, creating a heavy, open sound.
    Common in choruses for lift and impact.

    Args:
        density: Pattern density (0.0-1.0)
        beats_per_bar: Beats per bar
        rng: Random generator

    Returns:
        GtrPattern: Half-time pattern
    """
    subdivision = 2  # Eighth notes
    total_slots = int(beats_per_bar * subdivision)

    # Minimal hits: beat 1, maybe beat 3
    hits = [0]  # Always beat 1

    # Add beat 3 based on density
    beat_3_pos = int(beats_per_bar / 2) * subdivision
    if density > 0.3:
        hits.append(beat_3_pos)

    # Maybe add beat 2 or 4 at higher density
    if density > 0.6:
        if rng.random() < 0.5:
            hits.append(subdivision)  # Beat 2
        else:
            hits.append(3 * subdivision)  # Beat 4

    hits = sorted(set(hits))

    # All downstrokes for power
    directions = ["down"] * len(hits)

    # Accent all hits in half-time (they're all important)
    accents = hits.copy()

    return GtrPattern(
        name=f"half_time_d{int(density*100)}",
        subdivision=subdivision,
        hits=hits,
        accents=accents,
        palm_mutes=[],
        strum_directions=directions,
        density=density,
    )


def _apply_accents(
    pattern: GtrPattern,
    accent_beats: List[float],
    beats_per_bar: float,
) -> GtrPattern:
    """Apply accent markers based on rhythm.accents from drums.

    Args:
        pattern: Existing pattern to modify
        accent_beats: Beat positions within the bar that should be accented
        beats_per_bar: Beats per bar

    Returns:
        GtrPattern: Pattern with updated accents
    """
    # Convert accent beats to subdivision indices.
    # Bound by the bar's total slot count (beats_per_bar * subdivision), NOT by
    # the number of hits — hits are slot indices, not a dense array.
    total_slots = max(1, int(beats_per_bar * pattern.subdivision))
    accent_indices: Set[int] = set()

    for accent_beat in accent_beats:
        # Normalize to bar-relative position
        bar_beat = accent_beat % beats_per_bar
        # Convert to subdivision index
        subdivision_idx = int(round(bar_beat * pattern.subdivision))
        if 0 <= subdivision_idx < total_slots:
            accent_indices.add(subdivision_idx)

    # Find hits that are close to accent beats: exact slot match or directly
    # adjacent slot (1-slot proximity window).
    new_accents = set(pattern.accents)
    for hit in pattern.hits:
        for acc_idx in accent_indices:
            if abs(hit - acc_idx) <= 1:
                new_accents.add(hit)
                break

    return GtrPattern(
        name=pattern.name,
        subdivision=pattern.subdivision,
        hits=pattern.hits,
        accents=sorted(list(new_accents)),
        palm_mutes=pattern.palm_mutes,
        strum_directions=pattern.strum_directions,
        density=pattern.density,
    )


def _apply_palm_mutes(
    pattern: GtrPattern,
    pm_bias: float,
    rng: random.Random,
) -> GtrPattern:
    """Apply palm muting to pattern based on bias.

    Args:
        pattern: Existing pattern to modify
        pm_bias: Palm mute probability (0.0-1.0)
        rng: Random generator

    Returns:
        GtrPattern: Pattern with updated palm mutes
    """
    if pm_bias <= 0.0:
        return pattern

    # Start with existing palm mutes (e.g., from chugs)
    palm_mutes = set(pattern.palm_mutes)

    # Add palm mutes probabilistically
    for hit in pattern.hits:
        # Don't palm mute accents (they need to ring out)
        if hit in pattern.accents:
            continue

        # Apply palm mute based on bias
        if rng.random() < pm_bias:
            palm_mutes.add(hit)

    return GtrPattern(
        name=pattern.name,
        subdivision=pattern.subdivision,
        hits=pattern.hits,
        accents=pattern.accents,
        palm_mutes=sorted(list(palm_mutes)),
        strum_directions=pattern.strum_directions,
        density=pattern.density,
    )


def apply_microtiming(
    beat_position: float,
    groove_profile: str = "tight",
    push_pull_amount: float = 0.0,
    rng: Optional[random.Random] = None,
) -> float:
    """Apply push/pull microtiming to a beat position.

    Args:
        beat_position: Original beat position
        groove_profile: Groove style ("tight", "laid_back", "pushed", "loose")
        push_pull_amount: Amount of timing adjustment in beats (±0.0-0.1)
        rng: Random generator for loose timing

    Returns:
        float: Adjusted beat position
    """
    if rng is None:
        rng = random.Random()

    if push_pull_amount <= 0.0:
        return beat_position

    # Apply groove-specific timing
    if groove_profile == "tight":
        # No adjustment
        return beat_position

    elif groove_profile == "laid_back":
        # Slight delay (push back)
        return beat_position + (push_pull_amount * 0.5)

    elif groove_profile == "pushed":
        # Slight rush (pull forward)
        return beat_position - (push_pull_amount * 0.5)

    elif groove_profile == "loose":
        # Random variation
        offset = (rng.random() - 0.5) * push_pull_amount * 2.0
        return beat_position + offset

    # Unknown profile: no adjustment
    return beat_position
