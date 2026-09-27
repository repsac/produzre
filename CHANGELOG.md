# Changelog

## 0.10.0 (unreleased): the composer

### Config, guitar and docs fixes from the examples findings

- The top-level `engines:` block works as documented: each field overrides
  the built-in registry (program, channel, priority, new engines). Registry
  fields on a global `instruments:` entry still apply; `engines` wins when
  both set a field, and the build logs the conflict.
- A `persona` on a section's instrument applies its params for that
  section, at the persona layer (persona < recipe < global params < section
  params). `params.persona` works too.
- The build warns about instrument params no built-in engine reads, naming
  the key, where it was set and the closest known keys; `validate` reports
  the same lines. Section-level registry fields and unknown `engines`
  fields are flagged too.
- Rhythm-guitar walks only lead into chord changes: a riff's walk over a
  held chord becomes a hold, and a phrase-end walk-up into the same chord
  becomes root and fifth. The approach note is chromatic unless it rubs a
  semitone against the chord it is played over (C, not C#, into Dm over Am).
- `sustain_mode` plays held chords on both classic renderers (struck on each
  chord, restruck every `sustain_duration` beats, not palm-muted by the
  section default); `sustain_duration` caps every strum on every renderer,
  composed comping included. Composed comping logs the classic renderers'
  controls (`mute`, `retrigger`, a `register` preset and so on) as unused.
- Acoustic `capo` is consistent in the composed fingerstyle: thumb, inner
  voice and melody all sound in the song's key over capo-relative shapes.
  Barre shapes sit at their lowest position on the neck, and picked melodies
  (including groove-memory restatements) stay at or below A5.

### Examples for the current app

- New `examples/songs/`: twelve complete songs across genres and meters.
- New solo-track folders: `drums/solo`, `bass/solo`, `acoustic_gtr/solo`
  and `lead_gtr/solo`, each with three full pieces for one instrument.
- One current song per genre replaces the simple, full and recipe-showcase
  files (31 files instead of about 90).
- Drum, lead, rhythm guitar, orchestration, persona and seed demos are
  rewritten around settings the composer honors; each instrument keeps one
  `composer: false` classic-engine demo. `drums/transitions/` plays one song
  with each into-chorus device.
- Tests read frozen copies under `tests/fixtures/examples/`, so examples can
  change freely. App findings from writing them are in
  `docs/reviews/2026-09-26-examples-findings.md`.

### Country waltzes and style hints

- Country waltzes get a per-song waltz band: bass on 1 with its own
  ring length, root/fifth habit and walks on 2 and 3 into chord changes;
  guitar answers on 2 and 3 with the song's figure; drums keep the kick on
  1 with their own snare or cross-stick, foot hat and timekeeper. The ten-song
  waltz album moves from 0.69 to about 0.51 similarity. Other meters are
  byte-identical.
- Genre names choose the country style (`outlaw_country`, `country_rock`,
  `honky_tonk`, `bakersfield`, `texas_country`, `country_ballad`); a pinned
  `country_style` still wins.
- Composed drums can play `cross_stick` (GM 37).

### Rhythm-guitar groove review

- Keep riff pitch calculations from changing subsequent note velocities.
- Fit signature riffs to section meter/grouping and honor rhythm part seeds;
  trim bar-two body notes before the answering tail.
- Keep drum group starts on the same compound pulse as the guitars.
- Preserve explicit bass line choices and registers through riff doubling,
  retain transition/ending bars, and use actual scale neighbors for approaches.
- Add opt-in `comp_activity: normal` and `sparse`, with repeated open bars,
  spaced phrase devices and drum-aware riff candidate scoring.
- `comp_activity` is now a per-song habit (busy, normal, sparse), drawn
  like the other arrangement habits and pinned by `arrangement_style`.
- Signature riffs lock with the drummer in every mode: kick and snare
  unisons score up, sixteenths off the backbeat are ruled out. Verse
  near-misses against the drums halve across the benchmark album.
- Riff power moves under a clashing held lead note are choked to a stab
  (sustained guitar/lead clashes on the album: 22 to 2).
- A doubling bass plays the riff tail alone where the guitar leaves it open.
- Add a rendered bar audit and regression tests. Default guitar album
  similarity is unchanged; see the [review](docs/design/rhythm-guitar-review.md)
  for the bass tradeoff, rejected automatic changes and audio comparisons.

### Composer review, round 2

- Correct compound shuffle grids and preserve group starts through shared swing.
- Include grouping in lead recall and adapt generated ideas to section meters.
- Preserve authored bass contours, avoid fast-answer overlaps and honor bounds.
- Honor section settings across field/param layers, nested lead registers,
  composed rhythm timing, octave voicing and final gesture register bounds.
- Add opt-in `hook_response: develop` for rotating hook fragments and answers.
  Responses remain off by default in every genre.
- Add 37 regression/probe cases, a 216-build before/after matrix, and four
  blinded listening pairs. The three existing 4/4 composer examples retain
  byte-identical MIDI; no goldens regenerated. See the
  [second review](docs/design/composer-review-round2.md).

### Composer review fixes and extension

- Respect explicit lead phrase and technique controls, numeric lead register
  bounds, and rhythm density, voicing, and performance controls.
- Fit song DNA using the source section's key, mode, and meter. Counter-lines
  include chords already sounding at phrase entry; realization uses actual
  section-relative metric position.
- Walk toward the next harmonic change, independent of arpeggio state. Keep
  power chords and walking notes above standard guitar's low E.
- Groove recall includes top-level configuration and canonical nested params.
- Keep slide graces MIDI-safe and the final lead monophonic after transitions.
- Add metric and harmonic exposure scoring to listener development choices,
  plus a reproducible A/B tool and readable lead sheets. Exposure fell 5.6%
  on 288 controlled section cases; other metrics show small tradeoffs.
- Existing affected songs intentionally change. No golden files regenerated.
  See [the review report](docs/design/composer-review.md).

### What changes for existing songs

Existing YAML produces different MIDI. The lead guitar is now composed, and
the rhythm section settles into grooves.

- **Lead guitar** comes from the song composer (`produzre/composer/`). A song
  gets one set of ideas, its DNA: a hook, answer, verse idea, bridge idea,
  and three signature licks. Returning sections remember their material.
  `song.composer: false`, or `composer: false` on the lead, restores the 0.9
  motif generator.
- The auto-generated melody theme (`auto_hook`) is replaced by the
  composer's hook, so the acoustic guitar, arpeggiator, and lead share one
  melody. Authored melody themes are never replaced; they become the hook.
- **Groove memory** gives drums, bass, rhythm guitar, and acoustic guitar a
  bar form: each 4-bar phrase restates the section's most typical bar and
  keeps the engine's own last bar. Choruses recall their groove.
  `song.groove_memory: false`, or `groove_memory: false` per instrument,
  restores bar-by-bar output. The bass golden baseline was regenerated.
- **Your settings shape composed parts.** Part selectors (`style`,
  `pattern`, `sustain_mode`, `recipe`, `composer: false`) keep the previous
  engines. Lead `rest_probability`, `contour_style` and expression rates, and
  rhythm `density`, `palm_mute`, `chuck_rate`, `voicing`, register and dynamics,
  shape the composed parts. Legacy-only tuning is logged as unused.
- **Rhythm guitar** is composed unless a part pins its own style or mode.
  Each song gets signature comp riffs (chucks, walks, sus hammer-ons,
  slides, boogies, gallops), with verse, chorus, and bridge contrast,
  walk-ups, and stop-time before choruses. `composer: false` on the rhythm
  part restores the recipe or legacy behavior.
- **Odd and compound meters phrase by beat groups** (6/8 = 3+3, 7/8 = 2+2+3,
  5/4 = 3+2; `meter_grouping` overrides). Without an explicit `chord_rate`,
  chords change once per bar in every meter (previously every 4 beats, which
  drifted against 7/8 and 6/8 bars). 4/4 output is unchanged.
- Bass `hook_response: true` (opt-in): the bass answers the composed lead at
  phrase ends with the hook's rhythm and contour, starting on a kick.
- **Every song its own band.** Composed drums (per-song kick patterns,
  timekeepers per section, backbeat styles, ghost notes, synthesized fills,
  fill and crash habits, and a band feel), arrangement habits shared by all
  parts (chorus approach, phrase endings, riff-alone intros, solo stories
  and endings, lead counter-parts, chorus forms, fill density, endings),
  signature riffs for riff-driven songs with optional bass doubling,
  synthesized comp figures, and generated licks. Across a ten-song hard
  rock album, part similarity fell from 0.41 to 0.16
  (`tools/album_diversity.py`). `song.arrangement_style` pins any habit;
  drum `composer: false` keeps the drum engine.
- **Turnarounds**: preset and recipe progressions now lead into sections
  that start on the tonic (the last half bar moves to V, V7, or bVII).
  Explicit progressions are unchanged unless you opt in.
- The shared groove clock now shortens swung off-beat notes so they end on
  the grid; previously they overlapped the next downbeat.
- The lead's `foreground` setting is read from `params:` (the documented
  block). Before, only `extra:` or a bare key worked.

