"""Drum and transition fixes found after the 2026-09-26 drum review: ramps
protect the composed drummer's fills, builds and devices and use the
section's meter; drums never get pitched pickups; the drop intent plays
closed hats; one hit per voice per step; solo answers stay out of arranged
bars; groove memory recalls only within an intent. Property tests over many
seeds, genres and meters, not single-seed MIDI pins."""
from __future__ import annotations

import collections

import pytest

import produzre.orchestrate.transitions as T
from produzre.composer.drums import compose_drum_dna, plan_drum_section
from produzre.composer.groove_memory import GrooveMemory, apply_groove_memory
from produzre.orchestrate.transitions import (EnergyProfile, TransitionPlan, TransitionRecipe,
                                              apply_transition_plan)
from produzre.timeline import InstrumentTimeline, NoteEvent
from tests.test_album_diversity import _arr
from tests.test_drum_review_fixes import _by_section, _song
from tests.test_groove_clock import _render_timelines

ARRANGED = ("fill", "snare_build", "snare_pickup", "tom_pickup")
DRUM_PITCHES = {35, 36, 37, 38, 39, 40, 42, 44, 45, 46, 47, 49, 50, 51, 52, 53, 54, 55, 56, 57, 70}


def _render_forced(monkeypatch, cfg, kind):
    orig = T.choose_transition_recipe
    calls = []

    def choose(a, b, settings, rng, logger=None):
        calls.append(1)
        return TransitionRecipe(kind=kind, ramp_bars=getattr(settings, "ramp_bars", 1))
    monkeypatch.setattr(T, "choose_transition_recipe", choose)
    try:
        return _render_timelines(cfg)
    finally:
        monkeypatch.setattr(T, "choose_transition_recipe", orig)


def _secs():
    """A song whose section ids are unique, so each payload is its occurrence's."""
    prog = {"verse": "I IV V I", "chorus": "IV V I I", "bridge": "vi IV I V"}
    return {sid: {"type": st, "bars": 4, "harmony": {"progression": prog[st]}}
            for sid, st in (("verse", "verse"), ("chorus", "chorus"), ("verse2", "verse"),
                            ("bridge", "bridge"), ("chorus2", "chorus"))}


ORDER = ["verse", "chorus", "verse2", "bridge", "chorus2"]


def _transitions(**kw):
    return {"params": {"transitions": dict({"enabled": True, "strength": 1.0}, **kw)}}


# --- #1 ramps protect the drummer's own transitions ----------------------------------

@pytest.mark.parametrize("meter", ["4/4", "6/8", "3/4"])
@pytest.mark.parametrize("device", ["fill", "build", "stop", "drop", "push"])
def test_ramp_down_leaves_composed_fills_builds_and_devices(tmp_path, monkeypatch, meter, device):
    for seed, genre in ((1, "rock"), (2, "pop"), (3, "hard_rock")):
        cfg = _song(tmp_path, f"r{device}{meter[0]}{seed}", genre=genre, seed=seed, meter=meter,
                    sections=_secs(), arrangement=ORDER,
                    song_extra={"arrangement_style": {"into_chorus": device}, **_transitions(ramp_bars=2)},
                    drums={"push_pull": 0.08})
        tl, res = _render_forced(monkeypatch, cfg, "ramp_down")
        for meta, played in _by_section(tl["drums"], res):
            planned = res.performance_plan.get(f"composer.drums.{meta.id}") or []
            want = collections.Counter(h["kind"] for h in planned if h["kind"] in ARRANGED)
            got = collections.Counter(e.kind for e in played if e.kind in ARRANGED)
            assert got == want, (seed, meta.id, device, meter)


def test_composed_drums_register_their_transitions_as_device_windows():
    for genre in ("rock", "pop", "metal", "country", "dance_pop", "jazz", "reggae"):
        for seed in range(12):
            dna = compose_drum_dna(seed=seed, genre=genre)
            for device in ("fill", "build", "stop", "drop", "push"):
                for bpb, groups in ((4.0, None), (3.0, (1.5, 1.5)), (3.0, None)):
                    windows = []
                    hits = plan_drum_section(dna, _arr(into_chorus=device), section_type="verse", bars=8,
                                             beats_per_bar=bpb, next_section_type="chorus",
                                             groups=groups, windows=windows)
                    for h in (h for h in hits if h.kind in ARRANGED):
                        assert any(s - 1e-6 <= h.beat < e for s, e in windows), (genre, seed, device, h)
                    # The last bar is the drummer's transition, whatever the device.
                    assert any(s < 8 * bpb and e > 7 * bpb for s, e in windows)


