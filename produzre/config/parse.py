from __future__ import annotations

"""YAML-to-model parsing helpers.

This module converts raw YAML mappings (already loaded from disk) into strongly
typed configuration objects defined in `produzre.model`.

Responsibilities:
- Parse the `song:` mapping into `SongConfig`.
- Parse each entry under `sections:` into `SectionConfig`.
- Parse nested blocks such as `harmony:` and per-section `instruments:`.
- Preserve unknown/extra keys in `extra`/`extras` fields so users can annotate
  configs without breaking parsing, while still validating required fields.

These functions assume that higher-level validation (e.g., presence of `song`,
`sections`, and `arrangement`) is handled by the loader layer.
"""

from typing import Any, Dict, Optional

from .errors import ConfigError
from ..model import (
    HarmonyConfig,
    InstrumentConfig,
    SectionConfig,
    SongConfig,
    TransitionSettings,
)


def parse_transition_settings(data: Dict[str, Any]) -> TransitionSettings:
    """Parse a `transitions:` mapping into `TransitionSettings`.

    This helper is used to parse both song-level and instrument-level
    transition settings from YAML.

    Expected keys (all optional with defaults):
      - enabled (bool, default: True)
      - strength (float, default: 0.5)
      - ramp_bars (int, default: 1, clamped to 0-2)
      - pickup_rate (float, default: 0.35)
      - turnaround_rate (float, default: 0.25)
      - bridge_start_bars (int, default: 1, clamped to 0-2)
      - debug (bool, default: False)

    Args:
        data: Raw YAML mapping for transitions settings.

    Returns:
        TransitionSettings: Parsed transition settings.
    """
    enabled = bool(data.get("enabled", True))
    strength = float(data.get("strength", 0.5))

    # Clamp ramp_bars to 0-2
    ramp_bars = int(data.get("ramp_bars", 1))
    ramp_bars = max(0, min(2, ramp_bars))

    pickup_rate = float(data.get("pickup_rate", 0.35))
    turnaround_rate = float(data.get("turnaround_rate", 0.25))

    # Clamp bridge_start_bars to 0-2
    bridge_start_bars = int(data.get("bridge_start_bars", 1))
    bridge_start_bars = max(0, min(2, bridge_start_bars))

    debug = bool(data.get("debug", False))

    return TransitionSettings(
        enabled=enabled,
        strength=strength,
        ramp_bars=ramp_bars,
        pickup_rate=pickup_rate,
        turnaround_rate=turnaround_rate,
        bridge_start_bars=bridge_start_bars,
        debug=debug,
    )


def resolve_transition_settings(
    song_transitions: TransitionSettings,
    instrument_override: Optional[TransitionSettings] = None,
) -> TransitionSettings:
    """Resolve effective transition settings by merging song defaults with instrument overrides.

    When an instrument provides transition overrides, the override completely replaces
    the song-level settings for that instrument. In future phases, we may add
    field-level merging if needed.

    Args:
        song_transitions: Song-level transition settings (global defaults).
        instrument_override: Optional per-instrument transition override.

    Returns:
        TransitionSettings: Resolved transition settings for the instrument.
    """
    # If no override, use song-level defaults
    if instrument_override is None:
        return song_transitions

    # If override exists, use it (complete replacement for Phase 0)
    # Future enhancement: field-level merging
    return instrument_override


