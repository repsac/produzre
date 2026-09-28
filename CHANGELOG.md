# Changelog

## 0.10.0 (2026-09-27): the composer

Songs are now written by a composer instead of assembled from patterns. Each
song gets its own band: a drummer, a bassist, a rhythm guitarist and a lead
player with their own habits, playing a hook the whole song is built around.
The detailed design notes and review reports are in `docs/design/` and
`docs/reviews/`.

### What changes for existing songs

Existing YAML produces different MIDI. To keep a part's older behavior, set
`composer: false` on it (or `song.composer: false` for the whole song).

- **The lead guitar is composed.** A song gets one set of ideas: a hook, an
  answer, verse and bridge ideas and a bank of licks, and returning sections
  remember them. `foreground: auto` plays around a singer (fills, a chorus
  counter-line, the solo); `full` makes the lead the melody.
- **The rest of the band is composed too.** Drums, rhythm guitar and, in band
  sections, the bass play per-song parts, and all parts agree on arrangement
  habits: how the band goes into a chorus, how phrases end, how the song
  ends. Pin any habit with `song.arrangement_style`.
- **Grooves settle.** Drums, bass, rhythm and acoustic guitar restate a
  section's typical bar through each phrase, and choruses recall their
  groove. `groove_memory: false` turns it off.
- **Odd and compound meters phrase by beat groups** (6/8 as 3+3, 7/8 as
  2+2+3). Without an explicit `chord_rate`, chords change once per bar in
  every meter.
- **Dynamics follow the song.** Composed drums, bass and the arpeggiator get
  louder from verse to chorus and grow on repeats.
- **The bass lands on the root on beat 1** of every new chord.
- Your settings still win. Explicit patterns, styles, recipes, `intent`,
  swing and register settings keep their engines or bound the composed parts,
  and settings only the older generators use are logged as unused.

### New

- **Every song its own band.** Per-song drum kits and grooves, signature
  riffs with optional bass doubling, synthesized comp figures, generated
  licks and bass roles, so an album in one genre doesn't sound like one song.
- **Genre idioms**, each with per-song variety: country (six styles such as
  honky-tonk, Bakersfield and outlaw, plus real waltzes), reggae (one-drop,
  steppers, rockers), jazz (spang-a-lang ride, walking bass), and a
  four-on-the-floor drummer for dance and electronic music.
- **Solo instruments** carry a piece on their own: solo drums, fingerpicked
  acoustic guitar with a melody over the thumb, and a solo lead that plays
  the tune.
- A section or instrument `genre` now changes that part's player, so one
  song can move between genres.
- `song.final_chorus: modulate` for a last-chorus key change, and
  `song.turnarounds` to lead sections into each other.
- `lead_gtr` chorus forms (`lift`, `anthem`, `call`), solo stories and
  endings, octave and stab counters, country fills with double stops.
- The top-level `engines:` block sets MIDI programs and channels. Section
  personas work. Unknown settings print a warning with a suggestion.
- Rewritten examples: twelve complete songs in `examples/songs/`, one song
  per genre, solo pieces for drums, bass, acoustic and lead guitar, and
  instrument demos for the current app. They use the built-in
  `produzre-examples` project, so they sound the same on every machine.
- Tools: `tools/album_diversity.py`, `tools/rhythm_review.py`,
  `tools/musicality.py` and `tools/preview_audio.py` for MP3 previews.

### Fixed

- **Drums:** 12/8 and 6/8 grooves, swing that no longer warps compound
  meters, audible builds, one hit per drum per step, the drum persona being
  ignored, and transitions thinning fills.
- **Bass:** walking lines that actually walk, no more silent bars, the bass
  playing through stop-time and drops, authored bass motifs, slap on composed
  parts, register limits, and the root on one after groove memory.
- **Lead and arpeggiator:** a crash with a numeric `register` list, dead
  `bend_rate` and `dive_rate` ranges, lead seeds, sparse or repeated solos,
  trills under swing, and the arpeggiator's voicings and loudness.
- **Guitars:** walk-up notes over held chords, capo in fingerstyle and tabs,
  barre melodies out of range, `sustain_duration`, and chords that started
  sections an octave high.
- **Transitions:** pickups now respect the key, meter and register, and never
  lead into silence; bass notes no longer overlap pickups or ramps.
- Many smaller fixes. Every issue is listed with its fix in
  `docs/reviews/2026-09-26-examples-findings.md` and
  `docs/reviews/2026-09-26-final-review.md`.

## 0.9.0 (2026-09-13)

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
