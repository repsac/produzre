"""Tests for produzre.engine.lead_gtr.phrasing.develop_motif."""

import random

from produzre.engine.lead_gtr.phrasing import Motif, make_motif, develop_motif


def _make_base_motif(seed=42):
    return make_motif(random.Random(seed), intensity=0.5)


class TestDevelopMotifIdentity:
    def test_phrase_zero_returns_original(self):
        motif = _make_base_motif()
        result = develop_motif(motif, random.Random(1), phrase_index=0)
        assert result.intervals == motif.intervals
        assert result.durations == motif.durations

    def test_empty_intervals_returns_original(self):
        motif = Motif(intervals=(), durations=())
        result = develop_motif(motif, random.Random(1), phrase_index=3)
        assert result.intervals == ()


class TestDevelopMotifVariation:
    def test_later_phrase_differs(self):
        base = _make_base_motif()
        rng = random.Random(99)
        variations = set()
        for i in range(1, 8):
            m = develop_motif(base, random.Random(rng.randint(0, 10000)), phrase_index=i, total_phrases=8)
            variations.add(m.intervals)
        assert len(variations) > 1, "Expected at least some variation across phrases"

    def test_preserves_length(self):
        base = _make_base_motif()
        for i in range(1, 5):
            m = develop_motif(base, random.Random(i), phrase_index=i, total_phrases=5)
            assert len(m.intervals) == len(base.intervals)
            assert len(m.durations) == len(base.durations)


class TestFinalPhraseResolution:
    def test_final_phrase_last_interval_near_zero(self):
        base = _make_base_motif()
        resolved_count = 0
        for seed in range(50):
            m = develop_motif(
                base, random.Random(seed),
                phrase_index=3, is_final_phrase=True, total_phrases=4,
            )
            if abs(m.intervals[-1]) <= 2:
                resolved_count += 1
        assert resolved_count > 25, "Final phrase should resolve most of the time"


class TestProgressScaling:
    def test_more_variation_at_higher_progress(self):
        base = _make_base_motif()
        early_diffs = 0
        late_diffs = 0
        trials = 100
        for seed in range(trials):
            early = develop_motif(base, random.Random(seed), phrase_index=1, total_phrases=8)
            late = develop_motif(base, random.Random(seed), phrase_index=7, total_phrases=8)
            if early.intervals != base.intervals:
                early_diffs += 1
            if late.intervals != base.intervals:
                late_diffs += 1
        assert late_diffs >= early_diffs, "Later phrases should vary at least as much as early ones"
