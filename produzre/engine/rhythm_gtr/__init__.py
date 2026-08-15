# produzre/engine/rhythm_gtr/__init__.py
"""Rhythm guitar engine for Produzre (Phase RG0).

This engine generates rhythm guitar parts based on harmony plan, rhythm grid,
and rhythm accents. It supports multiple strumming patterns, voicings, and
dynamic responsiveness to section types.

Public API:
    - ENGINE_DEFAULT_PRIORITY: Execution priority
    - ENGINE_DEFAULT_CHANNEL: MIDI channel
    - ENGINE_DEFAULT_PROGRAM: GM program number
    - contribute_plan(): Optional plan contribution (no-op for now)
    - render_into_timeline(): Main rendering function
"""

from __future__ import annotations

import logging
import hashlib
import random
from typing import Optional, Dict, Any

from ..bass import _get_mode_scale_offsets, _parse_roman_numeral
from ...model import RootConfig, SectionConfig
from ...harmony import HarmonySectionPlan
from ...rhythm import RhythmGrid
from ...timeline import InstrumentTimeline

# Phase RG0: Import defaults and types for better organization
from .defaults import (
    ENGINE_DEFAULT_PRIORITY,
    ENGINE_DEFAULT_CHANNEL,
    ENGINE_DEFAULT_PROGRAM,
    ENGINE_REQUIRES,
    ENGINE_PROVIDES,
    ENGINE_ROLES,
)

# Phase RG1: Import voicing generation
from .voicings import choose_voicing_for_section_type
from .types import ChordShape

# Phase RG2: Import pattern generation
from .rhythm import (
    build_bar_pattern,
    develop_bar_pattern,
    apply_density_budget,
    apply_microtiming,
    _apply_accents as _apply_accent_beats,
)

# Phase RG3: Import parameter resolution
from .params import resolve_params, params_to_dict

# Phase RG4: Import legacy parameter extraction (refactoring)
from .legacy_params import resolve_legacy_guitar_params

# Phase RG4: Import articulation and humanization
from .articulation import create_chord_articulation, apply_strum_spread
from .humanize import humanize_velocity, humanize_timing

# Phase RG5: Import transition handling
from .transitions import (
    get_transition_directive,
    adjust_pattern_for_transition,
)


def quantize_to_subdivision(
    value: float,
    subdivision: int,
) -> float:
    """Quantize a beat value to the nearest subdivision grid point.

    Args:
        value: Beat position or duration to quantize
        subdivision: Subdivision level (2=8ths, 4=16ths)

    Returns:
        float: Quantized value
    """
    if subdivision <= 0:
        return value

    # Calculate grid size
    grid_size = 1.0 / subdivision

    # Round to nearest grid point
    return round(value / grid_size) * grid_size

# Export engine metadata for orchestrator
__all__ = [
    "ENGINE_DEFAULT_PRIORITY",
    "ENGINE_DEFAULT_CHANNEL",
    "ENGINE_DEFAULT_PROGRAM",
    "contribute_plan",
    "render_into_timeline",
]


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))



def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


# Add stable hash helper for deterministic strum direction alternation

def _stable_u32(text: str) -> int:
    """Return a stable 32-bit integer hash for a string (cross-run stable)."""
    return int.from_bytes(hashlib.md5(text.encode("utf-8")).digest()[:4], "little")


def _truthy(v) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "y", "on")
    return False


def _voice_lead_root(root: int, prev: int, lo: int, hi: int, key: str) -> int:
    """Octave-shift `root` to be near `prev`, staying within [lo, hi].

    Candidates are root +/- 12*k. Choose the candidate with the smallest
    absolute distance to `prev`. Tie-break deterministically.
    """
    cands = []
    for k in (-2, -1, 0, 1, 2):
        p = root + 12 * k
        if lo <= p <= hi:
            cands.append(p)

    if not cands:
        return max(lo, min(hi, root))

    best = cands[0]
    best_d = abs(best - prev)
    for cand in cands[1:]:
        d = abs(cand - prev)
        if d < best_d:
            best = cand
            best_d = d
        elif d == best_d:
            pick_hi = (_stable_u32(key + ":tie") % 2) == 1
            best = max(best, cand) if pick_hi else min(best, cand)
    return best


# R3-V2: Helper for strum offsets (micro-staggered chord hits)
def _strum_offsets(n: int, span_beats: float, direction: str) -> list[float]:
    """Return per-note start offsets (in beats) for a simple strum.

    - n: number of notes in the chord hit
    - span_beats: total strum spread across the notes
    - direction: 'down' (low→high), 'up' (high→low)

    Offsets always start at 0.0 and increase; caller decides ordering.
    """
    if n <= 1 or span_beats <= 0.0:
        return [0.0] * max(1, n)
    step = span_beats / float(n - 1)
    offs = [i * step for i in range(n)]
    return offs


def _apply_rhythmic_pattern(play_pattern: Optional[str], beat_in_bar: float, base_place: bool) -> bool:
    """
    Minimal R2-C pattern override for rhythm placement.

    All patterns assume a 4/4-style beat grid where beat_in_bar increases from 0.0
    at the bar start:

    - "gallop": eighth + two sixteenths per beat → fractions 0.0, 0.5, 0.75
      relative to each beat
    - "syncopated": emphasize offbeats [0.5, 1.5, 2.5]
    - "offbeat": emphasize eighth-note offbeats (the "and" of every beat)
    - "backbeat": emphasize 2 and 4 in 4/4 → [1.0, 3.0]

    Returns a modified place_note decision that can be used to override the
    intensity-based grid selection. Note: the legacy renderer synthesizes its
    own sub-beat positions for these patterns (see
    ``_pattern_positions_for_bar``) because the shared rhythm grid is usually
    quarter-note resolution and would never contain the sub-beat targets.
    """
    if not play_pattern:
        return base_place

    # Small window around target beats to tolerate floating-point/grid jitter.
    tol = 0.05
    frac = beat_in_bar % 1.0

    if play_pattern == "gallop":
        return any(abs(frac - f) < tol for f in (0.0, 0.5, 0.75)) or abs(frac - 1.0) < tol

    if play_pattern == "syncopated":
        syncop_beats = [0.5, 1.5, 2.5]
        return any(abs(beat_in_bar - b) < tol for b in syncop_beats)

    if play_pattern == "offbeat":
        return abs(frac - 0.5) < tol

    if play_pattern == "backbeat":
        back_beats = [1.0, 3.0]
        return any(abs(beat_in_bar - b) < tol for b in back_beats)

    # Unknown pattern: fall back to whatever the intensity logic decided.
    return base_place


def _pattern_positions_for_bar(play_pattern: Optional[str], bpb: float) -> Optional[list]:
    """Bar-relative hit positions (in beats) for legacy play_pattern presets.

    The orchestrator rhythm grid is typically quarter-note resolution, so
    sub-beat presets (gallop/syncopated/offbeat) can never match grid cells —
    filtering integer-beat cells produced ZERO notes. Instead, the legacy
    renderer synthesizes eighth/sixteenth-note positions directly per bar:

    - "gallop":     0.0, 0.5, 0.75 relative to each beat (gallop rhythm)
    - "syncopated": the "and" of every beat except the last → 0.5, 1.5, 2.5
    - "offbeat":    the "and" of every beat → 0.5, 1.5, 2.5, 3.5
    - "backbeat":   beats 2 and 4 (odd integer beats) → 1.0, 3.0

    Returns None for unknown patterns (caller falls back to grid cells).
    """
    if not play_pattern:
        return None
    n_beats = max(1, int(bpb))
    if play_pattern == "gallop":
        return [b + f for b in range(n_beats) for f in (0.0, 0.5, 0.75)]
    if play_pattern == "syncopated":
        return [b + 0.5 for b in range(max(1, n_beats - 1))]
    if play_pattern == "offbeat":
        return [b + 0.5 for b in range(n_beats)]
    if play_pattern == "backbeat":
        return [float(b) for b in range(n_beats) if b % 2 == 1]
    return None


