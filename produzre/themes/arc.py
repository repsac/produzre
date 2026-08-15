"""Arrangement arc: which transform each theme gets per section (prototype).

This is the minimal M2 slice of design doc §9: a default table mapping
section type -> transform, plus repeat-statement escalation. A full ``arc.py``
with config overrides and persona modulation is milestone M4.
"""

from __future__ import annotations

from typing import Dict, Tuple

from .model import Theme, ThemeRole

# section type -> (transform, params) applied to every theme
DEFAULT_ARC: Dict[str, Tuple[str, dict]] = {
    "intro": ("fragment", {"keep": "first"}),
    "verse": ("quote", {}),
    "prechorus": ("displace", {"shift_beats": 0.5}),
    "pre-chorus": ("displace", {"shift_beats": 0.5}),
    "chorus": ("quote", {}),
    "hook": ("quote", {}),
    "bridge": ("invert", {}),
    "solo": ("sequence", {"steps": 2}),
    "breakdown": ("thin", {}),
    "outro": ("fragment", {"keep": "last"}),
}

# Repeat statements (2nd+ occurrence of a section type) escalate per role.
REPEAT_ARC: Dict[str, Dict[ThemeRole, Tuple[str, dict]]] = {
    "chorus": {ThemeRole.MELODY: ("octave_shift", {"octaves": 1})},
    "hook": {ThemeRole.MELODY: ("octave_shift", {"octaves": 1})},
}


def treatment_for(
    theme: Theme,
    section_type: str,
    occurrence: int = 0,
) -> Tuple[str, dict]:
    """Resolve the (transform, params) for a theme in one section occurrence.

    Args:
        theme: The theme being placed. User-authored themes marked ``locked``
            (``allow_development: false``) always quote — user material is
            intent, not clay.
        section_type: Section type label ("verse", "chorus", ...).
        occurrence: 0-based count of prior sections of the same type.

    Returns:
        (transform_name, params) suitable for transform.apply_transform.
    """
    if "locked" in theme.tags:
        return ("quote", {})

    sec = str(section_type or "").strip().lower()
    if occurrence > 0:
        repeat = REPEAT_ARC.get(sec, {}).get(theme.role)
        if repeat is not None:
            name, params = repeat
            return name, dict(params)
    name, params = DEFAULT_ARC.get(sec, ("quote", {}))
    return name, dict(params)
