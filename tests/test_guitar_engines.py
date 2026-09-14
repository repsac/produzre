"""Smoke tests for guitar engines (rhythm_gtr, lead_gtr, acoustic_gtr).

Verifies that:
1. Each engine builds successfully with its demo YAML
2. MIDI output is produced (non-empty)
3. Builds are deterministic with same seed
4. Personas load and resolve correctly for each engine
"""

import subprocess
import sys
from pathlib import Path

import pytest


def _build(yaml_path: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "produzre.cli", "build", yaml_path],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _export_root(result: subprocess.CompletedProcess) -> str:
    for line in result.stderr.splitlines():
        if "Export root:" in line:
            return line.split("Export root:")[1].strip()
    raise AssertionError("No export root in build output")


# ---------------------------------------------------------------------------
# Rhythm guitar
# ---------------------------------------------------------------------------

class TestRhythmGuitar:
    YAML = "examples/rhythm_gtr/sustained-chords-demo.yaml"

    def test_builds_successfully(self):
        result = _build(self.YAML)
        assert result.returncode == 0, f"Build failed:\n{result.stderr}"

    def test_produces_midi_events(self):
        result = _build(self.YAML)
        assert result.returncode == 0
        root = _export_root(result)
        midi_files = list(Path(root).rglob("*.mid"))
        assert len(midi_files) > 0, "No MIDI files produced"
        assert all(f.stat().st_size > 0 for f in midi_files), "Empty MIDI file"

    def test_deterministic(self):
        r1 = _build(self.YAML)
        r2 = _build(self.YAML)
        assert r1.returncode == 0 and r2.returncode == 0
        root1, root2 = _export_root(r1), _export_root(r2)
        for suffix in Path(root1).rglob("*.mid"):
            rel = suffix.relative_to(root1)
            f2 = Path(root2) / rel
            assert f2.exists(), f"Missing file in second build: {rel}"
            assert suffix.read_bytes() == f2.read_bytes(), f"MIDI differs: {rel}"


# ---------------------------------------------------------------------------
# Lead guitar
# ---------------------------------------------------------------------------

class TestLeadGuitar:
    YAML = "examples/lead_gtr/styles/rock-solo.yaml"

    def test_builds_successfully(self):
        result = _build(self.YAML)
        assert result.returncode == 0, f"Build failed:\n{result.stderr}"

    def test_produces_midi_events(self):
        result = _build(self.YAML)
        assert result.returncode == 0
        root = _export_root(result)
        midi_files = list(Path(root).rglob("*.mid"))
        assert len(midi_files) > 0, "No MIDI files produced"

    def test_deterministic(self):
        r1 = _build(self.YAML)
        r2 = _build(self.YAML)
        assert r1.returncode == 0 and r2.returncode == 0
        root1, root2 = _export_root(r1), _export_root(r2)
        for suffix in Path(root1).rglob("*.mid"):
            rel = suffix.relative_to(root1)
            f2 = Path(root2) / rel
            assert suffix.read_bytes() == f2.read_bytes(), f"MIDI differs: {rel}"


# ---------------------------------------------------------------------------
# Acoustic guitar
# ---------------------------------------------------------------------------

class TestAcousticGuitar:
    YAML = "examples/acoustic_gtr/style-comparison.yaml"

    def test_builds_successfully(self):
        result = _build(self.YAML)
        assert result.returncode == 0, f"Build failed:\n{result.stderr}"

    def test_produces_midi_events(self):
        result = _build(self.YAML)
        assert result.returncode == 0
        root = _export_root(result)
        midi_files = list(Path(root).rglob("*.mid"))
        assert len(midi_files) > 0, "No MIDI files produced"

    def test_deterministic(self):
        r1 = _build(self.YAML)
        r2 = _build(self.YAML)
        assert r1.returncode == 0 and r2.returncode == 0
        root1, root2 = _export_root(r1), _export_root(r2)
        for suffix in Path(root1).rglob("*.mid"):
            rel = suffix.relative_to(root1)
            f2 = Path(root2) / rel
            assert suffix.read_bytes() == f2.read_bytes(), f"MIDI differs: {rel}"


