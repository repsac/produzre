"""Regression tests for verified drums-engine bug fixes (2026-06-10 review).

Covers:
1. Transition pickups are spaced one 16th-note step apart (not 64ths).
2. Limb constraints never let more than max_hand_hits simultaneous hand hits
   through, even when the total hit count is within hand+foot budget.
3. Ornament accent "boost" makes flams MORE likely on accented snares.

All tests use seeded RNGs for determinism.
"""

from __future__ import annotations

import random

from produzre.engine.drums.constraints import apply_constraints
from produzre.engine.drums.ornaments import add_ornaments
from produzre.engine.drums.patterns.kit import DrumEvent, _apply_transition_effects


PITCHES = {
    "kick": 36,
    "snare": 38,
    "hat_closed": 42,
    "hat_open": 46,
    "hat_pedal": 44,
    "ride": 51,
    "ride_bell": 53,
    "crash": 49,
    "splash": 55,
    "china": 52,
    "tom_high": 50,
    "tom_mid": 47,
    "tom_low": 45,
}


# ---------------------------------------------------------------------------
# Fix 1: pickup hits spaced one 16th apart (sb is already one 16th step)
# ---------------------------------------------------------------------------

def test_transition_pickups_are_16th_spaced():
    """Pickup hits before a section change must land on the 16th grid.

    Regression: the pickup code divided the 16th-note step by 4 again,
    producing 64th-note machine-gun pickups.
    """
    beats_per_bar = 4.0
    total_beats = 16.0
    sb = beats_per_bar / 16.0  # one 16th-note step = 0.25 beats

    ctx = {
        "section_type": "verse",
        "prev_section_type": None,
        "next_section_type": "chorus",
        "is_first_section": True,
        "pickup_rate": 1.0,   # always place a pickup
        "downbeat_rate": 0.0,
        # Energy lift >= 0.35 avoids the "stop_time" style (which intentionally
        # skips every other hit), so spacing must be exactly one 16th.
        "current_energy": 0.4,
        "prev_energy": 0.4,
        "next_energy": 0.9,
    }

    found_multi_hit_pickup = False
    for seed in range(10):
        rng = random.Random(seed)
        events = _apply_transition_effects(
            events=[],
            transition_context=ctx,
            total_beats=total_beats,
            sb=sb,
            base_velocity=72,
            accent_strength=0.1,
            rng=rng,
            pitches=PITCHES,
        )
        pickups = sorted(
            (e for e in events if e.kind in ("snare_pickup", "tom_pickup", "kick_pickup")),
            key=lambda e: e.beat,
        )
        if len(pickups) < 2:
            continue
        found_multi_hit_pickup = True
        for a, b in zip(pickups, pickups[1:]):
            diff = b.beat - a.beat
            # One 16th apart, allowing for the +/-0.004 micro-timing jitter.
            assert abs(diff - sb) < 0.02, (
                f"seed={seed}: pickup hits spaced {diff:.4f} beats apart, "
                f"expected one 16th step ({sb:.4f})"
            )
    assert found_multi_hit_pickup, "expected at least one multi-hit pickup across seeds"


# ---------------------------------------------------------------------------
# Fix 3: limb constraints partition by limb before the early-out
# ---------------------------------------------------------------------------

def test_constraints_limit_simultaneous_hand_hits():
    """4 simultaneous hand hits must be reduced to max_hand_hits.

    Regression: the early-out compared the TOTAL hit count to
    max_hand_hits + max_foot_hits, so 4 hand hits (and 0 foot hits)
    slipped through unfiltered.
    """
    beat = 1.0
    # Four hand-played voices on the exact same step, zero foot hits.
    events = [
        DrumEvent(beat=beat, duration_beats=0.25, pitch=PITCHES["snare"], velocity=100, kind=""),
        DrumEvent(beat=beat, duration_beats=0.25, pitch=PITCHES["tom_high"], velocity=90, kind=""),
        DrumEvent(beat=beat, duration_beats=0.25, pitch=PITCHES["crash"], velocity=95, kind=""),
        DrumEvent(beat=beat, duration_beats=0.25, pitch=PITCHES["hat_closed"], velocity=70, kind=""),
    ]

    max_hand_hits = 2
    filtered = apply_constraints(
        events,
        beats_per_bar=4.0,
        max_hand_hits=max_hand_hits,
        max_foot_hits=2,
        fill_duck_hats=False,  # isolate the limb-budget logic
    )

    hand_pitches = {
        PITCHES["snare"],
        PITCHES["tom_high"],
        PITCHES["crash"],
        PITCHES["hat_closed"],
    }
    hand_hits = [e for e in filtered if e.pitch in hand_pitches]
    assert len(hand_hits) <= max_hand_hits, (
        f"{len(hand_hits)} simultaneous hand hits survived constraints "
        f"(max_hand_hits={max_hand_hits})"
    )
    # Highest-priority hits (crash accent, snare) should be the survivors.
    surviving_pitches = {e.pitch for e in hand_hits}
    assert PITCHES["hat_closed"] not in surviving_pitches, (
        "low-priority hat timekeep hit should be dropped first"
    )


