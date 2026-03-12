# Drum Performance Features

Produzre includes performance features that add drummer realism beyond note placement: cymbal chokes, flams, drags, and velocity crescendos.

## Features

### 1. Cymbal Chokes

**What**: Shortened cymbal sustain when drummer grabs cymbal to stop ringing.

**Applies to**: Open hats, crashes, splashes, chinas, ride (with different probabilities)

**Configuration**:
```yaml
sections:
  chorus:
    instruments:
      drums:
        params:
          choke_rate: 0.7  # 0.0-1.0 probability of choking open cymbals
```

**Behavior**:
- **Open hats**: Choked when next event is close (< 0.5 beats) in tight grooves
- **Crashes/splashes/chinas**: Probabilistically choked based on `choke_rate`
- **Ride**: Rarely choked (20% of choke_rate)
- **Duration**: 0.05-0.1 beats (vs normal ~0.5 beats)

**TSV Tags**:
- `crash_choke`, `open_hat_choke`, `ride_choke`, `fill_choke`
- Indicates event was choked (shortened duration)

**Example**:
```tsv
drums  verse  8  1.000  28.000  0.059  crash  93  crash_choke
drums  verse  8  3.500  30.500  0.071  open_hat  86  open_hat_choke
```
Duration 0.059 and 0.071 beats indicates choked cymbals (normal would be ~0.5).

### 2. Snare Flams

**What**: Two-note ornament (grace note + main note) adding power and articulation.

**Timing**:
- Grace note: 0.035-0.045 beats before main note (~0.04 beats)
- Grace velocity: 50-60% of main note

**Configuration**:
```yaml
sections:
  chorus:
    instruments:
      drums:
        params:
          flam_rate: 0.5  # 0.0-1.0 probability of flam on accented snares
```

**Placement Context** (flams are more likely on):
- Accented snares (velocity >= 80) [1.5x probability]
- Backbeats (beats 2 and 4 in 4/4) [1.2x probability]
- Both [1.8x probability]

**TSV Tags**:
- `flam_grace`: The grace note (lower velocity, ~0.04 beats before)
- `snare_flam`: The main note with flam
- `snare_pickup_flam`: Flammed pickup note
- `fill_flam`: Flammed fill note

**Example**:
```tsv
drums  chorus  9  1.960  32.960  0.050  snare  42  flam_grace
drums  chorus  9  2.000  33.000  0.250  snare  79  snare_flam
```
Grace note at 1.960 (beat 32.960), main at 2.000 (beat 33.000) = 0.04 beats before.
Grace velocity 42 vs main 79 = ~53% ratio.

### 3. Snare Drags

**What**: Three-note ornament (two grace notes + main note) for dramatic emphasis.

**Timing**:
- First grace: 0.055-0.065 beats before main (~0.06 beats)
- Second grace: 0.025-0.035 beats before main (~0.03 beats)
- Grace velocities: 45-55% of main note

**Configuration**:
```yaml
sections:
  solo:
    instruments:
      drums:
        params:
          drag_rate: 0.4  # 0.0-1.0 probability of drag on accented snares
```

**Placement Context**: Same as flams (accented snares, backbeats).