def parse_song(song_data: Dict[str, Any]) -> SongConfig:
    """Parse the `song:` mapping into a `SongConfig`.

    The `song:` mapping defines global defaults for a build (tempo, key/mode,
    meter, seeding, export configuration, and pattern extraction defaults).

    Parsing rules:
      - Missing values fall back to reasonable defaults (e.g., bpm=120).
      - Numeric fields are coerced to `int`/`float`.
      - `project` is optional and normalized to `str | None`.

    Expected keys (subset):
      - title, bpm, key, mode, meter
      - beats_per_bar
      - pattern_bars
      - seed, variation
      - humanize_velocity, humanize_timing
      - exports_root
      - project

    Args:
        song_data: Raw YAML mapping under `song:`.

    Returns:
        SongConfig: Parsed song configuration.
    """
    title = str(song_data.get("title", "produzre"))
    bpm = float(song_data.get("bpm", 120.0))
    key = str(song_data.get("key", "C"))
    mode = str(song_data.get("mode", "ionian"))
    meter = str(song_data.get("meter", "4/4"))

    project = song_data.get("project")
    project = str(project) if project is not None else None

    beats_per_bar = int(song_data.get("beats_per_bar", 4))
    pattern_bars = int(song_data.get("pattern_bars", 1))

    seed = int(song_data.get("seed", 0))
    take = int(song_data.get("take", 0))
    variation = float(song_data.get("variation", 0.0))

    humanize_velocity = float(song_data.get("humanize_velocity", 0.0))
    humanize_timing = float(song_data.get("humanize_timing", 0.0))

    exports_root = str(song_data.get("exports_root", "exports"))

    genre = song_data.get("genre")
    genre = str(genre).strip() if genre is not None else None

    # Parse transition settings from params.transitions if present
    transitions = TransitionSettings()  # Default
    params = song_data.get("params", {})
    if isinstance(params, dict) and "transitions" in params:
        transitions_data = params["transitions"]
        if isinstance(transitions_data, dict):
            transitions = parse_transition_settings(transitions_data)

    return SongConfig(
        title=title,
        bpm=bpm,
        key=key,
        mode=mode,
        meter=meter,
        genre=genre,
        beats_per_bar=beats_per_bar,
        pattern_bars=pattern_bars,
        seed=seed,
        take=take,
        variation=variation,
        humanize_velocity=humanize_velocity,
        humanize_timing=humanize_timing,
        project=project,
        exports_root=exports_root,
        transitions=transitions,
    )


def _parse_instrument_config(name: str, data: Dict[str, Any]) -> InstrumentConfig:
    """Parse a per-section instrument config mapping into `InstrumentConfig`.

    Instrument configs live under:
        sections.<section_id>.instruments.<instrument_name>

    Parsing rules:
      - Known keys are parsed into typed fields (floats/ints/bools as applicable).
      - `enabled` is allowed to be omitted (meaning "enabled" is implied by the
        presence of the instrument in the section).
      - `seed` and `variation` are optional overrides. When present they are
        normalized to `int` and `float` respectively.
      - `humanize_velocity` and `humanize_timing` can override the song-level
        humanize settings on a per-instrument basis.
      - Any unknown keys are preserved in `InstrumentConfig.extra` for forward
        compatibility and user annotations.

    Args:
        name: Instrument name (e.g., "bass", "drums").
        data: Raw YAML mapping for this instrument.

    Returns:
        InstrumentConfig: Parsed instrument settings for this section.
    """
    enabled = data.get("enabled")
    intensity = float(data.get("intensity", 1.0))
    style_bias = data.get("style_bias", 0.0)
    offset_beats = float(data.get("offset_beats", 0.0))

    seed = data.get("seed")
    if seed is not None:
        seed = int(seed)

    variation = data.get("variation")
    variation = float(variation) if variation is not None else None

    groove = data.get("groove")
    recipe = data.get("recipe")
    if recipe is not None:
        recipe = str(recipe).strip()

    genre = data.get("genre")
    if genre is not None:
        genre = str(genre).strip()

    voicing = data.get("voicing")
    register = data.get("register")
    role = data.get("role")
    patterns = data.get("patterns")
    solo = data.get("solo")

    hv = data.get("humanize_velocity")
    ht = data.get("humanize_timing")
    hv = float(hv) if hv is not None else None
    ht = float(ht) if ht is not None else None

    # Parse transition settings override from params.transitions if present
    transitions = None
    params = data.get("params", {})
    if isinstance(params, dict) and "transitions" in params:
        transitions_data = params["transitions"]
        if isinstance(transitions_data, dict):
            transitions = parse_transition_settings(transitions_data)

    known_keys = {
        "enabled",
        "intensity",
        "style_bias",
        "offset_beats",
        "seed",
        "variation",
        "groove",
        "recipe",
        "genre",
        "voicing",
        "register",
        "role",
        "patterns",
        "solo",
        "humanize_velocity",
        "humanize_timing",
        "params",  # Handle params sub-structure for transitions
    }
    extra = {k: v for k, v in data.items() if k not in known_keys}

    return InstrumentConfig(
        enabled=enabled,
        intensity=intensity,
        style_bias=style_bias,
        offset_beats=offset_beats,
        seed=seed,
        variation=variation,
        groove=groove,
        recipe=recipe,
        genre=genre,
        voicing=voicing,
        register=register,
        role=role,
        patterns=patterns,
        solo=solo,
        humanize_velocity=hv,
        humanize_timing=ht,
        transitions=transitions,
        extra=extra,
    )


