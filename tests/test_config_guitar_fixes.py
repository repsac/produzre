"""Examples-findings fixes: engines block, section personas, unknown params,
rhythm-guitar walks and sustain, acoustic capo and range (2026-09-26 review,
items 8a, 8c, 8e, 13, 23, 24, 25 and 28)."""
import logging
import random
import re
from pathlib import Path
from types import SimpleNamespace as NS

import mido
import pytest
import yaml

from produzre.composer.acoustic import MELODY_CEILING, compose_picking_dna, fingerstyle
from produzre.composer.comping import compose_comp_dna, plan_comp_section, riff_events, CompRiff
from produzre.composer.groove_memory import map_pitch
from produzre.composer.theory import ChordMap, scale_pcs
from produzre.config.engines import build_engine_registry
from produzre.config.errors import ConfigError
from produzre.config.validation import (KNOWN_INSTRUMENT_FIELDS, KNOWN_PARAMS_BY_INSTRUMENT,
                                        unknown_instrument_param_warnings)
from produzre.engine.acoustic_gtr import _melody_window
from produzre.engine.acoustic_gtr.voicings import choose_acoustic_voicing
from produzre.engine.rhythm_gtr.composed import _walk_pitch, perform_comp
from produzre.melody import chord_pitch_classes
from produzre.timeline import InstrumentTimeline
from tests.test_groove_clock import _load_cfg, _render_timelines

REPO = Path(__file__).resolve().parents[1]


def _slots(prog, bpb=4.0):
    return [NS(numeral=n, start_beat=i * bpb, end_beat=(i + 1) * bpb, index=i)
            for i, n in enumerate(prog)]


def _song(tmp_path, sections, *, instruments=None, engines=None, song=None, name="song.yaml"):
    data = {"song": {"title": "Fix", "seed": 5, "key": "A", "mode": "minor", "genre": "rock",
                     "bpm": 100, **(song or {})},
            "instruments": instruments or {},
            "sections": sections,
            "arrangement": list(sections)}
    if engines is not None:
        data["engines"] = engines
    return _load_cfg(tmp_path, yaml.safe_dump(data, sort_keys=False), name=name)


def _section(stype="verse", bars=4, prog="i bVI bIII bVII", **insts):
    return {"type": stype, "bars": bars, "harmony": {"progression": prog},
            "instruments": {"harmony": {}, **insts}}


# --- 8a: the engines block ---------------------------------------------------

_BUILTINS = ("bass", "drums", "rhythm_gtr", "lead_gtr", "acoustic_gtr", "arpeggiator")


def test_engines_block_overrides_each_registry_field():
    defaults = build_engine_registry({})
    rng = random.Random(8)
    for _ in range(30):
        name = rng.choice(_BUILTINS)
        program, channel, priority = rng.randint(0, 127), rng.randint(0, 15), rng.randint(0, 9)
        reg = build_engine_registry({"engines": {name: {"program": program, "channel": channel,
                                                        "priority": priority}}})
        assert (reg[name].program, reg[name].channel, reg[name].priority) == (program, channel, priority)
        # Unset fields and other engines keep the built-in registry.
        assert reg[name].requires == defaults[name].requires
        assert reg[name].module_path == defaults[name].module_path
        for other in _BUILTINS:
            if other != name:
                assert reg[other].program == defaults[other].program


def test_engines_block_wins_over_instrument_registry_fields(caplog):
    with caplog.at_level(logging.WARNING, logger="produzre.config.engines"):
        reg = build_engine_registry({"instruments": {"bass": {"program": 38, "channel": 5}},
                                     "engines": {"bass": {"program": 42}}})
    assert reg["bass"].program == 42 and reg["bass"].channel == 5
    assert any("engines.bass" in r.getMessage() and "program" in r.getMessage() for r in caplog.records)


def test_engines_block_registers_a_new_engine():
    reg = build_engine_registry({"engines": {"pad": {"engine": ".engine.arpeggiator", "channel": 7,
                                                     "program": 89, "requires": ["harmony.plan"]}}})
    assert reg["pad"].channel == 7 and reg["pad"].program == 89
    with pytest.raises(ConfigError):
        build_engine_registry({"engines": {"pad": {"channel": 7}}})
    with pytest.raises(ConfigError):
        build_engine_registry({"engines": ["bass"]})


