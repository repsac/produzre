"""Articulation and performance techniques for rhythm guitar (Phase RG4).

This module implements guitar-specific articulations to make MIDI output sound
more realistic and less mechanical:
- Palm muting (reduced sustain + dampened tone)
- Dead notes / "chucks" (percussive muted strums)
- Accent variation based on beat position

All articulations are deterministic given RNG and parameters.
"""

from __future__ import annotations

import random
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class ArticulatedNote:
    """A single note with articulation information.

    Attributes:
        pitch: MIDI note number
        velocity: MIDI velocity (1-127)
        duration: Note duration in beats
        is_palm_mute: Whether this note is palm muted
        is_dead_note: Whether this is a percussive dead note
        is_accent: Whether this note should be accented
    """
    pitch: int
    velocity: int
    duration: float
    is_palm_mute: bool = False
    is_dead_note: bool = False
    is_accent: bool = False


def apply_palm_mute(
    velocity: int,
    duration: float,
    palm_mute_amount: float = 0.7,
) -> Tuple[int, float]:
    """Apply palm mute articulation to a note.

    Palm muting dampens the strings, resulting in:
    - Reduced velocity (darker, less resonant tone)
    - Shortened duration (strings don't ring out)

    Args:
        velocity: Original MIDI velocity
        duration: Original note duration in beats
        palm_mute_amount: Intensity of palm muting (0.0-1.0)

    Returns:
        Tuple[int, float]: (modified_velocity, modified_duration)
    """
    palm_mute_amount = max(0.0, min(1.0, palm_mute_amount))

    # Reduce velocity by palm mute amount
    # Full palm mute (1.0) → 60% of original velocity
    # No palm mute (0.0) → 100% of original velocity
    velocity_factor = 1.0 - (palm_mute_amount * 0.4)
    new_velocity = int(velocity * velocity_factor)
    new_velocity = max(1, min(127, new_velocity))

    # Shorten duration significantly for palm muted notes
    # Full palm mute → 25% of original duration (staccato)
    # No palm mute → 100% of original duration
    duration_factor = 1.0 - (palm_mute_amount * 0.75)
    new_duration = duration * duration_factor
    new_duration = max(0.05, new_duration)  # At least 1/20th beat

    return (new_velocity, new_duration)


def create_dead_note(
    pitch: int,
    base_velocity: int = 60,
    rng: Optional[random.Random] = None,
) -> ArticulatedNote:
    """Create a percussive dead note ("chuck").

    Dead notes are muted strums that produce a percussive, clicking sound
    rather than a pitched tone. They're common in funk, reggae, and ska.

    Args:
        pitch: Base pitch to mute (usually a chord tone)
        base_velocity: Base velocity for the dead note
        rng: Random number generator for variation

    Returns:
        ArticulatedNote: A dead note with very short duration and low velocity
    """
    if rng is None:
        rng = random.Random()

    # Dead notes have low velocity with some variation
    velocity = base_velocity + rng.randint(-10, 10)
    velocity = max(20, min(80, velocity))  # Keep it percussive but quiet

    # Very short duration (just a click)
    duration = 0.05 + rng.random() * 0.05  # 0.05-0.10 beats

    return ArticulatedNote(
        pitch=pitch,
        velocity=velocity,
        duration=duration,
        is_palm_mute=True,  # Dead notes are always muted
        is_dead_note=True,
        is_accent=False,
    )


def should_add_chuck(
    beat_position: float,
    beats_per_bar: float,
    chuck_rate: float,
    rng: random.Random,
) -> bool:
    """Determine if a dead note chuck should be added at this position.

    Chucks are typically added on off-beats to create rhythmic texture.

    Args:
        beat_position: Beat position within the bar
        beats_per_bar: Number of beats per bar
        chuck_rate: Probability of adding a chuck (0.0-1.0)
        rng: Random number generator

    Returns:
        bool: True if a chuck should be added
    """
    if chuck_rate <= 0.0:
        return False

    # Normalize beat position within bar
    beat_in_bar = beat_position % beats_per_bar

    # Chucks more likely on off-beats (between beats)
    is_offbeat = abs(beat_in_bar - round(beat_in_bar)) > 0.2

    # Apply chuck rate with bias toward off-beats
    prob = chuck_rate
    if is_offbeat:
        prob *= 1.5  # 50% more likely on off-beats

    return rng.random() < prob


def apply_beat_position_velocity(
    velocity: int,
    beat_position: float,
    beats_per_bar: float,
    downbeat_boost: float = 0.2,
) -> int:
    """Apply velocity variation based on beat position.

    Guitarists naturally play downbeats stronger than upbeats.

    Args:
        velocity: Base velocity
        beat_position: Position within the bar
        beats_per_bar: Beats per bar
        downbeat_boost: Amount to boost downbeats (0.0-1.0)

    Returns:
        int: Modified velocity
    """
    beat_in_bar = beat_position % beats_per_bar

    # Determine if this is a strong beat
    # Beat 1 is strongest, beat 3 is secondary strong (in 4/4)
    distance_to_downbeat = beat_in_bar % 1.0
    is_on_beat = distance_to_downbeat < 0.1 or distance_to_downbeat > 0.9

    if is_on_beat:
        # On the beat: boost velocity
        if abs(beat_in_bar) < 0.1:
            # Beat 1: strongest
            boost = downbeat_boost
        elif abs(beat_in_bar - int(beats_per_bar / 2)) < 0.1:
            # Beat 3 (in 4/4): secondary strong
            boost = downbeat_boost * 0.6
        else:
            # Other beats: slight boost
            boost = downbeat_boost * 0.3

        new_velocity = int(velocity * (1.0 + boost))
    else:
        # Off-beat: slight reduction
        new_velocity = int(velocity * (1.0 - downbeat_boost * 0.2))

    return max(1, min(127, new_velocity))


