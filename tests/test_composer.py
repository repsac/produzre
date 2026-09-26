"""Composer: song DNA, phrase memory, groove memory, cadential phrasing.

These tests pin *musical* properties, not exact notes: the hook returns
note-for-note, grooves repeat bar-to-bar with chord-relative voicing, rests
survive, cadences land on chord tones, and every stage stays deterministic.
"""
from __future__ import annotations

from types import SimpleNamespace as NS

import pytest
import yaml

from produzre.composer import cells as C
from produzre.composer.dna import _parse_pattern, compose_dna, contour_score
from produzre.composer.groove_memory import (
    GrooveMemory, apply_groove_memory, bar_form, map_pitch, source_bars,
)
from produzre.composer.lead import LeadContext, SongComposer
from produzre.composer.licks import LICKS, realize_lick
from produzre.composer.listener import Listener
from produzre.composer.realize import realize_cell
from produzre.composer.theory import ChordMap
from produzre.harmony.phrasing import apply_turnaround, turnaround_chord
from produzre.harmony.plan import ChordSlot, HarmonySectionPlan
from produzre.harmony.meter import parse_meter
from produzre.melody import chord_pitch_classes
from produzre.timeline import NoteEvent
from tests.test_groove_clock import _load_cfg, _render_timelines


def _slots(prog, bpb=4.0):
    return [NS(numeral=n, start_beat=i * bpb, end_beat=(i + 1) * bpb, index=i)
            for i, n in enumerate(prog)]


def _ctx(sid, stype, occ, prog, *, final=False, fg="full", bars=8, key="E", mode="minor"):
    slots = _slots([prog[i % len(prog)] for i in range(bars)])
    return LeadContext(sid, stype, occ, final, bars, 4.0, bars * 4.0, key, mode, slots,
                       foreground=fg, register=(60, 79))


def _composer(seed=7, genre="rock"):
    return SongComposer(seed=seed, genre=genre, key="E", mode="minor", beats_per_bar=4.0,
                        hook_slots=_slots(["i", "bVII"]), verse_slots=_slots(["i", "bVI"]),
                        register=(60, 79))


# --- DNA ---------------------------------------------------------------------

def test_dna_is_deterministic_and_seeded():
    a = compose_dna(seed=11, genre="rock", key="E", mode="minor", beats_per_bar=4.0)
    b = compose_dna(seed=11, genre="rock", key="E", mode="minor", beats_per_bar=4.0)
    c = compose_dna(seed=12, genre="rock", key="E", mode="minor", beats_per_bar=4.0)
    assert a.signature == b.signature
    assert a.signature != c.signature


def test_dna_verse_rhythm_contrasts_with_hook():
    for seed in range(8):
        dna = compose_dna(seed=seed, genre="pop", key="C", mode="major", beats_per_bar=4.0)
        assert dna.verse.durations != dna.hook.durations


def test_rhythm_patterns_parse_to_full_bars():
    assert _parse_pattern("x..x..x.x.......") == (0.75, 0.75, 0.5, 2.0)
    assert _parse_pattern("--x.x.x.x.......") == (-0.5, 0.5, 0.5, 0.5, 2.0)
    assert abs(sum(abs(d) for d in _parse_pattern("x.x.x.x.x...----")) - 4.0) < 1e-9


def test_contour_score_prefers_gap_fill_over_monotone():
    gap_fill = [64, 69, 67, 65, 64]      # leap up, stepwise recovery
    monotone = [64, 64, 64, 64, 64]
    assert contour_score(gap_fill) > contour_score(monotone)


# --- realization -------------------------------------------------------------

def test_realized_motif_keeps_contour_over_changing_chords():
    cell = C.cell_from([0.5, 0.5, 1.0, 0.5, 1.5], [0, 1, 1, -3, 1])
    chords = ChordMap(_slots(["i", "bVI", "bVII"]), "E", "minor")
    for bar in range(3):
        notes, _ = realize_cell(cell, bar * 4.0, chords, key="E", mode="minor",
                                lo=60, hi=81, anchor=71)
        moves = [b.pitch - a.pitch for a, b in zip(notes, notes[1:])]
        signs = [m > 0 for m in moves if m]
        assert signs[:2] == [True, True], (bar, moves)  # the rise survives
        # Long notes and downbeats sit on chord tones.
        span = chords.at(bar * 4.0)
        for n in notes:
            if n.dur >= 1.0 or abs(n.beat % 4.0) < 1e-6:
                assert n.pitch % 12 in span.pcs


