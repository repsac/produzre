"""Musicality benchmark: structural metrics for melodic lines.

Measures the properties that separate composed melodies from procedural
noodling, so changes to the composition engines can be judged by numbers
instead of taste alone. Works on any MIDI file: human reference material
(the melody is taken as the skyline of all pitched tracks) or a Produzre
stem (pass ``--track`` to pick one track).

Metrics:
    step_ratio       Fraction of intervals that are steps (<= 2 semitones).
    leap_recovery    After a leap (> 4 semitones), fraction answered by a
                     step in the opposite direction.
    exact_repeat     Fraction of 2-bar windows that repeat an earlier window
                     (similarity >= 0.9).
    varied_repeat    Fraction of windows that vary an earlier window
                     (0.5 <= similarity < 0.9): repetition with variation.
    novel            Fraction of windows unlike anything earlier.
    rhythm_recur     Fraction of bars whose onset pattern appeared before.
    self_ic          Mean information content (bits) of each interval under
                     an order-2 model trained only on the melody so far. Low
                     means predictable, high means random.
    ic_spread        Standard deviation of IC: human music alternates
                     settled and surprising moments.
    climax_share     Fraction of 2-bar windows reaching the global peak
                     pitch. Composed melodies save the peak for few moments.

Usage:
    python tools/musicality.py FILE.mid [FILE.mid ...] [--track NAME]
    python tools/musicality.py --corpus DIR           # summary over a folder
"""

from __future__ import annotations

import argparse
import difflib
import glob
import math
import os
import statistics
import sys
from collections import defaultdict
from typing import Dict, List, Optional, Sequence, Tuple

import mido
import mido.midifiles.meta as _mido_meta


class _LenientKeys(dict):
    """Decode out-of-range key signatures (common in DAW exports) as C."""

    def __missing__(self, key):
        return "C"


_mido_meta._key_signature_decode = _LenientKeys(_mido_meta._key_signature_decode)

Note = Tuple[float, float, int]  # (start_beat, dur_beats, pitch)


def _track_notes(trk, tpb: int) -> List[Note]:
    notes: List[Note] = []
    tick = 0
    active: Dict[Tuple[int, int], int] = {}
    for msg in trk:
        tick += msg.time
        if msg.type not in ("note_on", "note_off") or msg.channel == 9:
            continue
        key = (msg.channel, msg.note)
        if msg.type == "note_on" and msg.velocity > 0:
            active[key] = tick
        elif key in active:
            start = active.pop(key)
            notes.append((start / tpb, max(1, tick - start) / tpb, msg.note))
    return sorted(notes)


def _skyline(notes: Sequence[Note]) -> List[Note]:
    by_onset: Dict[float, Note] = {}
    for n in notes:
        k = round(n[0] * 4) / 4
        if k not in by_onset or n[2] > by_onset[k][2]:
            by_onset[k] = (k, n[1], n[2])
    return [by_onset[k] for k in sorted(by_onset)]


def _monophony(notes: Sequence[Note]) -> float:
    onsets: Dict[float, int] = defaultdict(int)
    for n in notes:
        onsets[round(n[0] * 4) / 4] += 1
    return sum(1 for c in onsets.values() if c == 1) / max(1, len(onsets))


def load_melody(path: str, track: Optional[str] = None,
                strict: bool = False) -> Tuple[List[Note], int]:
    """Return a monophonic melody line and beats per bar.

    With ``track`` the named track is used. Otherwise the melody is the
    highest mostly-monophonic track (>= 70% single-note onsets, >= 40 notes);
    ``strict`` returns an empty line when no such track exists instead of
    falling back to the skyline of every track.
    """
    mid = mido.MidiFile(path)
    tpb = mid.ticks_per_beat or 480
    bpb = 4
    for trk in mid.tracks:
        for msg in trk:
            if msg.type == "time_signature":
                bpb = int(msg.numerator * 4 / msg.denominator) or 4
                break
    tracks = [(trk.name or "", _track_notes(trk, tpb)) for trk in mid.tracks]
    if track is not None:
        chosen = [n for name, ns in tracks if track.lower() in name.lower() for n in ns]
        return _skyline(chosen), bpb
    candidates = [
        ns for _, ns in tracks
        if len(ns) >= 40 and _monophony(ns) >= 0.7
    ]
    if candidates:
        best = max(candidates, key=lambda ns: statistics.fmean(n[2] for n in ns))
        return _skyline(best), bpb
    if strict:
        return [], bpb
    return _skyline([n for _, ns in tracks for n in ns]), bpb


def _tokens(window: Sequence[Note], start: float) -> List[Tuple[float, int]]:
    """Transposition-invariant (onset, interval-from-first) tokens."""
    if not window:
        return []
    ref = window[0][2]
    return [(round((n[0] - start) * 4) / 4, n[2] - ref) for n in window]


