"""Controlled listener A/B and readable lead sheets.

Run from the repository root with .venv/bin/python tools/composer_review.py.
The two arms differ only in contextual listener scoring. This measures
heuristic exposure and existing musicality metrics, not listener preference.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import produzre.composer.lead as lead
from produzre.composer.theory import ChordMap
from tools.musicality import analyze


def run(seeds=24, sheets=False):
    rows = {"before": [], "after": []}
    original = lead.CONTEXT_WEIGHT
    try:
        for arm, weight in (("before", 0.0), ("after", original)):
            lead.CONTEXT_WEIGHT = weight
            for seed in range(seeds):
                for genre, key, mode, prog in (
                    ('rock', 'E', 'minor', ['i', 'bVI', 'bIII', 'bVII']),
                    ('pop', 'C', 'major', ['I', 'vi', 'IV', 'V']),
                    ('funk', 'D', 'minor', ['i', 'iv', 'bVII', 'V']),
                ):
                    comp = lead.SongComposer(seed=seed, genre=genre, key=key, mode=mode,
                                              beats_per_bar=4, register=(60, 79))
                    for bpb, rate in ((4.0, 4.0), (3.0, 1.5), (3.5, 2.0), (5.0, 3.0)):
                        total = 8 * bpb
                        slots = []
                        t = 0.0
                        while t < total:
                            slots.append(SimpleNamespace(start_beat=t, end_beat=min(t + rate, total),
                                                         numeral=prog[len(slots) % len(prog)]))
                            t += rate
                        ctx = lead.LeadContext('chorus', 'chorus', 0, False, 8, bpb, total,
                                                key, mode, slots, foreground='full', register=(60, 79))
                        notes = comp.compose_lead(ctx)
                        cm = ChordMap(slots, key, mode)
                        metrics = analyze([(n.beat, n.dur, n.pitch) for n in notes], bpb)
                        metrics['exposure'] = comp.listener.contextual_cost(notes, cm, bpb)
                        metrics['strong_chord_tones'] = sum(
                            n.pitch % 12 in cm.at(n.beat).pcs for n in notes
                            if abs(n.beat % bpb) < 1e-6) / max(1, sum(
                                abs(n.beat % bpb) < 1e-6 for n in notes))
                        rows[arm].append(metrics)
                        if sheets and seed == 0 and genre == 'rock':
                            print(f'{arm}: {genre}, {bpb:g} beats/bar, chord_rate={rate:g}')
                            for bar in range(8):
                                start, end = bar * bpb, (bar + 1) * bpb
                                chords = ' '.join(f'{max(start,s.start_beat)-start:g}:{s.numeral}'
                                                  for s in slots if s.end_beat > start and s.start_beat < end)
                                line = ' '.join(f'{n.beat-start:g}:{pitch_name(n.pitch)}/{n.dur:g}'
                                                for n in notes if start <= n.beat < end)
                                print(f'  {bar + 1}: [{chords}] {line}')
    finally:
        lead.CONTEXT_WEIGHT = original
    return {arm: {k: round(statistics.mean(r[k] for r in data), 6)
                  for k in data[0]} for arm, data in rows.items()}


def pitch_name(pitch):
    return ('C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B')[pitch % 12] + str(pitch // 12 - 1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seeds', type=int, default=24)
    parser.add_argument('--lead-sheets', action='store_true')
    args = parser.parse_args()
    print(json.dumps(run(args.seeds, args.lead_sheets), indent=2))