# Very simple key → MIDI root mapping for rhythm guitar (powerchord root)
_KEY_TO_MIDI_ROOT: Dict[str, int] = {
    "C": 48,   # C3
    "C#": 49,
    "Db": 49,
    "D": 50,
    "D#": 51,
    "Eb": 51,
    "E": 52,
    "F": 53,
    "F#": 54,
    "Gb": 54,
    "G": 55,
    "G#": 56,
    "Ab": 56,
    "A": 57,
    "A#": 58,
    "Bb": 58,
    "B": 59,
}


# Compute a rhythm guitar root MIDI note for a given chord numeral (modal logic, guitar register)
def _rhythm_root_for_numeral(
    cfg: RootConfig,
    section: SectionConfig,
    numeral: str,
    rhythm_cfg,
) -> int:
    """Compute a rhythm guitar root MIDI note for a given chord numeral.

    This uses:
    - song key (cfg.song.key or section.key) as the tonic,
    - song mode (cfg.song.mode) to choose the scale,
    - the Roman numeral (with accidentals) to pick the scale degree,
    - a simple register assumption appropriate for rhythm guitar.

    It mirrors the bass engine's degree logic but in a higher octave.
    """
    # Base tonic in a guitar-friendly register (around C3 by default).
    key = (section.key or cfg.song.key or "C").strip()
    key = key.replace("♭", "b").replace("♯", "#")
    tonic_midi = _KEY_TO_MIDI_ROOT.get(key, 48)  # default C3

    offsets = _get_mode_scale_offsets(getattr(cfg.song, "mode", None))
    degree_index, accidental = _parse_roman_numeral(numeral)
    if not offsets:
        semitone = 0
    else:
        degree_index = max(0, min(degree_index, len(offsets) - 1))
        semitone = offsets[degree_index] + accidental

    pitch = tonic_midi + semitone

    # Octave shift based on register setting. rhythm_cfg may be an
    # InstrumentConfig-like object (legacy mode) or a plain params dict
    # (pattern mode) — support both, including the nested 'extra' wrapper.
    register = None
    if rhythm_cfg is not None:
        if isinstance(rhythm_cfg, dict):
            register = rhythm_cfg.get("register")
        else:
            register = getattr(rhythm_cfg, "register", None)
            if register is None:
                _extra = getattr(rhythm_cfg, "extra", None)
                if isinstance(_extra, dict):
                    if isinstance(_extra.get("extra"), dict):
                        _extra = _extra["extra"]
                    register = _extra.get("register")
    if register == "high":
        pitch += 12
    elif register == "low":
        pitch -= 12

    return pitch


def _resolve_rhythm_root_midi(cfg: RootConfig, section: SectionConfig) -> int:
    """Resolve a basic rhythm guitar tonic MIDI note for the section's key.

    This is intentionally simple for this phase; later the harmony engine
    will provide full degree-based chord pitches.
    """
    key = (section.key or cfg.song.key or "C").strip()
    key = key.replace("♭", "b").replace("♯", "#")
    return _KEY_TO_MIDI_ROOT.get(key, 48)  # default C3


def contribute_plan(*args: Any, **kwargs: Any) -> None:
    """Optional plan contribution hook for rhythm guitar (Phase RG0).

    Currently a no-op. Future phases may export rhythm texture data,
    chord voicing information, or strumming patterns to the PerformancePlan.

    Args (all via kwargs):
        plan: PerformancePlan - Central data store
        section_ctx: dict - Section metadata
        rng: random.Random - Deterministic RNG
        logger: logging.Logger - For debug output

    Returns:
        None
    """
    if args:
        raise TypeError("rhythm_gtr.contribute_plan only supports keyword arguments")
    plan = kwargs.get("plan")
    section_ctx = kwargs.get("section_ctx") or {}
    section = section_ctx.get("section")
    if plan is None or section is None:
        return
    ensemble = plan.get(f"ensemble.{section.id}", {})
    role_data = ensemble.get("roles", {}).get("rhythm_gtr", {}) if isinstance(ensemble, dict) else {}
    payload = {
        "section_id": section.id,
        "role": role_data.get("role", "comp"),
        "density_multiplier": role_data.get("density_multiplier", 1.0),
        "lead_activity_windows": ensemble.get("lead_activity_windows", []) if isinstance(ensemble, dict) else [],
    }
    plan.set("rhythm.texture", payload)
    plan.set("rhythm.chords", {"section_id": section.id, "source": "harmony.plan"})


