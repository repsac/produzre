# CI Integration for Golden TSV Tests

This document describes how to integrate the golden TSV tests into CI/CD pipelines.

## Overview

The golden TSV tests prevent regressions in the drums engine by comparing generated output against committed snapshot files. These tests are deterministic and suitable for CI environments.

## GitHub Actions

Add this workflow to `.github/workflows/test.yml`:

```yaml
name: Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  golden-tests:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e .
        # Install any additional dependencies
        pip install pyyaml mido

    - name: Run golden TSV tests
      run: python tests/test_golden_drums.py

    - name: Upload test artifacts on failure
      if: failure()
      uses: actions/upload-artifact@v3
      with:
        name: test-output
        path: exports/
```

## GitLab CI

Add this to `.gitlab-ci.yml`:

```yaml
test:golden-tsv:
  stage: test
  image: python:3.11
  script:
    - pip install -e .
    - pip install pyyaml mido
    - python tests/test_golden_drums.py
  artifacts:
    when: on_failure
    paths:
      - exports/
    expire_in: 1 week
```

## Local Pre-commit Hook

To run tests before every commit, add to `.git/hooks/pre-commit`:

```bash
#!/bin/bash

echo "Running golden TSV tests..."
python tests/test_golden_drums.py

if [ $? -ne 0 ]; then
    echo ""
    echo "Golden TSV tests failed!"
    echo "If changes are intentional, regenerate golden files:"
    echo "  python tests/test_golden_drums.py --regenerate"
    echo ""
    exit 1
fi
```

Make it executable:
```bash
chmod +x .git/hooks/pre-commit
```

## Test Workflow

### Developer Workflow

1. Make changes to drums engine
2. Run tests: `python tests/test_golden_drums.py`
3. If tests fail:
   - Review the diff output
   - Listen to the generated MIDI to verify changes sound correct
   - If correct: `python tests/test_golden_drums.py --regenerate`
   - Commit both code changes and updated golden files

### CI Workflow

1. CI runs tests on every push/PR
2. If tests fail, the build fails
3. Developer must fix the issue or regenerate golden files
4. Updated golden files must be reviewed in PR

## Test Maintenance

### Adding New Test Cases

When adding new drum features, add corresponding test cases:

1. Create a demo YAML in `examples/drums/`
2. Ensure `exports.midi_text.enabled: true` is set
3. Add to `GOLDEN_TESTS` in `test_golden_drums.py`
4. Generate golden file: `python tests/test_golden_drums.py --regenerate`
5. Commit both the test case and golden file

### Updating Existing Tests

When intentionally changing drum behavior:

1. Make your code changes
2. Run tests to see what changed
3. Review the diffs carefully
4. Listen to the generated MIDI files
5. If correct: `python tests/test_golden_drums.py --regenerate`
6. Include updated golden files in your commit
7. Document changes in commit message

### Test Failures in CI

If tests fail in CI but pass locally:

1. Check Python version (tests require consistent random seeds)
2. Check dependency versions
3. Ensure test configuration files haven't been modified
4. Re-run tests locally with same Python version as CI

## Performance Considerations

- Each test builds a full YAML file (1-2 seconds per test)
- Total test suite runtime: ~5-10 seconds for 3 test cases
- Tests are CPU-bound (MIDI generation)
- No network dependencies

## Golden File Format

Golden files are deterministic TSV exports with these properties:

- UTF-8 encoding
- Tab-separated values
- Sorted by `(start_beat_abs, pitch)`
- No trailing whitespace
- LF line endings (Unix style)

Any deviation from the golden file causes test failure.

## Debugging Test Failures

When a test fails:

1. **Check the diff**: The test outputs a unified diff showing exact changes
2. **Review the section**: Look at which bars/beats changed
3. **Check velocity/timing**: Small numerical changes might indicate precision issues
4. **Listen to both**: Generate MIDI from old and new TSV to hear the difference
5. **Check git history**: See when the golden file was last updated

Example debugging:
```bash
# Run tests with verbose output
python tests/test_golden_drums.py

# Review the diff (shown in test output)

# Generate MIDI from golden file for comparison
# (if you have a TSV-to-MIDI converter)

# If changes are correct, regenerate
python tests/test_golden_drums.py --regenerate
```

## Best Practices

1. **Review changes carefully**: Golden files represent "correct" output
2. **Listen to the output**: Numbers can lie, your ears don't
3. **Small commits**: Update golden files separately from feature work when possible
4. **Document changes**: Explain why golden files changed in commit messages
5. **Keep tests fast**: Avoid adding too many test cases (aim for <10 total)
6. **Test edge cases**: Include tests for boundary conditions (empty sections, max values, etc.)

## Troubleshooting

### Tests pass locally but fail in CI

- **Cause**: Python version mismatch affecting random number generation
- **Fix**: Use same Python version locally as in CI

### Tests fail after dependency update

- **Cause**: Updated library changed behavior (e.g., YAML parsing, MIDI writing)
- **Fix**: Review changes, regenerate if correct

### Golden files have merge conflicts

- **Cause**: Multiple developers changing same drum feature
- **Fix**: Regenerate golden files from merged code

### Tests are too slow

- **Cause**: Too many test cases or complex YAMLs
- **Fix**: Reduce test cases or simplify test YAMLs (fewer bars, simpler patterns)
