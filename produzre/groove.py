"""Shared swing and performance timing.

Drums apply timing internally and publish their resolved settings. The
orchestrator applies one matching feel pass to each pitched instrument.
Eighth offbeats move by 0.25 * swing beats; sixteenth e/a positions move by
0.25 * swing_16th. True triplets stay on their own grid. An omitted swing_16th
uses half of swing, while explicit zero disables it.

Positive pocket_ms means behind the beat. Positive push_pull means ahead;
it maps to -100 * push_pull milliseconds, capped at 25 ms in either direction.
Instrument pocket_ms overrides the groove mapping and push_pull.

A config without swing, pocket, push/pull, jitter, or velocity-humanization
indications resolves to no feel pass. Default pockets apply only when a feel
is active. Per-event random choices use stable seeds so repeat builds match.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .rng import stable_seed_int


# Default pocket offsets (milliseconds; positive = behind the beat) applied
# when a groove feel is resolved and the instrument has no explicit
# pocket_ms / push_pull override. Bass sits deepest in the pocket; strummed
# guitars slightly behind; lead and drums on the grid.
DEFAULT_POCKET_MS: Dict[str, float] = {
    "bass": 8.0,
    "rhythm_gtr": 3.0,
    "lead_gtr": 0.0,
    "acoustic_gtr": 3.0,
    "drums": 0.0,
}

# Conversion factor for persona push_pull (dimensionless) -> pocket ms.
# See module docstring for the mapping rationale.
PUSH_PULL_MS_PER_UNIT = 100.0
_POCKET_MS_CLAMP = 25.0

# Engines that already consume their push_pull param internally (drums via
# humanize_events, rhythm_gtr via apply_microtiming). Deriving a pocket from
# push_pull for these would double-apply the offset.
_PUSH_PULL_CONSUMED_INTERNALLY = frozenset({"drums"})

# Half of a 16th-note: events within this window of a 16th grid point are
# classified to that grid point (tolerates strum spread / engine microtiming
# riding on top of a nominal grid position, so a whole strum swings together).
_GRID_SNAP_WINDOW = 0.124

_EPS = 1e-9
_MIN_DURATION = 0.01


@dataclass
class GrooveFeel:
    """A resolved per-section groove feel shared by the whole band.

    Attributes:
        swing: 0..1: 8th offbeats ("&") delayed by ``0.25 * swing`` beats
            (same semantics as the drums engine).
        swing_16th: 0..1: "e"/"a" 16th positions delayed by
            ``0.25 * swing_16th`` beats. Defaults to ``swing * 0.5`` unless
            explicitly set (drum params or song ``groove:`` block).
        pocket_offsets_ms: Per-instrument constant timing offset in
            milliseconds; positive = behind the beat.
        source: Where the feel came from, for logging (e.g. "drums.params",
            "groove_block", "instrument.pocket").
    """

    swing: float = 0.0
    swing_16th: float = 0.0
    pocket_offsets_ms: Dict[str, float] = field(default_factory=dict)
    source: str = "none"


def effective_params_dict(instrument_cfg: Any) -> Dict[str, Any]:
    """Extract the effective engine-params dict from an instrument config.

    Mirrors the engines' own param extraction: orchestrated configs are
    InstrumentConfig dataclasses with params in ``.extra`` (possibly wrapped
    one level under an ``extra`` key by the loader); raw dicts may carry
    ``params`` or ``extra``.
    """
    params: Any = {}
    if instrument_cfg is None:
        return {}
    if isinstance(instrument_cfg, dict):
        params = instrument_cfg.get("params") or instrument_cfg.get("extra") or {}
    elif getattr(instrument_cfg, "params", None):
        params = instrument_cfg.params
    elif hasattr(instrument_cfg, "extra"):
        params = instrument_cfg.extra or {}
    if isinstance(params, dict) and isinstance(params.get("extra"), dict) and (
        "params" not in params
    ):
        params = params["extra"]
    return params if isinstance(params, dict) else {}


def _optional_float(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def swing_offset(beat: float, swing: float, swing_16th: float, tolerance: float = 1e-6) -> float:
    """Delay straight subdivisions; already-triplet attacks keep their timing."""
    triplet = round(beat * 3) / 3
    if abs(triplet - round(triplet)) > 1e-6 and abs(beat - triplet) < min(tolerance, 0.025):
        return 0.0
    grid = round(beat * 4) / 4
    if abs(beat - grid) > tolerance:
        return 0.0
    frac = grid % 1
    return 0.25 * (swing if frac == 0.5 else swing_16th if frac in (0.25, 0.75) else 0.0)


def _nonzero_float(value: Any) -> Optional[float]:
    """Return float(value) if it is set and nonzero, else None.

    Zero values count as "no groove indication" (many personas ship
    ``swing: 0.0`` / ``push_pull: 0.0`` explicitly).
    """
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if f != 0.0 else None


def resolve_groove_feel(
    cfg: Any,
    section: Any,
    drum_params: Optional[Dict[str, Any]],
    instrument_params: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Optional[GrooveFeel]:
    """Resolve the shared groove feel for one section.

    Swing precedence (later wins):
        song-level ``groove:`` block  <  resolved drums params
    where ``drum_params`` should already be the drums engine's final merged
    params (persona < recipe < global < section), so recipe/persona swing and
    section ``drums: {params: {swing: X}}`` are both honoured.

    Pocket precedence per instrument (first match wins):
        explicit ``pocket_ms`` instrument param
        > ``groove:`` block ``pocket_ms: {instrument: ms}``
        > nonzero persona ``push_pull`` (mapped; skipped for engines that
          consume push_pull internally)
        > :data:`DEFAULT_POCKET_MS`

    Returns None when there is no groove indication anywhere (the no-op
    default: see module docstring).

    Args:
        cfg: Root config (the song-level ``groove:`` block is read from
            ``cfg.raw`` since the parser does not model it).
        section: Section config (currently only used for context; the section
            drums params are expected to be merged into ``drum_params``).
        drum_params: The drums engine's resolved humanize params for this
            section (or the merged drums instrument params when the engine
            did not run).
        instrument_params: Mapping of instrument name -> effective params
            dict for every instrument in the section (used for pocket
            overrides and groove-indication detection).

    Returns:
        GrooveFeel or None.
    """
    _ = section  # context only; section drums params arrive via drum_params
    drum_params = drum_params or {}
    instrument_params = instrument_params or {}

    groove_block: Dict[str, Any] = {}
    raw = getattr(cfg, "raw", None)
    if isinstance(raw, dict):
        gb = raw.get("groove")
        if isinstance(gb, dict):
            groove_block = gb

    # --- swing (groove block < drums chain) ---
    swing: Optional[float] = None
    source = "none"
    gb_swing = _optional_float(groove_block.get("swing"))
    if gb_swing is not None:
        swing = gb_swing
        source = "groove_block"
    drums_swing = _optional_float(drum_params.get("swing"))
    if drums_swing is not None:
        swing = drums_swing
        source = str(drum_params.get("source") or "drums.params")

    # --- swing_16th (explicit nonzero only; default = swing * 0.5) ---
    swing_16th = _optional_float(groove_block.get("swing_16th"))
    drums_swing_16th = _optional_float(drum_params.get("swing_16th"))
    if drums_swing_16th is not None:
        swing_16th = drums_swing_16th

    indicated = bool(swing or swing_16th) or any(
        _nonzero_float(params.get(key)) is not None
        for name, params in instrument_params.items() if name != "drums"
        for key in ("timing_jitter_ms", "velocity_humanize")
    )

    # --- per-instrument pockets ---
    gb_pockets = groove_block.get("pocket_ms")
    gb_pockets = gb_pockets if isinstance(gb_pockets, dict) else {}

    pocket_offsets: Dict[str, float] = {}
    pocket_source: Optional[str] = None
    instruments = set(instrument_params) | set(gb_pockets)
    for inst in sorted(instruments):
        params = instrument_params.get(inst, {}) or {}
        explicit = params.get("pocket_ms")
        gb_val = gb_pockets.get(inst)
        push_pull = (
            None
            if inst in _PUSH_PULL_CONSUMED_INTERNALLY
            else _nonzero_float(params.get("push_pull"))
        )
        if explicit is not None:
            try:
                pocket_offsets[inst] = float(explicit)
                indicated = True
                pocket_source = pocket_source or "instrument.pocket_ms"
                continue
            except (TypeError, ValueError):
                pass
        if gb_val is not None:
            try:
                pocket_offsets[inst] = float(gb_val)
                indicated = True
                pocket_source = pocket_source or "groove_block.pocket_ms"
                continue
            except (TypeError, ValueError):
                pass
        if push_pull is not None:
            ms = -push_pull * PUSH_PULL_MS_PER_UNIT
            pocket_offsets[inst] = max(-_POCKET_MS_CLAMP, min(_POCKET_MS_CLAMP, ms))
            indicated = True
            pocket_source = pocket_source or "instrument.push_pull"
            continue
        # Default pocket: only meaningful when a feel actually resolves.
        pocket_offsets[inst] = DEFAULT_POCKET_MS.get(inst, 0.0)

    if not indicated:
        return None

    swing_f = swing or 0.0
    if source == "none" and pocket_source is not None:
        source = pocket_source
    pocket_offsets["drums"] = 0.0  # drums are the reference clock by definition

    return GrooveFeel(
        swing=max(0.0, min(1.0, swing_f)),
        swing_16th=max(0.0, min(1.0, swing_16th if swing_16th is not None else swing_f * 0.5)),
        pocket_offsets_ms=pocket_offsets,
        source=source,
    )


def _event_key(ev: Any, rel_beat: float) -> str:
    """Stable per-event key so jitter/velocity RNG streams survive event
    insertion/removal elsewhere in the section."""
    return (
        f"rel={rel_beat:.6f}|dur={float(ev.duration_beats):.6f}"
        f"|pitch={int(ev.pitch)}|vel={int(ev.velocity)}"
    )


def apply_feel(
    events: List[Any],
    feel: GrooveFeel,
    instrument: str,
    bpm: float,
    beats_per_bar: float,
    rng_seed: int,
    *,
    section_start_beat: float = 0.0,
    timing_jitter_ms: float = 0.0,
    velocity_humanize: float = 0.0,
) -> None:
    """Apply a resolved groove feel to timeline events in place.

    Shifts events off the quantized grid: 8th offbeats by ``0.25 * swing``
    beats, 16th "e"/"a" positions by ``0.25 * swing_16th`` beats, plus the
    instrument's constant pocket offset (ms -> beats via bpm) and optional
    per-event timing jitter / velocity humanization.

    Guarantees:
        - Never shifts a note before ``section_start_beat``.
        - Constant shifts (swing/pocket) preserve relative order; jitter may
          reorder only within its window.
        - Durations shrink where needed so notes never cross the next
          same-pitch note.
        - Pure no-op (returns immediately) when every component is zero.
        - Deterministic: jitter/velocity use per-event RNGs derived from
          ``rng_seed`` + stable event keys, not shared RNG state.

    Args:
        events: The newly added NoteEvent objects for this instrument+section
            (mutated in place). Must be exactly the events of one section so
            swing classification and the section-start clamp are correct.
        feel: The resolved groove feel for the section.
        instrument: Instrument name (selects the pocket offset).
        bpm: Song tempo (ms -> beats conversions).
        beats_per_bar: Section meter (kept for symmetry/diagnostics; swing
            classification works on the quarter-beat fraction, which is
            meter-proof exactly like the drums engine).
        rng_seed: Stable seed material for this (section, instrument) scope.
        section_start_beat: Song-relative section start (clamp floor).
        timing_jitter_ms: Per-event random jitter amount (+/- ms).
        velocity_humanize: 0..1: +/- fraction of nominal velocity noise.
    """
    _ = beats_per_bar
    if not events:
        return

    bpm = float(bpm) if bpm and bpm > 0 else 0.0
    beats_per_ms = (bpm / 60000.0) if bpm > 0 else 0.0

    swing_shift_8th = 0.25 * float(feel.swing)
    swing_shift_16th = 0.25 * float(feel.swing_16th)
    pocket_beats = float(feel.pocket_offsets_ms.get(instrument, 0.0)) * beats_per_ms
    jitter_beats = max(0.0, float(timing_jitter_ms)) * beats_per_ms
    vel_amount = max(0.0, float(velocity_humanize))

    if (
        swing_shift_8th == 0.0
        and swing_shift_16th == 0.0
        and pocket_beats == 0.0
        and jitter_beats == 0.0
        and vel_amount == 0.0
    ):
        return  # exact no-op: do not touch timings or durations

    moved = False
    for ev in events:
        rel = float(ev.start_beat) - float(section_start_beat)
        key = _event_key(ev, rel)

        shift = pocket_beats

        shift += swing_offset(rel, feel.swing, feel.swing_16th, _GRID_SNAP_WINDOW)

        if jitter_beats > 0.0:
            rt = random.Random(stable_seed_int("groove.jitter", rng_seed, key))
            shift += rt.uniform(-jitter_beats, jitter_beats)

        if shift != 0.0:
            new_start = float(ev.start_beat) + shift
            if new_start < float(section_start_beat):
                new_start = float(section_start_beat)
            if new_start != ev.start_beat:
                ev.start_beat = new_start
                moved = True

        if vel_amount > 0.0:
            rv = random.Random(stable_seed_int("groove.velocity", rng_seed, key))
            delta = max(1, int(round(abs(int(ev.velocity)) * vel_amount)))
            v = int(ev.velocity) + rv.randint(-delta, delta)
            ev.velocity = max(1, min(127, v))

    if not moved:
        return

    # Shrink durations so shifted notes never cross the next same-pitch note.
    by_pitch: Dict[int, List[Any]] = {}
    for ev in events:
        by_pitch.setdefault(int(ev.pitch), []).append(ev)
    for evs in by_pitch.values():
        if len(evs) < 2:
            continue
        evs.sort(key=lambda e: float(e.start_beat))
        for cur, nxt in zip(evs, evs[1:]):
            gap = float(nxt.start_beat) - float(cur.start_beat)
            if float(cur.duration_beats) > gap - _EPS:
                cur.duration_beats = max(_MIN_DURATION, gap)
