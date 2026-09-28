# Composer review, round 2

Baseline: `8ecd293` on `dev`. Reviewed `7518483`, `92a4d93`, and `8ecd293`, including the performers, shared groove pass and settings merge they call. No commits, pushes or golden regeneration.

Validation: **605 tests pass** (568 baseline plus 37 new cases). `git diff --check` passes. No added em or en dash characters.

## Confirmed defects and reproducible checks

Run `.venv/bin/python -m pytest -q tests/test_composer_round2.py`. The names below identify focused reproductions in that file; each defect was reproduced before its fix.

| Defect | Reproduction | Result after the fix |
|---|---|---|
| Compound shuffle riffs use a quarter-triplet grid and miss dotted-quarter pulses | `test_shuffle_riffs_sound_each_compound_pulse`, 6/8, 9/8, 12/8 | Three steps now occupy one dotted quarter; successive riff beats remain distinct. Mixed groups use a common subdivision grid. |
| Shared swing moves corrected compound group starts | `test_compound_group_pulse_survives_shared_swing`, blues 12/8 | Group starts retain their timing; pocket and jitter still apply. |
| Equal-length meters share stale lead realizations | `test_grouping_change_does_not_recall_old_realization`, 3/4 then 6/8 | Grouping participates in memory and meter-view keys. |
| Changing meter trims an old phrase instead of phrasing in the new groups | `test_meter_view_rephrases_the_hook_in_new_groups`, seed 0 | Generated cells retain their contour vocabulary with a deterministic grouped rhythm. Authored themes remain authored. Rhythm and bass use the section's DNA view. |
| Authored hook degree pitches flatten into repeated bass roots | `test_authored_bass_response_keeps_chromatic_contour`, C, F#, G | Relative semitone contour survives, including accidentals. |
| Fast bass answers overlap | `test_fast_bass_signature_is_monophonic`, four eighth-beat notes | Duration follows the next attack instead of a 0.2-beat minimum. |
| Bass answers escape a narrow register | `test_bass_response_respects_narrow_register`, MIDI 40-44 | Octave candidates stay in bounds; clamp only if no octave fits. Integration supplies explicit bass bounds. |
| Nested lead register loses to persona or global field | `test_nested_lead_register_overrides_persona`, `test_section_param_register_overrides_global_field` | Explicit nested values win over persona defaults and earlier layers. |
| Section timing field loses to inherited params, and top-level timing never reaches composed rhythm | `test_section_field_overrides_inherited_param`, `test_zero_rhythm_timing_field_reaches_composed_performer` | Section overrides normalize across representations; zero timing jitter is honored. |
| Octave voicing is rendered as power chords | `test_octave_voicing_is_not_a_power_chord` | Requested voicing reaches the chord-shape selector. |
| Low-string gestures escape explicit high guitar bounds | `test_composed_gestures_keep_explicit_rhythm_register`, MIDI 60-72 | Final performed pitches respect the requested register. |

Additional checks cover every riff in 5/8, 7/8, 9/8, 11/8 and 12/8; invalid, nonfinite and nonpositive groupings; rest/contour changes followed by unshaped recall; nested selector ownership; recipe rate overrides; and developed bass responses with auto foreground, narrow bounds, groove memory and a modulated repeat.

## Measurements and musical reading

The identical `tools/composer_round2.py` was run in the baseline snapshot and working tree: nine genre/meter profiles, three response modes, four seeds, 108 builds per version. The section keys include final-chorus modulation. Kick alignment uses `RhythmFeatures.strong_beats`, not all drum attacks. Timing comparisons allow 0.08 beats for guitar and 0.1 beats for kick/lead coincidences. Groove lock is the most common onset pattern's bar share, averaged across sections, on a 1/12-beat grid. Response variety counts relative onset/pitch signatures; it is not a preference score. Raw-event overlap checks precede quantization.

[Metrics](composer-review-round2-metrics.json) and [lead sheets](composer-review-round2-lead-sheets.txt) are saved beside this report. Reproduce with `.venv/bin/python tools/composer_round2.py --output /tmp/composer-round2 --seeds 4 --export`.

Rhythm attacks at non-downbeat group starts, mean across four seeds with responses off:

| Meter | Before | After |
|---|---:|---:|
| 12/8 blues | 30.6% | 91.3% |
| 9/8 blues | 25.0% | 91.1% |
| 7/8 rock | 91.1% | 91.1% |
| 5/4 rock | 90.6% | 90.6% |
| 5/8 rock | 91.7% | 91.7% |
| 11/8 rock | 91.4% | 91.4% |

Musically, the boogie now articulates the dotted-quarter pulse at 0, 1.5, 3 and 4.5 in 12/8 instead of slipping through those accents on a quarter-triplet grid. Stop-time and phrase endings explain coverage below 100%; forcing every group to attack would erase those gestures.

The reported 7/8 and 5/4 consonance concern was checked with the existing instrumental anthem adapted to those meters, using each section's actual key. Before and after agree: 138/148 strong attacks are chord tones in 7/8 (93.2%), and 244/267 in 5/4 (91.4%). In 7/8 there are no held color notes without a step resolution. The six such 5/4 notes are interpretable colors: C5 over D major resolves to A4, D5 over E minor resolves to B4, and A4 over C major resolves to C5; the final chorus transposes the minor-seventh gesture. These resolve by a leap. A metric that only recognizes step resolution calls them unresolved incorrectly. No consonance weight was changed.

