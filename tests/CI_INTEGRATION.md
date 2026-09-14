# Run tests in CI

Run pytest and the standalone drum golden runner in CI. Install pytest
alongside the runtime requirements. Use the same Python and
dependency versions when comparing musical output across machines.

## GitHub Actions

This example checks pushes and pull requests. Adapt branch filters to the
repository's release policy.

```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: python -m pip install -r requirements.txt pytest
      - name: Run pytest
        run: python -m pytest -q
      - name: Check drum goldens
        run: python tests/test_golden_drums.py
      - name: Save failed build outputs
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: test-exports
          path: exports/
          if-no-files-found: ignore
```

The repo's requirements specify minimum versions. For a fixed release test
environment, supply a reviewed dependency lock or constraints file as well.

## GitLab CI

```yaml
test:
  image: python:3.11
  script:
    - python -m pip install -r requirements.txt pytest
    - python -m pytest -q
    - python tests/test_golden_drums.py
  artifacts:
    when: on_failure
    paths:
      - exports/
    expire_in: 1 week
```

## Optional local hook

If you want both suites before a local commit, put this in
`.git/hooks/pre-commit` and make it executable. It uses the active environment.

```bash
#!/bin/sh
set -e
python -m pytest -q
python tests/test_golden_drums.py
```

Do not replace an existing hook without preserving its checks.

## Handling failures

A nonzero exit fails the job. Keep the log and relevant exports so a reviewer
can inspect differences. See [golden-file checks](README.md#golden-files)
for build and baseline failures. When output changes intentionally, review it locally and
follow the [baseline update process](README.md#updating-expected-output).
Do not regenerate goldens automatically in CI.

Add the example-build and strict-determinism commands from the
[release checks](README.md#release-checks) to release jobs. See the [test guide](README.md) for environment requirements.
Allow time for the larger examples in release jobs.
