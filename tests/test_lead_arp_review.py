"""Lead guitar and arpeggiator fixes from the examples review (2026-09-26).

Findings 7, 8 (lead part), 15 (lead part), 16, 17, 18 and 26 in
docs/reviews/2026-09-26-examples-findings.md. Every test pins a musical
property over several seeds, genres or settings, not exact notes.
"""
from __future__ import annotations

import collections
import logging
import random
from types import SimpleNamespace as NS

import pytest
import yaml

from produzre.composer.lead import LeadContext, SongComposer, _solo_top
from produzre.composer.theory import scale_pcs, tonic_pc
from produzre.engine.lead_gtr.register import get_register_bounds
from produzre.timeline import InstrumentTimeline
from tests.test_groove_clock import _load_cfg, _render_timelines

logger = logging.getLogger(__name__)


def _slots(prog, bpb=4.0):
    return [NS(numeral=n, start_beat=i * bpb, end_beat=(i + 1) * bpb, index=i)
            for i, n in enumerate(prog)]


def _song(tmp_path, lead=None, *, sections=None, arrangement=None, name="song.yaml", **song):
    inst = {"harmony": {}, "drums": {}, "bass": {}, "lead_gtr": {}}
    data = {
        "song": {"title": "LeadReview", "seed": 21, "genre": "rock", "key": "E", "mode": "minor",
                 **song},
        "instruments": {"lead_gtr": lead or {}},
        "sections": sections or {
            "verse": {"type": "verse", "bars": 8, "harmony": {"progression": "i bVI bIII bVII"},
                      "instruments": dict(inst)},
            "chorus": {"type": "chorus", "bars": 8, "harmony": {"progression": "i bVII bVI bVII"},
                       "instruments": dict(inst)},
        },
        "arrangement": arrangement or ["verse", "chorus", "verse", "chorus"],
    }
    return _load_cfg(tmp_path, yaml.safe_dump(data, sort_keys=False), name)


def _by_section(timelines, result, inst="lead_gtr"):
    events = sorted(timelines[inst].events, key=lambda e: e.start_beat)
    out = []
    for st in result.section_timings:
        out.append((st, [e for e in events
                         if st.start_beat - 0.1 <= e.start_beat < st.end_beat - 0.1]))
    return out


# --- 7: register forms ---------------------------------------------------------

def test_register_bounds_accept_names_and_ranges():
    assert get_register_bounds([62, 81]) == (62, 81)
    assert get_register_bounds((81, 62)) == (62, 81)          # order does not matter
    assert get_register_bounds([-5, 200]) == (0, 127)         # clamped to MIDI
    assert get_register_bounds(" High ") == get_register_bounds("high")
    assert get_register_bounds([60]) == get_register_bounds("mid")  # malformed -> default
    assert get_register_bounds(None) == get_register_bounds("mid")


@pytest.mark.parametrize("composer", [True, False])
@pytest.mark.parametrize("form", ["field", "params", "reversed"])
def test_numeric_register_works_in_every_form(tmp_path, form, composer):
    reg = [81, 62] if form == "reversed" else [62, 81]
    lead = {"register": reg} if form != "params" else {"params": {"register": reg}}
    lead.setdefault("params", {})["composer"] = composer
    for seed in (3, 21):
        timelines, _ = _render_timelines(_song(tmp_path, lead, seed=seed, name=f"s{seed}.yaml"))
        # Section-boundary pickups come from the shared transition pass.
        pitches = [e.pitch for e in timelines["lead_gtr"].events
                   if e.kind not in ("slide_grace", "pickup_transition")]
        assert pitches and all(62 <= p <= 81 for p in pitches), (form, composer, seed)


def test_named_register_is_case_insensitive_on_both_paths(tmp_path):
    for composer in (True, False):
        got = []
        for name in ("high", "HIGH "):
            lead = {"register": name, "params": {"composer": composer}}
            timelines, _ = _render_timelines(_song(tmp_path, lead, name=f"{composer}{len(name)}.yaml"))
            got.append([(round(e.start_beat, 3), e.pitch) for e in timelines["lead_gtr"].events])
        assert got[0] == got[1]


# --- 15: bend_rate over its whole range ----------------------------------------

