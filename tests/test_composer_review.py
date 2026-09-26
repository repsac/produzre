"""Regressions for composer ownership, harmonic rhythm and performance."""
import random

import pytest

from tests.test_composer import _composer, _ctx, _slots, _song
from tests.test_groove_clock import _render_timelines
from produzre.composer.comping import CompRiff, riff_events
from produzre.composer.lead import PlanItem
from produzre.composer.theory import ChordMap
from produzre.engine.rhythm_gtr.composed import perform_comp
from produzre.engine.lead_gtr import _perform_composed
from produzre.timeline import InstrumentTimeline


def test_walk_targets_next_harmony_not_next_attack():
    riff = CompRiff('probe', ('rock',), 'low', 'w-x-x-x-x-x-x-x-', 1.0)
    cm = ChordMap(_slots(['I', 'IV']), 'C', 'major')
    assert riff_events(riff, 0, 4, cm)[0].target_pc == 5


def test_walk_does_not_inherit_arpeggio_index():
    riff = CompRiff('probe', ('rock',), 'low', 'a-a-w---X-------', 1.0)
    cm = ChordMap(_slots(['I', 'IV']), 'C', 'major')
    walk = next(e for e in riff_events(riff, 0, 4, cm) if e.kind == 'walk')
    assert walk.arp_index == 0


def test_power_shape_stays_above_low_e():
    tl = InstrumentTimeline('rhythm_gtr')
    perform_comp([dict(beat=0, dur=1, kind='power')], timeline=tl,
                 section_start_beat=0, shape_at=lambda b: ([50, 57, 62], [50, 57, 62], 'I'),
                 key='D', mode='major', intensity=.8, bpm=120, ring=1,
                 rng=random.Random(1), strum_ms=0, timing_jitter_ms=0)
    assert min(e.pitch for e in tl.events) >= 40


def test_guide_starts_inside_a_long_chord():
    comp = _composer()
    ctx = _ctx('c', 'chorus', 0, ['i'])
    cm = ChordMap(_slots(['i', 'iv'], bpb=6), 'E', 'minor')
    notes = comp._guide_line(PlanItem('guide', 4, end=8, anchor=70), ctx, cm, 60, 79, None)
    assert notes and notes[0].beat == 4


@pytest.mark.parametrize('name,value', [('phrase_len_bars', 1), ('theme_quote_rate', .9)])
def test_legacy_only_lead_controls_are_reported_not_obeyed(tmp_path, caplog, name, value):
    # Legacy-generator tuning does not choose a different part: the section
    # stays composed and the build says the setting is unused.
    import logging
    cfg = _song(tmp_path)
    cfg.raw['instruments']['lead_gtr']['params'][name] = value
    with caplog.at_level(logging.INFO):
        _, result = _render_timelines(cfg)
    assert result.performance_plan.get('composer.lead.chorus') is not None
    assert any(name in r.getMessage() and 'legacy generator' in r.getMessage()
               for r in caplog.records)


def test_composer_false_selects_the_legacy_lead(tmp_path):
    cfg = _song(tmp_path)
    cfg.raw['instruments']['lead_gtr']['params']['composer'] = False
    _, result = _render_timelines(cfg)
    assert result.performance_plan.get('composer.lead.chorus') is None


def _lead_notes(tmp_path, **params):
    cfg = _song(tmp_path)
    cfg.raw['instruments']['lead_gtr']['params'].update(params)
    timelines, result = _render_timelines(cfg)
    assert result.performance_plan.get('composer.lead.chorus') is not None
    return [e for e in timelines['lead_gtr'].events if e.kind != 'slide_grace']


def test_rest_probability_shapes_the_composed_line(tmp_path):
    assert len(_lead_notes(tmp_path, rest_probability=.9)) < len(_lead_notes(tmp_path))


def test_contour_style_shapes_the_composed_line(tmp_path):
    def mean_leap(ns):
        ns = sorted(ns, key=lambda e: e.start_beat)
        moves = [abs(b.pitch - a.pitch) for a, b in zip(ns, ns[1:])]
        return sum(moves) / len(moves)
    assert mean_leap(_lead_notes(tmp_path, contour_style='stepwise')) < \
        mean_leap(_lead_notes(tmp_path, contour_style='leaping'))


def test_zero_bend_rate_removes_composed_bends(tmp_path):
    notes = _lead_notes(tmp_path, bend_rate=0)
    assert not any(e.expression and 'bend_in' in e.expression for e in notes)


def test_slide_grace_is_monophonic_and_midi_safe():
    tl = InstrumentTimeline('lead_gtr')
    _perform_composed([dict(beat=0, duration_beats=1, pitch=60),
                       dict(beat=1, duration_beats=1, pitch=1, tech='slide')],
                      timeline=tl, section_start_beat=0, base_vel=90, intensity=.8,
                      solo=False, rng=random.Random(1), bpm=120, beats_per_bar=4,
                      vibrato_rate=0, dive_rate=0, swell_rate=0)
    notes = sorted(tl.events, key=lambda e: e.start_beat)
    assert all(0 <= e.pitch <= 127 for e in notes)
    assert all(a.start_beat + a.duration_beats <= b.start_beat + 1e-9
               for a, b in zip(notes, notes[1:]))


