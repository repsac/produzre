# Release review and fix pass: dev, 2026-09-13

## Result and scope

The release fixes and documentation rewrite are in the working tree on `dev`.
Nothing was staged, committed, pushed, tagged, or branched. The two original
September review/prompt files were left untouched.

I reviewed the five-commit `main...dev` diff and current implementations across
themes/melody/ensemble, drums and training, bass/harmony, guitars/arpeggiator,
configuration, groove, orchestration, RNG, and exports. The starting diff had
145 files, 12,013 added lines, and 2,938 removed lines. I treated the earlier
review as a list of leads and checked the relevant data paths and tests.

The commits are `b1244b5` (phrases/transitions), `da46bf8` (parameters/groove/meter),
`2552bc5` (guitars), `8b4bd85` (melody), and `7624d32` (themes). Package version
is now 0.9.0; the changelog marks it unreleased until the owner makes the release.

## Validation

Tests used an isolated environment with Python 3.14.4, Mido 1.3.3, PyYAML 6.0.3,
and pytest 9.1.1. The same environment was used for the before/after checks.
The pre-theme commit was tested from a temporary archive, without changing
branches or the working checkout.

| Check | Before | After |
|---|---|---|
| `python -m pytest -q` at dev | 12 failed, 346 passed, 7 warnings | 403 passed, 0 failed, 0 warnings (41.64 seconds) |
| Pre-theme commit `8b4bd85` | 358 passed, 0 failed, 7 warnings | Baseline only; not modified |
| Every example YAML, `build --dry-run` | 166 passed, 0 failed | 166 passed, 0 failed (36.81 seconds) |
| Standalone drum goldens | Earlier review identified stale outputs | 3 passed, 0 failed |
| Bass baseline TSV and grid | Existing baseline | Regenerated once; both byte-identical to the saved baseline |
| `git diff --check` | Not a baseline claim | Pass |
| Changed Python syntax | Not a baseline claim | 89 files parsed successfully |

The 45 additional cases are in `test_themes.py` and `test_release_fixes.py`.
Targeted suites were run throughout; the last combined targeted run passed
116 tests. The full suite passed after the musical changes and regeneration.

| Strict-determinism config | Result |
|---|---|
| `examples/themes_demo.yaml` | 131 MIDI files byte-identical |
| `examples/genres/rock/rock-full-arrangement.yaml` | 340 MIDI files byte-identical |
| `examples/drums/phrasing-demo.yaml` | 31 MIDI files byte-identical; includes a 6/8 section |

Each strict check exited 0. It compares two actual exports, including full song,
stems, sections, and patterns. Timestamped metadata is outside that contract.
Validation covered MIDI structure and event behavior; no audio listening review
was performed.

All output-changing fixes were completed before running
`tests/generate_golden.sh` once and rebuilding/copying the bass baseline once.
All three drum TSVs changed. Bass stayed identical because its saved baseline
does not opt into riff coupling. Its SHA-256 values remain:

- TSV: `97ac77eb3150fa2759049ebf82578113b0e6d92e26bdd171e2c15ab68501d2c7`
- Grid: `55698aa77a5304f2ecd495c6fecd49467dc7df41557d2e283b0595c0ea6a14ed`

## Default behavior chosen

Automatic theme composition stays on. Bass `lock_to_riff`, rhythm-guitar
`lock_to_riff`, and drum `riff_accent_rate` default to 0; drum
`riff_accent_boost` defaults to 1. Lead `theme_quote_rate` stays at 0.65.
Recipes, personas, or users can opt into accompaniment coupling. The demo does
so explicitly. This prevents automatic extra kicks from replacing a genre's
intended groove while retaining shared melodic material.

Authored themes are locked by default and can opt into the arrangement arc
with `allow_development: true`. Bass quotes bass-motif pitches before falling
back to riff; rhythm guitar adopts accents while retaining chord voicings.

## Applied fixes

P0 numbers match the original review. P1/P2 labels name its unnumbered items.
References point into the resulting working tree.