def _performed_bends(bend_rate, notes):
    from produzre.engine.lead_gtr import _perform_composed

    tl = InstrumentTimeline(instrument="lead_gtr")
    _perform_composed(notes, timeline=tl, section_start_beat=0.0, base_vel=90, intensity=0.8,
                      solo=False, rng=random.Random(4), bpm=120.0, beats_per_bar=4.0,
                      vibrato_rate=0.0, dive_rate=0.0, swell_rate=0.0, bend_rate=bend_rate,
                      scale_pcs=set(scale_pcs("E", "minor")))
    return {round(e.start_beat * 4) / 4: e for e in tl.events
            if e.expression and "bend_in" in e.expression}


def _lead_notes(n=64, seed=0):
    r = random.Random(seed)
    notes, t = [], 0.0
    for _ in range(n):
        dur = r.choice((0.25, 0.5, 1.0, 1.5))
        notes.append({"beat": t, "duration_beats": dur, "pitch": r.choice((64, 67, 69, 71, 74)),
                      "tech": "bend2" if r.random() < 0.1 else None,
                      "role": r.choice(("melody", "lick", "counter", "stab"))})
        t += dur + 0.25
    return notes


@pytest.mark.parametrize("seed", range(4))
def test_bend_rate_scales_bends_across_its_range(seed):
    notes = _lead_notes(seed=seed)
    composed = {n["beat"] for n in notes if n["tech"]}
    eligible = {n["beat"] for n in notes if n["tech"] is None and n["duration_beats"] >= 0.5
                and n["role"] != "stab"}
    counts = [len(_performed_bends(rate, notes)) for rate in (0.0, 0.08, 0.15, 0.4, 0.7, 1.0)]
    assert counts[0] == 0
    assert counts == sorted(counts)                      # more rate, more bends
    assert set(_performed_bends(0.15, notes)) == composed  # the default plays what was written
    at_one = set(_performed_bends(1.0, notes))
    assert at_one == composed | eligible                  # every eligible note at 1
    assert counts[4] > counts[2]


def test_added_bends_leave_short_notes_and_stabs_alone():
    notes = _lead_notes(seed=9)
    bent = _performed_bends(1.0, notes)
    for n in notes:
        if n["tech"] is None and (n["duration_beats"] < 0.5 or n["role"] == "stab"):
            assert n["beat"] not in bent


# --- 16: lead seeds re-roll the composed lead ----------------------------------

def _composer(seed=7, genre="rock", **kw):
    return SongComposer(seed=seed, genre=genre, key="E", mode="minor", beats_per_bar=4.0,
                        hook_slots=_slots(["i", "bVII"]), verse_slots=_slots(["i", "bVI"]),
                        register=(60, 79), **kw)


def _ctx(sid, stype, occ, prog, *, final=False, fg="full", bars=8, **kw):
    slots = _slots([prog[i % len(prog)] for i in range(bars)])
    return LeadContext(sid, stype, occ, final, bars, 4.0, bars * 4.0, "E", "minor", slots,
                       foreground=fg, register=(60, 79), **kw)


@pytest.mark.parametrize("song_seed", [1, 7, 21])
def test_part_seed_keeps_the_hook_and_rerolls_the_rest(song_seed):
    comp = _composer(seed=song_seed)
    rerolled = [comp.part_dna(s) for s in (101, 202, 303)]
    for dna in rerolled:
        assert dna.hook is comp.dna.hook and dna.hook_answer is comp.dna.hook_answer
    banks = {tuple(l.name for l in d.licks) for d in rerolled}
    assert len(banks | {tuple(l.name for l in comp.dna.licks)}) >= 3


@pytest.mark.parametrize("song_seed", [1, 7, 21])
def test_lead_seed_rerolls_fills_but_keeps_hook_statements(song_seed):
    prog = ["i", "bVI", "bIII", "bVII"]
    plain, seeded = _composer(seed=song_seed), _composer(seed=song_seed)
    intro = [plain.compose_lead(_ctx("intro", "intro", 0, prog, bars=4)),
             seeded.compose_lead(_ctx("intro", "intro", 0, prog, bars=4, seed=99))]
    assert [(n.beat, n.pitch) for n in intro[0]] == [(n.beat, n.pitch) for n in intro[1]]
    differs = 0
    for fg in ("auto", "full"):
        a = plain.compose_lead(_ctx("v", "verse", 0, prog, fg=fg))
        b = seeded.compose_lead(_ctx("v", "verse", 0, prog, fg=fg, seed=99))
        differs += [(n.beat, n.pitch) for n in a] != [(n.beat, n.pitch) for n in b]
    assert differs == 2


