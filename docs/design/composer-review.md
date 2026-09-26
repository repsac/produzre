# Composer review and extension

Reviewed commits `bc56299` and `8c16764`. Changes are uncommitted. No goldens
were regenerated. The baseline suite passed all 505 tests before edits.

## Confirmed defects and reproductions

All reproductions below were run against the pre-fix implementation and then
retained as regressions in `tests/test_composer_review.py`. Test names below
omit the `test_` prefix.

| Defect | Reproduction and observed failure | Fix |
|---|---|---|
| Walks targeted the next attack rather than harmonic change | `walk_targets_next_harmony_not_next_attack`: C followed by F, with intervening C strums, targeted C (0) instead of F (5). | Find the next span whose pitch-class content changes. |
| Arpeggio state leaked into walks | `walk_does_not_inherit_arpeggio_index`: two arpeggio attacks made a single walk use distance 2 rather than leading-tone distance 0. | Only arpeggio events inherit the arpeggio counter. |
| Low-key power chords left standard guitar range | `power_shape_stays_above_low_e`: D3 power shape [50, 57, 62] became [38, 45, 50]. | Only lower whole shapes when the bottom remains at least MIDI 40; keep walk approaches above low E too. |
| Counter-lines skipped an active chord | `guide_starts_inside_a_long_chord`: a phrase starting at beat 4 inside a six-beat chord began at beat 6. | Include overlapping spans and clip the first span to phrase entry. |
| Explicit lead controls were ignored | Rest probability, contour, and a zero bend rate had no effect on the composed line. | Narrowed after review: they now shape the composed line and performance (`rest_probability_shapes_the_composed_line`, `contour_style_shapes_the_composed_line`, `zero_bend_rate_removes_composed_bends`). Legacy-only tuning is logged as unused. |
| Explicit rhythm controls were ignored | Density, voicing, palm mute, and dynamics had no effect on composed comping. | Narrowed after review: the composed performer honors them (`rhythm_density_thins_the_composed_part`, `rhythm_palm_mute_turns_strums_into_chugs`); only part selectors such as `style` or `recipe` keep the previous engine. |
| User overrides read as persona defaults | Values in a section's nested `extra:` block were treated as persona-provided because the persona tag still listed the key. | Values in the nested block always count as the user's. |
| Slide graces violated MIDI range and monophony | `slide_grace_is_monophonic_and_midi_safe`: a slide to MIDI 1 created pitch -1 and overlapped the previous note. | Clamp grace pitch and clip against actual performed attacks. |
| Groove recall ignored top-level settings | `groove_recall_distinguishes_top_level_settings`: low and high bass registers shared the same memory key. | Include dataclass settings and canonical nested params; retain intensity scaling. |
| Numeric lead ranges were widened | `explicit_numeric_register_is_not_widened`: [60, 67] became [60, 74]. | Preserve numeric bounds and enforce them after realization, including solos. Recall distinguishes registers. |
| DNA fitting ignored section overrides | `dna_fitter_uses_section_key_and_meter`: F# major, 7/8 source chords were scored as E minor, 4/4. | Select the actual source context and fit verse candidates using their own context. |
| Realization used cell-relative metric position | `realizer_uses_section_metric_position`: an attack at section beat 1.5 was weighted as beat 0. | Use absolute section-relative attack modulo bar length. |
| Transitions reintroduced lead overlaps | `transition_pass_keeps_composed_lead_monophonic`: the band-with-singer example had five overlapping pairs in exported MIDI even after performer cleanup. | Clip the completed lead timeline after transition ramps. |

Additional coverage exercises one- and two-bar sections, no-chorus builds,
6/8, 7/8, 5/4, non-bar-aligned harmonic rhythm, key changes, authored chromatic
themes, every comp riff in odd meters, numeric solo ranges, canonical memory
signatures and subprocess MIDI comparison under different hash seeds.

## Chosen extension and measurements

The extension adds metric and harmonic exposure scoring to the listener's
choice among generated developments. This addresses a local, measurable gap:
the interval prior cannot distinguish a weak passing tone from a sustained
non-chord tone across a harmony change. It also has a smaller musical scope
than introducing bass DNA or reharmonization during a correctness review.

The score integrates non-chord-tone duration across chord spans, weighted by
metric position, with a discount for short stepwise passing tones. It is a
separate heuristic cost. The existing information-content model, its learned
counts and calibrated targets remain unchanged. Authored cells do not enter
variant selection.

Reproduce with:

