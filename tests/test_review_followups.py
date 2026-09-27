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