def test_instrument_and_section_seeds_reach_the_composed_lead(tmp_path):
    def sections(timelines, result):
        return [[(round(e.start_beat - st.start_beat, 1), e.pitch) for e in evs]
                for st, evs in _by_section(timelines, result)]

    base = sections(*_render_timelines(_song(tmp_path, {"params": {"foreground": "auto"}})))
    inst = sections(*_render_timelines(_song(tmp_path, {"seed": 5, "params": {"foreground": "auto"}},
                                             name="i.yaml")))
    assert base[0] != inst[0]            # the verse fills are the seed's own
    data_cfg = _song(tmp_path, {"params": {"foreground": "auto"}}, name="s.yaml")
    data_cfg.sections["verse"].seed = 9
    sec = sections(*_render_timelines(data_cfg))
    assert base[0] != sec[0]
    assert base[1] == sec[1]             # the chorus is not the seeded section


# --- 17: final chorus lift with an authored melody -----------------------------

def _authored_composer(events, prog, register=(60, 79)):
    from produzre.themes.io import parse_themes_block

    bank = parse_themes_block({"t": {"role": "melody", "events": events}}, logging.getLogger("t"))
    return SongComposer(seed=1, genre="pop", key="C", mode="major", beats_per_bar=4.0,
                        melody_theme=bank.themes["t"], hook_slots=_slots(prog), register=register)


_THEMES = ["5:.5 6:.5 5:1 3:1 2:1 1:2 2:1 3:1", "1:1 3:1 5:1 3:1 2:2 1:2", "3:.5 4:.5 5:2 6:1 5:4"]


@pytest.mark.parametrize("events", _THEMES)
def test_authored_final_chorus_lifts_an_octave_and_keeps_the_line(events):
    prog = ["I", "V", "vi", "IV"]
    comp = _authored_composer(events, prog)
    runs = []
    for occ, final in ((0, False), (1, False), (2, True)):
        ctx = LeadContext("c", "chorus", occ, final, 8, 4.0, 32.0, "C", "major",
                          _slots([prog[i % 4] for i in range(8)]), foreground="full",
                          register=(60, 79))
        runs.append(comp.compose_lead(ctx))
    first, second, last = runs
    assert [(n.beat, n.pitch) for n in first] == [(n.beat, n.pitch) for n in second]
    assert [n.beat for n in last] == [n.beat for n in first]
    assert any(n.tech == "vib" for n in last)
    if max(n.pitch for n in first) + 12 <= _solo_top(60, 79):
        assert [n.pitch + 12 for n in first] == [n.pitch for n in last]
        assert "lifted an octave" in comp.log[-1]
    else:  # the octave would leave the neck: the line keeps its notes
        assert [n.pitch for n in first] == [n.pitch for n in last]
        assert "does not fit" in comp.log[-1]


def test_most_authored_final_choruses_lift():
    prog = ["I", "V", "vi", "IV"]
    lifted = 0
    for events in _THEMES:
        comp = _authored_composer(events, prog)
        for occ, final in ((0, False), (1, True)):
            comp.compose_lead(LeadContext("c", "chorus", occ, final, 8, 4.0, 32.0, "C", "major",
                                          _slots([prog[i % 4] for i in range(8)]),
                                          foreground="full", register=(60, 79)))
        lifted += "lifted an octave" in comp.log[-1]
    assert lifted >= 2


