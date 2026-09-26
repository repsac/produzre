"""Seeded players retain their idiom without sharing every habit."""
from collections import Counter
from dataclasses import replace
from types import SimpleNamespace
import random

import pytest

from produzre.composer.acoustic import compose_picking_dna, fingerstyle
from produzre.composer.arrangement import apply_overrides, compose_arrangement_dna
from produzre.composer.bass import bass_bar, compose_bass_dna
from produzre.composer.comping import compose_comp_dna, plan_comp_section
from produzre.composer.drums import compose_drum_dna, plan_drum_section
from produzre.composer.theory import ChordMap, metric_weight
from produzre.orchestrate.transitions import build_bass_turnaround
from tests.test_album_diversity import _arr
from tests.test_composer import _slots


def test_country_players_vary_and_sections_contrast():
    bass = [compose_bass_dna(seed=s, genre='country') for s in range(100)]
    assert len({d.roles['verse'] for d in bass}) == 4
    assert Counter(d.roles['verse'] for d in bass).most_common(1)[0][0] == 'boom_chick'
    assert all(d.roles['verse'] != d.roles['chorus'] for d in bass)
    assert len({d.country_fifths['verse'] for d in bass}) == 2
    assert len({(d.walk_style, d.walk_every) for d in bass}) >= 8
    chords = ChordMap(_slots(['I', 'IV', 'V', 'I']), 'C', 'major')
    figures = {tuple(bass_bar(d.roles['verse'], 0, 4, chords, dna=d)) for d in bass}
    assert len(figures) >= 8


@pytest.mark.parametrize('genre', ['country', 'reggae'])
def test_drum_feet_hands_and_sections_vary(genre):
    players = [compose_drum_dna(seed=s, genre=genre) for s in range(100)]
    assert len({d.kick_verse for d in players}) >= 3
    assert all(d.kick_verse != d.kick_chorus for d in players)
    assert all(d.grooves['verse'][0] != d.grooves['chorus'][0] for d in players)
    assert len({d.train_patterns['verse'] for d in players}) > 20
    assert {d.crash_policy for d in players} == {'chorus', 'section', 'none'}
    if genre == 'reggae':
        assert Counter(d.kick_styles['verse'] for d in players).most_common(1)[0][0] == 'one_drop'
    for d in players:
        hits = plan_drum_section(d, _arr(), section_type='chorus', bars=4,
                                 beats_per_bar=4, next_section_type='verse')
        if d.crash_policy == 'none':
            assert not any(h.kind == 'crash' for h in hits)
        else:
            assert any(h.kind == 'crash' and h.voice == d.accent_voice for h in hits)


@pytest.mark.parametrize('genre', ['country', 'reggae', 'jazz'])
def test_arrangement_odds_are_not_constants_and_overrides_win(genre):
    players = [compose_arrangement_dna(seed=s, genre=genre) for s in range(100)]
    for habit in ('phrase_fill', 'intro', 'solo_ending', 'ending'):
        assert len({getattr(d, habit) for d in players}) > 1
    for d in players:
        pinned = apply_overrides(d, {'intro':'full', 'phrase_fill':'rake', 'ending':'big'})
        assert (pinned.intro, pinned.phrase_fill, pinned.ending) == ('full', 'rake', 'big')


def test_picking_players_have_independent_thumb_and_hand_choices():
    players = [compose_picking_dna(s, 'country') for s in range(100)]
    assert len({d.thumb for d in players}) == 4
    assert len({d.figure for d in players}) == 5
    assert len({d.placement for d in players}) == 3
    assert all(d.figure != d.chorus_figure for d in players)
    chords = ChordMap(_slots(['I']*4), 'C', 'major')
    shapes = {'I':SimpleNamespace(pitches=(48, 52, 55, 60, 64, 67))}
    for seed in range(20):
        args = dict(bars=4, bpb=4, groups=(2,2), melody_amount=1)
        a = fingerstyle(seed, 'country', chords, shapes, section_type='verse', **args)
        b = fingerstyle(seed, 'country', chords, shapes, section_type='chorus', **args)
        assert [(n[0], n[4]) for n in a] != [(n[0], n[4]) for n in b]
        assert a == fingerstyle(seed, 'country', chords, shapes, section_type='verse', **args)


