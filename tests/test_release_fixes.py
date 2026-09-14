"""Behavioral coverage for the September release review."""
import io
import logging
import random
from dataclasses import replace
from types import SimpleNamespace as NS

import mido
import pytest
import yaml

from tests.test_groove_clock import _load_cfg, _render_timelines
from produzre.config.parse import parse_song
from produzre.engine.drums.groove import groove_template
from produzre.engine.drums.humanize import humanize_start
from produzre.harmony.meter import parse_meter
from produzre.melody import chord_pitch_classes
from produzre.themes.guide import realized_to_dicts


def config(tmp_path, *, genre='rock', meter='4/4', instruments=None, themes=None, sections=None):
    instruments = instruments or {'bass': {'params': {'pocket_ms': 0, 'push_pull': 0}}, 'drums': {'params': {'swing': 0, 'swing_16th': 0, 'timing_jitter_ms': 0, 'push_pull': 0, 'velocity_humanize': 0}}}
    data = {'song': {'title': 'Review', 'seed': 22, 'genre': genre, 'meter': meter},
            'instruments': instruments,
            'sections': sections or {'v': {'type': 'verse', 'bars': 4, 'harmony': {'progression': 'I V'}, 'instruments': {'harmony': {}, **{i: {} for i in instruments}}}},
            'arrangement': list(sections) if sections else ['v']}
    if themes is not None:
        data['themes'] = themes
    return _load_cfg(tmp_path, yaml.safe_dump(data, sort_keys=False))


@pytest.mark.parametrize('role', ['riff', 'bass_motif'])
def test_realized_riff_pitches_reach_bass(tmp_path, role):
    cfg = config(tmp_path, instruments={'bass': {'params': {'lock_to_riff': 1.0, 'register_low': 36, 'register_high': 60, 'pocket_ms': 0}}},
                 themes={'line': {'role': role, 'events': '1:.5 3:.5 4:1 5:1 1:1', 'register': [36, 60]}})
    timelines, result = _render_timelines(cfg)
    expected = result.performance_plan.get('themes.realized.v')[role]
    actual = [n for n in timelines['bass'].events if n.kind == 'theme_riff']
    assert [(n.start_beat, n.pitch) for n in actual] == [(n['beat'], n['pitch']) for n in expected]
    assert result.performance_plan.get('performance.bass.v')['event_count'] == len(actual)


def test_same_role_guide_and_lead_use_first_theme(tmp_path):
    cfg = config(tmp_path, themes={'first': {'events': '1:4'}, 'second': {'events': '5:4'}})
    _, result = _render_timelines(cfg)
    plan = result.performance_plan
    named = plan.get('themes.realized_by_name.v')
    assert set(named) == {'first', 'second'}
    assert plan.get('themes.realized.v')['melody'] == named['first']
    assert [n['pitch'] for n in plan.get('melody.guide.v')['targets']] == [n['pitch'] for n in named['first']]


def test_theme_coupling_is_opt_in(tmp_path):
    cfg = config(tmp_path, genre='reggae')
    timelines, _ = _render_timelines(cfg)
    assert not any(e.kind == 'theme_riff' for e in timelines['bass'].events)
    assert not any(e.kind == 'kick_theme_lock' for e in timelines['drums'].events)
    assert any(e.pitch == 37 for e in timelines['drums'].events)
    assert not any(e.pitch == 38 for e in timelines['drums'].events)


def test_recipe_voice_user_precedence(tmp_path):
    inst = {'drums': {'recipe': 'reggae_straight', 'voices': {'snare': {'articulation': {'default': 'rimshot'}}}}}
    cfg = config(tmp_path, instruments=inst)
    timelines, _ = _render_timelines(cfg)
    assert any(e.pitch == 40 for e in timelines['drums'].events)
    cfg.sections['v'].instruments['drums'].extra['voices'] = {'snare': {'articulation': {'default': 'normal'}}}
    cfg.raw['sections']['v']['instruments']['drums']['voices'] = {'snare': {'articulation': {'default': 'normal'}}}
    timelines, _ = _render_timelines(cfg)
    assert any(e.pitch == 38 for e in timelines['drums'].events)


def test_six_eight_backbeat_is_fourth_eighth():
    simple = groove_template('verse_light', section_type='verse', intensity=.5, beats_per_bar=3, meter=parse_meter('3/4'))
    compound = groove_template('verse_light', section_type='verse', intensity=.5, beats_per_bar=3, meter=parse_meter('6/8'))
    assert simple.snare_backbeat_steps == (4,)
    assert compound.snare_backbeat_steps == (6,)


@pytest.mark.parametrize('numeral,expected', [('bVII', (10, 2, 5)), ('bVI', (8, 0, 3)), ('IVmaj7', (5, 9, 0, 4)), ('iiø7', (2, 5, 8, 0)), ('vii°7', (10, 1, 4, 7)), ('Vsus4', (7, 0, 2))])
def test_shared_chord_spelling(numeral, expected):
    assert chord_pitch_classes(numeral, 'C', 'minor') == expected


