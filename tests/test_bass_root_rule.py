"""Bass fixes found after the examples review (second round).

Property tests over many seeds and settings, never a single pinned take:

- the beat-1 root rule: every bar's downbeat sounds, and a new chord starts
  on its root, in engine lines, composed roles, restated groove bars,
  answers and modulated sections; a pedal holds only the key's tonic;
- composed bass notes follow the section's dynamics like the drummer;
- an explicit ``rhythm_pattern`` wins over the walking heuristic and the
  articulation's pattern bias;
- compound meters (6/8) put the bass on the dotted-quarter pulse grid;
- a transition pickup replaces the bass notes it lands on;
- the song's last bass note is a real note, and the slap floor holds;
- ``lock_to_riff`` next to a ``bass_motif`` is reported, and the ``[BASS]``
  log shows the section's own mode.
"""
from __future__ import annotations

import logging
import pathlib
import random
from collections import Counter
from types import SimpleNamespace

import pytest
import yaml

from produzre.composer.theory import ChordMap, tonic_pc
from produzre.timeline import NoteEvent
from tests.test_bass_band_fixes import _band, _local, _occurrences
from tests.test_groove_clock import _load_cfg, _render_timelines

def _render(tmp_path, *, genre="rock", meter="4/4", seed=1, key="C", mode="major", bass=None,
            sections=None, arrangement=None, style=None, themes=None, instruments=None,
            name="song.yaml", song_extra=None):
    song = {"title": "BassRoot", "seed": seed, "genre": genre, "meter": meter, "key": key,
            "mode": mode, "bpm": 120, **(song_extra or {})}
    if style:
        song["arrangement_style"] = style
    data = {"song": song, "instruments": {"bass": bass or {}, **(instruments or {})},
            "sections": sections, "arrangement": arrangement or list(sections)}
    if themes:
        data["themes"] = themes
    pathlib.Path(tmp_path).mkdir(parents=True, exist_ok=True)
    cfg = _load_cfg(tmp_path, yaml.safe_dump(data, sort_keys=False), name=name)
    return _render_timelines(cfg)


# Kinds that are the band's transition material, not the bass line itself.
_TRANSITION = ("pickup", "turnaround", "transition")


def _sections_with_plans(result, cfg_key="C", cfg_mode="major"):
    """(start, bpb, total, chord map, key) for each rendered occurrence."""
    out = []
    for ps in result.plan.planned_sections:
        hp = ps.harmony_plan
        if hp is None or not hp.chord_slots:
            continue
        key = ps.sec.key or cfg_key
        mode = getattr(ps.sec, "mode", None) or cfg_mode
        out.append((float(ps.timing.start_beat), float(hp.meter.beats_per_bar),
                    float(hp.chord_slots[-1].end_beat), ChordMap(hp.chord_slots, key, mode), key,
                    ps))
    return out


def _downbeat_violations(timelines, result, key="C", mode="major", skip_last_bar=False):
    """Bars without a downbeat note, and new chords whose downbeat is not
    the root (a held tonic pedal excepted)."""
    missing, wrong, total = [], [], 0
    events = [e for e in timelines["bass"].events if not str(e.kind).startswith(_TRANSITION)]
    for start, bpb, length, chords, sec_key, ps in _sections_with_plans(result, key, mode):
        bars = int(round(length / bpb))
        for b in range(bars):
            if skip_last_bar and b == bars - 1:
                continue
            total += 1
            t = start + b * bpb
            near = [e for e in events if abs(e.start_beat - t) < 0.07]
            if not near:
                missing.append((ps.sec_id, b))
                continue
            note = min(near, key=lambda e: abs(e.start_beat - t))
            span = chords.at(b * bpb)
            prev = chords.at(b * bpb - 1e-3) if b else None
            new_chord = prev is None or prev.root_pc != span.root_pc
            tonic = tonic_pc(sec_key)
            if new_chord and note.pitch % 12 != span.root_pc and not (
                    note.pitch % 12 == tonic and tonic in span.pcs):
                wrong.append((ps.sec_id, b, note.kind, note.pitch % 12, span.root_pc))
    return missing, wrong, total


