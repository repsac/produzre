"""Step grid calculations and beat-to-step conversions.

This module provides core step grid calculations used across all voice modules.
Grid logic is pure math, used by all voice modules to avoid circular dependencies.

Re-exports from groove.py:
- step_beats: Calculate beat-length of one step
- steps_per_bar_default: Returns canonical 16-step groove resolution
"""

from __future__ import annotations

import math

# Re-export groove helpers for convenience
from ..groove import step_beats, steps_per_bar_default

__all__ = ["bars_total", "step_beats", "steps_per_bar_default"]


def bars_total(total_beats: float, beats_per_bar: float) -> int:
    """Return the number of bars needed to cover total_beats.

    Parameters
    ----------
    total_beats : float
        Total duration in beats to cover.
    beats_per_bar : float
        Meter beats per bar (e.g., 4.0 for 4/4).

    Returns
    -------
    int
        Number of complete bars needed (rounded up).

    Examples
    --------
    >>> bars_total(16.0, 4.0)
    4
    >>> bars_total(17.0, 4.0)
    5
    """
    bpb = float(beats_per_bar)
    if bpb <= 0.0:
        return 0
    return int(math.ceil(float(total_beats) / bpb))
