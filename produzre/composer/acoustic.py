"""A fingerstyle figure with independent thumb time and a recurring top voice."""
from __future__ import annotations

import random

from ..rng import stable_seed_int
from .theory import ChordMap, nearest_in


def fingerstyle(seed, genre, chords, voicings, *, bars, bpb, groups, section_type,
                melody_amount=0.72, variation=0.35, capo=0, closing=False):
    """Two-bar picking DNA, voiced on the engine's chord shapes.

    Thumb roots and fifths mark the pulse. The treble contour recalls its
    two-bar idea with a phrase-end answer; a chorus lifts with pinches and
    a higher top voice, rather than switching to band strumming.
    """
    rng = random.Random(stable_seed_int("composer.fingerstyle", seed, genre, bpb, groups))
    contour = [rng.choice((-2, -1, 0, 1, 2)) for _ in range(8)]
    offsets = [rng.choice((0.0, 0.5, 0.5, 0.75)) for _ in range(8)]
    melody_mask = [rng.random() < melody_amount for _ in range(8)]
    grouped = any(g != int(g) for g in groups)
    pulses = [sum(groups[:i]) for i in range(len(groups))] if grouped else list(range(int(bpb)))
    lift = section_type in ("chorus", "solo")
    previous = 67 + capo
    notes = []
    for bar in range(bars):
        start = bar * bpb
        for i, pulse in enumerate(pulses):
            t = start + pulse
            span = chords.at(t)
            shape = voicings[span.numeral].pitches
            low, high = min(shape), max(shape)
            root = (span.root_pc + capo) % 12
            bass_pc = root if i % 2 == 0 else (root + 7) % 12
            bass = nearest_in((bass_pc,), low + (4 if i % 2 else 0), low, low + 12)
            length = (pulses[i+1] if i+1 < len(pulses) else bpb) - pulse
            notes.append((t, min(length * .82, span.end-t), bass, .72, "acoustic_thumb"))
            k = (bar % 2 * len(pulses) + i) % 8
            off = offsets[k] * length if grouped else min(offsets[k], length * .75)
            mt = t + off
            mspan = chords.at(mt)
            mshape = voicings[mspan.numeral].pitches
            pcs = tuple((pc + capo) % 12 for pc in mspan.pcs)
            target = previous + contour[k] * 2
            if i == 0:
                target = max(mshape) - (0 if lift else 3)
            if variation > 0 and bar % 4 == 3:
                target -= i * min(1.0, variation * 2)
            melody = nearest_in(pcs, target, max(55 + capo, max(mshape)-9), max(mshape)+3)
            if melody_mask[k]:
                notes.append((mt, min(length-off-.03, mspan.end-mt), melody, 1.0, "acoustic_theme"))
                previous = melody
            # An inner chord tone keeps harmony audible underneath the tune.
            if lift or melody_amount < .5 or k % 3 == 0:
                it = t + length * .5
                isp = chords.at(it)
                inner = sorted(voicings[isp.numeral].pitches)[-3]
                notes.append((it, min(length*.4, isp.end-it), inner, .52, "acoustic_inner"))
    if closing and bars and melody_amount > 0:
        end_start = max((bars-1) * bpb, chords.spans[-1].start)
        span = chords.at(end_start)
        shape = voicings[span.numeral].pitches
        notes = [n for n in notes if n[0] < end_start]
        root = (span.root_pc + capo) % 12
        notes += [(end_start, (bars*bpb-end_start)*.9, nearest_in((root,), min(shape), min(shape), min(shape)+12),
                   .72, "acoustic_thumb"),
                  (end_start, (bars*bpb-end_start)*.9, nearest_in(tuple((p+capo)%12 for p in span.pcs),
                    previous, max(shape)-7, max(shape)+3), 1.0, "acoustic_theme")]
    return sorted((n for n in notes if n[1] > .02), key=lambda n:(n[0], n[2]))
