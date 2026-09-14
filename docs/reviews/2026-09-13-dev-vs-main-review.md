# Review: dev vs main (2026-09-13)

Scope: the five commits on `dev` ahead of `main` (b1244b5 .. 7624d32), 145 files,
+12013 / -2938 lines. Reviewed by slice (themes/melody, orchestration/core,
bass/harmony, drums, guitars); every finding marked "verified" was reproduced
by reading the code or running a probe against the package.

## Branch status

| Check | Result |
|---|---|
| Commits ahead / behind main | 5 ahead, 0 behind (fast-forward mergeable) |
| Test suite on dev HEAD | 12 failed / 346 passed |
| Test suite on 8b4bd85 (commit before theme bank) | 358 passed |
| Test suite on main | 163 passed |
| All 166 example configs, `build --dry-run` | 0 failures |
| `--strict-determinism` (themes_demo, rock-full, soul-full) | byte-identical |
| References to deleted modules (`seeds.py`, `lead_gtr/types.py`) | none remain |
| `produzre.__version__` | still `0.8.0`; CHANGELOG says `0.9.0` |
| CHANGELOG | only covers da46bf8; nothing for melody, guitar, ensemble, themes |
| User docs for theme bank (`themes:`, `themes_auto`, `lock_to_riff`, `riff_accent_*`) | none outside the design doc |

All 12 failing tests were introduced by 7624d32 (theme bank). Auto-composed
themes are on by default, so every song's bass and drum output changed, and the
pinned counts and bass golden were never regenerated. The design doc (section
10) anticipated this and calls for a one-time golden regeneration plus a
changelog note; that step was not done. `tests/test_golden_drums.py` is a
script, not collected by pytest, and also fails against the stale goldens.

Failing: `test_bass_articulation` (2), `test_bass_determinism` (2),
`test_bass_groove` (3), `test_bass_harmony` (1), `test_bass_solo` (1),
`test_integration_e2e::test_param_plumbing_user_params_reach_engine`,
`test_meter_support` (2).

## P0: fix before release

### Theme bank

1. **Theme realization ignores the octave field** (`produzre/themes/realize.py:143`).
   `fit_pitch_to_range(60 + pc, ...)` only uses the pitch class, so
   `octave_shift` in the arc, authored `5+`/`5-` markers, and the composer's
   contour all collapse to nearest-neighbour voice leading. Verified:
   `octave_shift` and `quote` produce identical pitches. The first note of every
   theme is placed nearest C4, so the demo riff (register 40..55) starts on E3.
   Fix: compute a target pitch from register centre + degree + accidental +
   12 * octave and choose the in-register candidate nearest that target.

2. **Riff pitches are never played.** Only `lead_gtr` reads realized theme
   notes (`themes.realized.<sec>["melody"]`). Bass, drums, and rhythm_gtr call
   `get_theme_onsets(..., "riff")` and use onsets only; nothing reads
   `bass_motif`. The design doc's "riff stated by bass/rhythm_gtr" is not
   implemented, so the riff is audible only as accent placement.

3. **Chord-tone snapping rewrites the tonic and the 4th** (`realize.py:120-135`).
   Snapping is unconditional; over `V` in C the tonic becomes B, over `I` the 4th
   becomes E. The demo riff's `4` becomes G# on every I bar. Never snap degree 1
   or an occurrence's final note; follow the doc's memory rule.

4. **Non-4/4 cells are scaled uniformly and land off-grid** (`themes/compose.py:108`).
   In 3/4 an 8th cell becomes 0.375-beat events; `kick_theme_lock` then places
   kicks at beat 1.375, which is what breaks the two meter tests. Also
   `compose.py:236` reads the raw `song.beats_per_bar` int, so a `7/8` song
   composes 4-beat cells, and section meter overrides are ignored. Fix: build
   cells on the target meter's 8th/16th grid (truncate or pad, never scale), and
   quantize theme-lock kicks to the drum step grid.

5. **Theme-lock kicks are on by default and bypass constraints**
   (`engine/drums/__init__.py:1188-1240`). `riff_accent_rate` defaults to 0.5,
   runs after `apply_constraints`, and overrides genre grooves: a reggae one-drop
   verse now gets kicks on 1, 1&, 2e, 2&, 4. Default to 0 unless recipe/persona
   opts in, skip onsets within a 16th of a snare backbeat, and run before
   constraints.