- P0.1: Preserve authored and transformed octave targets before fitting the register (`produzre/themes/realize.py:141`).
- P0.2: Play realized bass-motif/riff pitches and replace overlapping generic bass material; refresh performance features (`produzre/engine/bass/__init__.py:497`).
- P0.3: Protect tonic and final notes; apply semitone snapping only under the preceding-chord-tone rule (`produzre/themes/realize.py:124`).
- P0.4: Truncate or pad cells on their eighth/sixteenth grid, including the overlong driving cell (`produzre/themes/compose.py:108`).
- P0.5: Default theme kicks off, quantize additions, leave backbeat space, and apply constraints afterward (`produzre/engine/drums/__init__.py:1209`).
- P0.6: Use the first theme per role consistently and retain all named realizations (`produzre/orchestrate/render.py:707`).
- P0.7: Resolve recipe params/voices before reading kit controls; reapply explicit global and section voices last (`produzre/engine/drums/__init__.py:480`).
- P0.8: Preserve recipe open-hat, extra-kick, double-kick, and ride choices ahead of energy fallbacks (`produzre/engine/drums/__init__.py:650`).
- P0.9: Use actual eighth-offbeat indices and feel metadata instead of inferring swing from hit-density imbalance (`tools/train_drum_recipes.py:440`).
- P0.9 presets: Set swing to zero in every shipped recipe tagged straight that previously carried a nonzero value (`produzre/resources/recipes/drums/pop_straight.yaml:36`).
- P0.10: Pass the notated meter through drums and fills so compound 6/8 uses its own anchors (`produzre/engine/drums/groove.py:245`).
- P0.11: Derive fractional bar duration from song meter when not explicitly overridden; match direct SongConfig construction (`produzre/config/parse.py:141`).
- P0.12 MIDI: Write time-signature changes at arrangement boundaries in full-song MIDI and stems (`produzre/export/midi.py:263`).
- P0.12 index: Accumulate bar positions using each section meter in the index and QUICKREF (`produzre/export/index.py:63`).
- P0.13: Share accidental Roman-numeral root spelling across bass, guitars, melody, and themes (`produzre/harmony/spelling.py:42`).
- P0.14: Resolve picked strings consistently and stop notes at the next attack on the same physical string (`produzre/engine/acoustic_gtr/__init__.py:100`).
- P0.15: Keep articulated stroke durations instead of quantizing short muted/stabbed notes to zero (`produzre/engine/rhythm_gtr/__init__.py:996`).
- P0.16 goldens: Regenerate all three drum baselines once; regenerate and verify the unchanged bass TSV/grid in the same final baseline pass (`tests/golden/fills-demo_drums.events.tsv:1`).
- P0.16 assertions: Replace arbitrary event/file-count pins with behavior checks while preserving byte-level output comparisons (`tests/test_midi_determinism.py:125`).
- P0.16 coverage: Add 19 theme cases and 26 release-regression cases, including pitches reaching bass output (`tests/test_themes.py:24`).
- P1 drumless groove: Resolve global drum and instrument recipe timing even when drums do not play (`produzre/orchestrate/render.py:534`).
- P1 triplets: Detect true triplet attacks before classifying sixteenth swing positions (`produzre/groove.py:111`).
- P1 push/pull: Use positive-ahead, -100 ms per unit, and a 25 ms limit consistently with the shared clock (`produzre/engine/drums/humanize.py:73`).
- P1 unset intensity: Treat None as missing in direct drum calls (`produzre/engine/drums/__init__.py:311`).
- P1 bass locking: Remove the second kick-lock pass so zero disables locking and rates are applied once (`produzre/engine/bass/__init__.py:854`).
- P1 locked register: Clamp kick-led bass to the requested register and clip note ends to chord/section bounds (`produzre/engine/bass/__init__.py:1592`).
- P1 locked velocity: Use the same intensity-to-base-velocity mapping in both bass renderers (`produzre/engine/bass/__init__.py:1476`).
- P1 fill timing: Swing fills and pickups with the rest of the kit, including sixteenth swing (`produzre/engine/drums/humanize.py:141`).
- P1 hat ducking: Recognize generated hat kinds during fills instead of matching only the NoteEvent timekeep label (`produzre/engine/drums/constraints.py:269`).
- P1 trainer meter: Derive the training step grid from meter; correct the shipped waltz recipe to twelve steps (`tools/train_drum_recipes.py:151`).
- P1 guitar accents: Use exact accent slots so every neighboring eighth does not become protected from thinning (`produzre/engine/rhythm_gtr/rhythm.py:513`).
- P1 lead masks: Include realized motif attacks in the rhythm mask so jazz/blues eighths survive (`produzre/engine/lead_gtr/__init__.py:471`).
- P1 short lead windows: Give short sections a usable last-half lead window (`produzre/orchestrate/ensemble.py:60`).
- P1 planned rests: Let explicit rest probability inform the planning signal as well as rendering (`produzre/engine/lead_gtr/__init__.py:157`).
- P1 half time: Place half-time anchors on whole quarter-note beats in odd meters; update cymbal/template helpers too (`produzre/engine/drums/patterns/kit.py:315`).
- P1 pedal suppression: Avoid suppressing 3/4 pedal hats merely because two kicks use a short-bar denominator (`produzre/engine/drums/constraints.py:346`).
- P1 stacked fills: Deduplicate simultaneous same-pitch/channel hits, preferring fill/louder strikes (`produzre/engine/drums/constraints.py:186`).
- P1 bass cells: Repeat or truncate rock/funk vocabulary within the actual bar length (`produzre/engine/bass/patterns/generators.py:149`).
- P1 turnarounds: Place turnarounds in the last two beats of the current meter (`produzre/engine/rhythm_gtr/transitions.py:230`).
- P1 transform boundaries: Clip straddling last-fragment notes and split displaced notes that wrap the theme boundary (`produzre/themes/transform.py:72`).
- P1 invalid lengths: Reject invalid theme lengths and transform factors instead of risking an endless loop (`produzre/themes/realize.py:88`).
- P1 antecedent: Stop forcing both final antecedent notes to the same half-cadence degree (`produzre/themes/compose.py:258`).
- P1 thinning: Restore strong grid positions so thin can retain useful strong-beat material (`produzre/themes/compose.py:108`).
- P2 release: Set version 0.9.0 and document all five commits plus changed output in CHANGELOG (`produzre/__init__.py:8`).
- P2 schema: List theme, timing, groove, placement, pattern-export, and supported instrument keys; document them in the reference (`produzre/config/validation.py:13`).
- P2 authored themes: Validate duration lists/registers/unknown keys, implement octave shorthand and authored development locks, and make length_beats an assertion (`produzre/themes/io.py:102`).
- P2 dead bass params: Remove unused swing/syncopation from bass personas and recipes (`produzre/resources/personas/bass.yml:1`).
- P2 dead guitar params: Remove unused rhythm swing/groove fields, presets, and internal duplicate timing helper (`produzre/engine/rhythm_gtr/params.py:1`).
- P2 dead coordination: Remove the unused lead-rest threshold argument (`produzre/orchestrate/coordinator.py:61`).
- P2 dead downshift: Remove the uncalled apply_downshift_to_pattern helper (`produzre/engine/rhythm_gtr/transitions.py:193`).
- P2 plan docs: Describe published texture/chord intent accurately without inventing a built-in consumer (`produzre/engine/rhythm_gtr/__init__.py:339`).
- P2 deterministic logs: Sort instrument iteration when selecting/logging pocket sources (`produzre/groove.py:219`).
- P2 directive counts: Count transition occurrences rather than occurrence keys plus aliases; fix build logging too (`produzre/cli/commands/song.py:263`).
- P2 config display: Hide private harmony parsing markers from show-config (`produzre/cli/commands/song.py:173`).
- P2 demo arc: Use the actual arc and authored locks instead of duplicate treatment tables (`tools/demo_themes.py:102`).
- P2 chord colors: Correct suspended, major seventh, diminished seventh, and half-diminished intervals through shared spelling (`produzre/harmony/spelling.py:50`).
- P2 UTC: Use timezone-aware UTC timestamps (`produzre/export/naming.py:126`).
- Small enhancement: Reuse the occurrence melody realization when creating the guide (`produzre/orchestrate/render.py:725`).
- Small enhancement: Retune tight bass to keep 0.8 kick locking without default snare doubling (`produzre/resources/personas/bass.yml:42`).
- New: composer start: Honor the requested first degree instead of moving before the opening note (`produzre/themes/compose.py:154`).
- New: bank identity: Include register/tags and active-role declaration order in bank identity (`produzre/themes/model.py:100`).
- New: rhythm coupling rate: Treat lock_to_riff as a seeded probability instead of enabling every onset for any positive value (`produzre/engine/rhythm_gtr/__init__.py:68`).
- New: drum controls: Pass hat/kick candidate placements and hat velocity/accent values into kit generation (`produzre/engine/drums/__init__.py:1089`).
- New: hat closures: Apply accent shaping to forced closures and carry the actual final hat state (`produzre/engine/drums/patterns/hats.py:194`).
- New: pedal with ride: Allow pedal chicks while the hand plays ride, with meter-aware or explicit positions (`produzre/engine/drums/patterns/hats.py:284`).
- New: snare units: Convert a custom snare placement grid back into the kit step units (`produzre/engine/drums/__init__.py:801`).
- New: per-beat density: Use four sixteenth steps per quarter-note beat in every meter (`produzre/engine/drums/patterns/utils.py:124`).
- New: hat locking: Publish top-cymbal onsets and consume them for bass lock_to_hat (`produzre/rhythm_features.py:67`).
- New: global bass offset: Read the merged global/section offset before the raw local fallback (`produzre/engine/bass/__init__.py:776`).
- New: guitar routing: Read follow_hats after merging the effective recipe params (`produzre/engine/rhythm_gtr/__init__.py:508`).
- New: lead mode: Use section mode overrides in lead pitch selection (`produzre/engine/lead_gtr/__init__.py:302`).
- New: short arpeggios: Give a positive-length short chord an attack and honor section intensity fallback (`produzre/engine/arpeggiator/__init__.py:116`).
- New: timing-only controls: Activate the feel pass for jitter/velocity controls alone and preserve explicit zero swing overrides (`produzre/groove.py:209`).
- New: timing bounds: Clamp final post-feel events to the current section window (`produzre/orchestrate/render.py:840`).
- New: pattern settings: Parse the five already-exported pattern quantization/repetition controls into SongConfig (`produzre/config/parse.py:173`).
- New: repeated exports: Keep repeated section sequence entries distinct and include local meter in pattern identity/MIDI (`produzre/export/patterns.py:338`).
- New: repeated index: Keep repeated section ids as distinct index entries (`produzre/export/index.py:68`).
- New: demo MIDI: Sort absolute note-on/off events, retain durations, write offs first at ties, and measure UTF-8 names in bytes (`tools/demo_themes.py:71`).
- New: golden runner: Read the current build export path rather than the newest directory and fail on missing goldens (`tests/test_golden_drums.py:55`).
- Test maintenance: Make the class-scoped fixture compatible with current pytest without deprecation warnings (`tests/test_chord_shapes_fixes.py:204`).
- Example cleanup: Remove ignored section beats_per_bar: 6; meter: 6/8 already gives the correct three-quarter-note length (`examples/drums/phrasing-demo.yaml:102`).

