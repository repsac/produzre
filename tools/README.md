# MIDI Analysis Tools

Tools for analyzing MIDI files to extract genre-specific statistics and generate
engine recipes and tuning recommendations for Produzre.

## Overview

There are two independent pipelines:

### Multi-instrument Analysis Pipeline

A 4-phase pipeline that analyzes any MIDI file for bass, drums, rhythm guitar,
and lead guitar statistics.  Each phase is an independent library module.

```
MIDI files ─┐
             │   batch_analyze.py
manifest ───┤   (orchestrator)
             │       │
             │   ┌───┴────────────────────────────────┐
             │   │ 1. midi_parse.py     Parse & norm   │
             │   │ 2. role_classify.py  Role detection  │
             │   │ 3. groove_extract.py Timing/groove   │
             │   │ 4. pattern_mine.py   Style profiles  │
             │   └───┬────────────────────────────────┘
             │       │
             │   genre_stats.json
             │       │
             ├───────┼───────────────────┐
             │       │                   │
     generate_recipes.py    apply_learned_defaults.py
        (recipes + tuning)    (default recommendations)
```

### Drum Recipe Training Pipeline

A focused pipeline for training drum groove recipes from a structured MIDI
archive.  Quantizes drum hits to a 16-step grid and computes per-step hit
probabilities to derive groove templates.

```
MIDI archive ──► build_drum_manifest.py ──► manifest.yaml
                                                │
                                    train_drum_recipes.py
                                                │
                                    recipes/drums/*.yaml
```

## Prerequisites

```bash
pip install mido    # MIDI parsing (required)
pip install pyyaml  # YAML manifest/recipe support (required for drum pipeline)
```

## Quick Start

```bash
# --- Multi-instrument analysis ---
# Analyze all MIDI files in a directory
python tools/batch_analyze.py /path/to/midi/files

# With genre metadata from a manifest
python tools/batch_analyze.py /path/to/midi -m manifest.yaml --output results/

# Generate recipes from analysis
python tools/generate_recipes.py --input results/genre_stats.json

# Review default recommendations
python tools/apply_learned_defaults.py --input results/genre_stats.json

# --- Drum recipe training ---
# Build a manifest from a drum MIDI archive
python tools/build_drum_manifest.py /path/to/drum/archive

# Train drum recipes from the manifest
python tools/train_drum_recipes.py --manifest manifest.yaml --archive-dir /path/to/drum/archive
```

## Pipeline Scripts

### `batch_analyze.py` — Batch Analysis Orchestrator

Recursively discovers MIDI files, runs the 4-phase analysis pipeline on each,
and aggregates per-genre statistics.

```
python tools/batch_analyze.py <input_dir> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `input_dir` | Directory containing MIDI files (searched recursively) |
| `-m`, `--manifest` | Path to a YAML or JSONL manifest with genre metadata |
| `--max-per-genre` | Max files to sample per genre (default: 80) |
| `--output` | Output directory for results (default: `analysis_output`) |
| `--genres` | Comma-separated list of genres to include (default: all) |
| `--timeout` | Per-file analysis timeout in seconds (default: 30) |
| `--verbose` | Enable debug logging |

**Manifest formats:**

YAML (flat or nested artist-block layout):
```yaml
# Flat
- file: path/to/song.mid
  genres: [rock, blues]

# Nested (artist-block)
- artist: Someone
  genres: [rock]
  tracks:
    - file: song1.mid
    - file: song2.mid
      genres: [blues]  # per-track override
