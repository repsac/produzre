# produzre/engine/bass/voicing.py
"""Voice leading and register management for bass engine."""

from typing import Optional, Dict


def clamp_to_register(pitch: int, register_low: int, register_high: int) -> int:
    """Clamp a pitch to register bounds using octave folding.

    Args:
        pitch: MIDI note number
        register_low: Lowest allowed MIDI note
        register_high: Highest allowed MIDI note

    Returns:
        MIDI note clamped to [register_low, register_high] via octave shifts
    """
    # Fold down if too high
    while pitch > register_high and pitch - 12 >= register_low:
        pitch -= 12

    # Fold up if too low
    while pitch < register_low and pitch + 12 <= register_high:
        pitch += 12

    # Final clamp
    return max(register_low, min(register_high, pitch))


def select_chord_tone_with_voice_leading(
    chord_tones: Dict[str, int],
    prev_pitch: Optional[int],
    is_downbeat: bool,
    is_cadence: bool,
    approach_rate: float,
    next_root: Optional[int],
    register_low: int,
    register_high: int,
    rng,
    chromatic_rate: float = 0.0,
    mode_offsets: Optional[list[int]] = None,
    key_root: int = 60,
    get_chromatic_approach=None,
    get_diatonic_approach=None,
    motion_style: str = "stepwise",
    root_bias: Optional[float] = None,
) -> tuple[int, str]:
    """Select the best chord tone using voice leading principles.

    Args:
        chord_tones: Dict of available chord tones (root, third, fifth, seventh)
        prev_pitch: Previous bass note (for voice leading)
        is_downbeat: True if this is a downbeat (prefer root)
        is_cadence: True if this is a cadence point (strong root)
        approach_rate: Probability of approach tone (diatonic or chromatic)
        next_root: Next chord's root (for approach tones)
        register_low: Lowest allowed MIDI note
        register_high: Highest allowed MIDI note
        rng: Random number generator
        chromatic_rate: Probability that approach is chromatic (vs diatonic)
        mode_offsets: Scale offsets for diatonic approach (Phase B5)
        key_root: Root MIDI pitch of the key (Phase B5)
        get_chromatic_approach: Function to get chromatic approach (injected to avoid circular import)
        get_diatonic_approach: Function to get diatonic approach (injected to avoid circular import)
        motion_style: Melodic motion preference ("stepwise", "leaping", "mixed") - Phase 4.2
        root_bias: Probability (0.0-1.0) of including the root among inner-beat
            candidates. None keeps the legacy default (~0.65).

    Returns:
        (pitch, kind) - Selected MIDI note and voice label
    """
    root = chord_tones["root"]
    third = chord_tones.get("third")
    fifth = chord_tones["fifth"]
    seventh = chord_tones.get("seventh")

    # Cadences: always use root for strong resolution
    if is_cadence:
        pitch = clamp_to_register(root, register_low, register_high)
        return (pitch, "root_cadence")

    # Downbeats: strongly prefer root
    if is_downbeat:
        # Occasionally use fifth on downbeat for variation (25% — was 15%).
        # Never on the first note of a section (prev_pitch is None): the bass
        # must establish the root before varying away from it. The rng draw is
        # unconditional to keep the stream stable.
        use_fifth = rng.random() < 0.25
        if fifth and use_fifth and prev_pitch is not None:
            pitch = clamp_to_register(fifth, register_low, register_high)
            return (pitch, "fifth")
        else:
            pitch = clamp_to_register(root, register_low, register_high)
            return (pitch, "root")

    # Approach tones: diatonic or chromatic approach to next chord (Phase B5)
    if next_root is not None and approach_rate > 0 and rng.random() < approach_rate:
        # Decide if chromatic or diatonic approach
        use_chromatic = rng.random() < chromatic_rate

        if use_chromatic and get_chromatic_approach:
            # Chromatic approach (half-step)
            approach_pitch = get_chromatic_approach(next_root, from_below=True)
            approach_pitch = clamp_to_register(approach_pitch, register_low, register_high)
            return (approach_pitch, "approach_chromatic")
        elif mode_offsets is not None and get_diatonic_approach:
            # Diatonic approach (scale-based)
            approach_pitch = get_diatonic_approach(
                target_pitch=next_root,
                from_below=True,
                mode_offsets=mode_offsets,
                key_root=key_root,
            )
            approach_pitch = clamp_to_register(approach_pitch, register_low, register_high)
            return (approach_pitch, "approach_diatonic")
        elif get_chromatic_approach:
            # Fallback to chromatic if no mode info
            approach_pitch = get_chromatic_approach(next_root, from_below=True)
            approach_pitch = clamp_to_register(approach_pitch, register_low, register_high)
            return (approach_pitch, "approach")

    # Voice leading: select based on motion_style (Phase 4.2)
    if prev_pitch is not None:
        # On non-downbeat inner beats, reduce root bias so the bass outlines
        # harmony with thirds and fifths rather than camping on the root.
        # Real bassists walk through chord tones on beats 2-4.
        # root_bias param controls the inclusion probability when provided;
        # the legacy default is equivalent to root_bias = 0.65.
        _root_threshold = 0.35 if root_bias is None else (1.0 - float(root_bias))
        include_root = rng.random() > _root_threshold
        candidates = []
        if include_root:
            candidates.append((root, "root"))
        if fifth is not None:
            candidates.append((fifth, "fifth"))
        if third:
            candidates.append((third, "third"))
        if seventh:
            candidates.append((seventh, "seventh"))
        # Safety: ensure at least one candidate always exists
        if not candidates:
            candidates.append((root, "root"))

        # Calculate intervals for all candidates
        candidates_with_intervals = []
        for pitch, kind in candidates:
            if pitch is None:
                continue
            # Clamp to register
            clamped = clamp_to_register(pitch, register_low, register_high)
            interval = abs(clamped - prev_pitch)
            candidates_with_intervals.append((clamped, kind, interval))

        if not candidates_with_intervals:
            # Fallback to root
            pitch = clamp_to_register(root, register_low, register_high)
            return (pitch, "root")

        # Select based on motion style
        if motion_style == "stepwise":
            # Prefer smaller intervals (smooth voice leading)
            candidates_with_intervals.sort(key=lambda x: x[2])  # Sort by interval ascending
            best_pitch, best_kind, _ = candidates_with_intervals[0]
        elif motion_style == "leaping":
            # Prefer larger intervals (angular motion)
            candidates_with_intervals.sort(key=lambda x: x[2], reverse=True)  # Sort by interval descending
            best_pitch, best_kind, _ = candidates_with_intervals[0]
        else:  # "mixed"
            # Random selection weighted by interval diversity
            selected = rng.choice(candidates_with_intervals)
            best_pitch, best_kind, _ = selected

        return (best_pitch, best_kind)

    # Default: root
    pitch = clamp_to_register(root, register_low, register_high)
    return (pitch, "root")