- Documentation and punctuation: rewrote the 19 requested guides listed below; removed long dashes from 80 tracked text files, including comments, YAML comments, and older guides/review text. The two original untracked September inputs are the deliberate exception, preserved as review evidence.

## Prior findings corrected or deliberately limited

- The claim that lead `rest_probability` was entirely dead with a plan was too broad. The renderer already used it; the planning signal needed the fix.
- The transition overcount was real, but the cited `negotiation.py` location was not its source. The affected build and show-config log messages now count occurrences.
- The old design's `grid` key was unsupported. I rejected it explicitly instead of creating another timing system; durations already define the theme rhythm. `octave` is now implemented, and `length_beats` is a consistency assertion.
- A song-level theme remains in quarter-note time through section meter changes. I fixed song-meter composition and drum quantization, but did not recompose the same theme for every local meter; preserving identity is deliberate and documented.
- The request to invert a hit-density swing ratio would still infer timing from the wrong evidence. The trainer now uses explicit feel metadata and correct offbeat indices instead. Straight presets were corrected without claiming a corpus retrain.
- The first-role inconsistency was fixed by making the first declaration active and adding a by-name map. I did not change every engine's public input to a list of themes.
- `rhythm.texture` and `rhythm.chords` still have no built-in readers. They remain useful published planning intent for inspection/custom engines; the documentation no longer claims they are no-ops or drive current coordination.
- No exact arbitrary bass/event/pattern count was treated as a musical requirement. Behavioral assertions replace those pins, while actual golden and byte comparisons remain.
- Bass regeneration produced identical files. I did not force a cosmetic golden change merely to make those two files appear in the diff.
- Broad claims that every song must change, or that changing drums can never affect bass, were removed. Coupling, selected recipes, and output content determine the actual effect.