def test_triplets_and_push_pull_use_shared_clock():
    from produzre.groove import swing_offset, resolve_groove_feel
    for beat in (1/3, 2/3, 4/3):
        assert swing_offset(beat, .7, .4, .124) == 0
    start = humanize_start(start_beat=1, beat_in_bar=1, bpm=120,
                           timing_jitter_ms=0, swing=0, push_pull=.1, rng=random.Random(1))
    assert start == pytest.approx(.98)
    feel = resolve_groove_feel(NS(raw={}), None, {}, {'rhythm_gtr': {'push_pull': .1}})
    assert feel.pocket_offsets_ms['rhythm_gtr'] == -10


def test_zero_swing_and_timing_only_controls():
    from produzre.groove import resolve_groove_feel
    feel = resolve_groove_feel(NS(raw={'groove': {'swing': .6}}), None, {'swing': 0, 'swing_16th': 0}, {})
    assert feel is None
    feel = resolve_groove_feel(NS(raw={}), None, {}, {'bass': {'timing_jitter_ms': 8}})
    assert feel is not None


def test_short_sections_have_lead_windows():
    from produzre.orchestrate.ensemble import _lead_windows
    for kind in ('verse', 'intro', 'prechorus', 'outro'):
        assert _lead_windows(kind, 3.5, 3.5)


def test_acoustic_string_resolution_and_retrigger():
    from produzre.engine.acoustic_gtr import _string_for_pattern_hit, _next_same_string_beat
    from produzre.engine.acoustic_gtr.patterns import PickHit, PickPattern
    from produzre.instruments.chord_shapes import ResolvedVoicing
    from produzre.instruments.profile import GUITAR_STANDARD
    rv = ResolvedVoicing(GUITAR_STANDARD, (-1, -1, 0, 2, 3, 2), 0, 'D')
    hits = (PickHit(0, 2, 1, False), PickHit(.5, 3, 1, False))
    assert _string_for_pattern_hit(rv, hits[0]) == 4
    assert _next_same_string_beat(PickPattern('test', 4, hits), hits[0], 0, 0, 4, rv, 4, 4) == .5


def test_demo_midi_notes_are_audible():
    from tools.demo_themes import _track_chunk
    import struct
    data = b'MThd' + struct.pack('>IHHH', 6, 0, 1, 480) + _track_chunk([(0, 1, 60, 90), (1, 2, 60, 90)], 'mélodie', 1, 0, 480)
    midi = mido.MidiFile(file=io.BytesIO(data))
    events = [msg for msg in midi.tracks[0] if msg.type in ('note_on', 'note_off')]
    assert [(m.type, m.time) for m in events] == [('note_on', 0), ('note_off', 480), ('note_on', 0), ('note_off', 480)]


def test_pattern_options_are_parsed():
    song = parse_song({'pattern_quantize_beats': .25, 'pattern_velocity_step': 8, 'pattern_merge_repeats': True})
    assert (song.pattern_quantize_beats, song.pattern_velocity_step, song.pattern_merge_repeats) == (.25, 8, True)


def test_mixed_meter_metadata_preserves_repeats(tmp_path):
    from produzre.export.stems import write_full_song_midi, write_instrument_stems
    from produzre.export.index import generate_export_index
    sections = {'a': {'type': 'verse', 'bars': 1, 'meter': '3/4'}, 'b': {'type': 'chorus', 'bars': 1, 'meter': '7/8'}}
    cfg = config(tmp_path, sections=sections)
    cfg.arrangement = ['a', 'b', 'a']
    timelines, result = _render_timelines(cfg)
    path = write_full_song_midi(cfg=cfg, song_name='meter', export_root=tmp_path, instruments_used=[], timelines={}, logger=None)
    tick, signatures = 0, []
    for msg in mido.MidiFile(path).tracks[0]:
        tick += msg.time
        if msg.type == 'time_signature':
            signatures.append((tick, msg.numerator, msg.denominator))
    assert signatures == [(0, 3, 4), (1440, 7, 8), (3120, 3, 4)]
    index = yaml.safe_load(generate_export_index(cfg, tmp_path, result.section_timings, []).read_text())
    assert len(index['sections']) == 3
    assert [s['start_bar'] for s in index['sections'].values()] == [1, 2, 3]


def test_hat_placements_and_velocity_reach_renderer(tmp_path):
    voices = {'hats': {'pattern': {'rate': 1, 'placements': ['1', '2&']},
                       'open': {'rate': 1, 'placements': ['2&']},
                       'accents': {'rate': 1, 'placements': ['1'], 'boost': 25, 'bias': -10},
                       'velocity': {'bias': -5}}}
    cfg = config(tmp_path, genre=None, instruments={'drums': {'voices': voices, 'params': {
        'fill_rate': 0, 'fill_chatter': 0, 'pickup_rate': 0, 'downbeat_rate': 0,
        'timing_jitter_ms': 0, 'velocity_humanize': 0, 'swing': 0, 'push_pull': 0,
        'constraints': {'enabled': False}}}})
    timelines, _ = _render_timelines(cfg)
    hats = [e for e in timelines['drums'].events if e.pitch in (42, 46)]
    assert hats
    assert {round(e.start_beat % 4, 6) for e in hats} == {0, 1.5}
    assert all(e.pitch == 46 for e in hats if e.start_beat % 4 == 1.5)
    downbeats = [e.velocity for e in hats if e.start_beat % 4 == 0]
    opens = [e.velocity for e in hats if e.start_beat % 4 == 1.5]
    assert sum(downbeats) / len(downbeats) > sum(opens) / len(opens) + 15


