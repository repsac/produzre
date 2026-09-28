"""Drum fixes from the 2026-09-26 examples findings (#1 #2 #3 #4 #10 #12 #14
#15 #27): property tests over many seeds, not single-seed MIDI pins."""
from __future__ import annotations

import statistics
from dataclasses import replace

import pytest
import yaml

from produzre.composer.drums import (apply_feel_knobs, compose_drum_dna, feel_values,
                                     is_dance_genre, plan_drum_section, section_level)
from tests.test_album_diversity import _arr
from tests.test_groove_clock import _load_cfg, _render_timelines

HANDS = ("hat_closed", "hat_open", "ride", "ride_bell", "crash", "tom_low", "hat_pedal")


def _song(tmp_path, name, *, genre="rock", seed=1, meter="4/4", sections, arrangement,
          drums=None, song_extra=None, groove=None, instruments=("harmony", "drums", "bass", "rhythm_gtr")):
    for sec in sections.values():
        sec.setdefault("instruments", {i: {} for i in instruments})
    data = {"song": {"title": name, "seed": seed, "genre": genre, "key": "C", "mode": "major",
                     "meter": meter, "bpm": 110, "exports_root": str(tmp_path / "exports"),
                     **(song_extra or {})},
            "instruments": {"drums": {"params": drums or {}}},
            "sections": sections, "arrangement": arrangement}
    if groove:
        data["groove"] = groove
    return _load_cfg(tmp_path, yaml.safe_dump(data, sort_keys=False), name=f"{name}.yaml")


def _by_section(timeline, result):
    out = []
    for meta in result.performance_plan.sections:
        out.append((meta, [e for e in timeline.events
                           if meta.start_beat - 0.1 <= e.start_beat < meta.end_beat - 0.1]))
    return out


def _mean_kick_snare(events):
    vals = [e.velocity for e in events if e.pitch == 36 or (e.pitch == 38 and e.kind == "snare")]
    return statistics.mean(vals)


# --- #1 dynamics ----------------------------------------------------------------

def test_section_level_follows_intensity_and_energy():
    assert section_level(0.65, 0.3) == pytest.approx(1.0)
    assert section_level(0.9, 0.9) > section_level(0.65, 0.3) + 0.2
    grid = [section_level(i / 10, e / 10) for i in range(11) for e in range(11)]
    assert all(0.55 <= g <= 1.35 for g in grid)
    for e in (0.3, 0.9):
        levels = [section_level(i / 20, e) for i in range(21)]
        assert levels == sorted(levels)
    assert section_level(0.95, 0.9) > section_level(0.9, 0.9)


@pytest.mark.parametrize("genre", ["rock", "pop", "country", "jazz", "dance_pop"])
def test_composed_verse_is_quieter_than_chorus_and_repeats_grow(tmp_path, genre):
    secs = {"verse": {"type": "verse", "bars": 8, "harmony": {"progression": "I IV V I"}},
            "chorus": {"type": "chorus", "bars": 8, "harmony": {"progression": "IV V I I"}}}
    for seed in (1, 2, 3):
        cfg = _song(tmp_path, f"dyn_{genre}_{seed}", genre=genre, seed=seed, sections=secs,
                    arrangement=["verse", "chorus", "verse", "chorus", "chorus"])
        tl, res = _render_timelines(cfg)
        # Jazz kicks feather and its snare comps, so its level is the ride on the beat.
        level = (lambda evs: statistics.mean(e.velocity for e in evs if e.pitch in (51, 42)
                                             and abs(e.start_beat - round(e.start_beat)) < .01)) \
            if genre == "jazz" else _mean_kick_snare
        levels = [(m.type, level(evs)) for m, evs in _by_section(tl["drums"], res)]
        verses = [v for t, v in levels if t == "verse"]
        choruses = [v for t, v in levels if t == "chorus"]
        assert min(choruses) > 1.12 * max(verses)
        assert choruses[2] >= choruses[0]