def render_into_timeline(
    cfg: Optional[RootConfig] = None,
    section: Optional[SectionConfig] = None,
    instrument_name: Optional[str] = None,
    instrument_cfg=None,
    harmony_plan: Optional[HarmonySectionPlan] = None,
    rhythm_grid: Optional[RhythmGrid] = None,
    section_start_beat: Optional[float] = None,
    timeline: Optional[InstrumentTimeline] = None,
    logger: Optional[logging.Logger] = None,
    **kwargs,
) -> None:
    """Render rhythm guitar pattern into the given timeline.

    Supports two modes:
    1. Legacy mode (explicit parameters) - uses rhythm grid cells with complex strumming
    2. Rhythm lock mode (kwargs with rhythm_features) - follows drum hat density and kick syncopation

    Rhythm lock mode parameters (from kwargs):
        rhythm_features: Dict with 'drums' key containing RhythmFeatures
        instrument_cfg.params:
            - follow_hats: Match hat density for strumming (default False for legacy compat)
            - accent_syncopation: Accent syncopated kicks (default True)
            - voicing: "power_chord" or "palm_mute" (default "power_chord")
            - octave: Guitar octave (default 3)
        rng: Deterministic RNG for variation
    """
    # Handle both legacy and new kwargs-based calling conventions
    if cfg is None:
        cfg = kwargs.get("cfg")
    if section is None:
        section = kwargs.get("section")
    if instrument_name is None:
        instrument_name = kwargs.get("instrument_name", "rhythm_gtr")
    if instrument_cfg is None:
        instrument_cfg = kwargs.get("instrument_cfg") or kwargs.get("instrument")
    if harmony_plan is None:
        harmony_plan = kwargs.get("harmony_plan")
    if rhythm_grid is None:
        rhythm_grid = kwargs.get("rhythm_grid")
    if section_start_beat is None:
        section_start_beat = float(kwargs.get("section_start_beat", 0.0))
    if timeline is None:
        timeline = kwargs.get("timeline")
    if logger is None:
        logger = kwargs.get("logger") or logging.getLogger("produzre.rhythm")

    rhythm_features_map = kwargs.get("rhythm_features", {})
    rng = kwargs.get("rng")

    # Check if rhythm locking is enabled
    params = {}
    if instrument_cfg is not None:
        if hasattr(instrument_cfg, "params"):
            params = instrument_cfg.params or {}
        elif isinstance(instrument_cfg, dict):
            params = instrument_cfg.get("params", {})

    follow_hats = False
    if isinstance(params, dict):
        follow_hats = params.get("follow_hats", False)
    elif hasattr(params, "follow_hats"):
        follow_hats = getattr(params, "follow_hats", False)

    # --- Rhythm guitar recipe resolution ---
    _all_rg_recipes: dict = {}
    if hasattr(cfg, "raw") and isinstance(getattr(cfg, "raw", None), dict):
        _all_rg_recipes = cfg.raw.get("_recipes", {}).get("rhythm_gtr", {})

    if _all_rg_recipes:
        from ...config.recipes import resolve_recipe_name as _resolve_rg_recipe

        _song = getattr(cfg, "song", None)
        _song_genre = getattr(_song, "genre", None) if _song else None
        _bpm = float(getattr(_song, "bpm", 120.0)) if _song else 120.0
        _meter = str(getattr(_song, "meter", None) or "4/4") if _song else "4/4"

        _section_recipe = None
        _global_recipe = None
        _inst_genre = None
        if instrument_cfg is not None:
            _extra_d = instrument_cfg.extra or {} if hasattr(instrument_cfg, "extra") else {}
            if isinstance(_extra_d, dict) and "extra" in _extra_d:
                _extra_d = _extra_d["extra"]
            _section_recipe = _extra_d.get("recipe") if isinstance(_extra_d, dict) else None
            _global_recipe = getattr(instrument_cfg, "recipe", None)
            _inst_genre = getattr(instrument_cfg, "genre", None)

        # Per-instrument genre: section instrument → global instrument → song
        if _inst_genre is None and hasattr(cfg, "raw") and isinstance(getattr(cfg, "raw", None), dict):
            _raw_instruments = cfg.raw.get("instruments")
            if isinstance(_raw_instruments, dict):
                _gi = _raw_instruments.get("rhythm_gtr")
                if isinstance(_gi, dict):
                    _inst_genre = _gi.get("genre")
        _genre = _inst_genre if _inst_genre is not None else _song_genre

        _rg_recipe_name = _resolve_rg_recipe(
            instrument="rhythm_gtr",
            genre=_genre,
            section_type=section.type if section else "verse",
            intensity=(
                (getattr(instrument_cfg, "intensity", None) if instrument_cfg else None)
                or getattr(section, "intensity", None)
                or 0.7
            ),
            bpm=_bpm,
            time_signature=_meter,
            instrument_recipe=_global_recipe,
            section_recipe=_section_recipe,
            recipes=_all_rg_recipes,
        )

        if _rg_recipe_name and _rg_recipe_name in _all_rg_recipes:
            _rg_recipe = _all_rg_recipes[_rg_recipe_name]
            _rp = _rg_recipe.get("params", {})
            if _rp and instrument_cfg is not None and hasattr(instrument_cfg, "extra"):
                from ...config.recipes import merge_recipe_params as _merge_recipe_params

                _existing = instrument_cfg.extra or {}
                if isinstance(_existing, dict) and "extra" in _existing:
                    _existing = _existing["extra"]
                if isinstance(_existing, dict):
                    # persona < recipe < user (see merge_recipe_params)
                    _merged = _merge_recipe_params(_existing, _rp)
                    _merged.setdefault("use_patterns", True)
                    instrument_cfg.extra = _merged

            if logger:
                logger.info(
                    "Rhythm guitar: using recipe '%s' (genre=%s, section=%s)",
                    _rg_recipe_name, _genre, section.type if section else "?",
                )

    # Phase RG2: Check if pattern-based rendering is enabled (from extra)
    use_patterns = False
    if instrument_cfg is not None and hasattr(instrument_cfg, "extra"):
        extra_dict = instrument_cfg.extra or {}
        # Handle nested 'extra' key if present (from config loader)
        if isinstance(extra_dict, dict) and 'extra' in extra_dict:
            extra_dict = extra_dict['extra']
        if isinstance(extra_dict, dict):
            use_patterns = bool(extra_dict.get("use_patterns", False))

    # Extract plan data for pattern-based mode
    plan = kwargs.get("plan")

    # Sprint 4: Apply coordination rules (Rule 1, Rule 4, Rule 5)
    coordinated_accent_beats: set = set()  # Rule 4: Drum accent positions for velocity boost
    if plan is not None and section is not None and instrument_cfg is not None:
        try:
            from ...orchestrate import EngineCoordinator
            coordinator = EngineCoordinator(plan, logger=logger)

            # Rule 4: Coordinated accents — read actual drum accent beats from plan
            coordinated_accent_beats = coordinator.get_accent_beats(section.id)

            # Theme coupling (M3): the song's riff attacks act as accent
            # positions, so strums punch where the theme hits (Rule 4 ext.).
            from ...themes.coupling import get_theme_onsets as _theme_onsets

            _riff_onsets = _theme_onsets(plan, section.id, "riff")
            if _riff_onsets:
                coordinated_accent_beats = set(coordinated_accent_beats) | set(
                    _riff_onsets
                )
                if logger:
                    logger.debug(
                        f"[THEMES] Section '{section.id}': {len(_riff_onsets)} "
                        f"riff attacks added to rhythm_gtr accents"
                    )
            if coordinated_accent_beats and logger:
                logger.debug(
                    f"[COORDINATION] Section '{section.id}': {len(coordinated_accent_beats)} "
                    f"coordinated accent beats for velocity boost"
                )

            # Rule 1: Inverse density (lead-rhythm coordination)
            intensity_adjustment = coordinator.get_rhythm_intensity_adjustment(section.id)

            # Rule 5: Solo support (simplify during lead solos)
            solo_adjustment = coordinator.get_rhythm_simplification_factor(section.id)

            # Combine adjustments (multiplicative)
            role_adjustment = coordinator.get_density_multiplier(section.id, "rhythm_gtr")
            combined_adjustment = intensity_adjustment * solo_adjustment * role_adjustment

            if abs(combined_adjustment - 1.0) > 0.01:  # Only apply if adjusted
                # Modify the density parameter in instrument_cfg.extra
                if hasattr(instrument_cfg, "extra"):
                    extra_dict = instrument_cfg.extra or {}
                    # Handle nested 'extra' key
                    if isinstance(extra_dict, dict) and 'extra' in extra_dict:
                        extra_dict = extra_dict['extra']
                    if isinstance(extra_dict, dict):
                        original_density = extra_dict.get("density", 1.0)
                        adjusted_density = float(original_density) * combined_adjustment
                        adjusted_density = max(0.25, min(2.0, adjusted_density))  # Clamp
                        extra_dict["density"] = adjusted_density

                        if logger:
                            if coordinator.is_solo_section(section.id):
                                logger.debug(
                                    f"[COORDINATION] Solo section '{section.id}': rhythm simplified "
                                    f"{original_density:.2f} * {solo_adjustment:.2f} (solo) = {adjusted_density:.2f}"
                                )
                            else:
                                logger.debug(
                                    f"[COORDINATION] Rhythm density adjusted in '{section.id}': "
                                    f"{original_density:.2f} * {intensity_adjustment:.2f} = {adjusted_density:.2f}"
                                )
        except Exception as e:
            # Silently fail coordination to avoid breaking rhythm rendering
            if logger:
                logger.debug(f"[COORDINATION] Rhythm coordination failed: {e}")

    if use_patterns and plan is not None and rng is not None:
        _render_pattern_based_guitar(
            cfg=cfg,
            section=section,
            instrument_name=instrument_name,
            instrument_cfg=instrument_cfg,
            harmony_plan=harmony_plan,
            rhythm_grid=rhythm_grid,
            section_start_beat=section_start_beat,
            timeline=timeline,
            plan=plan,
            rng=rng,
            logger=logger,
        )
        return

    # If rhythm locking is enabled and we have drum features, use rhythm lock mode
    drum_features = rhythm_features_map.get("drums") if rhythm_features_map else None
    if follow_hats and drum_features is not None and rng is not None:
        _render_rhythm_locked_guitar(
            cfg=cfg,
            section=section,
            instrument_name=instrument_name,
            harmony_plan=harmony_plan,
            rhythm_grid=rhythm_grid,
            section_start_beat=section_start_beat,
            timeline=timeline,
            drum_features=drum_features,
            instrument_cfg=instrument_cfg,
            rng=rng,
            logger=logger,
        )
        return

    # Fall back to legacy rhythm grid mode
    _render_legacy_rhythm_guitar(
        cfg=cfg,
        section=section,
        instrument_name=instrument_name,
        instrument_cfg=instrument_cfg,
        harmony_plan=harmony_plan,
        rhythm_grid=rhythm_grid,
        section_start_beat=section_start_beat,
        timeline=timeline,
        rng=rng,  # Phase RG1: Pass RNG for deterministic voicing
        coordinated_accent_beats=coordinated_accent_beats,  # Rule 4
        logger=logger,
    )