def test_engines_program_reaches_the_midi_file(tmp_path):
    from produzre.orchestrate.build import build_song

    cfg = _song(tmp_path, {"verse": _section(bass={})}, engines={"bass": {"program": 32}},
                song={"exports_root": str(tmp_path / "out")})
    build_song(cfg=cfg, dry_run=False, export_sections=False, export_patterns=False,
               sections_absolute_timing=False)
    stems = list((tmp_path / "out").rglob("*_bass.mid"))
    assert stems
    programs = {m.program for t in mido.MidiFile(str(stems[0])).tracks for m in t
                if m.type == "program_change"}
    assert programs == {32}


# --- 8c: section-level personas ---------------------------------------------

def _effective(cfg, sec, inst):
    from produzre.groove import effective_params_dict
    from produzre.orchestrate.render import _get_global_instrument_cfg, _merge_instrument_config

    return effective_params_dict(_merge_instrument_config(
        _get_global_instrument_cfg(cfg, inst, sec), cfg.sections[sec].instruments[inst]))


@pytest.mark.parametrize("inst", ["bass", "drums", "rhythm_gtr", "lead_gtr", "acoustic_gtr"])
def test_section_persona_applies_under_user_params(tmp_path, inst):
    from produzre.config.load import _load_personas_registry_for_instrument

    personas = _load_personas_registry_for_instrument(inst)["personas"]
    for i, name in enumerate(sorted(personas)):
        params = personas[name].get("params") or {}
        keys = sorted(k for k in params if not isinstance(params[k], (dict, list)))
        if len(keys) < 2:
            continue
        global_key, section_key = keys[0], keys[1]
        cfg = _song(tmp_path, {
            "a": _section(**{inst: {}}),
            "b": _section(stype="chorus", **{inst: {"persona": name,
                                                   "params": {section_key: "section"}}}),
        }, instruments={inst: {"params": {global_key: "global"}}}, name=f"{inst}{i}.yaml")
        b = _effective(cfg, "b", inst)
        for k in keys[2:]:
            assert b.get(k) == params[k], (inst, name, k)      # the section's persona
        assert b[global_key] == "global"                        # global params win over it
        assert b[section_key] == "section"                      # section params win over all
        # Other sections keep the global persona.
        default = cfg.raw["_effective"]["instruments"][inst]["params"]
        assert {k: _effective(cfg, "a", inst).get(k) for k in keys[2:]} == \
            {k: default.get(k) for k in keys[2:]}


def test_section_persona_voices_reach_the_drums(tmp_path):
    cfg = _song(tmp_path, {"a": _section(drums={}), "b": _section(drums={"params": {"persona": "metal"}})})
    eff = cfg.raw["_effective"]["sections"]["b"]["drums"]
    assert eff["persona"] == "metal" and eff["voices"]
    assert "a" not in cfg.raw["_effective"].get("sections", {})


def test_unknown_section_persona_is_an_error(tmp_path):
    with pytest.raises(ConfigError, match="unknown persona"):
        _song(tmp_path, {"a": _section(bass={"persona": "nope"})})


def test_global_persona_in_params_is_honored(tmp_path):
    cfg = _song(tmp_path, {"a": _section(bass={})}, instruments={"bass": {"params": {"persona": "loose"}}})
    assert cfg.raw["_effective"]["instruments"]["bass"]["persona"] == "loose"


# --- 8e: unknown params --------------------------------------------------------

def test_every_known_param_is_accepted():
    for inst, known in KNOWN_PARAMS_BY_INSTRUMENT.items():
        keys = sorted(known | KNOWN_INSTRUMENT_FIELDS)
        raw = {"instruments": {inst: {"params": {k: 1 for k in keys}}},
               "sections": {"s": {"instruments": {inst: {"params": {k: 1 for k in keys},
                                                         **{k: 1 for k in keys}}}}}}
        assert unknown_instrument_param_warnings(raw) == [], inst


def test_documented_instrument_params_are_known():
    text = (REPO / "docs" / "llm-song-config-reference.md").read_text()
    heads = {"Bass": "bass", "Drum": "drums", "Rhythm guitar": "rhythm_gtr",
             "Lead guitar": "lead_gtr", "Acoustic guitar": "acoustic_gtr", "Arpeggiator": "arpeggiator"}
    seen = 0
    for block in re.split(r"\n## ", text):
        inst = next((v for k, v in heads.items() if block.startswith(k)), None)
        if inst is None:
            continue
        known = KNOWN_PARAMS_BY_INSTRUMENT[inst] | KNOWN_INSTRUMENT_FIELDS
        for line in block.splitlines():
            if line.startswith("| `"):
                for key in re.findall(r"`([a-z_0-9]+)`", line.split("|")[1]):
                    # Drum voice and constraint sub-keys live under voices/constraints.
                    if inst == "drums" and key in ("max_hand_hits", "max_foot_hits", "fill_duck_hats",
                                                   "kick_density_hihat_pedal_limit"):
                        continue
                    assert key in known, (inst, key)
                    seen += 1
    assert seen > 60