@pytest.mark.parametrize("events", _THEMES)
def test_authored_final_chorus_embellishes_when_the_register_is_full(events):
    prog = ["I", "V", "vi", "IV"]
    comp = _authored_composer(events, prog, register=(60, 72))
    runs = []
    for occ, final in ((0, False), (1, True)):
        ctx = LeadContext("c", "chorus", occ, final, 8, 4.0, 32.0, "C", "major",
                          _slots([prog[i % 4] for i in range(8)]), foreground="full",
                          register=(60, 72), strict_register=True)
        runs.append(comp.compose_lead(ctx))
    first, last = runs
    assert [(n.beat, n.pitch) for n in first] == [(n.beat, n.pitch) for n in last]
    assert sum(n.tech in ("vib", "slide") for n in last) > sum(n.tech in ("vib", "slide")
                                                              for n in first)
    assert "does not fit" in comp.log[-1]


@pytest.mark.parametrize("events", _THEMES)
def test_authored_modulated_final_chorus_rises_by_the_key_change(events):
    prog = ["I", "V", "vi", "IV"]
    comp = _authored_composer(events, prog)
    runs = []
    for occ, final, key in ((0, False, "C"), (1, True, "D")):
        ctx = LeadContext("c", "chorus", occ, final, 8, 4.0, 32.0, key, "major",
                          _slots([prog[i % 4] for i in range(8)]), foreground="full",
                          register=(60, 79))
        runs.append(comp.compose_lead(ctx))
    first, last = runs
    mean = lambda ns: sum(n.pitch for n in ns) / len(ns)
    assert 0.5 <= mean(last) - mean(first) <= 3.5          # up a step, not down or an octave
    offs = scale_pcs("D", "major")
    assert all(n.pitch % 12 in offs for n in last)
    assert "key change" in comp.log[-1]


def test_authored_choruses_before_the_last_keep_the_written_notes(tmp_path):
    sections = {
        "verse": {"type": "verse", "bars": 4, "harmony": {"progression": "I IV V I"},
                  "instruments": {"harmony": {}, "lead_gtr": {}}},
        "chorus": {"type": "chorus", "bars": 4, "harmony": {"progression": "I V vi IV"},
                   "instruments": {"harmony": {}, "lead_gtr": {}}},
    }
    cfg = _load_cfg(tmp_path, yaml.safe_dump({
        "song": {"title": "A", "seed": 3, "genre": "pop", "key": "C", "mode": "major"},
        "themes": {"hook": {"role": "melody", "events": _THEMES[0]}},
        "instruments": {"lead_gtr": {"params": {"foreground": "full"}}},
        "sections": sections,
        "arrangement": ["verse", "chorus", "verse", "chorus", "chorus"],
    }, sort_keys=False))
    timelines, result = _render_timelines(cfg)
    choruses = [[e.pitch for e in evs if e.kind != "slide_grace"]
                for st, evs in _by_section(timelines, result) if st.type == "chorus"]
    assert choruses[0] == choruses[1]
    assert choruses[2] == [p + 12 for p in choruses[0]]


# --- 8: chorus forms under a singer ---------------------------------------------

def _sung(bars=8, prog=("i", "bVII", "bVI", "bVII")):
    """A singer's line: six quarter notes, then a held note, per two bars."""
    line = []
    pitches = (71, 74, 71, 69, 67, 69, 71)
    for bar in range(0, bars, 2):
        t = bar * 4.0
        for k, p in enumerate(pitches[:-1]):
            line.append((t + k, 1.0, p))
        line.append((t + 6.0, 2.0, pitches[-1]))
    return tuple(line)


def _auto_chorus(form=None, counter=None, seed=7, **ctx_kw):
    pins = {k: v for k, v in (("chorus_form", form), ("counter", counter)) if v}
    comp = _composer(seed=seed, arrangement_overrides=pins)
    prog = ["i", "bVII", "bVI", "bVII"]
    ctx = _ctx("c", "chorus", 0, prog, fg="auto", melody=ctx_kw.pop("melody", _sung()), **ctx_kw)
    return comp, comp.compose_lead(ctx)


