"""Type definitions for lead guitar engine (Phase LG0).

Data structures for lead guitar phrase planning and note events.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class LeadNoteEvent:
    """Single note event for lead guitar.

    Attributes:
        pitch: MIDI note number
        start_beat: Start position in beats (section-relative)
        duration_beats: Note duration in beats
        velocity: MIDI velocity (1-127)
        articulation: Note articulation ("normal", "bend", "slide", "vibrato", etc.)
    """
    pitch: int
    start_beat: float
    duration_beats: float
    velocity: int
    articulation: str = "normal"


@dataclass
class PhrasePlan:
    """Plan for a melodic phrase.

    Attributes:
        notes: List of note events in the phrase
        tag: Phrase identifier (e.g., "motif_A", "variation_1", "rest")
        start_beat: Phrase start position (section-relative)
        end_beat: Phrase end position (section-relative)
    """
    notes: List[LeadNoteEvent]
    tag: str
    start_beat: float
    end_beat: float


@dataclass
class Motif:
    """Melodic motif definition.

    A motif is a short, memorable melodic pattern that can be repeated
    and varied throughout a section or song.

    Attributes:
        intervals: List of interval steps from root (in semitones)
                  e.g., [0, 2, 4, 5] for root, 2nd, 3rd, 4th
        rhythm_pattern: List of note durations in beats
                       e.g., [0.5, 0.5, 1.0] for two eighths and a quarter
        name: Motif identifier
        density: Target density (0.0-1.0) indicating how many beats are filled
    """
    intervals: List[int]
    rhythm_pattern: List[float]
    name: str
    density: float = 0.5
