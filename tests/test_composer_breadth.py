"""Musical contracts for solo routing, idiom, meter and explicit ownership."""
from dataclasses import replace
from types import SimpleNamespace

import pytest
import yaml

from produzre.composer.arrangement import compose_arrangement_dna
from produzre.composer.drums import compose_drum_dna, plan_drum_section
from produzre.composer.bass import bass_bar, compose_bass_dna
from produzre.composer.theory import ChordMap
from produzre.orchestrate.render import _is_band_section, _riff_pocket
from tests.test_album_diversity import _arr
from tests.test_composer import _slots
from tests.test_groove_clock import _load_cfg, _render_timelines
from tools.album_diversity import album_configs, modal_bars


def solo_cfg(tmp_path, inst, params=None, meter='4/4', seed=1000):
    raw = album_configs('country' if inst == 'acoustic_gtr' else 'pop', 1,
                        instruments=[inst], meter=meter)[0]
    raw['song']['seed'] = seed
    raw['arrangement'] = ['verse', 'chorus', 'outro']
    raw['instruments'] = {inst: {'params': params or {}}}
    return _load_cfg(tmp_path, yaml.safe_dump(raw), name=f'{inst}.yaml')


def test_solo_lead_states_a_verse_and_explicit_auto_still_wins(tmp_path):
    full, _ = _render_timelines(solo_cfg(tmp_path, 'lead_gtr'))
    auto, _ = _render_timelines(solo_cfg(tmp_path, 'lead_gtr', {'foreground':'auto'}))
    assert any(e.start_beat < 4 for e in full['lead_gtr'].events)
    assert sum(e.start_beat < 32 for e in full['lead_gtr'].events) > sum(
        e.start_beat < 32 for e in auto['lead_gtr'].events)


@pytest.mark.parametrize('meter', ['4/4', '3/4', '6/8', '7/8'])
def test_fingerstyle_has_independent_thumb_and_top_voice(tmp_path, meter):
    cfg = solo_cfg(tmp_path, 'acoustic_gtr', {'technique':'fingerpicking'}, meter)
    timelines, _ = _render_timelines(cfg)
    notes = timelines['acoustic_gtr'].events
    thumbs = [e for e in notes if e.kind == 'acoustic_thumb']
    melody = [e for e in notes if e.kind == 'acoustic_theme']
    assert thumbs and melody
    assert min(e.pitch for e in melody) > min(e.pitch for e in thumbs)
    assert sum(e.velocity for e in melody)/len(melody) > sum(e.velocity for e in thumbs)/len(thumbs)
    assert all(e.duration_beats > 0 and e.start_beat >= 0 for e in notes)
    assert max(e.duration_beats for e in melody) > 2  # a closing arrival


@pytest.mark.parametrize('params', [
    {'technique':'fingerpicking','picking_pattern':'travis'},
    {'technique':'fingerpicking','composer':False},
    {'technique':'strumming'},
])
def test_explicit_acoustic_part_keeps_its_engine(tmp_path, params):
    timelines, _ = _render_timelines(solo_cfg(tmp_path, 'acoustic_gtr', params))
    assert timelines['acoustic_gtr'].events
    assert not any(e.kind == 'acoustic_theme' for e in timelines['acoustic_gtr'].events)


def test_fingerstyle_zero_melody_amount_is_respected(tmp_path):
    timelines, _ = _render_timelines(solo_cfg(tmp_path, 'acoustic_gtr',
        {'technique':'fingerpicking', 'melody_amount':0}))
    assert not any(e.kind == 'acoustic_theme' for e in timelines['acoustic_gtr'].events)


def test_solo_drum_answer_keeps_foot_time():
    dna = compose_drum_dna(seed=52, genre='pop')
    args = dict(section_type='verse', bars=8, beats_per_bar=4, next_section_type='verse')
    band = plan_drum_section(dna, _arr(), **args)
    solo = plan_drum_section(dna, _arr(), solo=True, **args)
    assert [h.beat for h in band if h.voice == 'kick'] == [h.beat for h in solo if h.voice == 'kick']
    assert any(h.kind == 'solo_answer' and h.voice.startswith('tom') for h in solo)
    assert any(a.vel != b.vel for a,b in zip(band, solo))


def test_solo_drum_intro_does_not_wait_for_nonexistent_guitar(tmp_path):
    raw = album_configs('pop', 1, instruments=['drums'])[0]
    raw['song']['arrangement_style'] = {'intro':'riff_alone'}
    raw['arrangement'] = ['intro', 'verse']
    cfg = _load_cfg(tmp_path, yaml.safe_dump(raw), name='drum_intro.yaml')
    timelines, _ = _render_timelines(cfg)
    assert any(e.start_beat < 4 for e in timelines['drums'].events)


def test_disabled_instruments_do_not_make_a_band():
    sec = SimpleNamespace(instruments={'drums':SimpleNamespace(enabled=False),
                                      'rhythm_gtr':SimpleNamespace(enabled=True)})
    assert not _is_band_section(sec)