# ---------------------------------------------------------------------------
# The beat-1 root rule
# ---------------------------------------------------------------------------

_ROOT_SONGS = {
    # A riff-driven rock song whose bass keeps its own picked line under the
    # riff (examples/genres/rock/rock.yaml): the drive pattern's density
    # draws used to drop every downbeat.
    "rock_pick": dict(genre="rock", key="A", mode="mixolydian",
                      bass={"params": {"articulation_style": "pick"}},
                      style={"riff_driven": True, "bass_doubles": False, "into_chorus": "fill",
                             "intro": "full"},
                      prog=("I bVII IV I", "IV V I I")),
    # The dub persona: sparse anchor with heavy pedal tones.
    "reggae_dub": dict(genre="reggae", key="G", mode="major", bass={"persona": "dub"},
                       style={"into_chorus": "fill", "intro": "full"},
                       prog=("I IV", "IV V I vi")),
    "pop_push": dict(genre="pop", key="C", mode="major",
                     bass={"params": {"rhythm_pattern": "push"}},
                     style={"into_chorus": "fill", "intro": "full"},
                     prog=("I V vi IV", "IV V vi I")),
    "funk_slap": dict(genre="funk", key="E", mode="dorian", bass={"persona": "funk"},
                      style={"into_chorus": "fill", "intro": "full"},
                      prog=("i7 IV7", "bIII7 IV7 i7 i7")),
}


@pytest.mark.parametrize("song", sorted(_ROOT_SONGS))
def test_every_bar_sounds_its_downbeat_and_new_chords_start_on_the_root(tmp_path, song):
    spec = _ROOT_SONGS[song]
    verse, chorus = spec["prog"]
    sections = {"verse": _band(verse, 8), "chorus": _band(chorus, 8, "chorus")}
    missing_all, wrong_all, total_all = [], [], 0
    for seed in range(1, 5):
        timelines, result = _render(tmp_path, genre=spec["genre"], seed=seed, key=spec["key"],
                                    mode=spec["mode"], bass=spec["bass"], sections=sections,
                                    arrangement=["verse", "chorus", "verse", "chorus"],
                                    style=spec["style"], name=f"root{song}{seed}.yaml")
        missing, wrong, total = _downbeat_violations(timelines, result, spec["key"], spec["mode"])
        missing_all += [(seed,) + m for m in missing]
        wrong_all += [(seed,) + w for w in wrong]
        total_all += total
    assert not missing_all, missing_all
    assert not wrong_all, wrong_all
    assert total_all >= 4 * 32


def test_a_pedal_never_carries_another_root_into_the_next_chord(tmp_path):
    # The dub persona holds pedal tones (pedal_rate 0.4): only the key's
    # tonic may be held under a chord that contains it.
    sections = {"verse": _band("I IV I V", 8), "chorus": _band("IV V I vi", 8, "chorus")}
    pedals = 0
    for seed in range(1, 7):
        timelines, result = _render(tmp_path, genre="reggae", seed=seed, key="G",
                                    bass={"persona": "dub"}, sections=sections,
                                    arrangement=["verse", "chorus"],
                                    style={"into_chorus": "fill"}, name=f"pedal{seed}.yaml")
        for start, bpb, length, chords, key, ps in _sections_with_plans(result, "G"):
            for t, e in [(e.start_beat - start, e) for e in timelines["bass"].events
                         if start <= e.start_beat < start + length - 0.06]:
                if not str(e.kind).startswith("pedal"):
                    continue
                pedals += 1
                span = chords.at(max(0.0, t) + 0.07)
                assert e.pitch % 12 in span.pcs, (seed, ps.sec_id, t, e.pitch)
                assert e.pitch % 12 in (span.root_pc, tonic_pc(key)), (seed, ps.sec_id, t, e.pitch)
    assert pedals  # the persona's pedal tones still play