## New findings

All entries below were fixed unless marked deferred. The two deferred issues
are pre-existing text-export limitations outside the changed musical paths.

| Severity | File:line | Failure scenario and disposition |
|---|---|---|
| P1 | `produzre/themes/compose.py:154` | A requested tonic opening could move before the first event; starting degree is now honored. |
| P1 | `produzre/themes/compose.py:108` | The driving cell summed to five beats despite a one-bar contract; grid-preserving truncation/padding now enforces its duration. |
| P2 | `produzre/themes/model.py:124` | Different registers, locks, or first-role selections could share a bank hash; serialization and order-sensitive hashing now distinguish them. |
| P1 | `tools/demo_themes.py:71` | Immediate note-offs made an audition effectively silent or lost overlapping durations; absolute event scheduling fixes it. |
| P1 | `produzre/engine/rhythm_gtr/__init__.py:68` | A tiny positive lock value enabled every riff accent; each onset now gets a deterministic probability draw. |
| P1 | `produzre/engine/drums/__init__.py:1089` | Parsed hat/kick placements never reached kit generation; placements and hat velocity/accent shaping now affect the rendered hits. |
| P1 | `produzre/engine/drums/patterns/hats.py:284` | Ride mode prevented pedal hats, and forced closures bypassed accent shaping; both paths now honor their controls. |
| P1 | `produzre/engine/drums/__init__.py:801` | Snare ghosts with subdiv: 8 used eighth-grid indices as sixteenths, moving 2& to 1a; conversion now preserves the beat position. |
| P1 | `produzre/engine/drums/patterns/utils.py:124` | A per-beat limit divided the bar into four groups in every meter; it now groups four sixteenths per quarter note. |
| P1 | `produzre/rhythm_features.py:67` | Bass lock_to_hat had no hat events to consume; actual top-cymbal attacks are now published and used. |
| P1 | `produzre/engine/bass/__init__.py:776` | A global bass offset was lost when the engine reread only the section; it now uses the merged instrument config. |
| P1 | `produzre/engine/rhythm_gtr/__init__.py:508` | The follow_hats switch was read from a missing params attribute before recipe merge; it now selects the intended renderer. |
| P1 | `produzre/engine/lead_gtr/__init__.py:302` | A local mode change still used the song scale for lead pitches; section mode now wins. |
| P1 | `produzre/engine/arpeggiator/__init__.py:116` | A chord shorter than note_duration produced no notes, and unset instrument intensity missed section dynamics; both cases now render correctly. |
| P1 | `produzre/orchestrate/render.py:534` | Timing snapshots taken before recipe resolution dropped instrument pockets and silent-drum groove; they now resolve the same precedence first. |
| P1 | `produzre/groove.py:209` | Jitter-only settings failed to activate timing, and zero swing could not clear defaults; presence and nonzero activation are now separate. |
| P1 | `produzre/orchestrate/render.py:840` | A positive post-render pocket could carry a note beyond the section; final clipping now enforces the endpoint. |
| P1 | `produzre/config/parse.py:173` | Five documented pattern export settings were ignored by parsing; they now reach export. |
| P1 | `produzre/export/index.py:68` | Repeated section ids overwrote index/sequence entries; occurrence keys now preserve each entry, and pattern identity includes meter. |
| P1 | `tests/test_golden_drums.py:55` | Golden checks could select another build or pass with a missing baseline; the runner now uses its own root and fails clearly. |
| P2, deferred | `produzre/export/textdump.py:194` | Pre-existing text views still label bars on the song grid during meter changes; MIDI, absolute beats, index, and QUICKREF are correct. Documented the limitation; changing all grid/tab/TSV display formats is deferred. |
| P2, deferred | `produzre/orchestrate/export_ops.py:259` | Pre-existing write_grids is parsed but does not independently select text views; documented midi_text.views as the working control and omitted write_grids from the supported-key set. Export-config API cleanup is deferred. |

