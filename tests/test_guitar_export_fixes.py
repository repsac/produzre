"""Guitar, export and groove-memory fixes found after the 2026-09-26 examples
round: body taps and chromatic approaches through groove memory, the
rhythm guitar's section-start voicing and dynamics, and capoed tabs.
Property tests over many seeds, keys and progressions, not MIDI pins."""
from __future__ import annotations

import random
import statistics
from types import SimpleNamespace as NS

import pytest
import yaml

from produzre.analysis.tab_format import tab_text_from_rows
from produzre.composer.groove_memory import GrooveMemory, apply_groove_memory
from produzre.composer.theory import ChordMap, scale_pcs
from produzre.instruments.profile import GUITAR_STANDARD
from produzre.orchestrate.transitions import compute_energy_profile
from produzre.timeline import InstrumentTimeline, NoteEvent
from tests.test_groove_clock import _load_cfg, _render_timelines

MINOR_NUMERALS = ["i", "iv", "v", "bVI", "bVII", "bIII", "iv", "i"]
MAJOR_NUMERALS = ["I", "IV", "V", "vi", "ii", "iii", "IV", "V"]
KEYS = ["C", "D", "E", "F", "G", "A", "Bb", "Eb"]


def _slots(prog, bpb=4.0):
    return [NS(numeral=n, start_beat=i * bpb, end_beat=(i + 1) * bpb, index=i)
            for i, n in enumerate(prog)]


def _progression(rng, mode, bars=8):
    pool = MINOR_NUMERALS if mode == "minor" else MAJOR_NUMERALS
    prog = [rng.choice(pool) for _ in range(bars)]
    for i in range(1, bars):  # a chord change at every bar line
        while prog[i] == prog[i - 1]:
            prog[i] = rng.choice(pool)
    return prog


# --- groove memory: unpitched body taps -----------------------------------------

@pytest.mark.parametrize("mode", ["major", "minor"])
def test_groove_memory_keeps_body_taps_at_their_fixed_pitch(mode):
    for seed in range(12):
        rng = random.Random(seed)
        key = rng.choice(KEYS)
        prog = _progression(rng, mode)
        cm = ChordMap(_slots(prog), key, mode)
        events = []
        for b in range(8):
            root = 48 + (cm.at(b * 4.0).root_pc - 48) % 12
            for off in (0.0, 1.0, 2.0, 3.0):
                events.append(NoteEvent(b * 4.0 + off, 0.5, root + (7 if off % 2 else 0), 70, 0,
                                        "acoustic_strum"))
            events.append(NoteEvent(b * 4.0 + 2.5, 0.08, 40, 40, 0, "body_tap"))
        memory = GrooveMemory()
        for occurrence_key in (key, rng.choice(KEYS)):  # recall, possibly in a new key
            out, report = apply_groove_memory(
                list(events), instrument="acoustic_gtr", section_start=0.0, beats_per_bar=4.0,
                bars=8, chord_slots=_slots(prog), key=occurrence_key, mode=mode, genre="folk",
                bpm=100, memory=memory, memory_key=("acoustic_gtr", "verse"), seed=seed)
            assert report["applied"] and report["restated"] > 0
            taps = [e for e in out if e.kind == "body_tap"]
            assert len(taps) == 8
            assert {e.pitch for e in taps} == {40}


# --- groove memory: chromatic approach notes ------------------------------------

def _bass_line(prog, key, mode, approach_kind, rng):
    """Root on one, a chord tone, and an approach into the next bar's root."""
    cm = ChordMap(_slots(prog), key, mode)
    scale = scale_pcs(key, mode)
    events = []
    for b in range(len(prog)):
        root = 33 + (cm.at(b * 4.0).root_pc - 33) % 12
        events.append(NoteEvent(b * 4.0, 0.9, root, 90, 1, "root"))
        events.append(NoteEvent(b * 4.0 + 1.0, 0.9, root + 7, 80, 1, "fifth"))
        events.append(NoteEvent(b * 4.0 + 2.0, 0.9, root, 80, 1, "root"))
        if b + 1 < len(prog):
            nxt = 33 + (cm.at((b + 1) * 4.0).root_pc - 33) % 12
            if approach_kind == "approach_chromatic":
                pitch = nxt - 1 if rng.random() < 0.7 else nxt + 1
            else:
                pitch = nxt - 1
                while pitch % 12 not in scale:
                    pitch -= 1
            events.append(NoteEvent(b * 4.0 + 3.5, 0.45, pitch, 70, 1, approach_kind))
    return events


