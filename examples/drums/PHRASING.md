# Drum Phrasing Feature

The phrasing feature ensures fills land on natural musical phrase boundaries, respecting meter and song structure.

## Overview

Instead of randomly placing fills throughout a section, the phrasing system:
- Divides sections into musical phrases (e.g., 4-bar chunks)
- Places fills at phrase boundaries (bars 4, 8, 12, etc.)
- Applies emphasis to the final phrase (section end) for bigger cadences

## Configuration

### `phrase_len_bars` (default: auto-detected by meter)

Number of bars per musical phrase. Fills are placed at the end of each phrase.

**Auto-detected defaults:**
- `4/4` time: 4 bars (standard rock/pop phrasing)
- `6/8` time: 2 bars (waltz/compound meter)
- `3/4` time: 2 bars (simple triple meter)

**Example:**
```yaml
sections:
  verse:
    bars: 8
    instruments:
      drums:
        params:
          phrase_len_bars: 4  # Fills at bars 4 and 8
```

**Common values:**
- `2`: Frequent fills (every 2 bars)
- `4`: Standard pop/rock phrasing
- `8`: Long phrases (only one fill per 8-bar section)

### `phrase_end_emphasis` (default: 1.5)

Multiplier for the final phrase fill (section ending). Values > 1.0 make the section-ending fill longer and more dramatic.

**Example:**
```yaml
sections:
  chorus:
    bars: 8
    instruments:
      drums:
        params:
          phrase_len_bars: 4
          phrase_end_emphasis: 2.0  # Bar 8 fill is 2x longer
          fill_length: "medium"     # 2 beats normally, 4 beats at bar 8
```

**Common values:**
- `1.0`: All fills same length (no emphasis)
- `1.5`: Subtle final phrase emphasis (default)
- `2.0`: Dramatic final phrase
- `3.0`: Very long final fill (can be up to full bar)

## Phrase Boundary Calculation

Phrases are defined by `phrase_len_bars` and section length.

**Examples:**

### 8-bar section, 4-bar phrases
```
Bars:      1  2  3  4  5  6  7  8
Phrases:   [---P1---][---P2---]
Fills:              ^         ^
           (bar 4)  (bar 8, emphasized)
```

### 8-bar section, 2-bar phrases
```
Bars:      1  2  3  4  5  6  7  8
Phrases:   [-P1][-P2][-P3][-P4]
Fills:        ^   ^   ^   ^
           All fills except bar 8 (emphasized)
```

### 6-bar section, 4-bar phrases
```
Bars:      1  2  3  4  5  6
Phrases:   [---P1---][P2]
Fills:              ^   ^
           (bar 4)  (bar 6, emphasized)
```

**Note:** If the section length is not evenly divisible by `phrase_len_bars`, the last bar is always treated as a phrase boundary.

## Integration with Other Parameters

### `fill_rate` (controls probability)

Even with phrase boundaries defined, `fill_rate` controls whether fills are placed:

```yaml
fill_rate: 1.0   # Always place fills at phrase boundaries
fill_rate: 0.5   # 50% chance per phrase boundary
fill_rate: 0.0   # No fills (ignores phrase boundaries)
```

### `fill_length` (base fill duration)

Determines the base length of fills before `phrase_end_emphasis` is applied:

```yaml
fill_length: "short"   # 1 beat (fast fills)
fill_length: "medium"  # 2 beats (default)
fill_length: "long"    # 1 bar (full-bar fills)
```

Final phrase fills are: `base_length * phrase_end_emphasis`

### `fill_chatter` (mid-phrase fills)

Chatter fills are independent of phrasing and can occur mid-phrase:

```yaml
fill_chatter: 0.0  # No chatter (only phrase-end fills)
fill_chatter: 0.3  # Occasional mid-phrase fills
```

## Meter Awareness

The phrasing system automatically detects meter and adjusts:

### 4/4 Time
- Default: 4-bar phrases
- Standard 16th note fills
- Common in rock, pop, funk

### 6/8 Time
- Default: 2-bar phrases (shorter due to feel)
- Triplet-based fills
- Common in waltzes, ballads

