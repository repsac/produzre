"""Rhythm-section coupling helpers (M3, design doc §4.4).

Engines read the realized theme notes published by the render prepass
(``themes.realized.<section_id>``) and use them to make the band play the
same song: bass locks placement to riff attacks, drums accent/double them,
rhythm guitar punches accents that coincide with them.

All beat positions are section-relative. Every consumer must keep RNG draws
independent of onset proximity (draw per onset/note unconditionally) so
streams stay stable.
"""

from __future__ import annotations

from bisect import bisect_left
from typing import List, Optional


def get_theme_onsets(plan, section_id: str, role: str = "riff") -> List[float]:
    """Return sorted section-relative onset beats for a realized theme role.

    Args:
        plan: PerformancePlan (or None). Missing plan/themes -> empty list.
        section_id: Section whose realized notes to read.
        role: Theme role key ("riff", "melody", "bass_motif").

    Returns:
        Sorted list of onset beats (empty when no themes are active).
    """
    if plan is None or not hasattr(plan, "get"):
        return []
    data = plan.get(f"themes.realized.{section_id}")
    if not isinstance(data, dict):
        return []
    notes = data.get(role) or []
    return sorted(float(n["beat"]) for n in notes if isinstance(n, dict) and "beat" in n)


def nearest_onset(onsets: List[float], beat: float, window: float) -> Optional[float]:
    """Return the onset nearest to ``beat`` if within ``window`` beats.

    Args:
        onsets: Sorted onset beats (from get_theme_onsets).
        beat: Query position, section-relative.
        window: Maximum distance in beats.

    Returns:
        The nearest onset beat, or None if none within the window.
    """
    if not onsets:
        return None
    i = bisect_left(onsets, beat)
    best: Optional[float] = None
    best_dist = window
    for j in (i - 1, i):
        if 0 <= j < len(onsets):
            d = abs(onsets[j] - beat)
            if d <= best_dist:
                best, best_dist = onsets[j], d
    return best