### Extension: developing bass answers

`instruments.bass.params.hook_response: develop` rotates the hook head, hook tail and answer motif, with the rotation advancing on returning section types. `true` keeps opening quotes. Both remain opt-in, once per four-bar phrase plus a section close. This is motivic development of responses, not a replacement bass engine.

After-fix comparison, mean of four seeds in each genre:

| Genre | Mode | Kick alignment | Groove lock | Lead coincidence | Answer shapes |
|---|---|---:|---:|---:|---:|
| funk | False | 63.4% | 49.0% | 52.0% | 0.00 |
| funk | True | 62.4% | 42.7% | 51.6% | 1.50 |
| funk | develop | 61.9% | 42.7% | 51.0% | 2.75 |
| soul | False | 72.6% | 47.9% | 28.2% | 0.00 |
| soul | True | 65.4% | 43.8% | 23.8% | 3.50 |
| soul | develop | 66.0% | 41.7% | 24.6% | 3.75 |
| rock | False | 54.2% | 74.0% | 36.2% | 0.00 |
| rock | True | 50.3% | 62.5% | 32.2% | 3.75 |
| rock | develop | 50.1% | 60.4% | 32.7% | 4.50 |

There are zero response-related adjacent overlap pairs in the 108 after builds. Greater variety does not establish better music: soul and rock lose groove repetition, and kick alignment remains below responses-off. Coincidence with lead attacks is also not inherently bad. Keep the default off in all genres.

The blues lead sheet gives a concrete reading: the first chorus answer in bar four repeats D2 under D major, quoting a repeated hook opening. On the modulated repeat, developed mode answers E2-F#2-E2-G#2 under E major. The departure and return preserve a root anchor while ending on the third. The authored-theme preview demonstrates the stronger correctness improvement: a flattened reply now retains its chromatic contour.

## Listening pairs

Eight MP3s are in `exports/review-round2/previews/`, two per case. Each is a 32-second excerpt plus synth tail, rendered with the same sketch synth and matched stereo RMS before encoding. Labels are counterbalanced across pairs. The answer key is separate in `answer-key.json` so the owner can rate pulse clarity, hook recognition, bass conversation and groove before seeing the version. No listener preference claims or weight fitting are inferred from these files.

| Pair | A | B |
|---|---|---|
| Compound blues pulse | [A](../../exports/review-round2/previews/compound_blues-A.mp3) | [B](../../exports/review-round2/previews/compound_blues-B.mp3) |
| Developed funk answers | [A](../../exports/review-round2/previews/develop_funk-A.mp3) | [B](../../exports/review-round2/previews/develop_funk-B.mp3) |
| Authored bass contour | [A](../../exports/review-round2/previews/authored_bass-A.mp3) | [B](../../exports/review-round2/previews/authored_bass-B.mp3) |
| Section meter changes | [A](../../exports/review-round2/previews/meter_changes-A.mp3) | [B](../../exports/review-round2/previews/meter_changes-B.mp3) |

The old implementation treats `develop` as truthy, so its funk A/B arm uses the existing opening-quote behavior. These excerpts exercise the audible changes, but do not cover the entire final chorus. MIDI, exact YAML, build logs and `verification.json` remain under `exports/review-round2/`. Exports are ignored by Git and must be retained separately if sharing this report.

## Compatibility, concerns and remaining risks

- All three existing composer examples retain byte-identical output in all five MIDI files versus `8ecd293`. Seven build configurations were checked with strict determinism and three `PYTHONHASHSEED` values (1, 77, 999). New grouping, authored-response, explicit-setting and develop cases intentionally change. No goldens were regenerated.
- A four-bar blues verse consumes only the first four tonic entries of the 12-bar recipe. The one-chord-per-bar rule is working; it does not compress the recipe into four bars. Tests confirm bar-relative recipe rates in 4/4, 12/8 and 7/8 and explicit-rate precedence. This is a form limitation, left unchanged to avoid silently rewriting existing songs. Use a 12-bar section or an explicit short progression; turnaround processing may add a final cadence.
- Meter adaptation preserves contour steps but changes generated rhythm; identity across radically different groups remains a listening judgment. Authored themes bypass rephrasing.
- Bounds narrower than an octave cannot always retain pitch class. Explicit register wins, using a clamp fallback. Guitar bounds also need not represent a physically fingerable shape.
- Bass responses are post-processing over engine and groove-memory output. They can reduce groove repetition and do not provide a complete DNA-derived bass counterline. Sparse engine output can still leave long spaces, including on a final chorus.
- The settings rule remains three tiers: selectors opt out, shaping/feel controls affect composed parts, legacy-only tuning is logged unused. This review does not expand the legacy tuning contract.
- Evaluation is four seeds per profile, not a labeled preference set. Synth timbre, louder mixes and more notes must not be mistaken for stronger composition. No weight fitting or preference validation was performed.

## Ranked next steps

1. Compose a kick-anchored bass counter-riff from hook and comp DNA, retaining one recognizable groove while varying phrase endings. Compare to the current optional responses with blinded ratings.
2. Give drums and instrument entrances a shared form plan, especially setup fills, a half-time bridge and a final-chorus arrival. Explicit rests and user settings must remain authoritative.
3. Collect owner A/B preferences across multiple seeds, reserve held-out songs, then consider fitting memorability/context weights.
4. Add form-aware short blues recipes explicitly, followed by numeral spelling for applied chords before repeat reharmonization.