### Example (6/8 auto-detection):
```yaml
sections:
  waltz:
    bars: 8
    meter: "6/8"
    beats_per_bar: 6
    instruments:
      drums:
        params:
          # phrase_len_bars not specified
          # Auto-detects to 2 bars for 6/8
          # Fills at bars 2, 4, 6, 8
```

## Examples

### Standard 8-bar verse (4-bar phrases)
```yaml
verse:
  bars: 8
  instruments:
    drums:
      params:
        fill_rate: 1.0           # Always fill
        phrase_len_bars: 4       # Fills at bars 4, 8
        phrase_end_emphasis: 1.5 # Bar 8 fill is 1.5x longer
        fill_length: "medium"    # 2 beats (bar 8: 3 beats)
```

**Result:**
- Bars 1-3: Groove only
- Bar 4: 2-beat fill + crash
- Bars 5-7: Groove only
- Bar 8: 3-beat fill + crash (emphasized)

### Short 2-bar phrases (frequent fills)
```yaml
chorus:
  bars: 8
  instruments:
    drums:
      params:
        fill_rate: 1.0
        phrase_len_bars: 2       # Frequent fills
        phrase_end_emphasis: 2.0 # Big finish
        fill_length: "short"     # 1 beat (bar 8: 2 beats)
```

**Result:**
- Fills at bars 2, 4, 6, 8
- Bar 8 fill is 2x longer (2 beats)

### Long phrases (minimal fills)
```yaml
intro:
  bars: 8
  instruments:
    drums:
      params:
        fill_rate: 0.7           # 70% chance
        phrase_len_bars: 8       # Only one phrase
        phrase_end_emphasis: 1.0 # No emphasis
        fill_length: "medium"
```

**Result:**
- 70% chance of a fill at bar 8
- If present, normal 2-beat fill (no emphasis)

## Grid Visualization

Phrase boundaries are marked with fills:

```
BAR 4   |1e&a2e&a3e&a4e&a|  (end of phrase 1)
CRASH   |x---------------|  ← Crash on downbeat
SNARE   |----x---gggggxxx|  ← Fill in last 2 beats
TOM_H   |----------x-----|
TOM_M   |------x-------x-|

BAR 8   |1e&a2e&a3e&a4e&a|  (end of phrase 2, emphasized)
CRASH   |x---------------|  ← Crash on downbeat
SNARE   |----x---gggggxxx|  ← Longer/more complex fill
TOM_H   |-----------x---x|  ← More toms (emphasized)
TOM_M   |---------x---x--|
```

## Best Practices

1. **Match song structure**: Use 4-bar phrases for standard verse/chorus, 2-bar for fast sections
2. **Emphasize climaxes**: Higher `phrase_end_emphasis` for choruses, lower for verses
3. **Control density**: Combine `phrase_len_bars` with `fill_rate` for sparse vs. busy fills
4. **Respect meter**: Let auto-detection handle 6/8 and 3/4 time
5. **Test with grid**: Use `midi_text.views: ["grid"]` to visualize phrase boundaries

## Troubleshooting

**Problem:** Fills appear too frequently
- **Solution:** Increase `phrase_len_bars` (e.g., 4 → 8)
- **Or:** Reduce `fill_rate` (e.g., 1.0 → 0.5)

**Problem:** Final fill not emphasized enough
- **Solution:** Increase `phrase_end_emphasis` (e.g., 1.5 → 2.5)
- **Or:** Use `fill_length: "long"` for base fills

**Problem:** Fills on wrong beats
- **Solution:** Check that `phrase_len_bars` divides evenly into section `bars`
- **Example:** 10-bar section with `phrase_len_bars: 4` gives fills at bars 4, 8, 10 (not 5, 10)

**Problem:** No fills appearing
- **Solution:** Check `fill_rate > 0` and section has `bars >= phrase_len_bars`

## Performance Notes

- Phrase boundary calculation is O(n) where n = number of bars
- Multiple fills per section (e.g., 2-bar phrases) have no performance impact
- Fill generation is deterministic (same seed = same fills)

## See Also

- [TRANSITIONS.md](TRANSITIONS.md) - Section boundary effects (pickups, downbeats)
- [examples/drums/phrasing-demo.yaml](phrasing-demo.yaml) - Full examples
- [examples/drums/fills-demo.yaml](fills-demo.yaml) - Fill types and styles
