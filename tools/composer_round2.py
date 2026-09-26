"""Build a reproducible second-review matrix with section-aware measurements.

Run this same script in the before and after checkouts. It writes JSON metrics,
raw-event lead sheets and optional MIDI exports. No metric changes generation.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import yaml
import produzre.orchestrate.build as build
from produzre.config.load import load_root_config
from produzre.composer.song import section_groups
from produzre.composer.theory import ChordMap, metric_weight


def config(name, genre, meter, response, seed, foreground='full'):
    instruments = {'harmony': {}, 'drums': {}, 'bass': {}, 'rhythm_gtr': {}, 'lead_gtr': {}}
    return {'song': {'title': name, 'genre': genre, 'meter': meter, 'key': 'E', 'mode': 'minor',
                     'bpm': 120, 'seed': seed, 'final_chorus': 'modulate'},
            'instruments': {'lead_gtr': {'params': {'foreground': foreground}},
                            'bass': {'params': {'hook_response': response}}},
            'sections': {sid: {'type': sid, 'bars': 8, 'harmony': {'progression': 'i bVI bIII bVII'},
                               'instruments': instruments} for sid in ('chorus', 'verse')},
            'arrangement': ['chorus', 'verse', 'chorus']}


def inspect(cfg, export=False):
    captured, sections = {}, []
    sort, render = build._sort_used_timelines, build._render_section_instruments
    def collect(timelines, used):
        captured.update(timelines)
        return sort(timelines, used)
    def section(**kwargs):
        result = render(**kwargs)
        sec, hp, plan = kwargs['sec'], kwargs['hplan'], kwargs['performance_plan']
        sections.append((sec, hp, kwargs['section_start_beat'],
                         list(plan.get(f'groove.kick_beats.{sec.id}') or [])))
        return result
    build._sort_used_timelines, build._render_section_instruments = collect, section
    try:
        result = build.build_song(cfg=cfg, dry_run=not export, export_sections=False,
                                  export_patterns=False, sections_absolute_timing=False)
    finally:
        build._sort_used_timelines, build._render_section_instruments = sort, render
    totals = Counter()
    locks, signatures, sheets = [], set(), []
    for sec, hp, start, kicks in sections:
        bpb, length = hp.meter.beats_per_bar, hp.total_beats
        groups = section_groups(cfg, sec, hp.meter)
        boundaries, t = [], 0
        for group in groups:
            boundaries.append(t)
            t += group
        strong_positions = [step/4 for step in range(int(bpb*4))
                            if metric_weight(step/4,bpb,groups) >= .55]
        chords = ChordMap(hp.chord_slots, sec.key or cfg.song.key, sec.mode or cfg.song.mode)
        events = {inst: [e for e in tl.events if start <= e.start_beat < start + length]
                  for inst, tl in captured.items()}
        lead = sorted((e for e in events.get('lead_gtr', []) if e.kind != 'slide_grace'), key=lambda e:e.start_beat)
        bass = events.get('bass', [])
        rhythm = events.get('rhythm_gtr', [])
        for bar in range(int(length / bpb)):
            for boundary in boundaries[1:]:
                onset = start + bar * bpb + boundary
                totals['group_positions'] += 1
                totals['rhythm_group_hits'] += any(abs(e.start_beat - onset) < .08 for e in rhythm)
        for i, n in enumerate(lead):
            local = n.start_beat - start
            nearest = min((bar * bpb + b for bar in range(int(length / bpb)) for b in strong_positions),
                          key=lambda b:abs(b-local))
            if abs(nearest-local) > .08:
                continue
            totals['strong_lead'] += 1
            consonant = n.pitch % 12 in chords.at(nearest).pcs
            totals['strong_chord'] += consonant
            if not consonant:
                resolved = i + 1 < len(lead) and 0 < abs(lead[i+1].pitch-n.pitch) <= 2 and \
                    lead[i+1].pitch % 12 in chords.at(lead[i+1].start_beat-start).pcs
                totals['color_step_resolutions'] += resolved
                totals['held_unresolved_colors'] += not resolved and n.duration_beats > .75
        totals['bass_notes'] += len(bass)
        totals['bass_lead_collisions'] += sum(any(abs(e.start_beat-n.start_beat) < .1 for n in lead) for e in bass)
        totals['bass_kick_hits'] += sum(any(abs(e.start_beat-start-k) < .1 for k in kicks) for e in bass)
        ordered_bass = sorted(bass, key=lambda e:e.start_beat)
        totals['response_overlap_pairs'] += sum(a.start_beat+a.duration_beats > b.start_beat+1e-6
            and (a.kind=='hook_response' or b.kind=='hook_response') for a,b in zip(ordered_bass,ordered_bass[1:]))
        answers = sorted((e for e in bass if e.kind == 'hook_response'), key=lambda e:e.start_beat)
        totals['answer_notes'] += len(answers)
        runs = {}
        for e in answers:
            runs.setdefault(int((e.start_beat-start+.02)//(4*bpb)), []).append(e)
        for run in runs.values():
            signatures.add(tuple((round((e.start_beat-run[0].start_beat)*12)/12, e.pitch-run[0].pitch) for e in run))
        rhythms = Counter(tuple(sorted({round((e.start_beat-start-bar*bpb)*12)/12
                                        for e in bass if bar*bpb <= e.start_beat-start < (bar+1)*bpb}))
                          for bar in range(int(length/bpb)))
        locks.append(max(rhythms.values(),default=0)/max(1,sum(rhythms.values())))
        if len(sheets) < 28:
            sheets.append(f'{sec.id}: {chords.key} {chords.mode}, {hp.meter}, groups={groups}')
            for bar in range(min(4,int(length/bpb))):
                a,b=bar*bpb,(bar+1)*bpb
                harmony=' '.join(f'{max(a,s.start)-a:g}:{s.numeral}' for s in chords.spans if s.end>a and s.start<b)
                def line(ns):
                    return ' '.join(f'{e.start_beat-start-a:.2f}:{e.pitch}/{e.duration_beats:.2f}'
                                    for e in ns if a<=e.start_beat-start<b)
                sheets.append(f'  bar {bar+1} [{harmony}] lead {line(lead)} | bass {line(bass)}')
    counts=dict(totals)
    def ratio(a,b): return totals[a]/max(1,totals[b])
    counts.update(rhythm_group_coverage=ratio('rhythm_group_hits','group_positions'),
                  strong_chord_fraction=ratio('strong_chord','strong_lead'),
                  kick_alignment=ratio('bass_kick_hits','bass_notes'),
                  collision_fraction=ratio('bass_lead_collisions','bass_notes'),
                  groove_lock=sum(locks)/max(1,len(locks)), response_shapes=len(signatures))
    return counts, sheets, result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seeds', type=int, default=4)
    parser.add_argument('--export', action='store_true')
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(level=logging.ERROR)
    matrix={}
    sheets=[]
    profiles=[('blues12','blues','12/8'), ('blues9','blues','9/8'), ('rock7','rock','7/8'),
              ('rock5','rock','5/4'), ('rock58','rock','5/8'), ('rock118','rock','11/8'),
              ('funk4','funk','4/4'), ('soul4','soul','4/4'), ('rock4','rock','4/4')]
    for name,genre,meter in profiles:
        for mode in (False,True,'develop'):
            for seed in range(args.seeds):
                title=f'{name}_{mode}_{seed}'
                data=config(title,genre,meter,mode,seed)
                data['song']['exports_root']=str(args.output/'midi')
                path=args.output/(title+'.yaml')
                path.write_text(yaml.safe_dump(data,sort_keys=False))
                stats, lines, result=inspect(load_root_config(str(path)),args.export and seed==0)
                if result.export_root:
                    stats['export_root']=result.export_root
                matrix[title]=stats
                if seed==0:
                    sheets.extend([title]+lines+[''])
    (args.output/'metrics.json').write_text(json.dumps(matrix,indent=2)+'\n')
    (args.output/'lead-sheets.txt').write_text('\n'.join(sheets))
    print(f'{len(matrix)} builds measured in {args.output}')


if __name__=='__main__':
    main()
