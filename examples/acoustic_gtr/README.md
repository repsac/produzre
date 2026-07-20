# Acoustic Guitar Examples

This directory contains examples demonstrating acoustic guitar techniques, picking patterns, and voicing styles.

## Directory Structure

```
acoustic_gtr/
└── style-comparison.yaml    - Compares different acoustic guitar techniques
```

## Examples by Category

### Style Comparison

**style-comparison.yaml**
- **Purpose**: Compare different acoustic guitar techniques side by side
- **Parameters tested**: `technique` (fingerpicking, strumming, hybrid, percussive)
- **Use case**: Understanding how each technique shapes the acoustic guitar output

## Key Acoustic Guitar Parameters

### Technique (Playing Approach)
- **technique**: Overall playing technique
  - `"fingerpicking"`: Individual string plucking (folk, classical, singer-songwriter)
  - `"strumming"`: Full chord strumming (pop, rock, campfire)
  - `"hybrid"`: Mix of picking and strumming (country, modern folk)
  - `"percussive"`: Body taps and muted hits mixed with notes (modern acoustic, Andy McKee style)

### Picking Pattern (Fingerpicking Mode)
- **picking_pattern**: Pattern used when technique is `"fingerpicking"` or `"hybrid"`
  - `"travis"`: Alternating bass with melody on top (country, folk)
  - `"pima"`: Classical right-hand pattern (p=thumb, i=index, m=middle, a=ring)
  - `"broken_chord"`: Arpeggiated chord tones in sequence
  - `"waltz"`: 3/4 time bass-chord-chord pattern
  - `"roll"`: Continuous rolling arpeggios (banjo-influenced)
  - `"cinematic"`: Spacious syncopated thumb pattern with a moving treble melody

### Melodic Fingerstyle
- **melody_amount** (0.0-1.0): How strongly treble fingers follow the shared melody guide
- **phrase_variation** (0.0-1.0): Introduces small omissions so each bar does not repeat mechanically
- The thumb and supporting fingers remain tied to the selected guitar voicing;
  only treble melody notes are reharmonized into a playable nearby register.

### Density & Muting
- **strum_density** (0.0-1.0): How many strings are struck per strum
  - 0.2-0.3: Sparse, partial strums
  - 0.5-0.6: Moderate coverage
  - 0.8-1.0: Full, rich strums
- **mute_ratio** (0.0-0.5): Proportion of muted/ghost notes
  - 0.0: No muted notes
  - 0.1-0.2: Subtle rhythmic texture
  - 0.3-0.5: Percussive, rhythmic feel
- **body_tap_ratio** (0.0-0.5): Frequency of percussive body taps between notes
  - 0.0: No body percussion
  - 0.1-0.2: Occasional rhythmic accents
  - 0.3-0.5: Prominent percussive element

### Voicing & Capo
- **voicing_style**: Chord shape approach
  - `"open"`: Open-position cowboy chords (bright, resonant)
  - `"barre"`: Barre chord shapes (movable, consistent tone)
  - `"auto"`: Engine selects based on key and genre
- **capo** (0-12): Capo position in frets
  - 0: No capo
  - 2-4: Common for singer-songwriter keys
  - 5-7: Bright, mandolin-like voicings

### Dynamics
- **base_vel** (30-110): Base MIDI velocity for notes
  - 30-50: Very soft, intimate playing
  - 60-80: Moderate, balanced dynamics
  - 90-110: Loud, aggressive strumming
- **vel_variation** (0-20): Random velocity variation range
  - 0-5: Very consistent dynamics (mechanical)
  - 10-15: Natural human variation
  - 15-20: Expressive, dynamic playing

### Timing Feel
- **timing_variation** (0.0-0.05): Random timing offset for humanization
  - 0.0: Perfectly quantized (mechanical)
  - 0.01-0.02: Subtle human feel
  - 0.03-0.05: Loose, relaxed timing

## Personas

Five personas are available in `produzre/resources/personas/acoustic_gtr.yml`:

- **natural** - Balanced, all-purpose acoustic tone
- **precise** - Tight timing, consistent velocity, clean technique
- **expressive** - Dynamic velocity, loose timing, percussive touches
- **percussive** - Body taps and mutes prominent
- **delicate** - Very soft, intimate fingerpicking

Use personas in your config:

```yaml
acoustic_gtr:
  persona: "natural"
```

## Building Examples

```bash
# Build a specific example
python -m produzre.cli build examples/acoustic_gtr/style-comparison.yaml

# Build all acoustic guitar examples
for f in examples/acoustic_gtr/*.yaml; do
  python -m produzre.cli build "$f"
done
```

## Tips and Best Practices

### Choosing a Technique
- **Fingerpicking** - Solo acoustic, folk, classical, ballad intros
- **Strumming** - Full-band arrangements, singer-songwriter, pop
- **Hybrid** - Country, modern folk, versatile arrangements
- **Percussive** - Solo performance, modern acoustic, loop-based

### Picking Pattern Selection
- **Travis** picking works best in 4/4 time with simple chord progressions
- **PIMA** suits classical and formal fingerstyle pieces
- **Broken chord** is versatile and works across most genres
- **Waltz** is designed for 3/4 time signatures
- **Roll** adds energy and continuous motion to upbeat songs
- **Cinematic** leaves room for a voice-led top line in intros, bridges, and interludes

### Humanization
- Always use some `timing_variation` (0.01-0.02) to avoid a mechanical feel
- Set `vel_variation` to 8-12 for natural dynamics
- Combine `mute_ratio: 0.1` with `body_tap_ratio: 0.1` for organic rhythm

### Combining Features

**Folk Fingerpicking:**
```yaml
acoustic_gtr:
  params:
    technique: "fingerpicking"
    picking_pattern: "travis"
    voicing_style: "open"
    base_vel: 65
    vel_variation: 10
    timing_variation: 0.015
```

**Pop Strumming:**
```yaml
acoustic_gtr:
  params:
    technique: "strumming"
    strum_density: 0.7
    voicing_style: "open"
    capo: 2
    base_vel: 80
    vel_variation: 12
```

**Percussive Acoustic:**
```yaml
acoustic_gtr:
  params:
    technique: "percussive"
    body_tap_ratio: 0.3
    mute_ratio: 0.2
    strum_density: 0.5
    base_vel: 75
    vel_variation: 15
    timing_variation: 0.02
```

**Classical Fingerstyle:**
```yaml
acoustic_gtr:
  params:
    technique: "fingerpicking"
    picking_pattern: "pima"
    voicing_style: "barre"
    base_vel: 55
    vel_variation: 8
    timing_variation: 0.01
```