def test_explicit_quiet_verse_and_loud_chorus(tmp_path):
    secs = {"verse": {"type": "verse", "bars": 8, "intensity": 0.4, "harmony": {"progression": "I IV V I"}},
            "chorus": {"type": "chorus", "bars": 8, "intensity": 1.0, "harmony": {"progression": "IV V I I"}}}
    for seed in range(4):
        tl, res = _render_timelines(_song(tmp_path, f"q{seed}", seed=seed, sections=secs,
                                          arrangement=["verse", "chorus"]))
        (_, v), (_, c) = _by_section(tl["drums"], res)
        assert _mean_kick_snare(c) > _mean_kick_snare(v) + 15


def test_intent_section_plays_at_the_composed_level(tmp_path):
    diffs, before = [], []
    for genre in ("rock", "pop", "hard_rock", "funk"):
        for seed in range(3):
            secs = {"a": {"type": "verse", "bars": 8, "intensity": 0.7, "energy": 0.5,
                          "harmony": {"progression": "I IV V I"}},
                    "b": {"type": "verse", "bars": 8, "intensity": 0.7, "energy": 0.5, "intent": "open",
                          "harmony": {"progression": "I IV V I"}}}
            tl, res = _render_timelines(_song(tmp_path, f"h{genre}{seed}", genre=genre, seed=seed,
                                              sections=secs, arrangement=["a", "b"]))
            assert res.performance_plan.get("composer.drums.a")
            assert not res.performance_plan.get("composer.drums.b")
            (_, a), (_, b) = _by_section(tl["drums"], res)
            ka = statistics.mean(e.velocity for e in a if e.pitch == 36)
            kb = statistics.mean(e.velocity for e in b if e.pitch == 36)
            diffs.append(kb - ka)
    assert abs(statistics.mean(diffs)) < 5


# --- #2 compound meters -----------------------------------------------------------

@pytest.mark.parametrize("genre", ["rock", "blues", "pop", "country", "hard_rock", "funk"])
@pytest.mark.parametrize("pulses", [2, 4])
def test_compound_backbeat_kicks_and_hands_sit_on_the_pulse(genre, pulses):
    bpb = 1.5 * pulses
    groups = (1.5,) * pulses
    for seed in range(40):
        dna = compose_drum_dna(seed=seed, genre=genre)
        for st in ("verse", "chorus", "bridge"):
            hits = plan_drum_section(dna, _arr(into_chorus="fill"), section_type=st, bars=4,
                                     beats_per_bar=bpb, next_section_type="verse", groups=groups)
            groove = [h for h in hits if h.beat < 3 * bpb]  # the last bar holds the transition
            snares = {round(h.beat % bpb, 3) for h in groove if h.kind == "snare"}
            halftime = dna.grooves[st][1] == "halftime" and pulses == 4
            assert snares == ({3.0} if halftime else {1.5, 4.5} if pulses == 4 else {1.5})
            for h in groove:
                if h.voice == "kick" or h.kind in ("hat", "ride") and h.voice != "hat_pedal":
                    assert (h.beat * 4) == int(h.beat * 4)
                if h.voice == "kick" and h.kind == "kick":
                    assert (h.beat * 2) == int(h.beat * 2), (seed, st, h)
            eighths = [h for h in groove if h.kind in ("hat", "ride") and h.vel >= 0.7]
            assert all(abs((h.beat % 1.5) - 0) < 1e-6 or abs(h.beat * 2 - round(h.beat * 2)) < 1e-6
                       for h in eighths)


def _pulse_offsets(timeline, pitches):
    return {round(e.start_beat % 1.5, 3) for e in timeline.events if e.pitch in pitches}


@pytest.mark.parametrize("composer", [True, False])
def test_recipe_swing_does_not_warp_compound_meters(tmp_path, composer):
    secs = {"verse": {"type": "verse", "bars": 4, "harmony": {"progression": "I IV V I"}},
            "chorus": {"type": "chorus", "bars": 4, "harmony": {"progression": "IV V I I"}}}
    for seed in range(4):
        cfg = _song(tmp_path, f"c{composer}{seed}", genre="blues", seed=seed, meter="12/8",
                    sections=secs, arrangement=["verse", "chorus"],
                    drums=None if composer else {"composer": False})
        tl, res = _render_timelines(cfg)
        assert _pulse_offsets(tl["drums"], (42, 46, 51, 53)) <= {0.0, 0.25, 0.5, 0.75, 1.0, 1.25}
        assert res.performance_plan.get("groove.humanize.verse")["swing"] == 0.0