def _tail_plan(kind, tail, bpb, **meta):
    recipe = TransitionRecipe(kind=kind, ramp_bars=1)
    return TransitionPlan(section_a_id="a", section_b_id="b", instrument="drums", recipe=recipe,
                          edit_windows={"tail": tail, "head": (tail[1], tail[1] + bpb)},
                          metadata=dict({"beats_per_bar_a": bpb}, **meta))


@pytest.mark.parametrize("bpb", [3.0, 4.0, 5.0, 6.0])
def test_ramp_down_thins_engine_hands_in_the_sections_meter(bpb):
    for shift in (-0.03, 0.0, 0.03):              # a humanized drummer, early or late
        tl = InstrumentTimeline(instrument="drums")
        tail = (2 * bpb, 3 * bpb)                     # bar 3 of a section in this meter
        for k in range(int(bpb * 4)):
            tl.add_note(start_beat=tail[0] + k * .25 + shift, duration_beats=.25, pitch=42,
                        velocity=70, kind="hat")
        for t, p in ((0, 36), (0, 49), (1, 38), (bpb - 1, 38)):
            tl.add_note(start_beat=tail[0] + t + shift, duration_beats=.25, pitch=p, velocity=96, kind="x")
        # The next section's downbeat, pushed a hair early, is not the tail's.
        tl.add_note(start_beat=tail[1] - .02, duration_beats=.25, pitch=36, velocity=100, kind="kick")
        apply_transition_plan(tl, "drums", _tail_plan("ramp_down", tail, bpb))
        bar = [e for e in tl.events if e.start_beat < tail[1] - .06]
        assert {(round(e.start_beat - shift - tail[0], 3), e.pitch) for e in bar if e.pitch != 42} == {
            (0, 36), (0, 49), (1, 38), (bpb - 1, 38)}
        hats = [e for e in bar if e.pitch == 42]
        assert any(abs(e.start_beat - shift - tail[0]) < 1e-6 for e in hats)   # the downbeat hat
        assert 0 < len(hats) < bpb * 4
        nxt = [e for e in tl.events if e.start_beat >= tail[1] - .06]
        assert len(nxt) == 1 and nxt[0].velocity == 100


# --- #2 no pitched drum pickups ---------------------------------------------------

@pytest.mark.parametrize("composer", [True, False])
def test_drum_pickups_are_snares_or_nothing(tmp_path, monkeypatch, composer):
    for seed, genre in ((1, "rock"), (2, "blues"), (3, "pop"), (4, "country")):
        cfg = _song(tmp_path, f"p{composer}{seed}", genre=genre, seed=seed, sections=_secs(),
                    arrangement=ORDER, drums={"composer": composer}, song_extra=_transitions())
        tl, res = _render_forced(monkeypatch, cfg, "pickup")
        drums = tl["drums"].events
        assert all(e.pitch in DRUM_PITCHES for e in drums)
        picks = [e for e in drums if e.kind == "pickup_transition"]
        assert all(e.pitch in (37, 38, 40) for e in picks)
        if composer:
            assert not picks          # the composed drummer writes its own lead-ins
        # A pickup never lands on a snare already there.
        for p in picks:
            assert not [e for e in drums if e is not p and e.pitch in (37, 38, 40)
                        and abs(e.start_beat - p.start_beat) < 0.06]


def test_engine_drum_pickup_is_a_snare_on_the_last_sixteenth():
    tl = InstrumentTimeline(instrument="drums")
    for k in range(8):
        tl.add_note(start_beat=k * .5, duration_beats=.25, pitch=42, velocity=70, kind="hat")
    for t, p in ((0, 36), (1, 40), (3, 40), (4, 36)):
        tl.add_note(start_beat=t, duration_beats=.25, pitch=p, velocity=95, kind="x")
    plan = _tail_plan("pickup", (0.0, 4.0), 4.0, composed_drums_a=False)
    plan.recipe.kind = "pickup"
    apply_transition_plan(tl, "drums", plan)
    picks = [e for e in tl.events if e.kind == "pickup_transition"]
    assert [(e.start_beat, e.pitch) for e in picks] == [(3.75, 40)]   # the kit's own snare
    composed = _tail_plan("pickup", (0.0, 4.0), 4.0, composed_drums_a=True)
    before = len(tl.events)
    apply_transition_plan(tl, "drums", composed)
    assert len(tl.events) == before


