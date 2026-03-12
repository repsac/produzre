# Produzre Examples

This directory contains example song configurations demonstrating various features of Produzre.

## Directory Overview

```
examples/
├── minimal.yaml              # Simplest possible song
├── tiny.yaml                 # Minimal test config
├── seed-variation-basic.yaml # Basic seed/variation demo
├── seed-variation-advanced.yaml # Advanced seed/variation demo
├── acoustic_gtr/             # Acoustic guitar demos
├── bass/                     # Bass engine deep dives
├── drums/                    # Drum engine demos
├── genres/                   # 31 genre directories with 90+ examples
├── lead_gtr/                 # Lead guitar demos
├── orchestration/            # Multi-instrument interaction
├── personas/                 # Persona system demos
├── rhythm_gtr/               # Rhythm guitar demos
└── seed-variation/           # Granular seed & variation override demos
```

## Getting Started

### minimal.yaml

The simplest possible song — one verse section with genre recipe auto-loading:

```bash
python -m produzre.cli build examples/minimal.yaml
```

### Genre Examples

Every genre has a simple example (single section, minimal config) and a full example
(multi-section arrangement). Start with the simple version and compare:

```bash
# Simple rock song
python -m produzre.cli build examples/genres/rock/rock-simple.yaml

# Full rock arrangement (intro → verse → chorus → bridge → solo → outro)
python -m produzre.cli build examples/genres/rock/rock-full-arrangement.yaml
```

See [genres/README.md](genres/README.md) for a complete guide to all 31 genres.

## Creating Your Own Songs

### Basic Structure

```yaml
version: 1
song:
  title: "My Song"
  bpm: 120
  key: C
  mode: ionian  # or dorian, mixolydian, etc.
  meter: "4/4"
  genre: rock   # auto-loads drum/rhythm_gtr/bass/harmony recipes
  seed: 42      # For reproducible randomness
  exports_root: "exports"

sections:
  verse:
    type: verse
    bars: 8
    harmony:
      progression: "I V vi IV"  # Roman numerals
    instruments:
      harmony: {}      # Required dependency for bass/rhythm_gtr
      drums:
        intensity: 0.7
      bass:
        intensity: 0.7
      rhythm_gtr:
        intensity: 0.7

arrangement:
  - verse
```

### Genre Recipe System

Setting `genre:` at the song level auto-loads recipes for drums, rhythm guitar, bass,
and harmony — no manual parameter tuning needed. There are 29 bass recipes, plus drum
and rhythm guitar recipes for each genre.

**Available genres** (31 total):

| Family | Genres |
|--------|--------|
| **Rock** | rock, hard_rock, soft_rock, alt_rock, prog_rock, arena_rock, blues_rock, pop_rock, grunge, emo |
| **Metal/Punk** | metal, heavy_metal, punk, ska |
| **Blues/Soul** | blues, soul, rnb, gospel |
| **Jazz** | jazz |
| **Funk** | funk |
| **Pop/Electronic** | pop, dance_pop, electronic, techno, new_wave |
| **World/Other** | country, reggae, latin, folk, classical |

### Available Section Types

- `intro` — Opening section (low energy)
- `verse` — Main verses (moderate energy)
- `prechorus` — Pre-chorus build (moderate-high energy)
- `chorus` — Chorus/hook (high energy)
- `bridge` — Contrasting section (moderate-high energy)
- `solo` — Instrumental solo section
- `breakdown` — Sparse, minimal section
- `outro` — Ending section (low energy)

### Important: Harmony Dependency

Any section using `bass`, `rhythm_gtr`, `acoustic_gtr`, or `lead_gtr` **must** include
`harmony: {}` in the instruments block. The harmony engine provides chord progression
data that other engines depend on:

```yaml
instruments:
  harmony: {}        # Required — provides chord data
  bass:
    intensity: 0.7
  rhythm_gtr:
    intensity: 0.7
```

## Instrument Parameters

All instruments support these base parameters:

```yaml
instruments:
  bass:
    intensity: 0.7        # 0.0-1.0, affects velocity and density
    style_bias: 0.0       # -1.0 to +1.0, style variation
    offset_beats: 0.0     # Timing offset (ahead/behind)
    seed: null            # Override section RNG seed
    variation: null       # Override global variation
    solo: false           # Enable solo mode (if supported)
    params:
      persona: "tight"    # Load a persona preset
```

### Engine-Specific Parameters

Engine parameters go in the `params:` block (or `extra:` for some engines).

#### Bass