@pytest.mark.parametrize('genre', ['country', 'reggae', 'jazz', 'pop'])
def test_nonrock_defaults_never_request_minor_power_riffs(genre):
    for seed in range(25):
        assert not compose_arrangement_dna(seed=seed, genre=genre).riff_driven


def test_country_bass_alternates_root_fifth():
    chords = ChordMap(_slots(['I']*4), 'C', 'major')
    for seed in range(12):
        dna = compose_bass_dna(seed=seed, genre='country')
        notes = bass_bar('boom_chick', 0, 4, chords, dna=dna)
        assert [(n[0], n[2]%12) for n in notes] == [(0,0),(2,7)]


def test_reggae_one_drop_keeps_beat_one_open():
    for seed in range(12):
        dna = compose_drum_dna(seed=seed, genre='reggae')
        dna.grooves['verse'] = ('hat8', 'one_drop')
        dna.kick_styles['verse'] = 'one_drop'
        hits = plan_drum_section(dna, _arr(), section_type='verse', bars=4,
                                 beats_per_bar=4, next_section_type='verse')
        assert not any(h.beat == 0 and h.voice in ('kick','snare') for h in hits)
        assert {h.voice for h in hits if h.beat == 2} >= {'kick','snare'}


def test_jazz_drum_comping_varies_across_songs():
    dna = [compose_drum_dna(seed=s, genre='jazz') for s in range(12)]
    assert len({d.grooves['verse'] for d in dna}) >= 8
    assert len({d.hand_patterns['verse'] for d in dna}) >= 8


def test_riff_pocket_uses_effective_drum_dna_and_excludes_suppressed_kicks():
    song = compose_drum_dna(seed=1, genre='rock')
    effective = replace(song, kick_verse='x...x...x...x...', grooves={'verse':('hat8','backbeat')})
    plan = {'composer.drums.verse':[{'beat':0}], 'composer.drum_dna.verse':effective}
    kicks, snares = _riff_pocket(SimpleNamespace(drum_dna=lambda:song), plan,
                                SimpleNamespace(id='verse'), 4, (2,2))
    assert kicks == (0,2) and snares == (1,3)


def test_album_solos_have_no_hidden_band_and_country_harmony_is_major():
    configs = album_configs('country', 5, instruments=['acoustic_gtr'])
    assert all(c['song']['mode'] == 'major' for c in configs)
    assert all(set(s['instruments']) == {'harmony','acoustic_gtr'} for c in configs for s in c['sections'].values())
    assert all('bVI' not in s['harmony']['progression'] for c in configs for s in c['sections'].values())


def test_fingerprint_does_not_wrap_five_four_into_four_four():
    events = [dict(start_beat_abs=str(t),pitch='60',kind='melody',section_id='verse') for t in (0,4)]
    assert modal_bars(events,bpb=5)['verse'] == ((0,''),(16,''))


def test_zero_fill_rate_keeps_groove_through_phrase_ends():
    dna = compose_drum_dna(seed=1, genre='rock')
    hits = plan_drum_section(dna, _arr(), section_type='verse', bars=8,
                             beats_per_bar=4, next_section_type='chorus', fills_enabled=False)
    assert not any(h.kind == 'fill' for h in hits)
    assert any(h.voice == 'kick' and 28 <= h.beat < 32 for h in hits)


def test_sparse_bass_does_not_hold_an_approach_for_half_a_bar(tmp_path):
    raw = album_configs('pop', 9)[-1]
    cfg = _load_cfg(tmp_path, yaml.safe_dump(raw), name='sparse_bass.yaml')
    timelines, _ = _render_timelines(cfg)
    assert all(e.duration_beats <= 1.0 for e in timelines['bass'].events
               if e.kind.startswith('approach'))


def test_odd_meter_swing_restarts_with_the_drummer_each_bar():
    from produzre.groove import GrooveFeel, apply_feel
    from produzre.timeline import InstrumentTimeline

    timeline = InstrumentTimeline('bass')
    for bar in range(4):
        timeline.add_note(start_beat=bar*3.5+.5, duration_beats=.4,
                          pitch=40, velocity=80, kind='root')
    apply_feel(timeline.events, GrooveFeel(swing=.6), 'bass', 120, 3.5, 1,
               groups=(1,1,1.5))
    assert [round(e.start_beat-bar*3.5, 4) for bar,e in enumerate(timeline.events)] == [.65]*4


def test_absent_lead_clears_previous_occurrence_before_rhythm_prepass():
    from produzre.orchestrate.render import _compose_lead_for_section

    data = {'composer.lead.verse':[{'pitch':60}]}
    plan = SimpleNamespace(data=data)
    _compose_lead_for_section(None, SimpleNamespace(id='verse'), None, None, None,
                              plan, None, None)
    assert 'composer.lead.verse' not in data