def _render_pattern_based_guitar(
    cfg: RootConfig,
    section: SectionConfig,
    instrument_name: str,
    instrument_cfg,
    harmony_plan: Optional[HarmonySectionPlan],
    rhythm_grid: RhythmGrid,
    section_start_beat: float,
    timeline: InstrumentTimeline,
    plan,
    rng: Optional[random.Random],
    logger: logging.Logger,
) -> None:
    """Pattern-based rhythm guitar rendering (Phase RG2).

    Uses rhythm.grid and rhythm.accents to generate musically coherent
    strumming patterns with proper accent placement and microtiming.
    """
    if logger is None:
        logger = logging.getLogger("produzre.rhythm")

    # Validate instrument configuration
    if instrument_cfg is None or getattr(instrument_cfg, "enabled", True) is False:
        logger.debug(
            "Section '%s': instrument '%s' disabled or missing; skipping.",
            section.id,
            instrument_name,
        )
        return

    if harmony_plan is None or not harmony_plan.chord_slots:
        logger.debug("Section '%s': no harmony plan; skipping rhythm guitar.", section.id)
        return

    # Extract rhythm.accents from plan
    rhythm_accents_data = plan.get("rhythm.accents") if plan else None
    accent_beats = []
    if rhythm_accents_data and "accent_beats" in rhythm_accents_data:
        accent_beats = rhythm_accents_data["accent_beats"]
    try:
        from ...orchestrate import EngineCoordinator
        actual_accents = EngineCoordinator(plan, logger=logger).get_accent_beats(section.id)
        if actual_accents:
            accent_beats = sorted(actual_accents)
    except Exception:
        pass

    # Theme coupling (M3): riff attacks act as accent positions so strums
    # punch where the song's theme hits (Rule 4 extension, pattern mode).
    if plan is not None:
        from ...themes.coupling import get_theme_onsets as _theme_onsets

        _riff = _theme_onsets(plan, section.id, "riff")
        if _riff:
            accent_beats = sorted(set(accent_beats) | set(_riff))

    # Phase RG3: Resolve parameters using section-type-aware defaults
    extra = instrument_cfg.extra if instrument_cfg is not None else {}
    # Handle nested 'extra' key if present (from config loader)
    if isinstance(extra, dict) and 'extra' in extra:
        extra = extra['extra']

    raw_intensity = getattr(instrument_cfg, "intensity", None) if instrument_cfg is not None else None
    if raw_intensity is None:
        # Macro-dynamics: fall back to the section's resolved intensity
        # (orchestrate.plan.resolve_section_intensity) before the default.
        raw_intensity = getattr(section, "intensity", None)
    if raw_intensity is None:
        raw_intensity = 0.7
    params = resolve_params(
        section_type=section.type,
        intensity=raw_intensity,
        extra=extra,
    )

    # Log resolved parameters
    if logger:
        logger.debug(
            "Section '%s': resolved rhythm_gtr params: %s",
            section.id,
            params_to_dict(params),
        )

    # Base velocity from intensity and accent_strength
    intensity = max(0.0, min(2.0, raw_intensity))
    base_velocity = int(75 * intensity * (1.0 + params.accent_strength * 0.3))
    base_velocity = max(1, min(127, base_velocity))

    # Root computation config: wire the resolved register through pattern
    # mode so the `register` param actually shifts the chord roots.
    rhythm_cfg = {"register": params.register}

    # Song tempo for ms→beats conversions (strum spread).
    song_bpm = 120.0
    if cfg is not None and getattr(cfg, "song", None) is not None:
        try:
            song_bpm = float(getattr(cfg.song, "bpm", 120.0) or 120.0)
        except Exception:
            song_bpm = 120.0

    # Phase RG1: Pre-generate chord voicings for all harmony slots
    # Now delegates to shared instruments library for physically playable shapes
    chord_voicings: Dict[str, ChordShape] = {}
    prev_shape: Optional[ChordShape] = None

    for chord_slot in harmony_plan.chord_slots:
        # Compute root MIDI note from the numeral
        root_midi = _rhythm_root_for_numeral(cfg, section, chord_slot.numeral, rhythm_cfg)

        # If params.voicing is "auto", use section-based selection
        # Otherwise, use the explicit voicing style
        if params.voicing == "auto":
            voicing = choose_voicing_for_section_type(
                root_midi=root_midi,
                numeral=chord_slot.numeral,
                section_type=section.type,
                intensity=intensity,
                prev_chord_shape=prev_shape,
                rng=rng,
            )
        else:
            from .voicings import choose_voicing
            voicing = choose_voicing(
                root_midi=root_midi,
                numeral=chord_slot.numeral,
                voicing_style=params.voicing,
                prev_chord_shape=prev_shape,
                rng=rng,
            )
        # Use numeral as key for quick lookup
        key = f"{chord_slot.numeral}_{chord_slot.index}"
        chord_voicings[key] = voicing
        prev_shape = voicing

        if logger:
            logger.debug(
                "Section '%s': chord %s (root=%d) → voicing %s with notes %s",
                section.id,
                chord_slot.numeral,
                root_midi,
                voicing.voicing_name or "default",
                voicing.pitches,
            )

    # Phase RG5: Extract transition directive for this section
    transition_directive = get_transition_directive(plan, section.id)
    lead_activity_windows = []
    try:
        from ...orchestrate import EngineCoordinator
        lead_activity_windows = EngineCoordinator(plan, logger=logger).get_lead_activity_windows(section.id)
    except Exception:
        lead_activity_windows = []
    if logger and transition_directive:
        logger.debug(
            "Section '%s': transition directive found - energy_ramp=%.2f, density_ramp=%.2f, turnaround=%s",
            section.id,
            transition_directive.get("energy_ramp", 0.0),
            transition_directive.get("density_ramp", 0.0),
            transition_directive.get("turnaround_hint", "none"),
        )

    # Generate patterns and events per bar
    beats_per_bar = rhythm_grid.beats_per_bar
    total_bars = int(rhythm_grid.total_beats / beats_per_bar)
    phrase_len_bars = 4
    phrase_development_enabled = True
    if isinstance(extra, dict):
        try:
            phrase_len_bars = int(extra.get("phrase_len_bars", phrase_len_bars))
        except Exception:
            phrase_len_bars = 4
        if "sustain_mode" in extra:
            phrase_development_enabled = False
        if extra.get("phrase_development") is False:
            phrase_development_enabled = False
    phrase_len_bars = max(1, phrase_len_bars)

    events_count = 0

    # Phase 1.4: strum_style guides auto style selection when style isn't pinned
    effective_style = params.style
    if params.strum_style != "balanced" and effective_style == "auto":
        effective_style = params.strum_style  # e.g. "downbeat_heavy" → straight_8s via mapping in rhythm.py

    base_pattern = None

    for bar_idx in range(total_bars):
        bar_start_beat = bar_idx * beats_per_bar

        # Get accent beats for this bar
        bar_accents = [
            beat - bar_start_beat
            for beat in accent_beats
            if bar_start_beat <= beat < bar_start_beat + beats_per_bar
        ]

        # Build the phrase's base pattern ONCE per phrase (at phrase
        # boundaries) and reuse it across the phrase, so phrases
        # repeat-and-develop instead of re-randomizing every bar.
        if base_pattern is None or (bar_idx % phrase_len_bars) == 0:
            base_pattern = build_bar_pattern(
                section_type=section.type,
                style=effective_style,
                density=params.density,
                accent_beats=None,
                beats_per_bar=beats_per_bar,
                rng=rng,
            )
        pattern = base_pattern

        # Per-bar drum accents are applied on top of the shared base pattern.
        if bar_accents:
            pattern = _apply_accent_beats(pattern, bar_accents, beats_per_bar)

        if phrase_development_enabled:
            pattern = develop_bar_pattern(
                pattern,
                bar_idx=bar_idx,
                total_bars=total_bars,
                phrase_len_bars=phrase_len_bars,
                section_type=section.type,
                density=params.density,
                beats_per_bar=beats_per_bar,
                rng=rng,
            )

        # During a lead statement retain only the comping cell's defining
        # accents. In the answer spaces the full pattern returns.
        bar_end_beat = bar_start_beat + beats_per_bar
        if any(start < bar_end_beat and end > bar_start_beat for start, end in lead_activity_windows):
            pattern = apply_density_budget(pattern, 0.58, rng)

        # Phase RG5: Adjust pattern for transitions (builds, turnarounds, pickups)
        pattern = adjust_pattern_for_transition(
            pattern=pattern,
            bar_idx=bar_idx,
            total_bars=total_bars,
            transition=transition_directive,
            beats_per_bar=beats_per_bar,
            rng=rng,
        )

        # Convert pattern hits to MIDI events (Phase RG4: articulation + humanization)
        for hit_idx in pattern.hits:
            # Convert subdivision index to beat offset
            beat_offset = hit_idx / pattern.subdivision
            beat_position = bar_start_beat + beat_offset

            # Resolve the active chord slot PER HIT so mid-bar chord changes
            # are honoured (one chord per bar smeared the old chord across
            # the barline-internal change).
            active_chord_slot = None
            for chord_slot in harmony_plan.chord_slots:
                if chord_slot.start_beat <= beat_position < chord_slot.end_beat:
                    active_chord_slot = chord_slot
                    break
            if active_chord_slot is None:
                continue
            voicing = chord_voicings.get(
                f"{active_chord_slot.numeral}_{active_chord_slot.index}"
            )
            if voicing is None or not voicing.pitches:
                continue

            # Apply microtiming if configured (Phase RG3: use params)
            if abs(params.push_pull) > 1e-6:
                beat_position = apply_microtiming(
                    beat_position,
                    groove_profile=params.groove,
                    push_pull_amount=params.push_pull,
                    rng=rng,
                )

            # Determine articulation flags
            is_accent = hit_idx in pattern.accents
            is_palm_mute = hit_idx in pattern.palm_mutes

            # Determine note duration (use next hit or end of bar)
            next_hit_beat = bar_start_beat + beats_per_bar
            for next_hit_idx in pattern.hits:
                if next_hit_idx > hit_idx:
                    next_hit_beat = bar_start_beat + (next_hit_idx / pattern.subdivision)
                    break
            duration = next_hit_beat - beat_position
            duration = min(duration, 1.0)  # Max sustain
            # Never ring past the active chord's span
            duration = max(0.05, min(duration, active_chord_slot.end_beat - beat_position))

            # Sustain cut: occasionally shorten to a percussive stab (stab vs ring)
            if params.sustain_cut_rate > 0.0 and rng.random() < params.sustain_cut_rate:
                duration = rng.uniform(0.08, 0.18)  # Short stab (kick-drum-tight)

            # Phase RG6: Quantize duration to grid when humanization is disabled
            if params.humanize_timing <= 0.0:
                duration = quantize_to_subdivision(duration, pattern.subdivision)

            # Determine strum direction early (needed for partial upstroke filtering)
            strum_direction = "down"
            if pattern.strum_directions and hit_idx in pattern.hits:
                hit_list_idx = pattern.hits.index(hit_idx)
                if hit_list_idx < len(pattern.strum_directions):
                    strum_direction = pattern.strum_directions[hit_list_idx]

            # Partial upstroke: real pick motion catches fewer strings on the way up.
            # Trim to the highest strings so upstrokes sound lighter than downstrokes.
            hit_pitches = list(voicing.pitches)
            if strum_direction == "up" and len(hit_pitches) > 2 and rng.random() < 0.65:
                keep = max(2, len(hit_pitches) - rng.randint(1, 2))
                hit_pitches = sorted(hit_pitches)[-keep:]  # Keep highest-pitched strings

            # Phase RG4: Create articulated chord with palm-mute, chucks, velocity shaping
            articulated_notes = create_chord_articulation(
                pitches=hit_pitches,
                base_velocity=base_velocity,
                base_duration=duration,
                beat_position=beat_offset,
                beats_per_bar=beats_per_bar,
                is_palm_mute=is_palm_mute,
                is_accent=is_accent,
                palm_mute_amount=params.palm_mute,
                accent_strength=params.accent_strength,
                downbeat_boost=params.downbeat_boost,
                chuck_rate=params.chuck_rate,
                rng=rng,
            )

            # Phase RG4: Apply strum spread based on direction (already determined above)

            # Phase RG6: Pass humanize_timing to strum spread for grid stability
            articulated_notes_with_spread = apply_strum_spread(
                notes=articulated_notes,
                strum_direction=strum_direction,
                strum_ms=params.strum_ms,
                humanize_amount=params.humanize_timing,
                rng=rng,
                bpm=song_bpm,
            )

            # Phase RG4/RG6: Apply humanization and add to timeline
            for note, strum_offset in articulated_notes_with_spread:
                # Phase RG6: Quantize note duration to grid when humanization is disabled
                final_duration = note.duration
                if params.humanize_timing <= 0.0:
                    final_duration = quantize_to_subdivision(final_duration, pattern.subdivision)

                # Humanize velocity
                final_velocity = humanize_velocity(
                    velocity=note.velocity,
                    amount=params.humanize_velocity,
                    rng=rng,
                )

                # Humanize timing (strum offset is already applied).
                # NOTE: the hit position (beat_position) is already grid
                # aligned; the intra-strum offset must NEVER be quantized —
                # quantizing it to the subdivision grid collapsed strums into
                # block chords whenever humanize_timing was 0.
                final_beat_offset = humanize_timing(
                    beat_position=strum_offset,
                    amount=params.humanize_timing,
                    rng=rng,
                )

                # Add note to timeline
                timeline.add_note(
                    start_beat=section_start_beat + beat_position + final_beat_offset,
                    duration_beats=final_duration,
                    pitch=note.pitch,
                    velocity=final_velocity,
                )
                events_count += 1

    if logger:
        logger.debug(
            "Section '%s': added %d rhythm guitar events (intensity=%.2f, style=%s, density=%.2f)",
            section.id,
            events_count,
            intensity,
            params.style,
            params.density,
        )


