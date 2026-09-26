"""Signature riffs: the figure a hard rock song is remembered by.

Riff-driven rock is not strummed chords. The rhythm guitar plays a figure on
the low strings: a power chord on the root, syncopated power-chord moves to
other pentatonic degrees inside the bar, palm-muted chugs between them, and
a single-note pentatonic tail that pulls into the next bar. Bar two answers
bar one with a different tail. The figure is written relative to the chord
root, so it moves with the progression like a player shifting a riff shape.

``compose_signature_riff`` generates candidates from that grammar and keeps
the most riff-like (a syncopated move, a single-note tail, a groove of
chugs, few enough attacks to hum). Each song draws its own.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from ..rng import stable_seed_int

# Minor-pentatonic intervals above the root a riff moves among: b3, 4, 5, b7,
# and the b5 "blue" passing tone for singles.
_POWER_MOVES = (3, 5, 7, 10, -2)
_SINGLE_STEPS = (0, 3, 5, 6, 7, 10, 12)


@dataclass(frozen=True)
class RiffNote:
    onset: float        # beats within the riff
    dur: float
    kind: str           # "rpower" (power chord), "rchug" (palm-muted root), "rsingle"
    interval: int       # semitones above the chord root
    accent: bool = False


@dataclass(frozen=True)
class SignatureRiff:
    bars: Tuple[Tuple[RiffNote, ...], ...]   # one tuple per bar (usually 2)
    name: str

    def notes_for_bar(self, index: int) -> Tuple[RiffNote, ...]:
        return self.bars[index % len(self.bars)]


def _bar(rng: random.Random, beats: float, tail_variant: int) -> List[RiffNote]:
    steps = int(round(beats * 4))
    # The single-note tail is decided first: the body ends where it begins.
    tail_len = rng.choice([2, 3, 4]) if tail_variant == 0 else rng.choice([3, 4])
    unit = rng.choice([1, 2]) if tail_variant == 0 else 1
    tail_start = steps - tail_len * unit
    events: List[Tuple[int, str, int, bool]] = [(0, "rpower", 0, True)]
    # One or two syncopated power moves in the body of the bar.
    moves = rng.choice([1, 1, 2])
    spots = [s for s in range(3, tail_start - 1) if s % 2 == 1 or s % 4 == 2]
    for s in sorted(rng.sample(spots, min(moves, len(spots)))):
        events.append((s, "rpower", rng.choice(_POWER_MOVES), True))
    # Chugs on the root fill the gaps (eighths, sometimes quarters).
    taken = {s for s, *_ in events}
    chug_every = rng.choice([2, 2, 4])
    for s in range(2, tail_start, chug_every):
        if s not in taken and (s - 1) not in taken and rng.random() < 0.75:
            events.append((s, "rchug", 0, False))
    # Single-note tail pulling into the next bar.
    line = sorted(rng.sample(_SINGLE_STEPS, tail_len), reverse=rng.random() < 0.5)
    for k, iv in enumerate(line):
        events.append((tail_start + k * unit, "rsingle", iv, k == 0))
    events.sort()
    notes = []
    for i, (s, kind, iv, acc) in enumerate(events):
        nxt = events[i + 1][0] if i + 1 < len(events) else steps
        dur = (nxt - s) * 0.25
        if kind == "rchug":
            dur = min(dur, 0.2)
        notes.append(RiffNote(s * 0.25, max(0.12, dur - 0.02), kind, iv, acc))
    return notes


def _score(bar: Sequence[RiffNote]) -> float:
    attacks = len(bar)
    powers = [n for n in bar if n.kind == "rpower"]
    singles = [n for n in bar if n.kind == "rsingle"]
    sync = any(abs(n.onset - round(n.onset)) > 1e-6 for n in powers)
    score = 0.0
    score += 1.0 if sync else 0.0
    score += 0.8 if len(singles) >= 2 else 0.0
    score += 0.5 if any(n.kind == "rchug" for n in bar) else 0.0
    score -= 0.4 * max(0, attacks - 9)            # hummable, not a flurry
    score += 0.3 * len({n.interval for n in powers})
    return score


def compose_signature_riff(*, seed: int, genre: str, beats_per_bar: float = 4.0,
                           tries: int = 40) -> Optional[SignatureRiff]:
    if beats_per_bar < 3:
        return None
    rng = random.Random(stable_seed_int("composer.riff", seed, genre, beats_per_bar))
    scored = []
    for k in range(tries):
        a = _bar(rng, beats_per_bar, 0)
        b = _bar(rng, beats_per_bar, 1)
        # Bar two keeps bar one's body and answers with its own tail.
        body = [n for n in a if n.kind != "rsingle"]
        tail_b = [n for n in b if n.kind == "rsingle" and n.onset > max(x.onset for x in body)]
        if not tail_b:
            tail_b = [n for n in a if n.kind == "rsingle"]
        b2 = tuple(sorted(body + tail_b, key=lambda n: n.onset))
        scored.append((_score(a) + 0.5 * (tail_b != [n for n in a if n.kind == "rsingle"]),
                       k, (tuple(a), b2)))
    scored.sort(key=lambda t: (-t[0], t[1]))
    bars = rng.choice(scored[:4])[2]
    sig = "".join(("P" if n.kind == "rpower" else "p" if n.kind == "rchug" else "s")
                  + str(n.interval) for n in bars[0])
    return SignatureRiff(bars, f"riff:{sig}")