def create_chord_articulation(
    pitches: List[int],
    base_velocity: int,
    base_duration: float,
    beat_position: float,
    beats_per_bar: float,
    is_palm_mute: bool,
    is_accent: bool,
    palm_mute_amount: float = 0.7,
    accent_strength: float = 0.5,
    downbeat_boost: float = 0.2,
    chuck_rate: float = 0.0,
    rng: Optional[random.Random] = None,
) -> List[ArticulatedNote]:
    """Create articulated notes for a chord strum.

    Args:
        pitches: MIDI note numbers in the chord
        base_velocity: Base velocity before articulation
        base_duration: Base note duration
        beat_position: Position within the bar
        beats_per_bar: Beats per bar
        is_palm_mute: Whether this chord is palm muted
        is_accent: Whether this is an accented hit
        palm_mute_amount: Intensity of palm muting (0.0-1.0)
        accent_strength: Intensity of accents (0.0-1.0)
        downbeat_boost: Downbeat velocity boost (0.0-1.0)
        chuck_rate: Probability of dead note instead of chord (0.0-1.0)
        rng: Random number generator

    Returns:
        List[ArticulatedNote]: Articulated notes for the chord
    """
    if rng is None:
        rng = random.Random()

    notes = []

    # Check if this should be a chuck instead of a regular chord
    if should_add_chuck(beat_position, beats_per_bar, chuck_rate, rng):
        # Replace chord with a dead note on the root pitch
        root_pitch = pitches[0] if pitches else 60
        chuck = create_dead_note(root_pitch, base_velocity, rng)
        return [chuck]

    # Apply beat position velocity variation
    velocity = apply_beat_position_velocity(
        base_velocity,
        beat_position,
        beats_per_bar,
        downbeat_boost,
    )

    # Apply accent if needed
    if is_accent:
        accent_mult = 1.0 + (accent_strength * 0.4)
        velocity = int(velocity * accent_mult)
        velocity = max(1, min(127, velocity))

    # Apply palm mute if needed
    duration = base_duration
    if is_palm_mute:
        velocity, duration = apply_palm_mute(velocity, duration, palm_mute_amount)

    # Create articulated notes for each pitch in the chord
    for pitch in pitches:
        # Add slight velocity variation per string for realism
        note_velocity = velocity + rng.randint(-5, 5)
        note_velocity = max(1, min(127, note_velocity))

        notes.append(ArticulatedNote(
            pitch=pitch,
            velocity=note_velocity,
            duration=duration,
            is_palm_mute=is_palm_mute,
            is_dead_note=False,
            is_accent=is_accent,
        ))

    return notes


def apply_strum_spread(
    notes: List[ArticulatedNote],
    strum_ms: float,
    strum_direction: str = "down",
    humanize_amount: float = 0.0,
    rng: Optional[random.Random] = None,
) -> List[Tuple[ArticulatedNote, float]]:
    """Apply strum spread timing to notes in a chord.

    Real guitarists don't hit all strings simultaneously - there's a slight
    spread as the pick moves across the strings.

    Args:
        notes: List of articulated notes in the chord
        strum_ms: Spread time in milliseconds
        strum_direction: "down" (low to high) or "up" (high to low)
        humanize_amount: Amount of random variation (0.0-1.0) - Phase RG6
        rng: Random number generator

    Returns:
        List[Tuple[ArticulatedNote, float]]: (note, timing_offset_beats)
    """
    if rng is None:
        rng = random.Random()

    if strum_ms <= 0 or len(notes) <= 1:
        # No spread or single note
        return [(note, 0.0) for note in notes]

    # Convert ms to beats (assuming 120 BPM as reference)
    # At 120 BPM, 1 beat = 500ms
    spread_beats = strum_ms / 500.0

    # Sort notes by pitch (for strum direction)
    sorted_notes = sorted(notes, key=lambda n: n.pitch)

    if strum_direction == "up":
        sorted_notes = list(reversed(sorted_notes))

    # Apply spread timing and velocity taper
    result = []
    num_notes = len(sorted_notes)
    for i, note in enumerate(sorted_notes):
        # Linear spread across the chord
        if num_notes > 1:
            offset = (i / (num_notes - 1)) * spread_beats
        else:
            offset = 0.0

        # Per-string velocity taper: first string hit gets +10, last gets -5.
        # On a downstroke the bass string leads (pick has full momentum);
        # on an upstroke the treble string leads with the same physics.
        if num_notes > 1:
            taper = int(10 - (i / (num_notes - 1)) * 15)  # +10 → -5
        else:
            taper = 0

        # Build a copy of the note with tapered velocity
        tapered_velocity = max(1, min(127, note.velocity + taper))
        tapered_note = ArticulatedNote(
            pitch=note.pitch,
            velocity=tapered_velocity,
            duration=note.duration,
            is_palm_mute=note.is_palm_mute,
            is_dead_note=note.is_dead_note,
            is_accent=note.is_accent,
        )

        # Phase RG6: Only add random variation if humanization is enabled
        if humanize_amount > 0.0:
            # Add small random variation scaled by humanize_amount
            max_variation = 0.005 * humanize_amount  # Up to ±5ms at full humanization
            offset += rng.uniform(-max_variation, max_variation)

        result.append((tapered_note, offset))

    return result