6. **Two themes with the same role publish inconsistent data**
   (`orchestrate/render.py:681-694`). The guide is built from the first MELODY
   theme while `themes.realized` keeps the last. Publish a list per role or key
   by name.

### Drums

7. **Recipe voices are merged after every voice block was read**
   (`engine/drums/__init__.py:495-763` vs `:923`). `snare.articulation:
   crossstick` (reggae, bossa), `hats.pedal` (jazz), funk kick/snare/hat voices,
   and recipe `fill_rate` never take effect. Verified: reggae renders snare 38,
   never 37. Move recipe resolution to just after the `params_m`/`voices_m`
   merge.

8. **Energy defaults overwrite recipe groove fields** (`:598-631`, `:978-983`).
   `double_kick_rate`, `kick_extra_rate`, `open_hat_rate` are filled from energy
   when the voice block is silent, then applied unconditionally to the template.
   Verified: metal verse renders 0 double kicks despite `double_kick_rate: 0.5`.
   Apply energy defaults only when neither user nor recipe supplies the field.

9. **Trainer swing heuristic is inverted** (`tools/train_drum_recipes.py:461-475`).
   `odd/even < 0.3 -> swing 0.35` gives straight recipes swing (pop_straight,
   punk_triplet, motown, progressive, songwriter_straight, extreme_metal_straight
   carry 0.35; disco/hip_hop/rnb/electronic carry 0.2). On main this only swung
   the drums; the new groove clock now swings the whole band. Verified: a
   `genre: pop` song resolves `swing=0.35` and bass "&" notes land at 0.607.
   Invert the ratio, regenerate; short term zero swing on every `feel: straight`
   recipe. `and_steps` at `:434` are the 16th e/a positions, not the "&"s.

10. **6/8 renders as 3/4** (`engine/drums/groove.py:296-310`, `fills.py:133`).
    `Meter.beats_per_bar` normalizes 6/8 to 3.0, so the backbeat lands on the
    third 8th instead of the fourth; `is_6_8` only fires for 6/4. Pass the meter
    numerator/denominator into the engine and derive compound-meter backbeats.

### Meter (song level)

11. **Song `meter` never drives bar length** (`config/parse.py:140`,
    `model.py:422`, `harmony/utils.py:84`). `beats_per_bar` is an independent,
    undocumented int defaulting to 4. Verified: `meter: "3/4"`, `bars: 4` gives a
    16-beat section on a 3/4 grid; `7/8` cannot be expressed. Only the section
    `meter:` override path works. Default `beats_per_bar` to
    `parse_meter(meter).beats_per_bar` (float) when unset.

12. **Full-song MIDI emits a single time signature** (`export/stems.py:82-90`,
    `export/index.py:72-73,165-166`). Sections that override meter get no meta
    event in the full-song file and QUICKREF bar counts use the song meter.

### Harmony

13. **Borrowed-chord spelling differs between bass and everything else**
    (`engine/bass/harmony.py:141-147` vs `rhythm_gtr/__init__.py:297`,
    `acoustic_gtr/__init__.py:87`, `melody.py:81`, `themes/realize.py:56`).
    Bass spells accidental numerals against the major scale (C minor bVII = Bb);
    guitars, melody, and themes spell against the mode scale (bVII = A). The new
    jazz/latin/rnb/soul minor recipes (`i bVII bVI V7`) clash on every bar.
    Move the major-scale spelling into the shared numeral parser.

### Guitars

14. **Acoustic fingerpicking maps logical strings to physical strings
    inconsistently** (`engine/acoustic_gtr/__init__.py:105-127`, `:444-465`).
    `_pitch_for_pattern_hit` remaps onto played strings but
    `_next_same_string_beat` compares raw logical indices. On a 4-string D shape
    the treble hit lands on the bass root and thumb/finger collide on the G
    string. Verified: 13 same-pitch overlaps in one render. Resolve the physical
    string once per hit and compare physical strings.