def test_ride_allows_pedal_hat():
    from produzre.engine.drums.patterns.hats import generate_top_cymbal_events
    template = replace(groove_template('verse_light', section_type='verse', intensity=.5, beats_per_bar=3), use_ride=True)
    events, _, _ = generate_top_cymbal_events(bar_i=0, bars=1, bar_start=0, spb=12, sb=.25, bpb=3,
        template=template, hat_steps=(0, 2, 4, 6, 8, 10), backbeats=(6,), prev_bar_open_hat=False,
        hat_density=1, hats_density=1, hats_open_rate=0, hats_pedal_rate=1, hats_accent_rate=0,
        base_velocity=80, accent_strength=.2, rng=random.Random(1),
        pitches={'hat_closed': 42, 'hat_open': 46, 'hat_pedal': 44, 'ride': 51})
    assert [(e.beat, e.pitch) for e in events if e.kind == 'hat_pedal'] == [(1.5, 44)]
    assert any(e.pitch == 51 for e in events)


def test_hat_lock_features_include_top_cymbal():
    from produzre.engine.drums.patterns.kit import DrumEvent
    from produzre.rhythm_features import extract_rhythm_features
    from produzre.engine.bass.patterns.filters import apply_drum_locking
    events = [DrumEvent(.5, .25, 42, 80, 'hat'), DrumEvent(1.5, .25, 51, 80, 'ride')]
    features = extract_rhythm_features(events, 4, 4, {})
    assert features.hat_beats == {.5, 1.5}
    assert apply_drum_locking(set(), events, 0, 0, 1, 4, random.Random(1)) == features.hat_beats


def test_recipe_feel_reaches_drumless_section(tmp_path):
    cfg = config(tmp_path, genre='jazz', instruments={'bass': {'params': {'lock_to_kick': 0, 'lock_to_snare': 0, 'pocket_ms': 0}}})
    cfg.raw['_recipes']['bass']['jazz']['params']['pocket_ms'] = 20
    timelines, _ = _render_timelines(cfg)
    with_pocket = [e.start_beat for e in timelines['bass'].events]
    cfg.raw['_effective']['instruments']['bass']['params'].pop('pocket_ms')
    cfg.raw['instruments']['bass']['params'].pop('pocket_ms')
    timelines, _ = _render_timelines(cfg)
    recipe_pocket = [e.start_beat for e in timelines['bass'].events]
    assert len(with_pocket) == len(recipe_pocket)
    assert all(b - a == pytest.approx(.04) for a, b in zip(with_pocket, recipe_pocket))


def test_snare_placement_subdivision_preserves_beat_units(tmp_path):
    cfg = config(tmp_path, genre=None, instruments={'drums': {
        'voices': {'snare': {'ghosts': {'rate': 1, 'placements': ['2&'], 'subdiv': 8}}},
        'params': {'fill_rate': 0, 'fill_chatter': 0, 'pickup_rate': 0, 'downbeat_rate': 0,
                   'timing_jitter_ms': 0, 'velocity_humanize': 0, 'swing': 0,
                   'swing_16th': 0, 'push_pull': 0, 'constraints': {'enabled': False}}}})
    timelines, _ = _render_timelines(cfg)
    ghosts = [e for e in timelines['drums'].events if e.kind == 'snare_ghost']
    assert ghosts
    assert {round(e.start_beat % 4, 6) for e in ghosts} == {1.5}


def test_golden_runner_reads_its_own_export(tmp_path, monkeypatch):
    from tests import test_golden_drums as runner
    (tmp_path / 'song.yaml').write_text('song: {}')
    own = tmp_path / 'exports' / 'own' / 'analysis' / 'drums'
    own.mkdir(parents=True)
    (own / 'Song_drums.events.tsv').write_text('own build\n')
    other = tmp_path / 'exports' / 'other' / 'analysis' / 'drums'
    other.mkdir(parents=True)
    (other / 'Other_drums.events.tsv').write_text('other build\n')
    monkeypatch.setattr(runner, 'get_repo_root', lambda: tmp_path)
    monkeypatch.setattr(runner.subprocess, 'run', lambda *a, **k: NS(
        returncode=0, stdout='', stderr='INFO Export root: exports/own\n'))
    assert runner.build_and_extract_tsv('song.yaml', 'drums') == 'own build\n'


def test_missing_golden_fails(tmp_path, monkeypatch):
    from tests import test_golden_drums as runner
    monkeypatch.setattr(runner, 'get_repo_root', lambda: tmp_path)
    assert runner.run_test('missing.yaml', 'drums') is False