def test_groove_recall_distinguishes_top_level_settings(tmp_path, monkeypatch):
    import produzre.composer.groove_memory as gm
    cfg = _song(tmp_path)
    cfg.sections['chorus'].instruments['bass'].register = 'low'
    # Reuse the section type with a different engine register.
    import copy
    cfg.sections['other'] = copy.deepcopy(cfg.sections['chorus'])
    cfg.sections['other'].id = 'other'
    cfg.sections['other'].instruments['bass'].register = 'high'
    cfg.arrangement = ['chorus', 'other']
    calls = []
    original = gm.apply_groove_memory
    def spy(*args, **kwargs):
        if kwargs['instrument'] == 'bass':
            calls.append(kwargs['memory_key'])
        return original(*args, **kwargs)
    monkeypatch.setattr(gm, 'apply_groove_memory', spy)
    _render_timelines(cfg)
    assert len(calls) == 2 and calls[0] != calls[1]


@pytest.mark.parametrize('bpb', [3.0, 3.5, 5.0])
@pytest.mark.parametrize('bars', [1, 2, 7])
def test_short_and_odd_meter_sections(bpb, bars):
    comp = _composer()
    for st in ('verse', 'chorus', 'bridge', 'solo', 'outro'):
        ctx = _ctx(st, st, 0, ['i'], bars=bars, key='F#')
        ctx.beats_per_bar = bpb
        ctx.total_beats = bars * bpb
        ctx.chord_slots = _slots(['i', 'iv', 'V'] * (bars + 1), bpb=1.5)
        notes = comp.compose_lead(ctx)
        assert all(0 <= n.pitch <= 127 and 0 <= n.beat < ctx.total_beats
                   and n.beat + n.dur <= ctx.total_beats + 1e-6 for n in notes)
        assert all(a.beat + a.dur <= b.beat + 1e-6 for a, b in zip(notes, notes[1:]))


def test_explicit_numeric_register_is_not_widened():
    from types import SimpleNamespace as NS
    from produzre.composer.song import lead_register
    assert lead_register(NS(raw={}), NS(register=None, extra={'register': [60, 67]})) == (60, 67)


def test_contextual_listener_distinguishes_passing_and_exposed_notes():
    from produzre.composer.listener import Listener
    from produzre.composer.realize import Note
    ear = Listener()
    cm = ChordMap(_slots(['I', 'IV']), 'C', 'major')
    passing = [Note(.25, .25, 60), Note(.5, .25, 62), Note(.75, .25, 64)]
    exposed = [Note(0, .25, 62)]
    assert ear.contextual_cost(passing, cm, 4) < ear.contextual_cost(exposed, cm, 4)
    assert ear.contextual_cost([Note(0, 1, 60)], cm, 4) == 0
    # E is consonant over C, but a long hold crosses into F's harmony.
    assert ear.contextual_cost([Note(0, 6, 64)], cm, 4) > 0


def test_contextual_listener_does_not_mutate_interval_memory():
    from produzre.composer.listener import Listener
    from produzre.composer.realize import Note
    ear = Listener()
    before = ear.mean_information([60, 62, 64], [.5] * 3)
    for _ in range(3):
        ear.contextual_cost([Note(0, 1, 62)], ChordMap(_slots(['I']), 'C', 'major'), 4)
    assert ear.mean_information([60, 62, 64], [.5] * 3) == before


@pytest.mark.parametrize('st', ['chorus', 'solo'])
def test_numeric_register_bounds_survive_realization(st):
    comp = _composer()
    ctx = _ctx(st, st, 0, ['i', 'iv', 'V'])
    ctx.register = (60, 67)
    ctx.strict_register = True
    notes = comp.compose_lead(ctx)
    assert notes and all(60 <= n.pitch <= 67 for n in notes)


@pytest.mark.parametrize('bpb', [3, 3.5, 5])
def test_all_comp_riffs_fit_odd_meter(bpb):
    from produzre.composer.comping import RIFFS
    cm = ChordMap(_slots(['I', 'IV'], bpb=bpb), 'C', 'major')
    for riff in RIFFS:
        notes = riff_events(riff, 0, bpb, cm)
        assert notes and all(0 <= n.beat < bpb and n.beat + n.dur <= bpb + 1e-4 for n in notes)


def test_groove_signature_is_order_independent():
    from produzre.orchestrate.render import _groove_signature
    assert _groove_signature({'nested': {'a': 1, 'b': 2}, 'tags': {'x', 'y'}}) == \
        _groove_signature({'tags': {'y', 'x'}, 'nested': {'b': 2, 'a': 1}})


