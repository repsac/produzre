# Changelog

## [0.8.0] — 2026-03-11 — First Public Release

**Produzre** is a deterministic, section-based procedural MIDI engine. Describe your song in YAML and get a fully-produced multi-track MIDI arrangement — drums, bass, guitars, harmony — reproducibly, every time.

---

### What is Produzre?

Write a YAML file describing your song's structure, genre, and instrumentation. Produzre renders complete arrangements that can be imported directly into any DAW as multi-track MIDI. The same config + seed always produces byte-identical output.

---

### Core Features

#### Instrument Engines

Six production-ready engines render in a coordinated pipeline:

| Engine | Role |
|---|---|
| `harmony` | Chord planning from Roman numeral progressions; feeds all melodic engines |
| `drums` | Multi-voice kit — kick, snare, hats, crash, ride — with fills and swing |
| `bass` | Chord-tone bass lines, kick-locked, with approach notes and octave/fifth jumps |
| `rhythm_gtr` | Strumming and arpeggio patterns, harmony-aware |
| `lead_gtr` | Phrase-based soloing within scale |
| `acoustic_gtr` | Fingerpicked and strummed acoustic patterns |

A seventh engine (`arpeggiator`) ships as a working example for building custom engines.

#### Genre-Aware Recipes

Set `genre:` in your config and parameter presets load automatically. 31 genres supported including rock, metal, jazz, funk, blues, folk, classical, reggae, bossa nova, and more. Bass recipes were generated from analysis of 2,275 real MIDI files across 116 genres.

#### Persona System

Character presets for each instrument that bundle multiple parameters into a single keyword:

- **Bass:** `tight`, `pocket`, `loose`, `funk`, `metal`, `walking`, `dub`
- **Drums:** `tight`, `rock`, `experimental`, `metal`, `funk-lite`, `jazz-lite`
- **Rhythm/Lead/Acoustic guitar:** 5 personas each

#### Deterministic Reproducibility

Hierarchical seeding from project → song → take → section → instrument → event. Same YAML + same seed = byte-identical MIDI output. Verify with `--strict-determinism`. Explore variations with `take:` without changing your arrangement.

#### Flexible Overrides

Config merges in priority order: persona → recipe → global instrument params → section params. Override anything at any level.

---

### Outputs

From a single `produzre build` command:

- **Full-track MIDI** — all instruments in one multi-track file
- **Stems** — one MIDI per instrument
- **Section clips** — per-section MIDIs for loop-based workflows
- **Pattern sequences** — unique deduplicated patterns with metadata
- **Index + QUICKREF** — build metadata and human-readable section map
- **ASCII piano rolls** — grid view with velocity symbols (optional)
- **Guitar tablature** — standard 6-string tab for guitar engines (optional)
- **Event log** — TSV with pitch, velocity, duration, note kind per event (optional)

---

### CLI

```
produzre build <config.yaml>          Build MIDI from YAML config
produzre validate <config.yaml>       Validate config without building
produzre show-config <config.yaml>    Print fully-resolved config

produzre project create <name>        Create a named project (persistent seed registry)
produzre project export/import        Share projects with collaborators
produzre project list/show            Browse projects

produzre user set <field> <value>     Store name, email, band, custom fields
```

Key build flags: `--dry-run`, `--strict-determinism`, `--no-export-sections`, `--no-export-patterns`, `-v`

---

### Configuration

Minimal example:

```yaml
version: 1

song:
  title: My Song
  bpm: 120
  key: E
  mode: minor
  genre: rock
  seed: 42

sections:
  verse:
    bars: 8
    harmony:
      progression: "i bVII VI i"
      chord_rate: 4.0
    instruments:
      harmony: {}
      drums: {}
      bass: {}
      rhythm_gtr: {}

arrangement:
  - verse
  - verse
```

See [docs/llm-song-config-reference.md](docs/llm-song-config-reference.md) for the complete reference, and [examples/](examples/) for 150+ working configs covering genres, personas, and parameter tuning.

---

### Extending Produzre

Custom engines can be added without modifying orchestration code. Implement `render_into_timeline()`, register in `resources/engines.yml`, and ship as a standalone module. See [produzre/engine/ENGINES.md](produzre/engine/ENGINES.md).

---

### Installation

**From source:**

```bash
git clone <repo>
pip install mido pyyaml
produzre build examples/minimal.yaml
```

**Standalone binary** (no Python required):

```bash
python scripts/build_executable.py
./dist/produzre build examples/minimal.yaml
```

**Requirements:** Python 3.9+, `mido >= 1.3.0`, `PyYAML >= 6.0`

---

### Examples

```bash
# Rock song with two sections
produzre build examples/genres/rock.yaml

# Explore micro-variations — same structure, different feel
produzre build song.yaml  # take: 0
# edit song.yaml: set take: 1
produzre build song.yaml  # take: 1

# Inspect the fully-resolved config before building
produzre show-config song.yaml

# Verify reproducibility
produzre build song.yaml --strict-determinism
```