### New

- Song DNA chosen by a memorability search. Hundreds of candidate ideas are
  scored for rhythm, contour, gap-fill, and surprise, then re-scored as
  realized over your real chorus and verse chords.
- Phrase grammars per section: a verse period, a climbing prechorus, a chorus
  of hook lines (A A' B A'', with one summit), a contrasting bridge, a
  narrative solo (hook quote, development, climax, resolution, dive), and an
  outro. `foreground: auto` gives a band part around a singer: the intro
  hook, verse fills from the lick bank, a chorus counter-line, and the solo.
- Composed comping (`composer/comping.py`, `engine/rhythm_gtr/composed.py`):
  57 idiomatic rhythm-guitar riffs across 20 genre families, chosen per song for
  character, personalized by seeded idiom-preserving mutations, and performed
  on playable chord shapes with strum spread, chucks, pull-offs, and slides.
- A listener model: a self-updating expectation model over intervals and
  durations, primed with statistics from human melodies. It picks each
  phrase's development so its surprise suits the phrase's role. Targets were
  calibrated on 3,520 human phrases.
- Beam-search realization: motifs keep their intervals over changing chords,
  with chord tones on strong beats, prepared dissonance, and cadences that
  re-aim when the harmony forbids their degree.
- `song.final_chorus: modulate` (or a semitone count): a final-chorus key
  change that every pitched part follows.
- `song.turnarounds` and per-section `harmony: turnaround:` overrides.
- `tools/musicality.py`: a structural benchmark for melodic lines against a
  reference corpus. `tools/preview_audio.py`: a quick MP3 preview renderer.
- The composer showcases in `examples/composer/`. Design and measurements are
  in [docs/design/composer-architecture.md](docs/design/composer-architecture.md).

### Fixed

- The grid dump rounds each hit to the nearest step, instead of drawing
  slightly-early hits a sixteenth early.
- Transition pickups are written once per boundary. They no longer duplicate,
  and they no longer land inside composed lead phrases.
- The lead is monophonic after the groove clock and humanization.

## 0.9.0 (unreleased)

### What changes for existing songs

Existing YAML can produce different MIDI in 0.9.0. Phrase development, shared
melody, corrected harmony, recipe precedence, meter handling, kit constraints,
and timing all affect what you hear.

- Drum and bass goldens were regenerated once after the output-changing fixes.
  The bass baseline remained byte-identical; the drum baselines capture the
  corrected kit behavior.
- Automatic themes are on by default with `song.themes_auto: true`. You get
  a riff and melody unless you supply authored themes or turn this off.
- Accompaniment theme coupling is off by default. Bass and rhythm-guitar
  `lock_to_riff` and drum `riff_accent_rate` default to 0; drum
  `riff_accent_boost` defaults to 1. Enable coupling explicitly to keep the
  riff-following kicks from the first theme-bank implementation. Lead quotation
  stays at 0.65, and automatic melodic material remains available.
- The arpeggiator defaults to `pattern: phrase` and `note_duration: 0.5`,
  replacing `up` and 0.25 beats. Legacy `up`, `down`, and `up_down` remain available.
- Bar length now comes from `meter` when you omit the legacy `beats_per_bar` override.
- Straight drum recipes now have zero inferred swing. The training corpus has
  not been rerun as part of this release review.

See [DETERMINISM.md](DETERMINISM.md) for repeatability within a version and
why output can change across releases.

### New

- Bass, rhythm guitar, and lead guitar develop phrases across bars. Bass can
  repeat two-bar rock/funk onset cells within longer phrases.
- Section energy shapes pickups, turnarounds, entrances, and endings.
  Repeated section occurrences receive their own transition directives.
- A shared groove clock applies swing and per-instrument pockets.
- A shared melody guide supplies targets to lead guitar, acoustic treble
  melody, and the arpeggiator.
- Ensemble planning assigns foreground roles, lead windows, density budgets,
  and fill ownership.
- Acoustic `melody_amount` and `phrase_variation` shape the moving top line.
  The `cinematic` picking pattern adds space around it.
- Automatic composition creates a riff and melody from the song seed.
  Takes and performance variation preserve that material.
- Top-level `themes` accepts authored degree/duration events or matching degree
  and rhythm lists. Registers and octave offsets affect realized pitches.
- Authored themes keep their written sequence unless `allow_development: true`.
  Generated or unlocked themes can be quoted, sequenced, inverted, fragmented,
  displaced, thinned, stretched, compressed, or shifted by octave.
- Bass quotes a `bass_motif` theme's onsets and pitches (`motif_quote_rate`,
  0.7 by default when a motif exists). With no motif, `lock_to_riff` locks
  onsets and quotes the riff's pitches. Rhythm guitar uses riff accents;
  drums can add constrained riff kicks.
