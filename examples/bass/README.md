# Bass Examples

This directory contains comprehensive bass guitar examples organized by technique and feature.

## Directory Structure

```
bass/
├── articulation/      - Playing styles (finger, pick, slap, mute)
├── rhythm/            - Rhythmic patterns (anchor, drive, push, syncopated)
├── techniques/        - Passing tones and walking bass
├── grooves/           - Groove techniques (pedal tones, octave jumps, fifth drops)
├── fills/             - Bass fill variations
├── slap/              - Slap bass technique demonstrations
├── advanced/          - Advanced features (solos, motion styles)
└── baseline/          - Basic starting examples
```

## Quick Reference

### Articulation (Playing Styles)
- `style-finger.yaml` - Fingerstyle playing (warm, sustained)
- `style-pick.yaml` - Picked bass (bright, articulate)
- `style-slap.yaml` - Slap bass (percussive, funky)
- `style-mute.yaml` - Palm-muted bass (short, tight)

### Rhythm Patterns
- `rhythm-anchor.yaml` - Root-focused, steady pattern
- `rhythm-drive.yaml` - Forward-pushing rhythm
- `rhythm-push.yaml` - Syncopated push feel
- `rhythm-syncopated.yaml` - Complex syncopation

### Techniques
- `passing-none.yaml` - No passing tones (simple roots)
- `passing-diatonic.yaml` - Scale-based passing tones
- `passing-chromatic.yaml` - Chromatic approaches
- `passing-walking.yaml` - Continuous walking bass
- `walking-blues.yaml` - Blues walking bass
- `walking-jazz.yaml` - Jazz walking bass
- `walking-vs-pocket.yaml` - Walking vs. pocket groove comparison

### Grooves
- `groove-pedal-tones.yaml` - Sustained root notes
- `groove-octave-jumps.yaml` - Octave variation
- `groove-fifth-drops.yaml` - Fifth interval movement
- `groove-combined.yaml` - Multiple groove techniques

### Fills
- `fills-minimal.yaml` - Simple, sparse fills
- `fills-pocket.yaml` - Groove-focused fills
- `fills-funk.yaml` - Funky, active fills

### Slap Technique
- `slap-vs-finger.yaml` - Slap vs. finger comparison
- `slap-conservative.yaml` - Subtle slap technique
- `slap-funk.yaml` - Aggressive funk slapping

### Advanced
- `solo-pocket.yaml` - Pocket-style bass solo
- `solo-funk.yaml` - Funk bass solo
- `solo-comparison.yaml` - Solo style comparison
- `motion-style-demo.yaml` - Voice leading motion styles (stepwise, leaping, mixed)

### Baseline
- `baseline-demo.yaml` - Basic bass demonstration
- `chord-changes-demo.yaml` - Following chord changes
- `chord-changes-minor.yaml` - Minor key chord following
- `negotiation-baseline.yaml` - Cross-instrument negotiation

## Key Parameters

### articulation_style
- `finger` - Warm, sustained notes
- `pick` - Bright, attack-heavy
- `slap` - Percussive, short
- `mute` - Very short, tight

### rhythm_pattern
- `anchor` - Steady, root-focused
- `drive` - Forward-pushing
- `push` - Syncopated feel
- `syncopated` - Complex rhythms

### motion_style (Phase 4.2)
- `stepwise` - Smooth voice leading (small intervals)
- `leaping` - Angular jumps (large intervals)
- `mixed` - Random combination

### Other Important Parameters
- `density` (0.0-1.0) - How many notes to play
- `lock_to_kick` (0.0-1.0) - How closely to follow kick drum
- `passing_tone_rate` (0.0-1.0) - Frequency of passing tones
- `fill_rate` (0.0-1.0) - Frequency of fills

## Learning Path

### Beginner
1. Start with `baseline/baseline-demo.yaml`
2. Try different articulation styles in `articulation/`
3. Explore rhythm patterns in `rhythm/`

### Intermediate
1. Learn passing tones in `techniques/`
2. Practice fills in `fills/`
3. Experiment with grooves in `grooves/`

### Advanced
1. Master slap technique in `slap/`
2. Study solos in `advanced/`
3. Explore motion styles and voice leading

## Building Examples

```bash
# Build all examples in a category
python3 -m produzre.cli build examples/bass/articulation/*.yaml

# Build specific example
python3 -m produzre.cli build examples/bass/advanced/motion-style-demo.yaml

# Build all bass examples
for dir in articulation rhythm techniques grooves fills slap advanced baseline; do
  for f in examples/bass/$dir/*.yaml; do
    python3 -m produzre.cli build "$f"
  done
done
```

## Tips and Best Practices

### Choosing Articulation
- **Finger** - Jazz, blues, soul, classic rock
- **Pick** - Punk, metal, hard rock, country
- **Slap** - Funk, fusion, modern R&B
- **Mute** - Reggae, ska, some funk

### Rhythm Pattern Selection
- **Anchor** - Simple songs, ballads, straightforward grooves
- **Drive** - Energetic rock, punk, driving songs
- **Push** - Funk, R&B, syncopated styles
- **Syncopated** - Jazz, fusion, complex arrangements

### Passing Tones
- Start with `passing_tone_rate: 0.2` for subtle movement
- Increase to 0.4-0.5 for jazz walking bass
- Use `motion_style: stepwise` for smooth walking lines
- Combine with high `density` (0.85-0.95) for continuous lines

### Fills
- Use `fill_rate: 0.2-0.3` for occasional fills
- Increase for more active bass lines
- Combine with appropriate articulation for style

## Combining Features

Bass parameters work together - here's an effective combination for different styles:

**Funk Bass:**
```yaml
bass:
  params:
    density: 0.9
    rhythm_pattern: "syncopated"
    articulation_style: "slap"
    lock_to_kick: 0.7
```

**Jazz Walking:**
```yaml
bass:
  params:
    density: 0.95
    rhythm_pattern: "anchor"
    articulation_style: "finger"
    motion_style: "stepwise"
    passing_tone_rate: 0.5
```

**Metal Bass:**
```yaml
bass:
  params:
    density: 0.9
    rhythm_pattern: "drive"
    articulation_style: "pick"
    lock_to_kick: 0.95
```

**Blues Bass:**
```yaml
bass:
  params:
    density: 0.8
    rhythm_pattern: "anchor"
    articulation_style: "finger"
    motion_style: "stepwise"
    passing_tone_rate: 0.3
```
