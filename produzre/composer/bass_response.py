"""Bass responses: the bass answers the lead with the hook's own rhythm.

In a band with character the bass does not only lock to the kick; when the
melody holds or breathes after a phrase, the bass answers in that hole. The
answer quotes the song's hook, its rhythmic signature (the first few
attacks) and its contour (diatonic steps), moved to the bass register over
the current chord and landing on a chord tone. Elsewhere the kick-locked
groove is untouched.

A response only answers a call: it fills holes of 1.25-4 beats that follow
lead activity, never whole silent bars (so a vocal-song verse keeps its
groove), and it starts half a beat after the lead's last attack so the held
note is heard before the answer. Deterministic; no randomness.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from .cells import Cell
from .theory import ChordMap, diatonic_index, diatonic_pitch, tonic_pc

MIN_HOLE = 1.25
MAX_HOLE = 4.0
MAX_NOTES = 4


@dataclass(frozen=True)
class BassNote:
    beat: float
    dur: float
    pitch: int


def phrase_holes(holes: Sequence[Tuple[float, float]], beats_per_bar: float,
                 total: float, phrase_bars: int = 4) -> List[Tuple[float, float]]:
    """One answer per phrase, at its end: an answer on every hole would turn
    the bass into a second lead and erode the groove. Each phrase answers in
    its last hole; the section's final bar may always answer."""
    if beats_per_bar <= 0:
        return list(holes)
    last_bar = int(total // beats_per_bar) - 1
    chosen: dict = {}
    for h in holes:
        bar = int((h[0] + 1e-6) // beats_per_bar)
        chosen[bar // phrase_bars] = h          # later holes in a phrase win
        if bar == last_bar:
            chosen[("end", bar)] = h
    return sorted(set(chosen.values()))


def align_to_kicks(holes: Sequence[Tuple[float, float]],
                   kicks: Sequence[float]) -> List[Tuple[float, float]]:
    """Start an answer on a kick near the hole's opening, so the groove's
    anchor stays under the fill."""
    out = []
    for start, end in holes:
        near = [k for k in kicks if start - 0.25 <= k <= start + 0.5 and k < end - 0.75]
        if near:
            start = min(near, key=lambda k: (abs(k - start), k))
        out.append((start, end))
    return out


def lead_holes(lead: Sequence[Tuple[float, float]], total: float) -> List[Tuple[float, float]]:
    """Windows after a lead attack with no new attack for 1.25-4 beats.

    ``lead`` holds (beat, duration) pairs. A hole opens half a beat after an
    attack (the call is heard first) and closes a quarter beat before the
    next one.
    """
    attacks = sorted(b for b, _ in lead)
    holes = []
    for i, a in enumerate(attacks):
        nxt = attacks[i + 1] if i + 1 < len(attacks) else total
        gap = nxt - a
        if MIN_HOLE + 0.5 <= gap <= MAX_HOLE + 0.5:
            start, end = a + 0.5, min(nxt - 0.25, total)
            if end - start >= 0.75:
                holes.append((start, end))
    return holes


def _signature(hook: Cell, room: float) -> List[Tuple[float, float, int]]:
    """The hook's opening (onset, duration, step) that fits in ``room``."""
    notes = [n for n in hook.notes]
    if not notes:
        return []
    base = notes[0].onset
    out = []
    for n in notes[:MAX_NOTES]:
        onset = n.onset - base
        if onset >= room - 0.2:
            break
        out.append((onset, n.dur, n.step if out else 0))
    # Each note lasts until the next attack, the last until the window ends.
    fitted = []
    for i, (o, d, s) in enumerate(out):
        end = out[i + 1][0] if i + 1 < len(out) else room
        fitted.append((o, max(0.2, min(d, end - o) - 0.02), s))
    return fitted


def respond(
    hook: Cell,
    holes: Sequence[Tuple[float, float]],
    chords: ChordMap,
    *,
    key: str,
    mode: str,
    reference: Optional[int] = None,
    lo: int = 28,
    hi: int = 55,
) -> List[BassNote]:
    """Answer every hole with the hook's signature, chord-relatively."""
    out: List[BassNote] = []
    tonic = tonic_pc(key)
    for start, end in holes:
        sig = _signature(hook, end - start)
        if len(sig) < 2:
            continue
        span = chords.at(start)
        if span is None:
            continue
        near = reference if reference is not None else 40
        root = min((p for p in range(lo, hi + 1) if p % 12 == span.root_pc),
                   key=lambda p: (abs(p - near), p), default=near)
        idx = diatonic_index(root, key, mode)
        pitches = []
        for k, (_, _, step) in enumerate(sig):
            idx = round(idx) + (step if k else 0)
            pitches.append(diatonic_pitch(int(idx), key, mode, tonic))
        # Land on a chord tone of the chord sounding at the last note.
        last_span = chords.at(start + sig[-1][0]) or span
        if pitches[-1] % 12 not in last_span.pcs:
            pitches[-1] = min((p for p in range(pitches[-1] - 2, pitches[-1] + 3)
                               if p % 12 in last_span.pcs),
                              key=lambda p: (abs(p - pitches[-1]), p), default=pitches[-1])
        for (o, d, _), p in zip(sig, pitches):
            while p < lo:
                p += 12
            while p > hi:
                p -= 12
            out.append(BassNote(round(start + o, 4), d, p))
    return out
