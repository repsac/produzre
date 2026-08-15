"""Core theme data model (prototype).

A Theme is a short musical idea stored as **rhythm + scale degrees**, never
absolute pitches. Degrees are key-relative (1 = tonic); accidentals are
semitone offsets applied after the diatonic step (b3 = degree 3, acc -1).
This keeps themes transposable across the harmony plan while preserving
melodic identity across chord changes.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class ThemeRole(str, Enum):
    """Musical role a theme plays; engines consume themes by role."""

    RIFF = "riff"
    MELODY = "melody"
    BASS_MOTIF = "bass_motif"
    DRUM_GROOVE = "drum_groove"  # reserved (M3); not yet realized


# Default MIDI registers per role when the config does not specify one.
DEFAULT_REGISTERS: Dict[ThemeRole, Tuple[int, int]] = {
    ThemeRole.RIFF: (40, 55),        # low-mid guitar range
    ThemeRole.MELODY: (64, 79),      # vocal-ish lead range
    ThemeRole.BASS_MOTIF: (28, 48),  # bass register
    ThemeRole.DRUM_GROOVE: (36, 60),  # unused placeholder
}


@dataclass(frozen=True)
class ThemeEvent:
    """One event within a theme.

    Attributes:
        offset_beats: Position within the theme, from 0.0.
        duration_beats: Event length in quarter-note beats.
        degree: Diatonic scale degree, 1-based (1 = tonic). ``None`` = rest.
        accidental: Semitone offset after the diatonic step (-1 flat, +1 sharp).
        octave: Octave displacement from the theme's base register.
        accent: Whether this event is emphasized.
    """

    offset_beats: float
    duration_beats: float
    degree: Optional[int]
    accidental: int = 0
    octave: int = 0
    accent: bool = False

    @property
    def is_rest(self) -> bool:
        return self.degree is None

    def degree_label(self) -> str:
        if self.degree is None:
            return "."
        acc = "b" * -self.accidental if self.accidental < 0 else "#" * self.accidental
        oct_ = "+" * self.octave if self.octave > 0 else "-" * -self.octave
        return f"{acc}{self.degree}{oct_}"


@dataclass(frozen=True)
class Theme:
    """A named, reusable musical idea.

    Attributes:
        name: Identifier ("main_riff", "chorus_hook", ...).
        role: ThemeRole; determines which engines quote it and in what register.
        length_beats: Theme length; occurrences loop on this boundary.
        events: Ordered events (rests included for rhythm fidelity).
        base_register: Preferred (low, high) MIDI range for realization.
        tags: Provenance markers ("user", "generated", "imported").
    """

    name: str
    role: ThemeRole
    length_beats: float
    events: Tuple[ThemeEvent, ...]
    base_register: Tuple[int, int] = (60, 72)
    tags: frozenset = frozenset()

    def pitch_events(self) -> Tuple[ThemeEvent, ...]:
        """Events excluding rests, in order."""
        return tuple(e for e in self.events if not e.is_rest)

    def rhythm_signature(self) -> Tuple[Tuple[float, float], ...]:
        """(offset, duration) pairs for all events, rests included.

        The rhythm is the theme's identity: a distinctive rhythm with plain
        pitches is a hook; the reverse is noodling.
        """
        return tuple((e.offset_beats, e.duration_beats) for e in self.events)

    def serialize(self) -> str:
        """Stable string form used for determinism checks and hashing."""
        rows = [
            f"{e.offset_beats:g},{e.duration_beats:g},{e.degree},"
            f"{e.accidental},{e.octave},{int(e.accent)}"
            for e in self.events
        ]
        return f"{self.name}|{self.role.value}|{self.length_beats:g}|" + ";".join(rows)


@dataclass
class ThemeBank:
    """The song-level collection of themes, built once per song."""

    themes: Dict[str, Theme] = field(default_factory=dict)
    seed_material_hash: str = ""

    def by_role(self, role: ThemeRole) -> List[Theme]:
        return [t for t in self.themes.values() if t.role is role]

    def get(self, name: str) -> Optional[Theme]:
        return self.themes.get(name)

    def finalize(self) -> "ThemeBank":
        """Compute the provenance hash after all themes are added."""
        payload = "|".join(self.themes[k].serialize() for k in sorted(self.themes))
        self.seed_material_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
        return self
