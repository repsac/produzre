"""Fit a motif cell to the harmony with a small beam search.

The cell supplies the *intent* (rhythm and contour). The search finds the
pitches that honor that intent while sounding composed: chord tones on
strong beats and long notes, dissonances approached and left by step,
leaps kept singable, and the line pulled toward a planned register target.
The search is exhaustive over a narrow window, so it is deterministic and
fast (a few hundred candidate evaluations per phrase).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from .cells import Cell
from .theory import (ChordMap, diatonic_index, diatonic_pitch, metric_weight,
                     scale_pcs, tonic_pc)


@dataclass(frozen=True)
class Note:
    """A realized melody note in section-relative beats."""

    beat: float
    dur: float
    pitch: int
    accent: bool = False
    tech: Optional[str] = None
    role: str = "melody"


_BEAM = 14


def _candidates(intended: float, chord_pcs, scale, lo: int, hi: int,
                pinned_pc: Optional[int] = None) -> List[int]:
    allowed = set(scale) | set(chord_pcs)
    centre = int(round(intended))
    window = 5
    cands: List[int] = []
    while not cands and window <= 12:
        cands = [p for p in range(max(lo, centre - window), min(hi, centre + window) + 1)
                 if p % 12 in allowed]
        window += 4
    if pinned_pc is not None:
        # A pinned degree (cadence, authored note) may sit in another octave
        # when the register is tight: offer every octave of it.
        cands += [p for p in range(lo, hi + 1) if p % 12 == pinned_pc and p not in cands]
    return cands


def realize_cell(
    cell: Cell,
    start: float,
    chords: ChordMap,
    *,
    key: str,
    mode: str,
    lo: int,
    hi: int,
    anchor: float,
    prev_pitch: Optional[int] = None,
    target_curve: Optional[Sequence[float]] = None,
    cadence_pcs: Optional[Sequence[int]] = None,
    beats_per_bar: float = 4.0,
    contour_weight: float = 1.2,
    exact_degrees: bool = False,
    entry_after_rest: bool = True,
    leap_scale: float = 1.0,
) -> Tuple[List[Note], float]:
    """Realize ``cell`` starting at section beat ``start``.

    Args:
        anchor: Pitch the cell's entry should sit near (register plan).
        prev_pitch: Last sounded pitch before this cell, for voice leading.
        target_curve: Optional per-note register targets (overrides anchor
            as the register pull, used for arcs toward a climax).
        cadence_pcs: Pitch classes the final note must land on.
        exact_degrees: Honor ``CellNote.degree`` strictly (authored themes).
        leap_scale: Weight on leap costs (the lead's ``contour_style``):
            above 1 favors stepwise lines, below 1 frees wider leaps.
        entry_after_rest: The cell starts out of silence, so its first note
            cannot be a prepared dissonance and should be a chord tone.

    Returns:
        (notes, cost). Lower cost means a better fit to intent and harmony.
    """
    if not cell.notes:
        return [], 0.0
    scale = scale_pcs(key, mode)
    # Ladder index 0 is the tonic pitch class in MIDI octave -1, matching
    # diatonic_index(), so diatonic_pitch() is its exact inverse.
    tonic_ref = tonic_pc(key)
    anchor_idx = diatonic_index(int(round(anchor)), key, mode)

    # Beam entries: (cost, pitches tuple, intended diatonic index of last)
    beam: List[Tuple[float, Tuple[int, ...], float]] = [(0.0, (), anchor_idx)]
    n_notes = len(cell.notes)
    for i, cn in enumerate(cell.notes):
        beat = start + cn.onset
        span = chords.at(beat)
        chord_pcs = span.pcs if span else scale
        mw = metric_weight(beat % beats_per_bar, beats_per_bar)
        is_last = i == n_notes - 1
        reg_target = (target_curve[i] if target_curve is not None and i < len(target_curve)
                      else anchor)
        new_beam: List[Tuple[float, Tuple[int, ...], float]] = []
        for cost, pitches, last_idx in beam:
            prev = pitches[-1] if pitches else prev_pitch
            if cn.degree is not None:
                intended_idx = float(cn.degree)
                # Pick the octave of the pinned degree nearest the line.
                ref_idx = diatonic_index(prev, key, mode) if prev is not None else anchor_idx
                while intended_idx - ref_idx > 3.5:
                    intended_idx -= 7
                while ref_idx - intended_idx > 3.5:
                    intended_idx += 7
            else:
                # Contour is relative to the note actually played, so the
                # motif's intervals survive a harmonic adjustment upstream.
                base_idx = diatonic_index(prev, key, mode) if pitches else anchor_idx
                intended_idx = round(base_idx) + cn.step
            intended_pitch = diatonic_pitch(int(round(intended_idx)), key, mode, tonic_ref)
            if cn.degree is not None and cn.alter:
                intended_pitch += cn.alter
                intended_idx = diatonic_index(intended_pitch, key, mode)
            pinned = intended_pitch % 12 if cn.degree is not None else None
            cands = _candidates(intended_pitch, chord_pcs, scale, lo, hi, pinned)
            if pinned is not None and exact_degrees:
                # Authored notes are intent: only their pitch class may sound.
                cands = [p for p in cands if p % 12 == pinned] or cands
            for p in cands:
                c = 0.0
                d_idx = diatonic_index(p, key, mode)
                c += contour_weight * abs(d_idx - intended_idx)
                if cn.degree is not None and (exact_degrees or is_last):
                    c += 4.0 * abs(d_idx - intended_idx)
                if prev is not None and pitches:
                    move = p - prev
                    if cn.step != 0 and move == 0:
                        c += 2.8  # a motif that stops moving loses its identity
                    elif cn.step > 0 and move < 0:
                        c += 1.6
                    elif cn.step < 0 and move > 0:
                        c += 1.6
                    elif cn.step == 0 and move != 0:
                        c += 0.9
                    leap = abs(move)
                    if leap > 7:
                        c += 0.6 * leap_scale * (leap - 7)
                    if leap_scale > 1.0 and leap > 4:
                        c += 0.5 * (leap_scale - 1.0) * (leap - 4)
                    if leap > 12:
                        c += 6.0
                    # Leap recovery: after a leap, prefer contrary motion.
                    if len(pitches) >= 2:
                        last_move = pitches[-1] - pitches[-2]
                        if abs(last_move) > 4 and move != 0 and (move > 0) == (last_move > 0):
                            c += 1.2
                in_chord = (p % 12) in chord_pcs
                if not in_chord:
                    c += 3.2 * mw + 0.25
                    if i == 0 and entry_after_rest:
                        c += 2.2  # a dissonance out of silence has no preparation
                    if cn.dur >= 1.0:
                        c += 1.6
                    if prev is not None and abs(p - prev) > 2:
                        c += 1.1  # unprepared dissonance
                    # Minor-ninth clash against a chord tone on a strong beat.
                    if mw >= 0.5 and any((p - cp) % 12 == 1 for cp in chord_pcs):
                        c += 1.0
                c += 0.09 * abs(p - reg_target)
                if is_last and cadence_pcs is not None and (p % 12) not in set(cadence_pcs):
                    c += 6.0
                new_beam.append((cost + c, pitches + (p,), intended_idx))
        if not new_beam:
            # Register too narrow for the window: clamp and carry on.
            fallback = int(max(lo, min(hi, round(anchor))))
            new_beam = [(cost + 5.0, pitches + (fallback,), last_idx)
                        for cost, pitches, last_idx in beam]
        new_beam.sort(key=lambda e: (e[0], e[1]))
        beam = new_beam[:_BEAM]

    best_cost, best_pitches, _ = beam[0]
    notes = [
        Note(round(start + cn.onset, 4), cn.dur, p, cn.accent, cn.tech)
        for cn, p in zip(cell.notes, best_pitches)
    ]
    return notes, best_cost / max(1, n_notes)
