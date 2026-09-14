# Changelog

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
