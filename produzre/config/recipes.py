"""Groove recipe loading, validation, and resolution for all instruments.

Recipes are genre-aware parameter presets stored as individual YAML files.
They can be auto-selected based on song.genre + section metadata, or explicitly
chosen by name. Each recipe provides a thin layer between personas (global play
style) and section-specific overrides.

Merge chain: persona < recipe < global_params < section_params

Loading pattern mirrors the persona system in load.py:
  - Built-in: produzre/resources/recipes/<instrument>/*.yaml
  - User override: <config_dir>/recipes/<instrument>/*.yaml
  - User recipes with same id fully replace built-in ones
"""

from __future__ import annotations

import importlib.resources
import logging
import pathlib
import sys
from typing import Any, Dict, Optional

import yaml

from .errors import ConfigError
from .paths import default_produzre_config_dir

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_recipe(data: Dict[str, Any], *, context: str) -> Dict[str, Any]:
    """Validate and normalize a single recipe mapping.

    Required: id (str), instrument (str).
    Optional: tags (dict), groove (dict), params (dict), voices (dict),
    progressions (dict).
    """
    recipe_id = data.get("id")
    if not recipe_id or not isinstance(recipe_id, str):
        raise ConfigError(f"{context}: recipe 'id' (string) is required")

    instrument = data.get("instrument")
    if not instrument or not isinstance(instrument, str):
        raise ConfigError(f"{context}: recipe 'instrument' (string) is required")

    tags = data.get("tags", {})
    if not isinstance(tags, dict):
        tags = {}

    groove = data.get("groove", {})
    if not isinstance(groove, dict):
        groove = {}

    params = data.get("params", {})
    if not isinstance(params, dict):
        params = {}

    voices = data.get("voices", {})
    if not isinstance(voices, dict):
        voices = {}

    progressions = data.get("progressions", {})
    if not isinstance(progressions, dict):
        progressions = {}

    return {
        "id": str(recipe_id),
        "instrument": str(instrument),
        "tags": tags,
        "groove": groove,
        "params": params,
        "voices": voices,
        "progressions": progressions,
    }


# ---------------------------------------------------------------------------
# Loading (mirrors _load_builtin_personas_yaml / _load_user_personas_yaml)
# ---------------------------------------------------------------------------

def _load_yaml_file(path: pathlib.Path, *, context: str) -> Optional[Dict[str, Any]]:
    """Load and parse a YAML file, returning None on failure."""
    try:
        text = path.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        if isinstance(data, dict):
            return data
    except Exception as e:
        logger.warning("Failed to load recipe %s: %s", context, e)
    return None


def _load_builtin_recipes_for_instrument(instrument: str) -> Dict[str, Dict[str, Any]]:
    """Load all built-in recipe YAML files for an instrument.

    Scans: produzre/resources/recipes/<instrument>/*.yaml
    Returns: { recipe_id: validated_recipe_dict }
    """
    recipes: Dict[str, Dict[str, Any]] = {}

    # Try importlib.resources first (installed package).
    try:
        base = importlib.resources.files("produzre")
        recipe_dir = base.joinpath("resources", "recipes", instrument)
        for item in recipe_dir.iterdir():
            if item.name.endswith((".yaml", ".yml")) and item.is_file():
                text = item.read_text(encoding="utf-8")
                data = yaml.safe_load(text)
                if isinstance(data, dict):
                    ctx = f"built-in recipe '{instrument}/{item.name}'"
                    validated = _validate_recipe(data, context=ctx)
                    recipes[validated["id"]] = validated
    except Exception:
        pass

    # Fallback for source checkouts / editable installs.
    if not recipes:
        try:
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                pkg_root = pathlib.Path(meipass) / "produzre"
            else:
                pkg_root = pathlib.Path(__file__).resolve().parents[1]
            recipe_dir_path = pkg_root / "resources" / "recipes" / instrument
            if recipe_dir_path.is_dir():
                for yaml_path in sorted(recipe_dir_path.glob("*.yaml")):
                    data = _load_yaml_file(yaml_path, context=yaml_path.name)
                    if data:
                        validated = _validate_recipe(
                            data, context=f"built-in recipe '{instrument}/{yaml_path.name}'"
                        )
                        recipes[validated["id"]] = validated
                for yaml_path in sorted(recipe_dir_path.glob("*.yml")):
                    data = _load_yaml_file(yaml_path, context=yaml_path.name)
                    if data:
                        validated = _validate_recipe(
                            data, context=f"built-in recipe '{instrument}/{yaml_path.name}'"
                        )
                        recipes[validated["id"]] = validated
        except Exception:
            pass

    return recipes