def test_explicit_swing_still_applies_in_compound_meters(tmp_path):
    secs = {"verse": {"type": "verse", "bars": 4, "harmony": {"progression": "I IV V I"}}}
    cfg = _song(tmp_path, "sw", genre="blues", meter="12/8", sections=secs, arrangement=["verse"],
                drums={"swing": 0.5})
    tl, _ = _render_timelines(cfg)
    assert 0.625 in _pulse_offsets(tl["drums"], (36, 38, 42, 44, 45, 46, 49, 51, 53))


@pytest.mark.parametrize("meter,backbeat", [("6/8", {1.5}), ("12/8", {1.5, 4.5})])
def test_drum_only_sections_keep_the_meter_grouping(tmp_path, meter, backbeat):
    secs = {"verse": {"type": "verse", "bars": 4, "instruments": {"drums": {}}},
            "chorus": {"type": "chorus", "bars": 4, "instruments": {"drums": {}}}}
    for seed in range(4):
        tl, res = _render_timelines(_song(tmp_path, f"d{seed}{meter[0]}", seed=seed, meter=meter,
                                          sections=secs, arrangement=["verse", "chorus"]))
        bpb = res.performance_plan.sections[0].beats_per_bar
        snares = {round(e.start_beat % bpb, 1) for e in tl["drums"].events   # feel moves them a few ms
                  if e.kind == "snare" and e.start_beat < 3 * bpb}
        assert snares <= backbeat and snares
        assert res.performance_plan.get("composer.drum_dna.verse").meter[1]


def test_straight_drummers_keep_recipe_swing_out_and_explicit_swing_wins(tmp_path):
    secs = {"verse": {"type": "verse", "bars": 4, "harmony": {"progression": "I IV V I"}}}
    seen = set()
    for seed in range(8):
        tl, res = _render_timelines(_song(tmp_path, f"p{seed}", genre="punk", seed=seed,
                                          sections=secs, arrangement=["verse"]))
        dna = res.performance_plan.get("composer.drum_dna.verse")
        swing = res.performance_plan.get("groove.humanize.verse")["swing"]
        seen.add(dna.feel)
        assert swing == (0.62 if dna.feel == "shuffle" else 0.0)
    assert seen - {"shuffle"}
    for source in ({"drums": {"swing": 0.4}}, {"groove": {"swing": 0.4}}):
        cfg = _song(tmp_path, "px" + str(len(source)), genre="punk", seed=0, sections=secs,
                    arrangement=["verse"], drums=source.get("drums"), groove=source.get("groove"))
        _, res = _render_timelines(cfg)
        assert res.performance_plan.get("groove.humanize.verse")["swing"] == pytest.approx(0.4)


def test_feel_values_are_never_swung_in_compound_meters():
    for seed in range(30):
        dna = compose_drum_dna(seed=seed, genre="blues")
        assert feel_values(dna, (1.5,) * 4)["swing"] == 0.0
        assert feel_values(dna, (1.0, 1.0, 1.0, 1.0))["swing"] == (0.62 if dna.feel == "shuffle" else 0.0)


# --- #3 jazz ----------------------------------------------------------------------

def _bars(hits, bpb, bars):
    return [[h for h in hits if b * bpb <= h.beat < (b + 1) * bpb] for b in range(bars)]