def test_dna_fitter_uses_section_key_and_meter(monkeypatch):
    from types import SimpleNamespace as NS
    from produzre.composer.song import build_song_composer
    import produzre.composer.lead as module
    observed = []
    original = module.realize_cell
    def spy(cell, start, chords, **kwargs):
        observed.append((chords.key, chords.mode, kwargs['beats_per_bar']))
        return original(cell, start, chords, **kwargs)
    monkeypatch.setattr(module, 'realize_cell', spy)
    hp = NS(chord_slots=_slots(['I', 'IV'], bpb=3.5), meter=NS(beats_per_bar=3.5))
    sec = NS(type='chorus', key='F#', mode='major')
    cfg = NS(raw={}, song=NS(key='E', mode='minor', beats_per_bar=4, seed=1, genre='rock'))
    build_song_composer(cfg, NS(planned_sections=[NS(sec=sec, harmony_plan=hp)]), None)
    assert observed and set(observed) == {('F#', 'major', 3.5)}


@pytest.mark.parametrize('params', [{'style': 'funk_chanks'}, {'pattern': 'offbeat'},
                                    {'sustain_mode': True}, {'recipe': 'rock'}])
def test_rhythm_part_selectors_keep_the_users_part(tmp_path, params):
    from tests.test_composer import _rhythm_song
    _, result = _render_timelines(_rhythm_song(tmp_path, params))
    assert result.performance_plan.get('composer.comp.verse') is None


def _comp_notes(tmp_path, params=None):
    from tests.test_composer import _rhythm_song
    timelines, result = _render_timelines(_rhythm_song(tmp_path, params))
    assert result.performance_plan.get('composer.comp.verse') is not None
    return timelines['rhythm_gtr'].events


@pytest.mark.parametrize('params', [{'voicing': 'octaves'}, {'humanize_velocity': 0},
                                    {'push_pull': .04}, {'accent_strength': 1.0}])
def test_rhythm_feel_controls_keep_composed_comping(tmp_path, params):
    assert _comp_notes(tmp_path, params)


def test_rhythm_density_thins_the_composed_part(tmp_path):
    assert len(_comp_notes(tmp_path, {'density': .1})) < len(_comp_notes(tmp_path))


def test_rhythm_palm_mute_turns_strums_into_chugs(tmp_path):
    kinds = [e.kind for e in _comp_notes(tmp_path, {'palm_mute': 1.0})]
    base = [e.kind for e in _comp_notes(tmp_path)]
    assert kinds.count('comp_chug') > base.count('comp_chug')


def test_realizer_uses_section_metric_position(monkeypatch):
    from produzre.composer import realize as module
    from produzre.composer.cells import Cell, CellNote
    seen = []
    original = module.metric_weight
    def spy(beat, bpb, groups=None):
        seen.append(beat)
        return original(beat, bpb, groups)
    monkeypatch.setattr(module, 'metric_weight', spy)
    module.realize_cell(Cell((CellNote(0, .5, 0),), 1), 1.5,
                        ChordMap(_slots(['I']), 'C', 'major'), key='C', mode='major',
                        lo=60, hi=79, anchor=70, beats_per_bar=4)
    assert seen == [1.5]


def test_transition_pass_keeps_composed_lead_monophonic():
    from produzre.config.load import load_root_config
    timelines, _ = _render_timelines(load_root_config('examples/composer/band_with_singer.yaml'))
    notes = sorted(timelines['lead_gtr'].events, key=lambda e: e.start_beat)
    assert all(a.start_beat + a.duration_beats <= b.start_beat + 1e-8
               for a, b in zip(notes, notes[1:]))


def test_midi_bytes_match_across_hash_seeds(tmp_path):
    import hashlib
    import os
    from pathlib import Path
    import subprocess
    import sys
    import yaml
    _song(tmp_path)
    path = tmp_path / 'song.yaml'
    data = yaml.safe_load(path.read_text())
    signatures = []
    for seed in ('1', '77'):
        export = tmp_path / ('export_' + seed)
        data['song']['exports_root'] = str(export)
        path.write_text(yaml.safe_dump(data, sort_keys=False))
        subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'produzre_entry.py'),
                        'build', str(path), '--no-export-sections', '--no-export-patterns'],
                       env={**os.environ, 'PYTHONHASHSEED': seed}, check=True, capture_output=True)
        signatures.append({p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in export.rglob('*.mid')})
    assert signatures[0] and signatures[0] == signatures[1]


def test_walk_pairs_stay_playable_and_ascend_in_low_keys():
    from produzre.engine.rhythm_gtr.composed import _walk_pitch
    for key in ('C', 'D', 'E', 'F#', 'Bb'):
        for mode in ('major', 'minor'):
            for target in range(12):
                lower = _walk_pitch(target, 1, 40, key, mode)
                leading = _walk_pitch(target, 0, 40, key, mode)
                assert 40 <= lower < leading
                assert (leading + 1) % 12 == target