# --- #3 drop plays closed hats ----------------------------------------------------

@pytest.mark.parametrize("genre", ["hard_rock", "rock", "pop", "funk", "blues", "metal"])
def test_drop_intent_plays_closed_hats_only_unless_the_user_opens_them(tmp_path, genre):
    for seed in range(3):
        secs = {"verse": {"type": "verse", "bars": 4, "harmony": {"progression": "I IV V I"}},
                "drop": {"type": "bridge", "intent": "drop", "bars": 8, "energy": 0.9,
                         "harmony": {"progression": "vi IV I V"}},
                "stomp": {"type": "breakdown", "intent": "stomp", "bars": 8, "energy": 0.9,
                          "harmony": {"progression": "vi IV I V"}}}
        tl, res = _render_timelines(_song(tmp_path, f"d{genre}{seed}", genre=genre, seed=seed,
                                          sections=secs, arrangement=["verse", "drop", "stomp"]))
        for meta, evs in _by_section(tl["drums"], res):
            if meta.id in ("drop", "stomp"):
                assert not [e for e in evs if e.pitch in (46, 51)], (genre, seed, meta.id)
                assert any(e.pitch == 42 for e in evs)
    secs["drop"]["instruments"] = {"harmony": {}, "drums": {"extra": {"voices": {"hats": {
        "open": {"rate": 1.0}}}}}}
    tl, res = _render_timelines(_song(tmp_path, f"du{genre}", genre=genre, sections=secs,
                                      arrangement=["verse", "drop"]))
    (_, _), (_, drop) = _by_section(tl["drums"], res)
    assert any(e.pitch == 46 for e in drop)          # the user's own open hats win


# --- #4 one hit per voice per step ---------------------------------------------------

def test_planner_plays_one_hit_per_voice_per_step():
    for genre in ("rock", "pop", "metal", "country", "reggae", "jazz", "dance_pop", "blues"):
        for seed in range(15):
            dna = compose_drum_dna(seed=seed, genre=genre)
            for ending in ("ring", "cold", "big"):
                for st, nxt, first in (("intro", "verse", True), ("verse", "chorus", False),
                                       ("chorus", None, False), ("bridge", "chorus", False)):
                    for arr in (_arr(ending=ending, intro="riff_alone"), _arr(ending=ending, into_chorus="push")):
                        hits = plan_drum_section(dna, arr, section_type=st, bars=8, beats_per_bar=4,
                                                 next_section_type=nxt, is_first_section=first)
                        keys = collections.Counter((h.voice, round(h.beat, 3)) for h in hits)
                        assert max(keys.values()) == 1, (genre, seed, st, ending,
                                                         [k for k, n in keys.items() if n > 1])


def test_performed_drums_sound_one_hit_per_kit_piece_per_step(tmp_path):
    for seed, genre in ((1, "rock"), (2, "country"), (3, "pop"), (4, "reggae"), (5, "hard_rock")):
        secs = {"intro": {"type": "intro", "bars": 4, "harmony": {"progression": "I IV V I"}},
                "verse": {"type": "verse", "bars": 8, "harmony": {"progression": "I IV V I"}},
                "chorus": {"type": "chorus", "bars": 8, "harmony": {"progression": "IV V I I"},
                           "instruments": {"harmony": {}, "drums": {"extra": {"voices": {
                               "crash": {"rate": 0.8}, "ride": {"bell_rate": 0.5}}}}}},
                "outro": {"type": "outro", "bars": 4, "harmony": {"progression": "I V I I"}}}
        tl, _ = _render_timelines(_song(tmp_path, f"u{seed}", genre=genre, seed=seed, sections=secs,
                                        arrangement=["intro", "verse", "chorus", "verse", "chorus", "outro"]))
        by_pitch = collections.defaultdict(list)
        for e in tl["drums"].events:
            by_pitch[e.pitch].append(e.start_beat)
        for pitch, beats in by_pitch.items():
            beats.sort()
            gaps = [b - a for a, b in zip(beats, beats[1:])]
            assert not gaps or min(gaps) > 0.02, (genre, pitch)