@pytest.mark.parametrize("bpb", [4, 3])
@pytest.mark.parametrize("genre", ["jazz", "swing", "bebop_jazz"])
def test_jazz_drummer_keeps_swing_time(genre, bpb):
    for seed in range(60):
        dna = compose_drum_dna(seed=seed, genre=genre, beats_per_bar=bpb)
        for st in ("intro", "verse", "chorus", "bridge", "solo"):
            hits = plan_drum_section(dna, _arr(into_chorus="fill"), section_type=st, bars=8,
                                     beats_per_bar=bpb, next_section_type="verse", groups=(1.0,) * bpb)
            for b, bar in enumerate(_bars(hits, bpb, 8)):
                if any(h.kind == "fill" for h in bar) or b == 7:
                    continue
                keep = [h for h in bar if h.voice in ("ride", "hat_closed")]
                # Every beat on the ride (or sticks on a closed hat), plus skip notes.
                assert {round(h.beat - b * bpb, 3) for h in keep} >= set(range(bpb)), (seed, st, b)
                assert any(abs((h.beat % 1) - 0.5) < 1e-6 for h in keep), (seed, st, b)
                feet = {round(h.beat - b * bpb) for h in bar if h.voice == "hat_pedal"}
                if bpb == 4:
                    assert feet >= {1, 3}
                else:
                    assert feet and feet <= {1, 2}
                kicks = [h for h in bar if h.voice == "kick"]
                assert len([k for k in kicks if k.vel > 0.6]) <= 1
                assert {round(k.beat - b * bpb, 3) for k in kicks if k.vel <= 0.45} | \
                    {round(k.beat - b * bpb) for k in kicks if k.vel > 0.6} >= set(range(bpb))
                assert all(h.vel <= 0.55 for h in bar if h.voice == "snare")


def test_jazz_song_rides_every_beat_of_the_head(tmp_path):
    secs = {"head": {"type": "verse", "bars": 8, "harmony": {"progression": "ii V I I"}},
            "solo": {"type": "solo", "bars": 8, "harmony": {"progression": "ii V I I"}}}
    for seed in range(4):
        tl, res = _render_timelines(_song(tmp_path, f"j{seed}", genre="jazz", seed=seed, sections=secs,
                                          arrangement=["head", "solo", "head"]))
        (_, head), _, _ = _by_section(tl["drums"], res)
        rides = [e for e in head if e.pitch in (51, 53, 42)]
        assert len(rides) >= 30          # every beat plus skips, less the phrase fills
        pedals = {round(e.start_beat % 4) for e in head if e.pitch == 44}
        assert pedals >= {1, 3}


# --- #4 four on the floor -----------------------------------------------------------

def test_dance_genres_are_matched_on_words():
    assert all(is_dance_genre(g) for g in ("dance", "dance_pop", "electronic", "techno", "house",
                                           "deep_house", "disco", "edm"))
    assert not any(is_dance_genre(g) for g in ("dancehall", "rock", "housewife_blues", "country"))
    assert compose_drum_dna(seed=1, genre="dance_hall_country").idiom == "country"


@pytest.mark.parametrize("genre", ["dance_pop", "techno", "house", "electronic", "disco"])
def test_four_on_the_floor(genre):
    kits = set()
    for seed in range(50):
        dna = compose_drum_dna(seed=seed, genre=genre)
        assert dna.dance is not None and dna.idiom == "dance"
        kits.add((dna.dance.backbeat, dna.dance.hats["verse"], dna.dance.hats["chorus"],
                  dna.dance.perc["chorus"], dna.dance.fill, dna.dance.intro))
        for st in ("verse", "chorus"):
            hits = plan_drum_section(dna, _arr(into_chorus="build"), section_type=st, bars=8,
                                     beats_per_bar=4, next_section_type="chorus" if st == "verse" else "verse")
            for b, bar in enumerate(_bars(hits, 4, 8)):
                if any(h.kind in ("fill", "snare_build") for h in bar) or b == 7:
                    continue
                kicks = {round(h.beat - 4 * b, 3) for h in bar if h.voice == "kick"}
                assert kicks >= {0, 1, 2, 3}
                assert kicks <= {0, 1, 2, 3, 3.75}
                backbeat = {round(h.beat - 4 * b, 3) for h in bar if h.voice in ("clap", "snare")}
                assert backbeat == {1, 3}
                offbeats = {round(h.beat - 4 * b, 3) for h in bar if h.voice in ("hat_open", "hat_closed")}
                assert {0.5, 1.5, 2.5, 3.5} <= offbeats
            if st == "chorus":
                assert dna.dance.hats["chorus"] != dna.dance.hats["verse"]
        # Bridges and breakdowns drop the kick (or take it to half time).
        bridge = plan_drum_section(dna, _arr(into_chorus="fill"), section_type="bridge", bars=4,
                                   beats_per_bar=4, next_section_type="verse")
        assert len([h for h in bridge if h.voice == "kick" and h.beat < 4]) <= 2
    assert len(kits) >= 25


