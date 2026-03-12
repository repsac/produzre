# Produzre Tests

## Running All Tests

```bash
# Run the full test suite with pytest
python -m pytest tests/ -v

# Run only unit tests (fast, no builds)
python -m pytest tests/test_negotiation.py tests/test_performance_plan.py \
  tests/test_section_transitions.py tests/test_engine_dependencies.py \
  tests/test_contribute_plan.py -v

# Run guitar engine smoke tests
python -m pytest tests/test_guitar_engines.py -v
```

## Test Categories

| Category | Files | Description |
|----------|-------|-------------|
| Bass engine | `test_bass_*.py` (12 files) | Articulation, groove, harmony, rhythm, fills, walking, slap, solo, personas, negotiation, determinism |
| Guitar engines | `test_guitar_engines.py` | Smoke tests for rhythm_gtr, lead_gtr, acoustic_gtr + persona resolution |
| Orchestration | `test_contribute_plan.py`, `test_engine_*.py`, `test_harmony_contribute_plan.py`, `test_drums_contribute_plan.py` | Engine priority, dependencies, contribute_plan hooks |
| Negotiation | `test_negotiation.py`, `test_performance_plan.py` | Feedback loops, performance plan API |
| Transitions | `test_section_transitions.py` | Section-level transition planning |
| Determinism | `test_midi_determinism.py` | Byte-for-byte MIDI reproducibility |
| Seed/Variation | `test_seed_variation.py` | Section-level and instrument-level seed/variation overrides |
| Golden files | `test_golden_drums.py` | TSV snapshot regression tests |

## Golden TSV Tests

Golden TSV tests prevent "it sounded good yesterday" regressions by comparing generated drum patterns against known-good snapshot files.

### Running Golden Tests

```bash
# Run all golden tests
python tests/test_golden_drums.py

# Or use the test runner script
./tests/run_tests.sh
```

### Regenerating Golden Files

When you intentionally change the drums engine and verify the new output is correct:

```bash
python tests/test_golden_drums.py --regenerate
```

**Important:** Always review the changes before committing regenerated golden files!

### Test Cases

Current golden tests:

- **hats-demo.yaml**: Hi-hat patterns (open/closed/pedal variations, density, accents)
- **kick-demo.yaml**: Kick patterns (syncopation, double-kick, extra kicks)
- **fills-demo.yaml**: Fill patterns (short/medium/long, chatter, persona-based types)

### Adding New Test Cases

1. Add the test case to `GOLDEN_TESTS` in `test_golden_drums.py`:
   ```python
   GOLDEN_TESTS = [
       # ... existing tests ...
       ("examples/drums/new-demo.yaml", "drums"),
   ]
   ```

2. Generate the golden file:
   ```bash
   python tests/test_golden_drums.py --regenerate
   ```

3. Commit both the test code and the golden file

### File Structure

```
tests/
├── README.md                           # This file
├── conftest.py                         # Shared fixtures and helpers
├── run_tests.sh                        # Test runner script
├── generate_golden.sh                  # Golden file regeneration
├── test_golden_drums.py                # Golden TSV test suite
├── test_guitar_engines.py              # Guitar engine smoke tests
├── test_bass_*.py                      # Bass engine tests (12 files)
├── test_*_contribute_plan.py           # Engine contribute_plan tests
├── test_engine_*.py                    # Engine priority/dependency tests
├── test_negotiation.py                 # Negotiation feedback tests
├── test_performance_plan.py            # Performance plan API tests
├── test_section_transitions.py         # Transition planning tests
├── test_midi_determinism.py            # MIDI determinism tests
├── test_seed_variation.py             # Seed/variation override tests
└── golden/                             # Golden TSV files (committed)
    ├── bass/
    │   ├── baseline.events.tsv
    │   └── baseline.grid.txt
    ├── hats-demo_drums.events.tsv
    ├── kick-demo_drums.events.tsv
    └── fills-demo_drums.events.tsv
```

### TSV Format

The `.events.tsv` files contain tab-separated values with these columns:

- `instrument`: Instrument name (e.g., "drums")
- `section_id`: Section identifier
- `bar`: Bar number (1-indexed)
- `beat`: Beat within bar (1-indexed, fractional)
- `start_beat_abs`: Absolute beat from song start
- `duration_beats`: Note duration in beats
- `pitch`: MIDI pitch (GM drum mapping)
- `velocity`: MIDI velocity (1-127)
- `channel`: MIDI channel
- `program`: MIDI program number

### CI Integration

These tests can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run golden tests
  run: python tests/test_golden_drums.py
```

The tests will fail (non-zero exit code) if any TSV mismatches are detected.
