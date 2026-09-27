# produzre/engine/bass/walking.py
"""Walking bass: one note per pulse, planned a bar at a time.

A walking line is a melody with rules, not a thinned rhythm pattern:

- every pulse sounds (quarter notes; dotted quarters in 6/8, 9/8, 12/8),
  so the line never drops a beat and every bar has its downbeat;
- a chord's first beat is its root, and a chord held into a new bar starts
  that bar on another chord tone (or the root an octave away);
- the last pulse before each change steps into the next downbeat, by a
  half step (chromatic) or a scale step (diatonic);
- the inner pulses connect the two, stepwise or through chord tones, with
  chord tones on the strong beats and no root repeated inside the bar.

Density, rests, drum locks, octave jumps and fills do not apply: they are
controls for a rhythm pattern, and a walk has no gaps to fill.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

EPS = 1e-6


@dataclass(frozen=True)
class WalkChord:
    """A chord span as the walk sees it (section-relative beats)."""
    start: float
    end: float
    root: int                    # root MIDI pitch (any octave)
    pcs: Tuple[int, ...]         # chord-tone pitch classes, root first


@dataclass(frozen=True)
class WalkNote:
    beat: float
    dur: float
    pitch: int
    kind: str                    # walk_root | walk_chord | walk_scale | walk_approach_*


def walk_pulses(beats_per_bar: float, meter: str = "") -> Tuple[float, ...]:
    """Pulse offsets inside one bar: quarters, or dotted quarters in compound time."""
    try:
        num, den = (int(x) for x in str(meter).split("/"))
    except (TypeError, ValueError):
        num, den = 0, 0
    if den == 8 and num >= 6 and num % 3 == 0:
        return tuple(i * 1.5 for i in range(num // 3))
    bpb = float(beats_per_bar)
    pulses = [float(i) for i in range(int(bpb + EPS))]
    return tuple(pulses) or (0.0,)


def _pitches(pcs, lo: int, hi: int) -> List[int]:
    return [p for p in range(lo, hi + 1) if p % 12 in pcs]


def _nearest(pcs, near: float, lo: int, hi: int, avoid: Optional[int] = None) -> int:
    cands = [p for p in _pitches(pcs, lo, hi) if p != avoid] or _pitches(pcs, lo, hi)
    if not cands:
        return max(lo, min(hi, int(round(near))))
    return min(cands, key=lambda p: (abs(p - near), p))


def _step_cost(a: int, b: int) -> float:
    d = abs(a - b)
    if d == 0:
        return 100.0
    if d <= 2:
        return 0.0
    if d <= 4:
        return 0.6
    if d == 5:
        return 1.2
    if d <= 7:
        return 2.5
    return 6.0 + d


def walk_section(
    chords: Sequence[WalkChord],
    *,
    beats_per_bar: float,
    total_beats: float,
    scale_pcs: Sequence[int],
    register_low: int,
    register_high: int,
    chromatic_rate: float,
    rng,
    pulses: Sequence[float] = (0.0, 1.0, 2.0, 3.0),
    final_target_pc: Optional[int] = None,
    cadence: bool = False,
) -> List[WalkNote]:
    """Plan a walking line over ``chords`` for one section.

    ``final_target_pc`` is where the last bar walks to (the next section's
    arrival; the key's tonic by default). With ``cadence`` the line ends on
    the last chord's root instead of approaching anything.
    """
    lo, hi = int(register_low), int(register_high)
    if hi - lo < 12:
        hi = lo + 12
    center = (lo + hi) / 2.0
    scale = set(int(pc) % 12 for pc in scale_pcs)
    bpb = float(beats_per_bar)
    bars = max(1, int(round(total_beats / bpb))) if bpb > 0 else 1
    pulse_len = [(pulses[i + 1] if i + 1 < len(pulses) else bpb) - pulses[i]
                 for i in range(len(pulses))]

    def chord_at(t: float) -> Optional[WalkChord]:
        for c in chords:
            if c.start - EPS <= t < c.end - EPS:
                return c
        return chords[-1] if chords and t >= chords[-1].start else None

    # Segments: the pulses of one chord inside one bar.
    segments: List[Tuple[List[float], List[float], WalkChord, bool]] = []
    for b in range(bars):
        cur: Optional[WalkChord] = None
        for i, off in enumerate(pulses):
            t = b * bpb + off
            if t >= total_beats - EPS:
                break
            c = chord_at(t)
            if c is None:
                continue
            if cur is None or c is not cur:
                new_chord = not segments or segments[-1][2] is not c
                segments.append(([], [], c, new_chord))
                cur = c
            segments[-1][0].append(t)
            segments[-1][1].append(pulse_len[i])
    if not segments:
        return []

    # Downbeat of each segment: the root of a new chord, another chord tone
    # when a chord is held into a new bar.
    downs: List[int] = []
    prev: Optional[int] = None
    for times, _, c, new_chord in segments:
        root_pc = c.root % 12
        near = center if prev is None else prev * 0.7 + center * 0.3
        if new_chord or prev is None:
            p = _nearest((root_pc,), near, lo, hi, avoid=prev)
        else:
            others = tuple(pc for pc in c.pcs[1:3] if pc != root_pc) or (root_pc,)
            pick = others[int(rng.random() * len(others)) % len(others)]
            p = _nearest((pick, root_pc) if rng.random() < 0.25 else (pick,), near, lo, hi,
                         avoid=prev)
        downs.append(p)
        prev = p

    out: List[WalkNote] = []
    for s, (times, lens, c, new_chord) in enumerate(segments):
        n = len(times)
        d = downs[s]
        root_pc = c.root % 12
        chord_pcs = set(c.pcs)
        kinds = ["walk_root" if d % 12 == root_pc else "walk_chord"]
        line = [d]
        if s + 1 < len(segments):
            target: Optional[int] = downs[s + 1]
        elif cadence:
            target = None
        else:
            tpc = root_pc if final_target_pc is None else int(final_target_pc) % 12
            target = _nearest((tpc,), d, lo, hi)
        if n >= 2:
            if target is None:
                # The song's last bar: arpeggiate down to the root.
                tones = sorted(set(_pitches(chord_pcs, max(lo, d - 12), d)) - {d}, reverse=True)
                for k in range(1, n):
                    p = tones[(k - 1) % len(tones)] if tones else d
                    line.append(p)
                    kinds.append("walk_root" if p % 12 == root_pc else "walk_chord")
                line[-1] = _nearest((root_pc,), line[-2] if n > 2 else d, lo, hi, avoid=line[-2])
                kinds[-1] = "walk_root"
            else:
                chromatic = rng.random() < float(chromatic_rate)
                if chromatic:
                    approaches = [(target - 1, "walk_approach_chromatic"),
                                  (target + 1, "walk_approach_chromatic")]
                else:
                    below = next(target - k for k in (1, 2) if (target - k) % 12 in scale) \
                        if any((target - k) % 12 in scale for k in (1, 2)) else target - 2
                    above = next(target + k for k in (1, 2) if (target + k) % 12 in scale) \
                        if any((target + k) % 12 in scale for k in (1, 2)) else target + 2
                    approaches = [(below, "walk_approach_diatonic"),
                                  (above, "walk_approach_diatonic")]
                approaches = [(p, k) for p, k in approaches if lo <= p <= hi] or approaches[:1]
                # The root sounds once, on the downbeat: the line moves away
                # from it (an approach that is the root pitch class is skipped).
                approaches = [(p, k) for p, k in approaches if p % 12 != root_pc] or approaches
                inner_n = n - 2
                span_lo = min(d, target) - 5
                span_hi = max(d, target) + 5
                pool = [p for p in range(max(lo, span_lo), min(hi, span_hi) + 1)
                        if (p % 12 in scale or p % 12 in chord_pcs) and p % 12 != root_pc]
                strong = [((times[k] % bpb) < EPS) or abs((times[k] % bpb) - bpb / 2) < EPS
                          for k in range(n)]
                # The bar's shape, a player's choice: climb, fall, or spell
                # the chord. Lines stay varied without leaving the rules.
                shape = ("up", "down", "arp")[int(rng.random() * 3) % 3]
                best = None
                for inner in itertools.product(pool, repeat=inner_n):
                    for a, akind in approaches:
                        seq = (d,) + inner + (a,)
                        cost = 0.0
                        for x, y in zip(seq, seq[1:] + (target,)):
                            cost += _step_cost(x, y)
                        if cost >= 100:
                            continue
                        dirs = [1 if y > x else -1 for x, y in zip(seq, seq[1:] + (target,))]
                        cost += 0.4 * sum(1 for x, y in zip(dirs, dirs[1:]) if x != y)
                        for k, p in enumerate(inner, start=1):
                            if p % 12 == root_pc:
                                cost += 2.0          # no root repeated inside the bar
                            if strong[k] and p % 12 not in chord_pcs:
                                cost += 3.0          # strong beats carry chord tones
                            if p in seq[:k]:
                                cost += 0.7          # prefer new pitches in the bar
                        if a % 12 == root_pc:
                            cost += 2.0
                        moves = [y - x for x, y in zip(seq[:-1], seq[1:])]
                        if shape == "up":
                            cost += 0.6 * sum(1 for m in moves if m < 0)
                        elif shape == "down":
                            cost += 0.6 * sum(1 for m in moves if m > 0)
                        else:
                            cost += 1.2 * sum(1 for p in inner if p % 12 not in chord_pcs)
                        cost += 0.5 * max(0.0, abs(a - center) - (hi - lo) / 2.0 + 2)
                        cost += rng.random() * 0.9  # the player's taste, not a rule
                        if best is None or cost < best[0]:
                            best = (cost, inner, a, akind)
                if best is None:
                    a, akind = approaches[0]
                    inner = tuple(pool[(k * 3) % len(pool)] for k in range(inner_n)) if pool else ()
                else:
                    _, inner, a, akind = best
                for p in inner:
                    line.append(p)
                    kinds.append("walk_root" if p % 12 == root_pc else
                                 "walk_chord" if p % 12 in chord_pcs else "walk_scale")
                line.append(a)
                kinds.append(akind)
        for t, ln, p, k in zip(times, lens, line, kinds):
            out.append(WalkNote(beat=t, dur=ln, pitch=int(p), kind=k))
    return out