- `drum_groove` themes: degrees map to kit voices (kick, snare, hat, open
  hat, crash, ride, tom) and the theme becomes the beat. `groove_strength`
  crossfades against the genre pattern. Groove themes also play in
  drums-only sections.
- Seeded pitch expression written as pitch bend and CC11: lead vibrato,
  bend-ins, volume swells, and a whammy dive on the solo's last held note;
  bass slide-ins and vibrato; rhythm guitar vibrato on sustained chords.
- Lead ring-out: notes sustain into the silence that follows them
  (`ring_out`, `ring_max_beats`), and the lead sits louder in the mix.
- Lead `foreground: full` gives the lead the whole section for instrumental
  music instead of call-and-answer windows.
- Drum tracks carry a Standard Kit program change so DAWs stop loading them
  as piano.
- New demos: `examples/theme_showcase.yaml` and `examples/lead_metal_demo.yaml`.

### Fixed

#### Themes

- Theme cells stay on eighth/sixteenth grids in odd meters. Tonic and final
  notes keep their identity. Duplicate roles use the first declared theme
  consistently; all named themes remain in the performance plan.
- Invalid lengths, unsupported theme keys, and unimplemented MIDI imports or
  drum themes now produce clear errors. The architecture document identifies
  the ideas that have not been built.
