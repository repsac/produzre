from __future__ import annotations

"""Root configuration loader.

This module is the primary entry point for turning a YAML configuration file
into a fully validated `RootConfig` object ready for orchestration.

Responsibilities:
- Read and validate the YAML document shape.
- Parse `song` and `sections` into strongly typed model objects.
- Validate arrangement references.
- Resolve the per-user project seed and compute the effective seed used for
  deterministic generation.
- Build the runtime engine registry from defaults + project overrides.
- Populate `RuntimeContext` so downstream code can report/serialize provenance.

Notes on seeds:
- The authored song YAML contains a `song.seed` value.
- The user selects a project by name (or defaults to the user’s default project).
- The effective seed used for generation is derived from:
    effective_seed = compute_effective_seed(project_seed, song_seed)
- For backward compatibility, this loader overwrites `song.seed` with the
  effective seed while preserving the original `song_seed` in `RuntimeContext`.

All filesystem interactions use `pathlib` to remain OS-agnostic.
"""

import pathlib
import importlib.resources
import logging
import sys
from typing import Any, Dict, Optional

import yaml

# YAML schema versioning
CURRENT_SCHEMA_VERSION = 1
SUPPORTED_SCHEMA_VERSIONS = {CURRENT_SCHEMA_VERSION}

logger = logging.getLogger(__name__)

from .errors import ConfigError
from .yaml_io import read_yaml_file
from .parse import parse_song, parse_section
from .registry import (
    load_projects_registry,
    save_projects_registry,
    ensure_default_project,
    resolve_project_seed,
)
from .seeding import compute_effective_seed
from .paths import projects_registry_path
from .engines import build_engine_registry
from ..model import RootConfig, RuntimeContext


def _load_yaml(path: pathlib.Path) -> Dict[str, Any]:
    """Load a YAML file from disk and require a top-level mapping.

    This helper centralizes YAML I/O and validation for configuration files.

    Behavior:
      - Raises a ConfigError if the file does not exist.
      - Uses the shared YAML reader (`read_yaml_file`) so parsing behavior is
        consistent across the codebase.
      - Ensures the parsed YAML is a dict (YAML mapping / JSON object).

    Args:
        path: Filesystem path to the YAML file.

    Raises:
        ConfigError: If the file is missing, unreadable, invalid YAML, or the
            top-level parsed value is not a mapping.

    Returns:
        Dict[str, Any]: Parsed YAML mapping.
    """
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    try:
        data = read_yaml_file(path)
    except yaml.YAMLError as e:
        raise ConfigError(f"Failed to parse YAML: {e}") from e
    except OSError as e:
        raise ConfigError(f"Failed to read YAML file: {path}: {e}") from e

    if not isinstance(data, dict):
        raise ConfigError("Top-level YAML must be a mapping/object.")
    return data


# --- Helper functions for personas registry and YAML merging ---

