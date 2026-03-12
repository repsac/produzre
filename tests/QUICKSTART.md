# Golden TSV Tests - Quick Start

This guide will help you get started with the golden TSV test suite.

## What Are Golden Tests?

Golden tests (also called snapshot tests) prevent "it sounded good yesterday" regressions by:
1. Capturing known-good output as "golden files"
2. Comparing future builds against these golden files
3. Failing if the output changes unexpectedly

## Setup

### 1. Install Produzre

Make sure Produzre is installed and working:

```bash
# From repo root
pip install -e .
```

### 2. Verify Test Script Works

```bash
# This will run tests but skip cases without golden files
python tests/test_golden_drums.py
```

You should see something like:
```
Testing hats-demo (drums)... SKIP (no golden file)
Testing kick-demo (drums)... SKIP (no golden file)
Testing fills-demo (drums)... SKIP (no golden file)

Tests complete: 3 passed, 0 failed
```

### 3. Generate Initial Golden Files

**Important**: Only do this after verifying the current output sounds correct!

```bash
# Interactive prompt
./tests/generate_golden.sh

# Or non-interactive
python tests/test_golden_drums.py --regenerate
```

This will:
- Build each test YAML file
- Extract the generated TSV file
- Save it as a golden file in `tests/golden/`

### 4. Run Tests

```bash
# Run all golden tests
python tests/test_golden_drums.py

# Or use the wrapper
./tests/run_tests.sh
```

You should see:
```
Testing hats-demo (drums)... PASS
Testing kick-demo (drums)... PASS
Testing fills-demo (drums)... PASS

Tests complete: 3 passed, 0 failed
```

## Daily Workflow

### When Developing

1. Make changes to drums engine
2. Run tests: `python tests/test_golden_drums.py`
3. If tests fail:
   - Review the diff (printed automatically)
   - Build the affected YAML and listen to the MIDI
   - If correct: regenerate golden files
   - If incorrect: fix your code

### When Regenerating

```bash
# See what changed
python tests/test_golden_drums.py

# If changes look correct
python tests/test_golden_drums.py --regenerate

# Verify tests now pass
python tests/test_golden_drums.py

# Review changes
git diff tests/golden/

# Commit if correct
git add tests/golden/
git commit -m "Update golden files for [reason]"
```

## Understanding Test Output

### Passing Test
```
Testing hats-demo (drums)... PASS
```

### Failing Test
```
Testing hats-demo (drums)... FAIL

======================================================================
MISMATCH: hats-demo (drums)
======================================================================
--- hats-demo (drums) (golden)
+++ hats-demo (drums) (actual)
@@ -10,7 +10,7 @@
 drums	verse_pattern	1	1.000	0.000	0.125	42	85	9	0
-drums	verse_pattern	1	1.500	0.500	0.125	42	72	9	0
+drums	verse_pattern	1	1.500	0.500	0.125	42	75	9	0
 drums	verse_pattern	1	2.000	1.000	0.125	42	85	9	0
======================================================================
```

This shows:
- **Line with `-`**: Expected (golden file)
- **Line with `+`**: Actual (current build)
- **Change**: Velocity changed from 72 to 75 at beat 1.5

### Missing Golden File
```
Testing hats-demo (drums)... SKIP (no golden file at tests/golden/hats-demo_drums.events.tsv)
```

## Troubleshooting

### "Build failed" Error

**Symptom**: `FAIL (build failed)`

**Causes**:
- Produzre not installed: `pip install -e .`
- Missing dependencies: `pip install pyyaml mido`
- Syntax error in YAML file
- Bug in build process

**Debug**:
```bash
# Try building manually
python -m produzre.cli build examples/drums/hats-demo.yaml
```

### Tests Pass But Output Sounds Wrong

**This is the most dangerous case!** It means:
- The golden files are incorrect
- You regenerated without listening to the output

**Fix**:
1. Build the YAML manually and listen
2. Fix the code issue
3. Regenerate golden files
4. Listen again to verify
5. Update tests

### Tests Fail But Output Sounds Correct

**This is expected** when you intentionally change behavior.

**Fix**:
```bash
# Regenerate golden files
python tests/test_golden_drums.py --regenerate

# Commit with explanation
git add tests/golden/
git commit -m "Update golden files: improved hi-hat velocity dynamics"
```

### Can't Find TSV File

**Symptom**: `ERROR: TSV file not found`

**Causes**:
- `exports.midi_text.enabled: false` in YAML
- Export directory was deleted
- Build didn't complete

**Fix**:
1. Ensure YAML has:
   ```yaml
   exports:
     midi_text:
       enabled: true
   ```
2. Check `exports/` directory exists
3. Try building manually first

## Advanced Usage

### Testing Only One File

```python
# Edit test_golden_drums.py temporarily
GOLDEN_TESTS = [
    ("examples/drums/hats-demo.yaml", "drums"),
    # Comment out others
]
```

### Comparing Specific Changes

```bash
# Before changes
python tests/test_golden_drums.py --regenerate
cp -r tests/golden tests/golden.backup

# Make changes

# After changes
python tests/test_golden_drums.py

# See exact diff
diff tests/golden.backup/hats-demo_drums.events.tsv \
     tests/golden/hats-demo_drums.events.tsv
```

### Adding Your Own Test

1. Create `examples/drums/my-test.yaml`
2. Add `midi_text.enabled: true` to exports
3. Edit `test_golden_drums.py`:
   ```python
   GOLDEN_TESTS = [
       # ... existing tests ...
       ("examples/drums/my-test.yaml", "drums"),
   ]
   ```
4. Generate: `python tests/test_golden_drums.py --regenerate`
5. Verify: `python tests/test_golden_drums.py`

## Next Steps

- Read [README.md](README.md) for test suite overview
- Read [CI_INTEGRATION.md](CI_INTEGRATION.md) for CI/CD setup
- Review existing golden files to understand TSV format
- Add more test cases for edge cases

## Quick Reference

```bash
# Run tests
python tests/test_golden_drums.py

# Regenerate golden files
python tests/test_golden_drums.py --regenerate

# Or use wrappers
./tests/run_tests.sh              # Run tests
./tests/generate_golden.sh        # Regenerate (interactive)
```
