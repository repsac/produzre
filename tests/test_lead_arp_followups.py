"""Lead guitar and arpeggiator follow-ups to the examples review (2026-09-26).

Octave stabs that sound both notes in every bar, `dive_rate` across solo
phrase endings, a build log that names the solo ending played, trills that
survive swing, and riff-alone intros where only the riff plays before the
band. See "Lead and arpeggiator follow-ups" in
docs/design/composer-architecture.md. Every test pins a musical property
over several seeds, keys, registers or genres, not exact notes.
"""
from __future__ import annotations

import collections
import random
from types import SimpleNamespace as NS

import pytest
import yaml

from produzre.composer.arrangement import compose_arrangement_dna, dives_in
from produzre.composer.lead import LeadContext, SongComposer
from produzre.composer.theory import ChordMap
from produzre.timeline import InstrumentTimeline
from tests.test_groove_clock import _load_cfg, _render_timelines

_PROGS = (("I", "V", "vi", "IV"), ("i", "bVI", "bIII", "bVII"), ("I", "bVII", "IV", "IV"),
          ("vi", "IV", "I", "V"), ("ii7", "V7", "Imaj7", "vi7"))
_KEYS = ("C", "D", "E", "F", "Ab", "B")


def _slots(prog, bpb=4.0):
    return [NS(numeral=n, start_beat=i * bpb, end_beat=(i + 1) * bpb, index=i)
            for i, n in enumerate(prog)]


def _mode(prog):
    return "minor" if prog[0].startswith("i") and not prog[0].startswith("ii") else "major"


def _octave_chorus(seed, key, prog, register, bars=8):
    mode = _mode(prog)
    comp = SongComposer(seed=seed, genre="rock", key=key, mode=mode, beats_per_bar=4.0,
                        hook_slots=_slots(prog[:2]), verse_slots=_slots(prog[:2]),
                        register=register, arrangement_overrides={"counter": "octaves"})
    slots = _slots([prog[i % len(prog)] for i in range(bars)])
    ctx = LeadContext("chorus", "chorus", 0, False, bars, 4.0, bars * 4.0, key, mode, slots,
                      foreground="auto", register=register)
    return comp.compose_lead(ctx), ChordMap(slots, key, mode)


# --- octave stabs ----------------------------------------------------------------