def test_lick_moves_by_octave_as_a_whole():
    tremolo = next(l for l in LICKS if l.name == "tremolo_scream")
    chords = ChordMap(_slots(["i"]), "E", "minor")
    notes = realize_lick(tremolo, 0.0, chords, key="E", mode="minor", lo=60, hi=86, anchor=90)
    heights = [n.pitch for n in notes]
    # The written shape (four repeats, a step up, back, a bend down) survives.
    assert heights[0] == heights[1] == heights[2] == heights[3]
    assert heights[4] > heights[3] and heights[5] == heights[3]
    assert max(heights) <= 88


# --- section memory ----------------------------------------------------------

def test_chorus_returns_note_for_note_and_final_chorus_lifts():
    comp = _composer()
    prog = ["i", "bVII", "bVI", "bVII"]
    first = comp.compose_lead(_ctx("chorus", "chorus", 0, prog))
    comp.compose_lead(_ctx("verse", "verse", 0, ["i", "bVI"]))
    second = comp.compose_lead(_ctx("chorus", "chorus", 1, prog))
    last = comp.compose_lead(_ctx("chorus", "chorus", 2, prog, final=True))
    key = lambda ns: [(n.beat, n.pitch, n.dur) for n in ns]
    assert key(first) == key(second)
    assert key(last) != key(first)
    assert sum(n.pitch for n in last) / len(last) >= sum(n.pitch for n in first) / len(first)


def test_second_verse_keeps_melody_shape():
    comp = _composer(seed=3)
    v1 = comp.compose_lead(_ctx("v1", "verse", 0, ["i", "bVI", "bIII", "bVII"]))
    v2 = comp.compose_lead(_ctx("v2", "verse", 1, ["i", "bVI", "bIII", "bVII"]))
    # Same idea, "new lyrics": most bar downbeat-region pitches agree.
    first_notes = lambda ns: [next((n.pitch for n in ns if b * 4 <= n.beat < b * 4 + 4), None)
                              for b in range(8)]
    same = sum(1 for a, b in zip(first_notes(v1), first_notes(v2)) if a == b)
    assert same >= 6


def test_chorus_cadence_lands_on_chord_tone():
    comp = _composer(seed=5)
    prog = ["i", "bVII", "bVI", "bVII"]
    notes = comp.compose_lead(_ctx("chorus", "chorus", 0, prog))
    final = notes[-1]
    pcs = chord_pitch_classes("bVII", "E", "minor")
    assert final.pitch % 12 in pcs