```

JSONL (one JSON object per line):
```
{"file": "path/to/song.mid", "genres": ["rock", "blues"]}
```

File paths are resolved relative to the manifest's parent directory.

**Output files:**

| File | Format | Description |
|------|--------|-------------|
| `genre_stats.json` | JSON | Per-genre aggregated statistics (mean, median, stdev, min, max) |
| `file_results.jsonl` | JSONL | Per-file raw analysis results |

---

### `generate_recipes.py` — Recipe Generator

Reads `genre_stats.json` and generates bass recipe YAML files plus a tuning
recommendations report for drums and rhythm guitar.

```
python tools/generate_recipes.py --input <genre_stats.json> [options]
```

| Argument | Description |
|----------|-------------|
| `--input` | Path to `genre_stats.json` (required) |
| `--output-bass` | Output directory for bass recipes (default: `produzre/resources/recipes/bass`) |
| `--output-report` | Output path for tuning report JSON (default: `tuning_report.json`) |
| `--min-files` | Minimum files per genre to generate a recipe (default: 3) |

**What it generates:**

- **Bass recipes** — one YAML per genre, with density, rhythm pattern, articulation,
  approach rate, octave/fifth jumps, swing, and other parameters derived from
  statistical analysis.
- **Tuning report** — JSON with per-genre drum and rhythm guitar recommendations
  (ghost rate, fill rate, hat mode, voicing style, palm mute ratio, etc.).

---

### `apply_learned_defaults.py` — Default Recommendations

Performs cross-genre analysis on `genre_stats.json` and prints recommended
changes to engine default values with statistical evidence.

```
python tools/apply_learned_defaults.py --input <genre_stats.json>
```

| Argument | Description |
|----------|-------------|
| `--input` | Path to `genre_stats.json` (required) |

This tool does **not** modify any code — it only prints recommendations for
a human to review and apply.

---

### `build_drum_manifest.py` — Drum Archive Manifest Builder

Walks a directory tree of drum MIDI files and builds a structured YAML manifest
with automatically extracted metadata (genre, BPM, time signature, feel, etc.).

```
python tools/build_drum_manifest.py <archive_dir> [options]
```

| Argument | Description |
|----------|-------------|
| `archive_dir` | Root directory containing drum MIDI files (searched recursively) |
| `--output` | Output YAML path (default: `<archive_dir>/manifest.yaml`) |
| `--compact` | Omit individual filenames (folder metadata only) |

**Metadata extraction:** Genre, region, BPM, time signature, feel, and musical
function are inferred from folder names and file paths using keyword matching.
Recognizes common drum library naming conventions (Superior Drummer 2, GM MIDI
Pack, decade-themed packs).

---

### `train_drum_recipes.py` — Drum Recipe Trainer

Reads a manifest (from `build_drum_manifest.py`), loads MIDI files by genre,
quantizes events to a 16-step grid, and writes groove recipe YAMLs.

```
python tools/train_drum_recipes.py --manifest <manifest.yaml> --archive-dir <dir> [options]
```

| Argument | Description |
|----------|-------------|
| `--manifest` | Path to manifest YAML (required) |
| `--archive-dir` | Root directory of the MIDI archive (required) |
| `--output-dir` | Recipe output directory (default: `produzre/resources/recipes/drums`) |
| `--genres` | Space-separated list of genres to train (default: all) |
| `--max-files` | Max MIDI files per genre (default: 2000) |
| `--min-files` | Minimum files to produce a recipe (default: 3) |
| `--dry-run` | Print recipes to stdout without writing files |
| `--verbose` | Print per-step probability grids for debugging |

**What it produces:** One recipe YAML per genre containing kick/snare/hat patterns,
ghost note positions, swing feel, fill rate, and other groove parameters derived
from statistical analysis of hit probabilities.

---

## Library Modules

These modules implement the 4 analysis phases.  They are imported by
`batch_analyze.py` but can also be used standalone for custom analysis scripts.

### `midi_parse.py` — Phase 1: MIDI Parsing

Parses a MIDI file into normalized `NoteEvent` objects with beat-aligned timing.

**Key exports:**
- `parse_midi_file(path, song_id) -> MIDIAnalysis`
- `NoteEvent` — dataclass with track, channel, pitch, velocity, beat position, duration
- `MIDIAnalysis` — dataclass with events, tempo map, time signatures, key signatures

### `role_classify.py` — Phase 2: Role Classification

Classifies MIDI tracks/channels into instrument roles (drums, bass, rhythm guitar,
lead guitar, other) using pitch range, density, polyphony, and sustain heuristics.

**Key exports:**
- `classify_roles(analysis) -> List[RoleClassification]`
- `RoleClassification` — dataclass with role, confidence, rationale, pitch stats

### `groove_extract.py` — Phase 3: Groove Extraction

Analyzes timing micro-variations to characterize groove feel — swing ratio,
push/pull tendency, syncopation intensity, and accent patterns.

**Key exports:**
- `extract_groove_features(analysis) -> GrooveFeatures`
- `GrooveFeatures` — dataclass with swing, push/pull, syncopation, accent metrics

### `pattern_mine.py` — Phase 4: Pattern Mining

Extracts reusable style features per instrument role without copying exact patterns.
Produces statistical profiles for drums, bass, rhythm guitar, and lead guitar.

**Key exports:**
- `extract_patterns(analysis, roles) -> Dict[str, profile]`
- `DrumProfile` — kick/snare/hat density, fills, ghosts, accents
- `BassProfile` — notes/bar, root ratio, step motion, staccato, sustain
- `RhythmProfile` — chords/bar, polyphony, palm mute, downbeat/upbeat ratio
- `LeadProfile` — phrase length, contour, note density, rest ratio

## Output Schema

The `genre_stats.json` output contains an array of genre objects:

```json
[
  {
    "genre": "rock",
    "file_count": 42,
    "bpm_values": {"n": 42, "mean": 123.5, "median": 120.0, "stdev": 15.2, "min": 80.0, "max": 180.0},
    "swing_values": {"n": 40, "mean": 0.502, ...},
    "bass_notes_per_bar": {"n": 35, "mean": 5.8, ...},
    "drum_kick_density": {"n": 38, "mean": 3.2, ...},
    ...
  }
]
```

Each metric field contains `{n, mean, median, stdev, min, max}` computed across
all files in that genre.  See `GenreStats` in `batch_analyze.py` for the full
list of tracked metrics.