def test_dance_builds_rise_and_drop_the_kick_before_the_chorus():
    for seed in range(40):
        dna = compose_drum_dna(seed=seed, genre="dance_pop")
        hits = plan_drum_section(dna, _arr(into_chorus="build"), section_type="prechorus", bars=4,
                                 beats_per_bar=4, next_section_type="chorus")
        rolls = [h for h in hits if h.kind == "snare_build"]
        assert len([h for h in rolls if h.beat >= 12]) >= 12      # sixteenths in the last bar
        tail = sorted(h.vel for h in rolls if h.beat >= 12)
        assert [h.vel for h in sorted(rolls, key=lambda h: h.beat) if h.beat >= 12] == tail
        assert not any(h.voice == "kick" and h.beat >= 15 for h in hits)


# --- #10 build versus fill -----------------------------------------------------------

@pytest.mark.parametrize("genre", ["rock", "pop", "hard_rock", "country", "reggae", "jazz"])
def test_build_is_a_snare_crescendo_not_a_fill(genre):
    for seed in range(40):
        dna = compose_drum_dna(seed=seed, genre=genre)
        args = dict(section_type="prechorus", bars=4, beats_per_bar=4, next_section_type="chorus")
        build = plan_drum_section(dna, _arr(into_chorus="build"), **args)
        fill = plan_drum_section(dna, _arr(into_chorus="fill"), **args)
        last = [h for h in build if h.beat >= 12]
        roll = sorted((h for h in last if h.kind == "snare_build"), key=lambda h: h.beat)
        assert len(roll) >= 8
        assert [h.vel for h in roll] == sorted(h.vel for h in roll)
        assert roll[-1].vel > 1.3 * roll[0].vel
        assert all(h.beat >= 12 + 2 - 1e-6 for h in roll[len(roll) - 8:])  # sixteenths at the end
        assert not any(h.kind == "fill" for h in last)
        assert not any(h.voice.startswith("tom") and h.beat >= 14 for h in last)
        assert any(h.kind == "fill" for h in fill if h.beat >= 12)
        if dna.build_bars == 2:
            assert any(h.kind == "snare_build" for h in build if 8 <= h.beat < 12)
    assert {compose_drum_dna(seed=s, genre="rock").build_bars for s in range(30)} == {1, 2}


# --- #12 bridge start ---------------------------------------------------------------

