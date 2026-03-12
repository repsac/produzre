# Rhythm Guitar Examples

This directory contains examples demonstrating rhythm guitar styles, strumming patterns, and voicing options.

## Directory Structure

```
rhythm_gtr/
├── strum-style-comparison.yaml    - Compares different strumming styles
└── sustained-chords-demo.yaml     - Demonstrates sustained chord voicings
```

## Examples by Category

### Strumming Styles

**strum-style-comparison.yaml**
- **Purpose**: Compare different strumming approaches side by side
- **Parameters tested**: `strum_style` (balanced, downbeat_heavy, upbeat_heavy)
- **Use case**: Understanding how strum style shapes the rhythmic feel

### Sustained Chords

**sustained-chords-demo.yaml**
- **Purpose**: Demonstrate sustained chord voicings and how they interact with other parameters
- **Parameters tested**: `sustain_cut_rate`, `voicing`
- **Use case**: Pad-like rhythm parts, ambient sections, slow ballads

## Key Rhythm Guitar Parameters

### Style (Overall Pattern)
- **style**: Overall rhythmic approach
  - `"auto"`: Engine selects based on genre/tempo
  - `"chug"`: Tight, palm-muted chugging (metal, hard rock)
  - `"strum"`: Open chord strumming (pop, folk, country)
  - `"syncopated"`: Off-beat accented patterns (funk, reggae)
  - `"half_time"`: Half-time feel (breakdowns, ballads)

### Strum Style (Accent Distribution)
- **strum_style**: Where rhythmic emphasis falls
  - `"balanced"`: Even distribution across beats
  - `"downbeat_heavy"`: Emphasis on downbeats (straight rock, country)
  - `"upbeat_heavy"`: Emphasis on upbeats (reggae, ska, funk)

### Density & Activity
- **density** (0.0-1.0): How many strums/hits per bar
  - 0.1-0.3: Sparse, open chords with space
  - 0.4-0.6: Moderate strumming
  - 0.7-1.0: Dense, driving rhythm

### Voicing
- **voicing**: Chord voicing type
  - `"power"`: Root-fifth power chords (rock, metal)
  - `"triad"`: Full three-note triads
  - `"shell"`: Root-third or root-seventh shells (jazz)
  - `"octaves"`: Octave doubling
  - `"auto"`: Engine selects based on genre context

### Articulation & Feel
- **palm_mute** (0.0-1.0): Amount of palm muting applied
  - 0.0: Fully open strings
  - 0.5: Moderate muting
  - 1.0: Fully muted (tight chug)
- **accent_strength** (0.0-1.0): Velocity difference between accented and unaccented hits
- **swing** (0.0-1.0): Swing feel amount (0.0 = straight, 1.0 = full triplet swing)
- **strum_ms** (0.0-100.0): Strum spread in milliseconds (0 = block chord, higher = more natural strum roll)

### Register & Dynamics
- **register**: Pitch register for voicings
  - `"low"`: Lower fret positions
  - `"mid"`: Middle register
  - `"high"`: Upper fret positions

### Rhythmic Modifiers
- **chuck_rate** (0.0-1.0): Frequency of percussive muted "chucks" between strums
- **sustain_cut_rate** (0.0-1.0): How often notes are cut short (staccato vs. legato)
- **downbeat_boost** (0.0-1.0): Extra velocity emphasis on beat 1
- **section_contrast** (0.0-1.0): How much parameters shift between sections (verse vs. chorus)

## Personas

Five personas are available in `produzre/resources/personas/rhythm_gtr.yml`:

- **tight** - Precise, locked to grid, minimal variation
- **loose** - Relaxed timing, dynamic velocity, laid-back feel
- **aggressive** - Tight but punchy, strong dynamics, pushed feel
- **funky** - Syncopated, choppy, ghost strums, upbeat heavy
- **jangly** - Bright, ringing chords, light touch, wide strums

Use personas in your config:

```yaml
rhythm_gtr:
  persona: "tight"
```

## Building Examples

```bash
# Build a specific example
python -m produzre.cli build examples/rhythm_gtr/strum-style-comparison.yaml

# Build all rhythm guitar examples
for f in examples/rhythm_gtr/*.yaml; do
  python -m produzre.cli build "$f"
done
```

## Tips and Best Practices

### Choosing a Style
- **Chug** - Metal, djent, hard rock verses
- **Strum** - Acoustic-driven pop, folk, singer-songwriter
- **Syncopated** - Funk, reggae, R&B
- **Half_time** - Breakdowns, intros, ballad sections

### Voicing Selection
- **Power** chords work best with high `palm_mute` and `density` for driving rock/metal
- **Triads** suit pop and folk styles with moderate `density`
- **Shell** voicings pair well with jazz and R&B at lower `density`
- **Octaves** add punch to single-note riff passages

### Strum Realism
- Set `strum_ms` between 15-40 for a natural strum roll
- Combine `chuck_rate: 0.2-0.3` with `strum_style: "upbeat_heavy"` for funky rhythm parts
- Use `accent_strength: 0.4-0.6` to add dynamic interest without overpowering

### Combining Features

**Driving Rock:**
```yaml
rhythm_gtr:
  params:
    style: "chug"
    voicing: "power"
    density: 0.8
    palm_mute: 0.7
    downbeat_boost: 0.5
```

**Funk Rhythm:**
```yaml
rhythm_gtr:
  params:
    style: "syncopated"
    strum_style: "upbeat_heavy"
    voicing: "triad"
    density: 0.7
    chuck_rate: 0.3
    accent_strength: 0.6
```

**Clean Ballad:**
```yaml
rhythm_gtr:
  params:
    style: "strum"
    voicing: "triad"
    density: 0.3
    palm_mute: 0.0
    strum_ms: 30
    sustain_cut_rate: 0.1
```
