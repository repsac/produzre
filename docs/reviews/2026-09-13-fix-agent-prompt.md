# Task: independent review, fixes, and documentation rewrite for the produzre `dev` branch

You are working in the Python repo at /Users/edcaspersen/Code/repos/produzre, a
procedural music generator (YAML song config in, multi-track MIDI out). The
`dev` branch is 5 commits ahead of `main` and is being prepared for the next
release. Your job has three parts: do your own review of the diff, fix what you
find, and rewrite the documentation so it reads like a person wrote it.

Do not commit, stage, push, tag, or create branches. Leave every change in the
working tree. The owner will review the diff and commit themselves.

## Context you should read first

1. `docs/reviews/2026-09-13-dev-vs-main-review.md`. A prior reviewer already
   went through this diff and left about 50 findings grouped P0 / P1 / cleanups
   / enhancements, with file and line references. Treat it as a strong lead,
   not as gospel: verify each finding yourself before acting on it, and if you
   disagree with one, say so in your final report and leave it alone.
2. `docs/design/theme-bank-architecture.md`. The design doc for the theme bank.
   Several findings are about code not matching this doc.
3. `git log --oneline main..dev` and `git diff --stat main...dev` to see the
   five commits and the 145 files they touch.
4. `CLAUDE.md` in the repo root if present, and `tests/README.md`.

Baseline facts established by the prior review (re-verify the first two):

- `python -m pytest -q` on dev HEAD: 12 failed / 346 passed. All 12 failures
  come from the last commit (7624d32, theme bank). The commit before it passes
  all 358 tests.
- All 166 example configs build with
  `python produzre_entry.py build <yaml> --dry-run`, and
  `--strict-determinism` passes on the examples that were tried.
- Auto-composed themes are on by default (`song.themes_auto` defaults to true),
  which changed every song's bass and drum output. The goldens in
  `tests/golden/` were not regenerated afterwards.
- `produzre/__init__.py` still says `0.8.0`; `CHANGELOG.md` says `0.9.0` and
  only describes one of the five commits.

## Part 1: your own review

Read the actual diff (`git diff main...dev -- <path>`) and the current files
on dev for every area listed below. Look for real bugs, not style: wrong units
(bars vs beats vs ticks vs seconds), off-by-one at section and chord
boundaries, odd meters (3/4, 6/8, 7/8, 5/4) breaking math that assumes 4 beats,
merge-order regressions (intended chain is persona < recipe < global params <
section params), params that are parsed or shipped in recipes but never read,
non-determinism (unseeded random, set or dict iteration order), exceptions on
edge cases (1-bar sections, missing keys, None), and features the changelog or
design doc claims that the code does not deliver.

Areas, in the order the prior review found the most trouble:

- `produzre/themes/` (all files), `produzre/melody.py`,
  `produzre/orchestrate/ensemble.py`, the theme parts of
  `produzre/orchestrate/render.py`, `tools/demo_themes.py`
- `produzre/engine/drums/` and `produzre/resources/recipes/drums/`,
  `tools/train_drum_recipes.py`
- `produzre/engine/bass/`, `produzre/engine/harmony/`, `produzre/harmony/`,
  `produzre/instruments/chord_shapes.py`, `produzre/resources/recipes/bass/`
  and `recipes/harmony/`
- `produzre/engine/rhythm_gtr/`, `lead_gtr/`, `acoustic_gtr/`, `arpeggiator/`
- `produzre/groove.py`, `produzre/orchestrate/` (build, coordinator, energy,
  plan, transitions), `produzre/config/`, `produzre/export/`,
  `produzre/model.py`, `produzre/rng.py`

Write down anything new you find in the same format as the prior review
(file:line, severity, one sentence, concrete failure scenario, fix).

## Part 2: apply fixes

Work in priority order. Fix all P0 items from the prior review that you can
verify, then P1, then cleanups, then anything new you found. Use judgment on
enhancements: implement the ones that are small and clearly right, and list the
rest in your report rather than building them.

Rules for the code changes:

- Run the relevant tests after each fix, and the full suite
  (`python -m pytest -q`) before you finish. The goal is 0 failures.
