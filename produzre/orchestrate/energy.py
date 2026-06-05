"""Shared energy resolution for section-level dynamics."""

_SECTION_TYPE_ENERGY = {
    "verse": 0.3,
    "intro": 0.3,
    "outro": 0.3,
    "chorus": 0.9,
    "hook": 0.9,
    "bridge": 0.6,
    "prechorus": 0.6,
    "pre-chorus": 0.6,
    "solo": 0.7,
    "breakdown": 0.7,
}

_ENERGY_NAMES = {
    "low": 0.3,
    "mid": 0.6,
    "medium": 0.6,
    "high": 0.9,
}


def resolve_section_energy(energy_raw, section_type: str) -> float:
    """Resolve a section's energy level to a float in [0.0, 1.0].

    ``energy_raw`` may be None (auto-detect from *section_type*), a descriptive
    string ("low"/"mid"/"high"), or a numeric value.
    """
    if energy_raw is None:
        return _SECTION_TYPE_ENERGY.get(section_type.lower(), 0.5)

    if isinstance(energy_raw, str):
        named = _ENERGY_NAMES.get(energy_raw.strip().lower())
        if named is not None:
            return named
        try:
            return max(0.0, min(1.0, float(energy_raw)))
        except (ValueError, TypeError):
            return 0.5

    try:
        return max(0.0, min(1.0, float(energy_raw)))
    except (ValueError, TypeError):
        return 0.5
