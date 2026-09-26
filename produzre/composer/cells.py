"""Motif cells and the developmental operations composers apply to them.

A ``Cell`` stores a short idea as rhythm plus *diatonic contour*: each note
records how many scale steps it moves from the previous note. Keeping the
contour relative (instead of absolute degrees) lets one idea be restated
over any chord, sequenced up or down, or answered, while its shape stays
recognizable: the property that makes a motif a motif.

Operations return new cells and never mutate. The ones taking ``rng`` use it
only to choose among musically valid options.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace
from typing import Optional, Sequence, Tuple


@dataclass(frozen=True)
class CellNote:
    """One note of a cell.

    Attributes:
        onset: Beat offset from the cell start.
        dur: Duration in beats.
        step: Diatonic steps from the previous note (first note: from the
            phrase anchor chosen at realization).
        accent: Emphasis hint for velocity shaping.
        tech: Guitar technique hint ("bend", "slide", "vib", "stac", ...).
        degree: Optional absolute diatonic index (0 = tonic) that realization
            should honor exactly; used for authored themes and cadences.
        alter: Semitone alteration applied to a pinned degree.
    """

    onset: float
    dur: float
    step: int
    accent: bool = False
    tech: Optional[str] = None
    degree: Optional[int] = None
    alter: int = 0  # chromatic alteration of a pinned degree (#4 = +1, b7 = -1)


@dataclass(frozen=True)
class Cell:
    notes: Tuple[CellNote, ...]
    length: float
    name: str = ""

    @property
    def steps(self) -> Tuple[int, ...]:
        return tuple(n.step for n in self.notes)

    @property
    def durations(self) -> Tuple[float, ...]:
        return tuple(n.dur for n in self.notes)

    def contour(self) -> Tuple[int, ...]:
        """Cumulative diatonic height of each note relative to the first."""
        h = 0
        out = []
        for i, n in enumerate(self.notes):
            if i:
                h += n.step
            out.append(h)
        return tuple(out)

    def with_name(self, name: str) -> "Cell":
        return replace(self, name=name)


def cell_from(durations: Sequence[float], steps: Sequence[int], *,
              length: Optional[float] = None, rests: Sequence[bool] = (),
              name: str = "") -> Cell:
    """Build a cell from parallel duration/step lists (rests skip a slot)."""
    notes = []
    t = 0.0
    for i, (d, s) in enumerate(zip(durations, steps)):
        if not (i < len(rests) and rests[i]):
            notes.append(CellNote(round(t, 4), float(d), int(s)))
        t += d
    return Cell(tuple(notes), float(length if length is not None else t), name)


def _renormalize(notes: Sequence[CellNote]) -> Tuple[CellNote, ...]:
    return tuple(sorted(notes, key=lambda n: n.onset))


def concat(*cells: Cell, name: str = "") -> Cell:
    """Join cells end to end; contour continues across the joins."""
    out = []
    t = 0.0
    for c in cells:
        for n in c.notes:
            out.append(replace(n, onset=round(n.onset + t, 4)))
        t += c.length
    return Cell(tuple(out), t, name)


def transpose(cell: Cell, steps: int) -> Cell:
    """Shift the entry point (sequence): contour identical, anchor moved."""
    if not cell.notes:
        return cell
    first = replace(cell.notes[0], step=cell.notes[0].step + steps)
    return replace(cell, notes=(first,) + cell.notes[1:])


def invert(cell: Cell) -> Cell:
    """Mirror the contour (first note keeps its entry step)."""
    notes = [cell.notes[0]] + [replace(n, step=-n.step) for n in cell.notes[1:]]
    return replace(cell, notes=tuple(notes))


def augment(cell: Cell, factor: float = 2.0) -> Cell:
    notes = tuple(replace(n, onset=round(n.onset * factor, 4), dur=n.dur * factor)
                  for n in cell.notes)
    return Cell(notes, cell.length * factor, cell.name)


def fragment(cell: Cell, beats: float, *, tail: bool = False) -> Cell:
    """The first (or last) ``beats`` of a cell, clipped at the boundary."""
    if tail:
        cut = cell.length - beats
        kept = [n for n in cell.notes if n.onset >= cut - 1e-6]
        if not kept:
            return Cell((), beats, cell.name)
        notes = tuple(replace(n, onset=round(n.onset - cut, 4)) for n in kept)
        notes = (replace(notes[0], step=0),) + notes[1:]
        return Cell(notes, beats, cell.name)
    kept = [replace(n, dur=min(n.dur, beats - n.onset)) for n in cell.notes
            if n.onset < beats - 1e-6]
    return Cell(tuple(kept), beats, cell.name)


def displace(cell: Cell, shift: float) -> Cell:
    """Rhythmic displacement inside the cell (notes past the end drop)."""
    kept = [replace(n, onset=round(n.onset + shift, 4),
                    dur=min(n.dur, cell.length - n.onset - shift))
            for n in cell.notes if n.onset + shift < cell.length - 1e-6]
    return replace(cell, notes=tuple(kept))


def vary_tail(cell: Cell, rng: random.Random, *, keep: float = 0.5,
              end_long: bool = False) -> Cell:
    """Keep the head, recompose the tail's contour (a new 'ending')."""
    cut = cell.length * keep
    notes = list(cell.notes)
    tail_idx = [i for i, n in enumerate(notes) if n.onset >= cut - 1e-6]
    if not tail_idx:
        return cell
    for i in tail_idx:
        old = notes[i].step
        choices = [s for s in (-2, -1, 1, 2) if s != old] or [-1]
        notes[i] = replace(notes[i], step=rng.choice(choices))
    if end_long and len(notes) >= 2:
        last = notes[-1]
        notes[-1] = replace(last, dur=max(last.dur, cell.length - last.onset))
    return replace(cell, notes=tuple(notes))