def _render_legacy_rhythm_guitar(
    cfg: RootConfig,
    section: SectionConfig,
    instrument_name: str,
    instrument_cfg,
    harmony_plan: Optional[HarmonySectionPlan],
    rhythm_grid: RhythmGrid,
    section_start_beat: float,
    timeline: InstrumentTimeline,
    rng: Optional[random.Random],
    logger: logging.Logger,
    coordinated_accent_beats: Optional[set] = None,  # Rule 4: drum accent positions
) -> None:
    """Legacy rhythm guitar rendering using rhythm grid cells (original implementation)."""
    if logger is None:
        logger = logging.getLogger("produzre.rhythm")

    # Validate instrument configuration passed from the engine dispatcher.
    if instrument_cfg is None or getattr(instrument_cfg, "enabled", True) is False:
        logger.debug(
            "Section '%s': instrument '%s' disabled or missing; skipping.",
            section.id,
            instrument_name,
        )
        return

    if harmony_plan is None or not harmony_plan.chord_slots:
        logger.debug("Section '%s': no harmony plan; skipping rhythm guitar.", section.id)
        return

    if logger:
        numerals_summary = " ".join(cs.numeral for cs in harmony_plan.chord_slots)
        logger.debug(
            "Section '%s': rhythm guitar harmony numerals: %s",
            section.id,
            numerals_summary,
        )

    # NOTE: the legacy renderer plays bare power chords built from the chord
    # root; it deliberately does NOT pre-generate CAGED voicings (a previous
    # version computed and logged them without ever using them, burning RNG
    # state and logging misleading voicing names).

    # Phase RG4: Use extracted parameter resolution (refactoring)
    # Resolve all legacy guitar parameters via the refactored module
    params = resolve_legacy_guitar_params(section, instrument_cfg, rhythm_grid)

    # Rule 4: Build quantised accent set for O(1) lookup in the per-beat loop.
    accent_beat_set: set = (
        {round(b, 2) for b in coordinated_accent_beats}
        if coordinated_accent_beats else set()
    )

    # Extract all values from params object for use in legacy rendering
    intensity = params.intensity
    base_vel = params.base_vel
    voicing = params.voicing
    offset_beats = params.offset_beats
    density_scale = params.density_scale
    mute_amount = params.mute_amount
    sustain_mode = params.sustain_mode
    sustain_duration = params.sustain_duration
    strum_amt = params.strum_amt
    strum_beats = params.strum_beats
    strum_dir = params.strum_dir
    playstyle = params.playstyle
    strum_style = params.strum_style
    play_pattern = params.play_pattern
    retrigger = params.retrigger
    reattack_vel = params.reattack_vel
    reattack_dur = params.reattack_dur
    reattack_strum = params.reattack_strum
    hit_strategy = params.hit_strategy
    stab_beats = params.stab_beats
    voice_leading = params.voice_leading
    vl_lo = params.vl_lo
    vl_hi = params.vl_hi

    # Rhythm grid basics (needed for rendering logic)
    bpb = rhythm_grid.beats_per_bar
    step_beats = getattr(rhythm_grid, "step_beats", 1.0)
    eps = 1e-6
    cells = rhythm_grid.cells

    # R2-C: play_pattern presets define their own (sub-beat) hit positions.
    # The shared rhythm grid is usually quarter-note resolution, so patterns
    # like "syncopated"/"offbeat"/"gallop" would otherwise match zero cells.
    pattern_positions = _pattern_positions_for_bar(play_pattern, bpb)
    if pattern_positions is not None and not params.user_retrigger_specified:
        # The preset's positions ARE the intended hits; the default "beat"
        # retrigger gate would silence every sub-beat hit.
        retrigger = "all"
    if pattern_positions is not None:
        total_beats = float(getattr(rhythm_grid, "total_beats", 0.0) or 0.0)
        cell_beats = []
        bar0 = 0.0
        while bar0 < total_beats - eps:
            for pos in pattern_positions:
                lb = bar0 + pos
                if lb < total_beats - eps:
                    cell_beats.append(lb)
            bar0 += bpb
        # Effective step = smallest gap between pattern hits (for durations).
        gaps = [b - a for a, b in zip(cell_beats, cell_beats[1:]) if b - a > eps]
        if gaps:
            step_beats = max(0.1, min(gaps))
    else:
        cell_beats = [cell.beat for cell in cells]

    # Classify intensity into bands to control density.
    eff_intensity = _clamp(intensity * density_scale, 0.0, 2.0)
    if eff_intensity <= 0.33:
        intensity_band = "low"
    elif eff_intensity <= 0.66:
        intensity_band = "mid"
    else:
        intensity_band = "high"

    # Adjust base velocity slightly for mute/section feel.
    base_vel = int(base_vel * _lerp(1.0, 0.85, mute_amount))

    events_before = len(timeline.events)

    # Walk the rhythm grid (or synthesized pattern positions) and place
    # power-chord hits according to intensity and chord.
    last_chord_key: Optional[str] = None
    prev_root_pitch: Optional[int] = None
    for local_beat in cell_beats:  # section-local beat position

        # Find the chord slot that covers this beat.
        cs_for_cell = None
        for cs in harmony_plan.chord_slots:
            if cs.start_beat - eps <= local_beat < cs.end_beat - eps:
                cs_for_cell = cs
                break
        if cs_for_cell is None:
            continue

        beat_in_bar = local_beat % bpb
        is_integer_beat = abs(beat_in_bar - round(beat_in_bar)) < eps
        is_downbeat = abs(beat_in_bar - 0.0) < eps

        # ---- R2-B: optional accent pattern for playstyles ----
        # Used only by 'accented' and future playstyles.
        # Pattern: [accent, normal, light, normal] repeating per bar.
        accent_pattern = [1.25, 1.0, 0.8, 1.0]
        beat_index = int(beat_in_bar) if beat_in_bar >= 0 else 0
        pattern_factor = accent_pattern[beat_index % len(accent_pattern)]

        # Decide whether to place a chord hit at this cell based on intensity band.
        # Synthesized pattern positions ARE the hits — no density gating needed.
        place_note = False
        if pattern_positions is not None:
            place_note = True
        elif intensity_band == "low":
            # Very sparse: hits on bar downbeats only.
            place_note = is_downbeat
        elif intensity_band == "mid":
            # Medium density: hits on all integer beats.
            place_note = is_integer_beat
        else:
            # High density: hit on every rhythm cell.
            place_note = True

        # ---- Phase 1.4: strum_style downbeat/upbeat weighting ----
        # At quarter-note grid resolution, work by beat position within the bar.
        # beat_index 0,2 → beats 1,3 (strong/downbeat side)
        # beat_index 1,3 → beats 2,4 (weak/backbeat/upbeat side)
        if strum_style != "balanced" and pattern_positions is None:
            is_strong_beat = (beat_index % 2 == 0)  # beats 1 & 3 (0-indexed: 0 & 2)
            if strum_style == "downbeat_heavy":
                # Keep only strong beats (1 & 3), suppress backbeat (2 & 4)
                if place_note and not is_strong_beat:
                    place_note = False
            elif strum_style == "upbeat_heavy":
                # Force backbeat (2 & 4), suppress strong beats (1 & 3)
                if is_strong_beat:
                    place_note = False
                else:
                    place_note = True

        # ---- R2-C: Apply rhythmic pattern preset (if any) ----
        # Only as a filter when iterating raw grid cells; synthesized pattern
        # positions already encode the preset's hits.
        if play_pattern and pattern_positions is None:
            place_note = _apply_rhythmic_pattern(play_pattern, beat_in_bar, place_note)

        if not place_note:
            continue

        # R3-V3: Chord-change awareness / retrigger gating.
        chord_key = f"{cs_for_cell.start_beat:.3f}:{cs_for_cell.end_beat:.3f}:{cs_for_cell.numeral}"
        chord_changed = (last_chord_key is None) or (chord_key != last_chord_key)
        is_reattack = (not chord_changed) and (last_chord_key is not None)

        # R3-V6: Strategy gating.
        # Sustain: only hit on chord change.
        if hit_strategy == "sustain" and not chord_changed:
            continue

        allow = True
        if retrigger == "all":
            allow = True
        elif retrigger == "chord":
            allow = chord_changed
        elif retrigger == "none":
            allow = chord_changed  # only first + chord changes
        elif retrigger == "bar":
            allow = chord_changed or is_downbeat
        elif retrigger == "beat":
            allow = chord_changed or is_integer_beat
        elif retrigger == "accent":
            # If a pattern is set, treat it as an accent mask; otherwise downbeat.
            if play_pattern:
                allow = chord_changed or _apply_rhythmic_pattern(play_pattern, beat_in_bar, is_downbeat)
            else:
                allow = chord_changed or is_downbeat

        if not allow:
            continue

        # Determine the rhythm guitar root for the active chord.
        root_midi = _rhythm_root_for_numeral(cfg, section, cs_for_cell.numeral, instrument_cfg)

        # R3-V5: Octave-shift roots to minimize jumps across chord changes.
        # Keep within a guitar-friendly rhythm range.
        if voice_leading and prev_root_pitch is not None:
            root_midi = _voice_lead_root(
                root_midi,
                prev_root_pitch,
                vl_lo,
                vl_hi,
                key=f"{section.id}:{instrument_name}:vl:{cs_for_cell.numeral}:{chord_key}",
            )
        else:
            root_midi = max(vl_lo, min(vl_hi, root_midi))

        fifth_midi = root_midi + 7          # power chord fifth above the root
        octave_root = root_midi + 12        # octave above the root

        # Determine chord tone list for optional strumming.
        chord_pitches = [root_midi, fifth_midi]
        if voicing == "open":
            chord_pitches.append(octave_root)

        # Resolve strum direction (alt toggles deterministically per integer beat).
        eff_dir = strum_dir
        if eff_dir == "alt":
            # Alternate per beat using a stable hash.
            pick_up = (_stable_u32(f"{section.id}:{instrument_name}:altstrum:{int(local_beat)}") % 2) == 1
            eff_dir = "up" if pick_up else "down"

        song_beat = section_start_beat + local_beat + offset_beats

        # Constrain duration by the remaining chord span and the rhythm step.
        chord_end = cs_for_cell.end_beat
        remaining_in_chord = max(0.0, chord_end - local_beat)

        # R3-V3: If we're not retriggering on every cell, let hits ring longer by default.
        if retrigger in ("chord", "bar", "beat", "accent", "none"):
            duration = max(0.1, remaining_in_chord)
        else:
            duration = max(0.1, min(step_beats, remaining_in_chord))

        # R3-V6: Strategy duration shaping.
        if hit_strategy == "stabs":
            # Short, percussive stabs.
            target = stab_beats
            if target is None:
                target = min(0.6, step_beats * 0.55)
            duration = max(0.1, min(duration, target, remaining_in_chord))
        elif hit_strategy == "chops":
            # Choppy: shorter re-attacks within the same chord; chord-change hit can ring a bit.
            if is_reattack:
                duration = max(0.1, min(duration, step_beats * 0.55, remaining_in_chord))
            else:
                duration = max(0.1, min(duration, step_beats * 0.95, remaining_in_chord))
        elif hit_strategy == "chug":
            # Chug: keep hits short, even if retriggering frequently.
            duration = max(0.1, min(duration, step_beats * 0.55, remaining_in_chord))
        # sustain is handled by gating + ring-through default above.

        # Phase 4.3: Sustained chord mode override
        if sustain_mode:
            # Override duration with fixed sustain duration (clamped to chord boundaries)
            duration = max(0.1, min(sustain_duration, remaining_in_chord))

        # ---- Voicing logic ----
        # Default: "tight" power chord (root + fifth)
        add_octave = False
        duration_scale = 1.0

        if voicing == "open":
            # Open voicing: add octave and allow slightly longer ring.
            add_octave = True
            duration_scale = 1.25
        elif voicing == "tight":
            # Explicit tight: shorter, more chug-like.
            duration_scale = 0.8
        # else: None or unknown → use defaults (power chord root+5, duration_scale=1.0)

        duration *= duration_scale
        # Ensure we still never exceed the remaining chord span
        duration = max(0.1, min(duration, remaining_in_chord))

        # Start from the section-level base velocity for this hit.
        vel = base_vel

        # ---- Playstyle logic (R2-B extended) ----
        if playstyle == "pmute":
            # Stronger palm-mute effect on weak beats.
            if not is_downbeat:
                duration *= 0.5
                vel = max(25, int(vel * 0.75))
            else:
                duration *= 0.75
                vel = max(30, int(vel * 0.85))

        elif playstyle == "open":
            # Longer ringing for open strums.
            duration *= 1.35

        elif playstyle == "accented":
            # Apply accent pattern per beat.
            vel = int(vel * pattern_factor)

        # ---- R2-D: Velocity curves by intensity band and beat position ----
        if intensity_band == "low":
            # Narrower dynamic range, generally softer.
            vel = int(vel * 0.85)
        elif intensity_band == "mid":
            # Subtle backbeat emphasis on beats 1 and 3 in 4/4,
            # slightly lighter on other integer beats.
            if abs(beat_in_bar - 0.0) < eps or abs(beat_in_bar - 2.0) < eps:
                vel = int(vel * 1.05)
            elif is_integer_beat:
                vel = int(vel * 0.95)
        else:
            # High intensity: offbeats slightly softer to avoid brickwall feel.
            if not is_integer_beat:
                vel = int(vel * 0.9)

        # R3-V1: General mute layer (works with or without explicit playstyle).
        if mute_amount > 0.0:
            if not is_downbeat:
                duration *= _lerp(1.0, 0.55, mute_amount)
                vel = int(vel * _lerp(1.0, 0.78, mute_amount))
            else:
                duration *= _lerp(1.0, 0.70, mute_amount)
                vel = int(vel * _lerp(1.0, 0.85, mute_amount))

        # R3-V4: If this is a retrigger within the same chord, shape it to feel like a re-attack.
        if is_reattack:
            vel = int(vel * reattack_vel)
            duration = duration * reattack_dur

        # Rule 4: Coordinated accent boost — punch harder on drum crash/accent positions.
        if accent_beat_set and round(local_beat, 2) in accent_beat_set:
            vel = int(vel * 1.20)

        # Final clamps for duration and velocity.
        duration = max(0.1, min(duration, remaining_in_chord))
        vel = max(20, min(127, vel))

        # ---- Humanization: natural variation so bars don't sound identical ----
        # Without this every bar produces exactly the same durations and velocities,
        # which is clearly mechanical when listening across multiple bars.
        skip_this_hit = False
        if rng is not None:
            # Velocity humanization: chord-change hits get slightly wider range
            # (the guitarist "digs in" harder on new chords), re-attacks stay subtle.
            vel_jitter = rng.randint(-6, 6) if chord_changed else rng.randint(-4, 4)
            vel = max(20, min(127, vel + vel_jitter))

            # Duration humanization: ±12% so note lengths feel natural, not stamped.
            duration = max(0.1, min(duration * rng.uniform(0.88, 1.12), remaining_in_chord))

            # "Breathe" skip: occasionally silence a non-structural re-attack so the
            # guitar doesn't hammer every beat identically every bar.  Only applies
            # to re-attacks (within same chord) on non-downbeats at high density.
            if is_reattack and not is_downbeat and intensity_band == "high":
                rest_prob = 0.10 + mute_amount * 0.12  # 10–22% based on mute amount
                if rng.random() < rest_prob:
                    skip_this_hit = True

        if not skip_this_hit:
            # R3-V2: Add chord tones, optionally strummed (micro-staggered starts).
            pitches = chord_pitches[:]  # [root, fifth] (+ octave if open)
            if eff_dir == "up":
                pitches = list(reversed(pitches))

            eff_strum_beats = strum_beats
            if is_reattack and eff_strum_beats > 0.0:
                eff_strum_beats = eff_strum_beats * reattack_strum
            offs = _strum_offsets(len(pitches), eff_strum_beats, eff_dir)

            for p, o in zip(pitches, offs):
                start = song_beat + o
                # Ensure the note doesn't extend beyond chord end.
                dur = max(0.1, min(duration, max(0.0, (section_start_beat + chord_end) - start)))
                timeline.add_note(
                    start_beat=start,
                    duration_beats=dur,
                    pitch=p,
                    velocity=vel,
                    channel=None,
                )
        # Always update chord/voice-leading state so subsequent hits see the
        # correct chord-change status even when this hit was silenced.
        last_chord_key = chord_key
        prev_root_pitch = root_midi

    added = len(timeline.events) - events_before
    logger.debug(
        "Section '%s': added %d rhythm guitar events (intensity=%.2f)",
        section.id,
        added,
        intensity,
    )