15. **Duration quantization deletes palm-muted and stabbed strums**
    (`engine/rhythm_gtr/__init__.py:929`, `:978`). With `humanize_timing: 0`,
    durations under half a slot round to 0 and the exporter drops them. Verified:
    28 of 73 notes vanish in a chugs/palm-mute chorus. Drop duration
    quantization or floor it at half a slot.

### Tests

16. Regenerate the bass golden and drum goldens after items 1-5 and 7-8 are
    settled, then update the pinned counts. Replace brittle exact-count pins
    with intent assertions where possible. Add tests for `produzre/themes`
    (there are none; the design doc lists three golden tests).

## P1: should fix

- **Groove feel ignores drums when drums are absent from a section**
  (`orchestrate/render.py:557`). Drumless intros play straight while the rest
  swings. Fall back to the global drums params.
- **Triplet-grid notes get 16th swing** (`groove.py:364-370` with
  `lead_gtr/rhythm.py:66-67`). Lead uses a 1/3-beat grid for jazz/swing/blues;
  a 0.124 window classifies 1/3 as "e". Check the triplet grid first.
- **`push_pull` sign and scale differ by instrument** (`groove.py:30` vs
  `drums/humanize.py:91`). Drums: positive = later, 10 ms/unit. Clock:
  positive = ahead, 100 ms/unit. Pick one convention.
- **`SectionConfig.intensity` is `None` off the orchestrated path**
  (`model.py:299`, `drums/__init__.py:308`), so `float(...)` raises on direct
  engine calls. Treat `None` as missing.
- **`lock_to_kick` applied twice, and 0.0 cannot disable it**
  (`engine/bass/__init__.py:854-881`). Effective rate 0.96 at reggae's 0.8;
  classical's zero still doubles 60% of kicks.
- **Rhythm-locked bass never clamps to register** (`engine/bass/__init__.py:1638`).
  Key B, `VII`, octave 3 gives A4.
- **Legacy and locked bass use different velocity mappings** (`:614` vs
  `:1573`): 49 vs 91 at intensity 0.7.
- **Fills and pickups are exempt from swing** (`drums/humanize.py:211`), so in
  the new 0.6+ shuffle recipes fill 8ths play straight against swung hats.
- **Fill hat-ducking is a no-op on the engine path** (`drums/constraints.py:319`,
  `:379`): ducking tests `kind == "timekeep"`, which only exists on the
  NoteEvent path. 10 of 41 fill steps in the golden still carry a hat.
- **Trainer quantizes every file to 16 steps regardless of meter**
  (`tools/train_drum_recipes.py:52`, `:184`), so `waltz.yaml` step indices are
  wrong on the new 12-step grid.
- **Rhythm_gtr accent proximity marks every slot** (`rhythm_gtr/rhythm.py:528`,
  `__init__.py:682`, `:854`): 1-slot proximity at 8th subdivision plus drum
  accents plus riff onsets make all 8 slots accents, so the lead-window density
  budget thins nothing.
- **Lead motif offsets not on the genre grid are silently dropped**
  (`lead_gtr/__init__.py:476-489`): blues/jazz templates contain 0.5-based
  offsets that a 1/3-beat mask never allows.
- **Lead windows: sections under 2 bars get no window and `rest_probability`
  is dead when a plan exists** (`orchestrate/ensemble.py:62-90`,
  `lead_gtr/__init__.py:164`).
- **Half-time snare and cymbal anchors assume even step counts**
  (`drums/__init__.py:1012`, `patterns/kit.py:306`, `cymbals.py:194`,
  `patterns/utils.py:154`): 5/4 half-time snare lands on the & of 3.
- **Pedal hats vanish in 3/4** (`constraints.py:372`): 2 kicks / 3 beats exceeds
  the 0.6 density limit.
- **Fill strokes stack on the backbeat snare** (same tick, same pitch) in the
  fills-demo golden.
- **`rock_riff` / `funk_16ths` bass cells and rhythm_gtr turnarounds hardcode
  4/4 positions** (`bass/patterns/generators.py:140`,
  `rhythm_gtr/transitions.py:296`).
- **`fragment(keep="last")` drops straddling events and `displace` truncates
  wrapped durations** (`themes/transform.py:75-102`).
