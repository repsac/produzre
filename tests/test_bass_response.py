"""Bass responses: the bass answers the lead's holes with the hook's rhythm."""
import yaml

from produzre.composer.bass_response import align_to_kicks, lead_holes, phrase_holes, respond
from produzre.composer.cells import cell_from
from produzre.composer.theory import ChordMap
from produzre.melody import chord_pitch_classes
from tests.test_composer import _slots
from tests.test_groove_clock import _load_cfg, _render_timelines


def test_holes_answer_a_call_only():
    lead = [(0.0, .5), (.5, .5), (1.0, 3.0), (4.0, .5), (12.0, 4.0)]
    holes = lead_holes(lead, 16.0)
    assert (1.5, 3.75) in holes            # after the held note, before the next attack
    assert all(b - a <= 4.0 for a, b in holes)
    assert not any(a <= 8.0 < b for a, b in holes)   # an 8-beat silence is space, not a call


def test_one_answer_per_phrase_plus_the_close():
    holes = [(b * 4 + 2.5, b * 4 + 3.75) for b in range(8)]
    assert phrase_holes(holes, 4.0, 32.0) == [(14.5, 15.75), (30.5, 31.75)]


def test_answers_start_on_a_nearby_kick():
    assert align_to_kicks([(2.5, 3.75)], [0.0, 2.25, 3.5]) == [(2.25, 3.75)]
    assert align_to_kicks([(2.5, 3.75)], [0.0, 1.0]) == [(2.5, 3.75)]


def test_answer_quotes_the_hook_and_lands_on_a_chord_tone():
    hook = cell_from([.5, .5, 1.0, 2.0], [0, 2, -1, 1])
    chords = ChordMap(_slots(["i", "bVI"]), "E", "minor")
    notes = respond(hook, [(2.5, 3.75)], chords, key="E", mode="minor", reference=40)
    assert [round(n.beat - 2.5, 3) for n in notes] == [0.0, 0.5, 1.0]  # the hook's opening rhythm
    assert notes[0].pitch % 12 == 4                                    # from the chord root
    assert notes[-1].pitch % 12 in chord_pitch_classes("i", "E", "minor")
    assert all(28 <= n.pitch <= 55 for n in notes)


def _song(tmp_path, response):
    data = {"song": {"title": "Resp", "seed": 5, "genre": "rock", "key": "E", "mode": "minor"},
            "instruments": {"lead_gtr": {"params": {"foreground": "full"}},
                            "bass": {"params": {"hook_response": response}}},
            "sections": {"chorus": {"type": "chorus", "bars": 8,
                                    "harmony": {"progression": "i bVII bVI bVII"},
                                    "instruments": {"harmony": {}, "drums": {}, "bass": {},
                                                    "lead_gtr": {}}}},
            "arrangement": ["chorus", "chorus"]}
    return _load_cfg(tmp_path, yaml.safe_dump(data, sort_keys=False))


def test_bass_response_is_opt_in(tmp_path):
    off, _ = _render_timelines(_song(tmp_path, False))
    on, _ = _render_timelines(_song(tmp_path, True))
    assert not any(e.kind == "hook_response" for e in off["bass"].events)
    answers = [e for e in on["bass"].events if e.kind == "hook_response"]
    assert answers
    # Answers sit in the lead's holes, never on a lead attack.
    attacks = [e.start_beat for e in on["lead_gtr"].events if e.kind != "slide_grace"]
    assert not any(abs(a.start_beat - t) < 0.1 for a in answers for t in attacks)
    # The two choruses answer identically: the response is part of the song.
    first = [(round(e.start_beat, 3), e.pitch) for e in answers if e.start_beat < 32]
    second = [(round(e.start_beat - 32, 3), e.pitch) for e in answers if e.start_beat >= 32]
    assert [p for _, p in first] == [p for _, p in second]
