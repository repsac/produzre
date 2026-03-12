"""Test bass negotiation hooks (Phase B11).

Verifies that:
1. Bass exports negotiation features (onset_map, accent_map, fill_windows_used, register_profile)
2. RhythmIntent.accent_beats affects bass accent placement
3. RhythmIntent.space_budget reduces bass density
4. Without RhythmIntent, behavior stays stable (backwards compatible)
5. Negotiation features are deterministic with same seed
"""

import subprocess
import sys
from pathlib import Path
from random import Random


def test_baseline_without_rhythm_intent():
    """Verify bass works normally without RhythmIntent (backwards compatible)."""
    yaml_path = "examples/bass/baseline/negotiation-baseline.yaml"

    result = subprocess.run(
        [sys.executable, "-m", "produzre.cli", "build", yaml_path],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Build failed: {result.stderr}"

    # Extract export root
    export_lines = [l for l in result.stderr.splitlines() if "Export root:" in l]
    assert export_lines, "No export root found"
    export_root = export_lines[0].split("Export root:")[1].strip()

    # Read TSV to verify notes were generated
    tsv_path = Path(export_root) / "analysis" / "bass" / "Negotiation_Baseline_bass.events.tsv"
    assert tsv_path.exists(), f"TSV not found: {tsv_path}"

    content = tsv_path.read_text()
    lines = content.strip().split("\n")
    note_count = len(lines) - 1  # Subtract header

    assert note_count > 0, "Bass should generate notes"

    print(f"✓ Baseline works without RhythmIntent ({note_count} notes generated)")


def test_rhythm_intent_injection():
    """Verify RhythmIntent can be injected programmatically."""
    # This test demonstrates the API but requires orchestrator-level changes
    # For now, we verify that the bass engine accepts rhythm_intent parameter
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from produzre.config.load import load_root_config
    from produzre.model import RhythmIntent
    from produzre.harmony import build_harmony_plan
    from produzre.rhythm import RhythmGrid
    from produzre.timeline import InstrumentTimeline
    from produzre.engine.bass import render_into_timeline

    # Load config
    cfg = load_root_config("examples/bass/baseline/negotiation-baseline.yaml")
    section = cfg.sections["verse1"]

    # Plan harmony
    import logging
    harmony_plan = build_harmony_plan(
        cfg=cfg,
        section=section,
        logger=logging.getLogger("test"),
    )

    # Create rhythm grid
    from produzre.harmony import parse_meter
    total_beats = section.total_beats(cfg.song.beats_per_bar)
    meter = parse_meter(section.meter or cfg.song.meter)
    rhythm_grid = RhythmGrid(meter=meter, beats_per_bar=cfg.song.beats_per_bar, total_beats=total_beats)

    # Create timeline
    timeline = InstrumentTimeline(instrument="bass")

    # Create RhythmIntent with accent beats
    rhythm_intent = RhythmIntent(
        accent_beats={0.0, 4.0, 8.0, 12.0},  # Accent on downbeats
        space_budget=None,
    )

    # Render with rhythm_intent
    rng = Random(2000)
    instrument_cfg = {"params": {
        "density": 0.8,
        "register_low": 28,
        "register_high": 52,
        "rhythm_pattern": "anchor",
        "lock_to_kick": 0.6,
        "articulation_style": "finger",
    }}

    features = render_into_timeline(
        cfg=cfg,
        section=section,
        harmony_plan=harmony_plan,
        rhythm_grid=rhythm_grid,
        section_start_beat=0.0,
        timeline=timeline,
        instrument_cfg=instrument_cfg,
        rng=rng,
        rhythm_intent=rhythm_intent,
    )

    # Verify features were returned
    assert features is not None, "Should return negotiation features"
    assert hasattr(features, "onset_map"), "Should have onset_map"
    assert hasattr(features, "accent_map"), "Should have accent_map"
    assert hasattr(features, "fill_windows_used"), "Should have fill_windows_used"
    assert hasattr(features, "register_profile"), "Should have register_profile"
    assert hasattr(features, "event_count"), "Should have event_count"

    # Verify some notes were generated
    assert features.event_count > 0, "Should generate notes"

    # Verify onset_map is populated
    assert len(features.onset_map) > 0, "Should track onsets"

    # Verify register_profile has expected fields
    assert "min_pitch" in features.register_profile
    assert "max_pitch" in features.register_profile
    assert "avg_pitch" in features.register_profile
    assert "pitch_range" in features.register_profile

    print(f"✓ RhythmIntent injection works (events={features.event_count}, "
          f"onsets={len(features.onset_map)}, accents={len(features.accent_map)})")


def test_space_budget_reduces_density():
    """Verify space_budget constraint reduces bass density."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from produzre.config.load import load_root_config
    from produzre.model import RhythmIntent
    from produzre.harmony import build_harmony_plan
    from produzre.rhythm import RhythmGrid
    from produzre.timeline import InstrumentTimeline
    from produzre.engine.bass import render_into_timeline
    from random import Random
    import logging

    # Load config
    cfg = load_root_config("examples/bass/baseline/negotiation-baseline.yaml")
    section = cfg.sections["verse1"]

    # Plan harmony
    import logging
    harmony_plan = build_harmony_plan(
        cfg=cfg,
        section=section,
        logger=logging.getLogger("test"),
    )

    # Create rhythm grid
    from produzre.harmony import parse_meter
    total_beats = section.total_beats(cfg.song.beats_per_bar)
    meter = parse_meter(section.meter or cfg.song.meter)
    rhythm_grid = RhythmGrid(meter=meter, beats_per_bar=cfg.song.beats_per_bar, total_beats=total_beats)

    instrument_cfg = {"params": {
        "density": 0.8,  # Start with high density
        "register_low": 28,
        "register_high": 52,
        "rhythm_pattern": "anchor",
        "lock_to_kick": 0.6,
        "articulation_style": "finger",
    }}

    # Render without space_budget
    timeline1 = InstrumentTimeline(instrument="bass")
    features1 = render_into_timeline(
        cfg=cfg,
        section=section,
        harmony_plan=harmony_plan,
        rhythm_grid=rhythm_grid,
        section_start_beat=0.0,
        timeline=timeline1,
        instrument_cfg=instrument_cfg,
        rng=Random(2000),
        rhythm_intent=None,
    )

    # Render with reduced space_budget
    timeline2 = InstrumentTimeline(instrument="bass")
    rhythm_intent_reduced = RhythmIntent(
        accent_beats=set(),
        space_budget=0.4,  # Reduce density to 40%
    )
    features2 = render_into_timeline(
        cfg=cfg,
        section=section,
        harmony_plan=harmony_plan,
        rhythm_grid=rhythm_grid,
        section_start_beat=0.0,
        timeline=timeline2,
        instrument_cfg=instrument_cfg,
        rng=Random(2000),
        rhythm_intent=rhythm_intent_reduced,
    )

    # Verify space_budget reduced note count
    assert features2.event_count < features1.event_count, \
        f"space_budget should reduce density ({features2.event_count} vs {features1.event_count})"

    # Space budget reduces density; exact ratio depends on engine internals.
    # Allow a wide range since sparse base density amplifies the effect.
    reduction_ratio = features2.event_count / features1.event_count
    assert 0.1 <= reduction_ratio <= 0.8, \
        f"Reduction should be noticeable, got {reduction_ratio:.1%}"

    print(f"✓ space_budget reduces density ({features1.event_count} → {features2.event_count}, "
          f"{reduction_ratio:.1%} ratio)")


def test_accent_map_with_rhythm_intent():
    """Verify RhythmIntent.accent_beats affects accent_map."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from produzre.config.load import load_root_config
    from produzre.model import RhythmIntent
    from produzre.harmony import build_harmony_plan
    from produzre.rhythm import RhythmGrid
    from produzre.timeline import InstrumentTimeline
    from produzre.engine.bass import render_into_timeline
    from random import Random
    import logging

    # Load config
    cfg = load_root_config("examples/bass/baseline/negotiation-baseline.yaml")
    section = cfg.sections["verse1"]

    # Plan harmony
    import logging
    harmony_plan = build_harmony_plan(
        cfg=cfg,
        section=section,
        logger=logging.getLogger("test"),
    )

    # Create rhythm grid
    from produzre.harmony import parse_meter
    total_beats = section.total_beats(cfg.song.beats_per_bar)
    meter = parse_meter(section.meter or cfg.song.meter)
    rhythm_grid = RhythmGrid(meter=meter, beats_per_bar=cfg.song.beats_per_bar, total_beats=total_beats)

    instrument_cfg = {"params": {
        "density": 1.0,  # Full density to ensure notes at accent beats
        "register_low": 28,
        "register_high": 52,
        "rhythm_pattern": "anchor",
        "lock_to_kick": 0.8,
        "articulation_style": "finger",
    }}

    # Render with specific accent beats
    accent_beats = {0.0, 8.0, 16.0, 24.0}  # Bar 1, 3, 5, 7 downbeats
    rhythm_intent = RhythmIntent(
        accent_beats=accent_beats,
        space_budget=None,
    )

    timeline = InstrumentTimeline(instrument="bass")
    features = render_into_timeline(
        cfg=cfg,
        section=section,
        harmony_plan=harmony_plan,
        rhythm_grid=rhythm_grid,
        section_start_beat=0.0,
        timeline=timeline,
        instrument_cfg=instrument_cfg,
        rng=Random(2000),
        rhythm_intent=rhythm_intent,
    )

    # Verify accent_map contains some of the requested accents
    # (Not all may have notes due to density/rest filtering, but some should)
    accents_found = set(features.accent_map.keys())
    overlap = accent_beats & accents_found

    assert len(overlap) > 0, \
        f"RhythmIntent accents should appear in accent_map (requested={accent_beats}, found={accents_found})"

    print(f"✓ RhythmIntent affects accent_map ({len(overlap)}/{len(accent_beats)} accents applied)")


def test_negotiation_features_deterministic():
    """Verify negotiation features are deterministic with same seed."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from produzre.config.load import load_root_config
    from produzre.model import RhythmIntent
    from produzre.harmony import build_harmony_plan
    from produzre.rhythm import RhythmGrid
    from produzre.timeline import InstrumentTimeline
    from produzre.engine.bass import render_into_timeline
    from random import Random
    import logging

    def build_and_get_features():
        cfg = load_root_config("examples/bass/baseline/negotiation-baseline.yaml")
        section = cfg.sections["verse1"]

        harmony_plan = build_harmony_plan(
            cfg=cfg,
            section=section,
            logger=logging.getLogger("test"),
        )

        total_beats = section.total_beats(cfg.song.beats_per_bar)
        from produzre.harmony import parse_meter
        meter = parse_meter(section.meter or cfg.song.meter)
        rhythm_grid = RhythmGrid(meter=meter, beats_per_bar=cfg.song.beats_per_bar, total_beats=total_beats)

        timeline = InstrumentTimeline(instrument="bass")

        rhythm_intent = RhythmIntent(accent_beats={0.0, 8.0}, space_budget=None)

        instrument_cfg = {"params": {
            "density": 0.8,
            "register_low": 28,
            "register_high": 52,
            "rhythm_pattern": "anchor",
            "lock_to_kick": 0.6,
            "articulation_style": "finger",
        }}

        features = render_into_timeline(
            cfg=cfg,
            section=section,
            harmony_plan=harmony_plan,
            rhythm_grid=rhythm_grid,
            section_start_beat=0.0,
            timeline=timeline,
            instrument_cfg=instrument_cfg,
            rng=Random(2000),
            rhythm_intent=rhythm_intent,
        )

        return features

    features1 = build_and_get_features()
    features2 = build_and_get_features()

    # Verify determinism
    assert features1.event_count == features2.event_count, "Event count should be deterministic"
    assert features1.onset_map == features2.onset_map, "Onset map should be deterministic"
    assert features1.accent_map == features2.accent_map, "Accent map should be deterministic"
    assert features1.register_profile == features2.register_profile, "Register profile should be deterministic"

    print("✓ Negotiation features are deterministic")


if __name__ == "__main__":
    print("Running bass negotiation hooks tests (Phase B11)...")
    print()

    test_baseline_without_rhythm_intent()
    print()

    test_rhythm_intent_injection()
    print()

    test_space_budget_reduces_density()
    print()

    test_accent_map_with_rhythm_intent()
    print()

    test_negotiation_features_deterministic()
    print()

    print("✅ All bass negotiation tests passed!")
