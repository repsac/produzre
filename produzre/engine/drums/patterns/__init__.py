"""Template interpreter for the Produzre drums engine.

This module turns a :class:`~produzre.engine.drums.groove.GrooveTemplate` into a
sequence of per-note events for a section.

Design goals:
- Pure logic (no MIDI writing, no timeline mutation, no I/O)
- Deterministic variability via an explicit `random.Random` passed in
- Meter-aware via beats_per_bar + an internal step grid

The drums engine is responsible for:
- Choosing the groove_id
- Creating a deterministic RNG for the section
- Humanizing start times and velocities
- Placing the returned events into the Timeline

---

Package Structure
~~~~~~~~~~~~~~~~~

This package contains the drum pattern generation implementation, split into
focused modules for maintainability:

Foundation Layer:
- `grid.py`: Step grid calculations and beat-to-step conversions
- `utils.py`: Shared utilities (velocity, clamping, proximity checks)

Voice Modules:
- `kick.py`: Kick drum event generation (base, extra, double-kick)
- `snare.py`: Snare drum event generation (backbeat, ghosts)
- `cymbals.py`: Crash cymbal placement
- `hats.py`: Hi-hat and ride cymbal with open-hat intent
- `toms.py`: Tom drum event generation (groove toms and fill runs)

Orchestration:
- `kit.py`: Main orchestration layer and public API (DrumEvent, events_for_section_from_template)

Public API:
- `DrumEvent`: Dataclass representing a single drum note event
- `events_for_section_from_template()`: Main function to generate drum events from a groove template
"""

from __future__ import annotations

from .kit import DrumEvent, events_for_section_from_template

__all__ = ["DrumEvent", "events_for_section_from_template"]
