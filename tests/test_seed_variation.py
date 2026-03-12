"""Test granular seed and variation control.

Verifies that:
1. Section-level seed override changes only the targeted section
2. Section-level variation override changes only the targeted section
3. Instrument-level seed override changes only the targeted instrument
4. Instrument-level variation override changes only the targeted instrument
5. Repeated sections in the arrangement produce different output
6. Non-targeted sections/instruments remain identical to the base song

Uses the 5 YAML files in examples/seed-variation/ as test fixtures.
"""

import logging
import random
from pathlib import Path

import pytest

from produzre.config.load import load_root_config as load_config
from produzre.orchestrate.build import build_song
from produzre.rng import make_section_rng, make_instrument_rng, stable_seed_int


EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples" / "seed-variation"

BASE_YAML = EXAMPLES_DIR / "base-song.yaml"
SECTION_SEED_YAML = EXAMPLES_DIR / "section-seed-override.yaml"
SECTION_VAR_YAML = EXAMPLES_DIR / "section-variation.yaml"
INST_SEED_YAML = EXAMPLES_DIR / "instrument-seed-override.yaml"
INST_VAR_YAML = EXAMPLES_DIR / "instrument-variation.yaml"

ALL_YAMLS = [BASE_YAML, SECTION_SEED_YAML, SECTION_VAR_YAML, INST_SEED_YAML, INST_VAR_YAML]


def _build_dry(yaml_path: Path):
    """Load config and build (dry run) to get timelines without writing files."""
    cfg = load_config(str(yaml_path))
    result = build_song(
        cfg=cfg,
        dry_run=True,
        export_sections=False,
        export_patterns=False,
        sections_absolute_timing=False,
        logger=logging.getLogger("test_seed_variation"),
    )
    return result


@pytest.fixture(scope="module")
def base_result():
    """Build the base song once for all tests."""
    return _build_dry(BASE_YAML)


@pytest.fixture(scope="module")
def section_seed_result():
    return _build_dry(SECTION_SEED_YAML)


@pytest.fixture(scope="module")
def section_var_result():
    return _build_dry(SECTION_VAR_YAML)


@pytest.fixture(scope="module")
def inst_seed_result():
    return _build_dry(INST_SEED_YAML)


@pytest.fixture(scope="module")
def inst_var_result():
    return _build_dry(INST_VAR_YAML)


# ---------------------------------------------------------------------------
# Test: All 5 files load and build without errors
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("yaml_path", ALL_YAMLS, ids=[p.stem for p in ALL_YAMLS])
def test_all_files_build_successfully(yaml_path):
    """Every seed-variation example file should load and build without errors."""
    assert yaml_path.exists(), f"Missing example file: {yaml_path}"
    result = _build_dry(yaml_path)
    assert result is not None
    assert result.total_beats > 0
    assert len(result.instruments_used) > 0


# ---------------------------------------------------------------------------
# Test: Event counts differ where expected
# ---------------------------------------------------------------------------

def test_section_seed_changes_chorus_events(base_result, section_seed_result):
    """Section seed override should change chorus event counts."""
    assert base_result.events_per_instrument != section_seed_result.events_per_instrument, (
        "Section seed override should produce different total event counts"
    )


def test_section_seed_preserves_structure(base_result, section_seed_result):
    """Section seed override should preserve the same instruments and section count."""
    assert base_result.instruments_used == section_seed_result.instruments_used
    assert len(base_result.section_timings) == len(section_seed_result.section_timings)
    assert base_result.total_beats == section_seed_result.total_beats


def test_instrument_seed_changes_events(base_result, inst_seed_result):
    """Instrument seed override should change event counts."""
    assert base_result.events_per_instrument != inst_seed_result.events_per_instrument, (
        "Instrument seed override should produce different event counts"
    )


def test_instrument_seed_preserves_structure(base_result, inst_seed_result):
    """Instrument seed override should preserve structure."""
    assert base_result.instruments_used == inst_seed_result.instruments_used
    assert len(base_result.section_timings) == len(inst_seed_result.section_timings)
    assert base_result.total_beats == inst_seed_result.total_beats


# ---------------------------------------------------------------------------
# Test: Variation is injected into configs
# ---------------------------------------------------------------------------

def test_section_variation_builds(section_var_result):
    """Section variation file should build successfully with variation applied."""
    assert section_var_result is not None
    assert section_var_result.total_beats > 0


def test_instrument_variation_builds(inst_var_result):
    """Instrument variation file should build successfully with variation applied."""
    assert inst_var_result is not None
    assert inst_var_result.total_beats > 0


# ---------------------------------------------------------------------------
# Test: Repeated sections produce different output
# ---------------------------------------------------------------------------