# ---------------------------------------------------------------------------
# Persona resolution
# ---------------------------------------------------------------------------

class TestGuitarPersonas:
    def test_personas_load(self):
        from produzre.config.load import load_root_config
        cfg = load_root_config("examples/genres/rock/rock-recipe-showcase.yaml")
        personas = cfg.raw.get("_personas", {})
        for inst in ("rhythm_gtr", "lead_gtr", "acoustic_gtr"):
            assert inst in personas, f"Missing personas for {inst}"
            assert "personas" in personas[inst], f"No personas key for {inst}"
            assert len(personas[inst]["personas"]) >= 3, f"Too few personas for {inst}"

    def test_effective_persona_defaults(self):
        from produzre.config.load import load_root_config
        cfg = load_root_config("examples/genres/rock/rock-recipe-showcase.yaml")
        eff = cfg.raw.get("_effective", {}).get("instruments", {})
        assert eff.get("rhythm_gtr", {}).get("persona") == "tight"
        assert eff.get("lead_gtr", {}).get("persona") == "balanced"
        assert eff.get("acoustic_gtr", {}).get("persona") == "natural"

    def test_persona_params_reach_engine(self):
        from produzre.config.load import load_root_config
        from produzre.orchestrate.render import _get_global_instrument_cfg
        cfg = load_root_config("examples/genres/rock/rock-recipe-showcase.yaml")
        for inst in ("rhythm_gtr", "lead_gtr", "acoustic_gtr"):
            ic = _get_global_instrument_cfg(cfg, inst)
            assert ic is not None, f"No instrument config for {inst}"
            extra = getattr(ic, "extra", None) or (ic.get("params") if isinstance(ic, dict) else None)
            assert extra, f"No persona params in instrument config for {inst}"


class TestDevelopBarPattern:
    """Unit tests for rhythm guitar phrase-level pattern development."""

    def _make_pattern(self):
        from produzre.engine.rhythm_gtr.types import GtrPattern
        return GtrPattern(
            name="test_base",
            subdivision=4,
            hits=[0, 4, 8, 12],
            accents=[0, 8],
            palm_mutes=[],
            strum_directions=["down", "up", "down", "up"],
            density=0.5,
        )

    def test_returns_valid_pattern(self):
        import random as rng_mod
        from produzre.engine.rhythm_gtr.rhythm import develop_bar_pattern
        pattern = self._make_pattern()
        result = develop_bar_pattern(
            pattern, bar_idx=3, total_bars=8, phrase_len_bars=4,
            section_type="verse", density=0.5, beats_per_bar=4.0,
            rng=rng_mod.Random(42),
        )
        assert hasattr(result, "hits")
        assert hasattr(result, "accents")
        assert len(result.hits) > 0

    def test_phrase_end_adds_hits(self):
        import random as rng_mod
        from produzre.engine.rhythm_gtr.rhythm import develop_bar_pattern
        pattern = self._make_pattern()
        results_lens = []
        for seed in range(30):
            result = develop_bar_pattern(
                pattern, bar_idx=3, total_bars=8, phrase_len_bars=4,
                section_type="verse", density=0.7, beats_per_bar=4.0,
                rng=rng_mod.Random(seed),
            )
            results_lens.append(len(result.hits))
        assert max(results_lens) > len(pattern.hits), "Phrase ends should sometimes add hits"

    def test_accents_subset_of_hits(self):
        import random as rng_mod
        from produzre.engine.rhythm_gtr.rhythm import develop_bar_pattern
        pattern = self._make_pattern()
        for bar_idx in range(8):
            result = develop_bar_pattern(
                pattern, bar_idx=bar_idx, total_bars=8, phrase_len_bars=4,
                section_type="bridge", density=0.6, beats_per_bar=4.0,
                rng=rng_mod.Random(bar_idx),
            )
            assert set(result.accents).issubset(set(result.hits))
