# Testing Produzre

Run both the pytest suite and the standalone drum golden runner from the
repository root:

```bash
python -m pip install -r requirements.txt pytest
python -m pytest -q
python tests/test_golden_drums.py
```

`test_golden_drums.py` is a command-line runner. Pytest does not collect its
three build comparisons. `tests/run_tests.sh` wraps that runner only. The bass golden comparison is part of pytest.

## What the tests cover

| Area | Main files |
|---|---|
| Bass | `test_bass_*.py`: articulation, harmony, rhythm, fills, slap, walking, solos, personas, and determinism. |
| Guitars | `test_guitar_engines.py`, `test_lead_phrasing.py`, `test_chord_shapes_fixes.py`. |
| Melody and themes | `test_melody_engine.py`, `test_themes.py`, `test_ensemble_generation.py`. |
| Release edge cases | `test_release_fixes.py`: theme pitches, register/order hashing, meter, precedence, drum voices, export indexing, and timing. |
| Planning | `test_contribute_plan.py`, `test_*_contribute_plan.py`, `test_engine_*.py`, `test_performance_plan.py`. |
| Coordination | `test_negotiation.py`, `test_section_transitions.py`, `test_macro_dynamics.py`, `test_energy_helper.py`. |
| Timing and export | `test_groove_clock.py`, `test_meter_support.py`, `test_midi_determinism.py`, `test_seed_variation.py`. |
| Integration and recipes | `test_integration_e2e.py`, `test_core_fixes.py`, `test_drum_fixes.py`, `test_recipe_tools.py`. |

For a focused check:

```bash
python -m pytest -q tests/test_themes.py tests/test_release_fixes.py
python -m pytest -q tests/test_groove_clock.py tests/test_meter_support.py
```

Tests build real examples and write ignored files under `exports/`. Install
Mido, PyYAML, and pytest first. You can then run tests offline without a DAW
or audio hardware.

## Golden files

Golden files record expected musical output. They catch changes in timing,
pitch, velocity, duration, and note kind. Review a changed golden to decide whether you intended the change. Listen
to the output too.

```text
tests/golden/
  hats-demo_drums.events.tsv
  kick-demo_drums.events.tsv
  fills-demo_drums.events.tsv
  bass/
    baseline.events.tsv
    baseline.grid.txt
```

The [output guide](../README.md#output-files) defines the TSV columns and
timing units.

The drum runner reads the export root printed by its own build. Missing
baselines, failed builds, missing TSVs, and content differences all fail.

### Updating expected output

Finish all output-changing fixes first. Review the event differences and
listen to the affected examples, then regenerate once:

```bash
bash tests/generate_golden.sh
# Noninteractive equivalent:
# python tests/test_golden_drums.py --regenerate
```

The script updates only the three drum TSVs. To update the bass baseline,
build it and copy both files from that build's printed export root:

```bash
python produzre_entry.py build examples/bass/baseline/baseline-demo.yaml
# Replace the path below with the Export root printed by this build.
BASS_EXPORT='exports/BassBaseline_<timestamp>'
cp "$BASS_EXPORT/analysis/bass/BassBaseline_bass.events.tsv" tests/golden/bass/baseline.events.tsv
cp "$BASS_EXPORT/analysis/bass/BassBaseline_bass.grid.txt" tests/golden/bass/baseline.grid.txt
```

Rerun both suites and inspect `git diff -- tests/golden/`. Explain intentional
musical changes in the changelog. Prefer behavioral assertions for properties
such as range, cadence, or articulation ordering. Keep exact snapshots where
the full sequence is what the test is meant to guard.

To add a drum baseline, create an example with event text export enabled, add
its path and instrument to `GOLDEN_TESTS` in `test_golden_drums.py`, and review
the generated TSV before accepting it.

## Release checks

```bash
python produzre_entry.py build examples/themes_demo.yaml --strict-determinism
python produzre_entry.py build examples/genres/rock/rock-full-arrangement.yaml --strict-determinism
python produzre_entry.py build examples/drums/phrasing-demo.yaml --strict-determinism
```

The last config includes a 6/8 section; see [DETERMINISM.md](../DETERMINISM.md#verify-a-build)
for what strict mode compares.

Check all example configs in Bash:

```bash
find examples -name '*.yaml' -print0 | while IFS= read -r -d '' file; do
  python produzre_entry.py build "$file" --dry-run || exit 1
done
```

[QUICKSTART.md](QUICKSTART.md) covers setup and failures.
[CI_INTEGRATION.md](CI_INTEGRATION.md) shows automation examples.