- When a fix intentionally changes musical output, regenerate the affected
  goldens (`tests/generate_golden.sh` and the bass golden under
  `tests/golden/bass/`) and update pinned counts. Do this once, after the
  output-changing fixes are all in, not after each one. Where a test pins an
  exact event count with no musical meaning, replace the pin with an assertion
  about the behavior it was really guarding (ordering, range, presence).
- Add tests for `produzre/themes/`. There are none. At minimum: same seed
  gives the same bank serialization, different seed gives a different bank,
  `octave_shift` changes pitches, odd-meter cells land on the 8th/16th grid,
  and realized riff pitches actually reach the bass output.
- Keep determinism intact. After your changes, run
  `python produzre_entry.py build examples/themes_demo.yaml --strict-determinism`
  and the same for `examples/genres/rock/rock-full-arrangement.yaml` and one
  non-4/4 config; all must report byte-identical output.
- Build every example config in dry-run mode at the end and make sure none
  fail:
  `for f in $(find examples -name '*.yaml'); do python produzre_entry.py build "$f" --dry-run >/dev/null 2>&1 || echo "FAIL $f"; done`
- Decide deliberately whether theme coupling (`lock_to_riff`,
  `riff_accent_rate`, the default-on `themes_auto`) should be on by default. The
  prior review leans toward keeping auto-compose on but defaulting the drum
  theme-lock kicks to off unless a recipe or persona opts in. Whatever you
  choose, make it consistent across bass, drums, and rhythm guitar, document
  it, and note it in the changelog.
- Bump `produzre/__init__.py` to the release version and write CHANGELOG
  entries for all five commits (phrase development and energy-aware
  transitions, param plumbing / groove clock / meter, guitar refinement,
  melody engine, theme bank), plus a "Changed output" note explaining that
  goldens were regenerated and why.
- Add every new user-facing config key to the KNOWN_* sets in
  `produzre/config/validation.py` and to `docs/llm-song-config-reference.md`.
  The prior review lists them (theme keys, `pocket_ms`, `timing_jitter_ms`,
  `velocity_humanize`, `swing_16th`, the song-level `groove:` block).
- Remove or wire up dead params rather than leaving them documented. The prior
  review lists them under P2.
- Do not use em-dashes or en-dashes anywhere: not in code comments, docstrings,
  YAML comments, changelog, or docs. Use commas, colons, parentheses, or a new
  sentence.

## Part 3: rewrite the documentation

Rewrite the user-facing Markdown so it sounds like a person explaining the
tool to another musician or developer. Files: `README.md`, `CHANGELOG.md`,
`DETERMINISM.md`, `docs/llm-song-config-reference.md`, `produzre/engine/ENGINES.md`,
every `README.md` under `examples/`, `tests/README.md`, `tests/QUICKSTART.md`,
`tests/CI_INTEGRATION.md`, and `docs/design/theme-bank-architecture.md`
(for the design doc, also update it so it describes what the code does now,
and move anything still unbuilt into a clearly labelled "Not yet built"
section).

What "sounds more human" means here:

- Short sentences. One idea per sentence. Cut filler and marketing language
  ("fully-produced", "seamlessly", "powerful", "robust", "leverage").
- Say what a parameter does and when you would change it, in plain words. A
  table row like "Strength of the moving treble melody" is fine; a paragraph
  restating the table is not.
- Remove all em-dashes and en-dashes. Do not replace them with a different
  decorative punctuation; restructure the sentence.
- Remove duplicated explanations. If the same concept is explained in the
  README and in the config reference, keep the full version in one place and
  link to it from the other.
- Keep every fact that a user needs (parameter names, ranges, defaults, file
  layouts, CLI flags). Check each documented parameter against the code and
  delete the ones nothing reads. Add the ones that exist but are undocumented.
- Keep headings, tables, and code blocks; drop emoji, banners, and badges that
  do not carry information.
- Do not shorten for its own sake. If a section is already clear and accurate,
  leave it.

## Final report

End with a Markdown report written to
`docs/reviews/2026-09-13-fix-pass-report.md` containing:

1. Test results before and after (counts), example build results, and
   determinism results.
2. Every fix you applied, one line each, with file references.
3. Findings from the prior review you disagreed with or deliberately skipped,
   with a one-sentence reason each.
4. New findings you made, whether fixed or not.
5. Enhancements you chose not to build.
6. A list of every doc file you rewrote and, in a few words, what changed.

Do not commit. Leave everything in the working tree.