```bash
.venv/bin/python tools/composer_review.py --seeds 24 --lead-sheets
.venv/bin/python tools/musicality.py --corpus ~/Downloads/MIDI-movie_themes
.venv/bin/python -m pytest tests/test_composer_review.py -q
.venv/bin/python -m pytest -q
```

The controlled A/B uses 24 seeds, rock/pop/funk, and four paired
bar-length/chord-rate settings: (4, 4), (3, 1.5), (3.5, 2), (5, 3).
There are 288 eight-bar section cases per arm. Both arms include the bug
fixes; the contextual scoring weight is the only A/B variable.

| Metric | Context off | Context on |
|---|---:|---:|
| Weighted harmonic exposure, lower is better | 0.082692 | 0.078047 |
| Downbeat chord-tone fraction | 0.581597 | 0.582031 |
| Step ratio | 0.392112 | 0.383065 |
| Leap recovery | 0.357152 | 0.351810 |
| Exact phrase repeats | 0.075231 | 0.076389 |
| Rhythm recurrence | 0.624566 | 0.618490 |
| Interval self-information, bits | 3.890730 | 3.884388 |

Exposure improves 5.6%; downbeat consonance barely changes. Step motion,
leap recovery and rhythmic recurrence slip slightly. This is evidence for a
narrow harmonic improvement, not evidence of general preference or parity
with ML-generated music. Exposure is also the optimization objective, so it
is not an independent quality judgment.

The 110-file human corpus still yields medians of 0.516 step ratio, 0.286
exact repeats, 0.686 rhythm recurrence and 2.654 bits self-information. The
short section stress test is not directly comparable to the architecture
document's whole-song benchmark. Corpus files lack verified chord labels, so
no human harmonic-exposure baseline is claimed.

Raw results: [metrics](composer-review-metrics.json) and
[printed lead sheets](composer-review-lead-sheets.txt).

## Musical reading

In the printed seed-0 rock 4/4 chorus, bars 1, 3 and 7 retain the hook's
rhythmic identity. The fifth bar develops it and the last bar settles on D
against bVII. The answers' held notes make the line breathe. This reads as a
recognizable phrase rather than independent bar draws.

The odd-meter sheets show the remaining compromise: 5/4 often leaves a gap
at the end of a phrase derived from four beats, and 7/8 truncates a familiar
figure instead of inventing an asymmetric grouping. In 6/8, duration fitting
works but dotted-quarter grouping is not modeled explicitly. Rapid harmony
changes can leave sustained non-chord tones; the contextual listener reduces
exposure only where a phrase has candidate variants, preserving established
hooks and authored material.

The walk reproduction is musically concrete: a C figure preparing F should
use E as its final chromatic approach. Previously it prepared C again because
another C strum occurred before F. Fixing the target and removing arpeggio
state from walk distance makes that intention consistent.

## Validation and remaining risks

- The final full suite passes 543 tests, including 38 new regression and
  property cases. No golden files changed.
- All three composer examples and a no-chorus authored-theme stress song
  passed strict determinism at `PYTHONHASHSEED` 1, 77 and 999. Each run builds
  twice. All five MIDI files per config also matched across hash seeds.
- The stress song combines 1-bar 6/8, 2-bar 7/8 and 5-bar 5/4 sections,
  C/F#/D keys, chord rates 1.5/2/3, and an authored chromatic theme.
- Raw exported lead MIDI has zero overlapping pairs in all four configs,
  including grace notes. Counts are 316 anthem, 168 singer, 275 funk and 43
  stress-song notes. Use raw MIDI attacks for this check: the musicality
  tool quantizes onsets for pattern analysis and can report false overlaps.
- Numeric bounds are hard limits. Very narrow ranges may force octave folding
  or constrain an authored pitch. Named presets still allow headroom.
- The listener's contextual weights and memorability weights remain hand-set.
  Its contextual score is not a learned syncopation model.
- Comp riffs still fit a predominantly 4/4 vocabulary to other meters.
  Bass does not yet derive material from DNA, and repeated sections are not
  reharmonized. Guitar pitch-range checks do not prove every composite
  gesture is physically playable on a particular tuning.
- The musical assessment here is a reading of printed notes and quantitative
  checks, not a blinded listening evaluation. No new perceptual quality claim
  is justified by these measurements alone.

Next steps: first add explicit meter grouping and a listening comparison of
odd-meter phrases; then an opt-in bass response derived from hook attacks,
measured for kick alignment, repetition and lead/bass competition. Fit
memorability and contextual weights only with a labeled preference set and
held-out evaluation. Applied-chord spelling should precede reharmonization.