## Enhancements not built

- Cross-occurrence realization caching. Realizations are shared with the guide within an occurrence; caching across harmony, mode, meter, register, treatment, and occurrence changes needs a complete cache key and profiling.
- A new genre gate for all pickup styles. Theme kicks are now opt-in and constrained; a separate stylistic policy for every existing pickup would need listening comparisons.
- A different sixteenth swing policy. The current `swing_16th` remains explicit, with omitted values inheriting half of swing; changing the groove model again is deferred.
- MIDI motif import, drum-groove themes, per-section theme selection/overrides, chord-relative theme degrees, YAML arc overrides, and multiple active themes per role.
- External-model theme composition, theme scoring, and a separate compose/audition/orchestrate interface.
- A complete retrain of drum recipes from the external MIDI corpus. The trainer and affected shipped values were fixed, but the corpus was not available as part of this pass.
- A mixed-meter redesign of TSV/grid/tab bar labeling and cleanup of the old independent `write_grids` export switch. Working alternatives and the exact limitations are documented in the export reference.

## Documentation rewritten

| File | Change |
|---|---|
| `README.md` | Source setup, a usable first song, CLI flags, actual paths, themes, MIDI limits, projects, and focused links. |
| `CHANGELOG.md` | All five commits, release fixes, arpeggiator defaults, coupling decision, and changed-output explanation. |
| `DETERMINISM.md` | Actual seed scopes, project sharing, take-independent themes, musical dependencies, and MIDI-only comparison scope. |
| `docs/llm-song-config-reference.md` | Consolidated supported schema, units, defaults, engine paths, timing, themes, kit voices, exports, and limitations. |
| `produzre/engine/ENGINES.md` | Working engine interface/example, actual timeline/plan APIs, registry priorities, features, and feedback. |
| `docs/design/theme-bank-architecture.md` | Shipped model, role selection, pitch policy, locks, defaults, and a separate Not yet built section. |
| `examples/README.md` | A navigable index, working commands, correct dependency/precedence explanation, and links to the main reference. |
| `examples/genres/README.md` | Verified file/key/tempo catalog, 30 genres plus mashup, and practical editing guidance. |
| `examples/bass/README.md` | Full file catalog, real passing/locking controls, theme pitches, and useful comparisons. |
| `examples/drums/README.md` | Demo map, voice placements, meter units, constraints, correct output paths, and validation. |
| `examples/rhythm_gtr/README.md` | Distinguish pattern/legacy/follow-hats controls; remove dead swing claims and incorrect style names. |
| `examples/lead_gtr/README.md` | Real phrasing controls, theme behavior, full file catalog, and removal of unsupported controls/count promises. |
| `examples/acoustic_gtr/README.md` | Techniques, picking patterns, treble melody, physical strings, real dynamics/timing units, and removal of base_vel. |
| `examples/orchestration/README.md` | Explain locking probabilities, density/rest choices, fills, themes, and cross-instrument effects accurately. |
| `examples/personas/README.md` | Persona names, verified precedence, examples, real controls, and the tight-bass decision. |
| `examples/seed-variation/README.md` | Targeted overrides, actual export discovery, preserved themes, and downstream musical effects. |
| `tests/README.md` | Pytest versus standalone goldens, both baseline workflows, output columns, and release checks. |
| `tests/QUICKSTART.md` | Working source setup, failures, missing baselines, and focused tests without editable-install assumptions. |
| `tests/CI_INTEGRATION.md` | CI templates running both suites, failure artifacts, optional hooks, and explicit baseline review. |