@pytest.mark.parametrize("seed", [1, 7, 21])
@pytest.mark.parametrize("counter", [None, "guide", "stabs", "fills"])
def test_anthem_harmonizes_the_singer(seed, counter):
    _, notes = _auto_chorus("anthem", counter, seed)
    body = [n for n in notes if n.beat < 24.0]
    sung = {b: p for b, _, p in _sung()}
    assert body and all(n.role == "harmony" for n in body)
    assert all(n.beat in sung for n in body)
    thirds_sixths = sum((n.pitch - sung[n.beat]) % 12 in (3, 4, 8, 9) for n in body)
    assert thirds_sixths >= 0.8 * len(body)
    assert all(n.pitch != sung[n.beat] for n in body)    # a second voice, never a unison


@pytest.mark.parametrize("seed", [1, 7, 21])
@pytest.mark.parametrize("counter", [None, "guide", "octaves", "stabs", "fills"])
def test_call_answers_in_the_singers_holds(seed, counter):
    _, notes = _auto_chorus("call", counter, seed)
    body = [n for n in notes if n.beat < 24.0]
    assert body
    for n in body:
        # Only inside a held note after it has landed (beats 6.5-8 of each line).
        assert 6.5 - 1e-6 <= n.beat % 8.0 < 8.0, n
    lines = {int(n.beat // 8) for n in body}
    assert len(lines) >= 2


@pytest.mark.parametrize("seed", [1, 7, 21])
@pytest.mark.parametrize("counter", [None, "guide", "octaves", "stabs", "fills"])
def test_lift_climbs_line_by_line(seed, counter):
    _, notes = _auto_chorus("lift", counter, seed)
    body = [n for n in notes if n.beat < 24.0]
    lines = [[n.pitch for n in body if int(n.beat // 8) == u] for u in range(3)]
    assert all(lines)
    means = [sum(l) / len(l) for l in lines]
    assert means[-1] > means[0]
    assert max(lines[-1]) >= max(lines[0])


def test_pinned_counter_with_drawn_form_keeps_the_plain_counter():
    for seed in (1, 7, 21):
        comp, notes = _auto_chorus(None, "guide", seed)
        plain = [n for n in notes if n.beat < 24.0]
        assert plain and all(n.role == "counter" for n in plain)


def test_chorus_form_shapes_auto_choruses_in_a_song(tmp_path):
    kinds = {}
    for form in ("anthem", "call", "lift"):
        cfg = _song(tmp_path, {"params": {"foreground": "auto"}}, name=f"{form}.yaml",
                    arrangement_style={"chorus_form": form})
        timelines, result = _render_timelines(cfg)
        chorus = next(evs for st, evs in _by_section(timelines, result) if st.type == "chorus")
        kinds[form] = collections.Counter(e.kind.split("_")[0] for e in chorus)
    assert kinds["anthem"]["harmony"] > 0
    assert kinds["call"]["lick"] > 0 and not kinds["call"]["counter"]
    assert kinds["lift"]["counter"] > 0
    assert len({tuple(sorted(k.items())) for k in kinds.values()}) == 3


# --- 18: solo stories -----------------------------------------------------------

_TWELVE = ["I7", "IV7", "I7", "I7", "IV7", "IV7", "I7", "I7", "V7", "IV7", "I7", "V7"]


def _solo(comp, occ, *, prev="verse", nxt="verse"):
    ctx = LeadContext("solo", "solo", occ, False, 12, 4.0, 48.0, "A", "major", _slots(_TWELVE),
                      foreground="auto", register=(60, 79), prev_section_type=prev,
                      next_section_type=nxt)
    return comp.compose_lead(ctx)


def _solo_composer(seed, genre, story):
    return SongComposer(seed=seed, genre=genre, key="A", mode="major", beats_per_bar=4.0,
                        hook_slots=_slots(_TWELVE[:2]), verse_slots=_slots(_TWELVE[:2]),
                        register=(60, 79), arrangement_overrides={"solo_story": story})


@pytest.mark.parametrize("genre", ["blues", "rock", "country", "jazz"])
@pytest.mark.parametrize("story", ["blues", "trade"])
def test_blues_and_trade_solos_fill_a_twelve_bar_solo(genre, story):
    for seed in range(5):
        notes = _solo(_solo_composer(seed, genre, story), 0)
        per_bar = collections.Counter(int(n.beat // 4) for n in notes)
        units = [per_bar[2 * u] + per_bar[2 * u + 1] for u in range(6)]
        assert len(notes) / 12 >= 2.5, (genre, story, seed, units)
        assert min(units) >= 4, (genre, story, seed, units)


@pytest.mark.parametrize("story", ["climb", "melodic", "trade", "blues"])
@pytest.mark.parametrize("genre", ["blues", "rock", "country"])
def test_consecutive_solos_develop(story, genre):
    for seed in range(4):
        comp = _solo_composer(seed, genre, story)
        first = _solo(comp, 0, nxt="solo")
        second = _solo(comp, 1, prev="solo")
        a = {(n.beat, n.pitch) for n in first}
        b = {(n.beat, n.pitch) for n in second}
        assert len(a & b) <= 0.5 * len(b), (story, genre, seed)
        assert not b <= a
        # The first hands over on the dominant instead of the solo's ending.
        last = first[-1]
        assert last.tech not in ("dive", "fall") and last.pitch % 12 == (tonic_pc("A") + 7) % 12


def test_country_full_lead_fills_its_phrases_with_country_licks():
    prog = ["I", "I", "IV", "I", "I", "V", "V", "I"]
    doubles_expected = doubles_found = 0
    for seed in range(8):
        comp = SongComposer(seed=seed, genre="country", key="G", mode="major", beats_per_bar=4.0,
                            hook_slots=_slots(["IV", "IV"]), verse_slots=_slots(prog[:2]),
                            register=(55, 84), arrangement_overrides={"lead_fills": "chatty"})
        ctx = LeadContext("verse", "verse", 0, False, 8, 4.0, 32.0, "G", "major", _slots(prog),
                          foreground="full", register=(55, 84))
        notes = comp.compose_lead(ctx)
        roles = collections.Counter(n.role for n in notes)
        assert roles["melody"] >= 16 and roles["country_lick"] + roles["country_double"] > 0
        fill_bars = {int(n.beat // 4) for n in notes if n.role != "melody"}
        assert fill_bars <= {1, 3, 5, 7}                 # chatty: every two bars
        if any("thirds" in l.name or "sixths" in l.name for l in comp.dna.licks):
            doubles_expected += 1
            doubles_found += roles["country_double"] > 0
    assert doubles_expected and doubles_found == doubles_expected


def test_full_lead_outside_country_keeps_the_melody_without_a_fills_pin():
    prog = ["i", "bVI", "bIII", "bVII"]
    for seed in (1, 7):
        notes = _composer(seed=seed).compose_lead(_ctx("v", "verse", 0, prog))
        assert {n.role for n in notes} == {"melody"}
        pinned = _composer(seed=seed, arrangement_overrides={"lead_fills": "normal"})
        filled = pinned.compose_lead(_ctx("v", "verse", 0, prog))
        assert {n.role for n in filled} > {"melody"}


# --- 26: arpeggiator ------------------------------------------------------------

@pytest.mark.parametrize("numeral,expected", [
    ("I", (0, 4, 7)), ("V7", (0, 4, 7, 10)), ("Imaj7", (0, 4, 7, 11)),
    ("V9", (0, 4, 7, 10, 14)), ("ii9", (0, 3, 7, 10, 14)), ("Iadd9", (0, 4, 7, 14)),
    ("I6", (0, 4, 7, 9)), ("I69", (0, 4, 7, 9, 14)), ("V13", (0, 4, 7, 10, 14, 21)),
    ("V7b9", (0, 4, 7, 10, 13)), ("ii7b5", (0, 3, 6, 10)), ("V11", (0, 7, 10, 14, 17)),
    ("IVmaj7#11", (0, 4, 7, 11, 14, 18)),
])
def test_arpeggiator_spells_sevenths_and_extensions(numeral, expected):
    from produzre.engine.arpeggiator import chord_intervals_with_extensions

    assert chord_intervals_with_extensions(numeral) == expected


class _Plan:
    """A plan whose melody guide sits far from any chord tone."""

    def get(self, key, default=None):
        if key.startswith("melody.guide"):
            return {"targets": [{"beat": float(b), "pitch": 61} for b in range(0, 16)]}
        return default


def _arp(pattern, *, intensity=0.7, prog=("Imaj7", "vi7", "ii9", "V7")):
    from produzre.engine.arpeggiator import render_into_timeline

    class Section:
        id = "verse"
        key = None
        mode = None

    tl = InstrumentTimeline(instrument="arpeggiator")
    render_into_timeline(
        cfg=NS(song=NS(key="C", mode="major")), section=Section(),
        harmony_plan=NS(chord_slots=_slots(list(prog))), rhythm_grid=NS(beats_per_bar=4.0),
        section_start_beat=0.0, timeline=tl, rng=random.Random(3), plan=_Plan(), logger=logger,
        instrument_cfg={"intensity": intensity, "extra": {"pattern": pattern}},
    )
    return sorted(tl.events, key=lambda e: e.start_beat)


@pytest.mark.parametrize("pattern", ["up", "down", "up_down", "ostinato"])
def test_fixed_arpeggio_patterns_ignore_the_melody_guide(pattern):
    from produzre.engine.arpeggiator import _get_chord_tones_from_numeral

    prog = ("Imaj7", "vi7", "ii9", "V7")
    for e in _arp(pattern, prog=prog):
        slot = int(e.start_beat // 4)
        pcs = {p % 12 for p in _get_chord_tones_from_numeral(prog[slot], "C", "major")}
        assert e.pitch % 12 in pcs


@pytest.mark.parametrize("pattern", ["phrase", "cinematic"])
def test_phrase_patterns_follow_the_melody_guide(pattern):
    events = _arp(pattern)
    assert any(e.pitch % 12 == 1 for e in events if e.kind == "arpeggio_apex")


@pytest.mark.parametrize("pattern", ["up", "down", "up_down", "ostinato", "phrase"])
def test_arpeggio_apex_is_the_top_of_its_cycle(pattern):
    events = [e for e in _arp(pattern, prog=("I", "IV", "V", "I"))]
    for slot in range(4):
        cycle = [e for e in events if slot * 4 <= e.start_beat < (slot + 1) * 4]
        apexes = [e for e in cycle if e.kind == "arpeggio_apex"]
        assert apexes
        if pattern != "phrase":                       # guided apexes may leave the chord
            assert all(a.pitch == max(e.pitch for e in cycle) for a in apexes)


def test_arpeggio_voices_the_ninth():
    events = _arp("up", prog=("V9", "V9", "V9", "V9"))
    assert {e.pitch % 12 for e in events} == {7, 11, 2, 5, 9}


@pytest.mark.parametrize("pattern", ["phrase", "up", "ostinato"])
def test_arpeggio_velocity_follows_intensity(pattern):
    means = []
    for intensity in (0.2, 0.45, 0.7, 0.95):
        vel = [e.velocity for e in _arp(pattern, intensity=intensity)]
        means.append(sum(vel) / len(vel))
    assert means == sorted(means)
    assert means[-1] - means[0] >= 40
    assert means[-1] - means[1] >= 25


def test_arpeggio_follows_section_dynamics_in_a_song(tmp_path):
    inst = {"harmony": {}, "arpeggiator": {}}
    sections = {
        "verse": {"type": "verse", "bars": 4, "harmony": {"progression": "I vi IV V"},
                  "instruments": dict(inst)},
        "chorus": {"type": "chorus", "bars": 4, "harmony": {"progression": "I V vi IV"},
                   "instruments": dict(inst)},
        "quiet": {"type": "bridge", "bars": 4, "intensity": 0.3,
                  "harmony": {"progression": "vi IV I V"}, "instruments": dict(inst)},
    }
    cfg = _load_cfg(tmp_path, yaml.safe_dump({
        "song": {"title": "Arp", "seed": 5, "genre": "pop", "key": "C", "mode": "major"},
        "instruments": {"arpeggiator": {"params": {"pattern": "phrase"}}},
        "sections": sections, "arrangement": ["verse", "chorus", "quiet"],
    }, sort_keys=False))
    timelines, result = _render_timelines(cfg)
    means = {st.id: sum(e.velocity for e in evs) / len(evs)
             for st, evs in _by_section(timelines, result, "arpeggiator")}
    assert means["chorus"] - means["verse"] >= 12        # 0.9 against 0.65
    assert means["verse"] - means["quiet"] >= 18         # 0.65 against 0.3
