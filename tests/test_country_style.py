"""Country styles coordinate players without fixing their personal figures."""
import random
from dataclasses import replace

import pytest

from produzre.composer.country import STYLES, country_style
from produzre.composer.lead import SongComposer, _tidy
from produzre.composer.licks import generate_lick, realize_lick
from produzre.composer.theory import ChordMap
from tests.test_composer import _slots


def composer(seed, style):
    return SongComposer(seed=seed, genre='country', key='C', mode='major', beats_per_bar=4,
                        arrangement_overrides={'country_style':style})


def test_styles_vary_and_invalid_values_use_seeded_default():
    assert {country_style(s, 'country') for s in range(100)} == set(STYLES)
    assert country_style(7, 'country', 'unknown') == country_style(7, 'country')
    assert country_style(7, 'hard_rock', 'ballad') == ''


@pytest.mark.parametrize('style', STYLES)
def test_every_player_varies_inside_a_pinned_style(style):
    players = [composer(s, style) for s in range(12)]
    assert all(c.arrangement_dna().country_style == style for c in players)
    assert all(c.bass_dna().country_style == c.drum_dna().country_style == style for c in players)
    assert len({c.bass_dna().country_rhythms['verse'] for c in players}) >= 3
    assert len({c.comp_dna().riffs['low'].steps for c in players}) >= 8
    assert len({c.drum_dna().kick_chorus for c in players}) >= 3
    assert len({tuple(l.notes for l in c.dna.licks) for c in players}) >= 8
    for c in players:
        assert c.bass_dna().country_rhythms['verse'] != c.bass_dna().country_rhythms['chorus']
        assert c.comp_dna().riffs['low'].steps != c.comp_dna().riffs['drive'].steps


def test_generated_country_licks_have_sixths_thirds_and_short_passing_notes():
    chords = ChordMap(_slots(['I']*4), 'C', 'major')
    material = []
    for seed in range(100):
        lick = generate_lick(random.Random(seed), family='country', energy=.6)
        assert lick.families == ('country',)
        notes = realize_lick(lick, 0, chords, key='C', mode='major', lo=55, hi=84, anchor=67)
        material += notes
        for n in notes:
            assert n.pitch%12 in (0,2,4,7,9) or n.pitch%12 == 3 and n.dur <= .12
    assert {4,9} <= {n.pitch%12 for n in material}
    assert any(n.role == 'country_double' for n in material)
    doubles = [n for n in material if n.role == 'country_double']
    assert all(n.tech == 'stac' for n in doubles)


def test_unbent_double_stops_survive_composer_cleanup():
    from produzre.composer.realize import Note
    ns = [Note(0,.3,64,tech='stac',role='country_double'),
          Note(0,.3,67,tech='stac',role='country_double'),Note(1,.5,69)]
    assert len(_tidy(ns,4)) == 3


def test_explicit_arrangement_habits_win_over_country_style():
    c = SongComposer(seed=17, genre='country', key='C', mode='major', beats_per_bar=4,
        arrangement_overrides={'country_style':'ballad','counter':'stabs','solo_story':'climb'})
    assert c.arrangement_dna().counter == 'stabs'
    assert c.arrangement_dna().solo_story == 'climb'


def test_double_stops_survive_performance_without_channel_bends():
    from produzre.engine.lead_gtr import _perform_composed
    from produzre.timeline import InstrumentTimeline
    timeline = InstrumentTimeline(instrument='lead_gtr')
    notes = [dict(beat=0, duration_beats=.4, pitch=p, tech='stac', role='country_double')
             for p in (64,67)]
    notes.append(dict(beat=1,duration_beats=.4,pitch=69,tech='stac',role='lick'))
    _perform_composed(notes, timeline=timeline, section_start_beat=0, base_vel=80,
        intensity=.7, solo=True, rng=random.Random(8), bpm=100, beats_per_bar=4,
        vibrato_rate=0, dive_rate=0, swell_rate=0)
    first = [e for e in timeline.events if e.pitch in (64,67)]
    assert len(first) == 2
    assert min(e.start_beat+e.duration_beats for e in first)-max(e.start_beat for e in first) > .1
    assert all(e.expression is None for e in first)


def test_yaml_style_pin_reaches_players_and_explicit_bass_wins(tmp_path, monkeypatch):
    import yaml
    from tools.album_diversity import album_configs
    from tests.test_groove_clock import _load_cfg, _render_timelines
    seen = []
    original = SongComposer.__init__
    def capture(self, **kwargs):
        original(self, **kwargs)
        seen.append(self)
    monkeypatch.setattr(SongComposer, '__init__', capture)
    raw = album_configs('country', 1)[0]
    raw['song']['arrangement_style'] = {'country_style':'bakersfield'}
    raw['arrangement'] = ['verse', 'chorus']
    raw['instruments'] = {'bass':{'params':{'walking':False}}}
    timelines, _ = _render_timelines(_load_cfg(tmp_path, yaml.safe_dump(raw)))
    assert seen[0].arrangement_dna().country_style == 'bakersfield'
    assert seen[0].bass_dna().country_style == seen[0].drum_dna().country_style == 'bakersfield'
    assert not any(e.kind.startswith('bass_') for e in timelines['bass'].events)


def test_country_double_stops_survive_full_song_pipeline(tmp_path):
    import yaml
    from tools.album_diversity import album_configs
    from tests.test_groove_clock import _load_cfg, _render_timelines
    raw = album_configs('country', 3)[-1]
    timelines, _ = _render_timelines(_load_cfg(tmp_path, yaml.safe_dump(raw)))
    ns = [n for n in timelines['lead_gtr'].events if n.kind == 'country_double_stac']
    pairs = [(a,b) for a,b in zip(ns,ns[1:]) if abs(a.start_beat-b.start_beat)<.06]
    assert pairs
    assert all(min(a.start_beat+a.duration_beats,b.start_beat+b.duration_beats)-max(a.start_beat,b.start_beat) > .06
               for a,b in pairs)