def _parse_harmony(data: Dict[str, Any]) -> HarmonyConfig:
    """Parse a section-level `harmony:` mapping into `HarmonyConfig`.

    The harmony block defines the Roman numeral progression and the chord change
    rate (in beats). It is section-scoped because different sections may use
    different progressions or harmonic rhythm.

    Validation:
      - `progression` is optional; when absent, recipe or preset fallback is used.

    Unknown keys:
      - Any additional keys are preserved in `HarmonyConfig.extra`.

    Args:
        data: Raw YAML mapping under `harmony:`.

    Returns:
        HarmonyConfig: Parsed harmony configuration.
    """
    progression = data.get("progression", "")
    chord_rate = float(data.get("chord_rate", 4.0))

    known_keys = {"progression", "chord_rate"}
    extra = {k: v for k, v in data.items() if k not in known_keys}

    prog_value = progression if progression else ""
    if isinstance(prog_value, list):
        pass  # Keep as list for build_harmony_plan to handle
    else:
        prog_value = str(prog_value)

    return HarmonyConfig(progression=prog_value, chord_rate=chord_rate, extra=extra)


def parse_section(section_id: str, data: Dict[str, Any]) -> SectionConfig:
    """Parse a single section mapping into a `SectionConfig`.

    Sections define the high-level arrangement building blocks (verse, chorus,
    bridge, etc.), along with timing and optional per-section overrides.

    Required fields:
      - `type` (e.g., "verse", "chorus", "solo")

    Optional timing fields:
      - `bars` (int): number of bars in this section
      - `beats` (float): explicit beat length (overrides bars)

    Optional musical overrides:
      - `meter`, `key`, `mode`

    Harmony:
      - `harmony` may be provided as a mapping; when present it is parsed and
        validated by `_parse_harmony()`.

    Instruments:
      - `instruments` must be a mapping of instrument name -> mapping.
      - Each instrument mapping is parsed by `_parse_instrument_config()`.
      - If an instrument entry is not a mapping, a ConfigError is raised.

    Unknown keys:
      - Top-level unknown section keys are preserved in `SectionConfig.extras`.

    Args:
        section_id: Key of the section under `sections:`.
        data: Raw YAML mapping for the section.

    Raises:
        ConfigError: If required fields are missing or if nested structures are
            of the wrong type.

    Returns:
        SectionConfig: Parsed section configuration.
    """
    stype = data.get("type")
    if not stype:
        raise ConfigError(f"Section '{section_id}' is missing required 'type' field")

    bars = data.get("bars")
    beats = data.get("beats")
    if bars is not None:
        bars = int(bars)
    if beats is not None:
        beats = float(beats)

    meter = data.get("meter")
    key = data.get("key")
    mode = data.get("mode")

    # Seed & variation overrides (granular section-level control)
    section_seed = data.get("seed")
    if section_seed is not None:
        section_seed = int(section_seed)
    section_variation = data.get("variation")
    if section_variation is not None:
        section_variation = float(section_variation)

    harmony_data = data.get("harmony")
    harmony = _parse_harmony(harmony_data) if isinstance(harmony_data, dict) else None
    progression = data.get("progression")

    # Intent: bridge/break contrast patterns (Phase 15)
    intent = data.get("intent")
    if intent is not None:
        intent = str(intent)

    # Solo/lead section flags (Phase B10)
    solo = data.get("solo")
    if solo is not None:
        solo = bool(solo)

    role = data.get("role")
    if role is not None:
        role = str(role)

    instruments_data = data.get("instruments") or {}
    instruments = {}
    if isinstance(instruments_data, dict):
        for inst_name, inst_cfg in instruments_data.items():
            if not isinstance(inst_cfg, dict):
                raise ConfigError(
                    f"Section '{section_id}' instrument '{inst_name}' config must be a mapping."
                )
            instruments[inst_name] = _parse_instrument_config(inst_name, inst_cfg)

    known_keys = {"type", "bars", "beats", "meter", "key", "mode", "harmony", "instruments", "progression", "intent", "solo", "role", "seed", "variation"}
    extras = {k: v for k, v in data.items() if k not in known_keys}

    return SectionConfig(
        id=section_id,
        type=str(stype),
        bars=bars,
        beats=beats,
        meter=str(meter) if meter is not None else None,
        key=str(key) if key is not None else None,
        mode=str(mode) if mode is not None else None,
        seed=section_seed,
        variation=section_variation,
        harmony=harmony,
        instruments=instruments,
        progression=progression,
        intent=intent,
        solo=solo,
        role=role,
        extras=extras,
    )
