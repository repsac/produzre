# Run the tests

From a source checkout, create an environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt pytest
python -m pytest -q
python tests/test_golden_drums.py
```

On Windows, activate with `.venv\Scripts\activate`. You can run this checkout directly. Run commands from the repository root so example paths resolve.

The drum runner should end with `3 passed, 0 failed`; see the
[test guide](README.md#golden-files) for its baseline checks.

## If a test fails

For a build error, run the example directly with verbose logging:

```bash
python produzre_entry.py build examples/drums/hats-demo.yaml -v
```

For a golden mismatch, read the diff. A line prefixed with `-` is the saved
output; `+` is the current output. Check the onset, duration, pitch, velocity,
and kind columns to see what changed. Open the generated MIDI for a listening
check before accepting a new musical baseline.

For a missing TSV, check `exports.midi_text.enabled` and whether `views`
contains `events`. Use the export root printed by that build; another build's
folder may be newer.

For an import error, confirm the active Python has the requirements and pytest
installed. For differences across machines, check [the repeatability inputs](../DETERMINISM.md)
before changing the baselines.

## Intentional musical changes

Follow [the baseline update process](README.md#updating-expected-output)
after finishing the related behavior changes. CI should never regenerate a baseline to make itself pass.

A useful focused run during theme work is:

```bash
python -m pytest -q tests/test_themes.py tests/test_release_fixes.py
```

The [test guide](README.md) also lists meter, example-build, and strict
repeatability checks for a release.
