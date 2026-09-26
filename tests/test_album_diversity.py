"""Album diversity: every song gets its own drummer, riffs, licks and habits.

These pin the properties that keep an album of one genre from sounding like
one song: per-song DNA is seeded and varied, devices are per-song choices
the parts agree on, explicit user settings still win, and output stays
deterministic.
"""
from __future__ import annotations

import random

import pytest
import yaml

from produzre.composer.arrangement import (ArrangementDNA, apply_overrides,
                                           compose_arrangement_dna, intro_entry_bar)
from produzre.composer.comping import compose_comp_dna, plan_comp_section, synthesize_riff
from produzre.composer.drums import compose_drum_dna, plan_drum_section
from produzre.composer.licks import generate_lick
from produzre.composer.riff import compose_signature_riff
from tests.test_composer import _composer, _ctx, _slots
from tests.test_groove_clock import _load_cfg, _render_timelines


def _arr(**kw) -> ArrangementDNA:
    base = dict(into_chorus="fill", phrase_fill="walkup", intro="full", solo_story="climb",
                solo_ending="hold", counter="guide")
    base.update(kw)
    return ArrangementDNA(**base)


# --- drum DNA ------------------------------------------------------------------

def test_drum_dna_is_seeded_and_songs_differ():
    a = compose_drum_dna(seed=1, genre="hard_rock")
    assert a.signature == compose_drum_dna(seed=1, genre="hard_rock").signature
    kicks = {compose_drum_dna(seed=s, genre="hard_rock").kick_verse for s in range(12)}
    grooves = {compose_drum_dna(seed=s, genre="hard_rock").grooves["verse"] for s in range(12)}
    assert len(kicks) >= 8 and len(grooves) >= 4


def test_verse_and_chorus_grooves_contrast():
    for s in range(20):
        d = compose_drum_dna(seed=s, genre="rock")
        assert d.grooves["verse"][0] != d.grooves["chorus"][0]


def _grid(hits, voice, bar=0):
    return {round((h.beat - bar * 4) * 4) for h in hits
            if h.voice == voice and bar * 4 <= h.beat < bar * 4 + 4}


def test_groove_keeps_the_backbeat_and_the_one():
    d = compose_drum_dna(seed=3, genre="hard_rock")
    hits = plan_drum_section(d, _arr(), section_type="verse", bars=4, beats_per_bar=4,
                             next_section_type="verse")
    assert 0 in _grid(hits, "kick", 1)
    snare = _grid(hits, "snare", 1) - {s for s in _grid(hits, "snare", 1)
                                       if any(h.kind == "snare_ghost" and
                                              round((h.beat - 4) * 4) == s for h in hits)}
    assert {4, 12} <= snare or {8} <= snare          # backbeat or half-time


def test_push_anticipates_the_chorus_and_the_chorus_does_not_crash_again():
    d = compose_drum_dna(seed=4, genre="rock")
    pre = plan_drum_section(d, _arr(into_chorus="push"), section_type="prechorus", bars=4,
                            beats_per_bar=4, next_section_type="chorus")
    assert max(h.beat for h in pre) == pytest.approx(15.5)
    assert any(h.voice == "crash" and h.beat == pytest.approx(15.5) for h in pre)
    chorus = plan_drum_section(d, _arr(into_chorus="push"), section_type="chorus", bars=4,
                               beats_per_bar=4, next_section_type="verse",
                               prev_section_type="prechorus")
    assert not any(h.voice == "crash" and h.beat == 0 for h in chorus)


def test_riff_alone_intro_waits_then_enters_with_a_fill():
    d = compose_drum_dna(seed=2, genre="hard_rock")
    arr = _arr(intro="riff_alone")
    hits = plan_drum_section(d, arr, section_type="intro", bars=4, beats_per_bar=4,
                             next_section_type="verse", is_first_section=True)
    assert intro_entry_bar(arr, "intro", 4, True) == 2
    assert not any(h.beat < 4 for h in hits)                       # bar 1: guitar alone
    assert all(h.kind == "fill" for h in hits if 4 <= h.beat < 8)  # bar 2: the fill in
    assert any(h.voice == "crash" and h.beat == 8 for h in hits)


@pytest.mark.parametrize("ending,check", [
    ("cold", lambda hits: all(h.beat == 12 for h in hits if h.beat >= 12)),
    ("big", lambda hits: sum(1 for h in hits if h.beat > 12 and h.kind == "fill") >= 8),
])
def test_song_endings(ending, check):
    d = compose_drum_dna(seed=5, genre="hard_rock")
    hits = plan_drum_section(d, _arr(ending=ending), section_type="outro", bars=4,
                             beats_per_bar=4, next_section_type=None)
    assert check(hits)


# --- arrangement DNA -------------------------------------------------------------

def test_arrangement_habits_vary_across_songs():
    songs = [compose_arrangement_dna(seed=s, genre="hard_rock") for s in range(30)]
    for field in ("into_chorus", "solo_ending", "counter", "chorus_form", "ending"):
        values = [getattr(a, field) for a in songs]
        assert max(values.count(v) for v in set(values)) <= 20, field


def test_arrangement_style_overrides_pin_habits():
    dna = compose_arrangement_dna(seed=1, genre="rock")
    pinned = apply_overrides(dna, {"into_chorus": "build", "riff_driven": False,
                                   "ending": "nonsense"})
    assert pinned.into_chorus == "build" and pinned.riff_driven is False
    assert pinned.ending == dna.ending                  # unknown values are ignored
    assert "into chorus=build" in pinned.signature


# --- rhythm guitar ---------------------------------------------------------------

