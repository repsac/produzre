# Persona Examples

This directory contains examples demonstrating how to use **personas** in Produzre. Personas are predefined parameter sets that give instruments a consistent musical character.

## What are Personas?

Personas allow you to quickly apply a musical "personality" to an instrument without manually setting all parameters. They define:

- Playing style and technique
- Rhythmic feel and timing
- Density and intensity preferences
- Articulation choices

## Available Personas

### Drum Personas (6)

Defined in `produzre/resources/personas/drums.yml`:

| Persona | Character | Best For |
|---------|-----------|----------|
| **tight** (default) | Precise, locked to grid, minimal variation | New users, clean tracks |
| **experimental** | Noticeable humanization, high swing, busy fills | Creative exploration |
| **rock** | Driving, consistent, ghost notes on snare | Rock, pop rock |
| **metal** | Very tight, aggressive, double-kick patterns | Metal, hard rock |
| **funk-lite** | Syncopated, groovy, open hats, ghost notes | Funk, R&B |
| **jazz-lite** | Loose, swung, ride-heavy, dynamic velocity | Jazz, blues, swing |

Key parameters: `timing_jitter_ms`, `velocity_humanize`, `swing`, `push_pull`,
`accent_strength`, `hat_density`, `fill_rate`, `fill_chatter`.

### Bass Personas (7)

Defined in `produzre/resources/personas/bass.yml`:

| Persona | Character | Best For |
|---------|-----------|----------|
| **tight** (default) | Minimal humanization, locked to groove | Clean, precise tracks |
| **pocket** | Slightly behind the beat, warm and solid | R&B, soul, pop |
| **loose** | Timing variation, swung feel, syncopated | Jazz, blues |
| **funk** | Syncopated, percussive, slap technique | Funk, disco |
| **metal** | Tight, fast, picked, aggressive, low register | Metal, hard rock |
| **walking** | Quarter notes, chord tones, smooth voice leading | Jazz, swing |
| **dub** | Sparse, deep, way behind the beat, heavy rests | Reggae, dub |

Key parameters: `density`, `rhythm_pattern`, `articulation_style`, `approach_rate`,
`lock_to_kick`, `octave_jump_rate`, `fill_rate`.

### Rhythm Guitar Personas (5)

Defined in `produzre/resources/personas/rhythm_gtr.yml`:

| Persona | Character | Best For |
|---------|-----------|----------|
| **tight** (default) | Precise timing, no swing, clean strumming | Rock, pop, metal |
| **loose** | Relaxed timing, variable velocity, laid-back | Blues, soul |
| **aggressive** | Tight but punchy, strong dynamics, pushed feel | Punk, hard rock |
| **funky** | Syncopated, choppy, ghost strums, upbeat heavy | Funk, R&B |
| **jangly** | Bright, ringing chords, light touch, wide strums | Indie, new wave |

Key parameters: `humanize_velocity`, `humanize_timing`, `swing`, `groove`,
`accent_strength`, `chuck_rate`, `strum_ms`, `sustain_cut_rate`.

### Lead Guitar Personas (5)

Defined in `produzre/resources/personas/lead_gtr.yml`:

| Persona | Character | Best For |
|---------|-----------|----------|
| **balanced** (default) | Moderate phrasing, smooth contour | General purpose |
| **melodic** | Long phrases, stepwise motion, strong resolution | Ballads, pop |
| **shredder** | Fast runs, wide leaps, minimal rests | Metal, hard rock |
| **bluesy** | Spacious phrasing, breathing room, chord-tone focus | Blues, classic rock |
| **ambient** | Sparse, long phrases, wide intervals, lots of space | Post-rock, ambient |

Key parameters: `phrase_len_bars`, `rest_probability`, `resolution_strength`,
`contour_style`.

### Acoustic Guitar Personas (5)

Defined in `produzre/resources/personas/acoustic_gtr.yml`:

| Persona | Character | Best For |
|---------|-----------|----------|
| **natural** (default) | Moderate humanization, open voicings | General purpose |
| **precise** | Tight timing, consistent velocity, clean | Classical, pop |
| **expressive** | Dynamic velocity, loose timing, percussive | Singer-songwriter |
| **percussive** | Heavy muting, body taps, rhythmic emphasis | Percussive acoustic |
| **delicate** | Soft touch, minimal variation, open voicings | Fingerpicking, ballads |

Key parameters: `vel_variation`, `timing_variation`, `mute_ratio`,
`body_tap_ratio`, `voicing_style`.

## Using Personas in Your Songs

### Basic Usage

```yaml
instruments:
  drums:
    params:
      persona: "rock"

  bass:
    params:
      persona: "pocket"

  rhythm_gtr:
    params:
      persona: "funky"

  lead_gtr:
    params:
      persona: "bluesy"

  acoustic_gtr:
    params:
      persona: "expressive"
```

### Overriding Persona Parameters

Personas provide defaults that you can override:

```yaml
instruments:
  drums:
    params:
      persona: "rock"
      fill_rate: 0.6       # Override: more fills than rock default
      swing: 0.10           # Override: add slight swing

  bass:
    params:
      persona: "funk"
      density: 0.70         # Override: slightly less busy
```

### Section Variation

Change personas per section for dynamic contrast:

```yaml
sections:
  verse:
    instruments:
      drums:
        params:
          persona: "tight"    # Controlled in verse
      bass:
        params:
          persona: "pocket"   # Laid back

  chorus:
    instruments:
      drums:
        params:
          persona: "rock"     # Opens up in chorus
      bass:
        params:
          persona: "loose"    # More expressive
```

## Examples Included

### Drums
- `drums/persona-demo.yaml` — Side-by-side comparison of drum personas

### Bass
- `bass/persona-tight.yaml` — Tight bass player demonstration
- `bass/persona-pocket.yaml` — Pocket bass player demonstration
- `bass/persona-walking.yaml` — Walking bass player demonstration

## Building Examples

```bash
# Build all persona examples
for f in examples/personas/drums/*.yaml examples/personas/bass/*.yaml; do
  python3 -m produzre.cli build "$f"
done
```

## Tips

1. **Start with a persona** — Pick the one closest to your desired sound
2. **Override selectively** — Only change parameters you need to customize
3. **Mix personas** — Use different personas for different instruments
4. **Section variation** — Change personas per section for dynamic variety
5. **Combine with genre** — Personas and genre recipes work together; persona params merge on top of recipe defaults