Local file links in all 19 rewritten guides were checked. No long dashes remain
in tracked text or newly authored files; original untracked review inputs were
not edited. The working tree is ready for the owner's diff and listening review.

## Docs editorial pass

Edited the 19 rewritten guides in place. The existing layout remains, apart
from the requested changelog order and example comparison groups. All changes
remain unstaged on `dev`. This section is the only addition under `docs/reviews/`;
every earlier report byte and every other review file remains unchanged.

### Files edited and voice changes

Counts are rough estimates of prose sentences added, replaced, or removed.
They exclude code, line wrapping, and simple table formatting, and include new
listening notes. The config reference also has about 30 rewritten parameter
descriptions, included in its estimate below.

| File | Sentences changed, approximately | Editorial changes |
|---|---:|---|
| `README.md` | 30 | First-use definitions, build paragraph, six verified pitfalls, direct wording, and reference pointers. |
| `CHANGELOG.md` | 33 | Existing-song changes first; New and Fixed follow, with fixes grouped by area and hashes at the end. |
| `DETERMINISM.md` | 12 | Plain repeatability language, project-sharing pointer, and a complete validating override example. |
| `docs/llm-song-config-reference.md` | 50 | First-use definitions, clearer descriptions, 17 uniform parameter tables, and all 189 original data rows retained. |
| `produzre/engine/ENGINES.md` | 12 | Direct instructions for engine authors and links to preset and constraint details. |
| `docs/design/theme-bank-architecture.md` | 34 | Active descriptions of planning and realization; public controls point to the config reference. |
| `tests/README.md` | 11 | Clearer golden-file instructions and pointers to output and determinism details. |
| `tests/QUICKSTART.md` | 9 | Direct setup and failure guidance, with one baseline-update reference. |
| `tests/CI_INTEGRATION.md` | 7 | Direct CI instructions and links to baseline checks and environment requirements. |
| `examples/README.md` | 13 | Removed the repeated sound caveat and linked shared setup and preset rules. |
| `examples/acoustic_gtr/README.md` | 3 | Listening note with the actual technique settings and simpler performance advice. |
| `examples/bass/README.md` | 38 | 33 listening notes grouped by folder; removed the repeated sound caveat and unsupported name. |
| `examples/drums/README.md` | 17 | 12 listening notes in three groups, with values and shorter output guidance. |
| `examples/genres/README.md` | 1 | Replaced the sound-patch caveat with the recipe reference; retained file/key/BPM table. |
| `examples/lead_gtr/README.md` | 10 | Seven listening notes with actual values and supported phrasing controls. |
| `examples/orchestration/README.md` | 9 | Direct coordination advice and references for locking, themes, and seed dependencies. |
| `examples/personas/README.md` | 8 | Four listening notes, including the controlled bass persona comparison. |
| `examples/rhythm_gtr/README.md` | 6 | Two listening notes, including the renderer switch needed to hear legacy sustain controls. |
| `examples/seed-variation/README.md` | 9 | Corrected the shared-title description and linked the seed contract. |