@pytest.mark.parametrize("meter", ["4/4", "3/4"])
def test_bridge_start_keeps_the_composed_first_bar(tmp_path, meter):
    import produzre.orchestrate.build as B

    kinds = []
    orig = B.apply_transition_plan

    def spy(tl, inst, plan, logger=None):
        kinds.append((inst, plan.recipe.kind, plan.metadata.get("beats_per_bar_b")))
        return orig(tl, inst, plan, logger)

    B.apply_transition_plan = spy
    try:
        for seed in range(4):
            secs = {"verse": {"type": "verse", "bars": 4, "intensity": .3, "harmony": {"progression": "I IV V I"},
                              "instruments": {"drums": {"params": {"hat_density": 0.2}}, "harmony": {}}},
                    "bridge": {"type": "bridge", "bars": 4, "intensity": 1.0, "harmony": {"progression": "vi IV I V"},
                               "instruments": {"drums": {"params": {"hat_density": 0.9}}, "harmony": {}}}}
            cfg = _song(tmp_path, f"b{seed}{meter[0]}", seed=seed, meter=meter, sections=secs,
                        arrangement=["verse", "bridge"],
                        song_extra={"params": {"transitions": {"enabled": True, "bridge_start_bars": 1, "strength": 1.0}}})
            tl, res = _render_timelines(cfg)
            meta = res.performance_plan.sections[1]
            bpb = meta.beats_per_bar
            planned = [h for h in res.performance_plan.get("composer.drums.bridge") if h["beat"] < bpb - 0.1]
            played = [e for e in tl["drums"].events if meta.start_beat - 0.1 <= e.start_beat < meta.start_beat + bpb - 0.1]
            assert len(played) == len(planned)
            assert any(e.pitch in (49, 52, 57) for e in played)
            assert any(e.kind == "snare" for e in played)
    finally:
        B.apply_transition_plan = orig
    starts = [k for k in kinds if k[0] == "drums" and k[1] == "bridge_start"]
    assert starts and all(k[2] == (4.0 if meter == "4/4" else 3.0) for k in starts)


def test_bridge_start_thins_engine_hands_not_the_groove_in_the_bridge_meter():
    from produzre.orchestrate.transitions import (EnergyProfile, TransitionPlan, TransitionRecipe,
                                                  apply_transition_plan)
    from produzre.timeline import InstrumentTimeline

    tl = InstrumentTimeline(instrument="drums")
    head = 12.0
    for k in range(12):                                # one 3/4 bar of sixteenth hats
        tl.add_note(start_beat=head + k * .25, duration_beats=.25, pitch=42, velocity=70, kind="hat")
    for t, p, v in ((0, 49, 100), (0, 36, 90), (1, 38, 95), (2, 38, 95), (1.5, 36, 85)):
        tl.add_note(start_beat=head + t, duration_beats=.25, pitch=p, velocity=v, kind="x")
    tl.add_note(start_beat=head + 3, duration_beats=.25, pitch=42, velocity=70, kind="hat")  # bar 2
    recipe = TransitionRecipe(kind="bridge_start", bridge_start_bars=1)
    plan = TransitionPlan(section_a_id="a", section_b_id="b", instrument="drums", recipe=recipe,
                          edit_windows={"tail": (8.0, 12.0), "head": (head, head + 3)},
                          metadata={"profile_a": EnergyProfile(1.0, 80, 50, 0, 0),
                                    "profile_b": EnergyProfile(5.0, 80, 50, 0, 0),
                                    "beats_per_bar_b": 3.0, "composed_drums": False})
    apply_transition_plan(tl, "drums", plan)
    first = [e for e in tl.events if e.start_beat < head + 3]
    assert {(e.start_beat - head, e.pitch) for e in first if e.pitch != 42} == {
        (0, 49), (0, 36), (1, 38), (2, 38), (1.5, 36)}
    assert 0 < len([e for e in first if e.pitch == 42]) < 12
    assert any(e.start_beat == head + 3 for e in tl.events)       # bar 2 is not the bridge start
    composed = replace(plan, metadata=dict(plan.metadata, composed_drums=True))
    before = len(tl.events)
    apply_transition_plan(tl, "drums", composed)
    assert len(tl.events) == before


# --- #14 solo drums -----------------------------------------------------------------