# --- #5 solo answers stay out of fills and builds --------------------------------------

@pytest.mark.parametrize("genre", ["rock", "pop", "metal", "funk", "country"])
def test_solo_answers_never_play_in_a_build_fill_or_device_bar(genre):
    for seed in range(25):
        dna = compose_drum_dna(seed=seed, genre=genre)
        for device in ("build", "fill", "stop", "push", "drop"):
            for bpb, groups in ((4.0, None), (3.0, (1.5, 1.5)), (6.0, (1.5,) * 4)):
                hits = plan_drum_section(dna, _arr(into_chorus=device), section_type="verse", bars=8,
                                         beats_per_bar=bpb, next_section_type="chorus", groups=groups,
                                         solo=True)
                arranged = {int(h.beat // bpb) for h in hits if h.kind in ARRANGED}
                answers = {int(h.beat // bpb) for h in hits if h.kind == "solo_answer"}
                assert not arranged & answers, (seed, device, bpb, sorted(arranged & answers))
                last = [h for h in hits if h.beat >= 7 * bpb]
                if device == "build":
                    assert any(h.kind == "snare_build" for h in last)


# --- #6 groove memory recalls within an intent -----------------------------------------

def _drum_bar_events(start, snare_at, hat_open=False):
    evs = []
    for bar in range(4):
        t0 = start + 4 * bar
        evs += [NoteEvent(t0, .25, 36, 100, 9, "kick"), NoteEvent(t0 + snare_at, .25, 38, 100, 9, "snare")]
        evs += [NoteEvent(t0 + k * .5, .25, 46 if hat_open and k % 4 == 1 else 42, 70, 9, "hat")
                for k in range(8)]
    return evs


def test_groove_memory_recalls_only_within_an_intent():
    args = dict(instrument="drums", beats_per_bar=4.0, bars=4, chord_slots=None, key="C", mode="major",
                genre="rock", bpm=120.0, seed=1)
    for first, second in (("drop", "half_time"), ("drop", None), (None, "drop"), ("build", "open")):
        memory = GrooveMemory()
        key = ("drums", "bridge", 4.0, 7)
        apply_groove_memory(_drum_bar_events(0.0, 1.0, hat_open=True), section_start=0.0, memory=memory,
                            memory_key=key, intent=first, **args)
        out, report = apply_groove_memory(_drum_bar_events(16.0, 2.0), section_start=16.0,
                                          memory=memory, memory_key=key, intent=second, **args)
        assert not report["recalled"]
        assert {round((e.start_beat - 16) % 4, 2) for e in out if e.pitch == 38} == {2.0}
        assert not any(e.pitch == 46 for e in out)
        # The same intent still recalls its groove.
        _, again = apply_groove_memory(_drum_bar_events(32.0, 2.0), section_start=32.0,
                                       memory=memory, memory_key=key, intent=second, **args)
        assert again["recalled"]


def test_half_time_bridge_after_a_drop_keeps_its_snare_on_three(tmp_path):
    for seed, genre in ((1, "hard_rock"), (2, "rock"), (3, "pop"), (4, "metal")):
        secs = {"verse": {"type": "verse", "bars": 4, "harmony": {"progression": "i bVI bIII bVII"}},
                "drop": {"type": "bridge", "intent": "drop", "bars": 4,
                         "harmony": {"progression": "bVI bIII bVII i"}},
                "half": {"type": "bridge", "intent": "half_time", "bars": 4,
                         "harmony": {"progression": "bVI bIII bVII i"}}}
        tl, res = _render_timelines(_song(tmp_path, f"h{seed}", genre=genre, seed=seed, sections=secs,
                                          arrangement=["verse", "drop", "half"]))
        (_, _), (_, drop), (meta, half) = _by_section(tl["drums"], res)
        # Groove bars (the phrase's last bar may fill): the lone backbeat on 3.
        for bar in range(3):
            t0 = meta.start_beat + 4 * bar
            snares = {round(e.start_beat - t0, 1) for e in half
                      if e.pitch == 38 and e.kind == "snare" and t0 - .1 <= e.start_beat < t0 + 3.9}
            assert snares == {2.0}, (genre, seed, bar, snares)
