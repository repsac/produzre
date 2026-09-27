"""A fingerstyle figure with independent thumb time and a recurring top voice."""
from __future__ import annotations

import random
from dataclasses import dataclass

from ..rng import stable_seed_int
from .theory import nearest_in, scale_pcs


# The top of a picked acoustic melody: A5, the 17th fret on the high E,
# where a cutaway steel-string still plays comfortably.
MELODY_CEILING = 81


@dataclass(frozen=True)
class PickingDNA:
    thumb: str
    figure: str
    chorus_figure: str
    placement: str
    fifth: int
    answer: tuple


def compose_picking_dna(seed, genre):
    rng = random.Random(stable_seed_int("composer.picking", seed, genre))
    figures = ("pinch", "pima", "forward", "banjo", "held_top")
    thumb = rng.choice(("travis", "travis", "monotonic", "roots", "walking"))
    figure = rng.choice(figures)
    chorus = rng.choice([f for f in figures if f != figure])
    return PickingDNA(thumb, figure, chorus, rng.choice(("onbeat", "syncopated", "anticipated")),
                      rng.choice((-5, 7)), tuple(rng.sample(range(4), 2)))


def fingerstyle(seed, genre, chords, voicings, *, bars, bpb, groups, section_type,
                melody_amount=0.72, variation=0.35, capo=0, closing=False):
    """A recurring right-hand figure under a stronger, independent top voice.

    ``chords`` are concert pitch and ``voicings`` are sounding shapes (the
    capo is already in them), so every voice is placed in sounding pitch:
    the capo changes the shapes and raises the open-string floor, never the
    pitch classes.
    """
    rng = random.Random(stable_seed_int("composer.fingerstyle", seed, genre, bpb, groups))
    contour = [rng.choice((-2, -1, 0, 1, 2)) for _ in range(8)]
    offsets = [rng.choice((0.0, 0.5, 0.5, 0.75)) for _ in range(8)]
    melody_mask = [rng.random() < melody_amount for _ in range(8)]
    dna = compose_picking_dna(seed, genre)
    grouped = any(g != int(g) for g in groups) or bpb not in (3, 4)
    pulses = [sum(groups[:i]) for i in range(len(groups))] if grouped else list(range(int(bpb)))
    lift = section_type in ("chorus", "solo")
    figure = dna.chorus_figure if lift else dna.figure
    previous = 67 + capo
    notes = []
    for bar in range(bars):
        start = bar * bpb
        for i, pulse in enumerate(pulses):
            t = start + pulse
            span = chords.at(t)
            shape = voicings[span.numeral].pitches
            low = min(shape)
            root = span.root_pc
            length = (pulses[i+1] if i+1 < len(pulses) else bpb) - pulse
            alternate = dna.thumb == "travis" and i % 2
            bass = nearest_in(((root + dna.fifth if alternate else root) % 12,),
                              low + (dna.fifth if alternate else 0), low, low+12)
            if dna.thumb not in ("roots", "walking") or i % 2 == 0 or grouped:
                notes.append((t, min(length*.82, span.end-t), bass, .72, "acoustic_thumb"))
            if dna.thumb == "walking" and i == len(pulses)-1 and start+bpb < chords.total:
                nxt = chords.at(start+bpb)
                if nxt.root_pc != span.root_pc:
                    target = nearest_in((nxt.root_pc,), low, low, low+12)
                    pcs = tuple(scale_pcs(chords.key, chords.mode))
                    pitch = nearest_in(pcs, target-2, low, low+12)
                    notes.append((t+length*.5, length*.4, pitch, .65, "acoustic_thumb"))
            k = (bar % 2 * len(pulses) + i) % 8
            off = {"onbeat": 0, "syncopated": .5, "anticipated": .75}[dna.placement]
            if figure == "pinch" and i == 0:
                off = 0
            elif figure == "pima":
                off = .75 if i % 2 else .5
            elif figure == "forward":
                off = (0, .5, .25)[i % 3]
            elif figure == "banjo":
                off = (.5, 0, .75)[i % 3]
            elif figure == "held_top":
                off = 0
            if bar % 2 and i in dna.answer and variation > 0:
                off = offsets[k]
            mt = t + off*length
            mspan = chords.at(mt)
            mshape = voicings[mspan.numeral].pitches
            pcs = tuple(mspan.pcs)
            target = previous + contour[k] * 2
            if i == 0:
                target = max(mshape) - (0 if lift else 3)
            if variation > 0 and bar % 4 == 3:
                target -= i * min(1.0, variation * 2)
            hi = min(max(mshape) + 3, max(MELODY_CEILING, max(mshape)))
            melody = nearest_in(pcs, target, min(hi, max(55 + capo, max(mshape)-9)), hi)
            melodic = melody_mask[k] and (figure != "held_top" or i % 2 == 0)
            if melodic:
                dur = (2 if figure == "held_top" else 1)*length-off*length-.03
                notes.append((mt, min(dur, mspan.end-mt, bars*bpb-mt), melody, 1.0, "acoustic_theme"))
                previous = melody
            # Each figure assigns the inner finger a place, not extra density.
            inner_pulse = i in dna.answer or melody_amount < .5
            if inner_pulse:
                it = t + length * (.25 if figure in ("pima", "forward") else .5)
                isp = chords.at(it)
                inner = sorted(voicings[isp.numeral].pitches)[-3 if i % 2 else -2]
                notes.append((it, min(length*.35, isp.end-it), inner, .52, "acoustic_inner"))
    if closing and bars and melody_amount > 0:
        end_start = max((bars-1) * bpb, chords.spans[-1].start)
        span = chords.at(end_start)
        shape = voicings[span.numeral].pitches
        notes = [n for n in notes if n[0] < end_start]
        root = span.root_pc
        notes += [(end_start, (bars*bpb-end_start)*.9, nearest_in((root,), min(shape), min(shape), min(shape)+12),
                   .72, "acoustic_thumb"),
                  (end_start, (bars*bpb-end_start)*.9, nearest_in(tuple(span.pcs),
                    previous, max(shape)-7, min(max(shape)+3, max(MELODY_CEILING, max(shape)))),
                   1.0, "acoustic_theme")]
    return sorted((n for n in notes if n[1] > .02), key=lambda n:(n[0], n[2]))