def _deep_merge_dict(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge mapping b into mapping a and return a new dict.

    Rules:
    - Dict values are merged recursively.
    - Non-dict values are replaced by b.
    - Lists are replaced (not concatenated).

    This is used for merging built-in and user-provided persona registries.
    """
    out: Dict[str, Any] = dict(a)
    for k, vb in b.items():
        va = out.get(k)
        if isinstance(va, dict) and isinstance(vb, dict):
            out[k] = _deep_merge_dict(va, vb)
        else:
            out[k] = vb
    return out


def _load_yaml_mapping_from_text(text: str, *, context: str) -> Dict[str, Any]:
    """Parse YAML text and require a top-level mapping."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ConfigError(f"Failed to parse YAML for {context}: {e}") from e
    if not isinstance(data, dict):
        raise ConfigError(f"Top-level YAML for {context} must be a mapping/object.")
    return data


def _package_root() -> pathlib.Path:
    """Return the root ``produzre/`` package directory.

    Works in three environments:
    1. PyInstaller frozen bundle (``sys._MEIPASS``)
    2. Installed wheel/sdist (``importlib.resources``)
    3. Source checkout / editable install (``__file__`` relative)
    """
    # PyInstaller sets sys._MEIPASS to the temp extraction directory.
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return pathlib.Path(meipass) / "produzre"
    return pathlib.Path(__file__).resolve().parents[1]  # .../produzre/


def _load_builtin_personas_yaml(rel_path: str) -> Optional[Dict[str, Any]]:
    """Load a built-in personas YAML shipped inside the Produzre package.

    Returns None if the resource does not exist (allows incremental rollout).

    We try `importlib.resources` first (installed package), then fall back to a
    filesystem path for source checkouts / editable installs / frozen bundles.
    """
    # First try package resources (works for installed wheels/sdists).
    try:
        base = importlib.resources.files("produzre")
        res = base.joinpath(rel_path)
        if res.is_file():
            text = res.read_text(encoding="utf-8")
            return _load_yaml_mapping_from_text(text, context=f"built-in personas '{rel_path}'")
    except Exception:
        pass

    # Fallback: filesystem path (source checkouts, editable installs, frozen bundles).
    try:
        fs_path = _package_root() / rel_path
        if fs_path.is_file():
            text = fs_path.read_text(encoding="utf-8")
            return _load_yaml_mapping_from_text(text, context=f"built-in personas '{rel_path}'")
    except Exception:
        pass

    return None


def _load_user_personas_yaml(path: pathlib.Path) -> Optional[Dict[str, Any]]:
    """Load a user personas YAML from disk.

    Returns None if missing.
    """
    if not path.exists():
        return None
    return _load_yaml(path)



def _normalize_personas_registry(data: Dict[str, Any], *, context: str) -> Dict[str, Any]:
    """Validate and normalize a personas registry mapping.

    Expected shape:
        version: int (optional)
        default: str (optional)
        personas: { <name>: { params: {..}, voices: {..} } }

    The function returns a dict with keys: version, default, personas.
    """
    version = data.get("version", 1)
    try:
        version = int(version)
    except Exception as e:
        raise ConfigError(f"{context}: 'version' must be an integer") from e

    # Prefer the more explicit key name, but accept legacy `default` for compatibility.
    default_persona = data.get("default_persona", data.get("default"))
    if default_persona is not None and not isinstance(default_persona, str):
        raise ConfigError(f"{context}: 'default_persona' must be a string")

    personas = data.get("personas", {})
    if personas is None:
        personas = {}
    if not isinstance(personas, dict):
        raise ConfigError(f"{context}: 'personas' must be a mapping")

    norm_personas: Dict[str, Any] = {}
    for name, p in personas.items():
        if not isinstance(name, str):
            raise ConfigError(f"{context}: persona names must be strings")
        if not isinstance(p, dict):
            raise ConfigError(f"{context}: persona '{name}' must be a mapping")
        params = p.get("params", {})
        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise ConfigError(f"{context}: persona '{name}.params' must be a mapping")

        # Also preserve voices (voice-level defaults for this persona)
        voices = p.get("voices", {})
        if voices is None:
            voices = {}
        if not isinstance(voices, dict):
            raise ConfigError(f"{context}: persona '{name}.voices' must be a mapping")

        norm_personas[name] = {"params": params, "voices": voices}

    # Keep both keys for compatibility; `default_persona` is the canonical name.
    return {
        "version": version,
        "default_persona": default_persona,
        "default": default_persona,
        "personas": norm_personas,
    }


# --- Drum voice concept block validation ---

def _as_float_01(value: Any, *, context: str) -> float:
    """Parse a value as float and validate it is within [0.0, 1.0]."""
    try:
        f = float(value)
    except Exception as e:
        raise ConfigError(f"{context}: expected a number in [0.0, 1.0]; got {value!r}") from e
    if f < 0.0 or f > 1.0:
        raise ConfigError(f"{context}: expected a number in [0.0, 1.0]; got {f}")
    return f



def _as_int(value: Any, *, context: str) -> int:
    """Parse a value as int."""
    try:
        return int(value)
    except Exception as e:
        raise ConfigError(f"{context}: expected an integer; got {value!r}") from e


# --- Drum voice concept normalization helpers ---

def _normalize_token_list(value: Any, *, context: str) -> Optional[list[str]]:
    """Normalize a musician-friendly token list.

    Accepts:
      - None -> None
      - A single token string (e.g., "2&")
      - A list of token strings (e.g., ["2&", "4&"])
      - A comma-separated string (e.g., "2&, 4&")

    Returns:
        A list of string tokens, or None if the input is None.

    Raises:
        ConfigError: If the input cannot be interpreted as token(s).
    """
    if value is None:
        return None
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return []
        # Allow comma-separated convenience.
        parts = [p.strip() for p in s.split(",")]
        parts = [p for p in parts if p]
        return parts
    if isinstance(value, list):
        if not all(isinstance(x, str) for x in value):
            raise ConfigError(f"{context}: expected a list of strings")
        return [x.strip() for x in value]
    raise ConfigError(f"{context}: expected a token string or list of strings")


def _normalize_drum_voice_concepts(voices: Dict[str, Any], *, context: str) -> Dict[str, Any]:
    """Normalize the musician-friendly `voices.*` concept-block schema for drums.

    This performs the same validation as `_validate_drum_voice_concepts`, but also:
      - normalizes `placements` into a list of tokens (accepting a scalar string or
        comma-separated string)
      - coerces numeric types where safe

    The normalized mapping is returned so callers can store a canonical shape.
    """
    _validate_drum_voice_concepts(voices, context=context)

    out: Dict[str, Any] = {}
    for voice_name, voice_cfg in voices.items():
        if not isinstance(voice_name, str) or not isinstance(voice_cfg, dict):
            # Should be impossible due to validation, but keep defensive.
            continue
        v_out: Dict[str, Any] = {}

        if voice_name == "kick":
            for block in ("syncopation", "double"):
                if block not in voice_cfg:
                    continue
                b = voice_cfg.get(block)
                if not isinstance(b, dict):
                    continue
                b_out = dict(b)
                if "rate" in b_out:
                    b_out["rate"] = _as_float_01(b_out.get("rate"), context=f"{context}: voices.kick.{block}.rate")
                if "placements" in b_out:
                    b_out["placements"] = _normalize_token_list(
                        b_out.get("placements"),
                        context=f"{context}: voices.kick.{block}.placements",
                    )
                v_out[block] = b_out

        if voice_name == "snare":
            if "ghosts" in voice_cfg and isinstance(voice_cfg.get("ghosts"), dict):
                g = dict(voice_cfg["ghosts"])
                if "rate" in g:
                    g["rate"] = _as_float_01(g.get("rate"), context=f"{context}: voices.snare.ghosts.rate")
                if "placements" in g:
                    g["placements"] = _normalize_token_list(
                        g.get("placements"),
                        context=f"{context}: voices.snare.ghosts.placements",
                    )
                if "velocity_bias" in g:
                    g["velocity_bias"] = _as_int(g.get("velocity_bias"), context=f"{context}: voices.snare.ghosts.velocity_bias")
                v_out["ghosts"] = g

            if "articulation" in voice_cfg and isinstance(voice_cfg.get("articulation"), dict):
                art = dict(voice_cfg["articulation"])
                if "default" in art:
                    art["default"] = str(art.get("default")).strip().lower()
                v_out["articulation"] = art

        if voice_name == "hats":
            for block in ("pattern", "open", "opens", "pedal", "accents"):
                if block not in voice_cfg:
                    continue
                b = voice_cfg.get(block)
                if not isinstance(b, dict):
                    continue
                b_out = dict(b)
                if "rate" in b_out:
                    b_out["rate"] = _as_float_01(b_out.get("rate"), context=f"{context}: voices.hats.{block}.rate")
                if "placements" in b_out:
                    b_out["placements"] = _normalize_token_list(
                        b_out.get("placements"),
                        context=f"{context}: voices.hats.{block}.placements",
                    )
                if block == "accents":
                    if "boost" in b_out:
                        b_out["boost"] = _as_int(b_out.get("boost"), context=f"{context}: voices.hats.accents.boost")
                    if "bias" in b_out:
                        b_out["bias"] = _as_int(b_out.get("bias"), context=f"{context}: voices.hats.accents.bias")
                v_out[block] = b_out

            velocity = voice_cfg.get("velocity")
            if isinstance(velocity, dict):
                v_vel = dict(velocity)
                if "bias" in v_vel:
                    v_vel["bias"] = _as_int(v_vel.get("bias"), context=f"{context}: voices.hats.velocity.bias")
                v_out["velocity"] = v_vel

        if voice_name == "toms":
            for block in ("groove", "fills"):
                if block not in voice_cfg:
                    continue
                b = voice_cfg.get(block)
                if not isinstance(b, dict):
                    continue
                b_out = dict(b)
                if "rate" in b_out:
                    b_out["rate"] = _as_float_01(b_out.get("rate"), context=f"{context}: voices.toms.{block}.rate")
                v_out[block] = b_out

        if voice_name == "crash":
            if "rate" in voice_cfg:
                v_out["rate"] = _as_float_01(voice_cfg.get("rate"), context=f"{context}: voices.crash.rate")
            if "placements" in voice_cfg:
                placements = voice_cfg.get("placements")
                if isinstance(placements, (list, tuple)):
                    v_out["placements"] = _normalize_token_list(
                        placements,
                        context=f"{context}: voices.crash.placements",
                    )

        if voice_name == "ride":
            if "bell_rate" in voice_cfg:
                v_out["bell_rate"] = _as_float_01(voice_cfg.get("bell_rate"), context=f"{context}: voices.ride.bell_rate")

        if voice_name == "cymbals":
            if "splash_rate" in voice_cfg:
                v_out["splash_rate"] = _as_float_01(voice_cfg.get("splash_rate"), context=f"{context}: voices.cymbals.splash_rate")
            if "china_rate" in voice_cfg:
                v_out["china_rate"] = _as_float_01(voice_cfg.get("china_rate"), context=f"{context}: voices.cymbals.china_rate")
            if "ride_bell_rate" in voice_cfg:
                v_out["ride_bell_rate"] = _as_float_01(voice_cfg.get("ride_bell_rate"), context=f"{context}: voices.cymbals.ride_bell_rate")

        # Preserve any other validated keys as-is (future extensions).
        for k, v in voice_cfg.items():
            if k in v_out:
                continue
            if k == "params":
                continue
            v_out[k] = v

        out[voice_name] = v_out

    return out


def _validate_drum_voice_concepts(voices: Dict[str, Any], *, context: str) -> None:
    """Validate the musician-friendly `voices.*` concept-block schema for drums.

    We intentionally do NOT support legacy `voices.<voice>.params` in early development.

    Supported (currently validated) shapes:
      - voices.kick.syncopation: { rate?: float[0..1], placements?: [token, ...] }
      - voices.kick.double: { rate?: float[0..1], placements?: [token, ...] }
      - voices.snare.ghosts: { rate?: float[0..1], placements?: [token, ...], velocity_bias?: int }
      - voices.snare.articulation: { default?: "normal" | "rimshot" | "crossstick" }
      - voices.hats.pattern: { rate?: float[0..1], placements?: [token, ...] }
      - voices.hats.open:    { rate?: float[0..1], placements?: [token, ...] }
      - voices.hats.opens:   { rate?: float[0..1], placements?: [token, ...] }  (alias for open)
      - voices.hats.pedal:   { rate?: float[0..1], placements?: [token, ...] }
      - voices.hats.accents: { rate?: float[0..1], boost?: int, bias?: int, placements?: [token, ...] }
      - voices.hats.velocity: { bias?: int }
      - voices.toms.groove: { rate?: float[0..1] }
      - voices.toms.fills: { rate?: float[0..1] }
      - voices.crash: { rate?: float[0..1], placements?: [token, ...] }
      - voices.ride: { bell_rate?: float[0..1] }
      - voices.cymbals: { splash_rate?: float[0..1], china_rate?: float[0..1], ride_bell_rate?: float[0..1] }

    Tokens are the same style used elsewhere (e.g., "2&", "4e"); we only validate they are strings.
    """
    if not isinstance(voices, dict):
        raise ConfigError(f"{context}: 'voices' must be a mapping")

    for voice_name, voice_cfg in voices.items():
        if not isinstance(voice_name, str):
            raise ConfigError(f"{context}: voice names must be strings")
        if not isinstance(voice_cfg, dict):
            raise ConfigError(f"{context}: voices.{voice_name} must be a mapping")

        # Strict: disallow the old `params` bucket under voices.
        if "params" in voice_cfg:
            raise ConfigError(
                f"{context}: legacy key 'voices.{voice_name}.params' is not supported. "
                f"Use concept blocks like voices.{voice_name}.ghosts / voices.{voice_name}.accents / opens / pedal instead."
            )

        # Kick
        if voice_name == "kick":
            for block in ("syncopation", "double"):
                if block not in voice_cfg:
                    continue
                b = voice_cfg.get(block)
                if not isinstance(b, dict):
                    raise ConfigError(f"{context}: voices.kick.{block} must be a mapping")
                if "rate" in b:
                    _as_float_01(b.get("rate"), context=f"{context}: voices.kick.{block}.rate")
                if "placements" in b:
                    placements = b.get("placements")
                    if isinstance(placements, str):
                        pass  # normalized later
                    elif not isinstance(placements, list) or not all(isinstance(x, str) for x in placements):
                        raise ConfigError(
                            f"{context}: voices.kick.{block}.placements must be a string token or a list of strings"
                        )

        # Snare
        if voice_name == "snare":
            if "ghosts" in voice_cfg:
                ghosts = voice_cfg.get("ghosts")
                if not isinstance(ghosts, dict):
                    raise ConfigError(f"{context}: voices.snare.ghosts must be a mapping")
                if "rate" in ghosts:
                    _as_float_01(ghosts.get("rate"), context=f"{context}: voices.snare.ghosts.rate")
                if "placements" in ghosts:
                    placements = ghosts.get("placements")
                    if isinstance(placements, str):
                        # Allow scalar token or comma-separated tokens; normalized later.
                        pass
                    elif not isinstance(placements, list) or not all(isinstance(x, str) for x in placements):
                        raise ConfigError(
                            f"{context}: voices.snare.ghosts.placements must be a string token (e.g., '2&') or a list of strings"
                        )
                if "velocity_bias" in ghosts:
                    _as_int(ghosts.get("velocity_bias"), context=f"{context}: voices.snare.ghosts.velocity_bias")

            if "articulation" in voice_cfg:
                articulation = voice_cfg.get("articulation")
                if not isinstance(articulation, dict):
                    raise ConfigError(f"{context}: voices.snare.articulation must be a mapping")
                if "default" in articulation:
                    default = articulation.get("default")
                    if not isinstance(default, str):
                        raise ConfigError(f"{context}: voices.snare.articulation.default must be a string")
                    if str(default).strip().lower() not in ("normal", "rimshot", "crossstick"):
                        raise ConfigError(
                            f"{context}: voices.snare.articulation.default must be one of: normal, rimshot, crossstick"
                        )

        # Hats
        if voice_name == "hats":
            for block in ("pattern", "open", "opens", "pedal", "accents"):
                if block not in voice_cfg:
                    continue
                b = voice_cfg.get(block)
                if not isinstance(b, dict):
                    raise ConfigError(f"{context}: voices.hats.{block} must be a mapping")
                if "rate" in b:
                    _as_float_01(b.get("rate"), context=f"{context}: voices.hats.{block}.rate")
                if "placements" in b:
                    placements = b.get("placements")
                    if isinstance(placements, str):
                        # Allow scalar token or comma-separated tokens; normalized later.
                        pass
                    elif not isinstance(placements, list) or not all(isinstance(x, str) for x in placements):
                        raise ConfigError(
                            f"{context}: voices.hats.{block}.placements must be a string token or a list of strings"
                        )

            accents = voice_cfg.get("accents")
            if isinstance(accents, dict):
                if "boost" in accents:
                    _as_int(accents.get("boost"), context=f"{context}: voices.hats.accents.boost")
                if "bias" in accents:
                    _as_int(accents.get("bias"), context=f"{context}: voices.hats.accents.bias")

            velocity = voice_cfg.get("velocity")
            if isinstance(velocity, dict):
                if "bias" in velocity:
                    _as_int(velocity.get("bias"), context=f"{context}: voices.hats.velocity.bias")

        # Toms
        if voice_name == "toms":
            for block in ("groove", "fills"):
                if block not in voice_cfg:
                    continue
                b = voice_cfg.get(block)
                if not isinstance(b, dict):
                    raise ConfigError(f"{context}: voices.toms.{block} must be a mapping")
                if "rate" in b:
                    _as_float_01(b.get("rate"), context=f"{context}: voices.toms.{block}.rate")

        # Crash
        if voice_name == "crash":
            if "rate" in voice_cfg:
                _as_float_01(voice_cfg.get("rate"), context=f"{context}: voices.crash.rate")
            if "placements" in voice_cfg:
                placements = voice_cfg.get("placements")
                if not isinstance(placements, (list, tuple)):
                    raise ConfigError(f"{context}: voices.crash.placements must be a list")
                for p in placements:
                    if not isinstance(p, (str, int, float)):
                        raise ConfigError(f"{context}: voices.crash.placements must contain strings or numbers")

        # Ride
        if voice_name == "ride":
            if "bell_rate" in voice_cfg:
                _as_float_01(voice_cfg.get("bell_rate"), context=f"{context}: voices.ride.bell_rate")

        # Cymbals (splash, china)
        if voice_name == "cymbals":
            if "splash_rate" in voice_cfg:
                _as_float_01(voice_cfg.get("splash_rate"), context=f"{context}: voices.cymbals.splash_rate")
            if "china_rate" in voice_cfg:
                _as_float_01(voice_cfg.get("china_rate"), context=f"{context}: voices.cymbals.china_rate")
            if "ride_bell_rate" in voice_cfg:
                _as_float_01(voice_cfg.get("ride_bell_rate"), context=f"{context}: voices.cymbals.ride_bell_rate")


def _load_personas_registry_for_instrument(instrument: str) -> Dict[str, Any]:
    """Load and merge built-in + user personas for an instrument.

    Built-in path:
        produzre/resources/personas/<instrument>.yml

    User override path:
        <user_config_dir>/personas/<instrument>.yml

    The user config dir is derived from the projects registry location.
    """
    built_rel = f"resources/personas/{instrument}.yml"
    built = _load_builtin_personas_yaml(built_rel) or {}
    built_norm = _normalize_personas_registry(built, context=f"built-in personas ({instrument})")

    user_dir = projects_registry_path().parent
    user_path = user_dir / "personas" / f"{instrument}.yml"
    user = _load_user_personas_yaml(user_path) or {}
    user_norm = _normalize_personas_registry(user, context=f"user personas ({instrument})")

    merged = _deep_merge_dict(built_norm, user_norm)

    # If user didn't specify a default, preserve the built-in default
    if merged.get("default_persona") is None and built_norm.get("default_persona") is not None:
        merged["default_persona"] = built_norm["default_persona"]
        merged["default"] = built_norm["default_persona"]

    return merged


def _resolve_persona_name(
    *,
    instrument: Optional[str],
    instrument_cfg: Optional[Dict[str, Any]],
    registry: Dict[str, Any],
    fallback_default: str,
    context: str,
) -> str:
    """Resolve a persona name from config + registry, validating existence."""
    persona = None
    if instrument_cfg and isinstance(instrument_cfg, dict):
        persona = instrument_cfg.get("persona")

    if persona is None:
        persona = registry.get("default_persona") or registry.get("default") or fallback_default

    personas = registry.get("personas", {})
    if not personas:
        if instrument:
            built_rel = f"produzre/resources/personas/{instrument}.yml"
            user_path = projects_registry_path().parent / "personas" / f"{instrument}.yml"
            raise ConfigError(
                f"{context}: no personas loaded for '{instrument}'. "
                f"Create the built-in file '{built_rel}' or a user override at '{user_path}'."
            )
        raise ConfigError(f"{context}: no personas loaded.")

    if persona not in personas:
        known = ", ".join(sorted(personas.keys()))
        raise ConfigError(
            f"{context}: unknown persona '{persona}'. Known personas: {known if known else '(none)'}"
        )

    return persona


def _resolve_simple_persona(
    raw: Dict[str, Any],
    instruments_raw: Any,
    registry: Dict[str, Any],
    instrument: str,
    fallback_default: str,
) -> None:
    """Resolve persona for a simple instrument (flat params, no voice concepts)."""
    inst_cfg = None
    if isinstance(instruments_raw, dict):
        v = instruments_raw.get(instrument)
        if isinstance(v, dict):
            inst_cfg = v

    effective_persona = _resolve_persona_name(
        instrument=instrument,
        instrument_cfg=inst_cfg,
        registry=registry,
        fallback_default=fallback_default,
        context=f"instruments.{instrument}",
    )

    persona_data = ((registry.get("personas", {}) or {}).get(effective_persona, {}) or {})
    persona_params = persona_data.get("params", {})

    inst_params = {}
    if inst_cfg and isinstance(inst_cfg, dict):
        ip = inst_cfg.get("params")
        if isinstance(ip, dict):
            inst_params = ip

    raw["_effective"]["instruments"].setdefault(instrument, {})
    raw["_effective"]["instruments"][instrument]["persona"] = effective_persona
    raw["_effective"]["instruments"][instrument]["params"] = _deep_merge_dict(persona_params, inst_params)


def load_root_config(path: str) -> RootConfig:
    """Load, validate, and parse a Produzre YAML configuration file.

    The resulting `RootConfig` is the canonical in-memory representation used by
    orchestration and engine rendering.

    Validation performed:
      - `version` is optional; if missing we assume the current schema version.
      - `song` exists and is a mapping.
      - `sections` exists, is a non-empty mapping, and each section is a mapping.
      - `arrangement` exists, is a non-empty list, and all references exist in
        the parsed sections.

    Seed / project resolution:
      - Loads the local projects registry.
      - Resolves the project name + project seed from `song.project` (or the
        default project).
      - Ensures the default project exists and persists the registry if needed.
      - Computes an effective generation seed from (project_seed, song_seed).
      - Stores both authored and effective values in `RuntimeContext`.
      - Overwrites `song.seed` with the effective seed for generation.

    Engine registry:
      - Builds the runtime engine registry from defaults plus top-level
        `instruments:` overrides in the YAML.

    Args:
        path: Path to the YAML config file.

    Raises:
        ConfigError: If the file cannot be loaded, parsed, or fails validation.

    Returns:
        RootConfig: Fully parsed configuration including runtime context and
        engine registry.
    """
    p = pathlib.Path(path)
    raw = _load_yaml(p)

    # Phase P1: load built-in + user personas and attach to raw for visibility.
    drums_personas = _load_personas_registry_for_instrument("drums")
    bass_personas = _load_personas_registry_for_instrument("bass")
    rhythm_gtr_personas = _load_personas_registry_for_instrument("rhythm_gtr")
    lead_gtr_personas = _load_personas_registry_for_instrument("lead_gtr")
    acoustic_gtr_personas = _load_personas_registry_for_instrument("acoustic_gtr")
    raw.setdefault("_personas", {})
    raw["_personas"]["drums"] = drums_personas
    raw["_personas"]["bass"] = bass_personas
    raw["_personas"]["rhythm_gtr"] = rhythm_gtr_personas
    raw["_personas"]["lead_gtr"] = lead_gtr_personas
    raw["_personas"]["acoustic_gtr"] = acoustic_gtr_personas

    # Phase R1: load groove recipes for all instruments.
    from .recipes import load_recipes_for_instrument as _load_recipes
    raw.setdefault("_recipes", {})
    raw["_recipes"]["drums"] = _load_recipes("drums")
    raw["_recipes"]["harmony"] = _load_recipes("harmony")
    raw["_recipes"]["rhythm_gtr"] = _load_recipes("rhythm_gtr")
    raw["_recipes"]["bass"] = _load_recipes("bass")

    instruments_raw = raw.get("instruments")

    # === Drums persona resolution ===
    drums_instrument_cfg = None
    if isinstance(instruments_raw, dict):
        v = instruments_raw.get("drums")
        if isinstance(v, dict):
            drums_instrument_cfg = v

    # Default shipped persona is 'tight' if none specified.
    effective_drums_persona = _resolve_persona_name(
        instrument="drums",
        instrument_cfg=drums_instrument_cfg,
        registry=drums_personas,
        fallback_default="tight",
        context="instruments.drums",
    )

    # Merge persona params + voices with instrument-level params + voices.
    # Precedence: persona defaults < instrument defaults < section overrides < voice overrides
    persona_data = ((drums_personas.get("personas", {}) or {}).get(effective_drums_persona, {}) or {})
    persona_params = persona_data.get("params", {})
    persona_voices = persona_data.get("voices", {})

    inst_params = {}
    inst_voices = {}
    if drums_instrument_cfg and isinstance(drums_instrument_cfg, dict):
        ip = drums_instrument_cfg.get("params")
        if isinstance(ip, dict):
            inst_params = ip
        iv = drums_instrument_cfg.get("voices")
        if isinstance(iv, dict):
            inst_voices = iv

    # Normalize persona voices first
    if persona_voices:
        persona_voices = _normalize_drum_voice_concepts(persona_voices, context=f"persona '{effective_drums_persona}'")

    # Normalize instrument voices
    if inst_voices:
        inst_voices = _normalize_drum_voice_concepts(inst_voices, context="instruments.drums")

    raw.setdefault("_effective", {})
    raw["_effective"].setdefault("instruments", {})
    raw["_effective"]["instruments"].setdefault("drums", {})
    raw["_effective"]["instruments"]["drums"]["persona"] = effective_drums_persona
    raw["_effective"]["instruments"]["drums"]["params"] = _deep_merge_dict(persona_params, inst_params)
    # Carry voice defaults forward: persona voices < instrument voices
    # Sections that specify `drums: {}` will inherit these voice-specific params.
    effective_voices = _deep_merge_dict(persona_voices, inst_voices)
    if effective_voices:
        raw["_effective"]["instruments"]["drums"]["voices"] = effective_voices

    # === Bass persona resolution ===
    bass_instrument_cfg = None
    if isinstance(instruments_raw, dict):
        v = instruments_raw.get("bass")
        if isinstance(v, dict):
            bass_instrument_cfg = v

    effective_bass_persona = _resolve_persona_name(
        instrument="bass",
        instrument_cfg=bass_instrument_cfg,
        registry=bass_personas,
        fallback_default="tight",
        context="instruments.bass",
    )

    # Merge persona params with instrument-level params
    # Bass doesn't have voice concepts like drums, just flat params
    bass_persona_data = ((bass_personas.get("personas", {}) or {}).get(effective_bass_persona, {}) or {})
    bass_persona_params = bass_persona_data.get("params", {})

    bass_inst_params = {}
    if bass_instrument_cfg and isinstance(bass_instrument_cfg, dict):
        bp = bass_instrument_cfg.get("params")
        if isinstance(bp, dict):
            bass_inst_params = bp

    raw["_effective"]["instruments"].setdefault("bass", {})
    raw["_effective"]["instruments"]["bass"]["persona"] = effective_bass_persona
    raw["_effective"]["instruments"]["bass"]["params"] = _deep_merge_dict(bass_persona_params, bass_inst_params)

    # === Rhythm guitar persona resolution ===
    _resolve_simple_persona(raw, instruments_raw, rhythm_gtr_personas, "rhythm_gtr", "tight")

    # === Lead guitar persona resolution ===
    _resolve_simple_persona(raw, instruments_raw, lead_gtr_personas, "lead_gtr", "balanced")

    # === Acoustic guitar persona resolution ===
    _resolve_simple_persona(raw, instruments_raw, acoustic_gtr_personas, "acoustic_gtr", "natural")

    raw_version = raw.get("version", None)
    if raw_version is None:
        # Backward-compatible default: assume the current schema.
        version = CURRENT_SCHEMA_VERSION
        #logger.warning(
        #    "YAML is missing top-level 'version'; assuming schema v%d. "
        #    "Consider adding 'version: %d' to the file.",
        #    version,
        #    version,
        #)
    else:
        try:
            version = int(raw_version)
        except Exception as e:
            raise ConfigError(f"Top-level 'version' must be an integer; got {raw_version!r}.") from e

    if version not in SUPPORTED_SCHEMA_VERSIONS:
        supported = ", ".join(str(v) for v in sorted(SUPPORTED_SCHEMA_VERSIONS))
        raise ConfigError(
            "Unsupported YAML schema version: {v}. Supported versions: {supported}. "
            "If this file was created by a newer Produzre, upgrade Produzre; "
            "if it's an older file, run a conversion tool (future: `produzre yaml upgrade`).".format(
                v=version, supported=supported
            )
        )

    song_data = raw.get("song")
    if not isinstance(song_data, dict):
        raise ConfigError("Top-level 'song' mapping is required.")
    song = parse_song(song_data)

    # Phase 1: resolve per-user project seed and compute effective seed.
    reg = load_projects_registry()
    pname, pseed = resolve_project_seed(reg, getattr(song, "project", None))
    # Persist default project creation if needed.
    ensure_default_project(reg)
    save_projects_registry(reg)

    song_seed = int(song.seed)
    effective_seed = compute_effective_seed(pseed, song_seed)

    # Runtime context: keep authored song_seed but use effective_seed for generation.
    runtime = RuntimeContext(
        project_name=pname,
        project_seed=int(pseed),
        song_seed=int(song_seed),
        effective_seed=int(effective_seed),
        projects_registry_path=str(projects_registry_path()),
    )

    # Backward-compatible: drive generation from effective seed without changing song YAML.
    song.seed = int(effective_seed)

    sections_data = raw.get("sections")
    if not isinstance(sections_data, dict) or not sections_data:
        raise ConfigError("Top-level 'sections' mapping is required and cannot be empty.")

    # Normalize musician-friendly drum voice concept blocks at the section level so
    # downstream code and `show-config` see a canonical shape.
    for _sec_id, _sec_data in sections_data.items():
        if not isinstance(_sec_data, dict):
            continue
        _insts = _sec_data.get("instruments")
        if not isinstance(_insts, dict):
            continue
        _dr = _insts.get("drums")
        if not isinstance(_dr, dict):
            continue
        _extra = _dr.get("extra")
        if not isinstance(_extra, dict):
            continue
        _voices = _extra.get("voices")
        if not isinstance(_voices, dict):
            continue
        # Validate + normalize in-place.
        _extra["voices"] = _normalize_drum_voice_concepts(
            _voices,
            context=f"sections.{_sec_id}.instruments.drums",
        )

    sections = {}
    for sec_id, sec_data in sections_data.items():
        if not isinstance(sec_data, dict):
            raise ConfigError(f"Section '{sec_id}' must be a mapping.")
        sections[sec_id] = parse_section(sec_id, sec_data)

    arrangement = raw.get("arrangement")
    if not isinstance(arrangement, list) or not arrangement:
        raise ConfigError("Top-level 'arrangement' list is required and cannot be empty.")
    for sec_ref in arrangement:
        if sec_ref not in sections:
            raise ConfigError(f"Arrangement references unknown section id '{sec_ref}'.")

    engines = build_engine_registry(raw)
    cfg = RootConfig(
        version=version,
        song=song,
        sections=sections,
        arrangement=list(map(str, arrangement)),
        raw=raw,
        engines=engines,
        runtime=runtime,
    )

    # Preserve persona/debug metadata for CLI inspection (not part of the formal model yet).
    try:
        setattr(cfg, "_personas", raw.get("_personas"))
        setattr(cfg, "_effective", raw.get("_effective"))
    except Exception:
        # If the model uses slots/frozen dataclasses, ignore.
        pass

    return cfg
