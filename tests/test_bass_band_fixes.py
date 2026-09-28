"""Bass fixes from the examples review (docs/reviews/2026-09-26-examples-findings.md).

Property tests over many seeds, never a single pinned take:

- #5 walking bass walks: one note per beat, roots on each change, stepwise
  or chromatic approaches, no root repeated inside a bar, in 4/4 and 3/4,
  and groove memory leaves the walk alone;
- #6 no silent bars in band sections, repeated choruses keep their line;
- #9 the bass plays every ``into_chorus`` device (and endings) with the band;
- #11 one rule for who plays a riff-alone intro;
- #19 recipe register bounds are enforced, explicit bounds win;
- #20 groove memory keeps the root tie-break on beat 1;
- #21 an authored bass_motif owns the bass with its written rhythm;
- #22 articulation reaches the composer's bass roles.
"""
from __future__ import annotations

import pathlib
import random
from collections import Counter
from types import SimpleNamespace

import pytest
import yaml

from produzre.melody import chord_pitch_classes
from produzre.timeline import NoteEvent
from tests.test_groove_clock import _load_cfg, _render_timelines


def _render(tmp_path, *, genre="rock", meter="4/4", seed=1, key="C", mode="major", bass=None,
            sections=None, arrangement=None, style=None, themes=None, instruments=None,
            name="song.yaml"):
    song = {"title": "BassFix", "seed": seed, "genre": genre, "meter": meter, "key": key,
            "mode": mode, "bpm": 120}
    if style:
        song["arrangement_style"] = style
    data = {"song": song, "instruments": {"bass": bass or {}, **(instruments or {})},
            "sections": sections, "arrangement": arrangement or list(sections)}
    if themes:
        data["themes"] = themes
    pathlib.Path(tmp_path).mkdir(parents=True, exist_ok=True)
    cfg = _load_cfg(tmp_path, yaml.safe_dump(data, sort_keys=False), name=name)
    timelines, result = _render_timelines(cfg)
    return timelines, result


def _band(progression, bars=8, stype="verse", extra=()):
    parts = {"harmony": {}, "drums": {}, "bass": {}, "rhythm_gtr": {}}
    parts.update({k: {} for k in extra})
    return {"type": stype, "bars": bars, "harmony": {"progression": progression},
            "instruments": parts}


def _occurrences(result):
    return list(result.performance_plan.sections)


def _local(events, meta):
    """(local beat, event) pairs for one arrangement occurrence."""
    return [(e.start_beat - meta.start_beat, e) for e in events
            if meta.start_beat - 0.06 <= e.start_beat < meta.end_beat - 0.06]


