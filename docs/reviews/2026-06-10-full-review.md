# Produzre Full Review — 2026-06-10

Five-track parallel review: bass engine, drums/arpeggiator, guitar engines, harmony/core/config, and a musical-aesthetics pass. Test suite at time of review: **192 passed / 0 failed** — none of the findings below are covered by tests.

The highest-impact findings were **empirically verified** by the reviewers (repro against shipped examples), not just read from code.

---

## Theme 1 — Parameter plumbing is broken at the core (CRITICAL)

The single biggest problem: large parts of the config system are placebo. Recipes, personas, and user params are silently dropped before engines see them.

### 1.1 `_merge_instrument_config` wipes persona/global params for every instrument
`produzre/orchestrate/render.py:241-266`. `InstrumentConfig.extra` defaults to `{}` (not `None`), so a section declaring `bass: {}` replaces the base `extra` — which is exactly where personas and global params are stashed. Verified with `examples/tiny.yaml`: base extra had 8 persona keys, post-merge `extra == {}`. Drums survives only because it separately re-reads `cfg.raw["_effective"]`; bass/rhythm_gtr/lead_gtr/acoustic_gtr do not. Same root cause: `intensity=1.0`, `style_bias=0.0`, `offset_beats=0.0` are non-None defaults, so unset section values clobber global ones (verified: global `intensity=0.5` → effective `1.0`).
**Fix:** deep-merge `extra` (`{**base.extra, **override.extra}`); use `None` sentinels for scalar fields.

### 1.2 Bass engine reads a field that doesn't exist — all bass params/recipes dead
`produzre/engine/bass/__init__.py:399-404` (also 489-494, 1284-1296). The engine reads `instrument_cfg.params`, but the orchestrator delivers an `InstrumentConfig` dataclass with no `params` field (params are folded into `.extra` at `render.py:258-266`). So `effective_params = {}` always. Verified: building `examples/bass/rhythm/rhythm-drive.yaml` (sets `rhythm_pattern: drive, density: 0.7, rest_rate: 0.15`, persona `metal`) logs `pattern=anchor, density=0.57, rest_rate=0.24` — pure hardcoded defaults. Consequences:
- All **29 generated bass recipes are dead** in production (only live in unit tests passing raw dicts).
- `lock_to_kicks` can never be True → `_render_rhythm_locked_bass` is unreachable from real configs.
- The comment in `tests/test_bass_rhythm.py:81` misdiagnoses this as intended recipe-override behavior.
**Fix:** read/merge via `.extra` like `rhythm_gtr/legacy_params.py:151` does.

### 1.3 Merge order inverted: persona masks recipe
Docs (`config/recipes.py:8`) say `persona < recipe < global < section`, but `load.py:833` merges persona under user params first and the engine merges recipe under that, giving `recipe < persona`. Default bass persona `tight` defines every groove key, so recipes would be fully masked even after fixing 1.2.

### 1.4 Dead/never-read parameters (per engine)
- **Bass**: `swing`, `timing_jitter_ms`, `push_pull`, `velocity_humanize`, `root_bias`, `syncopation`, `motif_repeat_rate` — never read. `apply_drum_locking` imported, never called. Bass output is fully grid-quantized in every genre; all pocket/swing persona claims (`personas/bass.yml`) are placebo.
- **Rhythm gtr**: `apply_groove_swing()` (correct triplet math, `humanize.py:216`) never called; `swing`, `velocity_curve` resolved then dropped; `apply_velocity_curve`, `apply_dynamic_swell`, `apply_downbeat_emphasis`, `create_velocity_envelope` zero callers; most of `defaults.py` dead. `register` param dead in pattern mode (`__init__.py:265` — `getattr` on a dict). Downshift on energy drops is dead code (`transitions.py:189-253`, TODO admits it).
- **Drums**: intent overrides check nonexistent keys (`"hats_density"` vs actual `voices.hats.params.density`, `__init__.py:977-1012`) so `drop`/`stomp`/`open` intents always clobber explicit user config. Energy-derived `crash_rate` permanently overrides recipe `crash_phrase_end_rate` (`__init__.py:742-748` + `patterns/cymbals.py:109`) — every trained crash rate is dead. `build` intent's `fill_length: "long"` is a dead store (`__init__.py:774` vs `:993`).
- **Lead gtr**: `defaults.py` section-density tables and all of `types.py` have zero callers — `__init__.py` re-derives with different hardcoded formulas.
- **Core**: section `energy:` override is parsed into extras and never read (`build.py:237`, `parse.py:414`) — `examples/drums/energy-demo.yaml:76` demonstrably does nothing. Legacy `SectionConfig.progression` parsed but dead → user gets silence instead of harmony (`plan.py:119`). `validate_song_config` never runs in the build path — typos silently no-op.