def test_the_modulated_final_chorus_keeps_roots_on_one(tmp_path):
    # iron-horse-road.yaml: a hard rock song whose final chorus steps up a
    # whole tone; its downbeats played the old fifth drops.
    sections = {"verse": _band("i i bVII bVI", 8),
                "chorus": _band("bVI bVII i i bVI bVII V V", 8, "chorus")}
    for seed in range(1, 6):
        data_style = {"into_chorus": "fill", "intro": "full"}
        timelines, result = _render(tmp_path, genre="hard_rock", seed=seed, key="A", mode="minor",
                                    bass={"params": {"articulation_style": "pick"}},
                                    sections=sections, style=data_style,
                                    arrangement=["verse", "chorus", "verse", "chorus", "chorus"],
                                    name=f"mod{seed}.yaml", song_extra={"final_chorus": "modulate"})
        keys = {ps.sec.key for ps in result.plan.planned_sections}
        assert "B" in keys, keys
        missing, wrong, _ = _downbeat_violations(timelines, result, "A", "minor")
        assert not missing and not wrong, (seed, missing, wrong)


def test_recipe_fifth_drops_leave_new_chords_on_the_root_and_explicit_ones_play(tmp_path):
    sections = {"verse": _band("I IV V I", 4)}
    solo = {"verse": {"type": "verse", "bars": 4, "harmony": {"progression": "I IV V I"},
                      "instruments": {"harmony": {}, "bass": {}}}}
    drops = 0
    for seed in range(1, 7):
        # A fifth_jump_rate you set drops the fifth on chord changes.
        timelines, _ = _render(tmp_path, seed=seed, sections=solo,
                               bass={"params": {"fifth_jump_rate": 0.9, "density": 0.9}},
                               name=f"fx{seed}.yaml")
        drops += sum(1 for e in timelines["bass"].events if str(e.kind).startswith("fifth_drop"))
        # The metal persona's rate (not yours) only varies held chords.
        timelines, result = _render(tmp_path, seed=seed, sections=sections, genre="metal",
                                    bass={"persona": "metal"}, style={"intro": "full"},
                                    name=f"fp{seed}.yaml")
        missing, wrong, _ = _downbeat_violations(timelines, result)
        assert not missing and not wrong, (seed, missing, wrong)
    assert drops >= 3


def test_groove_memory_restates_a_root_on_one_even_when_the_source_bar_starts_late():
    from produzre.composer.groove_memory import apply_groove_memory

    slots = [SimpleNamespace(numeral=n, start_beat=4.0 * i, end_beat=4.0 * (i + 1))
             for i, n in enumerate(["I", "IV", "V", "I"] * 2)]
    roots = {"I": 36, "IV": 41, "V": 43}
    for seed in range(8):
        rng = random.Random(seed)
        late = rng.choice([0.5, 1.0, 1.5, 2.5])
        events = []
        for bar, slot in enumerate(slots):
            root = roots[slot.numeral]
            # The engine's typical bar starts after the downbeat.
            for t, p, k in ((late, root + 7, "fifth"), (3.0, root, "root")):
                events.append(NoteEvent(start_beat=bar * 4 + t, duration_beats=0.9, pitch=p,
                                        velocity=80, kind=k, channel=None))
        out, report = apply_groove_memory(events, instrument="bass", section_start=0.0,
                                          beats_per_bar=4, bars=8, chord_slots=slots, key="C",
                                          mode="major", genre="rock", bpm=120, memory=None,
                                          memory_key=None, seed=seed, register=(28, 52))
        assert report["applied"]
        for bar, slot in enumerate(slots):
            if bar in (3, 7):
                continue  # phrase ends keep the engine's own bar
            one = [e for e in out if abs(e.start_beat - bar * 4) < 0.06]
            assert one and one[0].pitch % 12 == roots[slot.numeral] % 12, (seed, bar, late)
            assert one[0].start_beat + one[0].duration_beats <= bar * 4 + late + 1e-6


