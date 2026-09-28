"""Groove review: repeatable figures, dynamics, meter and user ownership."""
import random

import pytest

from produzre.composer.bass import bass_bar
from produzre.composer.comping import CompDNA, CompRiff, plan_comp_section
from produzre.composer.riff import compose_signature_riff
from produzre.composer.theory import ChordMap
from produzre.engine.rhythm_gtr.composed import perform_comp
from produzre.timeline import InstrumentTimeline
from tests.test_album_diversity import _arr, _song
from tests.test_composer import _composer, _slots
from tests.test_groove_clock import _render_timelines


def test_riff_pitch_does_not_change_later_attack_velocity():
    def play(interval):
        tl=InstrumentTimeline('rhythm_gtr')
        perform_comp([dict(beat=i,dur=.4,kind='rpower',interval=interval,accent=True) for i in range(4)],
                     timeline=tl,section_start_beat=0,shape_at=lambda t:([40,44,47],[40,47,52],'I'),
                     key='E',mode='major',intensity=1,bpm=120,ring=1,rng=random.Random(1),
                     timing_jitter_ms=0,feel={'humanize_velocity':0})
        return tl.events
    assert [e.velocity for e in play(0)] == [e.velocity for e in play(7)]
    assert len({e.velocity for e in play(0)[::3]}) == 1


def test_signature_answer_never_overlaps_body():
    for seed in range(100):
        riff=compose_signature_riff(seed=seed,genre='hard_rock')
        for bar in riff.bars:
            assert all(a.onset+a.dur <= b.onset for a,b in zip(bar,bar[1:]))


@pytest.mark.parametrize('groups',[(1.5,1.5),(1,1,1.5),(1.5,)*4,(1,1,1),(.5,)*6])
def test_signature_phrases_on_each_meter_group(groups):
    for seed in range(10):
        riff=compose_signature_riff(seed=seed,genre='rock',beats_per_bar=sum(groups),groups=groups)
        starts=[sum(groups[:i]) for i in range(len(groups))]
        for bar in riff.bars:
            assert all(any(n.onset==t and n.accent for n in bar) for t in starts)
            assert all(0 <= n.onset < n.onset+n.dur <= sum(groups) for n in bar)


def test_signature_cache_tracks_meter_grouping_and_part_seed():
    comp=_composer()
    a=comp.signature_riff(3,(1,1,1))
    b=comp.signature_riff(3,(1.5,1.5))
    c=comp.signature_riff(3,(1.5,1.5),seed=81)
    assert a!=b and b!=c
    assert b is comp.signature_riff(3,(1.5,1.5))


def test_verse_body_holds_for_three_bars_then_answers():
    dna=CompDNA('rock',{'low':CompRiff('plain',('rock',),'low','p-p-p-p-p-p-p-p-')})
    riff=compose_signature_riff(seed=1,genre='hard_rock')
    events,_,_=plan_comp_section(dna,section_type='verse',occurrence=0,is_final_of_type=False,
        bars=8,beats_per_bar=4,chord_slots=_slots(['i']*8),key='E',mode='minor',
        next_section_type='verse',arrangement=_arr(riff_driven=True,comp_activity='sparse'),signature_riff=riff)
    assert {int(e.beat//4) for e in events if e.kind=='rsingle'} == {3,7}
    head=lambda bar:[(e.beat-bar*4,e.kind,e.interval) for e in events if bar*4<=e.beat<(bar+1)*4]
    assert head(0)==head(1)==head(2)


def test_repeated_slides_are_reserved_for_phrases():
    dna=CompDNA('rock',{'drive':CompRiff('slide',('rock',),'drive','/---/---/---/---')})
    def plan(activity):
        return plan_comp_section(dna,section_type='chorus',occurrence=0,is_final_of_type=False,
            bars=8,beats_per_bar=4,chord_slots=_slots(['I']*8),key='C',mode='major',
            next_section_type='verse',arrangement=_arr(phrase_fill='none',comp_activity=activity))[0]
    normal=plan('sparse')
    assert [e.beat for e in normal if e.kind=='slide']==[28]
    assert sum(e.kind=='slide' for e in plan('busy'))==32


@pytest.mark.parametrize('setting',[{'lock_to_kick':.6},{'rhythm_pattern':'anchor'},{'walking':False}])
def test_explicit_bass_line_survives_automatic_doubling(tmp_path,setting):
    cfg=_song(tmp_path,4,style={'riff_driven':True,'bass_doubles':True})
    cfg.sections['verse'].instruments['bass'].extra.update(setting)
    tl,_=_render_timelines(cfg)
    assert not any(e.kind=='riff_double' and e.start_beat<32 for e in tl['bass'].events)


def test_doubled_bass_keeps_transition_and_final_bars(tmp_path):
    cfg=_song(tmp_path,4,style={'riff_driven':True,'bass_doubles':True})
    tl,_=_render_timelines(cfg)
    assert any(28<=e.start_beat<32 for e in tl['bass'].events)
    cfg.sections['chorus'].type='outro'
    tl,_=_render_timelines(cfg)
    assert any(124<=e.start_beat<128 for e in tl['bass'].events)


def test_bass_doubling_respects_explicit_register(tmp_path):
    cfg=_song(tmp_path,4,style={'riff_driven':True,'bass_doubles':True})
    for sec in cfg.sections.values():
        sec.instruments['bass'].extra.update(register_low=48,register_high=60)
    tl,_=_render_timelines(cfg)
    assert tl['bass'].events and all(48<=e.pitch<=60 for e in tl['bass'].events)


@pytest.mark.parametrize('key,mode,prog',[('C','major',['V','I']),('E','minor',['bVII','i'])])
def test_scale_approach_is_an_actual_scale_step(key,mode,prog):
    from produzre.composer.theory import scale_pcs
    chords=ChordMap(_slots(prog),key,mode)
    notes=bass_bar('pedal8',0,4,chords,approach='scale')
    assert notes[-1][2]%12 in scale_pcs(key,mode)
    target=chords.at(4).root_pc
    assert (target-notes[-1][2])%12 in (1,2,10,11)


def test_compound_drum_group_start_is_not_swung():
    from produzre.engine.drums.humanize import humanize_events
    from produzre.engine.drums.patterns.kit import DrumEvent
    notes=humanize_events(events=[DrumEvent(1.5,.25,38,90,'snare')],section_start_beat=0,
        beats_per_bar=3,bpm=120,timing_jitter_ms=0,swing=.62,push_pull=0,
        velocity_humanize=0,rng=random.Random(1),groups=(1.5,1.5))
    assert notes[0][0]==1.5


def test_signature_uses_the_same_body_in_intro_and_verse(tmp_path):
    cfg=_song(tmp_path,4,style={'riff_driven':True,'intro':'full'})
    cfg.sections['chorus'].type='intro'
    _,result=_render_timelines(cfg)
    plans=[result.performance_plan.get(f'composer.comp.{sid}') for sid in ('verse','chorus')]
    bodies=[[(e['beat']%4,e['kind'],e['interval']) for e in p['events']
             if e['beat']<4 and e['tag']=='comp_riff' and e['kind']!='rsingle'] for p in plans]
    assert bodies[0] and bodies[0]==bodies[1]


def test_restrained_candidate_search_improves_body_pocket_across_seeds():
    from produzre.composer.riff import pocket_score
    pocket=(0,1,2.5,3)
    scores=[]
    for supplied in ((),pocket):
        scores.append(sum(pocket_score(
            compose_signature_riff(seed=s,genre='hard_rock',pocket=supplied).bars[0],pocket)
            for s in range(30)))
    assert scores[1] > scores[0]
