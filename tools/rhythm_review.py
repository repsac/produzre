"""Rendered rhythm-section audit, with gesture counts instead of string counts.

Run before and after a change with --out pointing to separate directories.
The JSON includes every bar, planned accents matched to performed attacks,
actual drum onsets, harmony, and sustained cross-part interval candidates.
An accent is a gesture at least 90 percent of its bar's peak MIDI velocity;
alignment uses a 0.1 beat tolerance. This is a diagnostic, not a preference test.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import json
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import yaml
import produzre.orchestrate.build as build
from produzre.config.load import load_root_config
from produzre.composer.theory import ChordMap
from produzre.composer.song import section_groups
from tools.album_diversity import album_configs


def part_summaries(rows):
    """Coverage and dynamics expose sparse solos that similarity alone rewards."""
    out = {}
    instruments = sorted({i for r in rows for i in r.get('parts', {}) if i != 'harmony'})
    for inst in instruments:
        out[inst] = {}
        for st in sorted({r['type'] for r in rows}):
            selected = [r for r in rows if r['type'] == st]
            notes = [n for r in selected for n in r['parts'].get(inst, [])]
            out[inst][st] = dict(bars=len(selected), notes=len(notes),
                attack_bars=sum(bool(r['parts'].get(inst)) for r in selected),
                mean_velocity=round(sum(n[3] for n in notes)/max(1,len(notes)),2),
                register=[min((n[1] for n in notes), default=0), max((n[1] for n in notes), default=0)])
    return out


def inspect(cfg):
    captured, sections = {}, []
    sort, render = build._sort_used_timelines, build._render_section_instruments

    def collect(timelines, used):
        captured.update(timelines)
        return sort(timelines, used)

    def section(**kw):
        result = render(**kw)
        sec, plan = kw['sec'], kw['performance_plan']
        sections.append((sec, kw['hplan'], kw['section_start_beat'],
                         deepcopy(plan.get(f'composer.comp.{sec.id}') or {})))
        return result

    build._sort_used_timelines, build._render_section_instruments = collect, section
    try:
        result = build.build_song(cfg=cfg, dry_run=False, export_sections=False,
                                  export_patterns=False, sections_absolute_timing=False)
    finally:
        build._sort_used_timelines, build._render_section_instruments = sort, render
    rows = []
    for occurrence, (sec, hp, start, comp) in enumerate(sections):
        bpb = hp.meter.beats_per_bar
        chords = ChordMap(hp.chord_slots, sec.key or cfg.song.key, sec.mode or cfg.song.mode)
        groups = section_groups(cfg, sec, hp.meter) or (bpb,)
        for bar in range(round(hp.total_beats / bpb)):
            a, z = start + bar * bpb, start + (bar + 1) * bpb
            ns = {inst: [e for e in tl.events if a - .06 <= e.start_beat < z - .06]
                  for inst, tl in captured.items()}
            guitar = sorted(ns.get('rhythm_gtr', []), key=lambda e: e.start_beat)
            gestures = []
            for e in guitar:
                if not gestures or e.start_beat - gestures[-1][0].start_beat > .075 or e.kind != gestures[-1][0].kind:
                    gestures.append([e])
                else:
                    gestures[-1].append(e)
            drum = [e.start_beat for e in ns.get('drums', [])
                    if e.pitch in (35, 36, 37, 38, 40) and 'ghost' not in (e.kind or '')]
            bass = ns.get('bass', [])
            planned = [e for e in comp.get('events', []) if bar*bpb <= e['beat'] < (bar+1)*bpb]
            planned_accents = [g[0].start_beat for g in gestures if any(
                p['accent'] and abs(g[0].start_beat - start - p['beat']) < .1 for p in planned)]
            attacks = [g[0].start_beat for g in gestures]
            peak = max((max(e.velocity for e in g) for g in gestures), default=0)
            accents = [g[0].start_beat for g in gestures if max(e.velocity for e in g) >= .9*peak
                       and 'chuck' not in g[0].kind]
            off = [t for t in accents if abs((t-a)-round(t-a)) > .1]
            near_misses = [t for t in off if not any(abs(t-d) < .1 for d in drum)
                           and any(.1 <= abs(t-d) <= .3 for d in drum)]
            clashes = []
            sounding_notes = {inst: [e for e in tl.events if e.start_beat < z and
                              e.start_beat + e.duration_beats > a]
                              for inst, tl in captured.items()}
            for inst in ('bass', 'lead_gtr'):
                for g in sounding_notes.get('rhythm_gtr', []):
                    for n in sounding_notes.get(inst, []):
                        overlap = min(g.start_beat+g.duration_beats,n.start_beat+n.duration_beats)-max(g.start_beat,n.start_beat)
                        # Assign cross-bar exposure to the bar where the overlap starts.
                        onset = max(g.start_beat, n.start_beat)
                        if a - .06 <= onset < z - .06 and overlap >= .5 and (g.pitch-n.pitch)%12 in (1,6,11):
                            clashes.append([inst, round(max(g.start_beat,n.start_beat)-a,3),g.pitch,n.pitch,round(overlap,3)])
            figure = [(round((g[0].start_beat-a)*4)/4,g[0].kind) for g in gestures]
            intervals = sorted((max(a,e.start_beat),min(z,e.start_beat+e.duration_beats))
                               for e in guitar)
            end, sounding = a, 0.0
            for left,right in intervals:
                sounding += max(0,right-max(end,left))
                end = max(end,right)
            boundaries = [a+sum(groups[:i]) for i in range(len(groups))]
            rows.append(dict(section=sec.id, type=sec.type, occurrence=occurrence+1, bar=bar+1,
                absolute_bar=round(a/bpb)+1, harmony=chords.at(bar*bpb).numeral,
                attacks=len(attacks), accents=len(accents), locked=sum(any(abs(t-d)<.1 for d in drum) for t in accents),
                near_misses=len(near_misses), bass_lock=sum(any(abs(t-e.start_beat)<.1 for e in bass) for t in attacks),
                attack_lock=sum(any(abs(t-d)<.1 for d in drum) for t in attacks),
                planned_accents=len(planned_accents), silent_beats=round(max(0,bpb-sounding),3),
                group_hits=sum(any(abs(t-b)<.1 for t in attacks) for b in boundaries), groups=len(groups),
                tail_lead_attacks=sum(any(abs(g[0].start_beat-n.start_beat)<.1 for n in ns.get('lead_gtr',[]))
                                      for g in gestures if 'rsingle' in g[0].kind),
                device=any('fill' in e.kind or 'stop' in e.kind for e in guitar),
                tail=any('rsingle' in e.kind for e in guitar),
                slides=sum(g[0].kind.endswith('slide') for g in gestures),
                walks=sum(g[0].kind.endswith('walk') for g in gestures),
                choked=sum(max(e.duration_beats for e in g)<.25 for g in gestures),
                sustained=sum(max(e.duration_beats for e in g)>=.75 for g in gestures),
                mean_velocity=round(sum(e.velocity for e in guitar)/max(1,len(guitar)),2),
                figure=figure, drums=[round(t-a,3) for t in drum],
                guitar=[[round(g[0].start_beat-a,3),[e.pitch for e in g],g[0].kind,round(max(e.duration_beats for e in g),3)] for g in gestures],
                bass=[[round(e.start_beat-a,3),e.pitch,e.kind] for e in bass], clashes=clashes,
                parts={inst:[[round(e.start_beat-a,3),e.pitch,round(e.duration_beats,3),e.velocity,e.kind]
                             for e in es] for inst,es in ns.items()}))
    summaries = {}
    for st in sorted({r['type'] for r in rows}):
        selected=[r for r in rows if r['type']==st]
        totals={k:sum(r[k] for r in selected) for k in ('attacks','accents','locked','near_misses','device','tail','slides','walks','choked','sustained','bass_lock','attack_lock','silent_beats','group_hits','groups','tail_lead_attacks')}
        totals['bars']=len(selected)
        totals['figure_bars']=sum(sum(n for _,n in Counter(
            tuple(tuple(x) for x in r['figure']) for r in selected if r['occurrence']==occ
        ).most_common(2)) for occ in {r['occurrence'] for r in selected})
        totals['pocket']=round(totals['locked']/max(1,totals['accents']),4)
        summaries[st]=totals
    return dict(summary=summaries,parts=part_summaries(rows),bars=rows,export=str(getattr(result,'export_root','')),result=str(result))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--genre')
    ap.add_argument('--songs',type=int,default=10)
    ap.add_argument('--configs',nargs='+',type=Path)
    args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    configs=album_configs('hard_rock',10)
    sparse=deepcopy(configs[0])
    sparse['song'].update(title='restrained_hard_rock',arrangement_style={'comp_activity':'sparse'})
    configs.append(sparse)
    for path in sorted(Path('examples/composer').glob('*.yaml')):
        cfg=yaml.safe_load(path.read_text())
        cfg['song']['title']=path.stem
        configs.append(cfg)
    for genre,meter in [('pop','4/4'),('punk','4/4'),('blues','12/8'),('rock','6/8'),('rock','7/8')]:
        cfg=deepcopy(configs[0])
        cfg['song'].update(title=f'{genre}_{meter.replace("/","_")}',genre=genre,meter=meter)
        if meter in ('6/8','7/8'):
            cfg['song']['arrangement_style']={'riff_driven':True,'bass_doubles':True}
        configs.append(cfg)
    if args.genre:
        configs=album_configs(args.genre,args.songs)
    if args.configs:
        configs=[yaml.safe_load(p.read_text()) for p in args.configs]
    data={}
    for cfg in configs:
        title=cfg['song']['title'].replace(' ','_')
        cfg['song']['exports_root']=str(args.out.resolve()/'renders')
        path=args.out/f'{title}.yaml'
        path.write_text(yaml.safe_dump(cfg,sort_keys=False))
        data[title]=inspect(load_root_config(str(path)))
        print(title,data[title]['summary'].get('verse'),flush=True)
        (args.out/'metrics.json').write_text(json.dumps(data,indent=2))


if __name__=='__main__':
    logging.basicConfig(level=logging.ERROR)
    main()
