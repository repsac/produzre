"""Follow-up fixes found while fixing the examples findings."""
from __future__ import annotations

import logging

import pytest
import yaml

from tests.test_groove_clock import _load_cfg, _render_timelines


def _song(persona_where: str, persona: str) -> str:
    drums = {"composer": False}
    data = {"version": 1,
            "song": {"title": "Persona", "seed": 3, "genre": "rock", "key": "E", "mode": "minor"},
            "instruments": {"drums": {"params": dict(drums)}},
            "sections": {"verse": {"type": "verse", "bars": 4,
                                   "instruments": {"drums": {}}}},
            "arrangement": ["verse"]}
    if persona_where == "global":
        data["instruments"]["drums"]["persona"] = persona
    else:
        data["sections"]["verse"]["instruments"]["drums"]["persona"] = persona
    return yaml.safe_dump(data, sort_keys=False)


@pytest.mark.parametrize("where", ["global", "section"])
@pytest.mark.parametrize("persona", ["rock", "experimental"])
def test_drum_engine_uses_the_resolved_persona(tmp_path, caplog, where, persona):
    caplog.set_level(logging.DEBUG)
    _render_timelines(_load_cfg(tmp_path, _song(where, persona)))
    rendered = [r.getMessage() for r in caplog.records if "Drums rendered" in r.getMessage()]
    assert rendered and all(f"persona={persona}" in m for m in rendered)


def test_unknown_song_section_and_top_level_keys_warn(tmp_path, caplog):
    from produzre.config.validation import unknown_structure_warnings

    raw = {"version": 1, "songs": {}, "exprts": {},
           "song": {"title": "x", "turnarounds": True, "final_chorus": "modulate",
                    "arrangement_style": {}, "turnaround": True},
           "sections": {"verse": {"type": "verse", "bars": 4, "intesity": 0.5,
                                  "meter_grouping": [2, 2]}},
           "arrangement": ["verse"]}
    messages = unknown_structure_warnings(raw)
    assert any("'turnaround'" in m and "turnarounds" in m for m in messages)
    assert any("'intesity'" in m and "intensity" in m for m in messages)
    assert any("'exprts'" in m and "exports" in m for m in messages)
    flagged = {m.split("'")[1] for m in messages}
    assert flagged == {"songs", "exprts", "turnaround", "intesity"}


def test_every_example_uses_only_known_structure_keys():
    import glob
    from produzre.config.validation import unknown_structure_warnings

    for f in glob.glob("examples/**/*.yaml", recursive=True):
        assert unknown_structure_warnings(yaml.safe_load(open(f))) == [], f


@pytest.mark.parametrize("section_type,bars", [("intro", 4), ("solo", 8), ("breakdown", 4),
                                              ("verse", 1)])
@pytest.mark.parametrize("device", ["stop", "drop", "push", "build"])
def test_drums_and_comp_agree_on_the_device_into_any_chorus(section_type, bars, device):
    from produzre.composer.arrangement import into_chorus_device
    from produzre.composer.comping import compose_comp_dna, plan_comp_section
    from produzre.composer.drums import compose_drum_dna, plan_drum_section
    from tests.test_album_diversity import _arr
    from tests.test_composer import _slots

    arr = _arr(into_chorus=device)
    assert into_chorus_device(arr, section_type, "chorus") == device
    last = (bars - 1) * 4
    comp = compose_comp_dna(seed=5, genre="rock", key="E", mode="minor", shuffle=False)
    events, _, _ = plan_comp_section(comp, section_type=section_type, occurrence=0,
                                     is_final_of_type=True, bars=bars, beats_per_bar=4.0,
                                     chord_slots=_slots(["i"] * bars), key="E", mode="minor",
                                     next_section_type="chorus", arrangement=arr)
    ordinary, _, _ = plan_comp_section(comp, section_type=section_type, occurrence=0,
                                       is_final_of_type=True, bars=bars, beats_per_bar=4.0,
                                       chord_slots=_slots(["i"] * bars), key="E", mode="minor",
                                       next_section_type="verse", arrangement=arr)
    tail = lambda evs: [(e.beat, e.kind, e.dur, e.tag) for e in evs if e.beat >= last]
    assert tail(events) != tail(ordinary)
    drums = compose_drum_dna(seed=5, genre="rock")
    hits = plan_drum_section(drums, arr, section_type=section_type, bars=bars,
                             beats_per_bar=4, next_section_type="chorus")
    plain = plan_drum_section(drums, arr, section_type=section_type, bars=bars,
                              beats_per_bar=4, next_section_type="verse")
    dtail = lambda hs: sorted((round(h.beat, 3), h.voice) for h in hs if h.beat >= last)
    assert dtail(hits) != dtail(plain)


def _note(beat, pitch):
    from types import SimpleNamespace
    return SimpleNamespace(start_beat=beat, pitch=pitch)


def test_pickup_respects_register_scale_and_meter():
    import random
    from produzre.composer.theory import ChordMap
    from produzre.orchestrate.transitions import choose_pickup_pitch
    from tests.test_composer import _slots

    chords = ChordMap(_slots(["I", "IV"]), "C", "major")
    for seed in range(20):
        rng = random.Random(seed)
        # Approaches the downbeat target from a scale step below.
        p = choose_pickup_pitch([_note(64.0, 64)], instrument="lead_gtr", rng=rng,
                                incoming_chords=chords, register=(55, 81), incoming_start=64.0)
        assert p in (62, 63) and p % 12 in (2,)  # D, the scale tone below E
        # Near the bottom of the register it approaches from above.
        p = choose_pickup_pitch([_note(64.0, 62)], instrument="lead_gtr", rng=rng,
                                incoming_chords=chords, register=(62, 81), incoming_start=64.0)
        assert 62 <= p <= 81 and p % 12 in (4, 5)
        # In 3/4 the downbeat is found on the section's own bar grid.
        p = choose_pickup_pitch([_note(64.5, 72), _note(67.0, 67)], instrument="lead_gtr",
                                rng=rng, register=(55, 81), beats_per_bar=3.0,
                                incoming_start=64.0)
        assert p in (65, 66) or p in (68, 69)
    assert choose_pickup_pitch([], instrument="lead_gtr", register=(62, 81)) is None