- One-bar sections now receive usable lead windows.

#### Drums

- Drum recipe voices apply before generation. Crossstick, ghost, hat, and kick
  settings honor overrides. Recipe groove rates survive energy defaults.
- Hat and kick placement controls reach the kit. Hat velocity and accent controls
  affect forced closures too. Pedal hats work alongside ride cymbal.
- Fills and pickups swing with the groove. Hat ducking recognizes generated
  voice kinds, duplicate hits are removed, and theme kicks pass constraints.
- Trainer keyword matching and drum-grid analysis were corrected.

#### Bass

- Kick locking applies once, and zero disables it. Hat locking uses rendered
  cymbal attacks. Locked bass respects register, velocity, and section boundaries.
- Tight bass keeps kick locking at 0.8 and snare locking at 0 instead of 0.3.
  Global bass offsets now reach rendering.

#### Guitars

- Rhythm patterns vary by phrase and leave space for lead activity. Muted and
  stabbed strokes keep positive durations through export.
- Acoustic fingerpicking uses physical strings consistently and stops each
  string before its next attack.
- Lead phrases retain off-grid motif attacks and use genre color tones.
  Local mode overrides now reach lead pitches.
- Guitar voicings and legacy play patterns handle chord spelling and boundaries
  correctly. Chords shorter than the arpeggiator's spacing still receive an attack.

#### Groove and meter

- Explicit zero swing overrides presets. True triplets keep their timing.
- Positive `push_pull` means ahead for every instrument. The conversion is
  `-100 * push_pull` milliseconds, capped at 25 ms each way. Positive `pocket_ms`
  means behind for pitched instruments.
- Timing offsets apply once through the shared clock where appropriate. Recipe
  timing reaches silent-drum sections and pitched engines.
- Section meter changes reach planning, full-song MIDI, stems, patterns, and the
  bar map. Compound 6/8 has a different backbeat from 3/4.
- Shared Roman-numeral spelling handles borrowed chords, dominant and major
  sevenths, suspended, diminished, and half-diminished chords consistently.

#### Export

- Pattern export settings are parsed. Repeated sections retain distinct index
  and sequence entries. Time metadata uses timezone-aware UTC.
- The drum golden runner reads its own export and fails on missing baselines.

#### Config

- Explicit user settings now reach the renderers; see [preset order](docs/llm-song-config-reference.md#recipes-and-personas)
  for how persona, recipe, global, and section values combine.
- Removed unused bass `swing`/`syncopation`, rhythm-guitar `swing`/`groove`,
  the unused coordination threshold, and the unused downshift helper.
- Added theme and release regression tests. Count-only assertions now check
  the musical properties they were meant to guard.
- Updated the README, config reference, engine guide, determinism guide, theme
  design, example guides, and test guides against the code. The package version
  is now 0.9.0.

Commits: `b1244b5`, `da46bf8`, `2552bc5`, `8b4bd85`, `7624d32`; followed by the September 13 release review fixes.

## 0.8.0 (2026-03-11)

First public release. YAML song definitions describe key, tempo, harmony,
instruments, sections, and arrangement order. Built-in engines provide drums,
bass, rhythm guitar, lead guitar, acoustic guitar, and an arpeggiator example.
Harmony supplies chord plans to the pitched engines.

The release includes genre recipes, instrument personas, project seed
registries, seed/take/variation controls, full-song MIDI, stems, section clips,
deduplicated patterns, sequence/index metadata, and optional grid, tablature,
and event-text exports. The CLI supports building, validation, resolved config
inspection, project sharing, and local user profiles.