### 1.5 Recipe resolution bugs
- Bass passes section *id* ("verse1") instead of *type* ("verse") to recipe scoring (`bass/__init__.py:353`) — the +4 section bonus never applies. rhythm_gtr does it right.
- Recipe with empty `tags.genre` matches every genre at +5 (`config/recipes.py:294`, `"" in genre_lower` is always True).
- `resolve_recipe_name`'s `intensity` arg is accepted, never used.
- Harmony recipe `params.chord_rate` (present in all 12 harmony recipes) never consumed.

---

## Theme 2 — Harmony correctness (CRITICAL)

### 2.1 Quality-suffixed numerals resolve to the tonic
`produzre/engine/bass/harmony.py:89`: `ROMAN_TO_DEGREE.get(s.upper(), 1)` — `"V7"`, `"ii°"`, `"IVsus4"` aren't in the dict, default to degree 1. Verified `parse_roman_numeral('V7') == (0, 0)`. Shipped examples use `V7`/`i7`/`iv7` (e.g. `examples/genres/latin/latin-full.yaml:38`) → bass plays the tonic under every dominant. Same in arpeggiator: accidentals stripped but never applied (`bVII` → VII = off by a semitone, `arpeggiator/__init__.py:151-161`).
**Fix:** `re.match(r'[ivIV]+', s)` before lookup; apply accidental after.

### 2.2 Borrowed chords a semitone flat
`bass/harmony.py:64-92`: accidentals applied on top of the current mode's offsets, but presets/recipes spell relative to major. In C aeolian: `bVII` → A (should be Bb), `bVI` → G — the fifth! (should be Ab). Every minor-mode progression like `["i","bVII","bVI","bVII"]` renders C-A-G-A.

