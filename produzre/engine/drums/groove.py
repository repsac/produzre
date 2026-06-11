"""Drum groove scaffolding for the Produzre drums engine.

This module is intentionally *pure* (no I/O, no MIDI writing). It provides:

- A canonical internal step grid (default 16 steps per bar)
- Helpers to map meter (beats-per-bar) to step durations
- A small, declarative groove-template system

The groove template describes *what* to play (e.g., hats on 8ths, backbeat on 2&4,
extra kick syncopation). The drums engine decides *how* to humanize and place
those events into a timeline.

Determinism rule:
All stochastic decisions must be driven by the section RNG passed down from the
engine entrypoint; this module must not use global randomness.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Set, Tuple



DEFAULT_STEPS_PER_BAR = 16

# Internal grid convention (meter support):
#
# Produzre expresses musical time in quarter-note beats everywhere
# (`Meter.beats_per_bar` returns *quarter-note* beats per bar: 4/4 -> 4.0,
# 3/4 -> 3.0, 6/8 -> 3.0, 7/8 -> 3.5). The drum grid is therefore defined as
# **4 steps per quarter-note beat** — every step is one 16th note
# (0.25 beats), regardless of meter:
#
#   steps_per_bar = round(beats_per_bar * 4)   # 16 in 4/4, 12 in 3/4 & 6/8
#
# Consequence: compound meters such as 6/8 are normalized to 3.0 quarter
# beats per bar before they reach the drums engine, so the engine cannot
# distinguish 6/8 from 3/4 — both render on a 12-step bar of 16th notes.
STEPS_PER_QUARTER_BEAT = 4


def steps_per_bar_default() -> int:
    """Return the canonical internal groove resolution (steps per bar, 4/4).

    Produzre standardizes drum grooves on a 16th-note grid: 4 steps per
    quarter-note beat. This constant is the 4/4 value (16). For other meters
    use :func:`steps_per_bar_for_meter`.
    """

    return DEFAULT_STEPS_PER_BAR


def steps_per_bar_for_meter(beats_per_bar: float) -> int:
    """Return the internal step-grid resolution for a meter.

    The grid is always 4 steps per quarter-note beat (one 16th note per step,
    step duration == 0.25 beats):

        4/4 (beats_per_bar=4.0)  -> 16 steps
        3/4 (beats_per_bar=3.0)  -> 12 steps
        6/8 (beats_per_bar=3.0)  -> 12 steps (normalized by Meter.beats_per_bar)
        7/8 (beats_per_bar=3.5)  -> 14 steps

    Args:
        beats_per_bar: Quarter-note beats per bar (see `Meter.beats_per_bar`).

    Returns:
        Steps per bar (at least 1).
    """

    try:
        bpb = float(beats_per_bar)
    except Exception:
        bpb = 4.0
    if bpb <= 0.0:
        bpb = 4.0
    return max(1, int(round(bpb * STEPS_PER_QUARTER_BEAT)))


def step_beats(beats_per_bar: float, *, steps_per_bar: int) -> float:
    """Return the beat-length of one step in the internal grid."""

    spb = max(1, int(steps_per_bar))
    bpb = float(beats_per_bar)
    return bpb / float(spb)


def step_index_in_bar(beat_in_bar: float, beats_per_bar: float, *, steps_per_bar: int) -> int:
    """Quantize a beat position within a bar to the nearest step index.

    Args:
        beat_in_bar: Beat offset within the bar (0.0 == bar downbeat).
        beats_per_bar: Meter beats per bar for this section.
        steps_per_bar: Internal grid resolution.

    Returns:
        Step index in [0, steps_per_bar-1].

    Notes:
        We clamp the result to avoid producing step == steps_per_bar at the bar
        boundary due to rounding.
    """

    sb = step_beats(beats_per_bar, steps_per_bar=steps_per_bar)
    if sb <= 0.0:
        return 0

    i = int(round(float(beat_in_bar) / sb))
    return max(0, min(int(steps_per_bar) - 1, i))


def hat_steps_for_mode(hat_mode: str, *, steps_per_bar: int) -> Set[int]:
    """Return the set of step indices that should place a top cymbal.

    hat_mode options:
        - "16th": every step
        - "8th": every 2 steps
        - "quarter": every 4 steps

    Unknown values fall back to "8th".
    """

    spb = max(1, int(steps_per_bar))
    mode = (hat_mode or "").strip().lower()

    if mode == "16th":
        return set(range(0, spb))
    if mode == "quarter":
        return set(range(0, spb, 4))

    # Default/fallback: 8ths
    return set(range(0, spb, 2))


@dataclass(frozen=True)
class GrooveTemplate:
    """Declarative description of a drum groove.

    The template uses step indices on the internal grid to indicate where events
    should be placed. The engine may still probabilistically add/remove events
    (e.g., kick_extra_rate, ghost_rate) using a deterministic RNG.

    Attributes:
        hat_mode: "quarter" | "8th" | "16th".
        use_ride: If True, the engine should use ride as the top cymbal.
        half_time: If True, the engine should bias toward half-time backbeat.
        kick_base: Step indices where kicks should always occur.
        kick_extra_rate: Probability of adding extra kicks at eligible syncopation steps.
        double_kick_rate: Probability of adding double-kick near bar endings.
        snare_backbeat_steps: Step indices for main snare hits.
        ghost_rate: Probability of adding snare ghost notes at ghost_steps.
        ghost_steps: Step indices eligible for ghost notes.
        open_hat_rate: Probability of opening hat on an "&" step (engine-defined).
        crash_start: Whether to crash on the section downbeat.
        crash_phrase_end_rate: Probability of a crash at the start of the last bar.
    """

    hat_mode: str = "8th"
    use_ride: bool = False
    half_time: bool = False

    kick_base: Tuple[int, ...] = (0,)
    kick_extra_rate: float = 0.0
    double_kick_rate: float = 0.0

    snare_backbeat_steps: Tuple[int, ...] = (4, 12)

    ghost_rate: float = 0.0
    ghost_steps: Tuple[int, ...] = (7, 15)

    open_hat_rate: float = 0.0

    crash_start: bool = False
    crash_phrase_end_rate: float = 0.0



def _classify_intensity(x: float) -> str:
    """Map an intensity value into a small band label."""

    try:
        v = float(x)
    except Exception:
        v = 0.0

    if v >= 0.75:
        return "high"
    if v >= 0.35:
        return "mid"
    return "low"


# Helper to resolve groove id for a section, given section type/intensity/params.
def resolve_groove_id(
    *,
    section_type: str,
    intensity: float,
    params: Mapping[str, object] | None = None,
) -> str:
    """Resolve the effective drum groove id for a section.

    Precedence:
        1) Explicit override in params: `groove` or `groove_id`
        2) A predictable default based on section type + intensity

    This keeps *selection policy* co-located with groove definitions, so the
    package entrypoint can remain thin and orchestration-focused.

    Args:
        section_type: Section type label (e.g., "verse", "chorus", "bridge", "solo").
        intensity: 0..1 scalar that biases toward more/less busy grooves.
        params: Optional instrument params mapping for explicit overrides.

    Returns:
        A groove id string suitable for `groove_template(...)`.
    """

    p = params or {}

    # Explicit override.
    explicit = (str(p.get("groove") or "").strip() or str(p.get("groove_id") or "").strip())
    if explicit:
        return explicit

    st = (section_type or "").strip().lower()

    # Normalize common numbered/typed forms like "verse1", "chorus2", etc.
    if st.startswith("chorus"):
        return "chorus_hat_dense" if float(intensity) >= 0.7 else "chorus_hat"
    if st.startswith("pre"):
        return "prechorus_drive" if float(intensity) >= 0.7 else "prechorus_light"
    if st.startswith("bridge"):
        return "bridge_sparse" if float(intensity) < 0.6 else "bridge_groove"
    if st.startswith("solo"):
        return "solo_ride" if float(intensity) >= 0.7 else "solo_hat"

    # Default: verses.
    if float(intensity) >= 0.7:
        return "verse_drive"
    if float(intensity) >= 0.5:
        return "verse_groove"
    return "verse_light"


def groove_template(
    groove_id: str,
    *,
    section_type: str,
    intensity: float,
    beats_per_bar: float = 4.0,
    **_: object,
) -> "GrooveTemplate":
    """Return a groove template for a given groove id.

    This function produces a deterministic template (no RNG). Any variability is
    applied later by the engine using a seeded RNG.

    Args:
        groove_id: Selected groove name/id (e.g., "verse_groove").
        beats_per_bar: Section meter beats per bar.
        intensity: 0..1 intensity scalar.

    Returns:
        GrooveTemplate for the engine to interpret.
    """

    gid = (groove_id or "").strip().lower()
    band = _classify_intensity(float(intensity))

    try:
        bpb = float(beats_per_bar)
    except Exception:
        bpb = 4.0
    if bpb <= 0.0:
        bpb = 4.0

    spb = steps_per_bar_for_meter(bpb)

    def step_at(beat: float) -> int:
        return step_index_in_bar(beat, bpb, steps_per_bar=spb)

    def steps_at(*beats: float) -> Tuple[int, ...]:
        """Map beat offsets onto step indices, DROPPING out-of-bar positions.

        Positions at or beyond the bar length are dropped (not clamped onto
        the last step), so 4/4-shaped templates degrade gracefully in shorter
        meters instead of stacking hits on the final 16th.
        """

        return tuple(step_at(b) for b in beats if 0.0 <= float(b) < bpb - 1e-9)

    # Meter-aware backbeats (beat offsets within the bar; 0.0 == downbeat).
    # Convention (beats are quarter-note beats, see steps_per_bar_for_meter):
    #   - bpb >= 4 (4/4, 5/4, 7/4, ...): classic backbeat on beats 2 and 4.
    #   - bpb == 6 (6/4, or 6/8 expressed as 6 quarter beats): snare on beat 4,
    #     the start of the second 3-beat group (second dotted-quarter group).
    #   - bpb < 4 (3/4, 6/8-normalized 3.0, 2/4): snare on beat 2 only.
    # Note: Meter.beats_per_bar normalizes 6/8 to 3.0 quarter beats, so 6/8
    # normally takes the "beat 2" branch; the bpb==6 case only fires when the
    # config supplies six quarter beats per bar.
    if abs(bpb - 6.0) < 1e-6:
        backbeat_offsets: Tuple[float, ...] = (3.0,)
    elif bpb >= 4.0 - 1e-6:
        backbeat_offsets = (1.0, 3.0)
    else:
        backbeat_offsets = (1.0,)

    snare_backbeats = steps_at(*backbeat_offsets)

    # Common ghost placements: the 'a' (last 16th) of each backbeat's beat.
    # Out-of-bar positions are dropped (e.g. 3.75 in 3/4).
    default_ghosts = steps_at(*(off + 0.75 for off in backbeat_offsets))

    # Defaults.
    tpl = GrooveTemplate(
        hat_mode="8th",
        use_ride=False,
        half_time=False,
        kick_base=steps_at(0.0),
        kick_extra_rate=0.0,
        double_kick_rate=0.0,
        snare_backbeat_steps=snare_backbeats,
        ghost_rate=0.0,
        ghost_steps=default_ghosts,
        open_hat_rate=0.0,
        crash_start=False,
        crash_phrase_end_rate=0.0,
    )

    # --- Section archetypes ---

    # Choruses: bigger, more motion.
    if gid in ("chorus_hat", "chorus_hat_dense", "chorus_ride"):
        hat_mode = "16th" if gid == "chorus_hat_dense" else "8th"
        use_ride = (gid == "chorus_ride")

        kick_extra = 0.08 if band == "low" else 0.15 if band == "mid" else 0.25
        ghost = 0.10 if band == "low" else 0.20 if band == "mid" else 0.25
        double_kick = 0.0 if band != "high" else 0.12

        # A common driving chorus kick (1 + "& of 2" + 3).
        kick_base = steps_at(0.0, 1.5, 2.0)

        return GrooveTemplate(
            hat_mode=hat_mode,
            use_ride=use_ride,
            half_time=False,
            kick_base=kick_base,
            kick_extra_rate=kick_extra,
            double_kick_rate=double_kick,
            snare_backbeat_steps=snare_backbeats,
            ghost_rate=ghost,
            ghost_steps=default_ghosts,
            open_hat_rate=0.10 if band == "low" else 0.20,
            crash_start=True,
            crash_phrase_end_rate=0.10 if band != "high" else 0.20,
        )

    # Solos: ride timekeeping, steady.
    if gid in ("solo_hat", "solo_ride"):
        use_ride = (gid == "solo_ride")
        kick_extra = 0.06 if band == "low" else 0.12 if band == "mid" else 0.18
        ghost = 0.08 if band == "low" else 0.12 if band == "mid" else 0.18
        double_kick = 0.0 if band != "high" else 0.10

        return GrooveTemplate(
            hat_mode="8th",
            use_ride=use_ride,
            half_time=False,
            kick_base=steps_at(0.0, 2.0),
            kick_extra_rate=kick_extra,
            double_kick_rate=double_kick,
            snare_backbeat_steps=snare_backbeats,
            ghost_rate=ghost,
            ghost_steps=default_ghosts,
            open_hat_rate=0.10,
            crash_start=True,
            crash_phrase_end_rate=0.10,
        )

    # Pre-chorus: build energy.
    if gid in ("prechorus_light", "prechorus_build", "prechorus_drive"):
        hat_mode = "8th" if gid == "prechorus_light" else "16th"
        kick_extra = 0.05 if gid == "prechorus_light" else 0.10 if gid == "prechorus_build" else 0.18
        ghost = 0.06 if gid == "prechorus_light" else 0.12

        kick_base = (
            steps_at(0.0, 2.0)
            if gid == "prechorus_light"
            else steps_at(0.0, 1.0, 2.0)
        )

        return GrooveTemplate(
            hat_mode=hat_mode,
            use_ride=False,
            half_time=False,
            kick_base=kick_base,
            kick_extra_rate=kick_extra,
            double_kick_rate=0.08 if (gid == "prechorus_drive" and band == "high") else 0.0,
            snare_backbeat_steps=snare_backbeats,
            ghost_rate=ghost,
            ghost_steps=default_ghosts,
            open_hat_rate=0.06 if gid != "prechorus_light" else 0.03,
            crash_start=False,
            crash_phrase_end_rate=0.05,
        )

    # Bridges: pull back.
    if gid in ("bridge_sparse", "bridge_groove"):
        return GrooveTemplate(
            hat_mode="quarter" if gid == "bridge_sparse" else "8th",
            use_ride=False,
            half_time=False,
            kick_base=steps_at(0.0) if gid == "bridge_sparse" else steps_at(0.0, 2.0),
            kick_extra_rate=0.02 if gid == "bridge_sparse" else 0.06,
            double_kick_rate=0.0,
            snare_backbeat_steps=snare_backbeats,
            ghost_rate=0.04 if gid == "bridge_sparse" else 0.10,
            ghost_steps=default_ghosts,
            open_hat_rate=0.02,
            crash_start=False,
            crash_phrase_end_rate=0.0,
        )

    # Verses.
    if gid in ("verse_light", "verse_groove", "verse_drive"):
        hat_mode = "quarter" if gid == "verse_light" else "8th" if gid == "verse_groove" else "16th"
        kick_extra = 0.02 if gid == "verse_light" else 0.06 if gid == "verse_groove" else 0.14
        ghost = 0.06 if gid == "verse_light" else 0.10 if gid == "verse_groove" else 0.16
        double_kick = 0.0 if gid != "verse_drive" else (0.08 if band == "high" else 0.0)

        return GrooveTemplate(
            hat_mode=hat_mode,
            use_ride=False,
            half_time=False,
            kick_base=steps_at(0.0) if gid == "verse_light" else steps_at(0.0, 2.0),
            kick_extra_rate=kick_extra,
            double_kick_rate=double_kick,
            snare_backbeat_steps=snare_backbeats,
            ghost_rate=ghost,
            ghost_steps=default_ghosts,
            open_hat_rate=0.04 if gid == "verse_drive" else 0.02,
            crash_start=False,
            crash_phrase_end_rate=0.0,
        )

    return tpl


def groove_template_from_recipe(
    recipe_groove: dict,
    beats_per_bar: float = 4.0,
) -> "GrooveTemplate":
    """Build a GrooveTemplate from a recipe's ``groove`` dict.

    The recipe groove dict maps directly to GrooveTemplate field names.
    Lists are converted to tuples. Missing fields use GrooveTemplate defaults.

    Args:
        recipe_groove: The ``groove`` section from a recipe YAML.
        beats_per_bar: Section meter beats per bar.

    Returns:
        GrooveTemplate populated from the recipe values.
    """

    def _to_tuple(val: object, default: Tuple[int, ...] = ()) -> Tuple[int, ...]:
        if val is None:
            return default
        if isinstance(val, (list, tuple)):
            return tuple(int(x) for x in val)
        return (int(val),)  # type: ignore[arg-type]

    g = recipe_groove or {}
    return GrooveTemplate(
        hat_mode=str(g.get("hat_mode", "8th")),
        use_ride=bool(g.get("use_ride", False)),
        half_time=bool(g.get("half_time", False)),
        kick_base=_to_tuple(g.get("kick_base"), (0,)),
        kick_extra_rate=float(g.get("kick_extra_rate", 0.0)),
        double_kick_rate=float(g.get("double_kick_rate", 0.0)),
        snare_backbeat_steps=_to_tuple(g.get("snare_backbeat_steps"), (4, 12)),
        ghost_rate=float(g.get("ghost_rate", 0.0)),
        ghost_steps=_to_tuple(g.get("ghost_steps"), (7, 15)),
        open_hat_rate=float(g.get("open_hat_rate", 0.0)),
        crash_start=bool(g.get("crash_start", False)),
        crash_phrase_end_rate=float(g.get("crash_phrase_end_rate", 0.0)),
    )
