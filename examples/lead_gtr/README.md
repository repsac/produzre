# Lead Guitar Examples

This directory contains examples demonstrating lead guitar capabilities and parameters.

## Directory Structure

```
lead_gtr/
├── basics/           # Fundamental parameter comparisons
├── styles/           # Genre-specific examples
└── advanced/         # Complex parameter interactions
```

## Examples by Category

### Basics (Parameter Isolation)

**density-comparison.yaml**
- **Purpose**: Compare sparse, moderate, and dense lead guitar approaches
- **Parameters tested**: `rest_probability`, `intensity`
- **Expected behavior**:
  - Sparse: ~1-2 notes/bar
  - Moderate: ~3-5 notes/bar
  - Dense: ~5-8 notes/bar

**resolution-comparison.yaml**
- **Purpose**: Demonstrate harmonic resolution strength effects
- **Parameters tested**: `resolution_strength` (0.2, 0.5, 0.8)
- **Expected behavior**:
  - Low: More passing tones and tension
  - Medium: Balanced chord tones and color notes
  - High: Strong chord tone emphasis

### Styles (Genre-Specific)

**blues-lead.yaml**
- 12-bar blues progression, stepwise motion, 4-bar phrases
- Sparse verse → denser solo section

**rock-solo.yaml**
- High energy, wide intervals, leaping motion
- Build from verse to 16-bar guitar solo

**jazz-lead.yaml**
- ii-V-I progressions, stepwise voice leading, 4-bar phrases
- Head → Solo → Head (standard jazz form)

### Advanced (Complex Behaviors)

**contour-comparison.yaml**
- **Parameters tested**: `contour_style` (stepwise, balanced, leaping)
- Stepwise: 1-3 semitone intervals; Leaping: 5+ semitone jumps

**phrase-length-comparison.yaml**
- **Parameters tested**: `phrase_len_bars` (1, 2, 4)
- 1-bar: riff-like repetition; 4-bar: longer melodic development

## Key Lead Guitar Parameters

### Density & Activity
- **intensity** (0.0-1.0+): Overall energy and note density
- **rest_probability** (0.0-0.85): Amount of space between notes
  - 0.05-0.15: Very dense (solo)
  - 0.20-0.30: Moderate (melodic lead)
  - 0.40-0.50: Sparse (verse backing)
- **solo** (boolean): Enable solo mode (higher density, wider range)

### Melodic Shape
- **contour_style**: Melodic interval behavior
  - `"stepwise"`: Smooth, conjunct motion (2-3 semitones)
  - `"balanced"`: Mix of steps and leaps (default)
  - `"leaping"`: Wide intervals (7-9 semitones)
- **phrase_len_bars** (1-4): Length of repeated motifs

### Harmonic Behavior
- **resolution_strength** (0.0-1.0): Pull toward chord tones
  - 0.2-0.3: More passing tones, "outside" playing
  - 0.5-0.6: Balanced approach
  - 0.7-0.8: Strong chord tone emphasis

### Other Parameters
- **motif_strength** (0.0-1.0): How strongly motifs repeat/develop
- **approach_tones**: `"diatonic"` or `"chromatic"`
- **syncopation** (0.0-1.0): Off-beat emphasis
- **leap_probability** (0.0-1.0): Frequency of large interval jumps
- **leap_min_semitones** (int): Minimum interval size for leaps

## Personas

5 lead guitar personas are available (defined in `produzre/resources/personas/lead_gtr.yml`):

| Persona | Character | Best For |
|---------|-----------|----------|
| **balanced** (default) | Moderate phrasing, smooth contour | General purpose |
| **melodic** | Long phrases, stepwise, strong resolution | Ballads, pop |
| **shredder** | Fast runs, wide leaps, minimal rests | Metal, hard rock |
| **bluesy** | Spacious phrasing, breathing room | Blues, classic rock |
| **ambient** | Sparse, long phrases, wide intervals | Post-rock, ambient |

## Building Examples

```bash
# Build a specific example
python -m produzre.cli build examples/lead_gtr/basics/density-comparison.yaml

# Build all lead guitar examples
for f in examples/lead_gtr/**/*.yaml; do
  python -m produzre.cli build "$f"
done
```

## Analysis Targets

When analyzing output, look for:

1. **Note density**: Count notes per bar in each section
2. **Interval sizes**: Semitone distances between consecutive notes
3. **Chord tone percentage**: Ratio of chord tones to passing tones
4. **Phrase structure**: Motif repetition and variation
5. **Melodic range**: Highest minus lowest pitch in each section
6. **Rest distribution**: Gaps between notes and phrases
