"""Cross-system properties from the merged examples review."""
from types import SimpleNamespace

import pytest
import yaml

from produzre.timeline import InstrumentTimeline
from produzre.orchestrate.transitions import thin_events, _drum_structural
from tests.test_groove_clock import _load_cfg, _render_timelines


@pytest.mark.parametrize('kind', ['country_double_stac', 'country_lick_stac', 'trill'])
def test_transition_thinning_keeps_composed_country_phrases_and_ornaments(kind):
    for bpb in (3, 3.5, 4, 5, 6):
        for offset in (.25, .5, 1):
            tl = InstrumentTimeline('lead_gtr')
            for i in range(8):
                step = i // 2 if kind == 'country_double_stac' else i
                tl.add_note(start_beat=offset + step * .125, duration_beats=.1,
                            pitch=60 + i % 3, velocity=80, kind=kind)
            assert thin_events(tl.events, beats_per_bar=bpb) == tl.events


@pytest.mark.parametrize('kind,pitch', [('snare', 38), ('snare', 81),
                                       ('kick', 36), ('crash', 51)])
def test_structural_drum_roles_survive_quiet_dynamics_and_custom_kits(kind, pitch):
    for velocity in range(20, 81, 10):
        note = SimpleNamespace(kind=kind, pitch=pitch, velocity=velocity)
        assert _drum_structural(note)
    assert not _drum_structural(SimpleNamespace(kind='snare_ghost', pitch=38, velocity=25))


@pytest.mark.parametrize('meters', [('3/4', '6/8'), ('6/4', '12/8')])
def test_equal_length_meters_do_not_recall_each_others_groove(tmp_path, monkeypatch, meters):
    import produzre.composer.groove_memory as gm

    captured = []
    original = gm.apply_groove_memory

    def capture(events, **kwargs):
        result = original(events, **kwargs)
        captured.append((kwargs, result[1]))
        return result

    monkeypatch.setattr(gm, 'apply_groove_memory', capture)
    for seed in range(3):
        captured.clear()
        raw = {
            'song': {'title': 'Meter recall', 'genre': 'rock', 'seed': seed,
                     'exports_root': str(tmp_path / 'out'),
                     'params': {'transitions': {'enabled': False}}},
            'instruments': {'drums': {'params': {'composer': False}}},
            'sections': {
                name: {'type': 'verse', 'meter': meter, 'bars': 8,
                       'instruments': {'drums': {}}}
                for name, meter in zip(('simple', 'compound'), meters)
            },
            'arrangement': ['simple', 'compound'],
        }
        _render_timelines(_load_cfg(tmp_path, yaml.safe_dump(raw, sort_keys=False)))
        assert len(captured) == 2
        assert captured[0][0]['memory_key'] != captured[1][0]['memory_key']
        assert not captured[1][1].get('recalled')


@pytest.mark.parametrize('kind', ['comp', 'bass', 'drums'])
def test_explicit_country_style_reaches_a_part_with_its_own_genre(kind):
    from produzre.composer.lead import SongComposer
    from produzre.composer.country import STYLES
    from produzre.orchestrate.render import _part_dna

    for seed, style in enumerate(STYLES):
        composer = SongComposer(seed=seed, genre='rock', key='C', mode='major',
                                beats_per_bar=4,
                                arrangement_overrides={'country_style': style})
        for genre in ('country', 'outlaw_country'):
            dna = _part_dna(composer, kind, genre, None)
            if kind == 'comp':
                from produzre.composer.comping import compose_comp_dna

                expected = compose_comp_dna(seed=seed, genre=genre, key='C', mode='major',
                                            shuffle=False, country_style=style)
                assert dna == expected
            else:
                assert dna.country_style == style


@pytest.mark.parametrize('bpb', [3, 3.5, 4, 5, 6])
def test_bass_ramp_does_not_extend_a_note_across_the_next_attack_or_section(bpb):
    from produzre.orchestrate.transitions import (
        TransitionPlan, TransitionRecipe, apply_transition_plan,
    )

    for offset in (-.02, 0, .02):
        tl = InstrumentTimeline('bass')
        for beat, pitch in [(0, 36), (bpb, 41), (2*bpb, 43)]:
            duration = min(bpb, 2*bpb - beat - offset) if beat < 2*bpb else bpb
            tl.add_note(start_beat=beat + offset, duration_beats=duration,
                        pitch=pitch, velocity=80, kind='root')
        plan = TransitionPlan('a', 'b', 'bass', TransitionRecipe('ramp_down'),
                              {'tail': (0, 2*bpb)}, {'beats_per_bar_a': bpb})
        apply_transition_plan(tl, 'bass', plan)
        notes = sorted(tl.events, key=lambda ev: ev.start_beat)
        for previous, following in zip(notes, notes[1:]):
            assert previous.start_beat + previous.duration_beats <= following.start_beat + 1e-6
        assert notes[1].start_beat + notes[1].duration_beats <= 2*bpb + 1e-6


def test_groove_cycle_uses_the_parts_genre(tmp_path, monkeypatch):
    import produzre.composer.groove_memory as gm

    captured = []
    original = gm.apply_groove_memory

    def capture(events, **kwargs):
        captured.append(kwargs['genre'])
        return original(events, **kwargs)

    monkeypatch.setattr(gm, 'apply_groove_memory', capture)
    for genre in ('funk', 'reggae', 'jazz'):
        captured.clear()
        raw = {
            'song': {'title': 'Part groove', 'genre': 'rock', 'seed': 3,
                     'exports_root': str(tmp_path / 'out')},
            'sections': {'verse': {'type': 'verse', 'bars': 8,
                'instruments': {'drums': {'genre': genre,
                                           'params': {'composer': False}}}}},
            'arrangement': ['verse'],
        }
        _render_timelines(_load_cfg(tmp_path, yaml.safe_dump(raw, sort_keys=False)))
        assert captured == [genre]


@pytest.mark.parametrize('meter', ['3/4', '6/8', '12/8', '7/8', '5/4'])
def test_solo_classic_rhythm_guitar_does_not_require_a_drummer(tmp_path, meter):
    for patterns in (False, True):
        raw = {
            'song': {'project': 'produzre-examples', 'title': 'Solo classic guitar',
                     'genre': 'country', 'meter': meter, 'seed': 4,
                     'exports_root': str(tmp_path / 'out')},
            'sections': {'verse': {'type': 'verse', 'bars': 1,
                'harmony': {'progression': 'I'},
                'instruments': {'harmony': {}, 'rhythm_gtr': {
                    'params': {'composer': False, 'use_patterns': patterns}}}}},
            'arrangement': ['verse'],
        }
        timelines, _ = _render_timelines(_load_cfg(tmp_path, yaml.safe_dump(raw)))
        assert timelines['rhythm_gtr'].events
        assert all(ev.duration_beats > 0 for ev in timelines['rhythm_gtr'].events)