def test_synthesized_riffs_are_unique_and_open_on_an_attack():
    rng = random.Random(1)
    riffs = [synthesize_riff(rng, "rock", "drive", heavy=True) for _ in range(20)]
    assert all(r.steps[0] not in "-." for r in riffs)
    assert len({r.steps for r in riffs}) >= 15


def test_comp_dna_differs_across_a_genre():
    songs = {compose_comp_dna(seed=s, genre="hard_rock", key="E", mode="minor",
                              shuffle=False).riffs["drive"].steps for s in range(12)}
    assert len(songs) >= 11


@pytest.mark.parametrize("device", ["stop", "build", "push", "drop", "fill"])
def test_into_chorus_devices(device):
    dna = compose_comp_dna(seed=2, genre="rock", key="E", mode="minor", shuffle=False)
    events, _, _ = plan_comp_section(dna, section_type="prechorus", occurrence=0,
                                     is_final_of_type=True, bars=4, beats_per_bar=4.0,
                                     chord_slots=_slots(["iv", "bVI", "bVII", "bVII"]),
                                     key="E", mode="minor", next_section_type="chorus",
                                     arrangement=_arr(into_chorus=device))
    last = [e for e in events if e.beat >= 12]
    assert last
    if device == "build":
        assert len(last) == 8 and all(e.kind == "strum" for e in last)
    if device == "drop":
        assert len(last) == 1 and last[0].dur == 4
    if device == "push":
        assert max(e.beat for e in last) == pytest.approx(15.5)


def test_signature_riff_moves_and_answers_itself():
    riff = compose_signature_riff(seed=7, genre="hard_rock")
    first, second = riff.bars
    assert first[0].kind == "rpower" and first[0].interval == 0 and first[0].onset == 0
    assert any(n.kind == "rpower" and n.interval != 0 for n in first)
    assert any(n.kind == "rsingle" for n in first)
    body = lambda bar: [(n.onset, n.kind, n.interval) for n in bar if n.kind != "rsingle"]
    assert body(first) == body(second)            # same body, its own tail


# --- lead ----------------------------------------------------------------------

def test_generated_licks_fit_and_land():
    rng = random.Random(9)
    for _ in range(30):
        lick = generate_lick(rng, family="rock", energy=rng.uniform(.3, .9), max_len=3.0)
        assert lick.length <= 3.0 + 1e-6
        last = lick.notes[-1]
        assert last[3] in ("vib", "bend2") and last[1] >= 1.0   # a held landing note


@pytest.mark.parametrize("story", ["climb", "melodic", "trade", "blues"])
def test_every_solo_story_resolves_to_the_tonic(story):
    comp = _composer(seed=11)
    comp._arrangement_dna = _arr(solo_story=story, solo_ending="hold")
    notes = comp.compose_lead(_ctx("solo", "solo", 0, ["i", "bVI", "bVII", "i"]))
    assert notes and notes[-1].pitch % 12 == 4


# --- integration ---------------------------------------------------------------

def _song(tmp_path, seed, drums=None, style=None, song_extra=None):
    data = {"song": {"title": f"Div{seed}", "seed": seed, "genre": "hard_rock", "key": "E",
                     "mode": "minor", **(song_extra or {})},
            "instruments": {"drums": {"params": drums or {}}},
            "sections": {
                "verse": {"type": "verse", "bars": 8, "harmony": {"progression": "i bVI bIII bVII"},
                          "instruments": {"harmony": {}, "drums": {}, "bass": {}, "rhythm_gtr": {}}},
                "chorus": {"type": "chorus", "bars": 8, "harmony": {"progression": "i bVII bVI bVII"},
                           "instruments": {"harmony": {}, "drums": {}, "bass": {}, "rhythm_gtr": {}}}},
            "arrangement": ["verse", "chorus", "verse", "chorus"]}
    if style:
        data["song"]["arrangement_style"] = style
    return _load_cfg(tmp_path, yaml.safe_dump(data, sort_keys=False), name=f"s{seed}.yaml")


def test_three_songs_three_drummers(tmp_path):
    grooves = set()
    for seed in (1, 2, 3):
        tl, _ = _render_timelines(_song(tmp_path, seed))
        grooves.add(tuple(sorted((round(e.start_beat % 4, 2), e.pitch) for e in tl["drums"].events
                                 if 4 <= e.start_beat < 8)))
    assert len(grooves) == 3


def test_explicit_drum_voices_keep_the_engine(tmp_path):
    _, result = _render_timelines(_song(tmp_path, 1, drums={"voices": {"kick": {"density": .5}}}))
    assert result.performance_plan.get("composer.drums.verse") is None


def test_ghost_rate_zero_removes_ghosts(tmp_path):
    tl, _ = _render_timelines(_song(tmp_path, 3, drums={"ghost_rate": 0}))
    assert not any(e.kind == "snare_ghost" for e in tl["drums"].events)


def test_explicit_timing_owns_the_feel(tmp_path):
    _, result = _render_timelines(_song(tmp_path, 1, song_extra={"humanize_timing": 0.0}))
    assert result.performance_plan.get("composer.drums_feel.verse") is None


def test_bass_doubles_a_riff_driven_song(tmp_path):
    tl, result = _render_timelines(_song(tmp_path, 4, style={"riff_driven": True,
                                                             "bass_doubles": True}))
    riff = [e for e in result.performance_plan.get("composer.comp.verse")["events"]
            if e["tag"] == "comp_riff"]
    doubled = [e for e in tl["bass"].events if e.kind == "riff_double"]
    assert riff and doubled
    assert {round(e.start_beat % 4, 2) for e in doubled} <= {round(r["beat"] % 4, 2) for r in riff}
