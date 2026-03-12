# Orchestration Examples

This directory contains examples demonstrating **cross-instrument coordination** and orchestration techniques.

## What is Orchestration?

Orchestration in Produzre refers to how instruments interact and coordinate with each other:

- Rhythm locking (bass following drums)
- Inverse density (lead vs. rhythm)
- Fill coordination at transitions
- Solo section support
- Dynamic interplay between instruments

## Examples Included

### rhythm-lock-demo.yaml
Demonstrates how bass and rhythm guitar can lock to drum patterns for tight, coordinated grooves.

**Features:**
- Bass `lock_to_kick` parameter
- Rhythm coordination across instruments
- Section-by-section locking variations
- Dynamic adjustment of locking strength

**Use Cases:**
- Funk and R&B grooves
- Metal and rock with tight rhythm sections
- Any style requiring precise instrumental coordination

## Orchestration Techniques

### 1. Bass-Drum Locking

```yaml
instruments:
  bass:
    params:
      lock_to_kick: 0.8  # 80% of bass notes follow kick drum
```

**Strength Guidelines:**
- `0.0-0.3` - Minimal locking (independent bass)
- `0.4-0.6` - Moderate locking (some coordination)
- `0.7-0.9` - Strong locking (tight groove)
- `0.9-1.0` - Complete locking (bass follows kick exactly)

### 2. Inverse Density

When lead instrument is active, reduce rhythm density:

```yaml
sections:
  solo:
    instruments:
      rhythm_gtr:
        params:
          density: 0.5  # Reduce rhythm during solo
      lead_gtr:
        params:
          density: 0.9  # Increase lead activity
```

### 3. Fill Coordination

Coordinate fills across instruments at section transitions:

```yaml
instruments:
  drums:
    params:
      fill_rate: 0.35  # Fills at transitions

  bass:
    params:
      fill_rate: 0.25  # Complementary bass fills
```

### 4. Solo Support

Simplify backing instruments during solos:

```yaml
sections:
  solo:
    instruments:
      drums:
        intensity: 0.8  # Reduce intensity
        params:
          fill_rate: 0.2  # Fewer fills
      bass:
        intensity: 0.8
        params:
          density: 0.7  # Simpler bass lines
      rhythm_gtr:
        intensity: 0.6
        params:
          density: 0.5  # Sparse rhythm guitar
```

## Building Orchestration Examples

```bash
# Build all orchestration examples
for f in examples/orchestration/*.yaml; do
  python3 -m produzre.cli build "$f"
done
```

## Best Practices

1. **Start Simple** - Add orchestration gradually
2. **Listen for Clash** - Too much coordination can sound robotic
3. **Vary by Section** - Use different coordination per section
4. **Genre Appropriate** - Metal needs more locking than jazz
5. **Test Different Values** - Small changes in locking can have big impact

## Advanced Techniques

### Dynamic Locking Per Section

```yaml
sections:
  verse:
    instruments:
      bass:
        params:
          lock_to_kick: 0.6  # Moderate locking in verse

  chorus:
    instruments:
      bass:
        params:
          lock_to_kick: 0.9  # Strong locking in chorus
```

### Complementary Rhythms

Create interplay by varying density across instruments:

```yaml
sections:
  verse:
    instruments:
      drums:
        intensity: 0.7
      bass:
        intensity: 0.8  # Bass more prominent
      rhythm_gtr:
        intensity: 0.6  # Guitar less prominent
```

## Related Examples

- See `genres/funk/` for heavy orchestration usage
- See `genres/jazz/` for loose, independent orchestration
- See `genres/metal/` for tight, locked orchestration