def _similarity(a, b) -> float:
    if not a and not b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def _order2_ic(intervals: Sequence[int]) -> List[float]:
    """Incremental order-2 interval model with order-1/0 backoff (PPM-like)."""
    alphabet = 25  # intervals clipped to +/-12
    c2: Dict[Tuple[int, int], Dict[int, int]] = defaultdict(lambda: defaultdict(int))
    c1: Dict[int, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
    c0: Dict[int, int] = defaultdict(int)
    ics = []
    hist: List[int] = []
    for iv in intervals:
        iv = max(-12, min(12, iv))
        p0 = (c0[iv] + 1) / (sum(c0.values()) + alphabet)
        p = p0
        if hist:
            d1 = c1[hist[-1]]
            n1 = sum(d1.values())
            if n1:
                p = (d1[iv] + p0 * 2) / (n1 + 2)
        if len(hist) >= 2:
            d2 = c2[(hist[-2], hist[-1])]
            n2 = sum(d2.values())
            if n2:
                p = (d2[iv] + p * 2) / (n2 + 2)
        ics.append(-math.log2(max(p, 1e-9)))
        if len(hist) >= 2:
            c2[(hist[-2], hist[-1])][iv] += 1
        if hist:
            c1[hist[-1]][iv] += 1
        c0[iv] += 1
        hist.append(iv)
    return ics


def analyze(notes: Sequence[Note], bpb: int = 4) -> Dict[str, float]:
    notes = sorted(notes)
    if len(notes) < 8:
        return {}
    pitches = [n[2] for n in notes]
    ivs = [b - a for a, b in zip(pitches, pitches[1:])]
    moves = [i for i in ivs if i != 0] or [0]
    step_ratio = sum(1 for i in moves if abs(i) <= 2) / len(moves)

    leaps = recov = 0
    for a, b in zip(ivs, ivs[1:]):
        if abs(a) > 4:
            leaps += 1
            if b != 0 and (b > 0) != (a > 0) and abs(b) <= 2:
                recov += 1
    leap_recovery = recov / leaps if leaps else 1.0

    win = 2 * bpb
    end = notes[-1][0] + notes[-1][1]
    windows = []
    t = math.floor(notes[0][0] / win) * win
    while t < end:
        w = [n for n in notes if t <= n[0] < t + win]
        if len(w) >= 2:
            windows.append((_tokens(w, t), max(n[2] for n in w)))
        t += win
    exact = varied = novel = 0
    for i, (tok, _) in enumerate(windows):
        best = max((_similarity(tok, windows[j][0]) for j in range(i)), default=0.0)
        if i == 0:
            continue
        if best >= 0.9:
            exact += 1
        elif best >= 0.5:
            varied += 1
        else:
            novel += 1
    total = max(1, exact + varied + novel)
    peak = max(pitches)
    climax_share = sum(1 for _, top in windows if top == peak) / max(1, len(windows))

    bars = defaultdict(list)
    for n in notes:
        bars[int(n[0] // bpb)].append(round((n[0] % bpb) * 4) / 4)
    seen = set()
    recur = 0
    for b in sorted(bars):
        sig = tuple(sorted(set(bars[b])))
        if sig in seen:
            recur += 1
        seen.add(sig)
    rhythm_recur = recur / max(1, len(bars))

    ics = _order2_ic(ivs)
    return {
        "notes": float(len(notes)),
        "step_ratio": step_ratio,
        "leap_recovery": leap_recovery,
        "exact_repeat": exact / total,
        "varied_repeat": varied / total,
        "novel": novel / total,
        "rhythm_recur": rhythm_recur,
        "self_ic": statistics.fmean(ics),
        "ic_spread": statistics.pstdev(ics),
        "climax_share": climax_share,
    }


KEYS = ("step_ratio", "leap_recovery", "exact_repeat", "varied_repeat", "novel",
        "rhythm_recur", "self_ic", "ic_spread", "climax_share")


def summarize(rows: Sequence[Dict[str, float]]) -> Dict[str, Tuple[float, float]]:
    out = {}
    for k in KEYS:
        vals = [r[k] for r in rows if k in r]
        if vals:
            out[k] = (statistics.median(vals), statistics.pstdev(vals))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("files", nargs="*")
    ap.add_argument("--track", default=None, help="Track-name substring to analyze.")
    ap.add_argument("--corpus", default=None, help="Folder of reference MIDI files.")
    args = ap.parse_args(argv)

    if args.corpus:
        rows = []
        for f in sorted(glob.glob(os.path.join(args.corpus, "**", "*.mid"), recursive=True)):
            try:
                notes, bpb = load_melody(f, strict=True)
                r = analyze(notes, bpb)
            except Exception:
                continue
            if r:
                rows.append(r)
        print(f"corpus: {len(rows)} files")
        for k, (med, sd) in summarize(rows).items():
            print(f"  {k:14s} median {med:6.3f}  sd {sd:5.3f}")
        return 0

    for f in args.files:
        notes, bpb = load_melody(f, args.track)
        r = analyze(notes, bpb)
        print(os.path.basename(f))
        for k in ("notes",) + KEYS:
            if k in r:
                print(f"  {k:14s} {r[k]:6.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