@pytest.mark.parametrize("mode", ["major", "minor"])
def test_restated_chromatic_approaches_stay_a_half_step_from_the_next_chord(mode):
    checked = 0
    for seed in range(20):
        rng = random.Random(100 + seed)
        key = rng.choice(KEYS)
        prog = _progression(rng, mode)
        events = _bass_line(prog, key, mode, "approach_chromatic", rng)
        out, report = apply_groove_memory(
            events, instrument="bass", section_start=0.0, beats_per_bar=4.0, bars=8,
            chord_slots=_slots(prog), key=key, mode=mode, genre="rock", bpm=110,
            memory=None, memory_key=None, seed=seed)
        assert report["applied"]
        cm = ChordMap(_slots(prog), key, mode)
        for e in out:
            if e.kind != "approach_chromatic":
                continue
            res = (int(e.start_beat // 4) + 1) * 4.0
            nxt = [n for n in out if abs(n.start_beat - res) < 0.08 and n.kind != e.kind]
            if not nxt or res >= 32.0:
                continue
            checked += 1
            # A half step from the chord it resolves into, and from the note
            # actually played there.
            assert (cm.at(res).root_pc - e.pitch) % 12 in (1, 11)
            assert min(abs(n.pitch - e.pitch) for n in nxt) == 1
    assert checked > 60


def test_restated_diatonic_approaches_stay_in_the_key():
    for seed in range(20):
        rng = random.Random(300 + seed)
        mode = rng.choice(["major", "minor"])
        key = rng.choice(KEYS)
        prog = _progression(rng, mode)
        events = _bass_line(prog, key, mode, "approach_diatonic", rng)
        out, _ = apply_groove_memory(
            events, instrument="bass", section_start=0.0, beats_per_bar=4.0, bars=8,
            chord_slots=_slots(prog), key=key, mode=mode, genre="rock", bpm=110,
            memory=None, memory_key=None, seed=seed)
        scale = set(scale_pcs(key, mode))
        assert all(e.pitch % 12 in scale for e in out if e.kind == "approach_diatonic")


# --- rhythm guitar: section starts ----------------------------------------------

def _reggae_song(tmp_path, name, *, key, seed, chorus):
    inst = {"harmony": {}, "drums": {}, "bass": {}, "rhythm_gtr": {}}
    data = {"song": {"title": name, "project": "produzre-examples", "seed": seed,
                     "genre": "reggae", "key": key, "mode": "minor", "bpm": 74,
                     "exports_root": str(tmp_path / "exports")},
            "sections": {"verse": {"type": "verse", "bars": 8, "instruments": dict(inst),
                                   "harmony": {"progression": "i iv i v"}},
                         "chorus": {"type": "chorus", "bars": 8, "instruments": dict(inst),
                                    "harmony": {"progression": chorus}}},
            "arrangement": ["verse", "chorus", "verse", "chorus"]}
    return _load_cfg(tmp_path, yaml.safe_dump(data, sort_keys=False), name=f"{name}.yaml")


@pytest.mark.parametrize("key", ["A", "E", "C", "G"])
def test_a_sections_first_chord_sits_with_the_rest_and_is_not_softened(tmp_path, key):
    """The first chord of a section (no previous chord to lead from) is
    voiced in the section's register and keeps the section's dynamics."""
    for seed, chorus in ((5702, "bVI bVII i i bVI bVII v v"), (11, "bVI bVII i i"),
                         (12, "iv v bVI bVII"), (13, "bIII bVII i v")):
        tl, result = _render_timelines(_reggae_song(tmp_path, f"rs{key}{seed}", key=key,
                                                    seed=seed, chorus=chorus))
        for meta in result.performance_plan.sections:
            bpb = meta.beats_per_bar
            notes = [e for e in tl["rhythm_gtr"].events
                     if meta.start_beat - 0.1 <= e.start_beat < meta.end_beat - bpb - 0.1]
            first = [e for e in notes if e.start_beat < meta.start_beat + bpb - 0.1]
            rest = [e for e in notes if e.start_beat >= meta.start_beat + bpb - 0.1]
            assert first and rest
            assert max(e.pitch for e in first) <= max(e.pitch for e in rest) + 2, (key, seed)
            played = lambda es: [e.velocity for e in es if "chuck" not in str(e.kind)]
            if played(first) and played(rest):
                assert statistics.mean(played(first)) >= 0.85 * statistics.mean(played(rest)), \
                    (key, seed)


def test_energy_profile_counts_chord_gestures_and_ignores_chucks():
    rng = random.Random(4)
    for _ in range(30):
        n = rng.randint(2, 8)
        onsets = sorted(rng.sample([i * 0.25 for i in range(16)], n))
        single = [NoteEvent(t, 0.2, 60, 80, 0, "comp_stab") for t in onsets]
        chords = [NoteEvent(t + k * 0.007, 0.2, 60 + 4 * k, 80, 0, "comp_stab")
                  for t in onsets for k in range(rng.randint(3, 6))]
        a = compute_energy_profile(single, 4.0, "4/4", chordal=True)
        b = compute_energy_profile(chords, 4.0, "4/4", chordal=True)
        assert a.density == pytest.approx(b.density) == pytest.approx(n / 4.0)
        chucks = [NoteEvent(t + 0.125, 0.06, 64, 36, 0, "comp_chuck") for t in onsets]
        c = compute_energy_profile(chords + chucks, 4.0, "4/4", chordal=True)
        assert c.avg_velocity == pytest.approx(80.0)
    # Drums keep counting every hit.
    kit = [NoteEvent(0.0, 0.1, 36, 100, 9, "kick"), NoteEvent(0.0, 0.1, 42, 70, 9, "hat")]
    assert compute_energy_profile(kit, 1.0, "4/4").density == 2.0


# --- tab export with a capo -----------------------------------------------------

def _rows(events):
    return [NS(start_beat_abs=e.start_beat, duration_beats=e.duration_beats, pitch=e.pitch,
               velocity=e.velocity) for e in events]


def _tab_cells(text):
    """{(bar, step): {string_index: fret}} parsed from tab text (6 strings).

    A string line is its cells joined by "-", where an empty cell is "-".
    """
    cells, bar, string = {}, 0, 0
    for line in text.splitlines():
        if line.startswith("Bar "):
            bar, string = int(line.split()[1]), 5
            continue
        if bar and "|" in line:
            body, p, step = line.split("|")[1], 0, 0
            while p < len(body):
                q = p
                while q < len(body) and body[q].isdigit():
                    q += 1
                if q > p:
                    cells.setdefault((bar, step), {})[string] = int(body[p:q])
                    p = q
                else:
                    p += 1
                step += 1
                p += 1  # the separator
            string -= 1
    return cells


@pytest.mark.parametrize("capo", [1, 2, 3, 5, 7])
def test_tab_frets_are_relative_to_the_capo(capo):
    rng = random.Random(capo)
    opens = GUITAR_STANDARD.open_tuning
    events = []
    for bar in range(4):
        for step in range(0, 16, 2):
            s = rng.randrange(6)
            fret = rng.randint(0, 5)
            events.append(NoteEvent(bar * 4.0 + step * 0.25, 0.2, opens[s] + capo + fret, 70, 0))
    text = tab_text_from_rows(_rows(events), beats_per_bar=4.0, subdiv=16,
                              instrument="acoustic_gtr", bars_total=4,
                              capo_by_bar={b: capo for b in range(1, 5)})
    assert f"CAPO: fret {capo}" in text
    cells = _tab_cells(text)
    for e in events:
        bar, step = int(e.start_beat // 4) + 1, int(round((e.start_beat % 4) / 0.25))
        placed = cells[(bar, step)]
        assert any(opens[s] + capo + f == e.pitch for s, f in placed.items())
        assert all(0 <= f <= 5 for f in placed.values())  # fingered near the capo


def test_capoed_acoustic_song_tab_names_the_capo_and_fingers_the_shapes(tmp_path):
    from produzre.export.textdump import write_tabs
    import logging

    for seed, capo in ((8101, 2), (3, 4), (4, 1)):
        data = {"song": {"title": f"capo{seed}", "project": "produzre-examples", "seed": seed,
                         "genre": "folk", "key": "A", "mode": "major", "bpm": 100,
                         "exports_root": str(tmp_path / "exports")},
                "instruments": {"acoustic_gtr": {"params": {"technique": "fingerpicking",
                                                            "capo": capo}}},
                "sections": {"verse": {"type": "verse", "bars": 4,
                                       "harmony": {"progression": "I IV V I"},
                                       "instruments": {"harmony": {}, "acoustic_gtr": {}}}},
                "arrangement": ["verse"]}
        cfg = _load_cfg(tmp_path, yaml.safe_dump(data, sort_keys=False), name=f"c{seed}.yaml")
        tl, _ = _render_timelines(cfg)
        paths = write_tabs(cfg=cfg, song_name=f"capo{seed}", analysis_dir=tmp_path / f"a{seed}",
                           instruments_used=["acoustic_gtr"], timelines=tl,
                           section_timings=None, subdiv=16, logger=logging.getLogger("t"))
        text = paths["acoustic_gtr"].read_text()
        assert f"CAPO: fret {capo}" in text
        opens = GUITAR_STANDARD.open_tuning
        cells = _tab_cells(text)
        by_step = {}
        for e in tl["acoustic_gtr"].events:
            key_ = (int(e.start_beat // 4) + 1, int((e.start_beat % 4) / 0.25 + 1e-9))
            by_step.setdefault(key_, set()).add(e.pitch)
        for pos, placed in cells.items():
            for s, f in placed.items():
                assert opens[s] + capo + f in by_step[pos]


def test_timeline_without_capo_tabs_as_before():
    tl = InstrumentTimeline(instrument="acoustic_gtr")
    assert tl.capo_windows == []
    text = tab_text_from_rows(_rows([NoteEvent(0.0, 0.5, 45, 70, 0)]), instrument="acoustic_gtr",
                              bars_total=1)
    assert "CAPO" not in text and "A|0-" in text


def test_a_unison_struck_twice_in_one_step_is_one_fretted_note():
    rng = random.Random(9)
    for _ in range(40):
        pitch = rng.randint(45, 76)
        events = [NoteEvent(0.0, 0.8, pitch, 70, 0), NoteEvent(0.2, 0.3, pitch, 60, 0)]
        cells = _tab_cells(tab_text_from_rows(_rows(events), instrument="acoustic_gtr",
                                              bars_total=1))
        assert len(cells[(1, 0)]) == 1


# --- bass: chromatic approaches sound chromatic -----------------------------------

def _chromatic_misses(events, skip=("fill",)):
    """Chromatic approaches whose next note is not a half step away."""
    evs = sorted(events, key=lambda e: e.start_beat)
    total, misses = 0, []
    for i, e in enumerate(evs):
        k = str(e.kind or "")
        if "approach_chromatic" not in k or any(t in k for t in skip):
            continue
        nxt = [n for n in evs[i + 1:] if n.start_beat > e.start_beat + 0.05]
        if not nxt:
            continue
        total += 1
        if abs(nxt[0].pitch - e.pitch) != 1:
            misses.append((e.start_beat, e.pitch, nxt[0].pitch, nxt[0].kind))
    return total, misses


def _bass_song(tmp_path, name, *, key, mode, seed, sections, arrangement, bass):
    data = {"song": {"title": name, "project": "produzre-examples", "seed": seed, "genre": "rock",
                     "key": key, "mode": mode, "bpm": 110,
                     "exports_root": str(tmp_path / "exports")},
            "instruments": {"bass": {"params": bass}},
            "sections": sections, "arrangement": arrangement}
    return _load_cfg(tmp_path, yaml.safe_dump(data, sort_keys=False), name=f"{name}.yaml")


@pytest.mark.parametrize("mode", ["major", "minor"])
def test_a_chromatic_approach_resolves_even_when_a_fifth_drop_is_drawn(tmp_path, mode):
    prog = "I vi ii V I vi ii V" if mode == "major" else "i bVI iv v i bVII bVI v"
    total = 0
    for seed in range(6):
        key = KEYS[seed % len(KEYS)]
        secs = {"verse": {"type": "verse", "bars": 8, "harmony": {"progression": prog},
                          "instruments": {"harmony": {}, "bass": {}}}}
        cfg = _bass_song(tmp_path, f"ap{mode}{seed}", key=key, mode=mode, seed=seed,
                         sections=secs, arrangement=["verse", "verse"],
                         bass={"rhythm_pattern": "drive", "density": 0.8, "rest_rate": 0.05,
                               "approach_rate": 0.9, "chromatic_rate": 0.9,
                               "fifth_jump_rate": 0.8, "octave_jump_rate": 0.4,
                               "max_passing_per_bar": 3})
        tl, _ = _render_timelines(cfg)
        n, misses = _chromatic_misses(tl["bass"].events)
        total += n
        assert not misses, (key, seed, misses)
    assert total > 20


@pytest.mark.parametrize("key", ["Bb", "E", "G", "D"])
def test_a_walking_line_steps_chromatically_into_the_next_section(tmp_path, key):
    total = 0
    for seed in range(5):
        secs = {"head": {"type": "verse", "bars": 4, "harmony": {"progression": "ii7 V7 Imaj7 vi7"},
                         "instruments": {"harmony": {}, "bass": {}}},
                "bridge": {"type": "bridge", "bars": 4,
                           "harmony": {"progression": "iii7 VI7 ii7 V7"},
                           "instruments": {"harmony": {}, "bass": {}}}}
        cfg = _bass_song(tmp_path, f"wk{key}{seed}", key=key, mode="major", seed=seed,
                         sections=secs, arrangement=["head", "bridge", "head"],
                         bass={"rhythm_pattern": "walking", "chromatic_rate": 1.0,
                               "register_low": 28, "register_high": 55})
        tl, _ = _render_timelines(cfg)
        n, misses = _chromatic_misses(tl["bass"].events)
        total += n
        assert not misses, (seed, misses)
    assert total > 10
