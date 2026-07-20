from __future__ import annotations

"""Deterministic section-level role planning for the core band."""

from typing import Any


_ROLE_PROFILES: dict[str, dict[str, tuple[str, float]]] = {
    "intro": {
        "drums": ("establish", 0.65),
        "bass": ("anchor", 0.65),
        "rhythm_gtr": ("texture", 0.68),
        "lead_gtr": ("pickup", 0.35),
    },
    "verse": {
        "drums": ("pocket", 0.82),
        "bass": ("anchor", 0.82),
        "rhythm_gtr": ("comp", 0.78),
        "lead_gtr": ("answer", 0.48),
    },
    "prechorus": {
        "drums": ("build", 0.90),
        "bass": ("push", 0.92),
        "rhythm_gtr": ("build", 0.86),
        "lead_gtr": ("pickup", 0.58),
    },
    "chorus": {
        "drums": ("drive", 1.0),
        "bass": ("drive", 0.96),
        "rhythm_gtr": ("hook", 0.92),
        "lead_gtr": ("counterhook", 0.68),
    },
    "bridge": {
        "drums": ("contrast", 0.72),
        "bass": ("counterline", 0.76),
        "rhythm_gtr": ("space", 0.62),
        "lead_gtr": ("statement", 0.72),
    },
    "solo": {
        "drums": ("support", 0.90),
        "bass": ("anchor", 0.78),
        "rhythm_gtr": ("support", 0.56),
        "lead_gtr": ("solo", 1.0),
    },
    "breakdown": {
        "drums": ("space", 0.50),
        "bass": ("pedal", 0.62),
        "rhythm_gtr": ("punctuate", 0.55),
        "lead_gtr": ("silence", 0.18),
    },
    "outro": {
        "drums": ("resolve", 0.68),
        "bass": ("resolve", 0.72),
        "rhythm_gtr": ("resolve", 0.72),
        "lead_gtr": ("answer", 0.45),
    },
}


def _lead_windows(section_type: str, total_beats: float, beats_per_bar: float) -> list[tuple[float, float]]:
    """Return phrase-sized windows where lead guitar owns foreground space."""
    if total_beats <= 0.0:
        return []

    st = section_type.lower()
    phrase = max(beats_per_bar, beats_per_bar * 4.0)
    windows: list[tuple[float, float]] = []

    for start in _frange(0.0, total_beats, phrase):
        end = min(total_beats, start + phrase)
        if st in ("solo", "lead"):
            active_start, active_end = start, end
        elif st in ("chorus", "hook"):
            active_start = start
            active_end = min(end, start + beats_per_bar * 3.0)
        elif st == "bridge":
            active_start = start
            active_end = min(end, start + beats_per_bar * 2.0)
        elif st in ("intro", "prechorus", "pre-chorus"):
            active_start = min(end, start + beats_per_bar * 2.0)
            active_end = end
        elif st == "breakdown":
            active_start = max(start, end - beats_per_bar)
            active_end = end
        else:
            active_start = min(end, start + beats_per_bar)
            active_end = min(end, start + beats_per_bar * 3.0)
        if active_end - active_start > 1e-6:
            windows.append((active_start, active_end))
    return windows


def _frange(start: float, stop: float, step: float):
    value = start
    while value < stop - 1e-9:
        yield value
        value += step


def build_ensemble_section_plan(
    cfg: Any,
    section: Any,
    rhythm_grid: Any,
    transition_context: dict | None = None,
) -> dict[str, Any]:
    """Build role and space assignments before any instrument renders."""
    section_type = str(getattr(section, "type", "verse") or "verse").lower()
    section_type = "prechorus" if section_type == "pre-chorus" else section_type
    profile = _ROLE_PROFILES.get(section_type, _ROLE_PROFILES["verse"])
    instruments = set(getattr(section, "instruments", {}) or {})
    beats_per_bar = float(getattr(rhythm_grid, "beats_per_bar", 4.0) or 4.0)
    total_beats = float(getattr(rhythm_grid, "total_beats", beats_per_bar * 4.0) or beats_per_bar * 4.0)

    roles = {
        name: {"role": role, "density_multiplier": density}
        for name, (role, density) in profile.items()
        if name in instruments
    }
    lead_windows = _lead_windows(section_type, total_beats, beats_per_bar) if "lead_gtr" in instruments else []
    active_beats = sum(end - start for start, end in lead_windows)
    lead_rest_ratio = 1.0 - min(1.0, active_beats / max(total_beats, 1e-6))

    # Drums own transitions by default. Bass only gets the final pickup when
    # drums are absent; this prevents independent fill lotteries at boundaries.
    fill_owner = "drums" if "drums" in instruments else ("bass" if "bass" in instruments else None)
    return {
        "section_type": section_type,
        "genre": str(getattr(getattr(cfg, "song", None), "genre", "") or "").lower(),
        "roles": roles,
        "lead_activity_windows": lead_windows,
        "lead_rest_ratio": round(lead_rest_ratio, 4),
        "fill_owner": fill_owner,
        "transition": dict(transition_context or {}),
    }