The 17 parameter tables contain 171 rows. The section-intensity and suggested-
progression lookup tables retain their 18 rows and their descriptive headings.
Defaults that come from presets say `recipe` or `persona`; numeric preset and
engine fallback values remain in the descriptions. All 59 instrument/persona
example YAML files were read before writing their listening notes.

### Verification results

Temporary scripts ran from the repository root using
`/tmp/produzre-review-venv/bin/python` (Python 3.14.4, PyYAML 6.0.3).
The checkers are `/tmp/check_produzre_docs.py`,
`/tmp/check_produzre_parameters.py`, and `/tmp/produzre_editorial_audit.py`.
Their JSON results are `/tmp/produzre-doc-check-results.json`,
`/tmp/produzre-parameter-check-results.json`, and
`/tmp/produzre-editorial-audit-results.json`. No checker was added to the repo.

Copied check output:

```text
Markdown files scanned: 31
Complete YAML songs: 3; failed: 0
YAML fragments skipped: 41
Bash commands checked with --help: 47; failed: 0
Relative/anchor links checked: 286; failed: 0
Tracked long-dash hits: 0
Long-dash scan: 485 tracked files; rg exit 1; output empty
README/config reference files scanned: 15
Documented identifiers found under produzre/: 432
Missing identifiers: {}
Uniform parameter tables: 17; parameter rows: 171; all table data rows: 189
Protected source/config changes during editorial pass: 0
Other review files changed: 0
Existing report prefix preserved: true
Git index unchanged: true
Branch: dev
```

The Markdown scan includes tracked and untracked, non-ignored Markdown files
throughout the repository, including the protected reviews. Each complete YAML
block was written to a temporary file and passed to `produzre_entry.py validate`.
All three now exit 0:

| Complete YAML block | Exit |
|---|---:|
| `DETERMINISM.md:45` | 0 |
| `README.md:53` | 0 |
| `docs/llm-song-config-reference.md:14` | 0 |

The first check caught the missing section type in the determinism excerpt.
Adding its type, length, and arrangement made it a complete drum-only song.

Every matching Bash command was checked with `--help`, preserving its arguments
and joining continued lines. Shell loop variables and sample filenames stayed
literal because help exits before loading them. Shell operators were excluded;
no loop, project import, executable build, or golden regeneration was run.
These are CLI checks, not new musical rendering or listening results.

| Markdown file | Matching commands checked; all exit 0 |
|---|---:|
| `DETERMINISM.md` | 3 |
| `README.md` | 15 |
| `examples/README.md` | 7 |
| `examples/acoustic_gtr/README.md` | 1 |
| `examples/bass/README.md` | 2 |
| `examples/drums/README.md` | 2 |
| `examples/genres/README.md` | 3 |
| `examples/lead_gtr/README.md` | 1 |
| `examples/orchestration/README.md` | 1 |
| `examples/personas/README.md` | 1 |
| `examples/rhythm_gtr/README.md` | 2 |
| `examples/seed-variation/README.md` | 1 |
| `produzre/engine/ENGINES.md` | 2 |
| `tests/QUICKSTART.md` | 1 |
| `tests/README.md` | 5 |

Relative links were checked against existing files and directories; Markdown
fragments were checked against heading anchors. The dash scan checked U+2013
and U+2014 in all 485 tracked Markdown, YAML, and Python files. `rg` provides
the equivalent Unicode scan on this machine; exit 1 means no matches.

The identifier scan checked backticked names and inline assignments/comparisons
in all 14 READMEs plus the config reference. Dotted keys were checked by their
components because the code reads nested mappings. Five absent names were
removed from the rewritten guides: `passing_tone_rate`, `motif_strength`,
`approach_tones`, `leap_probability`, and `leap_min_semitones`. None remains
in those guides. Filename mentions, the sample output label `hats_closed`,
and the directory name `analysis_output` are not song parameters.
The `input_dir` and `archive_dir` arguments in `tools/README.md` belong to
scripts under `tools/`, where they are implemented; those valid CLI docs were
retained. No absent song-config parameter remains in the scan.

### YAML fragments skipped

These blocks lack either top-level `song` or `sections`, so the requested
complete-song check does not apply. Locations identify the opening fence.