def _render_rhythm_locked_guitar(
    cfg: RootConfig,
    section: SectionConfig,
    instrument_name: str,
    harmony_plan: Optional[HarmonySectionPlan],
    rhythm_grid: RhythmGrid,
    section_start_beat: float,
    timeline: InstrumentTimeline,
    drum_features,
    instrument_cfg,
    rng,
    logger: logging.Logger,
) -> None:
    """Render rhythm guitar that follows drum groove.

    This mode follows drum rhythm features:
    - Strumming density matches hat density per bar
    - Accents syncopated kick beats
    - Avoids playing during fill windows
    """
    from ...rhythm_features import is_beat_in_fill

    if harmony_plan is None or not harmony_plan.chord_slots:
        logger.debug("Section '%s': no harmony plan; skipping rhythm guitar.", section.id)
        return

    # Extract parameters
    params = {}
    if hasattr(instrument_cfg, "params"):
        params = instrument_cfg.params or {}
    elif isinstance(instrument_cfg, dict):
        params = instrument_cfg.get("params", {})

    # Get configuration values
    if isinstance(params, dict):
        accent_syncopation = params.get("accent_syncopation", True)
        voicing = params.get("voicing", "power_chord")
        octave = params.get("octave", 3)
    else:
        accent_syncopation = getattr(params, "accent_syncopation", True)
        voicing = getattr(params, "voicing", "power_chord")
        octave = getattr(params, "octave", 3)

    # Get intensity
    intensity = None
    if isinstance(instrument_cfg, dict):
        intensity = instrument_cfg.get("intensity")
    elif instrument_cfg is not None:
        intensity = getattr(instrument_cfg, "intensity", None)
    if intensity is None:
        intensity = 0.7

    base_vel = int(75 + intensity * 30)

    # Rhythm features from drums
    syncopation_beats = drum_features.syncopation_beats if accent_syncopation and hasattr(drum_features, "syncopation_beats") else set()
    density_per_bar = drum_features.density_per_bar if hasattr(drum_features, "density_per_bar") else {}

    # Quantised set for robust membership tests (avoids exact-float comparisons)
    syncopation_set = {round(float(b), 2) for b in syncopation_beats}

    events_before = len(timeline.events)

    bpb = rhythm_grid.beats_per_bar
    total_beats = rhythm_grid.total_beats
    num_bars = int(total_beats / bpb) if bpb > 0 else 0

    eps = 1e-6

    # Generate strumming pattern per bar based on hat density
    for bar_idx in range(num_bars):
        bar_start = bar_idx * bpb
        bar_end = bar_start + bpb

        # Get hat density for this bar (events per beat)
        hat_density = density_per_bar.get(bar_idx, 2.0)  # Default: 2 strums per beat

        # Scale strumming pattern based on hat density and intensity
        strums_per_beat = max(1.0, min(4.0, hat_density * intensity))

        # Generate strum beats for this bar. Iterate by index (beat derived
        # as i / strums_per_beat) instead of accumulating floats, which
        # drifted across the bar and broke membership tests.
        n_strums = max(1, int(round(bpb * strums_per_beat)))
        for strum_idx in range(n_strums):
            beat = bar_start + strum_idx / strums_per_beat
            if beat >= bar_end - eps:
                break

            # Skip if in fill window (let drums shine)
            if is_beat_in_fill(beat, drum_features):
                continue

            # Find the chord slot that covers this beat
            cs_for_beat = None
            for cs in harmony_plan.chord_slots:
                if cs.start_beat - eps <= beat < cs.end_beat - eps:
                    cs_for_beat = cs
                    break
            if cs_for_beat is None:
                continue

            # Get rhythm guitar root for this chord
            root_midi = _rhythm_root_for_numeral(cfg, section, cs_for_beat.numeral, instrument_cfg)

            # Apply octave adjustment (octave 3 is default in _rhythm_root_for_numeral)
            octave_offset = (octave - 3) * 12  # 3 is default octave
            root_midi += octave_offset

            # Determine velocity: accent syncopated kicks (rounded membership
            # — exact float equality misses derived beat positions)
            is_syncopated = round(beat, 2) in syncopation_set
            vel = base_vel

            if is_syncopated:
                vel = min(127, vel + 15)  # Accent syncopation

            vel = max(50, min(127, vel + rng.randint(-5, 5)))

            # Duration: short for palm mute, sustained for power chords
            if voicing == "palm_mute":
                duration = 0.15  # Short, staccato
            else:
                duration = min(0.4, 1.0 / strums_per_beat * 0.8)

            # Add chord voicing
            song_beat = section_start_beat + beat

            if voicing == "palm_mute":
                # Palm mute: just root note
                timeline.add_note(
                    start_beat=song_beat,
                    duration_beats=duration,
                    pitch=root_midi,
                    velocity=vel,
                    channel=None,
                )
            else:
                # Power chord: root + fifth
                fifth_midi = root_midi + 7

                # Add root
                timeline.add_note(
                    start_beat=song_beat,
                    duration_beats=duration,
                    pitch=root_midi,
                    velocity=vel,
                    channel=None,
                )

                # Add fifth (slightly quieter)
                timeline.add_note(
                    start_beat=song_beat,
                    duration_beats=duration,
                    pitch=fifth_midi,
                    velocity=vel - 5,
                    channel=None,
                )

    added = len(timeline.events) - events_before
    logger.debug(
        "Section '%s': added %d rhythm-locked guitar events (follow_hats=True, intensity=%.2f)",
        section.id,
        added,
        intensity,
    )