@pytest.mark.parametrize('bpb,groups,expected', [(3,(1,1,1),[0]), (3,(1.5,1.5),[0,1.5]),
                                              (3.5,(1,1,1.5),[0,1,2]), (5,(3,2),[0,3])])
def test_country_bass_obeys_meter_before_vocabulary(bpb, groups, expected):
    slots = [SimpleNamespace(numeral='I', start_beat=0, end_beat=bpb*4)]
    chords = ChordMap(slots, 'C', 'major')
    for seed in range(50):
        d = compose_bass_dna(seed=seed, genre='country')
        for role in d.roles.values():
            notes = bass_bar(role, 0, bpb, chords, dna=d, groups=groups)
            assert [n[0] for n in notes] == expected
            if groups == (1,1,1):
                nxt = bass_bar(role, bpb, bpb, chords, dna=d, groups=groups)
                assert notes[0][2]%12 == 0 and nxt[0][2]%12 == 7


def test_country_guitar_waltz_answers_bass_on_two_and_three():
    dna = compose_comp_dna(seed=4, genre='country', key='C', mode='major', shuffle=False)
    events, _, _ = plan_comp_section(dna, section_type='verse', occurrence=0,
        is_final_of_type=False, bars=4, beats_per_bar=3, chord_slots=_slots(['I']*4),
        key='C', mode='major', groups=(1,1,1), arrangement=_arr(), next_section_type='verse')
    first = [e for e in events if e.beat < 3]
    assert [(e.beat, e.kind) for e in first] == [(0, 'root'), (1, 'strum'), (2, 'strum')]


@pytest.mark.parametrize('key,mode', [('C','major'), ('F','major'), ('Eb','minor')])
def test_turnaround_strong_notes_and_holds_belong_to_current_chord(key, mode):
    current = ChordMap(_slots(['I','IV','V','bVII']), key, mode)
    incoming = ChordMap(_slots(['ii','V','I','I']), key, mode)
    for seed in range(20):
        notes = build_bass_turnaround(12, 16, [], random.Random(seed),
            current_chords=current, incoming_chords=incoming, beats_per_bar=4, groups=(2,2))
        assert notes and len({n.start_beat for n in notes}) == len(notes)
        for n in notes:
            span = current.at(n.start_beat)
            if n.duration_beats >= .25 or metric_weight(n.start_beat%4, 4, (2,2)) >= .5:
                assert n.pitch%12 in span.pcs
            assert n.start_beat+n.duration_beats <= span.end
        assert notes[-1].start_beat+notes[-1].duration_beats < 16


def test_waltz_transition_cannot_add_an_extra_bass_pickup(tmp_path):
    import yaml
    from tools.album_diversity import album_configs
    from tests.test_groove_clock import _load_cfg, _render_timelines

    raw = album_configs('country', 1, meter='3/4')[0]
    timelines, _ = _render_timelines(_load_cfg(tmp_path, yaml.safe_dump(raw), name='waltz.yaml'))
    assert timelines['bass'].events
    assert all(min(e.start_beat % 3, 3-e.start_beat % 3) < .08
               for e in timelines['bass'].events)


def test_turnaround_respects_register_and_chord_changes_inside_edit_window():
    current = ChordMap([SimpleNamespace(numeral='I', start_beat=0, end_beat=15.5),
                        SimpleNamespace(numeral='IV', start_beat=15.5, end_beat=16)], 'C', 'major')
    incoming = ChordMap(_slots(['V']*4), 'F', 'major')
    notes = build_bass_turnaround(112, 116, [], random.Random(1), current_chords=current,
        incoming_chords=incoming, current_start=100, register=(48, 60))
    assert notes
    for n in notes:
        span = current.at(n.start_beat-100)
        assert 48 <= n.pitch <= 60
        assert n.start_beat+n.duration_beats <= 100+span.end
        assert n.duration_beats < .25 or n.pitch%12 in span.pcs