def test_solo_has_single_climax_and_resolves():
    comp = _composer(seed=9)
    notes = comp.compose_lead(_ctx("solo", "solo", 0, ["i", "bVI", "bVII", "i"]))
    top = max(n.pitch for n in notes)
    peak_bars = {int(n.beat // 4) for n in notes if n.pitch == top}
    assert len(peak_bars) <= 2, peak_bars
    assert min(peak_bars) >= 3                     # the climax comes late
    assert notes[-1].pitch % 12 == 4               # ends on the tonic (E)
    assert max(n.pitch for n in notes) <= 88


def test_vocal_mode_leaves_room_for_the_singer():
    comp = _composer(seed=4)
    notes = comp.compose_lead(_ctx("verse", "verse", 0, ["i", "bVI", "bIII", "bVII"], fg="auto"))
    busy_bars = {int(n.beat // 4) for n in notes}
    assert busy_bars <= {3, 7}                     # fills answer phrase ends only


def test_listener_finds_repetition_predictable():
    ear = Listener()
    motif = [64, 67, 69, 67, 64]
    durs = [0.5, 0.5, 1.0, 0.5, 1.5]
    fresh = ear.mean_information(motif, durs)
    for _ in range(3):
        ear.observe(motif, durs)
    assert ear.mean_information(motif, durs) < fresh


# --- groove memory -----------------------------------------------------------

def test_bar_form_keeps_phrase_ends_for_the_engine():
    assert bar_form(8) == [0, 0, 0, None, 0, 0, 0, None]
    assert bar_form(8, cycle=2) == [0, 1, 0, None, 0, 1, 0, None]
    assert bar_form(2) == [None, None]


def test_source_bar_is_the_most_typical_bar():
    form = bar_form(8)
    sig = {0: (1, 2), 1: (1, 2, 3, 4, 5), 2: (1, 2), 4: (1, 2), 5: (1, 2), 6: (1, 3)}
    assert source_bars(form, 1, sig)[0] in (2, 4, 5)


def test_map_pitch_keeps_chord_role():
    cm = ChordMap(_slots(["i", "bVI"]), "E", "minor")
    em, c = cm.at(0.0), cm.at(4.0)
    assert map_pitch(43, em, c, (4, 6, 7, 9, 11, 0, 2)) % 12 == 4   # G (3rd of Em) -> E (3rd of C)
    assert map_pitch(40, em, c, (4, 6, 7, 9, 11, 0, 2)) % 12 == 0   # root -> root


def _bass_events(pattern_by_bar, bars=8):
    out = []
    for b in range(bars):
        for off, pitch, kind in pattern_by_bar(b):
            out.append(NoteEvent(b * 4.0 + off, 0.45, pitch, 90, 1, kind))
    return out


def test_groove_memory_restates_bars_chord_relatively_and_keeps_rests():
    prog = ["i", "bVI", "bIII", "bVII"] * 2
    import random
    rng = random.Random(1)
    cm = ChordMap(_slots(prog), "E", "minor")

    def bar(b):
        if b == 2:
            return []  # a deliberate rest bar
        root = 36 + (cm.at(b * 4.0).root_pc - 36) % 12
        return [(off, root, "root") for off in sorted(rng.sample([0, 0.5, 1, 1.5, 2, 2.5, 3], 3))]

    events = _bass_events(bar)
    out, report = apply_groove_memory(
        events, instrument="bass", section_start=0.0, beats_per_bar=4.0, bars=8,
        chord_slots=_slots(prog), key="E", mode="minor", genre="rock", bpm=120,
        memory=GrooveMemory(), memory_key=("bass", "verse"), seed=1,
    )
    assert report["applied"]
    by_bar = {}
    for e in out:
        by_bar.setdefault(int(e.start_beat // 4), []).append(e)
    assert 2 not in by_bar                                   # rest preserved
    rhythms = {b: tuple(round(e.start_beat - b * 4, 3) for e in by_bar[b]) for b in (0, 1, 4, 5, 6)}
    assert len(set(rhythms.values())) == 1                    # one locked groove
    for b in (0, 1, 4, 5, 6):
        assert all(e.pitch % 12 == cm.at(b * 4.0).root_pc for e in by_bar[b])


def test_groove_memory_leaves_grid_exact_parts_on_the_grid():
    events = _bass_events(lambda b: [(0, 40, "root"), (1.5, 40, "root"), (2, 47, "fifth")])
    out, _ = apply_groove_memory(
        events, instrument="bass", section_start=0.0, beats_per_bar=4.0, bars=8,
        chord_slots=_slots(["i"] * 8), key="E", mode="minor", genre="rock", bpm=120,
        memory=None, memory_key=None, seed=3,
    )
    assert all(abs(e.start_beat * 4 - round(e.start_beat * 4)) < 1e-9 for e in out)


def test_groove_memory_skips_theme_quotes():
    events = _bass_events(lambda b: [(0, 40, "motif"), (1, 43, "motif"), (2, 45, "root")])
    out, report = apply_groove_memory(
        events, instrument="bass", section_start=0.0, beats_per_bar=4.0, bars=8,
        chord_slots=_slots(["i", "bVI"] * 4), key="E", mode="minor", genre="rock", bpm=120,
        memory=None, memory_key=None, seed=3,
    )
    assert not report["applied"] and out is events


# --- cadential phrasing ------------------------------------------------------

def _hplan(sid, prog, source="preset"):
    slots = [ChordSlot(i, n, i * 4.0, (i + 1) * 4.0) for i, n in enumerate(prog)]
    return HarmonySectionPlan(sid, parse_meter("4/4"), len(prog) * 4.0, 4.0, slots, source)


def test_turnaround_leads_home():
    verse, chorus = _hplan("v", ["i", "bVI", "bIII", "i"]), _hplan("c", ["i", "bVII"])
    assert apply_turnaround(verse, chorus, mode="minor", genre="rock")
    assert [s.numeral for s in verse.chord_slots][-2:] == ["i", "bVII"]
    assert verse.chord_slots[-1].start_beat == 14.0 and verse.chord_slots[-1].end_beat == 16.0
    assert turnaround_chord("minor", "blues") == "V7"
    assert turnaround_chord("major", "pop") == "V"


def test_turnaround_skips_sections_already_on_the_dominant():
    pre = _hplan("p", ["iv", "bVI", "bVII", "bVII"])
    assert not apply_turnaround(pre, _hplan("c", ["i"]), mode="minor", genre="rock")


# --- integration -------------------------------------------------------------

def _song(tmp_path, **song_extra):
    data = {
        "song": {"title": "ComposerTest", "seed": 21, "genre": "rock", "key": "E", "mode": "minor",
                 **song_extra},
        "instruments": {"lead_gtr": {"params": {"foreground": "full"}}},
        "sections": {
            "verse": {"type": "verse", "bars": 8, "harmony": {"progression": "i bVI bIII bVII"},
                      "instruments": {"harmony": {}, "drums": {}, "bass": {}, "lead_gtr": {}}},
            "chorus": {"type": "chorus", "bars": 8, "harmony": {"progression": "i bVII bVI bVII"},
                       "instruments": {"harmony": {}, "drums": {}, "bass": {}, "lead_gtr": {}}},
        },
        "arrangement": ["verse", "chorus", "verse", "chorus", "chorus"],
    }
    return _load_cfg(tmp_path, yaml.safe_dump(data, sort_keys=False))


def _section_notes(timeline, start, length):
    return [(round(e.start_beat - start, 1), e.pitch) for e in timeline.events
            if start - 0.1 <= e.start_beat < start + length - 0.1 and e.kind != "slide_grace"]


def test_song_lead_hook_recurs_across_choruses(tmp_path):
    timelines, result = _render_timelines(_song(tmp_path))
    lead = timelines["lead_gtr"]
    c1 = _section_notes(lead, 32.0, 32.0)
    c2 = _section_notes(lead, 96.0, 32.0)
    assert c1 and [p for _, p in c1] == [p for _, p in c2]
    # Monophonic line: nothing still sounds when the next note starts.
    evs = sorted((e for e in lead.events if e.kind != "slide_grace"), key=lambda e: e.start_beat)
    for a, b in zip(evs, evs[1:]):
        assert a.start_beat + a.duration_beats <= b.start_beat + 0.02


def test_final_chorus_modulation_moves_every_pitched_part(tmp_path):
    timelines, _ = _render_timelines(_song(tmp_path, final_chorus="modulate"))
    bass = timelines["bass"]
    last = [e.pitch % 12 for e in bass.events if 128.0 <= e.start_beat < 132.0]
    first = [e.pitch % 12 for e in bass.events if 32.0 <= e.start_beat < 36.0]
    assert last and first
    assert (last[0] - first[0]) % 12 == 2          # up a whole step


def test_composer_opt_out_restores_legacy_lead(tmp_path):
    _, result = _render_timelines(_song(tmp_path, composer=False))
    assert result.performance_plan.get("composer.song") is None
    assert result.performance_plan.get("composer.lead.chorus") is None


def test_groove_memory_opt_out(tmp_path):
    on, _ = _render_timelines(_song(tmp_path))
    off, _ = _render_timelines(_song(tmp_path, groove_memory=False))
    sig = lambda tl: [(round(e.start_beat, 3), e.pitch) for e in tl.events]
    assert sig(on["bass"]) != sig(off["bass"])


def test_build_is_deterministic(tmp_path):
    a, _ = _render_timelines(_song(tmp_path))
    b, _ = _render_timelines(_song(tmp_path))
    for inst in ("lead_gtr", "bass", "drums"):
        assert [(e.start_beat, e.pitch, e.velocity, e.duration_beats) for e in a[inst].events] == \
               [(e.start_beat, e.pitch, e.velocity, e.duration_beats) for e in b[inst].events]


# --- regressions from the composer review ------------------------------------

def test_recalled_groove_follows_a_key_change():
    prog = ["i", "iv", "bVI", "bVII"] * 2
    mem = GrooveMemory()

    def bars(key):
        cm = ChordMap(_slots(prog), key, "minor")
        return _bass_events(lambda b: [(0, 36 + (cm.at(b * 4.0).root_pc - 36) % 12, "root"),
                                       (2, 36 + (cm.at(b * 4.0).root_pc - 36) % 12, "root")])

    common = dict(instrument="bass", section_start=0.0, beats_per_bar=4.0, bars=8,
                  chord_slots=_slots(prog), mode="minor", genre="rock", bpm=120,
                  memory=mem, memory_key=("bass", "chorus"), seed=1)
    apply_groove_memory(bars("E"), key="E", **common)
    out, report = apply_groove_memory(bars("F#"), key="F#", **common)
    assert report["recalled"]
    cm = ChordMap(_slots(prog), "F#", "minor")
    for e in out:
        b = int(e.start_beat // 4)
        if b % 4 != 3:
            assert e.pitch % 12 == cm.at(b * 4.0).root_pc, (b, e.pitch)


def test_extreme_register_stays_inside_midi():
    comp = _composer()
    ctx = _ctx("chorus", "chorus", 0, ["i", "bVII"])
    ctx.register = (100, 125)
    notes = comp.compose_lead(ctx)
    solo = comp.compose_lead(LeadContext("s", "solo", 0, True, 8, 4.0, 32.0, "E", "minor",
                                         _slots(["i"] * 8), register=(100, 125)))
    assert notes and all(0 <= n.pitch <= 127 for n in notes + solo)
    assert len({n.pitch for n in solo}) > 3            # the solo register did not collapse


def _authored(events, prog, bars=4):
    from produzre.themes.io import parse_themes_block
    import logging
    bank = parse_themes_block({"t": {"role": "melody", "events": events}}, logging.getLogger("t"))
    comp = SongComposer(seed=1, genre="pop", key="C", mode="major", beats_per_bar=4.0,
                        melody_theme=bank.themes["t"], hook_slots=_slots(prog),
                        register=(60, 79))
    ctx = LeadContext("c", "chorus", 0, False, bars, 4.0, bars * 4.0, "C", "major",
                      _slots([prog[i % len(prog)] for i in range(bars)]), foreground="full",
                      register=(60, 79))
    return comp.compose_lead(ctx)


def test_authored_four_bar_theme_plays_intact():
    notes = _authored("1:2 2:2 3:2 4:2 5:2 6:2 7:2 1:2", ["I", "IV", "V", "I"])
    assert [n.pitch % 12 for n in notes] == [0, 2, 4, 5, 7, 9, 11, 0]
    assert [n.beat for n in notes] == [0, 2, 4, 6, 8, 10, 12, 14]


def test_authored_accidentals_survive():
    notes = _authored("1:.5 #4:.5 5:1 b7:1 5:.5 #4:.5", ["IV", "V"], bars=2)
    assert [n.pitch % 12 for n in notes[:6]] == [0, 6, 7, 10, 7, 6]


def test_section_meter_change_realigns_the_hook():
    comp = _composer()
    comp.compose_lead(_ctx("chorus", "chorus", 0, ["i", "bVII"]))
    slots = _slots(["i", "bVII"] * 2, bpb=3.0)
    ctx = LeadContext("c34", "chorus", 1, False, 4, 3.0, 12.0, "E", "minor", slots,
                      foreground="full", register=(60, 79))
    notes = comp.compose_lead(ctx)
    assert notes and all(n.beat < 12.0 for n in notes)
    starts = sorted(n.beat for n in notes)
    assert all(b - a > 0.05 for a, b in zip(starts, starts[1:]))   # no overlapping lines


def test_one_bar_chorus_is_a_single_line():
    comp = _composer()
    notes = comp.compose_lead(_ctx("c", "chorus", 0, ["i"], bars=1))
    starts = [n.beat for n in notes]
    assert notes and starts == sorted(set(starts)) and max(starts) < 4.0