def _load_user_recipes_for_instrument(instrument: str) -> Dict[str, Dict[str, Any]]:
    """Load user-override recipe YAML files for an instrument.

    Scans: <config_dir>/recipes/<instrument>/*.yaml
    Returns: { recipe_id: validated_recipe_dict }
    """
    recipes: Dict[str, Dict[str, Any]] = {}
    user_dir = default_produzre_config_dir() / "recipes" / instrument

    if not user_dir.is_dir():
        return recipes

    for pattern in ("*.yaml", "*.yml"):
        for yaml_path in sorted(user_dir.glob(pattern)):
            try:
                data = _load_yaml_file(yaml_path, context=yaml_path.name)
                if data:
                    validated = _validate_recipe(
                        data, context=f"user recipe '{instrument}/{yaml_path.name}'"
                    )
                    recipes[validated["id"]] = validated
            except ConfigError:
                logger.warning("Skipping invalid user recipe: %s", yaml_path)

    return recipes


def load_recipes_for_instrument(instrument: str) -> Dict[str, Dict[str, Any]]:
    """Load and merge built-in + user recipes for an instrument.

    User recipes with the same id fully replace built-in ones.
    Returns: { recipe_id: validated_recipe_dict }
    """
    builtin = _load_builtin_recipes_for_instrument(instrument)
    user = _load_user_recipes_for_instrument(instrument)
    merged = {**builtin, **user}

    if merged:
        logger.debug(
            "Loaded %d recipes for '%s' (%d built-in, %d user)",
            len(merged), instrument, len(builtin), len(user),
        )

    return merged


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def resolve_recipe_name(
    *,
    instrument: str,
    genre: Optional[str],
    section_type: str,
    intensity: float,
    bpm: float,
    time_signature: str,
    instrument_recipe: Optional[str],
    section_recipe: Optional[str],
    recipes: Dict[str, Dict[str, Any]],
) -> Optional[str]:
    """Resolve which recipe to use for a given section+instrument.

    Resolution order:
        1. Explicit recipe on section instrument config
        2. Explicit recipe on global instrument config
        3. Auto-select from genre + section_type + bpm (best scored match)
        4. No match -> None (engine uses existing defaults)

    Returns: recipe id string or None.
    """
    if not recipes:
        return None

    # 1. Section-level explicit recipe.
    if section_recipe:
        rid = str(section_recipe).strip()
        if rid in recipes:
            return rid
        logger.warning(
            "Unknown recipe '%s' for %s. Known: %s",
            rid, instrument, ", ".join(sorted(recipes.keys())),
        )
        return None

    # 2. Global instrument-level explicit recipe.
    if instrument_recipe:
        rid = str(instrument_recipe).strip()
        if rid in recipes:
            return rid
        logger.warning(
            "Unknown recipe '%s' for %s. Known: %s",
            rid, instrument, ", ".join(sorted(recipes.keys())),
        )
        return None

    # 3. Auto-select from genre (only if genre is specified).
    if genre is None:
        return None

    return _auto_select_recipe(
        genre=genre,
        section_type=section_type,
        intensity=intensity,
        bpm=bpm,
        time_signature=time_signature,
        recipes=recipes,
    )


def _auto_select_recipe(
    *,
    genre: str,
    section_type: str,
    intensity: float,
    bpm: float,
    time_signature: str,
    recipes: Dict[str, Dict[str, Any]],
) -> Optional[str]:
    """Score and select the best-matching recipe for the given context.

    Scoring:
        - genre match: +10 (exact) / +5 (substring)
        - section_type in recipe's section_types: +4
        - bpm within recipe's bpm_range: +3
        - time_signature match: +2
    Must match genre at minimum (score > 0 requires genre match).
    """
    genre_lower = genre.strip().lower()
    section_lower = section_type.strip().lower()

    best_id: Optional[str] = None
    best_score: float = 0.0

    for recipe_id, recipe in recipes.items():
        tags = recipe.get("tags", {})
        score = 0.0

        # Genre match (required for any score).
        recipe_genre = str(tags.get("genre", "")).strip().lower()
        if recipe_genre == genre_lower:
            score += 10.0
        elif genre_lower in recipe_genre or recipe_genre in genre_lower:
            score += 5.0

        if score == 0.0:
            continue

        # Section type match.
        section_types = tags.get("section_types", [])
        if isinstance(section_types, list):
            if section_lower in [s.strip().lower() for s in section_types]:
                score += 4.0

        # BPM range match.
        bpm_range = tags.get("bpm_range")
        if isinstance(bpm_range, (list, tuple)) and len(bpm_range) >= 2:
            try:
                if float(bpm_range[0]) <= bpm <= float(bpm_range[1]):
                    score += 3.0
            except (ValueError, TypeError):
                pass

        # Time signature match.
        recipe_ts = str(tags.get("time_signature", "")).strip()
        if recipe_ts == time_signature:
            score += 2.0

        if score > best_score or (score == best_score and (best_id is None or recipe_id < best_id)):
            best_score = score
            best_id = recipe_id

    return best_id