### 2.3 Wrong chord-tone intervals
- `fifth_interval = 7` unconditionally → perfect 5th over diminished chords (`bass/harmony.py:163-165`).
- `seventh_interval = 11` for uppercase+7 → **V7 gets a major 7th** (F# over G7 in C).
- Jazz recipe writes plain `V` and `rhythm_gtr/voicings.py:183` upgrades major → maj7, so the ii–V–I comps as iim7 → **Vmaj7** → Imaj7. The most audible theory error in the output.

### 2.4 Chord-shape data and voicing bugs (verified empirically)
- **D-form movable shapes are wrong chords**: `chord_shapes.py:210-211` — D-form_major yields [0,7,11,15] (maj7 + minor 10th!), D-form_minor [0,7,11,14] (no minor 3rd). Correct rel_frets: `(-1,-1,0,2,3,2)` / `(-1,-1,0,2,3,1)`.
- **Voice-leading corrupts barre chords**: `chord_shapes.py:496-507` — −12 octave shift makes frets negative → treated as muted; the guard `0 < f + fret_delta < 1` can never be true for ints. Verified: E-form barre at fret 11 collapses to a 3-note unrelated cluster.
- **Capo discarded**: `chord_shapes.py:325-330` — open-shape lookup transposes by capo but returns `capo=0`. Verified: D major with capo 2 plays a C chord. The acoustic engine exposes `capo` as a user param.
- `_fallback_voicing` span check one-sided → up to 7-fret unplayable spans; root not guaranteed present/lowest (`chord_shapes.py:425-444`).
- "Shell" voicing mutes from the bottom, removing the root (`voicings.py:199-209`).
- Open-shape quality fallback runs before movable exact match — Dm7 loses its 7th (`chord_shapes.py:566-570`).
- Major/ionian songs without explicit progressions get the hardcoded minor loop `["i","bVII","VI","i"]` (`harmony/presets.py:22-34` — case-sensitive lookup, no major presets).

---

## Theme 3 — Timing & placement bugs

- **Drum pickups on a 64th grid**: `drums/patterns/kit.py:129-130` divides the 16th-step by 4 again → 32-hit machine-gun blur before section changes, fires at default `pickup_rate: 0.7`. Fix: `step_16th = sb`.
- **Fill crash lands a bar early**: `drums/fills.py:288-307` — resolution crash placed at the downbeat of the bar *containing* the fill, not the next downbeat. Builds crescendo into silence.
- **Guitar turnarounds smear outside the bar** (verified): `rhythm_gtr/transitions.py:375-388` — hits double-offset and interpreted in the wrong subdivision; notes land up to 5 beats past the barline on the old chord. Also `merge_patterns` density is `x/x` = always 1.0 (`:420`), and strum directions scramble after pattern mutation (`:159-186, 407-419`).
- **Bass fills at bar start, not leading into the downbeat**: `bass/__init__.py:769-854` — the chromatic pickup approach note lands mid-bar, defeating `generate_fill_rhythmic_pickup`.
- **Bass approach tones fire too early**: eligible for the entire second half of a chord span, so tension tones go unresolved (`:879, 1057-1065`); `is_cadence` window can never match anchor/walking slots so sections can end off the root (`:900-901`).
- **`play_pattern: syncopated/offbeat` silences legacy rhythm gtr entirely**: orchestrator grid is quarter-note; the pattern filter only accepts x.5 positions → zero notes (`rhythm_gtr/__init__.py:194-204`). Also breaks `chug` presets.
- **Phrase development re-randomizes instead of developing**: `rhythm_gtr/__init__.py:729-747` builds a fresh random base pattern every bar before applying phrase-position edits. Lead gtr does motifs right but then **discards the realized rhythm**: `lead_gtr/__init__.py:425-435` uses only `rn.pitch`, cycling pitches modulo onto grid slots — the motif's rhythmic identity and the `vary_last` chord-tone resolution both become inaudible.
- **Acoustic hybrid mode indexes sorted pitches with physical string indices** (`acoustic_gtr/__init__.py:521-522`); Travis alternating bass collapses to repeated roots on A/C/D shapes (`:329-335` vs `patterns.py:6-8` docstring).
- **Repeated sections get the wrong transition directive**: `orchestrate/transitions.py:1606-1640` keys `transitions_map` by `sec_id`, so the last occurrence's directive applies to all occurrences of a repeated verse.
- **Limb-collision early-out passes 4 simultaneous hand hits**: `drums/constraints.py:207-209` compares total hits to hand+foot budget without partitioning by limb.
- 3-hit tom fills stack two toms on the same step (`patterns/toms.py:206-217`); `crash.placements` repeats every bar ignoring `rate` (`patterns/cymbals.py:82-95`); splash "max 1 per section" is actually per-bar (`:276-280`); hats only duck during *tom* fills, not snare rolls (`constraints.py:347-353`).
- Exact-float comparisons: bass accent beats (`bass/__init__.py:994, 1176, 1364`), rhythm-locked strum loop drift (`rhythm_gtr/__init__.py:1409, 1456`), drum backbeat `% 4.0 in [1.0, 3.0]` (`ornaments.py:166`), rhythm grid accumulation (`rhythm.py:129-137`).
- Ornament accent "boost" inverted — accents get *fewer* flams (`drums/ornaments.py:169-177`, scales `r` up instead of down).
- Strum spread assumes 120 BPM (`rhythm_gtr/articulation.py:308-310`); with `humanize_timing: 0`, strum offsets quantize to 0 → block chords (`__init__.py:857-860`).
- Slide grace notes at register bottom octave-wrap to 11 semitones *above* and delay the main note (`lead_gtr/__init__.py:470-484`).
- Mid-bar chord changes ignored by strumming/hybrid/percussive/pattern modes — first chord strummed through the second's span (`acoustic_gtr/__init__.py:421-431, 499-506, 590-595`; `rhythm_gtr/__init__.py:702-709`).
- Bass mute/slap and fill durations exceed the gap to the next note → overlapping same-pitch notes, ambiguous note-offs (`bass/__init__.py:1111, 938`).

---

## Theme 4 — Meter support is effectively 4/4-only

- Drums always use 16 steps/bar with `step = bpb/16` → in 3/4 the grid sits on no real subdivision; templates hardcode 4/4 beat positions (snare clamps to the last 16th); swing becomes a no-op; pedal hats silently impossible (`drums/__init__.py:1043`, `groove.py:39-44, 235-240`, `patterns/hats.py:252-261`). Worse, `contribute_plan` publishes a *different* grid (`beats_per_bar*4`) than the renderer uses (`__init__.py:166-179` vs `:1043`).
- **No `time_signature` meta event anywhere in MIDI export** (`export/midi.py:45-57`) — 3/4 and 6/8 songs import into DAWs as 4/4.
- Bar→beat conversion ignores section meter: a `meter: 6/8, bars: 4` section in a 4/4 song resolves to 16 quarter-beats instead of 12 (`harmony/utils.py:76-83`, `model.py:295-316` — `Meter.beats_per_bar` is correct but unused).
- Bass anchor pattern starves odd meters — ~every other 3/4 bar has no bass at all (`bass/patterns/generators.py:33-37`).
- Acoustic percussive strum duration uses `bpb - 3.0` → 0 in 3/4 (`acoustic_gtr/__init__.py:628`).
- `train_drum_recipes.py` tags every recipe `time_signature: "4/4"`, even `odd_meter.yaml` (`:370-374`).

---

## Theme 5 — Musical feel & genre authenticity

- **No shared groove clock.** Each engine humanizes independently; jazz drums say `swing: 0.30`, jazz bass `0.05`, jazz rhythm gtr `0.2` — three clocks, one band. And only drums actually apply swing at all (see 1.4).
- **Swing is mis-scaled**: drums delay the "&" by `0.25 * swing` beats; triplet feel needs ~0.1667 → `swing ≈ 0.67`, but the max in any recipe is 0.30 and `bebop`/`swing` use 0.1 (inaudible). Corpus said blues swing = 0.54; `blues_shuffle.yaml` ships 0.2. Swing only fires on exact 8th-note offbeats — 16th-swing funk is impossible (`drums/humanize.py:110-116`).
- **Mined recipes regressed to a gray mean** (all 29 bass recipes share identical register/motion/template fields; genre identity lives in the mode of a distribution, not its mean):
  - Metal: kick on all 16 sixteenths unconditionally, snare on beats 2+3+4, `double_kick_rate: 0.0` while the metal persona says 0.6.
  - Reggae: four-on-the-floor **with a kick on beat 1** — the one beat reggae avoids; rock backbeat snares; lowest rest_rate of any bass genre when reggae bass lives on silence.
  - Jazz: quarter-note ride only — no spang-a-lang skip beat supported anywhere; bass `articulation: pick`; walking-persona trigger condition (`density >= 0.9`) unreachable from the jazz recipe (0.53) → jazz never walks.
  - Punk bass: `root_bias 0.55, octave_jump 0.34` — will noodle; idiom is ~0.9 root bias, relentless 8ths.
  - Bossa: full-velocity snares on clave-ish steps instead of cross-stick over 8th hats.
- **Trainer corruption confirmed in shipped data**: `tools/train_drum_recipes.py:178-185` ingests note_ons from ALL channels (no `channel == 9` check) with broad pitch-range fallbacks — melodic tracks counted as drums. Visible artifacts: `march.yaml` snare steps [4,8,12,15], `rock_straight.yaml` `double_kick_rate: 0.17`. Also: probabilities diluted by empty bars / inflated by multi-hits (`:247-256`); `--min-files` parsed, unused; manifest keyword matching false-positives on substrings ("dublin" → dub, `build_drum_manifest.py:373-381`).
- **Macro-dynamics are entirely user-supplied** — a config without per-section `intensity` gets a flat song. Lead gtr's `PHRASE_DENSITY_TARGETS` is the right idea, applied to only one engine (and actually dead, see 1.4).
- Two contradictory half-time definitions: template keeps snare on beat 4, intent puts it on beat 3 (standard) — `patterns/kit.py:291-292` vs `__init__.py:985`.
- Acoustic strumming is quarter-note grid + random 22% up-strums — no D-DU-UDU idiom (the fingerpicking library is much better).
- Drum humanization is uniform random jitter — no per-limb pocket, no fill-rushing, no behind-beat snare; velocity humanize is symmetric noise, not accent-shaped.

---

## Theme 6 — Infra & export

- **Stuck notes**: sub-tick durations sort a note's own note_off *before* its note_on (`export/midi.py:149-162`); same-pitch overlaps get cut by the earlier note_off. Fix: `end_tick = max(end_tick, start_tick + 1)` and de-overlap per channel.
- **Section MIDI exports clobber on repeats**: `[verse1, chorus, verse1]` writes the same filename twice (`export/sections.py:179`) — include the arrangement index.
- **Channel config never applied**: `engines.yml` `channel:` is parsed (`config/engines.py:179`) but `timeline.py:164-175` uses its own hardcoded name map; arpeggiator absent → lands on channel 0; any two unmapped instruments double-book channel 0.
- Arpeggiator: flat keys collapse to C (`.upper()` breaks `"Eb"` lookup, `arpeggiator/__init__.py:158`); `rng=None` crashes late; dict configs silently ignored (`getattr` only).
- `SectionMeta.meter/key/mode` become `None` instead of song defaults — `getattr` fallback never fires because the fields exist with value None (`orchestrate/build.py:98-100`).
- `harmony.plan` is a global plan key overwritten per section — stale-plan dependency validation passes for sections without harmony (`orchestrate/render.py:83-86`).
- RNG: `make_instrument_rng` seeds from `str(section_rng.getstate())` — one future draw from section_rng reshuffles every instrument stream (`rng.py:148-151`); `"|"` in ids can collide seeds (`:89`); `seeds.py` is dead code and a third incompatible hashing scheme.
- `load_root_config` writes the projects registry on every load — filesystem side effect for read-only commands (`config/load.py:879-880`).
- `rhythm_features.py:151-170`: syncopation counts every non-downbeat kick (contradicts its docstring); fill windows fragment on interleaved hat hits — both feed cross-engine coordination.
- Legacy rhythm gtr computes and logs CAGED voicings, then renders bare power chords — write-only dict that also burns RNG state (`rhythm_gtr/__init__.py:920-957`).
- Dead files: `drums/patterns/mix.py` (empty), `seeds.py`, much of `rhythm_gtr/defaults.py`, `lead_gtr/defaults.py` + `types.py`.

---

## Verified-OK (checked, no issue)

- GM drum pitches all correct; velocity math consistently clamped.
- Recipe tie-breaking deterministic (lexicographic id); section RNG correctly mixes take + arrangement index; engine order priority-sorted stable; MIDI delta-time output deterministic; `beats_to_ticks` has no cumulative drift.
- `resolve_section_energy` (new energy helper) clean; `adjust_pattern_for_transition` has no div-by-zero.
- Dual-RNG split for drum fills/chatter is well designed for determinism.

---

## Ranked roadmap

1. **Fix the param plumbing** (1.1 + 1.2 + 1.3): deep-merge `extra` in `_merge_instrument_config`, point bass at `.extra`, fix merge precedence. This single fix activates personas, recipes, and user params for 4 of 5 engines — everything else is masked behind it.
2. **Fix harmony spelling** (2.1–2.3): suffix-tolerant numeral parsing (bass + arpeggiator), major-scale-relative accidentals, dominant 7ths as b7, diminished fifths as b5, `V7` in jazz/blues recipes or context-aware voicing quality.
3. **Fix the verified note-placement bugs**: drum pickup 64th grid, fill crash a bar early, guitar turnaround smear, capo, D-form shapes, voice-leading barre corruption.
4. **Shared groove clock**: one `groove.feel = {swing_ratio, base_grid, pocket_offsets_ms}` on the PerformancePlan sourced from the drum recipe; apply in a common post-process for all engines; express swing as offbeat ratio (0.5 straight / 0.67 triplet) over 8ths *and* 16ths. Per-instrument constant pocket offsets (bass +8ms, hats −3ms) buy the most feel per line of code.
5. **Hand-author idiom groove templates** per genre (one-drop, spang-a-lang, shuffle-as-12/8, punk straight-8 roots), keeping mined stats as bounds only; fix the drum trainer's channel filter and regenerate.
6. **Default macro-dynamics arc**: section-type → intensity table in `orchestrate/plan.py` when the user omits `intensity`, + small per-repeat escalation.
7. **Meter honesty**: `steps_per_bar = beats_per_bar * 4` in drums, time_signature meta in export, meter-aware bar→beat conversion — or explicitly document 4/4-only.
8. **Test the seams**: the suite is green at 192 because it tests engines with raw dicts and structural output. Add integration tests that build shipped examples end-to-end and assert effective params (e.g. "rhythm-drive.yaml renders with density 0.7", "V7 in C produces a G root", "no note extends past its section").
