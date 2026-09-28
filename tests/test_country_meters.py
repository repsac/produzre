"""Country meter choices stay independent, playable and measurable."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from produzre.composer import country
from produzre.composer.bass import compose_bass_dna, bass_bar
from produzre.composer.comping import compose_comp_dna, _waltz_comp_bar
from produzre.composer.drums import compose_drum_dna, plan_drum_section
from produzre.composer.theory import ChordMap
from produzre.genres import normalize_genre
from tests.test_album_diversity import _arr
from tools.album_diversity import performance_bars, performance_similarity


def test_waltz_random_draws_are_independent_by_part(monkeypatch):
    before = [country.waltz_player(s, 'ballad') for s in range(20)]
    original = country.random.Random
    drum_seeds = {country.stable_seed_int('composer.country.waltz.drums', s, 'ballad') for s in range(20)}
    def extra_drum_draw(seed):
        rng = original(seed)
        if seed in drum_seeds:
            rng.random()
        return rng
    monkeypatch.setattr(country, 'random', SimpleNamespace(Random=extra_drum_draw))
    after = [country.waltz_player(s, 'ballad') for s in range(20)]
    for a, b in zip(before, after):
        assert (a.bass, a.bass_alternation, a.walk_every, a.walk_style, a.comp) == (
            b.bass, b.bass_alternation, b.walk_every, b.walk_style, b.comp)
    assert any(a.hands != b.hands for a, b in zip(before, after))


@pytest.mark.parametrize('alias', ['honky_tonk', 'bakersfield', 'outlaw', 'western', 'two-step'])
def test_country_aliases_are_normalized_at_configuration_boundary(alias):
    from produzre.config.parse import parse_song
    canonical = normalize_genre(alias)
    song = parse_song({'title':'Alias', 'genre':alias, 'bpm':100, 'key':'C', 'mode':'major'})
    assert song.genre == canonical and 'country' in canonical
    assert country.country_style(3, alias) == country.country_style(3, canonical)
    assert country.country_style(3, alias, 'ballad') == 'ballad'


@pytest.mark.parametrize('genre', ['rock', 'hard_rock', 'ballad', 'modern', 'country_rockabilly',
                                    'country_modernism', 'country_texasville'])
def test_hints_do_not_match_unrelated_words(genre):
    assert country.style_hint(genre) is None
    assert normalize_genre(genre) == genre


def test_waltz_walk_passing_tones_are_short_in_every_key():
    for key in ('C', 'G', 'Eb'):
        slots = [SimpleNamespace(numeral=n, start_beat=i*3, end_beat=(i+1)*3)
                 for i,n in enumerate(('I', 'IV', 'V', 'vi', 'ii', 'V', 'I', 'I'))]
        chords = ChordMap(slots, key, 'major')
        passing = 0
        for seed in range(40):
            dna = compose_bass_dna(seed=seed, genre='country')
            for bar in range(7):
                ns = bass_bar(dna.roles['verse'], bar*3, 3, chords, dna=dna, groups=(1,1,1))
                assert ns[0][0] == bar*3
                for beat, dur, pitch, accent in ns:
                    assert 28 <= pitch <= 52
                    if pitch % 12 not in chords.at(beat).pcs:
                        passing += 1
                        assert dur <= .2 and not accent
        assert passing > 0


def test_guitar_held_chord_fifth_agrees_with_bass_habit():
    chords = ChordMap([SimpleNamespace(numeral='I', start_beat=0, end_beat=6),
                       SimpleNamespace(numeral='IV', start_beat=6, end_beat=9)], 'C', 'major')
    for seed in range(20):
        dna = compose_comp_dna(seed=seed, genre='country', key='C', mode='major', shuffle=False)
        dna = replace(dna, waltz=replace(dna.waltz, bass_alternation='change', comp={'verse':'pah_pah'}))
        assert _waltz_comp_bar(dna, 'verse', 0, 0, chords)[0].kind == 'root'
        assert _waltz_comp_bar(dna, 'verse', 3, 1, chords)[0].kind == 'fifth'
        assert _waltz_comp_bar(dna, 'verse', 6, 2, chords)[0].kind == 'root'


def test_waltz_drums_have_voices_and_short_meter_fills_without_ghosts():
    voices = set()
    for seed in range(60):
        dna = compose_drum_dna(seed=seed, genre='country', beats_per_bar=3)
        for sec in ('verse', 'chorus'):
            hits = plan_drum_section(dna, _arr(), section_type=sec, bars=4, beats_per_bar=3,
                                     groups=(1,1,1), next_section_type='verse')
            assert all(0 <= h.beat < 12 for h in hits)
            assert not any('ghost' in h.kind or h.kind == 'kick_extra' for h in hits)
            assert any(h.voice == 'kick' and h.beat == 0 for h in hits)
            fills = [h for h in hits if h.kind == 'fill']
            assert all(abs(h.beat*2-round(h.beat*2)) < 1e-6 for h in fills)
            voices.update(h.voice for h in hits if h.beat < 3 and h.kind != 'fill')
    assert {'ride', 'ride_bell', 'hat_open', 'hat_pedal', 'tom_low'} <= voices


def test_performance_metric_sees_gates_kit_voice_and_infrequent_walks():
    def note(t=0, pitch=36, dur=.9):
        return dict(start_beat_abs=str(t), pitch=str(pitch), duration_beats=str(dur),
                    kind='bass', section_id='verse')
    def fp(ns, drums=False):
        return performance_bars(ns, 3, drums)['verse']
    base = [note(t=t) for t in range(0,12,3)]
    assert performance_similarity(fp(base), fp([dict(n, pitch='41') for n in base])) == 1
    assert performance_similarity(fp(base), fp([dict(n, duration_beats='2.9') for n in base])) < 1
    assert performance_similarity(fp(base), fp(base+[note(t=10,pitch=38),note(t=11,pitch=40)])) < 1
    assert performance_similarity(fp([note(pitch=37)], True), fp([note(pitch=38)], True)) == 0


def test_waltz_arpeggio_releases_at_harmony_boundary():
    import random
    from produzre.engine.rhythm_gtr.composed import perform_comp
    from produzre.timeline import InstrumentTimeline

    for seed in range(20):
        tl = InstrumentTimeline(instrument='rhythm_gtr')
        perform_comp([dict(beat=2.5, dur=.45, kind='arp', release_beat=3)], timeline=tl,
            section_start_beat=12, shape_at=lambda beat: ([48,52,55], [48,55], 'I'),
            key='C', mode='major', intensity=.7, bpm=100, ring=2, rng=random.Random(seed))
        assert tl.events
        assert all(n.start_beat+n.duration_beats <= 15+1e-8 for n in tl.events)


def test_loaded_bare_alias_plays_the_same_band_as_country_name(tmp_path):
    import yaml
    from tools.album_diversity import album_configs
    from tests.test_groove_clock import _load_cfg, _render_timelines

    raw = album_configs('outlaw', 1, meter='3/4')[0]
    raw['song']['exports_root'] = str(tmp_path/'renders')
    raw['arrangement'] = ['verse','chorus']
    raw['song']['arrangement_style'] = {'country_style':'ballad'}
    results = []
    for genre in ('outlaw', 'outlaw_country'):
        raw['song']['genre'] = genre
        tls, _ = _render_timelines(_load_cfg(tmp_path, yaml.safe_dump(raw)))
        results.append({name: [(n.start_beat,n.duration_beats,n.pitch,n.velocity,n.kind)
                              for n in tl.events] for name,tl in tls.items()})
    assert results[0] == results[1]


def test_explicit_waltz_hat_density_keeps_its_voice_and_grid(tmp_path):
    import yaml
    from tools.album_diversity import album_configs
    from tests.test_groove_clock import _load_cfg, _render_timelines

    raw = album_configs('country', 1, meter='3/4')[0]
    raw['song']['exports_root'] = str(tmp_path/'renders')
    raw['song']['arrangement_style'] = {'intro':'full'}
    raw['arrangement'] = ['verse','chorus']
    raw['instruments'] = {'drums':{'params':{'hat_density':.1, 'fill_rate':0}}}
    tls, _ = _render_timelines(_load_cfg(tmp_path, yaml.safe_dump(raw)))
    ns = [n for n in tls['drums'].events if n.start_beat < 3 and n.pitch in (42,46,51,53)]
    assert len(ns) == 3
    assert {n.pitch for n in ns} == {42}
    assert all(abs(n.start_beat-round(n.start_beat)) < .08 for n in ns)


@pytest.mark.parametrize('voice,other', [(37,38), (44,42), (53,51)])
def test_preview_preserves_kit_voice_differences_and_repeatability(voice, other):
    np = pytest.importorskip('numpy')
    from tools.preview_audio import _drum

    a = _drum(voice, 90, np.random.default_rng(42))
    again = _drum(voice, 90, np.random.default_rng(42))
    b = _drum(other, 90, np.random.default_rng(42))
    assert np.array_equal(a, again)
    n = min(len(a),len(b))
    assert not np.allclose(a[:n],b[:n])
    assert np.isfinite(a).all() and 0 < np.max(np.abs(a)) < 1
    assert np.mean(a[-n//4:]**2) < np.mean(a[:n//4]**2)