def _bar_of(local, bpb):
    return int((local + 0.06) // bpb)


# ---------------------------------------------------------------------------
# #5 walking bass
# ---------------------------------------------------------------------------

_WALK_PROGRESSION = ["Imaj7", "vi7", "ii7", "V7", "iii7", "VI7", "ii7", "V7"]


def _walk(tmp_path, seed, meter, bass, genre="jazz"):
    sections = {"head": {"type": "verse", "bars": 8,
                         "harmony": {"progression": " ".join(_WALK_PROGRESSION)},
                         "instruments": {"harmony": {}, "drums": {}, "bass": {},
                                         "rhythm_gtr": {}}}}
    timelines, result = _render(tmp_path, genre=genre, meter=meter, seed=seed, key="Bb",
                                bass=bass, sections=sections, arrangement=["head", "head"],
                                name=f"walk{seed}{meter.replace('/', '')}{genre}.yaml")
    return timelines, result


@pytest.mark.parametrize("meter", ["4/4", "3/4"])
@pytest.mark.parametrize("bass", [
    {"persona": "walking"},                                  # persona under the jazz recipe
    {"params": {"rhythm_pattern": "walking"}},               # the documented param
    {"persona": "walking", "params": {"rhythm_pattern": "walking"}},
])
def test_walking_line_walks(tmp_path, meter, bass):
    bpb = int(meter.split("/")[0])
    for seed in range(1, 6):
        timelines, result = _walk(tmp_path, seed, meter, bass)
        first = _occurrences(result)[0]  # the second head ends the song (ending device)
        notes = sorted(_local(timelines["bass"].events, first), key=lambda x: x[0])
        by_bar = {}
        for t, e in notes:
            by_bar.setdefault(_bar_of(t, bpb), []).append((t, e))
        assert sorted(by_bar) == list(range(8)), f"seed {seed}: a bar is missing"
        prev = None
        for bar in range(8):
            row = by_bar[bar]
            # One note per beat, every beat, downbeat included.
            beats = [round(t - bar * bpb) for t, _ in row]
            assert beats == list(range(bpb)), f"seed {seed} bar {bar}: {beats}"
            root_pc = chord_pitch_classes(_WALK_PROGRESSION[bar], "Bb", "major")[0]
            pitches = [e.pitch for _, e in row]
            assert pitches[0] % 12 == root_pc, f"seed {seed} bar {bar}: downbeat is not the root"
            # Chord tone on beat 3 of a 4/4 bar (the other strong beat).
            if bpb == 4:
                assert pitches[2] % 12 in chord_pitch_classes(_WALK_PROGRESSION[bar], "Bb", "major")
            assert all(p % 12 != root_pc for p in pitches[1:]), \
                f"seed {seed} bar {bar}: root repeated in the bar {pitches}"
            assert all(28 <= p <= 52 for p in pitches)
            if prev is not None:
                # The last beat before the change steps into the new root.
                assert 1 <= abs(pitches[0] - prev) <= 2, \
                    f"seed {seed} bar {bar}: approach {prev} -> {pitches[0]}"
            assert all(a != b for a, b in zip(pitches, pitches[1:]))
            prev = pitches[-1]
            assert all(str(e.kind).startswith("walk_") for _, e in row)


@pytest.mark.parametrize("genre", ["blues", "rock", "hard_rock"])
def test_walking_persona_walks_under_any_recipe(tmp_path, genre):
    # The blues recipe asks for a "push" pattern and rock songs give the bass
    # composed roles; a walking persona keeps its walk through both.
    for seed in (1, 2, 3):
        timelines, result = _walk(tmp_path, seed, "4/4", {"persona": "walking"}, genre=genre)
        first = _occurrences(result)[0]
        notes = _local(timelines["bass"].events, first)
        assert len(notes) == 32 and all(str(e.kind).startswith("walk_") for _, e in notes)


def test_groove_memory_leaves_walking_lines_alone(tmp_path):
    from produzre.composer.groove_memory import apply_groove_memory

    events = []
    for bar in range(8):
        for beat in range(4):
            events.append(NoteEvent(start_beat=bar * 4 + beat, duration_beats=0.9,
                                    pitch=36 + (bar * 3 + beat) % 12, velocity=80,
                                    kind="walk_chord", channel=None))
    out, report = apply_groove_memory(events, instrument="bass", section_start=0.0,
                                      beats_per_bar=4, bars=8, chord_slots=None, key="C",
                                      mode="major", genre="jazz", bpm=120, memory=None,
                                      memory_key=None, seed=1)
    assert out is events and not report["applied"]


def test_walking_line_is_deterministic(tmp_path):
    a, _ = _walk(tmp_path / "a", 4, "3/4", {"persona": "walking"})
    b, _ = _walk(tmp_path / "b", 4, "3/4", {"persona": "walking"})
    key = lambda tl: [(round(e.start_beat, 6), e.pitch, e.velocity, round(e.duration_beats, 6))
                      for e in tl["bass"].events]
    assert key(a) == key(b)


# ---------------------------------------------------------------------------
# #6 holes and repeated choruses
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("genre", ["blues", "blues_rock", "folk", "gospel", "pop"])
def test_band_sections_have_no_silent_bass_bars(tmp_path, genre):
    sections = {"verse": _band("I IV I V", 8), "chorus": _band("IV I V I", 8, "chorus")}
    for seed in range(1, 5):
        timelines, result = _render(tmp_path, genre=genre, seed=seed, sections=sections,
                                    arrangement=["verse", "chorus", "verse", "chorus"],
                                    style={"into_chorus": "fill", "intro": "full"},
                                    name=f"holes{genre}{seed}.yaml")
        for meta in _occurrences(result):
            bars = {_bar_of(t, 4) for t, _ in _local(timelines["bass"].events, meta)}
            assert bars == set(range(8)), \
                f"{genre} seed {seed} {meta.id}: silent bars {sorted(set(range(8)) - bars)}"


@pytest.mark.parametrize("genre", ["pop", "gospel", "blues", "rock"])
def test_repeated_choruses_keep_their_line(tmp_path, genre):
    sections = {"verse": _band("I IV I V", 8), "chorus": _band("IV I V vi", 8, "chorus")}
    for seed in range(1, 4):
        timelines, result = _render(tmp_path, genre=genre, seed=seed, sections=sections,
                                    arrangement=["verse", "chorus", "verse", "chorus", "chorus"],
                                    style={"into_chorus": "fill"}, name=f"rep{genre}{seed}.yaml")
        counts = [len(_local(timelines["bass"].events, m)) for m in _occurrences(result)
                  if m.type == "chorus"]
        assert len(counts) == 3
        # A returning chorus never thins out (the final one may lift and
        # add kick doubles; phrase-end fills vary a little).
        assert all(c >= 0.8 * counts[0] for c in counts[1:]), \
            f"{genre} seed {seed}: chorus counts {counts}"


# ---------------------------------------------------------------------------
# #9 into_chorus devices and endings
# ---------------------------------------------------------------------------

def _device_song(tmp_path, device, seed, bass=None, genre="rock", ending="ring"):
    sections = {"verse": _band("I IV V IV", 4), "chorus": _band("I V vi IV", 4, "chorus")}
    return _render(tmp_path, genre=genre, seed=seed, bass=bass, sections=sections,
                   arrangement=["verse", "chorus"],
                   style={"into_chorus": device, "ending": ending, "intro": "full"},
                   name=f"dev{device}{seed}{genre}{ending}.yaml")


def _last_bar(timelines, meta, inst="bass", bpb=4):
    last = meta.length_beats - bpb
    rows = [(t - last, e) for t, e in _local(timelines[inst].events, meta)]
    # Notes played a hair early by the groove clock still belong to the bar.
    held = [(t, e) for t, e in rows if t < -0.06 and t + e.duration_beats > 0.05]
    return sorted([(t, e) for t, e in rows if t >= -0.06], key=lambda x: x[0]), held


@pytest.mark.parametrize("bass", [None, {"persona": "walking"}, {"params": {"rhythm_pattern": "drive"}}])
@pytest.mark.parametrize("device", ["stop", "drop", "push", "fill", "build"])
def test_bass_plays_the_into_chorus_device(tmp_path, device, bass):
    for seed in range(1, 5):
        timelines, result = _device_song(tmp_path, device, seed, bass=bass)
        verse = _occurrences(result)[0]
        bar, held = _last_bar(timelines, verse)
        drums, _ = _last_bar(timelines, verse, "drums")
        onsets = [round(t * 4) / 4 for t, _ in bar]
        if device == "stop":
            # Hit on one with the drummer's kick and crash, then rest.
            assert onsets == [0.0] and bar[0][1].duration_beats <= 1.0, onsets
            assert any(abs(t) < 0.06 and e.kind == "kick" for t, e in drums)
        elif device == "drop":
            assert not bar and not held, onsets
        elif device == "push":
            # The band's anticipation on the last eighth, nothing after it.
            assert onsets and onsets[-1] == 3.5 and bar[-1][1].kind.startswith("push_hit")
            assert all(t + e.duration_beats <= 3.5 + 0.02 for t, e in bar[:-1])
        elif device == "fill":
            # The last beat belongs to the drum fill.
            assert all(t < 3.0 - 0.06 and t + e.duration_beats <= 3.0 + 0.02 for t, e in bar)
        elif device == "build":
            assert onsets == [k * 0.5 for k in range(8)]
            vels = [e.velocity for _, e in bar]
            assert vels[-1] > vels[0]
        if device in ("stop", "drop", "build"):
            assert all(t + e.duration_beats <= 0.02 for t, e in held), held


@pytest.mark.parametrize("ending", ["cold", "big", "ring"])
def test_bass_plays_the_song_ending_with_the_band(tmp_path, ending):
    for seed in (1, 2, 3):
        timelines, result = _device_song(tmp_path, "fill", seed, ending=ending)
        chorus = _occurrences(result)[-1]
        bar, _ = _last_bar(timelines, chorus)
        onsets = [round(t * 4) / 4 for t, _ in bar]
        if ending == "cold":
            assert onsets == [0.0] and bar[0][1].duration_beats <= 0.5
        elif ending == "big":
            assert onsets == [0.0, 3.5]
        else:
            assert onsets == [0.0] and bar[0][1].duration_beats >= 3.5


def test_drum_engine_songs_keep_the_bass_line_through_devices(tmp_path):
    # Drums the user wrote (a pattern) play through; so does the bass.
    for seed in (1, 2):
        sections = {"verse": _band("I IV V IV", 4), "chorus": _band("I V vi IV", 4, "chorus")}
        timelines, result = _render(tmp_path, seed=seed, sections=sections,
                                    arrangement=["verse", "chorus"],
                                    instruments={"drums": {"params": {"pattern": "rock_basic"}}},
                                    style={"into_chorus": "drop"}, name=f"eng{seed}.yaml")
        bar, _ = _last_bar(timelines, _occurrences(result)[0])
        assert bar


# ---------------------------------------------------------------------------
# #11 riff-alone intro
# ---------------------------------------------------------------------------

def _intro_song(tmp_path, seed, parts, drums=None):
    intro = {"type": "intro", "bars": 4, "harmony": {"progression": "i bVI bVII i"},
             "instruments": {"harmony": {}, **{p: {} for p in parts}}}
    sections = {"intro": intro, "verse": _band("i bVI bIII bVII", 4)}
    instruments = {"drums": drums} if drums else None
    return _render(tmp_path, genre="hard_rock", seed=seed, mode="minor", key="E",
                   sections=sections, arrangement=["intro", "verse"], instruments=instruments,
                   style={"intro": "riff_alone"},
                   name=f"intro{seed}{len(parts)}{bool(drums)}.yaml")


def _first_bar(timelines, meta, inst, skip=("fill",)):
    bars = [_bar_of(t, 4) for t, e in _local(timelines[inst].events, meta)
            if not str(e.kind).startswith(skip)]
    return min(bars) if bars else None


def test_riff_alone_intro_drums_and_bass_enter_together(tmp_path):
    for seed in range(1, 5):
        timelines, result = _intro_song(tmp_path, seed, ["drums", "bass", "rhythm_gtr", "lead_gtr"])
        intro = _occurrences(result)[0]
        assert _first_bar(timelines, intro, "drums") == 2
        assert _first_bar(timelines, intro, "bass") == 2
        assert _first_bar(timelines, intro, "rhythm_gtr", skip=()) == 0  # the riff, alone


def test_intro_without_a_riff_guitar_is_played_by_the_whole_band(tmp_path):
    for seed in range(1, 5):
        timelines, result = _intro_song(tmp_path, seed, ["drums", "bass", "lead_gtr"])
        intro = _occurrences(result)[0]
        assert _first_bar(timelines, intro, "drums") == 0
        assert _first_bar(timelines, intro, "bass") == 0


def test_riff_alone_intro_with_a_drum_engine_is_played_from_the_top(tmp_path):
    for seed in (1, 2):
        timelines, result = _intro_song(tmp_path, seed, ["drums", "bass", "rhythm_gtr"],
                                        drums={"params": {"pattern": "rock_basic"}})
        intro = _occurrences(result)[0]
        assert _first_bar(timelines, intro, "drums") == 0
        assert _first_bar(timelines, intro, "bass") == 0


# ---------------------------------------------------------------------------
# #19 register bounds
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("genre", ["latin", "pop_rock", "rock", "hard_rock", "funk", "country"])
def test_recipe_register_bounds_hold(tmp_path, genre):
    sections = {"verse": _band("I vi IV V", 8), "chorus": _band("IV V vi I", 8, "chorus")}
    for seed in range(1, 5):
        timelines, _ = _render(tmp_path, genre=genre, seed=seed, sections=sections,
                               arrangement=["verse", "chorus", "verse", "chorus"],
                               name=f"reg{genre}{seed}.yaml")
        pitches = [e.pitch for e in timelines["bass"].events]
        assert pitches and 28 <= min(pitches) and max(pitches) <= 52, (genre, seed, max(pitches))


def test_explicit_register_bounds_win_over_the_recipe(tmp_path):
    sections = {"verse": _band("I vi IV V", 8), "chorus": _band("IV V vi I", 8, "chorus")}
    for seed in range(1, 4):
        timelines, _ = _render(tmp_path, genre="latin", seed=seed, sections=sections,
                               bass={"params": {"register_low": 40, "register_high": 60}},
                               arrangement=["verse", "chorus"], name=f"regx{seed}.yaml")
        pitches = [e.pitch for e in timelines["bass"].events]
        assert pitches and 40 <= min(pitches) and max(pitches) <= 60


# ---------------------------------------------------------------------------
# #20 groove memory: root on one
# ---------------------------------------------------------------------------

def test_groove_memory_restates_the_root_on_one():
    from produzre.composer.groove_memory import apply_groove_memory

    slots = [SimpleNamespace(numeral=n, start_beat=4.0 * i, end_beat=4.0 * (i + 1))
             for i, n in enumerate(["I", "IV", "V", "I"] * 2)]
    roots = {"I": 36, "IV": 41, "V": 43}
    events = []
    for bar, slot in enumerate(slots):
        root = roots[slot.numeral]
        # Every bar the engine played: root on one, a fifth on three. One
        # bar (the typical onset pattern's first) had the fifth on one.
        one = (root + 7, "fifth") if bar == 1 else (root, "root")
        for t, (p, k) in ((0.0, one), (2.0, (root + 7, "fifth")), (3.0, (root, "root"))):
            events.append(NoteEvent(start_beat=bar * 4 + t, duration_beats=0.9, pitch=p,
                                    velocity=80, kind=k, channel=None))
    out, report = apply_groove_memory(events, instrument="bass", section_start=0.0,
                                      beats_per_bar=4, bars=8, chord_slots=slots, key="C",
                                      mode="major", genre="pop", bpm=120, memory=None,
                                      memory_key=None, seed=3, register=(28, 52))
    assert report["applied"]
    for bar, slot in enumerate(slots):
        if bar in (1, 3, 7):
            continue  # the engine's own bar (its fifth) or a phrase end
        one = [e for e in out if abs(e.start_beat - bar * 4) < 0.06]
        assert one and one[0].pitch % 12 == roots[slot.numeral] % 12, (bar, one[0].pitch)
    assert all(28 <= e.pitch <= 52 for e in out)


def test_pop_verse_downbeats_are_mostly_roots(tmp_path):
    sections = {"verse": _band("I V vi IV", 8), "chorus": _band("IV V vi I", 8, "chorus")}
    total = rooted = 0
    for seed in range(1, 7):
        timelines, result = _render(tmp_path, genre="pop", seed=seed, sections=sections,
                                    bass={"params": {"rhythm_pattern": "push"}},
                                    arrangement=["verse", "chorus"], name=f"pop{seed}.yaml")
        verse = _occurrences(result)[0]
        prog = ["I", "V", "vi", "IV"]
        ones = [(bar, e) for t, e in _local(timelines["bass"].events, verse)
                for bar in [_bar_of(t, 4)] if abs(t - bar * 4) < 0.06]
        roots = sum(1 for bar, e in ones
                    if e.pitch % 12 == chord_pitch_classes(prog[bar % 4], "C", "major")[0])
        # Never a fifth on every downbeat (the engine's fifth drops and its
        # phrase-end bars keep some variation).
        assert ones and roots >= 0.5 * len(ones), (seed, roots, len(ones))
        total, rooted = total + len(ones), rooted + roots
    assert rooted >= 0.65 * total, (rooted, total)


# ---------------------------------------------------------------------------
# #21 authored bass motif
# ---------------------------------------------------------------------------

_MOTIF = {"bass_line": {"role": "bass_motif", "register": [36, 60],
                        "events": "1:.5 3:.5 4:1 5:1 1:1"}}


def _match(beats, local_events, tol=0.2):
    """Map each wanted beat to the note played there, allowing the groove
    clock's swing, push or pull (a swung eighth sounds up to ~0.2 late)."""
    got = {}
    for t, e in local_events:
        near = min(beats, key=lambda b: abs(b - t))
        if abs(near - t) < tol and near not in got:
            got[near] = e
    return got


def _motif_song(tmp_path, seed, bass=None, genre="rock"):
    sections = {"verse": _band("i iv v i", 8), "chorus": _band("i bVI bIII bVII", 8, "chorus")}
    return _render(tmp_path, genre=genre, seed=seed, key="E", mode="minor", bass=bass,
                   sections=sections, themes=_MOTIF, arrangement=["verse", "chorus"],
                   style={"into_chorus": "fill"},
                   name=f"motif{seed}{genre}{bool(bass)}.yaml")


@pytest.mark.parametrize("genre", ["rock", "hard_rock", "funk"])
def test_authored_bass_motif_owns_the_bass(tmp_path, genre):
    for seed in range(1, 5):
        timelines, result = _motif_song(tmp_path, seed, genre=genre)
        for meta in _occurrences(result):
            realized = result.performance_plan.get(f"themes.realized.{meta.id}")["bass_motif"]
            want = {round(float(n["beat"]), 3): n for n in realized}
            local = _local(timelines["bass"].events, meta)
            got = _match(list(want), local)
            # The last beat before the chorus is the drum fill's (into_chorus:
            # fill), and the song's last bar is the band's ending.
            cut = meta.length_beats - 1.0 if meta.type == "verse" else meta.length_beats - 4.0
            for beat, n in want.items():
                if beat >= cut - 0.02:
                    continue
                assert beat in got, f"{genre} seed {seed} {meta.id}: motif onset {beat} missing"
                e = got[beat]
                assert e.kind == "motif" and e.pitch == int(n["pitch"])
                # Written lengths (swing shortens a late eighth by its delay).
                assert 0.8 * float(n["duration_beats"]) - 0.2 <= e.duration_beats \
                    <= float(n["duration_beats"]) + 1e-6
            assert all(e.kind == "motif" or e.kind.startswith(("ending_hit", "root_cadence"))
                       for _, e in local), Counter(e.kind for _, e in local)


def test_motif_rhythm_is_kept_on_the_kick_locked_path_with_written_lengths(tmp_path):
    for seed in (1, 2, 3):
        timelines, result = _motif_song(tmp_path, seed, bass={"params": {"lock_to_kicks": True}})
        meta = _occurrences(result)[1]  # the chorus; its last bar is the song's ending
        realized = [n for n in result.performance_plan.get(f"themes.realized.{meta.id}")["bass_motif"]
                    if float(n["beat"]) < meta.length_beats - 4.0]
        got = _match([float(n["beat"]) for n in realized], _local(timelines["bass"].events, meta))
        for n in realized:
            e = got.get(float(n["beat"]))
            assert e is not None and e.kind == "motif"
            assert float(n["duration_beats"]) - 0.2 <= e.duration_beats \
                <= float(n["duration_beats"]) + 1e-6


def test_motif_quote_rate_varies_pitches_but_keeps_the_rhythm(tmp_path):
    kinds = Counter()
    for seed in (1, 2, 3):
        timelines, result = _motif_song(tmp_path, seed, bass={"params": {"motif_quote_rate": 0.5}})
        meta = _occurrences(result)[1]
        realized = result.performance_plan.get(f"themes.realized.{meta.id}")["bass_motif"]
        wanted = [float(n["beat"]) for n in realized if float(n["beat"]) < meta.length_beats - 4.0]
        assert set(_match(wanted, _local(timelines["bass"].events, meta))) == set(wanted)
        kinds.update(e.kind for _, e in _local(timelines["bass"].events, meta))
    assert kinds["motif"] and kinds["motif_root"]


# ---------------------------------------------------------------------------
# #22 articulation on composed roles
# ---------------------------------------------------------------------------

def test_slap_and_mute_reach_the_composed_bass_roles(tmp_path):
    sections = {"verse": _band("i iv v i", 8), "chorus": _band("i bVI bIII bVII", 8, "chorus")}
    slapped, muted = Counter(), []
    for seed in range(1, 9):
        for style in ("slap", "mute"):
            timelines, _ = _render(tmp_path, seed=seed, mode="minor", key="E", sections=sections,
                                   bass={"params": {"articulation_style": style}},
                                   arrangement=["verse", "chorus"],
                                   name=f"art{style}{seed}.yaml")
            roles = [e for e in timelines["bass"].events
                     if str(e.kind).startswith(("bass_", "riff_double"))]
            if style == "slap":
                slapped.update("thumb" if "_slap_thumb" in e.kind else
                               "pop" if "_slap_pop" in e.kind else "plain" for e in roles)
            else:
                muted += roles
    assert slapped["thumb"] and slapped["pop"], slapped
    assert muted and all(e.duration_beats <= 0.45 + 1e-6 and e.kind.endswith("_mute")
                         for e in muted)


def test_articulate_written_note_styles():
    from produzre.engine.bass.articulation import articulate_written_note

    rng = random.Random(1)
    assert articulate_written_note("finger", duration=2.0, velocity=80, strong=True,
                                   offbeat=False, octave_up=False, rng=rng) == (2.0, 80, "")
    d, v, k = articulate_written_note("slap", duration=0.45, velocity=80, strong=False,
                                      offbeat=True, octave_up=True, rng=rng)
    assert k == "_slap_pop" and v >= 80
    d, v, k = articulate_written_note("mute", duration=2.0, velocity=80, strong=True,
                                      offbeat=False, octave_up=False, rng=rng)
    assert d <= 0.45 and v < 80 and k == "_mute"