| Location | Fragment starts with |
|---|---|
| `README.md:96` | `instruments:` |
| `README.md:121` | `themes:` |
| `README.md:140` | `groove:` |
| `README.md:213` | `exports:` |
| `docs/design/theme-bank-architecture.md:50` | `themes:` |
| `docs/llm-song-config-reference.md:137` | `harmony:` |
| `docs/llm-song-config-reference.md:203` | `groove:` |
| `docs/llm-song-config-reference.md:240` | `themes:` |
| `docs/llm-song-config-reference.md:343` | `instruments:` |
| `docs/llm-song-config-reference.md:537` | `exports:` |
| `docs/produzre-claude-project-setup.md:206` | `version: 1` |
| `examples/acoustic_gtr/README.md:37` | `# Inside an instruments block:` |
| `examples/bass/README.md:102` | `# Inside an instruments block:` |
| `examples/drums/PERFORMANCE.md:14` | `sections:` |
| `examples/drums/PERFORMANCE.md:49` | `sections:` |
| `examples/drums/PERFORMANCE.md:87` | `sections:` |
| `examples/drums/PERFORMANCE.md:169` | `sections:` |
| `examples/drums/PERFORMANCE.md:181` | `sections:` |
| `examples/drums/PERFORMANCE.md:193` | `sections:` |
| `examples/drums/PERFORMANCE.md:220` | `sections:` |
| `examples/drums/PHRASING.md:24` | `sections:` |
| `examples/drums/PHRASING.md:44` | `sections:` |
| `examples/drums/PHRASING.md:100` | `fill_rate: 1.0   # Always place fills at phrase boundaries` |
| `examples/drums/PHRASING.md:110` | `fill_length: "short"   # 1 beat (fast fills)` |
| `examples/drums/PHRASING.md:122` | `fill_chatter: 0.0  # No chatter (only phrase-end fills)` |
| `examples/drums/PHRASING.md:142` | `sections:` |
| `examples/drums/PHRASING.md:159` | `verse:` |
| `examples/drums/PHRASING.md:178` | `chorus:` |
| `examples/drums/PHRASING.md:195` | `intro:` |
| `examples/drums/README.md:39` | `# Inside an instruments block:` |
| `examples/drums/TRANSITIONS.md:23` | `sections:` |
| `examples/drums/TRANSITIONS.md:37` | `# Disable pickups (no snare roll before section changes)` |
| `examples/drums/TRANSITIONS.md:57` | `arrangement:` |
| `examples/orchestration/README.md:15` | `# Inside an instruments block:` |
| `examples/personas/README.md:6` | `instruments:` |
| `examples/rhythm_gtr/README.md:19` | `# Inside an instruments block:` |
| `produzre/engine/ENGINES.md:12` | `engines:` |
| `produzre/engine/ENGINES.md:48` | `sections:` |
| `tests/CI_INTEGRATION.md:12` | `name: Tests` |
| `tests/CI_INTEGRATION.md:43` | `test:` |
| `tools/README.md:106` | `# Flat` |

### Decisions and limits

- Kept quoted meter as the documented convention, but did not claim that unquoted `4/4` becomes a date. PyYAML 6.0.3 reads unquoted `4/4`, `6/8`, and `7/8` as strings.
- Described intensity as normally 0-1. The parser accepts numeric values beyond that range, so the docs do not claim a hard limit.
- Kept the genre pitfall, with the actual checks: `show-config` exposes the requested spelling and loaded presets; `build -v` reports the selected recipe. An unmatched `rokc` probe returned no recipe and emitted no warning. Matching also permits genre substrings, so a typo can sometimes match another family.
- Kept one full explanation of preset precedence and harmony setup in the config reference, seed/take/variation in the determinism guide, and project sharing and output columns in the root README. Other guides use short pointers. The explicitly requested first-use definitions remain in both the README and config reference.
- Preserved the genre catalog and comparison folder table. Instrument file titles were replaced with listening notes as requested. The bass articulation, rhythm, fill, and groove files change several settings or seeds, so they are described as starting points rather than controlled comparisons.
- The sustained-chords example selects a pop recipe, which enables pattern rendering. Its listening note tells you to set `use_patterns: false` to hear its legacy sustain settings. Its YAML was left unchanged.
- All five seed-comparison YAML files use the same title. Corrected the guide to use printed export directories to distinguish them. The YAML files were left unchanged.
- Kept technical limits that affect a user decision, including mixed-meter text labels, the legacy `write_grids` behavior, and unimplemented theme inputs. Shortened defensive phrasing without hiding those limits.
- Left other Markdown outside the 19-file editorial scope unchanged. It participated in the requested repository-wide checks. Protected reviews were inspected by the checkers but not edited.
- No source, YAML, golden, dependency, or Git-index changes were made during this editorial pass. The existing test results above belong to the earlier fix pass; the verification here covers the documentation changes.