def vary_rhythm(cell: Cell, rng: random.Random) -> Cell:
    """Split one long note or merge two short ones; contour survives."""
    notes = list(cell.notes)
    longs = [i for i, n in enumerate(notes) if n.dur >= 1.0]
    if longs and rng.random() < 0.6:
        i = rng.choice(longs)
        n = notes[i]
        half = n.dur / 2.0
        a = replace(n, dur=half)
        b = CellNote(round(n.onset + half, 4), half, rng.choice((-1, 0, 1)))
        notes[i:i + 1] = [a, b]
    elif len(notes) >= 3:
        i = rng.randrange(1, len(notes) - 1)
        a, b = notes[i], notes[i + 1]
        if abs(a.onset + a.dur - b.onset) < 1e-6:
            merged = replace(a, dur=a.dur + b.dur)
            nxt = notes[i + 2:]
            if nxt:
                nxt = [replace(nxt[0], step=nxt[0].step + b.step)] + nxt[1:]
            notes = notes[:i] + [merged] + nxt
    return replace(cell, notes=_renormalize(notes))


def ornament(cell: Cell, rng: random.Random) -> Cell:
    """Embellish a restatement: a neighbor-note turn into one long note."""
    notes = list(cell.notes)
    longs = [i for i, n in enumerate(notes) if n.dur >= 1.0 and i > 0]
    if not longs:
        return cell
    i = rng.choice(longs)
    n = notes[i]
    side = rng.choice((1, -1))
    grace = CellNote(n.onset, 0.25, n.step + side, tech="hammer")
    main = replace(n, onset=round(n.onset + 0.25, 4), dur=n.dur - 0.25, step=-side)
    notes[i:i + 1] = [grace, main]
    return replace(cell, notes=tuple(notes))


def liquidate(cell: Cell) -> Cell:
    """Strip to the rhythmic skeleton: keep notes on strong positions."""
    kept = [n for n in cell.notes if abs(n.onset - round(n.onset)) < 1e-6]
    if len(kept) < 2:
        kept = list(cell.notes[:2])
    # Re-accumulate steps so the kept notes keep their original heights.
    heights = dict(zip([id(n) for n in cell.notes], cell.contour()))
    out = []
    prev_h = None
    for n in kept:
        h = heights[id(n)]
        step = n.step if prev_h is None else h - prev_h
        out.append(replace(n, step=step))
        prev_h = h
    # Let each kept note ring until the next.
    rung = []
    for j, n in enumerate(out):
        end = out[j + 1].onset if j + 1 < len(out) else cell.length
        rung.append(replace(n, dur=max(n.dur, end - n.onset)))
    return replace(cell, notes=tuple(rung))


def cadence(cell: Cell, degree: int, *, hold: bool = True) -> Cell:
    """Pin the last note to an absolute diatonic degree and let it ring."""
    if not cell.notes:
        return cell
    last = cell.notes[-1]
    dur = max(last.dur, cell.length - last.onset) if hold else last.dur
    notes = cell.notes[:-1] + (replace(last, degree=int(degree), dur=dur, tech=last.tech or "vib"),)
    return replace(cell, notes=notes)


def fit_length(cell: Cell, length: float) -> Cell:
    """Clip or pad (with silence) to an exact length."""
    kept = tuple(replace(n, dur=min(n.dur, length - n.onset))
                 for n in cell.notes if n.onset < length - 1e-6)
    return Cell(kept, float(length), cell.name)
