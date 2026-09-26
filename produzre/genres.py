"""Canonical aliases at the configuration boundary, shared by every engine."""

_COUNTRY_ALIASES = {
    "honky": "honky_tonk_country", "honky_tonk": "honky_tonk_country",
    "bakersfield": "bakersfield_country", "outlaw": "outlaw_country",
    "western": "honky_tonk_country", "two_step": "two_step_country",
    "texas": "texas_country", "dance_hall": "dance_hall_country",
}


def normalize_genre(genre):
    if genre is None:
        return None
    key = str(genre).strip().lower().replace("-", "_").replace(" ", "_")
    return _COUNTRY_ALIASES.get(key, genre)
