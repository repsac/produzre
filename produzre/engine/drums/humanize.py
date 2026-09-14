"""Humanization helpers for the Produzre drums engine.

This module is *pure* logic and intentionally does not touch the Timeline.

It applies small, deterministic timing and velocity variations so grooves feel
played rather than step-programmed, while remaining reproducible given the same
RNG seed.

Key concepts:
- timing_jitter_ms: random +/- jitter around the nominal start time
- swing: delays the "&" (eighth off-beat) to create swing feel
- push_pull: deterministic ahead/behind bias (useful for "pushing" choruses)
- velocity_humanize: random +/- variation around nominal velocity

All randomness must be driven by an explicit `random.Random` passed in.
"""

from __future__ import annotations

import hashlib
import random
from typing import Iterable, List, Optional, Tuple

from .patterns import DrumEvent


def _seed_from_rng_state(rng: random.Random, label: str) -> int:
    """Derive a deterministic 64-bit seed from an RNG's *current* state + label.

    This does NOT advance the RNG. It is used to create independent, stable
    per-event RNG streams so adding/removing other events does not perturb
    existing timing/velocity humanization.
    """

    state_bytes = repr(rng.getstate()).encode("utf-8")
    h = hashlib.sha256(state_bytes + b"|" + label.encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big", signed=False)


def _event_key(
    *,
    rel_beat: float,
    pitch: int,
    kind: str,
    duration_beats: float,
) -> str:
    """Create a stable string key for an event.

    We round floats to avoid tiny representation differences while preserving
    musical intent.
    """

    rb = f"{rel_beat:.6f}"
    db = f"{duration_beats:.6f}"
    return f"rel={rb}|dur={db}|pitch={int(pitch)}|kind={kind}"


def _beats_from_ms(ms: float, bpm: float) -> float:
    """Convert milliseconds to beats for a given BPM."""

    b = float(bpm)
    if b <= 0.0:
        return 0.0
    return (float(ms) / 60000.0) * b


def clamp_int(x: int, lo: int, hi: int) -> int:
    """Clamp an int into the inclusive range [lo, hi]."""

    return lo if x < lo else hi if x > hi else x


def humanize_start(
    *,
    start_beat: float,
    beat_in_bar: float,
    bpm: float,
    timing_jitter_ms: float,
    swing: float,
    push_pull: float,
    rng: random.Random,
    swing_16th: Optional[float] = None,
) -> float:
    """Return a humanized start time in beats.

    Args:
        start_beat: Nominal start beat (song-relative or section-relative).
        beat_in_bar: Beat offset within the bar (0.0 == downbeat).
        bpm: Tempo.
        timing_jitter_ms: Random jitter amount in milliseconds.
        swing: 0..1 (approx). Delays the "&" of each beat.
        push_pull: -1..1 (approx). Positive values push later; negative pull earlier.
        rng: Deterministic RNG.

    Returns:
        Humanized start beat (never negative).

    Notes:
        This is intentionally conservative: it should preserve tightness by
        default so users do not mistake timing variation for a bug.
    """

    t = float(start_beat)

    from ...groove import swing_offset
    t += _beats_from_ms(max(-25.0, min(25.0, -100.0 * float(push_pull))), bpm)
    sixteenth = swing * 0.5 if swing_16th is None else swing_16th
    t += swing_offset(beat_in_bar, swing, sixteenth)

    # Random jitter.
    j_ms = float(timing_jitter_ms)
    if j_ms > 0.0:
        j = _beats_from_ms(j_ms, bpm)
        t += rng.uniform(-j, j)

    return 0.0 if t < 0.0 else t


def humanize_velocity(*, velocity: int, velocity_humanize: float, rng: random.Random) -> int:
    """Return a humanized MIDI velocity.

    Args:
        velocity: Nominal velocity (1..127).
        velocity_humanize: 0..1. Interpreted as +/- proportion of the nominal velocity.
        rng: Deterministic RNG.

    Returns:
        Clamped velocity (1..127).
    """

    v = int(velocity)
    amt = float(velocity_humanize)
    if amt <= 0.0:
        return clamp_int(v, 1, 127)

    delta = max(1, int(round(abs(v) * amt)))
    v2 = v + rng.randint(-delta, delta)
    return clamp_int(v2, 1, 127)


def humanize_events(
    *,
    events: Iterable[DrumEvent],
    section_start_beat: float,
    beats_per_bar: float,
    bpm: float,
    timing_jitter_ms: float,
    swing: float,
    push_pull: float,
    velocity_humanize: float,
    rng: random.Random,
    rng_timing: Optional[random.Random] = None,
    rng_velocity: Optional[random.Random] = None,
    swing_16th: Optional[float] = None,
) -> List[Tuple[float, float, int, int, str]]:
    """Humanize a sequence of DrumEvents into timeline-ready note tuples.

    Args:
        events: Idealized events (section-relative beats/velocities).
        section_start_beat: Absolute song beat for the section start.
        beats_per_bar: Meter beats per bar.
        bpm: Tempo.
        timing_jitter_ms: Jitter amount.
        swing: Swing amount.
        push_pull: Push/pull bias.
        velocity_humanize: Velocity variation.
        rng: Deterministic RNG (fallback if rng_timing/rng_velocity not provided).
        rng_timing: Optional RNG stream used for timing humanization.
        rng_velocity: Optional RNG stream used for velocity humanization.

    Returns:
        List of tuples: (start_beat_abs, duration_beats, pitch, velocity, kind)
    """

    bpb = float(beats_per_bar)
    out: List[Tuple[float, float, int, int, str]] = []

    rt = rng if rng_timing is None else rng_timing
    rv = rng if rng_velocity is None else rng_velocity

    for e in events:
        rel = float(e.beat)
        dur = float(e.duration_beats)
        kind = str(e.kind)
        pitch = int(e.pitch)

        beat_in_bar = rel % bpb if bpb > 0.0 else 0.0

        # Create per-event RNGs derived from the (section-level) timing/velocity RNG
        # states. This makes humanization stable under event insertion/removal.
        ek = _event_key(rel_beat=rel, pitch=pitch, kind=kind, duration_beats=dur)
        rt_e = random.Random(_seed_from_rng_state(rt, "timing|" + ek))
        rv_e = random.Random(_seed_from_rng_state(rv, "velocity|" + ek))

        start_abs = humanize_start(
            start_beat=float(section_start_beat) + rel,
            beat_in_bar=beat_in_bar,
            bpm=bpm,
            timing_jitter_ms=timing_jitter_ms,
            swing=swing,
            swing_16th=swing_16th,
            push_pull=push_pull,
            rng=rt_e,
        )
        start_abs = max(float(section_start_beat), start_abs)
        vel = humanize_velocity(velocity=int(e.velocity), velocity_humanize=velocity_humanize, rng=rv_e)
        out.append((start_abs, dur, pitch, vel, kind))

    out.sort(key=lambda x: (x[0], x[2], x[4]))
    return out