@pytest.mark.parametrize("seed", range(3))
def test_octave_stabs_sound_both_notes_in_every_bar_of_any_register(seed):
    rng = random.Random(seed)
    for _ in range(12):
        key, prog = rng.choice(_KEYS), rng.choice(_PROGS)
        lo = rng.randint(52, 66)
        register = (lo, lo + rng.randint(12, 30))
        notes, chords = _octave_chorus(seed, key, prog, register)
        stabs = [n for n in notes if n.role in ("stab", "stab_octave")]
        attacks = collections.defaultdict(list)
        for n in stabs:
            attacks[n.beat].append(n.pitch)
        assert all(register[0] <= n.pitch <= register[1] for n in stabs)
        # Every bar of the counter (the last two are the hook's tag) is hit.
        assert {int(b // 4) for b in attacks} >= set(range(6)), (key, prog, register)
        for beat, pitches in attacks.items():
            span = chords.at(beat)
            fits = any(p % 12 in span.pcs for p in range(register[0], register[1] - 11))
            if fits:
                # Both strings, an octave apart, on a chord tone.
                assert len(pitches) == 2 and max(pitches) - min(pitches) == 12, (beat, pitches)
                assert min(pitches) % 12 in span.pcs
                # The root's octave whenever it fits.
                if any(p % 12 == span.root_pc for p in range(register[0], register[1] - 11)):
                    assert min(pitches) % 12 == span.root_pc
            else:
                assert len(pitches) == 1


def _octave_song(tmp_path, seed, key, register, name):
    inst = {"harmony": {}, "drums": {}, "bass": {}, "rhythm_gtr": {}, "lead_gtr": {}}
    data = {
        "song": {"title": "Octaves", "seed": seed, "genre": "new_wave", "key": key,
                 "mode": "major", "bpm": 134, "arrangement_style": {"counter": "octaves"}},
        "instruments": {"lead_gtr": {"params": {"foreground": "auto", "register": register}}},
        "sections": {
            "verse": {"type": "verse", "bars": 4, "harmony": {"progression": "vi IV I V"},
                      "instruments": dict(inst)},
            "chorus": {"type": "chorus", "bars": 8, "harmony": {"progression": "I V vi IV"},
                       "instruments": dict(inst)},
        },
        "arrangement": ["verse", "chorus", "verse", "chorus"],
    }
    return _load_cfg(tmp_path, yaml.safe_dump(data, sort_keys=False), name)


@pytest.mark.parametrize("seed,key,register", [(8127, "D", [62, 81]), (5, "A", [60, 79]),
                                               (21, "F", [57, 76])])
def test_octave_stabs_survive_every_clip_in_a_song(tmp_path, seed, key, register):
    timelines, result = _render_timelines(_octave_song(tmp_path, seed, key, register,
                                                       f"o{seed}.yaml"))
    events = timelines["lead_gtr"].events
    for st in result.section_timings:
        if st.id != "chorus":
            continue
        stabs = [e for e in events if st.start_beat - 0.2 <= e.start_beat < st.end_beat - 8.2
                 and str(e.kind).startswith("stab")]
        by_start = collections.defaultdict(list)
        for e in stabs:
            by_start[round(e.start_beat, 6)].append(e)
        bars = {int((s - st.start_beat + 0.2) // 4) for s in by_start}
        assert bars >= set(range(6)), (seed, sorted(bars))
        for group in by_start.values():
            pitches = sorted(e.pitch for e in group)
            assert len(pitches) == 2 and pitches[1] - pitches[0] == 12, pitches
            assert all(e.duration_beats > 0.15 for e in group)


# --- dive_rate across solo phrase endings -----------------------------------------

def _solo_notes(seed):
    r = random.Random(seed)
    notes, t = [], 0.0
    for _ in range(48):
        dur = r.choice((0.25, 0.5, 1.0, 1.5, 2.0, 3.0))
        tech = r.choice((None, None, "vib", "bend2", "stac", "fall", "slide"))
        notes.append({"beat": t, "duration_beats": dur, "pitch": r.choice((64, 67, 69, 71, 74)),
                      "tech": tech, "role": r.choice(("melody", "lick", "stab"))})
        t += dur + 0.25
    notes.append({"beat": t, "duration_beats": 4.0, "pitch": 64, "tech": "dive",
                  "role": "melody"})
    return notes


def _dived(dive_rate, notes, solo=True):
    from produzre.engine.lead_gtr import _perform_composed

    tl = InstrumentTimeline(instrument="lead_gtr")
    _perform_composed(notes, timeline=tl, section_start_beat=0.0, base_vel=90, intensity=0.8,
                      solo=solo, rng=random.Random(4), bpm=120.0, beats_per_bar=4.0,
                      vibrato_rate=0.5, dive_rate=dive_rate, swell_rate=0.0, bend_rate=0.15)
    return {round(e.start_beat * 4) / 4 for e in tl.events
            if e.expression and "dive" in e.expression and str(e.kind).endswith("_dive")}


@pytest.mark.parametrize("seed", range(4))
def test_dive_rate_scales_dives_across_held_solo_notes(seed):
    notes = _solo_notes(seed)
    composed = {n["beat"] for n in notes if n["tech"] == "dive"}
    held = {n["beat"] for n in notes if n["duration_beats"] >= 1.5 and n["role"] != "stab"
            and n["tech"] in (None, "vib", "slide", "bend2")}
    counts = [len(_dived(rate, notes)) for rate in (0.0, 0.3, 0.5, 0.75, 1.0)]
    assert counts[0] == 0
    assert counts == sorted(counts)
    assert _dived(0.3, notes) == composed            # the default plays what was written
    assert _dived(1.0, notes) == composed | held     # every held phrase ending at 1
    assert counts[2] > counts[1]
    # Outside a solo only the composed dive plays.
    assert _dived(1.0, notes, solo=False) == composed


def _dive_song(tmp_path, seed, genre, name):
    inst = {"harmony": {}, "drums": {}, "bass": {}, "rhythm_gtr": {}, "lead_gtr": {}}
    data = {
        "song": {"title": "Dives", "seed": seed, "genre": genre, "key": "E", "mode": "minor",
                 "bpm": 108, "arrangement_style": {"solo_ending": "dive"}},
        "instruments": {"lead_gtr": {"params": {"foreground": "full"}}},
        "sections": {
            "chorus": {"type": "chorus", "bars": 4, "harmony": {"progression": "i bVI bIII bVII"},
                       "instruments": dict(inst)},
            "solo": {"type": "solo", "bars": 8, "harmony": {"progression": "i bVII bVI bVII"},
                     "instruments": {**inst, "lead_gtr": {"params": {"dive_rate": 1.0}}}},
        },
        "arrangement": ["chorus", "solo", "chorus"],
    }
    return _load_cfg(tmp_path, yaml.safe_dump(data, sort_keys=False), name)


@pytest.mark.parametrize("seed,genre", [(5103, "hard_rock"), (7, "metal"), (11, "blues")])
def test_dive_rate_one_dives_every_held_note_of_a_solo_section(tmp_path, seed, genre):
    timelines, result = _render_timelines(_dive_song(tmp_path, seed, genre, f"d{seed}.yaml"))
    solo = next(st for st in result.section_timings if st.id == "solo")
    composed = result.performance_plan.get("composer.lead.solo")
    held = [n for n in composed if n["duration_beats"] >= 1.5 and n["role"] != "stab"
            and n.get("tech") in (None, "vib", "slide", "bend1", "bend2", "dive")]
    assert len(held) >= 2
    events = [e for e in timelines["lead_gtr"].events
              if solo.start_beat - 0.2 <= e.start_beat < solo.end_beat]
    for n in held:
        at = solo.start_beat + n["beat"]
        hit = [e for e in events if abs(e.start_beat - at) < 0.1 and e.pitch == n["pitch"]]
        assert hit and "dive" in (hit[0].expression or {}), (genre, n)


# --- the solo ending the log names is the one played ------------------------------

_TAIL_TECH = {"dive": "dive", "hold": "vib", "slide_off": "fall", "trill": "vib"}


def _final_solo(comp, genre, seed):
    prog = ["i", "bVII", "bVI", "bVII"]
    slots = _slots([prog[i % 4] for i in range(8)])
    ctx = LeadContext("solo", "solo", 0, True, 8, 4.0, 32.0, "E", "minor", slots,
                      foreground="full", register=(60, 79))
    return comp.compose_lead(ctx)


@pytest.mark.parametrize("genre", ["blues", "soul", "pop", "rock", "metal", "funk", "jazz"])
def test_drawn_solo_ending_is_the_one_played(genre):
    drawn = collections.Counter()
    for seed in range(40):
        dna = compose_arrangement_dna(seed=seed, genre=genre)
        drawn[dna.solo_ending] += 1
        assert dna.solo_ending != "dive" or dives_in(genre), (genre, seed)
        assert f"/{dna.solo_ending}," in dna.signature
        if seed % 5:
            continue
        comp = SongComposer(seed=seed, genre=genre, key="E", mode="minor", beats_per_bar=4.0,
                            hook_slots=_slots(["i", "bVII"]), verse_slots=_slots(["i", "bVI"]),
                            register=(60, 79))
        notes = _final_solo(comp, genre, seed)
        assert notes[-1].tech == _TAIL_TECH[comp.arrangement_dna().solo_ending], (genre, seed)
        assert comp.solo_ending_played == comp.arrangement_dna().solo_ending
        assert "ends" in comp.log[-1]
    if dives_in(genre):
        assert drawn["dive"] > 0


@pytest.mark.parametrize("genre", ["blues", "jazz", "rock"])
def test_pinned_dive_ending_dives_in_any_genre(genre):
    for seed in range(3):
        comp = SongComposer(seed=seed, genre=genre, key="E", mode="minor", beats_per_bar=4.0,
                            hook_slots=_slots(["i", "bVII"]), verse_slots=_slots(["i", "bVI"]),
                            register=(60, 79), arrangement_overrides={"solo_ending": "dive"})
        assert _final_solo(comp, genre, seed)[-1].tech == "dive"
        assert "whammy dive" in comp.log[-1]


# --- trills under swing -----------------------------------------------------------

def _trill_song(tmp_path, seed, swing, name):
    inst = {"harmony": {}, "drums": {}, "bass": {}, "lead_gtr": {}}
    data = {
        "song": {"title": "Trill", "seed": seed, "genre": "jazz", "key": "F", "mode": "major",
                 "bpm": 144, "arrangement_style": {"solo_story": "melodic", "solo_ending": "trill"}},
        "groove": {"swing": swing},
        "instruments": {"lead_gtr": {"params": {"foreground": "full", "bend_rate": 0.0}}},
        "sections": {
            "head": {"type": "chorus", "bars": 4, "harmony": {"progression": "ii7 V7 Imaj7 Imaj7"},
                     "instruments": dict(inst)},
            "solo": {"type": "solo", "bars": 8,
                     "harmony": {"progression": "ii7 V7 Imaj7 vi7 ii7 V7 Imaj7 Imaj7"},
                     "instruments": dict(inst)},
        },
        "arrangement": ["head", "solo", "head"],
    }
    return _load_cfg(tmp_path, yaml.safe_dump(data, sort_keys=False), name)


@pytest.mark.parametrize("seed,swing", [(5202, 0.67), (3, 0.5), (17, 0.8), (5202, 0.0)])
def test_trill_ending_stays_even_under_swing(tmp_path, seed, swing):
    timelines, result = _render_timelines(_trill_song(tmp_path, seed, swing, f"t{seed}{swing}.yaml"))
    solo = next(st for st in result.section_timings if st.id == "solo")
    composed = result.performance_plan.get("composer.lead.solo")
    trill = [n for n in composed if n["beat"] >= 28.0 - 1e-6 and n["duration_beats"] < 0.2]
    assert len(trill) == 8
    start = solo.start_beat + 28.0
    played = sorted((e for e in timelines["lead_gtr"].events
                     if start - 0.15 <= e.start_beat < start + 0.95), key=lambda e: e.start_beat)
    assert [e.pitch for e in played] == [n["pitch"] for n in trill]
    gaps = [b.start_beat - a.start_beat for a, b in zip(played, played[1:])]
    assert all(abs(g - 0.125) < 1e-6 for g in gaps), gaps
    assert all(e.duration_beats >= 0.09 for e in played)


# --- riff-alone intros: the riff alone ---------------------------------------------

def _riff_alone_song(tmp_path, seed, genre, *, riff=True, name="r.yaml"):
    intro = {"harmony": {}, "drums": {}, "bass": {}, "lead_gtr": {}, "arpeggiator": {}}
    if riff:
        intro["rhythm_gtr"] = {}
    band = {"harmony": {}, "drums": {}, "bass": {}, "rhythm_gtr": {}, "lead_gtr": {},
            "arpeggiator": {}}
    data = {
        "song": {"title": "Riff", "seed": seed, "genre": genre, "key": "A", "mode": "minor",
                 "bpm": 120, "arrangement_style": {"intro": "riff_alone"}},
        "instruments": {"lead_gtr": {"params": {"foreground": "full"}}},
        "sections": {
            "intro": {"type": "intro", "bars": 4, "harmony": {"progression": "i bVII bVI V"},
                      "instruments": intro},
            "verse": {"type": "verse", "bars": 4, "harmony": {"progression": "i bVI bIII bVII"},
                      "instruments": band},
        },
        "arrangement": ["intro", "verse"],
    }
    return _load_cfg(tmp_path, yaml.safe_dump(data, sort_keys=False), name)


@pytest.mark.parametrize("seed,genre", [(1, "rock"), (2, "pop"), (3, "blues"), (4, "new_wave")])
def test_riff_alone_intro_is_the_riff_alone_until_the_band_enters(tmp_path, seed, genre):
    timelines, _ = _render_timelines(_riff_alone_song(tmp_path, seed, genre,
                                                      name=f"r{seed}.yaml"))
    entry = 8.0  # the second half of the four-bar intro
    for part in ("drums", "bass", "lead_gtr", "arpeggiator"):
        # The drummer's pickup fill leads the band in.
        before = [e for e in timelines[part].events if e.start_beat < entry - 0.25
                  and not (part == "drums" and e.kind == "fill" and e.start_beat >= entry - 4)]
        assert not before, (part, [(round(e.start_beat, 2), e.kind) for e in before][:4])
        # Every part comes in with the band.
        assert any(entry - 0.25 <= e.start_beat < 16.0 for e in timelines[part].events), part
    assert any(e.start_beat < 1.0 for e in timelines["rhythm_gtr"].events)


def test_without_a_riff_player_the_whole_band_plays_the_intro(tmp_path):
    timelines, _ = _render_timelines(_riff_alone_song(tmp_path, 1, "rock", riff=False))
    for part in ("drums", "bass", "arpeggiator"):
        assert any(e.start_beat < 4.0 for e in timelines[part].events), part


def test_lead_composes_its_intro_from_the_entry_bar():
    for seed in range(6):
        comp = SongComposer(seed=seed, genre="rock", key="A", mode="minor", beats_per_bar=4.0,
                            hook_slots=_slots(["i", "bVII"]), verse_slots=_slots(["i", "bVI"]),
                            register=(60, 79))
        for bars, entry in ((4, 2), (8, 4), (6, 3)):
            slots = _slots(["i", "bVII", "bVI", "V"] * 2)[:bars]
            ctx = LeadContext("intro", "intro", 0, True, bars, 4.0, bars * 4.0, "A", "minor",
                              slots, foreground="full", register=(60, 79), entry_bar=entry)
            notes = comp.compose_lead(ctx)
            assert notes and min(n.beat for n in notes) >= entry * 4.0 - 1e-6, (seed, bars)
