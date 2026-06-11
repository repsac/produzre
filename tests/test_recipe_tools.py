"""Tests for the MIDI-analysis tooling fixes and hand-tuned recipe data
(2026-06-10 genre-authenticity pass).

Covers:
1. train_drum_recipes: GM channel-9 filter with all-channel fallback.
2. train_drum_recipes: probability hygiene (set semantics per bar, P <= 1.0,
   leading/trailing silence excluded from total_bars).
3. train_drum_recipes: dominant meter detection instead of hardcoded 4/4.
4. train_drum_recipes: --min-files wired into train_genre.
5. build_drum_manifest: word-boundary keyword matching (no "dublin" -> dub).
6. Recipe data sanity: edited recipe ids load, step indices on the 16-grid,
   dominant V7 spelling in jazz/blues/soul/rnb/latin harmony recipes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# tools/ is not a package; import by path.
TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

mido = pytest.importorskip("mido")

import build_drum_manifest  # noqa: E402
import train_drum_recipes  # noqa: E402

from produzre.config.recipes import load_recipes_for_instrument  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_midi(path: Path, notes, ticks_per_beat: int = 480, time_signature=None):
    """Write a tiny MIDI file.

    ``notes`` is a list of ``(abs_tick, pitch, velocity, channel)``.
    """
    mid = mido.MidiFile(ticks_per_beat=ticks_per_beat)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    if time_signature is not None:
        num, den = time_signature
        track.append(mido.MetaMessage("time_signature", numerator=num,
                                      denominator=den, time=0))
    last = 0
    for abs_tick, pitch, vel, ch in sorted(notes):
        track.append(mido.Message("note_on", note=pitch, velocity=vel,
                                  channel=ch, time=abs_tick - last))
        track.append(mido.Message("note_off", note=pitch, velocity=0,
                                  channel=ch, time=10))
        last = abs_tick + 10
    mid.save(str(path))
    return path


# ---------------------------------------------------------------------------
# 1. Channel filter
# ---------------------------------------------------------------------------

def test_quantize_prefers_channel_9(tmp_path):
    """Melodic notes in drum pitch ranges on other channels are ignored
    when channel 9 has note_ons."""
    # ch9: kick on beat 1; ch0: a "bass line" note at pitch 38 (snare range).
    path = _write_midi(tmp_path / "drums.mid", [
        (0, 36, 100, 9),
        (480, 38, 90, 0),   # melodic, must be ignored
        (960, 38, 90, 9),
    ])
    result = train_drum_recipes.quantize_midi(path)
    assert result is not None
    grid, _meter = result
    kick_hits = sum(len(bar) for bar in grid.get("kick", []))
    snare_hits = sum(len(bar) for bar in grid.get("snare", []))
    assert kick_hits == 1
    assert snare_hits == 1  # only the ch9 snare, not the ch0 note


def test_quantize_falls_back_without_channel_9(tmp_path):
    """When the file has zero channel-9 note_ons, all channels are scanned."""
    path = _write_midi(tmp_path / "nochannel9.mid", [
        (0, 36, 100, 0),
        (480, 38, 90, 1),
    ])
    result = train_drum_recipes.quantize_midi(path)
    assert result is not None
    grid, _meter = result
    assert sum(len(bar) for bar in grid.get("kick", [])) == 1
    assert sum(len(bar) for bar in grid.get("snare", [])) == 1


# ---------------------------------------------------------------------------
# 2. Probability hygiene
# ---------------------------------------------------------------------------

def test_step_probability_capped_at_one():
    """Multiple hits on the same (step, class) in one bar count once."""
    profile = train_drum_recipes.GrooveProfile()
    # One bar with a triple-stacked kick on step 0 (e.g. layered kit).
    profile.add_file({"kick": [[(0, 100), (0, 90), (0, 80)]]})
    assert profile.total_bars == 1
    assert profile.step_probability("kick", 0) == 1.0


def test_total_bars_excludes_leading_trailing_silence():
    """Leading/trailing empty bars don't dilute probabilities; interior
    rests between active bars still count."""
    profile = train_drum_recipes.GrooveProfile()
    bars = [
        [],            # leading silence: excluded
        [(0, 100)],    # active
        [],            # interior rest: counted
        [(0, 100)],    # active
        [],            # trailing silence: excluded
        [],
    ]
    profile.add_file({"kick": bars})
    assert profile.total_bars == 3
    assert profile.step_probability("kick", 0) == pytest.approx(2 / 3)


# ---------------------------------------------------------------------------
# 3. Meter detection
# ---------------------------------------------------------------------------

def test_quantize_reports_explicit_meter(tmp_path):
    path = _write_midi(tmp_path / "waltz.mid",
                       [(0, 36, 100, 9)], time_signature=(3, 4))
    result = train_drum_recipes.quantize_midi(path)
    assert result is not None
    _grid, meter = result
    assert meter == "3/4"


def test_quantize_reports_none_without_meter_message(tmp_path):
    path = _write_midi(tmp_path / "nometer.mid", [(0, 36, 100, 9)])
    result = train_drum_recipes.quantize_midi(path)
    assert result is not None
    _grid, meter = result
    assert meter is None


def test_derive_recipe_uses_dominant_meter():
    profile = train_drum_recipes.GrooveProfile()
    profile.add_file({"kick": [[(0, 100)]]}, time_signature="3/4")
    profile.add_file({"kick": [[(0, 100)]]}, time_signature="3/4")
    profile.add_file({"kick": [[(0, 100)]]}, time_signature="4/4")
    recipe = train_drum_recipes.derive_recipe(
        profile, genre="waltz",
        time_signature=profile.dominant_meter() or "4/4",
    )
    assert recipe["tags"]["time_signature"] == "3/4"


def test_collect_time_signature_from_manifest():
    folders = [
        {"time_signature": "6/8"},
        {"time_signature": "6/8"},
        {"time_signature": None},
        {},
    ]
    assert train_drum_recipes.collect_time_signature(folders) == "6/8"


# ---------------------------------------------------------------------------
# 4. --min-files threshold
# ---------------------------------------------------------------------------

def test_train_genre_respects_min_files(tmp_path):
    """No folders / files -> below any positive min_files -> None."""
    result = train_drum_recipes.train_genre(
        "rock", [], tmp_path, min_files=1,
    )
    assert result is None


# ---------------------------------------------------------------------------
# 5. Manifest keyword matching on word boundaries
# ---------------------------------------------------------------------------

def test_keywords_no_substring_false_positives():
    kw = build_drum_manifest.GENRE_KEYWORDS
    assert "dub" not in build_drum_manifest._match_keywords("dublin pubs", kw)
    assert "house" not in build_drum_manifest._match_keywords("warehouse loops", kw)
    assert "ska" not in build_drum_manifest._match_keywords("alaska beats", kw)


def test_keywords_exact_token_matches():
    kw = build_drum_manifest.GENRE_KEYWORDS
    assert "dub" in build_drum_manifest._match_keywords("deep dub riddims", kw)
    assert "rock" in build_drum_manifest._match_keywords("ROCK_grooves", kw)


def test_keywords_multiword_token_subsequence():
    kw = build_drum_manifest.GENRE_KEYWORDS
    found = build_drum_manifest._match_keywords("big band charts 120bpm", kw)
    assert "big_band" in found
    # Separator-insensitive: hip-hop / hip_hop / "hip hop" all tokenize alike.
    assert "hip_hop" in build_drum_manifest._match_keywords("Hip-Hop loops", kw)
    assert "hip_hop" in build_drum_manifest._match_keywords("hip hop loops", kw)


# ---------------------------------------------------------------------------
# 6. Recipe data sanity (hand-tuned 2026-06-10)
# ---------------------------------------------------------------------------

def test_tuned_drum_recipes_load_and_are_on_grid():
    recipes = load_recipes_for_instrument("drums")
    for rid in ("metal_straight", "reggae_straight", "reggae_steppers",
                "blues_shuffle", "jazz_swing", "bebop", "swing_swing",
                "bossa_nova", "funk_straight"):
        assert rid in recipes, f"missing drum recipe {rid}"
        groove = recipes[rid]["groove"]
        for key in ("kick_base", "snare_backbeat_steps", "ghost_steps"):
            for step in groove.get(key, []):
                assert 0 <= int(step) <= 15, f"{rid}.{key} step {step} off grid"
        for key in ("kick_extra_rate", "double_kick_rate", "ghost_rate",
                    "open_hat_rate", "crash_phrase_end_rate"):
            v = groove.get(key)
            if v is not None:
                assert 0.0 <= float(v) <= 1.0, f"{rid}.{key}={v} out of range"


def test_reggae_one_drop_avoids_beat_one():
    recipes = load_recipes_for_instrument("drums")
    one_drop = recipes["reggae_straight"]["groove"]
    assert 0 not in one_drop["kick_base"]
    assert 8 in one_drop["kick_base"]
    steppers = recipes["reggae_steppers"]["groove"]
    assert steppers["kick_base"] == [0, 4, 8, 12]


def test_shuffle_and_swing_recipes_have_audible_swing():
    recipes = load_recipes_for_instrument("drums")
    for rid in ("blues_shuffle", "jazz_swing", "bebop", "swing_swing"):
        swing = float(recipes[rid]["params"]["swing"])
        assert swing >= 0.6, f"{rid} swing {swing} is inaudible"


def test_tuned_bass_recipes_load():
    recipes = load_recipes_for_instrument("bass")
    assert recipes["punk"]["params"]["root_bias"] >= 0.85
    assert recipes["punk"]["params"]["rest_rate"] <= 0.1
    assert recipes["jazz"]["params"]["rhythm_pattern"] == "walking"
    assert recipes["reggae"]["params"]["rest_rate"] >= 0.3
    assert recipes["blues"]["params"]["swing"] >= 0.5
    assert recipes["metal"]["params"]["articulation_style"] == "pick"
    assert recipes["classical"]["params"]["lock_to_kick"] == 0.0


def test_dominant_harmony_recipes_spell_v7():
    recipes = load_recipes_for_instrument("harmony")
    for rid in ("jazz", "blues", "soul", "rnb", "latin"):
        progs = recipes[rid]["progressions"]
        for mode, sections in progs.items():
            for section, chords in sections.items():
                assert "V" not in chords, (
                    f"harmony/{rid} {mode}.{section} uses plain V; "
                    "dominants must be spelled V7"
                )