def test_restated_bass_notes_never_ring_into_the_next_chord():
    from produzre.composer.groove_memory import apply_groove_memory

    # Source bars hold one chord; the restated bars change chord at beat 3.
    numerals = ["I", "I", "IV", "V"]
    slots = []
    for bar in range(8):
        if bar in (1, 5):
            slots += [SimpleNamespace(numeral="IV", start_beat=bar * 4.0, end_beat=bar * 4.0 + 2),
                      SimpleNamespace(numeral="V", start_beat=bar * 4.0 + 2, end_beat=bar * 4.0 + 4)]
        else:
            slots.append(SimpleNamespace(numeral=numerals[bar % 4], start_beat=bar * 4.0,
                                         end_beat=bar * 4.0 + 4))
    events = [NoteEvent(start_beat=bar * 4.0, duration_beats=3.8, pitch=36, velocity=80,
                        kind="root", channel=None) for bar in range(8)]
    out, report = apply_groove_memory(events, instrument="bass", section_start=0.0,
                                      beats_per_bar=4, bars=8, chord_slots=slots, key="C",
                                      mode="major", genre="rock", bpm=120, memory=None,
                                      memory_key=None, seed=1, register=(28, 52))
    assert report["applied"]
    chords = ChordMap(slots, "C", "major")
    for e in out:
        span = chords.at(e.start_beat + 0.01)
        assert e.start_beat + e.duration_beats <= span.end + 1e-6, (e.start_beat, e.duration_beats)


@pytest.mark.parametrize("groups,bpb", [(None, 4.0), ((1.5, 1.5), 3.0), ((1.5,) * 4, 6.0)])
def test_composed_roles_start_every_bar_on_the_root(groups, bpb):
    from produzre.composer.bass import BassDNA, bass_bar

    slots = [SimpleNamespace(numeral=n, start_beat=bpb * i, end_beat=bpb * (i + 1))
             for i, n in enumerate(["i", "bVI", "bIII", "bVII"])]
    chords = ChordMap(slots, "E", "minor")
    # Kick patterns without a kick on one (a one-drop, a pushed kick).
    kicks = ["....x.......x...", "..x...x...x.x...", "......x.x.......", "x.x...x..."]
    for seed in range(12):
        rng = random.Random(seed)
        dna = BassDNA(drop_eighths=tuple(sorted(rng.sample(range(1, 8), 2))),
                      pop_eighth=rng.choice([None, 3, 5]), anticipate=rng.random() < 0.5,
                      hold_figure=rng.choice(["whole", "dotted", "halves"]),
                      gallop_beats=rng.choice([(0, 1, 2, 3), (1, 3), (0, 2)]))
        for role in ("kick", "pedal8", "octaves", "gallop", "whole"):
            for bar in range(4):
                notes = bass_bar(role, bar * bpb, bpb, chords, dna=dna, kick=kicks[seed % 4],
                                 groups=groups, near=40)
                assert notes and abs(notes[0][0] - bar * bpb) < 1e-6, (role, seed, bar, notes)
                assert notes[0][2] % 12 == chords.at(bar * bpb).root_pc, (role, seed, bar)


def test_country_waltz_starts_each_new_chord_on_its_root():
    from produzre.composer.bass import bass_bar, compose_bass_dna

    progression = ["I", "IV", "IV", "V", "I", "I", "V", "I"]
    slots = [SimpleNamespace(numeral=n, start_beat=3.0 * i, end_beat=3.0 * (i + 1))
             for i, n in enumerate(progression)]
    chords = ChordMap(slots, "G", "major")
    alternated = 0
    for seed in range(1, 25):
        dna = compose_bass_dna(seed=seed, genre="country")
        for bar in range(len(progression)):
            notes = bass_bar(dna.roles["verse"], bar * 3.0, 3.0, chords, dna=dna,
                             groups=(1.0, 1.0, 1.0), section_type="verse", near=40)
            span = chords.at(bar * 3.0)
            held = bar and progression[bar - 1] == progression[bar]
            first = min(notes)
            assert abs(first[0] - bar * 3.0) < 1e-6
            if not held:
                assert first[2] % 12 in (span.root_pc, tonic_pc("G")), (seed, bar, first)
            elif first[2] % 12 != span.root_pc:
                alternated += 1
    assert alternated  # held chords still alternate to the fifth


