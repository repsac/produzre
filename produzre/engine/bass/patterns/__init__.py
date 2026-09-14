# produzre/engine/bass/patterns/__init__.py
"""Bass rhythm pattern generators and filters.

This package provides rhythm pattern generation and filtering for the bass engine.
"""

from .utils import create_subdivision_slots
from .generators import (
    get_rhythm_pattern_anchor,
    get_rhythm_pattern_push,
    get_rhythm_pattern_drive,
    get_rhythm_pattern_syncopated,
    get_rhythm_pattern_rock_riff,
    get_rhythm_pattern_funk_16ths,
)
from .filters import (
    apply_density_filter,
    apply_rest_filter,
    apply_drum_locking,
    apply_motif_repetition,
)

__all__ = [
    # Utils
    "create_subdivision_slots",
    # Generators
    "get_rhythm_pattern_anchor",
    "get_rhythm_pattern_push",
    "get_rhythm_pattern_drive",
    "get_rhythm_pattern_syncopated",
    "get_rhythm_pattern_rock_riff",
    "get_rhythm_pattern_funk_16ths",
    # Filters
    "apply_density_filter",
    "apply_rest_filter",
    "apply_drum_locking",
    "apply_motif_repetition",
]