@pytest.mark.parametrize("inst,key,hint", [
    ("bass", "phrase_bars", "phrase_len_bars"), ("drums", "fill_len_beats", "fill_length"),
    ("lead_gtr", "leap_probability", "rest_probability"), ("acoustic_gtr", "pattern", "picking_pattern"),
])
def test_unknown_params_name_key_instrument_and_suggestion(inst, key, hint):
    for where in ("global", "section", "direct"):
        if where == "global":
            raw = {"instruments": {inst: {"params": {key: 1}}}}
        elif where == "section":
            raw = {"sections": {"v": {"instruments": {inst: {"extra": {key: 1}}}}}}
        else:
            raw = {"sections": {"v": {"instruments": {inst: {key: 1}}}}}
        (msg,) = unknown_instrument_param_warnings(raw)
        assert f"'{key}'" in msg and inst in msg and f"'{hint}'" in msg


def test_registry_fields_and_custom_engines():
    raw = {"instruments": {"bass": {"program": 33, "channel": 1}},
           "engines": {"bass": {"progam": 3}},
           "sections": {"v": {"instruments": {"bass": {"program": 5}, "pad": {"anything": 1}}}}}
    msgs = unknown_instrument_param_warnings(raw)
    assert len(msgs) == 2
    assert any("'progam'" in m and "'program'" in m for m in msgs)
    assert any("engines.bass" in m and "section 'v'" in m for m in msgs)


def test_build_logs_unknown_params_and_still_loads(tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger="produzre.config.load"):
        cfg = _song(tmp_path, {"v": _section(bass={"params": {"kick_syncopation_rate": .3}})})
    assert cfg.sections["v"]
    assert any("kick_syncopation_rate" in r.getMessage() and "bass" in r.getMessage()
               for r in caplog.records)


# --- 13: walks lead into chord changes --------------------------------------

_PROGS = (["i", "i", "bVI", "bVI", "iv", "iv", "V", "i"], ["I", "IV"] * 4, ["i"] * 8,
          ["vi", "IV", "IV", "I", "V", "V", "vi", "vi"])


