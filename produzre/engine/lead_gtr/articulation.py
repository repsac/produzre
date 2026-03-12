"""Simple articulations for lead guitar (Phase LG5).

Adds basic note shaping: sustain (default), staccato (short),
and slide_hint (two quick stepwise notes simulating a slide).

Articulation choices are deterministic via the section RNG and
biased by intensity — higher intensity sections get more staccato
and slide activity for energy.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional


# Articulation weights by intensity band: (sustain, staccato, slide_hint).
_WEIGHTS_LOW  = (0.85, 0.10, 0.05)
_WEIGHTS_MID  = (0.70, 0.20, 0.10)
_WEIGHTS_HIGH = (0.55, 0.30, 0.15)

_LABELS = ("sustain", "staccato", "slide_hint")


@dataclass(frozen=True)
class ArticulatedNote:
    """A note after articulation processing.

    Attributes:
        pitch: Main note MIDI pitch.
        duration: Shaped duration in beats.
        grace_pitch: Optional grace note pitch (slide source, 1 semitone below).
        grace_duration: Grace note duration in beats (0.0 if no grace).
    """

    pitch: int
    duration: float
    grace_pitch: Optional[int] = None
    grace_duration: float = 0.0


def choose_articulation(rng: random.Random, intensity: float) -> str:
    """Pick an articulation weighted by intensity.

    Low intensity favours sustain; high intensity adds staccato and
    slide_hint for more energy and movement.

    Args:
        rng: Seeded RNG for determinism.
        intensity: 0.0–1.0 section intensity.

    Returns:
        One of ``"sustain"``, ``"staccato"``, ``"slide_hint"``.
    """
    if intensity < 0.4:
        weights = _WEIGHTS_LOW
    elif intensity < 0.7:
        weights = _WEIGHTS_MID
    else:
        weights = _WEIGHTS_HIGH

    total = sum(weights)
    roll = rng.random() * total
    cum = 0.0
    for w, label in zip(weights, _LABELS):
        cum += w
        if roll <= cum:
            return label
    return "sustain"


def apply_articulation(
    pitch: int,
    duration: float,
    articulation: str,
    rng: random.Random,
) -> ArticulatedNote:
    """Shape a note according to its articulation type.

    sustain:     No change — note plays at full duration.
    staccato:    Duration reduced to 40–60 % of original.
    slide_hint:  Duration reduced; a short grace note is added one
                 semitone below to simulate a slide-in.

    Args:
        pitch: MIDI pitch of the note.
        duration: Original duration in beats.
        articulation: Articulation type string.
        rng: Seeded RNG for slight per-note variation.

    Returns:
        ArticulatedNote with shaped duration and optional grace note.
    """
    if articulation == "staccato":
        factor = 0.40 + rng.random() * 0.20  # 40–60 %
        return ArticulatedNote(pitch=pitch, duration=duration * factor)

    if articulation == "slide_hint":
        grace_dur = min(0.15, duration * 0.25)
        main_dur = duration - grace_dur  # main note fills the rest
        grace_pitch = pitch - 1          # slide up from one semitone below
        return ArticulatedNote(
            pitch=pitch,
            duration=main_dur,
            grace_pitch=grace_pitch,
            grace_duration=grace_dur,
        )

    # sustain (default): unchanged.
    return ArticulatedNote(pitch=pitch, duration=duration)