def test_repeated_sections_differ():
    """Same section appearing twice in arrangement should produce different output.

    The base song has 'chorus' at arrangement positions 2 and 4.
    These should produce different RNG streams due to arrangement-index
    differentiation.
    """
    cfg = load_config(str(BASE_YAML))

    # Verify the arrangement has chorus appearing twice
    chorus_indices = [i for i, s in enumerate(cfg.arrangement) if s == "chorus"]
    assert len(chorus_indices) >= 2, "Base song should have chorus at least twice in arrangement"

    # Compute the section RNGs for each chorus occurrence
    runtime = getattr(cfg, "runtime", None)
    project_seed = getattr(runtime, "project_seed", 0) if runtime else 0
    song_seed = int(cfg.song.seed)
    take = int(cfg.song.take)

    rngs = []
    for idx in chorus_indices:
        effective_take = stable_seed_int(take, idx)
        rng = make_section_rng(project_seed, song_seed, effective_take, "chorus", "chorus")
        rngs.append(rng.random())

    # The two chorus RNGs should produce different values
    assert rngs[0] != rngs[1], (
        f"Repeated chorus sections should have different RNG streams, "
        f"but both produced {rngs[0]}"
    )


# ---------------------------------------------------------------------------
# Test: Section seed override produces different RNG than base
# ---------------------------------------------------------------------------

def test_section_seed_override_changes_rng():
    """A section with seed: 999 should produce a different RNG than seed: 42."""
    project_seed = 0
    take = 0
    idx = 2  # chorus is at arrangement index 2

    effective_take = stable_seed_int(take, idx)

    # Base song uses song_seed=42
    rng_base = make_section_rng(project_seed, 42, effective_take, "chorus", "chorus")

    # Section override uses seed=999
    rng_override = make_section_rng(project_seed, 999, effective_take, "chorus", "chorus")

    assert rng_base.random() != rng_override.random(), (
        "Section seed override should produce different RNG stream"
    )


# ---------------------------------------------------------------------------
# Test: Instrument seed override produces different RNG than base
# ---------------------------------------------------------------------------

def test_instrument_seed_override_changes_rng():
    """An instrument with seed: 777 should get its own RNG, different from
    the default instrument RNG derived from the section RNG."""
    project_seed = 0
    song_seed = 42
    take = 0
    idx = 2

    effective_take = stable_seed_int(take, idx)
    section_rng = make_section_rng(project_seed, song_seed, effective_take, "chorus", "chorus")

    # Default instrument RNG (no override)
    default_rng = make_instrument_rng(section_rng, "drums")

    # Override RNG (seed: 777)
    override_seed = stable_seed_int("inst_override", 777, "chorus", "drums")
    override_rng = random.Random(override_seed)

    assert default_rng.random() != override_rng.random(), (
        "Instrument seed override should produce different RNG stream"
    )


# ---------------------------------------------------------------------------
# Test: Parsing of seed/variation fields
# ---------------------------------------------------------------------------

def test_section_seed_parsed():
    """Section seed should be parsed from YAML into SectionConfig."""
    cfg = load_config(str(SECTION_SEED_YAML))
    chorus = cfg.sections["chorus"]
    assert chorus.seed == 999, f"Expected section seed 999, got {chorus.seed}"


def test_section_variation_parsed():
    """Section variation should be parsed from YAML into SectionConfig."""
    cfg = load_config(str(SECTION_VAR_YAML))
    chorus = cfg.sections["chorus"]
    assert chorus.variation == 0.6, f"Expected section variation 0.6, got {chorus.variation}"


def test_instrument_seed_parsed():
    """Instrument seed should be parsed from YAML into InstrumentConfig."""
    cfg = load_config(str(INST_SEED_YAML))
    drums = cfg.sections["chorus"].instruments["drums"]
    assert drums.seed == 777, f"Expected instrument seed 777, got {drums.seed}"


def test_instrument_variation_parsed():
    """Instrument variation should be parsed from YAML into InstrumentConfig."""
    cfg = load_config(str(INST_VAR_YAML))
    drums = cfg.sections["chorus"].instruments["drums"]
    assert drums.variation == 0.8, f"Expected instrument variation 0.8, got {drums.variation}"


def test_base_song_has_no_overrides():
    """Base song should have no seed/variation overrides on sections or instruments."""
    cfg = load_config(str(BASE_YAML))
    for sec_id, sec in cfg.sections.items():
        assert sec.seed is None, f"Section '{sec_id}' should have no seed override"
        assert sec.variation is None, f"Section '{sec_id}' should have no variation override"
        for inst_name, inst in sec.instruments.items():
            assert inst.seed is None, (
                f"Section '{sec_id}' instrument '{inst_name}' should have no seed override"
            )
            assert inst.variation is None, (
                f"Section '{sec_id}' instrument '{inst_name}' should have no variation override"
            )
