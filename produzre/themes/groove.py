"""Drum groove themes: map theme degrees to kit voices (design doc §4.5).

A ``drum_groove`` theme is rhythm + *voice* instead of rhythm + pitch. Degrees
select the drum voice; the event rhythm is the groove itself:

    1 = kick    2 = snare    3 = closed hat    4 = open hat
    5 = crash   6 = ride     7 = tom

Kick, snare, and hat/ride onsets replace the recipe's kit steps (see the
``groove_strength`` crossfade in the drums engine). Open-hat onsets join the
hat line and force the hit open; crash and tom onsets are injected as extra
hits alongside the recipe's structural crashes and fills. Arc transforms
(thin, displace, fragment, ...) apply to groove themes exactly as to pitched
themes, so a breakdown can thin the kit and a prechorus can re-groove it,
deterministically.

Like every theme realization this is a pure function: no RNG, no I/O.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .model import Theme
from .transform import apply_transform

# Degree -> drum voice for drum_groove themes.
VOICE_BY_DEGREE = {
    1: "kick",
    2: "snare",
    3: "hat",
    4: "open_hat",
    5: "crash",
    6: "ride",
    7: "tom",
}


def realize_groove(
    theme: Theme,
    transform_name: Optional[str] = "quote",
    transform_params: Optional[dict] = None,
    total_beats: float = 0.0,
) -> Dict[str, List[float]]:
    """Realize a drum_groove theme as per-voice onset beats (section-relative).

    The (possibly arc-transformed) theme loops to cover ``total_beats``.

    Returns:
        {"kick": [...], "snare": [...], "hat": [...], "open_hat": [...],
         "crash": [...], "ride": [...], "tom": [...]} with sorted beat lists.
        A non-empty "ride" list signals the drums engine to move the
        top-cymbal line to the ride cymbal.
    """
    if transform_name:
        theme = apply_transform(theme, transform_name, **(transform_params or {}))
    out: Dict[str, List[float]] = {
        "kick": [], "snare": [], "hat": [], "open_hat": [],
        "crash": [], "ride": [], "tom": [],
    }
    if total_beats <= 0:
        return out
    base = 0.0
    while base < total_beats - 1e-9:
        for e in theme.events:
            if e.is_rest:
                continue
            voice = VOICE_BY_DEGREE.get(e.degree)
            if voice is None:
                continue
            onset = base + e.offset_beats
            if onset < total_beats - 1e-9:
                out[voice].append(round(onset, 6))
        base += theme.length_beats
    return out