See [bass/README.md](bass/README.md) for full parameter documentation and examples.

Key parameters: `density`, `rhythm_pattern` (anchor/push/drive/syncopated),
`articulation_style` (finger/pick/slap/mute), `approach_rate`, `rest_rate`,
`octave_jump_rate`, `fifth_jump_rate`, `lock_to_kick`, `fill_rate`.

7 personas: tight, pocket, loose, funk, metal, walking, dub.

#### Drums

See [drums/README.md](drums/README.md) for full parameter documentation and examples.

Key parameters: `timing_jitter_ms`, `velocity_humanize`, `swing`, `push_pull`,
`accent_strength`, `hat_density`, `fill_rate`, `fill_chatter`.

6 personas: tight, experimental, rock, metal, funk-lite, jazz-lite.

#### Rhythm Guitar

See [rhythm_gtr/README.md](rhythm_gtr/README.md) for full parameter documentation.

Key parameters: `style` (chug/strum/syncopated/half_time/auto), `voicing` (power/triad/shell/octaves/auto),
`palm_mute`, `strum_style`, `register`, `swing`, `chuck_rate`, `strum_ms`.

5 personas: tight, loose, aggressive, funky, jangly.

#### Lead Guitar

See [lead_gtr/README.md](lead_gtr/README.md) for full parameter documentation.

Key parameters: `phrase_len_bars`, `rest_probability`, `resolution_strength`,
`contour_style` (stepwise/balanced/leaping), `syncopation`, `leap_probability`.

5 personas: balanced, melodic, shredder, bluesy, ambient.

#### Acoustic Guitar

See [acoustic_gtr/README.md](acoustic_gtr/README.md) for full parameter documentation.

Key parameters: `technique` (fingerpicking/strumming/hybrid/percussive), `picking_pattern`,
`voicing_style` (open/barre/auto), `capo`, `mute_ratio`, `body_tap_ratio`.

5 personas: natural, precise, expressive, percussive, delicate.

## Custom Engines

See [ENGINES.md](../produzre/engine/ENGINES.md) for a complete guide on creating custom instrument engines.

Quick steps:
1. Create a Python module with `render_into_timeline()` function
2. Register in `engines.yml` or override in your song YAML
3. Use in section `instruments` block

Example custom engine registration in song YAML:

```yaml
engines:
  my_synth:
    engine: "my_package.engines.synth"  # Python import path
    priority: 5
    channel: 7
    program: 80
    requires: ["harmony.plan"]

sections:
  verse:
    instruments:
      my_synth:
        intensity: 0.7
```

## Output Files

After building, check the `exports/` directory:

- `<song_name>.mid` — Full multi-track MIDI file
- `stems/<instrument>.mid` — Per-instrument MIDI stems
- `sections/<section_id>.mid` — Per-section MIDI files
- `patterns/<pattern_id>.mid` — Per-pattern MIDI files (if applicable)
- `seq/<instrument>.yml` — Sequencer YAML (if enabled)

## Tips

### Reproducible Output

Use the same `seed` value for identical results:

```yaml
song:
  seed: 42  # Same seed = same output
```

### Dry Run

Preview without generating files:

```bash
python -m produzre.cli build my_song.yaml --dry-run -v
```

### Show Configuration

View effective configuration (with defaults applied):

```bash
python -m produzre.cli show-config my_song.yaml
```

### Verbose Output

See detailed execution logs:

```bash
python -m produzre.cli build my_song.yaml -v
```

## Troubleshooting

### Missing Dependencies Error

```
ConfigError: Engine 'bass' has unsatisfied dependencies:
  - Missing 'harmony.plan' (provided by: 'harmony')
```

**Solution**: Add `harmony: {}` to your section instruments:

```yaml
instruments:
  harmony: {}
  bass:
    intensity: 0.7
```

### No Events Generated

If an instrument produces 0 events, check:
- Is the instrument enabled in `engines.yml`?
- Is the instrument listed in the section's `instruments` block?
- Does it have `harmony: {}` if required?
- Check verbose logs for warnings: `-v` flag

### Different Output with Same Seed

Ensure all randomness uses the section RNG:

```python
# Good: Deterministic
rng = kwargs.get("rng")
if rng.random() < 0.5:
    add_variation()

# Bad: Non-deterministic
import random
if random.random() < 0.5:  # DON'T
    add_variation()
```

## Resources

- [Engine Authoring Guide](../produzre/engine/ENGINES.md) — Complete engine development guide
- [Engine Registry](../produzre/resources/engines.yml) — Available engines and settings
