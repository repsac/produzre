"""Meter grouping: odd and compound meters phrase by their beat groups."""
import logging

import pytest

from produzre.composer.comping import CompRiff, _fit_steps
from produzre.composer.dna import compose_dna, uses_group_rhythm
from produzre.composer.theory import meter_groups, metric_weight, parse_grouping
from produzre.harmony.plan import build_harmony_plan
from tests.test_groove_clock import _load_cfg


def test_simple_meters_weigh_exactly_as_before():
    assert [metric_weight(b, 4) for b in (0, 1, 2, 3, .5, .25)] == [1.0, .55, .75, .55, .3, .12]
    assert [metric_weight(b, 3) for b in (0, 1, 2, .5)] == [1.0, .55, .55, .3]


@pytest.mark.parametrize('num,den,groups', [(6, 8, (1.5, 1.5)), (7, 8, (1.0, 1.0, 1.5)),
                                            (5, 4, (3.0, 2.0)), (12, 8, (1.5,) * 4),
                                            (5, 8, (1.0, 1.5)), (4, 4, (2.0, 2.0))])
def test_default_groupings(num, den, groups):
    assert meter_groups(num, den) == groups


def test_grouping_override_must_fill_the_bar():
    assert meter_groups(7, 8, "3+2+2") == (1.5, 1.0, 1.0)
    assert meter_groups(7, 8, "3+3") == (1.0, 1.0, 1.5)     # does not add up: ignored
    assert parse_grouping([2, 3], 4) == (2.0, 3.0)


def test_compound_meter_pulses_on_dotted_quarters():
    g = meter_groups(6, 8)
    assert metric_weight(1.5, 3, g) == .75            # the "4" of 6/8
    assert metric_weight(1.0, 3, g) == .3             # a weak eighth, not a beat


def test_odd_meter_ideas_are_built_from_groups():
    g = meter_groups(7, 8)
    assert uses_group_rhythm(3.5, g) and not uses_group_rhythm(4.0, (2.0, 2.0))
    dna = compose_dna(seed=3, genre="rock", key="E", mode="minor", beats_per_bar=3.5, groups=g)
    for cell in (dna.hook, dna.verse):
        assert abs(cell.length - 3.5) < 1e-9
        # Ideas are assembled group by group, so no note straddles the 2+2+3
        # boundaries: the meter stays audible in the melody itself.
        for start in (1.0, 2.0):
            assert not any(n.onset < start - 1e-9 < start + 1e-9 < n.onset + n.dur
                           for n in cell.notes), (cell.name, start)


def test_riff_slices_follow_the_groups():
    steps = "X-mxX-mxX-mxX-mx"
    assert _fit_steps(steps, 4.0, (2.0, 2.0)) == steps                  # 4/4 untouched
    five = _fit_steps(steps, 5.0, (3.0, 2.0))
    assert five[:12] == steps[:12] and five[12:] == "X-mxX-mx"          # 3 + head restart
    seven = _fit_steps(steps, 3.5, (1.0, 1.0, 1.5))
    assert len(seven) == 14 and all(seven[i] in "XxumpPSrfwdqQyha/" for i in (0, 4, 8))
    six = _fit_steps("X-mxX---x-mxX---", 3.0, (1.5, 1.5))
    assert six[0] == "X" and six[6] == "X"                               # both pulses attack


def _harmony(tmp_path, meter, harmony):
    cfg = _load_cfg(tmp_path, f"""
version: 1
song: {{title: M, key: C, mode: major, meter: "{meter}", seed: 1}}
sections:
  v: {{type: verse, bars: 4, harmony: {harmony}, instruments: {{harmony: {{}}}}}}
arrangement: [v]
""")
    return build_harmony_plan(cfg, cfg.sections["v"], logging.getLogger("t"))


def test_default_harmonic_rhythm_is_one_chord_per_bar(tmp_path):
    hp = _harmony(tmp_path, "7/8", "{progression: 'I IV V I'}")
    assert hp.chord_rate == 3.5
    assert [s.start_beat for s in hp.chord_slots] == [0.0, 3.5, 7.0, 10.5]


def test_explicit_harmonic_rhythm_is_kept(tmp_path):
    assert _harmony(tmp_path, "7/8", "{progression: 'I IV', chord_rate: 2}").chord_rate == 2.0
    assert _harmony(tmp_path, "4/4", "{progression: 'I IV'}").chord_rate == 4.0