def test_bass_answers_keep_the_root_on_one(tmp_path):
    for seed in range(1, 5):
        data = {"song": {"title": "Resp", "seed": seed, "genre": "funk", "key": "E",
                         "mode": "dorian"},
                "instruments": {"lead_gtr": {"params": {"foreground": "full"}},
                                "bass": {"params": {"hook_response": True}}},
                "sections": {"chorus": {"type": "chorus", "bars": 8,
                                        "harmony": {"progression": "i7 IV7 bIII7 IV7"},
                                        "instruments": {"harmony": {}, "drums": {}, "bass": {},
                                                        "lead_gtr": {}}}},
                "arrangement": ["chorus", "chorus"]}
        cfg = _load_cfg(tmp_path, yaml.safe_dump(data, sort_keys=False), name=f"ans{seed}.yaml")
        timelines, result = _render_timelines(cfg)
        answers = [e for e in timelines["bass"].events if e.kind == "hook_response"]
        assert answers
        missing, wrong, _ = _downbeat_violations(timelines, result, "E", "dorian")
        assert not wrong, (seed, wrong)
        # No answer inside the song's ending bar: the band's ending is played
        # as written.
        end = max(ps.timing.end_beat for ps in result.plan.planned_sections)
        assert not any(e.start_beat >= end - 4.0 - 0.02 for e in answers), seed


# ---------------------------------------------------------------------------
# Composed bass dynamics
# ---------------------------------------------------------------------------