**Note**: Flams and drags are mutually exclusive per note (can't have both).

**TSV Tags**:
- `drag_grace`: Grace notes (two per drag, lower velocity)
- `snare_drag`: The main note with drag
- `snare_pickup_drag`: Dragged pickup note
- `fill_drag`: Dragged fill note

**Example**:
```tsv
drums  chorus  13  3.940  50.940  0.050  snare  37  drag_grace
drums  chorus  13  3.967  50.967  0.050  snare  42  drag_grace
drums  chorus  13  4.000  51.000  0.250  snare  85  snare_drag
```
First grace at 3.940 (0.060 beats before), second grace at 3.967 (0.033 beats before), main at 4.000.
Grace velocities 37 and 42 vs main 85 = ~44% and ~49% ratio.

### 4. Fill Velocity Crescendos

**What**: Built-in velocity ramping within fills for natural crescendo effect.

**Implementation**: Already built into fills.py (no configuration needed).

**Fill Types and Crescendos**:
- **Snare roll**: Gentle crescendo (velocity +6 to +16 from base)
- **Alternating snare/tom**: Moderate crescendo (velocity +8 to +16)
- **Tom run**: Strong crescendo into final snare (velocity +10 to +22)
- **Kick burst**: Consistent power with accented snares (snare +12, kick +8)
- **Cymbal swell**: Dramatic crescendo (velocity +4 to +22)

**Progress-based ramping**:
```python
prog = (t - fill_start) / fill_len_beats  # 0.0 at start → 1.0 at end
ramp = int(6 + (prog * 10.0))  # For snare roll
velocity = base_velocity + ramp + random(-3, 3)
```

**Example** (snare roll fill):
```tsv
# Beat 3.500: start of 2-beat fill (prog=0.0)
drums  verse  8  3.500  30.500  0.250  snare  73  fill

# Beat 3.750 (prog=0.125)
drums  verse  8  3.750  30.750  0.250  snare  74  fill

# Beat 4.000 (prog=0.25)
drums  verse  8  4.000  31.000  0.250  snare  77  fill

# Beat 4.250 (prog=0.375)
drums  verse  8  4.250  31.250  0.250  snare  79  fill

# Beat 4.500 (prog=0.5)
drums  verse  8  4.500  31.500  0.250  snare  82  fill

# Beat 4.750 (prog=0.625)
drums  verse  8  4.750  31.750  0.250  snare  85  fill

# Beat 5.000 (prog=0.75)
drums  verse  8  5.000  32.000  0.250  snare  88  fill

# Beat 5.250 (prog=0.875)
drums  verse  8  5.250  32.250  0.250  snare  91  fill

# Beat 5.500: end (prog=1.0)
drums  verse  8  5.500  32.500  0.250  snare  94  fill
```
Velocity increases from 73 → 94 (+21) across the 2-beat fill.

## Configuration Summary

### Disable All Ornaments (Default)
```yaml
sections:
  verse:
    instruments:
      drums:
        params:
          choke_rate: 0.0  # No chokes (default)
          flam_rate: 0.0   # No flams (default)
          drag_rate: 0.0   # No drags (default)
```

### Realistic Performance (Moderate Ornaments)
```yaml
sections:
  chorus:
    instruments:
      drums:
        params:
          choke_rate: 0.5   # Moderate choking
          flam_rate: 0.3    # Occasional flams
          drag_rate: 0.15   # Rare drags (more difficult technique)
```

### Aggressive Performance (Frequent Ornaments)
```yaml
sections:
  solo:
    instruments:
      drums:
        params:
          choke_rate: 0.8   # Frequent chokes for tight control
          flam_rate: 0.6    # Frequent flams for power
          drag_rate: 0.3    # More drags for intensity
```

## Persona Influence

The `persona` parameter affects ornament behavior:

**`tight` (default)**:
- Conservative ornament placement
- Crash chokes: 80% of choke_rate
- Ride chokes: 20% of choke_rate
- Flams/drags: standard probability

**`loose`**:
- More experimental ornament placement
- Crash chokes: 50% of choke_rate (less tight control)
- Ride chokes: 20% of choke_rate (same as tight)
- Flams/drags: standard probability

```yaml
sections:
  verse:
    instruments:
      drums:
        persona: tight  # Conservative ornaments
        params:
          choke_rate: 0.6
          flam_rate: 0.4

  chorus:
    instruments:
      drums:
        persona: loose  # More experimental ornaments
        params:
          choke_rate: 0.6
          flam_rate: 0.4
```

## Determinism

All ornaments are deterministic (same seed = same ornaments):
- Separate RNG stream: `drums.ornaments`
- Independent from fills, patterns, humanization
- Changing `song.take` produces different ornament placements
- Same take always produces identical ornaments

## TSV Analysis

Check ornament distribution:
```bash
# Count ornament types
cut -f12 exports/MySong_*/analysis/drums/*.events.tsv | grep -E "(choke|flam|drag)" | sort | uniq -c

# Find flammed notes
grep "flam" exports/MySong_*/analysis/drums/*.events.tsv

# Find choked cymbals
grep "_choke" exports/MySong_*/analysis/drums/*.events.tsv

# Find drags
grep "drag" exports/MySong_*/analysis/drums/*.events.tsv
```

## Demo

See [performance-demo.yaml](performance-demo.yaml) for comprehensive examples:
1. **verse_no_ornaments**: Baseline (no ornaments)
2. **verse_chokes_only**: Cymbal chokes only
3. **chorus_flams_only**: Snare flams only
4. **chorus_drags_only**: Snare drags only
5. **bridge_all_ornaments**: All ornaments combined
6. **solo_aggressive_ornaments**: High intensity with aggressive ornaments
7. **verse_tight_persona**: Tight persona influence
8. **chorus_loose_persona**: Loose persona influence
9. **outro_fill_crescendos**: Fill crescendo showcase

Build the demo:
```bash
produzre build examples/drums/performance-demo.yaml
```

Check TSV for ornaments:
```bash
# Count all ornament types
cut -f12 exports/PerformanceDemo_*/analysis/drums/*.events.tsv | sort | uniq -c

# Output shows:
#   4 crash_choke          - Choked crashes
#   98 flam_grace          - Flam grace notes
#   25 snare_flam          - Main notes with flam
#   84 drag_grace          - Drag grace notes (2 per drag)
#   9 snare_drag           - Main notes with drag
#   16 ride_choke          - Choked ride cymbal
#   ... and more
```

## Best Practices

1. **Start conservative**: Use moderate rates (0.3-0.5) and listen
2. **Match intensity**: Higher intensity → higher ornament rates
3. **Drags are rare**: Real drummers use drags less than flams (drag_rate < flam_rate)
4. **Chokes for control**: High choke_rate (0.7-0.8) for tight grooves
5. **Persona matters**: Use `tight` for precision, `loose` for experimentation
6. **Check TSV**: Verify ornament placement matches intent

## Future Enhancements

Potential additions:
- **Buzz rolls**: Sustained snare rolls with fine subdivisions
- **Rim clicks**: Crossstick or rim-only hits
- **Hi-hat splashes**: Partially open hat hits
- **Cymbal swells**: Building intensity on sustained cymbals
- **Stick articulations**: Different stick positions (center, edge, bell)

## Technical Details

### Ornament Processing Pipeline

```
1. Generate patterns (patterns.py)
2. Add fills (fills.py) ← includes crescendos
3. Add ornaments (ornaments.py) ← chokes, flams, drags
4. Humanize (humanize.py) ← timing/velocity jitter
5. Write to timeline → MIDI export
```

### Why Ornaments Before Humanization?

Ornaments are added before humanization so grace notes get humanized timing/velocity like all other events. This creates realistic variation in ornament execution (not robotic).

### Collision Detection

- **Chokes replace originals**: Shortened duration, same pitch/velocity
- **Flams/drags add grace notes**: No collision (grace notes are earlier)
- **Mutual exclusion**: A snare cannot have both flam and drag

### MIDI Output

- **Chokes**: Same note-on, shortened note-off
- **Flams**: Two note-ons (grace + main) on same pitch
- **Drags**: Three note-ons (grace1 + grace2 + main) on same pitch

DAWs will render these as overlapping hits on the same drum voice, which sounds realistic.