def test_constraints_keep_within_budget_untouched():
    """Hits within each limb budget pass through unchanged."""
    beat = 0.0
    events = [
        DrumEvent(beat=beat, duration_beats=0.25, pitch=PITCHES["snare"], velocity=100, kind=""),
        DrumEvent(beat=beat, duration_beats=0.25, pitch=PITCHES["crash"], velocity=95, kind=""),
        DrumEvent(beat=beat, duration_beats=0.25, pitch=PITCHES["kick"], velocity=100, kind=""),
    ]
    filtered = apply_constraints(events, beats_per_bar=4.0, fill_duck_hats=False)
    assert len(filtered) == 3, "classic kick+snare+crash accent must survive"


# ---------------------------------------------------------------------------
# Fix 7: accents increase (not decrease) ornament probability
# ---------------------------------------------------------------------------

def _count_flams(velocity: int, n_events: int, flam_rate: float, seed: int) -> int:
    """Count flam grace notes added to n_events snares of a given velocity."""
    # Snares on bar downbeats (beat % 4 == 0): not backbeats, well spaced.
    events = [
        DrumEvent(beat=float(i) * 4.0, duration_beats=0.25, pitch=38, velocity=velocity, kind="snare")
        for i in range(n_events)
    ]
    out = add_ornaments(
        events=events,
        rng=random.Random(seed),
        pitches=PITCHES,
        choke_rate=0.0,
        flam_rate=flam_rate,
        drag_rate=0.0,
        persona="tight",
        beats_per_bar=4.0,
    )
    return sum(1 for e in out if e.kind == "flam_grace")


def test_accent_increases_flam_probability():
    """Accented snares (vel >= 80) must get MORE flams than soft snares.

    Regression: the accent "boost" multiplied the random draw UP instead of
    scaling the threshold, making ornaments LESS likely on accents.
    """
    n = 400
    flam_rate = 0.4
    accent_flams = _count_flams(velocity=100, n_events=n, flam_rate=flam_rate, seed=1234)
    soft_flams = _count_flams(velocity=70, n_events=n, flam_rate=flam_rate, seed=1234)

    # Expected ~0.6 * n for accents (0.4 * 1.5) vs ~0.4 * n for soft hits.
    assert accent_flams > soft_flams, (
        f"accents got fewer flams ({accent_flams}) than soft hits ({soft_flams})"
    )
    assert 0.50 * n < accent_flams < 0.70 * n, f"accent flam count {accent_flams} out of range"
    assert 0.30 * n < soft_flams < 0.50 * n, f"soft flam count {soft_flams} out of range"


def test_backbeat_detection_uses_tolerance():
    """Slightly off-grid backbeat snares still count as backbeats (boost applies)."""
    n = 400
    flam_rate = 0.4

    def count(offset: float, seed: int = 99) -> int:
        # Snares near beat 2 of each bar (beat_in_bar == 1.0), slightly jittered.
        events = [
            DrumEvent(
                beat=float(i) * 4.0 + 1.0 + offset,
                duration_beats=0.25,
                pitch=38,
                velocity=70,  # below accent threshold: isolates the backbeat boost
                kind="snare",
            )
            for i in range(n)
        ]
        out = add_ornaments(
            events=events,
            rng=random.Random(seed),
            pitches=PITCHES,
            choke_rate=0.0,
            flam_rate=flam_rate,
            drag_rate=0.0,
            persona="tight",
            beats_per_bar=4.0,
        )
        return sum(1 for e in out if e.kind == "flam_grace")

    # Backbeat boost is 1.2 => expected rate ~0.48 on (jittered) backbeats
    # vs ~0.40 well away from any backbeat.
    jittered_backbeat_flams = count(offset=0.01)
    non_backbeat_flams = count(offset=-1.0)  # lands on bar downbeats
    assert jittered_backbeat_flams > non_backbeat_flams, (
        f"jittered backbeat snares got {jittered_backbeat_flams} flams vs "
        f"{non_backbeat_flams} off-backbeat — tolerance-based backbeat "
        "detection is not applying the boost"
    )


if __name__ == "__main__":
    test_transition_pickups_are_16th_spaced()
    print("ok: test_transition_pickups_are_16th_spaced")
    test_constraints_limit_simultaneous_hand_hits()
    print("ok: test_constraints_limit_simultaneous_hand_hits")
    test_constraints_keep_within_budget_untouched()
    print("ok: test_constraints_keep_within_budget_untouched")
    test_accent_increases_flam_probability()
    print("ok: test_accent_increases_flam_probability")
    test_backbeat_detection_uses_tolerance()
    print("ok: test_backbeat_detection_uses_tolerance")