def test_composed_bass_velocity_follows_the_section_level(tmp_path):
    from produzre.composer.drums import section_level
    from produzre.orchestrate.energy import resolve_section_energy

    ratios = []
    for seed in range(1, 6):
        quiet = _band("i bVI bIII bVII", 8)
        loud = _band("i bVI bIII bVII", 8)
        quiet["intensity"], loud["intensity"] = 0.4, 1.0
        timelines, result = _render(tmp_path, seed=seed, genre="hard_rock", key="E",
                                    mode="minor", sections={"quiet": quiet, "loud": loud},
                                    arrangement=["quiet", "loud"],
                                    style={"into_chorus": "fill", "intro": "full"},
                                    bass={"params": {"articulation_style": "pick"}},
                                    name=f"dyn{seed}.yaml")
        med = {}
        for meta in _occurrences(result):
            vels = sorted(e.velocity for t, e in _local(timelines["bass"].events, meta)
                          if str(e.kind).startswith("bass_") and t < meta.length_beats - 4)
            if vels:
                med[meta.id] = vels[len(vels) // 2]
        if len(med) < 2:
            continue  # this band's verse role is the engine line
        level = section_level(1.0, resolve_section_energy(None, "verse")) / \
            section_level(0.4, resolve_section_energy(None, "verse"))
        ratios.append((med["loud"] / med["quiet"], level))
        assert med["loud"] > med["quiet"] + 10, (seed, med)
    assert ratios
    for got, want in ratios:
        # Pick articulation raises quiet notes to its floor, so the ratio
        # can only come in under the section-level ratio, never above it.
        assert 1.15 <= got <= want + 0.05, ratios


def test_repeated_sections_escalate_and_a_quieter_bridge_stays_under_the_chorus(tmp_path):
    # streetlight-summer.yaml: the bridge (intensity 0.6) played 107 against
    # choruses at 91 to 98.
    for seed in range(1, 5):
        bridge = _band("vi IV I V", 8, "bridge")
        bridge["intensity"] = 0.6
        sections = {"verse": _band("I V vi IV", 8), "chorus": _band("I V vi IV", 8, "chorus"),
                    "bridge": bridge}
        timelines, result = _render(tmp_path, seed=seed, genre="pop", sections=sections,
                                    arrangement=["verse", "chorus", "bridge", "chorus"],
                                    bass={"seed": 12, "params": {"articulation_style": "pick"}},
                                    style={"into_chorus": "fill", "intro": "full"},
                                    name=f"esc{seed}.yaml")
        med = {}
        for i, meta in enumerate(_occurrences(result)):
            vels = sorted(e.velocity for t, e in _local(timelines["bass"].events, meta)
                          if str(e.kind).startswith("bass_") and t < meta.length_beats - 4)
            if vels:
                med[(i, meta.type)] = vels[len(vels) // 2]
        choruses = [v for (i, t), v in sorted(med.items()) if t == "chorus"]
        bridges = [v for (i, t), v in med.items() if t == "bridge"]
        if choruses and bridges:
            assert max(bridges) < min(choruses), (seed, med)
        if len(choruses) == 2:
            assert choruses[1] >= choruses[0], (seed, med)


# ---------------------------------------------------------------------------
# Explicit rhythm patterns
# ---------------------------------------------------------------------------

def _bass_alone(progression="I vi IV V", bars=4, meter="4/4"):
    return {"verse": {"type": "verse", "bars": bars, "harmony": {"progression": progression},
                      "instruments": {"harmony": {}, "bass": {}}}}


@pytest.mark.parametrize("params", [
    {"rhythm_pattern": "anchor", "density": 1.0, "rest_rate": 0.0, "approach_rate": 0.3},
    {"rhythm_pattern": "anchor", "density": 0.9, "approach_rate": 0.5, "articulation_style": "pick"},
    {"rhythm_pattern": "anchor", "articulation_style": "slap", "density": 1.0},
    {"rhythm_pattern": "anchor", "articulation_style": "mute", "density": 1.0},
])
def test_an_explicit_anchor_is_played_as_written(tmp_path, params):
    for seed in range(1, 5):
        timelines, _ = _render(tmp_path, seed=seed, sections=_bass_alone(),
                               arrangement=["verse", "verse"],
                               bass={"params": dict(params, fill_rate=0.0, lock_to_kick=0.0)},
                               name=f"anc{seed}{len(params)}{params.get('articulation_style')}.yaml")
        for e in timelines["bass"].events:
            assert not str(e.kind).startswith("walk_"), e.kind
            if str(e.kind).startswith(_TRANSITION):
                continue
            local = e.start_beat % 4.0
            # Beats 1 and 3 only (a hair of groove-clock timing allowed).
            assert min(abs(local - p) for p in (0.0, 2.0, 4.0)) < 0.07, (seed, e.start_beat, e.kind)


def test_the_walking_heuristic_still_walks_an_unset_pattern(tmp_path):
    # Nobody chose the pattern: a dense line with frequent approaches walks.
    # (The gospel recipe's anchor is a genre default, not the user's choice.)
    timelines, _ = _render(tmp_path, seed=3, genre="gospel",
                           sections=_bass_alone("Imaj7 vi7 ii7 V7", 4),
                           bass={"params": {"density": 1.0, "approach_rate": 0.4}},
                           name="heur.yaml")
    kinds = Counter(str(e.kind).split("_")[0] for e in timelines["bass"].events)
    assert kinds["walk"] >= 12, kinds


# ---------------------------------------------------------------------------
# Compound meters
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("groups,bpb,strong", [((1.5, 1.5), 3.0, (0.0, 1.5)),
                                               ((1.5,) * 4, 6.0, (0.0, 3.0)),
                                               (None, 4.0, (0.0, 2.0))])
def test_composed_role_accents_sit_on_the_pulse(groups, bpb, strong):
    from produzre.composer.bass import BassDNA, bass_bar

    slots = [SimpleNamespace(numeral="I", start_beat=0.0, end_beat=bpb * 2)]
    chords = ChordMap(slots, "Ab", "major")
    for gallop in ((0, 1, 2, 3), (1, 3), (0, 2)):
        dna = BassDNA(gallop_beats=gallop, drop_eighths=())
        for role in ("pedal8", "octaves", "gallop", "kick"):
            notes = bass_bar(role, 0.0, bpb, chords, dna=dna, kick="x" * 24, groups=groups)
            accents = {round(t, 3) for t, _, _, acc in notes if acc}
            assert accents and accents <= set(strong), (role, groups, accents)
            if groups:
                # Everything on the eighth grid of the compound bar.
                assert all(abs(t * 4 - round(t * 4)) < 1e-6 for t, *_ in notes)


def test_the_engine_line_in_six_eight_plays_on_the_pulses(tmp_path):
    # gospel.yaml's bridge: an anchor line under the composed 6/8 drummer
    # played the second quarter (the third eighth), a 3/4 bar.
    for seed in range(1, 5):
        sections = {"verse": _band("I IV ii V", 8), "bridge": _band("vi IV I V", 8, "bridge")}
        timelines, result = _render(tmp_path, seed=seed, genre="gospel", meter="6/8", key="Ab",
                                    sections=sections, arrangement=["verse", "bridge"],
                                    bass={"params": {"rhythm_pattern": "anchor"}},
                                    style={"into_chorus": "fill", "intro": "full"},
                                    name=f"six{seed}.yaml")
        for meta in _occurrences(result):
            for t, e in _local(timelines["bass"].events, meta):
                if str(e.kind).startswith(("fill", "approach") + _TRANSITION) or \
                        t >= meta.length_beats - 3.0:
                    continue
                pos = t % 3.0
                assert min(abs(pos - p) for p in (0.0, 1.5, 3.0)) < 0.07, \
                    (seed, meta.id, round(t, 3), e.kind)


# ---------------------------------------------------------------------------
# Transition pickups
# ---------------------------------------------------------------------------

def test_a_bass_pickup_replaces_the_notes_it_lands_on():
    from produzre.orchestrate.transitions import (TransitionPlan, TransitionRecipe,
                                                  apply_transition_plan)
    from produzre.timeline import InstrumentTimeline

    for held_from, length in ((3.0, 1.0), (3.5, 0.5), (2.0, 1.95), (3.75, 0.25), (3.74, 0.3)):
        tl = InstrumentTimeline(instrument="bass")
        tl.add_note(start_beat=0.0, duration_beats=2.0, pitch=36, velocity=80, kind="root")
        tl.add_note(start_beat=held_from, duration_beats=length, pitch=43, velocity=80, kind="fifth")
        tl.add_note(start_beat=4.0, duration_beats=1.0, pitch=41, velocity=80, kind="root")
        plan = TransitionPlan(section_a_id="a", section_b_id="b", instrument="bass",
                              recipe=TransitionRecipe(kind="pickup"),
                              edit_windows={"tail": (0.0, 4.0), "head": (4.0, 8.0)},
                              metadata={"rng": random.Random(1)})
        apply_transition_plan(tl, "bass", plan)
        notes = sorted(tl.events, key=lambda e: e.start_beat)
        pickup = [e for e in notes if e.kind == "pickup_transition"]
        assert len(pickup) == 1
        for a, b in zip(notes, notes[1:]):
            assert a.start_beat + a.duration_beats <= b.start_beat + 1e-6, \
                (held_from, [(e.start_beat, e.duration_beats, e.kind) for e in notes])


def test_bass_pickups_never_stack_on_the_line_in_songs(tmp_path):
    sections = {"intro": dict(_band("I IV I V", 4), type="intro"),
                "verse": _band("I IV V IV", 8), "chorus": _band("I V vi IV", 8, "chorus")}
    pickups = 0
    for genre in ("reggae", "rock", "pop", "blues"):
        for seed in range(1, 4):
            timelines, _ = _render(tmp_path, seed=seed, genre=genre, sections=sections,
                                   arrangement=["intro", "verse", "chorus", "verse", "chorus"],
                                   style={"intro": "full"}, name=f"pu{genre}{seed}.yaml")
            notes = sorted(timelines["bass"].events, key=lambda e: e.start_beat)
            for p in (e for e in notes if e.kind == "pickup_transition"):
                pickups += 1
                others = [e for e in notes if e is not p]
                assert not any(e.start_beat < p.start_beat + p.duration_beats - 1e-6
                               and e.start_beat + e.duration_beats > p.start_beat + 1e-6
                               for e in others), (genre, seed, p.start_beat)
    assert pickups


# ---------------------------------------------------------------------------
# The song's last note, the slap floor
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("params", [
    {"articulation_style": "slap", "rhythm_pattern": "syncopated", "ghost_perc_rate": 0.5,
     "fill_rate": 1.0},
    {"articulation_style": "slap", "rhythm_pattern": "funk_16ths", "ghost_perc_rate": 0.3},
    {"articulation_style": "mute", "rhythm_pattern": "drive"},
    {"articulation_style": "pick", "rhythm_pattern": "rock_riff", "fill_rate": 1.0},
    {"rhythm_pattern": "walking", "articulation_style": "slap", "ghost_perc_rate": 0.5},
    {"lock_to_kicks": True},
])
def test_the_songs_last_bass_note_is_a_real_note(tmp_path, params):
    for seed in range(1, 7):
        sections = {"verse": {"type": "verse", "bars": 4, "harmony": {"progression": "I IV V I"},
                              "instruments": {"harmony": {}, "bass": {}, "drums": {}}}}
        timelines, result = _render(tmp_path, seed=seed, sections=sections,
                                    bass={"params": dict(params)},
                                    instruments={"drums": {"params": {"pattern": "rock_basic"}}},
                                    name=f"end{seed}{sorted(params.items())}.yaml".replace(" ", ""))
        notes = sorted(timelines["bass"].events, key=lambda e: (e.start_beat, e.pitch))
        last = notes[-1]
        assert "ghost" not in str(last.kind), (seed, last.kind)
        assert last.duration_beats >= 0.5, (seed, last.kind, last.duration_beats)
        assert last.pitch % 12 == 0, (seed, last.kind, last.pitch)  # the final I in C
        assert last.start_beat >= 12.0 - 0.07  # in the final bar


def test_a_named_slap_persona_slaps_and_holds_its_floor(tmp_path):
    # backstreet-strut.yaml: the funk persona under the funk recipe (which
    # plays fingerstyle) never slapped, so its floor of 75 never applied.
    sections = {"verse": _band("i7 IV7", 8), "chorus": _band("bIII7 IV7 i7 i7", 8, "chorus")}
    for seed in range(1, 5):
        timelines, _ = _render(tmp_path, seed=seed, genre="funk", key="E", mode="dorian",
                               bass={"persona": "funk"}, sections=sections,
                               arrangement=["verse", "chorus"], name=f"slapf{seed}.yaml")
        notes = [e for e in timelines["bass"].events
                 if not str(e.kind).startswith(_TRANSITION)]
        assert any("_slap_" in str(e.kind) for e in notes)
        assert all(e.velocity >= 75 for e in notes if "ghost" not in str(e.kind)), \
            sorted((e.velocity, e.kind) for e in notes if e.velocity < 75)[:5]
    # Your own articulation still wins over the persona's.
    timelines, _ = _render(tmp_path, seed=1, genre="funk", key="E", mode="dorian",
                           bass={"persona": "funk", "params": {"articulation_style": "finger"}},
                           sections=sections, arrangement=["verse", "chorus"],
                           name="slapfinger.yaml")
    assert not any("_slap_" in str(e.kind) for e in timelines["bass"].events)


def test_plain_slapped_notes_hold_the_floor():
    from produzre.engine.bass.slap import apply_slap_velocity

    for vel in range(1, 128, 7):
        assert apply_slap_velocity(vel, "normal", 75, 20) >= 75
        assert apply_slap_velocity(vel, "thumb", 75, 20) >= 75
        assert apply_slap_velocity(vel, "pop", 75, 20) >= 75
        assert apply_slap_velocity(vel, "ghost", 75, 20) <= 50


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

_MOTIF = {"bass_line": {"role": "bass_motif", "register": [36, 60],
                        "events": "1:.5 3:.5 4:1 5:1 1:1"},
          "hook": {"role": "riff", "events": "1:.5 5:.5 1:1"}}


def test_lock_to_riff_next_to_a_bass_motif_is_reported(tmp_path, caplog):
    sections = {"verse": _band("i iv v i", 4)}
    with caplog.at_level(logging.INFO):
        _render(tmp_path, seed=1, key="E", mode="minor", sections=sections, themes=_MOTIF,
                bass={"params": {"lock_to_riff": 0.8}}, name="lockmotif.yaml")
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING
                and "bass_motif" in r.getMessage() and "lock_to_riff" in r.getMessage()]
    assert warnings


def test_bass_log_shows_the_sections_mode(tmp_path, caplog):
    sections = {"verse": {"type": "verse", "bars": 4, "mode": "dorian",
                          "harmony": {"progression": "i IV i IV"},
                          "instruments": {"harmony": {}, "bass": {}}}}
    with caplog.at_level(logging.INFO):
        _render(tmp_path, seed=1, key="D", mode="major", sections=sections, name="mode.yaml")
    lines = [r.getMessage() for r in caplog.records if "[BASS]   Harmony" in r.getMessage()]
    assert lines and all("mode=dorian" in line for line in lines), lines
