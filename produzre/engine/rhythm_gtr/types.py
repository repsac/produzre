"""Type definitions for rhythm guitar engine (Phase RG0).

This module defines internal data structures used exclusively by the rhythm_gtr
engine package. These types are not part of the public API and may change
between versions.
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class StrumEvent:
    """Represents a single strum event with timing and voicing information.

    Attributes:
        start_beat: Section-relative beat position
        duration_beats: Note duration in beats
        pitches: List of MIDI note numbers for the chord voicing
        velocity: MIDI velocity (0-127)
        direction: Strum direction ("down", "up", "none")
        is_palm_mute: Whether palm muting should be applied
        is_accent: Whether this is an accented strum
        spread_ms: Milliseconds to spread between notes (0 = block chord)
    """
    start_beat: float
    duration_beats: float
    pitches: List[int]
    velocity: int
    direction: str = "down"  # "down", "up", "none"
    is_palm_mute: bool = False
    is_accent: bool = False
    spread_ms: float = 0.0


@dataclass
class ChordShape:
    """Guitar chord voicing with finger positions.

    Attributes:
        root_midi: MIDI note number of the chord root
        pitches: List of MIDI note numbers in the voicing (ordered low to high)
        numeral: Roman numeral representation (e.g., "I", "V", "vi")
        is_major: True for major chords, False for minor
        inversion: Inversion number (0=root, 1=first, 2=second)
        voicing_name: Optional name for the voicing (e.g., "power", "barre", "open")
    """
    root_midi: int
    pitches: List[int]
    numeral: str
    is_major: bool
    inversion: int = 0
    voicing_name: Optional[str] = None
    resolved: Optional[Any] = None  # Optional ResolvedVoicing from instruments library


@dataclass
class GtrPattern:
    """Rhythm pattern template for guitar strumming.

    Attributes:
        name: Pattern identifier (e.g., "verse_basic", "chorus_driving")
        subdivision: Subdivisions per beat (e.g., 4 for 16th notes)
        hits: List of subdivision indices that should be strummed
        accents: List of subdivision indices that should be accented
        palm_mutes: List of subdivision indices for palm mute strokes
        strum_directions: Optional list of directions per hit ("down", "up")
        density: Pattern density (0.0-1.0, for filtering)
    """
    name: str
    subdivision: int
    hits: List[int]
    accents: List[int] = field(default_factory=list)
    palm_mutes: List[int] = field(default_factory=list)
    strum_directions: Optional[List[str]] = None
    density: float = 0.5


@dataclass
class BarPlan:
    """Plan for rendering a single bar of rhythm guitar.

    Attributes:
        bar_index: Bar number within the section (0-indexed)
        chord_shape: Chord voicing for this bar
        pattern: Rhythm pattern to apply
        intensity: Intensity level for this bar (0.0-1.0)
        fills_allowed: Whether fills/variations are allowed in this bar
        is_transition: Whether this bar is a transition to next section
    """
    bar_index: int
    chord_shape: ChordShape
    pattern: GtrPattern
    intensity: float = 0.5
    fills_allowed: bool = True
    is_transition: bool = False