def _landing(ev, e, total):
    later = [x.beat for x in ev if x.beat > e.beat + 1e-6 and x.kind != "walk"]
    return min(later + [(int(e.beat // 4) + 1) * 4.0, total])


def test_every_composed_walk_lands_on_a_chord_change():
    walks = 0
    for genre in ("rock", "country", "funk", "blues", "pop", "hard_rock", "soul", "folk"):
        for seed in range(12):
            dna = compose_comp_dna(seed=seed, genre=genre, key="A", mode="minor", shuffle=genre == "blues")
            prog = _PROGS[seed % len(_PROGS)]
            cm = ChordMap(_slots(prog), "A", "minor")
            for st in ("verse", "chorus", "bridge", "prechorus", "solo"):
                ev, _, _ = plan_comp_section(dna, section_type=st, occurrence=0, is_final_of_type=False,
                                             bars=8, beats_per_bar=4, chord_slots=_slots(prog), key="A",
                                             mode="minor", next_section_type="verse")
                for e in ev:
                    if e.kind != "walk":
                        continue
                    walks += 1
                    land = _landing(ev, e, cm.total)
                    assert land < cm.total and cm.at(land).pcs != cm.at(e.beat).pcs, (genre, seed, st, e)
                    assert e.target_pc == cm.at(land).root_pc
    assert walks > 100


def test_walk_over_a_held_chord_becomes_a_hold():
    riff = CompRiff("probe", ("rock",), "low", "x-x-x-x-x-x-w-x-", 1.0)
    held = riff_events(riff, 0, 4, ChordMap(_slots(["I", "I"]), "C", "major"))
    assert not [e for e in held if e.kind == "walk"]
    assert [round(e.dur, 2) for e in held if e.beat == 2.5] == [1.0]   # the previous strum rings on


def test_walk_pitch_never_rubs_the_chord_it_is_played_over():
    rng = random.Random(3)
    for _ in range(400):
        key = rng.choice(("C", "D", "E", "F", "G", "A", "Bb", "F#"))
        mode = rng.choice(("major", "minor", "dorian", "mixolydian"))
        numeral = rng.choice(("i", "I", "iv", "IV", "V", "bVI", "bVII", "ii", "vi", "Imaj7", "vi7"))
        target = rng.randrange(12)
        chord = chord_pitch_classes(numeral, key, mode)
        scale = set(scale_pcs(key, mode))
        near = 40 + rng.randrange(8)
        lead = _walk_pitch(target, 0, near, key, mode, chord)
        lower = _walk_pitch(target, 1, near, key, mode, chord)
        assert lower < lead and 0 < ((target - lead) % 12) <= 2
        if lead % 12 not in scale:
            assert (lead + 1) % 12 == target
            assert not any((lead - pc) % 12 in (1, 11) for pc in chord)


def test_performed_walks_over_a_minor_avoid_c_sharp():
    # The review case: into Dm from Am or Fmaj7, the approach is C, never C#.
    for numeral in ("i", "bVImaj7"):
        tl = InstrumentTimeline("rhythm_gtr")
        full = [45, 52, 57, 60, 64]
        perform_comp([dict(beat=3.5, dur=.5, kind="walk", target_pc=2)], timeline=tl,
                     section_start_beat=0, shape_at=lambda b: (full, [45, 52], numeral),
                     key="A", mode="minor", intensity=.8, bpm=100, ring=1, rng=random.Random(1),
                     timing_jitter_ms=0)
        assert [e.pitch % 12 for e in tl.events] == [0]


# --- 25: sustain on both renderers -------------------------------------------

@pytest.mark.parametrize("use_patterns", [False, True])
def test_sustain_mode_holds_every_chord(tmp_path, use_patterns):
    for hold in (0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0):
        cfg = _song(tmp_path, {"v": _section(prog="i bVI bIII bVII", drums={}, rhythm_gtr={})},
                    instruments={"rhythm_gtr": {"params": {"sustain_mode": True, "sustain_duration": hold,
                                                           "use_patterns": use_patterns}}},
                    name=f"s{hold}{use_patterns}.yaml")
        events = _render_timelines(cfg)[0]["rhythm_gtr"].events
        strikes = sorted({round(e.start_beat * 4) / 4 for e in events})
        expected = sorted({round(c + k * hold, 4) for c in (0, 4, 8, 12)
                           for k in range(16) if k * hold < 4 - 1e-6})
        assert strikes == [round(x * 4) / 4 for x in expected] or \
            [round(s, 1) for s in strikes] == [round(x, 1) for x in expected], (hold, strikes)
        for e in events:
            strike = round(e.start_beat * 4) / 4
            want = min(hold, (int(strike // 4) + 1) * 4 - strike)
            assert abs(e.duration_beats - want) < 0.08, (hold, e)
        by_pitch = {}
        for e in sorted(events, key=lambda e: e.start_beat):
            assert e.start_beat >= by_pitch.get(e.pitch, -1) - 1e-6   # no self-overlap
            by_pitch[e.pitch] = e.start_beat + e.duration_beats


def test_grid_sustain_is_not_palm_muted_by_the_section_default(tmp_path):
    def mean_velocity(params):
        cfg = _song(tmp_path, {"v": _section(drums={}, rhythm_gtr={})},
                    instruments={"rhythm_gtr": {"params": {"use_patterns": False, "sustain_mode": True,
                                                           **params}}},
                    name=f"m{len(params)}.yaml")
        ev = _render_timelines(cfg)[0]["rhythm_gtr"].events
        return sum(e.velocity for e in ev) / len(ev)
    assert mean_velocity({}) > mean_velocity({"mute": 1.0}) + 5


@pytest.mark.parametrize("cap", [0.3, 0.75, 2.5])
def test_sustain_duration_caps_every_renderer(tmp_path, cap):
    for i, params in enumerate(({"use_patterns": True}, {"use_patterns": False}, {})):
        cfg = _song(tmp_path, {"v": _section(drums={}, bass={}, rhythm_gtr={})},
                    instruments={"rhythm_gtr": {"params": {"sustain_duration": cap, **params}}},
                    name=f"c{cap}{i}.yaml")
        events = _render_timelines(cfg)[0]["rhythm_gtr"].events
        assert events and max(e.duration_beats for e in events) <= cap + 1e-6, (params, cap)


def test_pattern_renderer_rings_longer_with_a_long_sustain(tmp_path):
    def longest(params):
        cfg = _song(tmp_path, {"v": _section(stype="bridge", drums={}, rhythm_gtr={})},
                    instruments={"rhythm_gtr": {"params": {"use_patterns": True, "style": "half_time",
                                                           **params}}},
                    name=f"l{len(params)}.yaml")
        return max(e.duration_beats for e in _render_timelines(cfg)[0]["rhythm_gtr"].events)
    assert longest({}) <= 1.0 + 1e-6 < longest({"sustain_duration": 4})


# --- 23 and 24: acoustic capo and range ----------------------------------------

def _voicings(prog, key, mode, style, capo):
    from produzre.engine.acoustic_gtr import _resolve_root

    cfg = NS(song=NS(key=key, mode=mode))
    sec = NS(key=None, mode=None)
    out, prev = {}, None
    for n in prog:
        prev = choose_acoustic_voicing(_resolve_root(cfg, sec, n, None), n, style, prev, capo=capo)
        out[n] = prev
    return out


def test_fingerstyle_voices_sound_in_the_song_key_with_any_capo():
    rng = random.Random(11)
    for _ in range(60):
        key = rng.choice(("C", "D", "E", "G", "A", "B", "F#", "Bb"))
        mode = rng.choice(("major", "minor"))
        prog = ["I", "V", "vi", "IV"] if mode == "major" else ["i", "bVI", "bIII", "bVII"]
        capo = rng.randrange(8)
        seed = rng.randrange(1000)
        chords = ChordMap(_slots(prog), key, mode)
        voicings = _voicings(prog, key, mode, rng.choice(("open", "barre", "auto")), capo)
        notes = fingerstyle(seed, "folk", chords, voicings, bars=4, bpb=4, groups=(2.0, 2.0),
                            section_type=rng.choice(("verse", "chorus")), capo=capo, closing=True)
        dna = compose_picking_dna(seed, "folk")
        scale = set(scale_pcs(key, mode))
        for beat, dur, pitch, vel, kind in notes:
            span = chords.at(beat)
            if kind == "acoustic_thumb":
                bass_pcs = {span.root_pc, (span.root_pc + dna.fifth) % 12}
                assert pitch % 12 in bass_pcs or (dna.thumb == "walking" and pitch % 12 in scale), \
                    (key, capo, beat, pitch)
                assert 40 <= pitch <= 40 + capo + 26
            elif kind == "acoustic_theme":
                assert pitch % 12 in span.pcs and 55 <= pitch <= MELODY_CEILING, (key, capo, pitch)
            else:
                assert pitch in voicings[span.numeral].pitches


@pytest.mark.parametrize("style", ["open", "barre", "auto"])
def test_acoustic_shapes_sit_low_on_the_neck(style):
    for key in ("C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"):
        for capo in range(8):
            for numeral in ("I", "ii", "iii", "IV", "V", "vi", "V7", "i", "bVII", "Imaj7"):
                rv = _voicings([numeral], key, "major", style, capo)[numeral]
                fretted = [f for f in rv.frets if f > 0]
                assert not fretted or min(fretted) <= 12, (key, capo, numeral, rv.frets)
                assert max(rv.pitches) <= 64 + capo + 15, (key, capo, numeral, rv.pitches)
                assert min(rv.pitches) >= 40 + capo


def test_melody_window_stays_under_the_ceiling():
    for top in range(55, 95):
        lo, hi = _melody_window(top)
        assert lo <= hi and hi <= max(MELODY_CEILING, top) and hi <= top + 9


def test_groove_memory_keeps_the_acoustic_melody_in_range():
    from produzre.composer.theory import ChordSpan

    src = ChordSpan(0, 4, "IV", (5, 9, 0), 5)
    dst = ChordSpan(4, 8, "bVII", (10, 2, 5), 10)
    for pitch in range(60, 82):
        assert map_pitch(pitch, src, dst, scale_pcs("C", "major"), 40, 81) <= 81


@pytest.mark.parametrize("pattern", ["cinematic", "pima", "broken_chord", "travis"])
def test_band_fingerpicking_stays_in_acoustic_range(tmp_path, pattern):
    for i, (key, capo) in enumerate((("Bb", 2), ("D", 7), ("B", 5), ("F#", 0))):
        cfg = _song(tmp_path, {"v": _section(bars=8, prog="I V vi IV", drums={}, bass={}, lead_gtr={},
                                             acoustic_gtr={})},
                    instruments={"acoustic_gtr": {"params": {"voicing_style": "barre", "capo": capo,
                                                             "technique": "fingerpicking",
                                                             "picking_pattern": pattern}}},
                    song={"key": key, "mode": "major", "genre": "folk"}, name=f"a{pattern}{i}.yaml")
        events = _render_timelines(cfg)[0]["acoustic_gtr"].events
        assert events
        assert all(40 <= e.pitch <= MELODY_CEILING for e in events), \
            (key, capo, sorted({e.pitch for e in events})[-3:])
