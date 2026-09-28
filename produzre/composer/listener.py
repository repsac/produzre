"""A deterministic model of a listener's melodic expectations.

Music with character manages expectation: repetition teaches the listener
what to expect, and well-placed deviations reward attention. Procedural
music usually fails one way or the other: uniform randomness is constantly
surprising (and therefore boring), strict looping is never surprising.

``Listener`` estimates how surprising each next note is, in bits of
information content (IC), from two sources:

* a long-term prior: interval statistics aggregated from human-composed
  melodies (``resources/composer/melodic_prior.json``), standing in for the
  listener's lifetime of listening; and
* a short-term memory trained on everything the song has already played,
  so a motif that has been heard becomes predictable, exactly as it does for
  a real listener.

The composer queries the listener while choosing among candidate
developments and steers the IC of each phrase toward a planned surprise
curve. Everything is counting; there is no randomness in this module.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from functools import lru_cache
from typing import Dict, Iterable, List, Sequence, Tuple

_CLIP = 12
_ALPHABET = 2 * _CLIP + 1
# Duration classes (beats) for the rhythm half of each token.
_DUR_CLASSES = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0)


def _clip(iv: int) -> int:
    return max(-_CLIP, min(_CLIP, int(iv)))


def dur_class(d: float) -> int:
    return min(range(len(_DUR_CLASSES)), key=lambda i: abs(_DUR_CLASSES[i] - d))


@lru_cache(maxsize=1)
def _prior() -> Tuple[Dict[int, float], Dict[int, Dict[int, float]]]:
    """Load the long-term interval prior (unigram + bigram probabilities)."""
    from ..config.load import _package_root  # lazy: avoids an import cycle

    path = _package_root() / "resources" / "composer" / "melodic_prior.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    uni_raw = {int(k): float(v) for k, v in (data.get("unigram") or {}).items()}
    # Octave leaps in the source skylines are inflated by doubling; damp them.
    for k in (-12, 12):
        if k in uni_raw:
            uni_raw[k] *= 0.25
    total = sum(uni_raw.values()) + _ALPHABET
    uni = {iv: (uni_raw.get(iv, 0.0) + 1.0) / total for iv in range(-_CLIP, _CLIP + 1)}
    bi: Dict[int, Dict[int, float]] = {}
    for a, row in (data.get("bigram") or {}).items():
        counts = {int(b): float(c) for b, c in row.items()}
        n = sum(counts.values())
        # Blend the bigram with the unigram (Witten-Bell style weight).
        lam = n / (n + 25.0)
        bi[int(a)] = {iv: lam * counts.get(iv, 0.0) / max(n, 1.0) + (1 - lam) * uni[iv]
                      for iv in range(-_CLIP, _CLIP + 1)}
    return uni, bi


class Listener:
    """Incremental expectation model over (interval, duration) tokens."""

    def __init__(self, memory_weight: float = 3.0):
        self.memory_weight = float(memory_weight)
        self._c1: Dict[int, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
        self._c2: Dict[Tuple[int, int], Dict[int, int]] = defaultdict(lambda: defaultdict(int))
        self._c3: Dict[Tuple[int, int, int], Dict[int, int]] = defaultdict(lambda: defaultdict(int))
        self._rhythm: Dict[Tuple[int, int], Dict[int, int]] = defaultdict(lambda: defaultdict(int))
        self.heard = 0

    # -- probabilities ---------------------------------------------------
    def _p_interval(self, hist: Sequence[int], iv: int) -> float:
        uni, bi = _prior()
        p = bi.get(hist[-1], uni)[iv] if hist else uni[iv]
        w = self.memory_weight
        # Short-term memory: back off from order 3 to order 1, each level
        # blending its counts with the estimate from the level below.
        if hist:
            d = self._c1.get(hist[-1])
            if d:
                n = sum(d.values())
                p = (d.get(iv, 0) + w * p) / (n + w)
        if len(hist) >= 2:
            d = self._c2.get((hist[-2], hist[-1]))
            if d:
                n = sum(d.values())
                p = (d.get(iv, 0) + w * p) / (n + w)
        if len(hist) >= 3:
            d = self._c3.get((hist[-3], hist[-2], hist[-1]))
            if d:
                n = sum(d.values())
                p = (d.get(iv, 0) + w * p) / (n + w)
        return p

    def _p_duration(self, hist_d: Sequence[int], dc: int) -> float:
        base = 1.0 / len(_DUR_CLASSES)
        if len(hist_d) >= 2:
            d = self._rhythm.get((hist_d[-2], hist_d[-1]))
            if d:
                n = sum(d.values())
                return (d.get(dc, 0) + 2.0 * base) / (n + 2.0)
        return base

    def information(self, pitches: Sequence[int], durations: Sequence[float],
                    context: Sequence[Tuple[int, float]] = ()) -> List[float]:
        """IC (bits) of each note after the first, given optional context.

        ``context`` is the (pitch, duration) tail of what played just before,
        so a phrase is judged as a continuation, not in isolation.
        """
        seq_p = [p for p, _ in context] + list(pitches)
        seq_d = [d for _, d in context] + list(durations)
        ivs = [_clip(b - a) for a, b in zip(seq_p, seq_p[1:])]
        dcs = [dur_class(d) for d in seq_d]
        out: List[float] = []
        start = max(0, len(context) - 1)
        for i in range(start, len(ivs)):
            hist = ivs[max(0, i - 3):i]
            p_iv = self._p_interval(hist, ivs[i])
            p_d = self._p_duration(dcs[max(0, i - 1):i + 1], dcs[i + 1])
            out.append(-math.log2(max(p_iv, 1e-9)) - 0.5 * math.log2(max(p_d, 1e-9)))
        return out

    def mean_information(self, pitches, durations, context=()) -> float:
        ics = self.information(pitches, durations, context)
        return sum(ics) / len(ics) if ics else 0.0

    def contextual_cost(self, notes, chords, beats_per_bar: float, groups=None) -> float:
        """Metric-weighted dissonance exposure, separate from calibrated IC.

        Evaluate held notes across chord boundaries as well as at attacks.
        Short, stepwise passing tones are cheaper than exposed dissonances.
        This is a musical heuristic, not a probability learned from the prior.
        """
        from .theory import metric_weight

        if not notes or beats_per_bar <= 0:
            return 0.0
        cost = total = 0.0
        for i, note in enumerate(notes):
            end = note.beat + note.dur
            passing = (0 < i < len(notes) - 1 and note.dur <= 0.5
                       and 0 < abs(note.pitch - notes[i - 1].pitch) <= 2
                       and 0 < abs(notes[i + 1].pitch - note.pitch) <= 2
                       and (note.pitch - notes[i - 1].pitch)
                       * (notes[i + 1].pitch - note.pitch) > 0)
            for span in chords.spans:
                start, stop = max(note.beat, span.start), min(end, span.end)
                if stop <= start:
                    continue
                duration = stop - start
                total += duration
                if note.pitch % 12 in span.pcs:
                    continue
                weight = metric_weight(start % beats_per_bar, beats_per_bar, groups)
                cost += duration * (0.25 + 0.75 * weight) * (0.35 if passing else 1.0)
        return cost / total if total else 0.0

    # -- learning --------------------------------------------------------
    def observe(self, pitches: Sequence[int], durations: Sequence[float]) -> None:
        ivs = [_clip(b - a) for a, b in zip(pitches, pitches[1:])]
        dcs = [dur_class(d) for d in durations]
        for i, iv in enumerate(ivs):
            if i >= 1:
                self._c1[ivs[i - 1]][iv] += 1
            if i >= 2:
                self._c2[(ivs[i - 2], ivs[i - 1])][iv] += 1
            if i >= 3:
                self._c3[(ivs[i - 3], ivs[i - 2], ivs[i - 1])][iv] += 1
        for i in range(2, len(dcs)):
            self._rhythm[(dcs[i - 2], dcs[i - 1])][dcs[i]] += 1
        self.heard += len(pitches)


def prior_information(pitches: Iterable[int]) -> float:
    """Mean IC under the long-term prior alone (how generic a line is)."""
    uni, bi = _prior()
    ps = list(pitches)
    ivs = [_clip(b - a) for a, b in zip(ps, ps[1:])]
    if not ivs:
        return 0.0
    total = 0.0
    for i, iv in enumerate(ivs):
        p = bi.get(ivs[i - 1], uni)[iv] if i else uni[iv]
        total += -math.log2(max(p, 1e-9))
    return total / len(ivs)