- **`realize_theme` loops forever when `length_beats <= 0`** (`realize.py:105`),
  reachable via `augment factor=0` in the demo tool.
- **Antecedent always ends on two identical notes** (`compose.py:145-151`).
- **`thin` keeps one event on scaled cells** because `_is_strong_beat` never
  fires on 0.875-style offsets.

## P2: cleanups and docs

- Bump `produzre/__init__.py` to `0.9.0` (or whatever the release is) and add
  CHANGELOG entries for b1244b5, 2552bc5, 8b4bd85, 7624d32.
- Add `theme_quote_rate`, `lock_to_riff`, `riff_accent_rate`,
  `riff_accent_boost`, `song.themes_auto`, `pocket_ms`, `timing_jitter_ms`,
  `velocity_humanize`, `swing_16th`, and the song-level `groove:` block to
  `config/validation.py` KNOWN_* sets and to `docs/llm-song-config-reference.md`.
- Document the `themes:` block in the config reference (design doc section 8
  is the only description; `grid:` and `octave:` keys there are ignored by
  `io.py`, and `length_beats` is redundant with the duration sum).
- Dead or unread params: bass recipe `syncopation` and `swing`; rhythm_gtr
  `swing` (params, recipes, README); lead README `motif_strength`,
  `approach_tones`, `syncopation`, `leap_probability`, `leap_min_semitones`;
  `coordinator.lead_rest_threshold`; `rhythm_gtr/transitions.py
  apply_downshift_to_pattern` (still no callers).
- `contribute_plan` docstrings in rhythm_gtr say "no-op" but now write
  `rhythm.texture` / `rhythm.chords`; no reader exists for those keys.
- `groove.py:229-259` iterates a set for `pocket_source`; log line depends on
  hash seed. Iterate sorted.
- `negotiation.py:311` reports 2N transition directives (occurrence key plus
  alias).
- `_chord_rate_default` leaks into `show-config` output.
- README section filename pattern is stale (`<song>_<inst>_<NN>_<section>.mid`
  is what is written).
- `tools/demo_themes.py:40-56` duplicates `arc.py` tables.
- `bass/harmony.get_chord_tones` ignores `sus` and mis-spells `°7`;
  `melody.chord_pitch_classes` spells `IVmaj7` with a minor 7th and treats
  `ø` as a plain minor 7th.
- `datetime.utcnow()` deprecation in `export/naming.py:126`.

## Enhancements

- Have bass state the riff pitches at locked onsets (from `bass_motif` or
  `riff`) so the headline feature is audible.
- Cache realization per (theme, transform) across repeated section ids;
  `build_themed_guide` currently re-realizes what `render.py` already did.
- Gate `kick_theme_lock` and pickup styles by genre or recipe (one-drop,
  bossa, jazz should not double the riff on kick).
- Recipe resolution scores on `song.meter` only; sections in 6/8 or 3/4 never
  get the meter bonus.
- `swing_16th` default of `swing * 0.5` compresses the last 16th; consider
  applying `swing` to the "a" only.
- Bass `tight` persona now has live `lock_to_kick 0.8` / `lock_to_snare 0.3`
  (dead on main); retune deliberately, snare doubling is not a tight idiom.
- Arpeggiator defaults changed (`note_duration` 0.25 to 0.5, pattern `up` to
  `phrase`); note in CHANGELOG.
- Consider a chord-relative degree escape hatch and a per-section `themes:`
  override (design doc open questions 1 and 3).

## What checked out

RNG tiers and length-prefixed seeding are consistent; `merge_recipe_params`
honours persona < recipe < user in bass, drums, and rhythm_gtr; `apply_feel`
is called once, excludes drums, clamps at section start, and shrinks same-pitch
overlaps; MIDI de-overlap and sub-tick fixes are deterministic; the drum
grid renders 1-bar, 3/4, 6/8, 7/8, 5/4 and mid-song meter changes without
exceptions or out-of-bounds notes; GM pitches and velocities are in range;
guitar pitches stay in E2..E6; V7 spelling and the chord-shape fixes are
correct; nothing references the deleted `seeds.py` or `lead_gtr/types.py`.
