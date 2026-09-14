"""Theme identity, pitch, and timing regressions."""
from dataclasses import replace
from types import SimpleNamespace as NS

import pytest

from produzre.config.errors import ConfigError
from produzre.model import SongConfig
from produzre.themes.compose import compose_theme_bank
from produzre.themes.io import parse_themes_block
from produzre.themes.realize import realize_theme
from produzre.themes.transform import augment, displace, fragment, octave_shift


def theme(events='1:1 4:1 5:1 1:1', **kwargs):
    return parse_themes_block({'test': {'events': events, 'register': [36, 84], **kwargs}}).get('test')


def realize(t, numeral='I', total=4):
    return realize_theme(t, [NS(start_beat=0, end_beat=total, numeral=numeral, index=0)],
                         key='C', mode='major', total_beats=total)


def test_seed_identity_and_variation():
    cfg = NS(song=SongConfig(seed=23))
    one = compose_theme_bank(cfg)
    assert one.seed_material_hash == compose_theme_bank(cfg).seed_material_hash
    cfg.song.take = 2
    cfg.song.variation = .9
    assert one.seed_material_hash == compose_theme_bank(cfg).seed_material_hash
    cfg.song.seed += 1
    assert one.seed_material_hash != compose_theme_bank(cfg).seed_material_hash


def test_octaves_are_audible():
    t = theme('1:2 5:2')
    assert [n.pitch + 12 for n in realize(t)] == [n.pitch for n in realize(octave_shift(t))]
    assert realize(theme('1+:2 5+:2')) == realize(octave_shift(t))


def test_tonic_and_final_color_survive_snapping():
    notes = realize(theme('1:1 5:1 1:1 4:1'), 'V')
    assert [notes[i].pitch % 12 for i in (0, 2, 3)] == [0, 0, 5]


@pytest.mark.parametrize('meter,bpb', [('3/4', 3), ('6/8', 3), ('7/8', 3.5), ('5/4', 5)])
def test_generated_cells_stay_on_grid(meter, bpb):
    for seed in range(12):
        bank = compose_theme_bank(NS(song=SongConfig(seed=seed, meter=meter)))
        for t in bank.themes.values():
            assert t.length_beats in (bpb, 2*bpb)
            assert all(e.offset_beats * 4 == round(e.offset_beats * 4) for e in t.events)
            assert all(e.duration_beats * 4 == round(e.duration_beats * 4) for e in t.events)


def test_transform_boundaries():
    t = theme('1:3 5:1')
    last = fragment(t, keep='last', beats=2)
    assert [(e.offset_beats, e.duration_beats) for e in last.events] == [(0, 1), (1, 1)]
    moved = displace(t, shift_beats=2)
    assert sum(e.duration_beats for e in moved.events) == 4
    assert all(e.offset_beats + e.duration_beats <= 4 for e in moved.events)


@pytest.mark.parametrize('factor', [0, -1, float('nan'), float('inf')])
def test_invalid_length_cannot_loop(factor):
    with pytest.raises(ValueError):
        augment(theme(), factor=factor)
    with pytest.raises(ValueError):
        realize(replace(theme(), length_beats=factor))


@pytest.mark.parametrize('spec', [
    {'degrees': [1], 'rhythm': [float('inf')]},
    {'events': '1:1', 'length_beats': 0},
    {'events': '1:1', 'register': [80, 40]},
    {'events': '1:1', 'source': {'midi': 'missing.mid'}},
    {'events': '1:1', 'role': 'kazoo'},
])
def test_malformed_theme_fails_clearly(spec):
    with pytest.raises(ConfigError):
        parse_themes_block({'bad': spec})


def test_register_changes_bank_hash():
    assert parse_themes_block({'x': {'events': '1:1', 'register': [36, 60]}}).seed_material_hash != \
           parse_themes_block({'x': {'events': '1:1', 'register': [48, 72]}}).seed_material_hash


def test_active_theme_order_changes_bank_hash():
    specs = {'first': {'events': '1:1'}, 'second': {'events': '5:1'}}
    first = parse_themes_block(specs)
    second = parse_themes_block(dict(reversed(list(specs.items()))))
    assert first.seed_material_hash != second.seed_material_hash