@pytest.mark.parametrize("genre", ["rock", "pop", "metal", "funk", "country"])
def test_solo_drums_keep_the_backbeat_and_answer_on_the_toms(genre):
    for seed in range(30):
        dna = compose_drum_dna(seed=seed, genre=genre)
        args = dict(section_type="verse", bars=8, beats_per_bar=4, next_section_type="verse")
        band = plan_drum_section(dna, _arr(), **args)
        solo = plan_drum_section(dna, _arr(), solo=True, **args)
        backbeats = lambda hits: sorted(h.beat for h in hits if h.kind == "snare")
        assert backbeats(solo) == backbeats(band)
        answers = [h for h in solo if h.kind == "solo_answer"]
        assert all(h.voice.startswith("tom") for h in answers)
        assert all(h.beat % 4 >= 3 - 1e-6 for h in answers)          # the bar's last beat
        assert all(int(h.beat // 4) % 4 in (1, 3) for h in answers)  # answer bars only
        for bar in (1, 3, 5):
            # Every answer bar answers: toms, or the song's own fill.
            assert any(4 * bar + 3 - 1e-6 <= h.beat < 4 * bar + 4 and h.kind in ("solo_answer", "fill")
                       for h in solo), (seed, bar)


# --- #15 feel knobs everywhere --------------------------------------------------------

@pytest.mark.parametrize("genre", ["rock", "pop", "country", "reggae", "jazz", "dance_pop", "metal"])
def test_hat_and_kick_density_reach_every_section(genre):
    def per_bar(dna, st, pick):
        hits = plan_drum_section(dna, _arr(into_chorus="fill"), section_type=st, bars=4,
                                 beats_per_bar=4, next_section_type="verse")
        return statistics.mean(len([h for h in bar if pick(h)]) for bar in _bars(hits, 4, 4)[1:3])
    hand = lambda h: h.voice in ("hat_closed", "hat_open", "ride", "tom_low") and h.kind not in ("fill", "perc")
    kick = lambda h: h.voice == "kick"
    for seed in range(20):
        dna = compose_drum_dna(seed=seed, genre=genre)
        for st in ("verse", "chorus", "bridge", "solo", "outro"):
            dense, sparse = apply_feel_knobs(dna, hat_density=0.9), apply_feel_knobs(dna, hat_density=0.1)
            assert per_bar(dense, st, hand) > per_bar(sparse, st, hand), (seed, st)
            assert per_bar(sparse, st, hand) <= 4
            if genre != "dance_pop":
                many, few = apply_feel_knobs(dna, kick_density=0.9), apply_feel_knobs(dna, kick_density=0.1)
                assert per_bar(many, st, kick) > per_bar(few, st, kick), (seed, st)


def test_density_knobs_shape_the_composed_chorus(tmp_path):
    secs = {"verse": {"type": "verse", "bars": 4, "harmony": {"progression": "I IV V I"}},
            "chorus": {"type": "chorus", "bars": 4, "harmony": {"progression": "IV V I I"}}}
    counts = {}
    for knobs in ({"hat_density": 0.9, "kick_density": 0.9}, {"hat_density": 0.1, "kick_density": 0.1}):
        tl, res = _render_timelines(_song(tmp_path, f"k{knobs['hat_density']}", sections=secs,
                                          arrangement=["verse", "chorus"], drums=knobs))
        _, (_, chorus) = _by_section(tl["drums"], res)
        counts[knobs["hat_density"]] = (len([e for e in chorus if e.pitch in (42, 46, 51)]),
                                        len([e for e in chorus if e.pitch == 36]))
    assert counts[0.9][0] > 2 * counts[0.1][0]
    assert counts[0.9][1] > counts[0.1][1]


# --- #27 ride bell --------------------------------------------------------------------

def test_classic_ride_bell_accents_survive_groove_memory(tmp_path, monkeypatch):
    import produzre.engine.drums.patterns.kit as kit

    made = []
    original = kit.generate_ride_bell_events

    def spy(**kwargs):
        out = original(**kwargs)
        made.extend(out)
        return out

    monkeypatch.setattr(kit, "generate_ride_bell_events", spy)
    secs = {"chorus": {"type": "chorus", "bars": 16, "harmony": {"progression": "I V vi IV"},
                       "instruments": {"harmony": {}, "drums": {"params": {"groove": "chorus_ride"},
                                                                "extra": {"voices": {"ride": {"bell_rate": 0.4}}}}}}}
    for seed in range(5):
        made.clear()
        tl, _ = _render_timelines(_song(tmp_path, f"bell{seed}", seed=seed, sections=secs,
                                        arrangement=["chorus"]))
        bells = [e for e in tl["drums"].events if e.pitch == 53]
        assert made and len(bells) == len(made)
