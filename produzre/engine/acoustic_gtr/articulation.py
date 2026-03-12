"""Articulation and duration shaping for acoustic guitar.

Handles the physical differences between thumb (bass) and finger (treble)
strokes, natural string decay, strum spread timing, and body percussion.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from .defaults import (
    BODY_TAP_PITCH,
    BODY_TAP_VEL_LO,
    BODY_TAP_VEL_HI,
    BODY_TAP_DURATION,
)

if TYPE_CHECKING:
    from ...timeline import InstrumentTimeline


# =============================================================================
# Finger attack — velocity shaping by stroke type
# =============================================================================

def apply_finger_attack(
    base_vel: int,
    is_bass: bool,
    is_downbeat: bool,
    vel_variation: int,
    rng: random.Random,
) -> int:
    """Compute final note velocity for a single fingerpicking hit.

    Bass (thumb/P stroke): warmer, slightly louder — the foundation.
    Treble (I/M/A finger stroke): lighter, airier — the melody layer.

    Args:
        base_vel:      Base velocity from params.
        is_bass:       True = thumb, False = finger.
        is_downbeat:   True when this hit falls on beat 1 of the bar.
        vel_variation: ±random range for humanization.
        rng:           Seeded RNG.

    Returns:
        Clamped MIDI velocity (1-127).
    """
    # Bass strings are plucked harder by the thumb naturally
    v = base_vel + (6 if is_bass else -4)

    # Downbeat emphasis — the guitarist naturally accents beat 1
    if is_downbeat:
        v += 5 if is_bass else 3

    # Humanization: slight per-hit variation
    if vel_variation > 0:
        v += rng.randint(-vel_variation, vel_variation)

    return max(20, min(127, v))


# =============================================================================
# Duration calculation — string-aware sustain
# =============================================================================

def calc_pick_duration(
    hit_beat: float,
    next_hit_beat: float,
    chord_end_beat: float,
    is_bass: bool,
) -> float:
    """Compute note duration for a single fingerpicked string.

    Bass strings sustain longer (90% of gap) because they have more mass
    and decay slowly. Treble strings decay faster (60% of gap).

    The gap to the NEXT hit on the same string (not the next hit overall)
    determines how long the note should ring. The chord boundary is always
    an absolute cap.

    Args:
        hit_beat:       Current hit's beat position (section-local).
        next_hit_beat:  When the same string is next plucked (or chord_end).
        chord_end_beat: Hard boundary — note cannot ring past this.
        is_bass:        True = bass string (longer sustain).

    Returns:
        Duration in beats (always > 0.0).
    """
    gap = max(0.0, next_hit_beat - hit_beat)
    gate = 0.90 if is_bass else 0.60
    duration = gap * gate

    # Hard floor and chord boundary
    duration = max(0.08, min(duration, max(0.0, chord_end_beat - hit_beat)))
    return duration


# =============================================================================
# Body percussion / tap
# =============================================================================

def emit_body_tap(
    beat: float,
    section_start_beat: float,
    base_vel: int,
    rng: random.Random,
    timeline: "InstrumentTimeline",
) -> None:
    """Add a percussive dead-note body tap to the timeline.

    Simulates the guitarist slapping the guitar body for rhythmic texture.
    Uses a fixed dead-note pitch (E2 = MIDI 40) at low velocity.

    Args:
        beat:               Section-local beat position for the tap.
        section_start_beat: Absolute song beat offset for this section.
        base_vel:           Instrument base velocity (tap is always softer).
        rng:                Seeded RNG for velocity variation.
        timeline:           Timeline to add note to.
    """
    vel = rng.randint(BODY_TAP_VEL_LO, BODY_TAP_VEL_HI)
    # Scale down if overall instrument is very quiet
    vel = min(vel, max(30, int(base_vel * 0.75)))

    timeline.add_note(
        start_beat=section_start_beat + beat,
        duration_beats=BODY_TAP_DURATION,
        pitch=BODY_TAP_PITCH,
        velocity=vel,
        channel=None,
        kind="body_tap",
    )


# =============================================================================
# Strum spread — micro-stagger for chord hits
# =============================================================================

def strum_spread_offsets(
    n_pitches: int,
    direction: str,          # "down" | "up"
    spread_beats: float,     # Total time across all strings (e.g. 0.03)
) -> list[float]:
    """Return per-pitch time offset for a strummed chord.

    Down strum: lowest pitch first (ascending).
    Up strum:   highest pitch first (descending).

    Args:
        n_pitches:    Number of strings in the chord.
        direction:    "down" or "up".
        spread_beats: Total elapsed time across the whole strum.

    Returns:
        List of beat offsets, one per pitch, in the order notes are added.
    """
    if n_pitches <= 1 or spread_beats <= 0.0:
        return [0.0] * n_pitches

    step = spread_beats / max(1, n_pitches - 1)
    offsets = [i * step for i in range(n_pitches)]

    if direction == "up":
        offsets = list(reversed(offsets))

    return offsets
