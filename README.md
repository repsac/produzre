# Produzre

A deterministic, section-based, procedural MIDI engine. Write a YAML config, get
a full multi-instrument song as MIDI — stems, section clips, patterns, tablature,
and analysis — all reproducible, every time.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Installation](#installation)
- [How It Works](#how-it-works)
- [Song YAML Reference](#song-yaml-reference)
  - [Minimal Config](#minimal-config)
  - [Full Config Anatomy](#full-config-anatomy)
  - [Song Settings](#song-settings)
  - [Sections](#sections)
  - [Instruments](#instruments)
  - [Arrangement](#arrangement)
  - [Harmony & Progressions](#harmony--progressions)
  - [Exports Block](#exports-block)
- [Genres (31)](#genres-31)
- [Personas](#personas)
- [Instrument Parameters](#instrument-parameters)
  - [Bass](#bass)
  - [Drums](#drums)
  - [Rhythm Guitar](#rhythm-guitar)
  - [Lead Guitar](#lead-guitar)
  - [Acoustic Guitar](#acoustic-guitar)
- [Seeds, Variation & Reproducibility](#seeds-variation--reproducibility)
  - [How Seeds Work](#how-seeds-work)
  - [Seed vs Take vs Variation](#seed-vs-take-vs-variation)
  - [Section-Level Overrides](#section-level-overrides)
  - [Instrument-Level Overrides](#instrument-level-overrides)
  - [Repeated Sections](#repeated-sections)
- [Projects & Collaboration](#projects--collaboration)
  - [What Is a Project?](#what-is-a-project)
  - [Your First Project](#your-first-project)
  - [Managing Projects](#managing-projects)
  - [Sharing Projects (Collaboration)](#sharing-projects-collaboration)
  - [Backing Up Your Seeds](#backing-up-your-seeds)
- [CLI Reference](#cli-reference)
  - [build](#build)
  - [validate](#validate)
  - [show-config](#show-config)
  - [project](#project)
  - [user](#user)
- [Understanding the Output](#understanding-the-output)
  - [Export Directory Structure](#export-directory-structure)
  - [Full Song MIDI](#full-song-midi)
  - [Stems](#stems)
  - [Section Clips](#section-clips)
  - [Patterns & Sequencer](#patterns--sequencer)
  - [Quick Reference File](#quick-reference-file)
  - [Index File](#index-file)
- [Text Exports (Grid, Tab, Events)](#text-exports-grid-tab-events)
  - [Grid View (ASCII Piano Roll)](#grid-view-ascii-piano-roll)
  - [Tab View (Guitar Tablature)](#tab-view-guitar-tablature)
  - [Events View (TSV)](#events-view-tsv)
- [Config Merge Priority](#config-merge-priority)
- [Common Pitfalls](#common-pitfalls)
- [Generating Song Configs with AI](#generating-song-configs-with-ai)
- [Standalone Executable](#standalone-executable)
- [Examples Library](#examples-library)

---

## Quick Start

```bash
# Build the minimal example
produzre build examples/minimal.yaml

# Listen to the output
open exports/Minimal\ Example_*/Minimal\ Example.mid

# Validate a config without building
produzre validate examples/minimal.yaml

# See the fully resolved config
produzre show-config examples/minimal.yaml
```

---

## Installation

### From Source

```bash
git clone <repo-url>
cd produzre

# Install dependencies
pip install mido pyyaml

# Run directly
python -m produzre.cli build examples/minimal.yaml
```

### Standalone Executable (No Python Required)

Pre-built executables are available for macOS, Linux, and Windows. See
[Standalone Executable](#standalone-executable) for building your own.

---

## How It Works

1. **You write a YAML file** describing your song: tempo, key, sections, instruments,
   and an arrangement order.
2. **Produzre reads the config**, resolves genre recipes and personas, and plans the
   song structure (section timings, harmony plans, rhythm grids).
3. **Engines render each instrument** into MIDI timelines — deterministically, based
   on your seed. Drums go first, then bass locks to the kick, then guitars layer on.
4. **The export system writes everything out**: a full multi-track MIDI, per-instrument
   stems, per-section clips, reusable patterns, and optional human-readable text
   exports (piano-roll grids, guitar tablature, event logs).

Same YAML + same project seed = **byte-identical output**, every time.

---

## Song YAML Reference

### Minimal Config

The simplest possible song — one section, one instrument:

```yaml
version: 1
song:
  title: "Hello World"
  bpm: 120
  key: C
  mode: ionian
  meter: "4/4"
  seed: 42
  exports_root: "exports"

sections:
  verse:
    type: verse
    bars: 8
    instruments:
      drums:
        intensity: 0.7

arrangement:
  - verse
```

This produces an 8-bar drum loop at 120 BPM. To add bass and guitar, include a
`harmony` instrument (required dependency) and the instruments you want:

```yaml
sections:
  verse:
    type: verse
    bars: 8
    harmony:
      progression: "I V vi IV"
    instruments:
      harmony: {}          # REQUIRED for bass/guitar to work
      drums:
        intensity: 0.7
      bass:
        intensity: 0.7
      rhythm_gtr:
        intensity: 0.7
```

### Full Config Anatomy

```yaml
version: 1                  # Always 1

song:                        # Global song settings
  title: "My Song"
  bpm: 120
  key: E
  mode: minor
  meter: "4/4"
  genre: rock                # Auto-loads recipes for all instruments
  seed: 42                   # Reproducibility seed
  take: 0                    # Micro-variation number (0, 1, 2...)
  variation: 0.0             # Global variation bias (0.0-1.0)
  project: "my-project"      # Optional: use a specific project seed
  humanize_velocity: 0.1     # Global velocity humanization (0.0-0.3)
  humanize_timing: 0.05      # Global timing humanization (0.0-0.2)
  exports_root: "exports"    # Output directory
  pattern_bars: 1            # Pattern window size in bars

exports:                     # Optional: control text export views
  midi_text:
    enabled: true
    views: ["events", "grid", "tab"]
    subdiv: 16               # Grid resolution (8, 12, 16, 32)

instruments:                 # Optional: global instrument defaults
  drums:
    persona: "rock"
  bass:
    params:
      articulation_style: "pick"

sections:                    # Section definitions
  verse:
    type: verse
    bars: 8
    harmony:
      progression: ["i", "VI", "VII", "i"]
    instruments:
      harmony:
        intensity: 0.7
      drums:
        intensity: 0.7
      bass:
        intensity: 0.7
      rhythm_gtr:
        intensity: 0.7

  chorus:
    type: chorus
    bars: 8
    harmony:
      progression: ["VI", "VII", "i", "VII"]
    instruments:
      harmony:
        intensity: 1.0
      drums:
        intensity: 1.0
      bass:
        intensity: 1.0
      rhythm_gtr:
        intensity: 1.0

arrangement:                 # Playback order
  - verse
  - chorus
  - verse
  - chorus
```

### Song Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `title` | string | `"produzre"` | Song title, used for export filenames |
| `bpm` | number | `120` | Tempo in beats per minute (40-240) |
| `key` | string | `"C"` | Key signature: C, C#, Db, D, D#, Eb, E, F, F#, Gb, G, G#, Ab, A, A#, Bb, B |
| `mode` | string | `"ionian"` | Scale mode (see table below) |
| `meter` | string | `"4/4"` | Time signature (must be quoted in YAML) |
| `genre` | string | — | Auto-loads genre recipes for all instruments |
| `seed` | int | `0` | Random seed for reproducibility |
| `take` | int | `0` | Take number for micro-variation |
| `variation` | float | `0.0` | Global variation bias (0.0 = stable, 1.0 = max) |
| `project` | string | — | Reference a named project for its seed |
| `humanize_velocity` | float | `0.0` | Global velocity humanization (0.0-0.3) |
| `humanize_timing` | float | `0.0` | Global timing humanization (0.0-0.2) |
| `exports_root` | string | `"exports"` | Root directory for output |
| `pattern_bars` | int | `1` | Bars per pattern window |

**Valid Modes:**

| Mode | Aliases | Character |
|------|---------|-----------|
| `ionian` | `major` | Happy, bright (C major scale) |
| `dorian` | — | Minor with bright 6th (jazz/funk) |
| `phrygian` | — | Dark, Spanish/metal feel |
| `lydian` | — | Dreamy, floating (#4) |
| `mixolydian` | — | Major with bluesy b7 (rock/blues) |
| `aeolian` | `minor` | Natural minor (sad, dark) |
| `locrian` | — | Very dark, diminished (rare) |

### Sections

Sections are named blocks that define a segment of the song. Each section has a
type, length, harmony, and per-instrument configuration.

```yaml
sections:
  my_section_name:           # Any name you choose
    type: verse              # Section type (affects recipe selection)
    bars: 8                  # Length in bars (or use beats: 32)
    key: G                   # Optional: override song key for this section
    mode: dorian             # Optional: override song mode for this section
    meter: "7/8"             # Optional: override song meter for this section
    seed: 999                # Optional: override song seed for this section
    variation: 0.5           # Optional: override song variation for this section
    harmony:
      progression: "I V vi IV"
      chord_rate: 4.0        # Beats per chord change (default: 4.0)
    instruments:
      harmony: {}
      drums:
        intensity: 0.7
      bass:
        intensity: 0.7
```

**Section types** (any string works, but these have special recipe/energy behavior):

| Type | Energy | Typical Use |
|------|--------|-------------|
| `intro` | Low | Opening, build anticipation |
| `verse` | Moderate | Main lyrical sections |
| `prechorus` | Moderate-High | Build tension before chorus |
| `chorus` | High | Hook, maximum energy |
| `bridge` | Moderate | Contrast, new harmonic territory |
| `solo` | High | Instrumental showcase |
| `breakdown` | Low-Moderate | Sparse, stripped-down |
| `outro` | Low | Ending, fade out |

### Instruments

Every instrument in a section gets its own config block. The `harmony` instrument
is a special dependency — it generates the chord plan that bass, guitar, and other
pitched instruments need. **You must include `harmony: {}` in any section that uses
bass, rhythm_gtr, lead_gtr, or acoustic_gtr.** Drums do not require harmony.

Available instruments: `harmony`, `drums`, `bass`, `rhythm_gtr`, `lead_gtr`, `acoustic_gtr`

**Common per-instrument fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `intensity` | float | `1.0` | Density/velocity scaling (0.0-1.0) |
| `seed` | int | — | Override RNG for this instrument in this section |
| `variation` | float | — | Variation bias for this instrument in this section |
| `solo` | bool | — | Enable solo/featured mode |
| `register` | string | — | Pitch range hint: `low`, `mid`, `high` |
| `genre` | string | — | Per-instrument genre override for recipe selection |
| `recipe` | string | — | Explicit recipe name (bypasses auto-selection) |
| `persona` | string | — | Load a persona preset (set in `params:` block) |

**Intensity guide:**

| Value | Description | Use For |
|-------|-------------|---------|
| 0.3-0.4 | Very quiet, sparse | Intros, breakdowns |
| 0.5-0.6 | Moderate, controlled | Verses, backgrounds |
| 0.7-0.8 | Full energy | Standard sections |
| 0.9-1.0 | Maximum energy | Choruses, climaxes |

### Arrangement

The arrangement is an ordered list of section names that defines the playback order.
Sections can repeat — each occurrence automatically sounds different (see
[Repeated Sections](#repeated-sections)).

```yaml
arrangement:
  - intro
  - verse
  - chorus
  - verse
  - chorus        # Sounds different from the first chorus
  - bridge
  - chorus        # Sounds different from both previous choruses
  - outro
```

### Harmony & Progressions

Harmony is specified as Roman numeral progressions relative to the song's key and mode.

```yaml
harmony:
  progression: "I V vi IV"    # String format (space-separated)
  chord_rate: 4.0              # Beats per chord (4.0 = one per bar in 4/4)
```

Or as a list:

```yaml
harmony:
  progression: ["I", "V", "vi", "IV"]
```

**Roman numeral rules:**
- **Uppercase** = major: `I`, `II`, `III`, `IV`, `V`, `VI`, `VII`
- **Lowercase** = minor: `i`, `ii`, `iii`, `iv`, `v`, `vi`, `vii`
- **Accidentals**: `bVII` (flat seven), `bIII`, `#IV`

**Common progressions by genre:**

| Genre | Verse | Chorus |
|-------|-------|--------|
| Rock | `i bVII VI bVII` | `VI bVII i bVII` |
| Pop | `I V vi IV` | `I V vi IV` |
| Blues | `I I I I IV IV I I V IV I V` | 12-bar form |
| Jazz | `ii V I vi` | `ii V I I` |
| Funk | `i IV i IV` | `i IV bVII IV` |
| Metal | `i bII i bII` | `i bVI bVII i` |
| Country | `I IV V I` | `I IV V V` |

**Chord rate examples:**
- `4.0` — One chord per bar (default, most genres)
- `2.0` — Two chords per bar (faster changes)
- `8.0` — One chord every two bars (slow harmonic rhythm)
- `1.0` — One chord per beat (very fast, jazz)

### Exports Block

Control which text analysis views are generated alongside the MIDI:

```yaml
exports:
  midi_text:
    enabled: true
    views: ["events", "grid", "tab"]   # Which views to generate
    subdiv: 16                          # Grid resolution per bar
```

- `events` — TSV event log (for debugging and technical analysis)
- `grid` — ASCII piano-roll visualization (useful for all users)
- `tab` — Guitar tablature (only generated for guitar instruments)
- `subdiv` — Steps per bar: `8` (8th notes), `12` (triplets), `16` (16th notes), `32` (32nd notes)

---

## Genres (31)

Setting `genre:` in the song block auto-loads appropriate recipes for drums, bass,
rhythm guitar, and harmony. You don't need to manually configure parameters — the
genre handles defaults.

Before MIDI rendering, Produzre now assigns section-level ensemble roles and
foreground windows. Bass, rhythm guitar, and lead guitar therefore receive
complementary jobs such as anchor, comp, answer, hook, counterline, or support.
Drums own transition fills when present; bass avoids those fill windows, and
rhythm guitar leaves additional space during planned lead phrases.

| Family | Genres |
|--------|--------|
| Rock | `rock`, `hard_rock`, `soft_rock`, `alt_rock`, `prog_rock`, `arena_rock`, `blues_rock`, `pop_rock`, `grunge`, `emo` |
| Metal/Punk | `metal`, `heavy_metal`, `punk`, `ska` |
| Blues/Soul | `blues`, `soul`, `rnb`, `gospel` |
| Jazz | `jazz` |
| Funk | `funk` |
| Pop/Electronic | `pop`, `dance_pop`, `electronic`, `techno`, `new_wave` |
| World/Other | `country`, `reggae`, `latin`, `folk`, `classical` |

---

## Personas

Personas are preset character bundles that configure an instrument's feel. Set them
in the global `instruments:` block or per-section.

```yaml
instruments:
  drums:
    persona: "rock"          # Global persona for all sections
```

Or per-section:

```yaml
sections:
  verse:
    instruments:
      drums:
        params:
          persona: "rock"    # Persona for this section only
```

See the instrument parameter tables below for available personas per instrument.

---

## Instrument Parameters

Parameters are set in `params:` (for named parameters) or `extra:` (for engine-specific
options) blocks under each instrument. Genre recipes provide sensible defaults —
you only need to override when you want something specific.

### Bass

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `persona` | `tight`, `pocket`, `loose`, `funk`, `metal`, `walking`, `dub` | `tight` | Character preset |
| `density` | 0.0-1.0 | 0.57 | Notes per bar density |
| `rhythm_pattern` | `anchor`, `push`, `drive`, `syncopated`, `rock_riff`, `funk_16ths` | `anchor` | Rhythmic feel |
| `articulation_style` | `finger`, `pick`, `slap`, `mute` | `finger` | Playing technique |
| `approach_rate` | 0.0-0.5 | 0.24 | Chromatic approach tones |
| `rest_rate` | 0.0-0.4 | 0.24 | Probability of rests |
| `octave_jump_rate` | 0.0-0.35 | 0.15 | Octave jump probability |
| `fifth_jump_rate` | 0.0-0.3 | 0.10 | Fifth interval probability |
| `lock_to_kick` | 0.0-1.0 | 0.8 | Bass-to-kick drum locking |
| `syncopation` | 0.0-0.6 | 0.0 | Off-beat emphasis |
| `swing` | 0.0-0.35 | 0.0 | Swing feel |
| `fill_rate` | 0.0-0.6 | 0.2 | Fill probability |
| `phrase_len_bars` | 1-8 | 4 | Phrase boundary spacing for fills |
| `section_role_variation` | true/false | false | Let section type bias bass rhythm role |
| `chromatic_rate` | 0.0-0.3 | 0.0 | Chromatic passing tones |
| `motif_repeat_rate` | 0.0-1.0 | recipe | Repeat a two-bar `rock_riff` or `funk_16ths` onset cell |

When `section_role_variation` is enabled and `rhythm_pattern` is left at
`anchor`, choruses lean toward drive patterns and bridges lean toward
syncopation. Phrase fills target the next chord or section resolution.

**Bass personas:**

| Persona | Best For | Key Traits |
|---------|----------|------------|
| `tight` | Rock, metal, punk | Locked to grid, minimal humanization |
| `pocket` | R&B, soul, pop | Slightly behind beat, warm |
| `loose` | Jazz, blues | Swung, timing variation |
| `funk` | Funk, disco | Slap technique, syncopated, busy |
| `metal` | Metal, hard rock | Fast, picked, low register |
| `walking` | Jazz, swing | Quarter notes, smooth voice leading |
| `dub` | Reggae, dub | Sparse, deep, way behind beat |

### Drums

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `persona` | `tight`, `experimental`, `rock`, `metal`, `funk-lite`, `jazz-lite` | `tight` | Character preset |
| `timing_jitter_ms` | 0.0-10.0 | 0.0 | Timing humanization (ms) |
| `velocity_humanize` | 0.0-0.25 | 0.05 | Velocity variation |
| `swing` | 0.0-0.35 | 0.0 | Swing feel |
| `push_pull` | -0.2 to 0.2 | 0.0 | Behind/ahead of beat |
| `accent_strength` | 0.0-0.4 | 0.10 | Accent emphasis |
| `hat_density` | 0.0-1.0 | 1.0 | Hi-hat fill density |
| `fill_rate` | 0.0-0.6 | 0.25 | Fill probability |
| `phrase_len_bars` | 1-8 | auto | Phrase boundary spacing for fills |
| `pickup_rate` | 0.0-1.0 | 0.7 | Transition pickup probability |
| `downbeat_rate` | 0.0-1.0 | 0.8 | Section downbeat crash/kick probability |

Drum transitions are energy-aware: lifts into high-energy sections favor longer
snare/tom/kick pickups, while drops use shorter stop-time pickups with more space.
Phrase fills use genre-weighted setup, tom, kick/snare, cymbal, and roll cells.
Their structural spacing never accelerates below the active drum subdivision.

**Drum personas:**

| Persona | Best For | Key Traits |
|---------|----------|------------|
| `tight` | Clean tracks | Precise, no swing, minimal variation |
| `experimental` | Creative | High humanization, busy fills |
| `rock` | Rock, pop rock | Driving, ghost notes, moderate fills |
| `metal` | Metal, hard rock | Very tight, double-kick, aggressive |
| `funk-lite` | Funk, R&B | Syncopated, open hats, ghost notes |
| `jazz-lite` | Jazz, blues | Loose, swung, ride-heavy |

**Advanced drum voice overrides** (set in `extra:` block):

```yaml
drums:
  extra:
    voices:
      kick:
        syncopation:
          rate: 0.4
        double:
          rate: 0.6
      snare:
        ghosts:
          rate: 0.35
      hats:
        opens:
          rate: 0.2
```

### Rhythm Guitar

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `persona` | `tight`, `loose`, `aggressive`, `funky`, `jangly` | `tight` | Character preset |
| `style` | `auto`, `straight_8s`, `chugs`, `syncopated`, `half_time`, `rock_riff`, `pop_push`, `funk_chanks`, `jazz_comp`, `blues_shuffle`, `country_boom_chuck`, `reggae_skank`, `latin_clave` | `auto` | Strumming pattern |
| `voicing` | `power`, `triad`, `shell`, `octaves`, `auto` | `auto` | Chord voicing type |
| `palm_mute` | 0.0-1.0 | 0.06 | Palm mute probability |
| `register` | `low`, `mid`, `high` | `mid` | Pitch register |
| `density` | 0.0-1.0 | 0.6 | Strum frequency |
| `phrase_len_bars` | 1-8 | 4 | Phrase cycle for bar-to-bar pattern development |
| `phrase_development` | true/false | true | Bar-level pattern variation |
| `swing` | 0.0-1.0 | 0.0 | Swing feel |
| `strum_ms` | 0.0-100.0 | 15.0 | Strum spread time |
| `accent_strength` | 0.0-1.0 | 0.5 | Accent emphasis |

**Rhythm guitar personas:**

| Persona | Best For | Key Traits |
|---------|----------|------------|
| `tight` | Rock, pop, metal | Clean, precise, no swing |
| `loose` | Blues, soul | Laid-back timing, dynamic velocity |
| `aggressive` | Punk, hard rock | Punchy, pushed timing, strong dynamics |
| `funky` | Funk, R&B | Choppy, ghost strums, upbeat emphasis |
| `jangly` | Indie, new wave | Bright, ringing, wide strum spread |

### Lead Guitar

Lead guitar is optional — omit it entirely for songs without lead lines.
Set parameters in `extra:` block.

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `persona` | `balanced`, `melodic`, `shredder`, `bluesy`, `ambient` | `balanced` | Character preset |
| `phrase_len_bars` | 1-4 | 2 | Phrase/motif length |
| `rest_probability` | 0.0-0.85 | 0.25 | Space between phrases |
| `resolution_strength` | 0.0-1.0 | 0.45 | Chord tone emphasis |
| `contour_style` | `stepwise`, `balanced`, `leaping` | `balanced` | Melodic motion |
| `register` | `low`, `mid`, `high`, `very_high`, `full` | `mid` | Melodic range |

Lead motifs now develop across phrases automatically: later phrases reuse the
opening contour with inversion, interval, rhythm, or cadence variation instead
of restarting with unrelated licks. Rock, blues, metal, funk, jazz, country,
and pop select distinct interval and rhythm vocabularies. The ensemble planner
also limits lead notes to foreground windows so accompaniment can answer them.

Use `solo: true` on the instrument for solo sections (denser playing, wider range):

```yaml
lead_gtr:
  intensity: 1.0
  solo: true
  extra:
    phrase_len_bars: 4
    contour_style: "leaping"
```

**Lead guitar personas:**

| Persona | Best For | Key Traits |
|---------|----------|------------|
| `balanced` | General purpose | Moderate phrasing, smooth contour |
| `melodic` | Ballads, pop | Long phrases, stepwise, strong resolution |
| `shredder` | Metal, hard rock | Fast runs, wide leaps, minimal rests |
| `bluesy` | Blues, classic rock | Spacious, chord-tone focus |
| `ambient` | Post-rock, ambient | Sparse, wide intervals, lots of space |

### Acoustic Guitar

Use instead of or alongside rhythm_gtr. Set parameters in `params:` or `extra:`.

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `persona` | `natural`, `precise`, `expressive`, `percussive`, `delicate` | `natural` | Character preset |
| `technique` | `fingerpicking`, `strumming`, `hybrid`, `percussive` | auto | Playing technique |
| `picking_pattern` | `travis`, `pima`, `broken_chord`, `waltz`, `roll` | `travis` | Fingerpick pattern |
| `voicing_style` | `open`, `barre`, `auto` | `auto` | Chord voicing |
| `capo` | 0-12 | 0 | Capo fret position |
| `strum_density` | 0.05-1.0 | varies | Strum frequency |
| `mute_ratio` | 0.0-0.5 | 0.08 | Dampened strum probability |
| `body_tap_ratio` | 0.0-0.5 | 0.0 | Body percussion probability |

**Acoustic guitar personas:**

| Persona | Best For | Key Traits |
|---------|----------|------------|
| `natural` | General purpose | Moderate humanization, open voicings |
| `precise` | Classical, pop | Tight timing, consistent velocity |
| `expressive` | Singer-songwriter | Dynamic velocity, percussive touches |
| `percussive` | Percussive acoustic | Heavy muting, body taps |
| `delicate` | Fingerpicking, ballads | Soft touch, minimal variation |

---

## Seeds, Variation & Reproducibility

### How Seeds Work

Produzre uses a hierarchical RNG (random number generator) system. Every creative
decision — which notes to play, where to place ghost notes, when to add a fill —
is driven by deterministic random numbers seeded from your config.

**The seed hierarchy:**

```
project_seed (per-user, stored locally)
    +
song.seed (in your YAML)
    =
effective_seed (used for generation)
    ↓
section_rng (one per section in the arrangement)
    ↓
instrument_rng (one per instrument per section)
    ↓
voice_rng (one per voice: kick, snare, hats...)
    ↓
event_rng (individual note decisions)
```

This means:
- Changing the kick pattern doesn't affect the snare pattern
- Changing the drums doesn't affect the bass
- Changing one section doesn't affect other sections
- Same config = same output, always

### Seed vs Take vs Variation

These three controls give you different levels of creative exploration:

**`seed`** — Changes everything. Different seeds produce completely different songs.
Use when exploring: "What does seed 42 sound like? How about 43?"

```yaml
song:
  seed: 42    # Try 43, 44, 100, 999...
```

**`take`** — Changes micro-details while keeping the overall structure. Different
takes give you different ghost notes, fills, and accents, but the same groove.
Use when fine-tuning: "I like this song, give me another take."

```yaml
song:
  seed: 42
  take: 0     # Try 1, 2, 3...
```

**`variation`** — A continuous bias (0.0-1.0) that influences how adventurous the
engines are. Higher values mean more unexpected choices. Use when you want the
same seed but with more or less "spice."

```yaml
song:
  seed: 42
  variation: 0.3    # 0.0 = stable, 1.0 = maximum variation
```

### Section-Level Overrides

You can override seed and variation on individual sections. This lets you keep a
song you like but re-roll just one section:

```yaml
sections:
  verse:
    type: verse
    bars: 8
    # No overrides — uses song.seed and song.variation

  chorus:
    type: chorus
    bars: 8
    seed: 999              # Re-roll this entire section
    variation: 0.5         # More variation in the chorus only
```

With this config, the verse sounds exactly the same as the base song, but the
chorus is completely different. Change the chorus `seed` to try alternatives
without touching anything else.

### Instrument-Level Overrides

For even more granular control, override seed and variation on a specific instrument
within a specific section. "I love the chorus but want different drums":

```yaml
sections:
  chorus:
    type: chorus
    bars: 8
    harmony:
      progression: ["VI", "VII", "i", "VII"]
    instruments:
      harmony:
        intensity: 1.0
      drums:
        intensity: 1.0
        seed: 777          # Re-roll ONLY the drums in this section
      bass:
        intensity: 1.0     # Bass stays the same
      rhythm_gtr:
        intensity: 1.0     # Guitar stays the same
```

**Variation cascade** (most specific wins):

```
instrument.variation > section.variation > song.variation
```

### Repeated Sections

When the same section appears multiple times in the arrangement, each occurrence
**automatically sounds different**. You don't need to create `chorus_1`, `chorus_2`:

```yaml
arrangement:
  - verse
  - chorus      # First chorus — unique
  - verse
  - chorus      # Second chorus — automatically different
  - chorus      # Third chorus — also different
```

This happens because the arrangement position index is mixed into the RNG seed.
The section definition is the same, but the output differs at each position.

---

## Projects & Collaboration

### What Is a Project?

A project is a named seed stored on your machine. When you build a song, Produzre
combines your project seed with the song's seed to create the "effective seed" that
actually drives generation.

This means two different users with the same YAML file will get **different output**
by default — each user has their own project seed. This is intentional: it lets
collaborators explore independently.

When you want to sync up and hear the **exact same output**, you share your project
(export/import).

### Your First Project

The first time you run any Produzre command, a default project is automatically
created with a random seed. You don't need to do anything — it just works.

```bash
# See your projects
produzre project list

# See where they're stored
produzre project path

# See your default project details (seed hidden by default)
produzre project show default

# See the actual seed value
produzre project show default -v
```

### Managing Projects

```bash
# Create a new project with a random seed
produzre project create my-album

# Create a project with a specific seed
produzre project create my-album --seed 12345 --notes "Rock album project"

# Set the owner name
produzre project set-owner my-album "Artist Name"

# Add custom metadata
produzre project set-custom my-album genre "rock"
produzre project set-custom my-album band "My Band"

# Remove custom metadata
produzre project unset-custom my-album genre
```

To use a specific project in your song YAML:

```yaml
song:
  title: "My Song"
  project: "my-album"    # Uses this project's seed
  seed: 42
```

If `project:` is omitted, the default project is used.

### Sharing Projects (Collaboration)

To get byte-identical output across machines, share the project seed:

**Alice exports her project:**
```bash
produzre project export my-album --out my-album-project.yml
```

This creates a portable YAML file containing the project seed and metadata.

**Bob imports Alice's project:**
```bash
produzre project import my-album-project.yml
```

Now both Alice and Bob produce identical output from the same YAML config.

**What's in the export file:**
```yaml
schema: 1
project:
  my-album:
    seed: 123456789
    created_at: "2026-03-08T12:34:56Z"
    owner: "Alice"
    notes: "Rock album project"
    exported_at: "2026-03-08T15:00:00Z"
    exported_by: "Alice"
```

**Export options:**
```bash
# Export without the seed (NOT recommended for reproducibility)
produzre project export my-album --out file.yml --no-seed

# Export with all custom metadata
produzre project export my-album --out file.yml --include-all-custom

# Export with specific custom keys only
produzre project export my-album --out file.yml --include genre,band
```

### Backing Up Your Seeds

Your projects registry is a single YAML file. Back it up to preserve your seeds:

```bash
# Find the file
produzre project path
# macOS: ~/Library/Application Support/produzre/projects.yml
# Linux: ~/.config/produzre/projects.yml
# Windows: %APPDATA%\produzre\projects.yml

# Copy it somewhere safe
cp "$(produzre project path)" ~/Dropbox/produzre-backup/projects.yml
```

Or export individual projects:
```bash
produzre project export default --out ~/backups/default-project.yml
produzre project export my-album --out ~/backups/my-album-project.yml
```

---

## CLI Reference

### build

Build a song from a YAML config and export MIDI files.

```bash
produzre build <config> [options]
```

**Arguments:**
- `<config>` — Path to the YAML song configuration file (required)

**Options:**
- `-v, --verbose` — Enable verbose logging
- `--song-name <name>` — Override song name for export filenames
- `--dry-run` — Load and render in memory but do not write any files
- `--no-export-sections` — Skip per-section MIDI clip exports
- `--no-export-patterns` — Skip pattern MIDI and sequence.yaml exports
- `--sections-absolute-timing` — Keep song-global timing in section MIDIs (default: each section starts at beat 0)
- `--strict-determinism` — Build twice and verify byte-identical MIDI output

**Examples:**
```bash
# Basic build
produzre build my-song.yaml

# Verbose output to see what's happening
produzre build my-song.yaml -v

# Dry run to check config without writing files
produzre build my-song.yaml --dry-run

# Override the song name in filenames
produzre build my-song.yaml --song-name "Take 5"

# Build without section clips (faster, smaller output)
produzre build my-song.yaml --no-export-sections --no-export-patterns

# Verify determinism (builds twice and compares)
produzre build my-song.yaml --strict-determinism
```

### validate

Fast validation of a YAML config. Checks parsing, section references, and reports warnings.

```bash
produzre validate <config> [options]
```

**Options:**
- `-v, --verbose` — Show detailed validation output
- `--song-name <name>` — Override song name

**Examples:**
```bash
# Quick validation check
produzre validate my-song.yaml

# Verbose validation with all details
produzre validate my-song.yaml -v
```

### show-config

Print the fully resolved configuration after all parsing, recipe merging, and
persona application. Useful for debugging why an instrument sounds a certain way.

```bash
produzre show-config <config> [options]
```

**Options:**
- `-v, --verbose` — Show detailed config
- `--song-name <name>` — Override song name
- `--format <yaml|json>` — Output format (default: `yaml`)

**Examples:**
```bash
# See the effective config as YAML
produzre show-config my-song.yaml

# See it as JSON
produzre show-config my-song.yaml --format json
```

### project

Manage local project seeds and metadata.

```bash
produzre project <subcommand> [options]
```

| Subcommand | Description | Example |
|------------|-------------|---------|
| `list` | List all projects | `produzre project list` |
| `path` | Print registry file path | `produzre project path` |
| `create <name>` | Create a new project | `produzre project create my-album --seed 42` |
| `show <name>` | Show project details | `produzre project show my-album -v` |
| `export <name>` | Export for sharing | `produzre project export my-album --out file.yml` |
| `import <path>` | Import from file | `produzre project import file.yml` |
| `set-custom <name> <key> <val>` | Set custom metadata | `produzre project set-custom my-album genre rock` |
| `unset-custom <name> <key>` | Remove custom metadata | `produzre project unset-custom my-album genre` |
| `set-owner <name> <owner>` | Set owner name | `produzre project set-owner my-album "Alice"` |

All subcommands accept `-v, --verbose` for more detail.

### user

Manage your local user profile.

```bash
produzre user <subcommand>
```

| Subcommand | Description | Example |
|------------|-------------|---------|
| `path` | Print profile file path | `produzre user path` |
| `show` | Display current profile | `produzre user show` |
| `set <field> <value>` | Set a profile field | `produzre user set name "Alice"` |
| `set-custom <key> <value>` | Set custom metadata | `produzre user set-custom genre jazz` |
| `unset-custom <key>` | Remove custom metadata | `produzre user unset-custom genre` |

Standard fields: `name`, `email`, `url`, `company`, `band`

---

## Understanding the Output

### Export Directory Structure

When you build a song, Produzre creates a timestamped directory:

```
exports/
  My Song_20260308_143052/
  ├── My Song.mid                              # Full multi-track MIDI
  ├── index.yaml                               # Machine-readable metadata
  ├── QUICKREF.txt                             # Human-readable guide for DAW import
  │
  ├── instruments/
  │   ├── drums/
  │   │   ├── My Song_drums.mid                # Full-length drum stem
  │   │   ├── sections/
  │   │   │   ├── My Song_drums_verse.mid      # Drums for verse section
  │   │   │   ├── My Song_drums_chorus.mid     # Drums for chorus section
  │   │   │   └── ...
  │   │   ├── patterns/
  │   │   │   ├── My Song_drums_p001.mid       # Unique pattern 1
  │   │   │   ├── My Song_drums_p002.mid       # Unique pattern 2
  │   │   │   └── ...
  │   │   └── sequence.yaml                    # Pattern sequence metadata
  │   ├── bass/
  │   │   └── ... (same structure)
  │   ├── rhythm_gtr/
  │   │   └── ... (same structure)
  │   └── ...
  │
  └── analysis/                                # Text exports (when enabled)
      ├── drums/
      │   ├── My Song_drums.events.tsv         # Event log
      │   └── My Song_drums.grid.txt           # Piano-roll grid
      ├── bass/
      │   ├── My Song_bass.events.tsv
      │   └── My Song_bass.grid.txt
      ├── rhythm_gtr/
      │   ├── My Song_rhythm_gtr.events.tsv
      │   ├── My Song_rhythm_gtr.grid.txt
      │   └── My Song_rhythm_gtr.tab.txt       # Guitar tab (guitar only)
      └── ...
```

### Full Song MIDI

`My Song.mid` — A single MIDI file containing all instruments as separate tracks.
Import this into any DAW (Logic, Ableton, FL Studio, Reaper, GarageBand) to hear
the complete song. Each track is named by instrument (drums, bass, rhythm_gtr, etc.).

### Stems

`instruments/<instrument>/My Song_<instrument>.mid` — One MIDI file per instrument
spanning the full song length. Use these for:
- **Individual mixing**: Import stems separately for independent volume/FX control
- **Replacing sounds**: Route each stem to a different virtual instrument
- **Selective editing**: Edit one instrument without affecting others

### Section Clips

`instruments/<instrument>/sections/My Song_<instrument>_<section>.mid` — One MIDI
file per instrument per section. Each clip starts at beat 0 (section-relative timing
by default). Use these for:
- **Arrangement editing**: Drag and drop sections in your DAW
- **Loop-based workflow**: Use individual section clips as loops
- **A/B comparison**: Compare different builds of the same section

### Patterns & Sequencer

`instruments/<instrument>/patterns/` — Unique pattern MIDI files extracted from each
instrument's performance. Patterns are deduplicated — if bars 1-2 and bars 5-6
have the same rhythm and notes, they share a pattern ID.

`instruments/<instrument>/sequence.yaml` — Maps sections to pattern sequences:

```yaml
patterns:
  p001:
    file: My Song_drums_p001.mid
    length_beats: 4.0
  p002:
    file: My Song_drums_p002.mid
    length_beats: 4.0
sections:
  verse:
    - p001
    - p002
    - p001
    - _            # "_" means silence/rest
  chorus:
    - p002
    - p002
    - p001
    - p001
```

Use patterns for:
- **Pattern-based DAW workflow**: Build arrangements from pattern blocks
- **Sound design**: Audition individual patterns in isolation
- **Analysis**: See what repeats and what's unique

### Quick Reference File

`QUICKREF.txt` — A plain-text guide designed to be read at a glance:

```
Quick Reference: My Song
Tempo: 120.0 BPM
Key: E minor
Time: 4/4

Section Markers (for DAW):
==================================================

Bar   1 | intro                | intro      | 4 bars
Bar   5 | verse                | verse      | 8 bars
Bar  13 | chorus               | chorus     | 8 bars
Bar  21 | verse                | verse      | 8 bars
Bar  29 | chorus               | chorus     | 8 bars
Bar  37 | outro                | outro      | 4 bars

==================================================
```

### Index File

`index.yaml` — Machine-readable metadata about the build: song settings, section
timings, instruments used, and file paths. Useful for scripts or tools that process
Produzre output programmatically.

---

## Text Exports (Grid, Tab, Events)

Text exports are human-readable representations of the MIDI output. Enable them in
the `exports` block of your YAML config:

```yaml
exports:
  midi_text:
    enabled: true
    views: ["grid", "tab", "events"]
    subdiv: 16
```

### Grid View (ASCII Piano Roll)

The grid view is an ASCII visualization of every note an instrument plays. Time
flows left to right, one column per subdivision step. Each row is a pitch.

**Example (drums):**

```
INSTRUMENT: drums
METER: 4.00 beats/bar   SUBDIV: 16 steps/bar

BAR 1   |1e&a2e&a3e&a4e&a|
KICK    |x---x---x---x---|
SNARE   |----x-------x---|
HAT_C   |x-x-x-x-x-x-x-x|
CRASH   |X---------------|

BAR 2   |1e&a2e&a3e&a4e&a|
KICK    |x---x---x-x-x---|
SNARE   |----x-------.x--|
HAT_C   |x-x-x-x-x-x-x-x|
```

**What the symbols mean:**

| Symbol | Meaning |
|--------|---------|
| `X` | Loud hit (velocity 110+) |
| `^` | Strong hit (velocity 92-109) |
| `x` | Normal hit (velocity 70-91) |
| `.` | Quiet/ghost note (velocity below 70) |
| `g` | Ghost note (snare-specific) |
| `-` | No note at this step |

**Step header guide** (16th-note grid in 4/4):
```
1e&a2e&a3e&a4e&a
│││││││││││││││└ 16th note before beat 1 of next bar
│││└ "a" of beat 1 (last 16th)
││└ "&" of beat 1 (8th note)
│└ "e" of beat 1 (first 16th)
└ Beat 1 (downbeat)
```

The grid is useful for:
- **Quickly seeing rhythmic patterns** without a DAW
- **Comparing builds**: diff two grid files to see what changed
- **Sharing with bandmates** who don't use DAWs
- **Debugging**: see exactly where ghost notes, fills, and accents land

### Tab View (Guitar Tablature)

Generated for guitar instruments only (rhythm_gtr, acoustic_gtr, lead_gtr). Shows
standard 6-string guitar tab with fret numbers on each string.

**Example (rhythm guitar):**

```
RHYTHM_GTR TAB
METER: 4/4   SUBDIV: 16 steps/bar

Bar 1
e|-------------------------------|
B|---5-------5-------5-------5---|
G|---6-------6-------6-------6---|
D|---7-------7-------7-------7---|
A|-0-------0-------0-------0-----|
E|-------------------------------|

Bar 2
e|-------------------------------|
B|---3-------3-------3-------3---|
G|---4-------4-------4-------4---|
D|---5-------5-------5-------5---|
A|-------------------------------|
E|-3-------3-------3-------3-----|
```

**How to read it:**
- Six lines represent the six guitar strings (high E at top, low E at bottom)
- Numbers are fret positions (0 = open string)
- `-` means the string is not played at that step
- Time flows left to right, one position per subdivision step
- Vertical alignment shows notes played simultaneously (chords)

The tab view is useful for:
- **Learning the part**: Read directly as guitar tablature
- **Verifying playability**: Check that fret positions make sense
- **Sharing with guitarists**: Standard notation they already know

### Events View (TSV)

A tab-separated values (TSV) file listing every note event with full timing detail.
This is the most technical view — primarily useful for debugging, scripting, and
detailed analysis.

**Example:**

```
instrument  section_id  bar  beat   start_beat_abs  duration_beats  pitch  note  velocity  channel  program  kind
bass        verse       1    1.000  0.000           1.000           40     E2    70        1        0        root
bass        verse       1    2.000  1.000           1.000           47     B2    65        1        0        fifth
bass        verse       1    3.000  2.000           0.500           40     E2    70        1        0        root
bass        verse       1    3.500  2.500           0.500           41     F2    60        1        0        approach
bass        verse       2    1.000  4.000           1.900           43     G2    72        1        0        root
```

**Column reference:**

| Column | Description |
|--------|-------------|
| `instrument` | Instrument name (drums, bass, rhythm_gtr, etc.) |
| `section_id` | Section name from your YAML |
| `bar` | Bar number (1-indexed) |
| `beat` | Position within bar (1-indexed, fractional) |
| `start_beat_abs` | Absolute beat from song start |
| `duration_beats` | Note length in beats |
| `pitch` | MIDI pitch number (0-127) |
| `note` | Human-readable note name (C4, G#2, etc.) |
| `velocity` | MIDI velocity (0-127) |
| `channel` | MIDI channel (0-15) |
| `program` | MIDI program change number |
| `kind` | Determinism tag — what generated this note |

**The `kind` column** tells you what musical decision created each note:
- Drums: `kick`, `snare`, `snare_ghost`, `hat`, `hat_close`, `open_hat`, `ride`, `crash`, `fill`
- Bass: `root`, `fifth`, `octave`, `approach`, `rest`
- Guitar: `strum`, `chord`, `mute`

This is helpful for debugging: "Why is there a crash here?" Check the `kind` — it
might say `crash_transition`, meaning it was auto-generated at a section boundary.

---

## Config Merge Priority

When multiple config layers set the same parameter, later layers override earlier ones:

1. **Persona defaults** — Base character from the persona YAML file
2. **Genre recipe** — Auto-loaded when `genre:` is set on the song
3. **Global instrument params** — Top-level `instruments:` block
4. **Section instrument params** — Per-section `instruments:` block

**Example:** If the `rock` genre recipe sets `fill_rate: 0.25` and you set
`fill_rate: 0.5` in a section's instrument block, the section value wins.

For seeds and variation, the cascade is:

```
instrument.seed > section.seed > song.seed
instrument.variation > section.variation > song.variation
```

---

## Common Pitfalls

**`harmony: {}` is required.** Every section using bass, rhythm_gtr, lead_gtr, or
acoustic_gtr must include `harmony: {}` (or harmony with parameters) in its
instruments block. Without it, those engines fail with a dependency error. Drums-only
sections don't need harmony.

**Meter must be quoted.** Write `meter: "4/4"`, not `meter: 4/4`. Without quotes,
YAML interprets it as a date or fraction.

**Progressions use Roman numerals, not note names.** Write `"I V vi IV"`, not
`"C G Am F"`. Produzre converts Roman numerals relative to the song's key.

**Intensity is 0.0-1.0.** Don't use `intensity: 70` (percent) — use `intensity: 0.7`.

**Don't duplicate sections for repeats.** You don't need `chorus_1` and `chorus_2`.
Just list `chorus` multiple times in the arrangement — each occurrence automatically
sounds different.

**Check that your genre is valid.** Misspelled genres are silently ignored.
Use `produzre show-config my-song.yaml` to verify recipes loaded correctly.

---

## Generating Song Configs with AI

Describe a song in plain English and get a ready-to-use YAML file — no manual parameter
tuning required. Two options are available depending on which AI platform you use.

### ChatGPT — Produzre Song Builder GPT

The easiest option. Open the [Produzre Song Builder GPT](https://chatgpt.com/g/g-69b2d0cda0088191a7126921c82fedbc-produzre-song-builder)
in ChatGPT and start describing your song. No setup needed.

### Claude — Set Up Your Own Project

Because Anthropic does not support sharing Claude Projects publicly, you set up your
own in a few minutes. See [docs/produzre-claude-project-setup.md](docs/produzre-claude-project-setup.md)
for step-by-step instructions.

The setup guide walks you through creating a Claude Project, uploading the knowledge
files, and pasting a ready-made system prompt. Once configured, you get the same
natural-language-to-YAML experience as the ChatGPT GPT.

### Example Prompts

Both options understand the same kinds of descriptions:

- "Create a 3-minute rock song in E minor with a verse-chorus-verse-chorus-bridge-chorus structure"
- "Make a funk groove at 105 BPM with slap bass and syncopated drums"
- "Translate this Suno prompt to Produzre YAML: 'Dreamy indie folk, fingerpicked acoustic guitar, gentle drums, 90 BPM, melancholic'"
- "That's great — can you make the chorus heavier and add a lead guitar solo?"

### The Reference Document

Both integrations are powered by `docs/llm-song-config-reference.md` — a compact
document containing the complete schema, all 31 genres, all 28 personas, every
parameter table, harmony syntax, and annotated examples. If you want to set up your
own integration (custom GPT, API workflow, etc.), this is the file to use as the
system prompt or knowledge source.

---

## Standalone Executable

Build a standalone executable that bundles Python and all dependencies:

```bash
# Install PyInstaller
pip install pyinstaller

# Build the executable
python scripts/build_executable.py

# Test it
./dist/produzre build examples/minimal.yaml
```

The output is a single binary at `dist/produzre` (macOS/Linux) or `dist/produzre.exe`
(Windows). Users can run it without installing Python or any packages.

To clean and rebuild:

```bash
python scripts/build_executable.py --clean
```

---

## Examples Library

The `examples/` directory contains 150+ working YAML configs organized by category:

```
examples/
├── minimal.yaml                    # Simplest possible config
├── tiny.yaml                       # Drums-only test
├── seed-variation/                  # 5 A/B comparison files for seed/variation
├── genres/                          # One example per genre (31 genres)
│   ├── rock/
│   ├── jazz/
│   ├── funk/
│   ├── blues/
│   └── ... (31 genre folders)
├── personas/                        # Persona showcase files
├── bass/                            # Bass-focused examples
├── drums/                           # Drum-focused examples
├── rhythm_gtr/                      # Rhythm guitar examples
├── lead_gtr/                        # Lead guitar examples
├── acoustic_gtr/                    # Acoustic guitar examples
└── orchestration/                   # Multi-instrument coordination
```

Build all examples:

```bash
python scripts/build_all_examples.py
```

Build a specific category:

```bash
python scripts/build_all_examples.py --dir genres/rock
```
