"""Second composer review: grouping, configuration ownership and bass answers."""
from dataclasses import replace
from types import SimpleNamespace as NS
import random

import pytest

from produzre.composer.bass_response import respond
from produzre.composer.cells import Cell, CellNote, cell_from
from produzre.composer.comping import CompRiff, riff_events
from produzre.composer.theory import ChordMap, meter_groups
from tests.test_composer import _composer, _ctx, _slots


@pytest.mark.parametrize('num', [6, 9, 12])
def test_shuffle_riffs_sound_each_compound_pulse(num):
    groups = meter_groups(num, 8)
    bpb = num / 2
    riff = CompRiff('shuffle', ('blues',), 'low', 'q-Qq-Qq-Qq-Q', 1)
    notes = riff_events(riff, 0, bpb, ChordMap(_slots(['I'], bpb=bpb), 'C', 'major'), groups=groups)
    assert all(any(abs(n.beat - 1.5 * i) < 1e-4 for n in notes) for i in range(num // 3))


def test_grouping_change_does_not_recall_old_realization():
    comp = _composer()
    ctx = _ctx('c', 'chorus', 0, ['i', 'iv'])
    ctx.beats_per_bar, ctx.total_beats = 3, 24
    ctx.chord_slots = _slots(['i', 'iv'] * 4, bpb=3)
    ctx.groups = (1, 1, 1)
    comp.compose_lead(ctx)
    comp.compose_lead(replace(ctx, occurrence=1, groups=(1.5, 1.5)))
    assert len(comp._realized) == 2


def test_authored_bass_response_keeps_chromatic_contour():
    # Authored cells encode pitches as degrees; their step fields are zero.
    hook = Cell((CellNote(0, .5, 0, degree=0), CellNote(.5, .5, 0, degree=3, alter=1),
                 CellNote(1, 1, 0, degree=4)), 2)
    notes = respond(hook, [(0, 2)], ChordMap(_slots(['I']), 'C', 'major'),
                    key='C', mode='major', reference=36)
    assert [n.pitch % 12 for n in notes] == [0, 6, 7]


def test_bass_response_respects_narrow_register():
    hook = cell_from([.5, .5, .5], [0, 4, -1])
    notes = respond(hook, [(0, 2)], ChordMap(_slots(['I']), 'C', 'major'),
                    key='C', mode='major', reference=42, lo=40, hi=44)
    assert notes and all(40 <= n.pitch <= 44 for n in notes)


def test_fast_bass_signature_is_monophonic():
    hook = cell_from([.125] * 4, [0, 1, 1, 1])
    notes = respond(hook, [(0, 2)], ChordMap(_slots(['I']), 'C', 'major'), key='C', mode='major')
    assert all(a.beat + a.dur <= b.beat + 1e-6 for a, b in zip(notes, notes[1:]))


def test_nested_lead_register_overrides_persona():
    from produzre.composer.song import lead_register
    part = NS(register=None, extra={'register': 'high', '_persona_keys': ['register'],
                                    'extra': {'register': [60, 67]}})
    assert lead_register(NS(raw={}), part) == (60, 67)


def test_zero_rhythm_timing_field_reaches_composed_performer(tmp_path, monkeypatch):
    from tests.test_composer import _rhythm_song
    from tests.test_groove_clock import _render_timelines
    import produzre.engine.rhythm_gtr.composed as module
    cfg = _rhythm_song(tmp_path)
    cfg.sections['verse'].instruments['rhythm_gtr'].humanize_timing = 0
    seen = []
    original = module.perform_comp
    def spy(*args, **kwargs):
        seen.append(kwargs['timing_jitter_ms'])
        return original(*args, **kwargs)
    monkeypatch.setattr(module, 'perform_comp', spy)
    _render_timelines(cfg)
    assert seen[0] == 0


def test_explicit_rhythm_voicing_changes_sounding_part(tmp_path):
    from tests.test_composer_review import _comp_notes
    signature = lambda ns: [(n.start_beat, n.pitch, n.duration_beats) for n in ns]
    assert signature(_comp_notes(tmp_path, {'voicing': 'octaves'})) != signature(_comp_notes(tmp_path))


def test_composed_gestures_keep_explicit_rhythm_register():
    from produzre.engine.rhythm_gtr.composed import perform_comp
    from produzre.timeline import InstrumentTimeline
    tl = InstrumentTimeline('rhythm_gtr')
    perform_comp([dict(beat=i, dur=.5, kind=k) for i,k in enumerate(('power','root','walk','dyad7'))],
                 timeline=tl, section_start_beat=0,
                 shape_at=lambda b: ([60,64,67,72], [60,67,72], 'I'),
                 key='C', mode='major', intensity=.8, bpm=120, ring=1, rng=random.Random(1),
                 feel={'register_min':60,'register_max':72})
    assert tl.events and all(60 <= n.pitch <= 72 for n in tl.events)


def test_octave_voicing_is_not_a_power_chord(tmp_path):
    from tests.test_composer_review import _comp_notes
    notes = _comp_notes(tmp_path, {'voicing': 'octaves'})
    chords = {}
    for n in notes:
        if n.kind in ('comp_strum', 'comp_slide', 'comp_riff_rpower', 'comp_riff_rchug'):
            chords.setdefault(round(n.start_beat, 1), set()).add(n.pitch % 12)
    # Octave voicing: every chord gesture sounds one pitch class, never a fifth.
    assert chords and all(len(pcs) == 1 for pcs in chords.values())


def test_meter_view_rephrases_the_hook_in_new_groups():
    comp = _composer(seed=0)
    ctx = _ctx('c', 'chorus', 0, ['i'])
    ctx.beats_per_bar, ctx.total_beats, ctx.groups = 3, 24, (1.5, 1.5)
    ctx.chord_slots = _slots(['i'] * 8, bpb=3)
    comp.compose_lead(ctx)
    view = next(iter(comp._dna_views.values()))
    assert all(not (n.onset < 1.5 - 1e-6 and n.onset + n.dur > 1.5 + 1e-6) for n in view.hook.notes)


def test_developed_bass_answers_reuse_different_hook_fragments():
    hook = cell_from([.5, .25, .75, 1, 1.5], [0, 2, -1, 3, -2])
    answer = cell_from([.75, .25, 2], [0, -1, -1])
    cm = ChordMap(_slots(['I'] * 8), 'C', 'major')
    holes = [(2, 3.75), (6, 7.75), (10, 11.75)]
    notes = respond(hook, holes, cm, key='C', mode='major', develop=True, answer=answer)
    shapes = {tuple((round(n.beat-a,3),n.pitch) for n in notes if a <= n.beat < b) for a,b in holes}
    assert len(shapes) == 3
    assert notes == respond(hook, holes, cm, key='C', mode='major', develop=True, answer=answer)


@pytest.mark.parametrize('meter', ['5/8', '7/8', '9/8', '11/8', '12/8'])
def test_all_riffs_remain_inside_unusual_meters(meter):
    from produzre.composer.comping import RIFFS
    num, den = map(int, meter.split('/'))
    bpb = num * 4 / den
    for riff in RIFFS:
        notes = riff_events(riff, 0, bpb, ChordMap(_slots(['I'], bpb=bpb), 'C', 'major'),
                            groups=meter_groups(num,den))
        assert notes and all(0 <= n.beat < bpb and n.beat+n.dur <= bpb+1e-4 for n in notes)


@pytest.mark.parametrize('invalid', ['3+3', '0+7', '-1+8', 'nan+7', 'inf+1', [], 'oops'])
def test_invalid_groupings_fall_back_without_partial_application(invalid):
    assert meter_groups(7, 8, invalid) == (1,1,1.5)


def test_rest_and_contour_changes_do_not_contaminate_recall():
    comp = _composer()
    ctx = _ctx('c', 'chorus', 0, ['i','iv'])
    first = comp.compose_lead(ctx)
    shaped = comp.compose_lead(replace(ctx, occurrence=1, rest_probability=.9, contour='stepwise'))
    recalled = comp.compose_lead(replace(ctx, occurrence=2))
    assert recalled == first
    assert shaped != first


def test_nested_user_settings_override_persona_classification():
    from produzre.orchestrate.render import _explicit_settings
    cfg=NS(extra={'density':.7,'_persona_keys':['density','style'],
                  'extra':{'density':0,'style':'funk_chanks'}})
    flat={**cfg.extra,**cfg.extra['extra']}
    assert _explicit_settings(cfg,flat,('density','style')) == {'density':0,'style':'funk_chanks'}


def test_section_param_register_overrides_global_field():
    from produzre.model import InstrumentConfig
    from produzre.orchestrate.render import _merge_instrument_config
    from produzre.composer.song import lead_register
    merged=_merge_instrument_config(InstrumentConfig(register='high'),
                                    InstrumentConfig(extra={'extra':{'register':[60,67]}}))
    assert lead_register(NS(raw={}),merged)==(60,67)


def test_section_field_overrides_inherited_param():
    from produzre.model import InstrumentConfig
    from produzre.orchestrate.render import _merge_instrument_config, _explicit_settings
    merged=_merge_instrument_config(InstrumentConfig(extra={'humanize_timing':.5}),
                                    InstrumentConfig(humanize_timing=0))
    assert _explicit_settings(merged,merged.extra,('humanize_timing',))=={'humanize_timing':0}


def test_compound_group_pulse_survives_shared_swing(tmp_path):
    import yaml
    from tools.composer_round2 import config
    from tests.test_groove_clock import _load_cfg, _render_timelines
    cfg=_load_cfg(tmp_path,yaml.safe_dump(config('pulse','blues','12/8',False,0)))
    timelines,result=_render_timelines(cfg)
    gestures=result.performance_plan.get('composer.comp.chorus')['events']
    pulses=[e['beat'] for e in gestures if 0 < e['beat'] < 6 and abs(e['beat']/1.5-round(e['beat']/1.5))<1e-6]
    assert pulses
    assert all(any(abs(n.start_beat-b)<.08 for n in timelines['rhythm_gtr'].events) for b in pulses)


@pytest.mark.parametrize('meter,bpb', [('4/4',4), ('12/8',6), ('7/8',3.5)])
def test_blues_recipe_rate_and_short_section_prefix(tmp_path, meter, bpb):
    import logging
    import yaml
    from tools.composer_round2 import config
    from tests.test_groove_clock import _load_cfg
    from produzre.harmony.plan import build_harmony_plan
    data = config('recipe', 'blues', meter, False, 0)
    data['song']['mode'] = 'major'
    data['sections']['verse'].update(bars=4, harmony={})
    cfg = _load_cfg(tmp_path, yaml.safe_dump(data))
    hp = build_harmony_plan(cfg, cfg.sections['verse'], logging.getLogger('t'))
    assert hp.source == 'recipe' and hp.chord_rate == bpb
    assert [s.numeral for s in hp.chord_slots] == ['I'] * 4
    cfg.sections['verse'].harmony.chord_rate = 2
    cfg.sections['verse'].harmony.extra.pop('_chord_rate_default', None)
    assert build_harmony_plan(cfg, cfg.sections['verse'], logging.getLogger('t')).chord_rate == 2


@pytest.mark.parametrize('meter', ['5/8', '11/8', '12/8'])
def test_developed_answers_with_auto_foreground_and_modulation(tmp_path, meter):
    import yaml
    from tools.composer_round2 import config
    from tests.test_groove_clock import _load_cfg, _render_timelines
    data = config('answers', 'rock', meter, 'develop', 2, foreground='auto')
    data['instruments']['bass']['params'].update(register_low=36, register_high=48)
    cfg = _load_cfg(tmp_path, yaml.safe_dump(data))
    timelines, _ = _render_timelines(cfg)
    bass = sorted(timelines['bass'].events, key=lambda n: n.start_beat)
    answers = [n for n in bass if n.kind == 'hook_response']
    assert answers and all(36 <= n.pitch <= 48 for n in answers)
    assert all(a.start_beat+a.duration_beats <= b.start_beat+1e-6
               for a,b in zip(bass,bass[1:]) if a.kind == 'hook_response' or b.kind == 'hook_response')
