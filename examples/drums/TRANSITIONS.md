# Drum Transitions Feature

The transitions feature makes the drummer announce section changes with pickups and downbeat punctuation.

## Features

### Pickup Window
- **What**: Snare roll in the last 2 beats before transitioning to a different section type
- **When**: Triggered when next section has a different type (verse→chorus, chorus→bridge, etc.)
- **Configurable**: `drums.params.pickup_rate` (0.0-1.0, default 0.7)
- **Effect**: 16th note snare crescendo leading into the next section

### Downbeat Punctuation
- **What**: Crash cymbal + kick on beat 1 when section type changes
- **When**: Triggered on first beat of a new section type
- **Configurable**: `drums.params.downbeat_rate` (0.0-1.0, default 0.8)
- **Effect**: Emphasizes the section boundary with a crash accent

## Configuration

Add to your YAML under `sections.<section_name>.instruments.drums.params`:

```yaml
sections:
  verse:
    instruments:
      drums:
        params:
          pickup_rate: 0.7      # 70% chance of pickup before section change
          downbeat_rate: 0.8    # 80% chance of downbeat crash on section change
```

### Disabling Transitions

Set rates to 0.0 to disable:

```yaml
# Disable pickups (no snare roll before section changes)
pickup_rate: 0.0

# Disable downbeat punctuation (no crash on section transitions)
downbeat_rate: 0.0
```

## Detection Logic

Transitions are detected automatically based on section `type` field:

- **Pickup**: Added to end of section when `next_section.type != current_section.type`
- **Downbeat**: Added to start of section when `prev_section.type != current_section.type`
- **No transition**: When consecutive sections have the same type (verse→verse, chorus→chorus)

## Example

See [examples/drums/transitions-demo.yaml](transitions-demo.yaml) for a full demonstration:

```yaml
arrangement:
  - verse_intro      # No pickup (first section)
  - chorus           # ✓ Pickup at end of verse + ✓ Downbeat crash
  - verse_return     # ✓ Pickup at end of chorus + ✓ Downbeat crash
  - bridge           # ✓ Pickup at end of verse + ✓ Downbeat crash
  - chorus_final     # ✓ Pickup at end of bridge + ✓ Downbeat crash
```

## Grid Visualization

The grid view shows transition effects:

```
BAR 4   |1e&a2e&a3e&a4e&a|  (last bar of verse)
SNARE   |----x---ggggxxxx|  ← Pickup roll

BAR 5   |1e&a2e&a3e&a4e&a|  (first bar of chorus)
CRASH   |^---------------|  ← Downbeat crash (^ = transition)
KICK    |x---------------|  ← Downbeat kick
```

## Implementation Details

### Pickup Window
- **Duration**: Last 2 beats of section
- **Pattern**: 16th note snare rolls
- **Velocity**: Crescendo from soft to loud (e.g., 50 → 80)
- **Kind**: `snare_pickup` (for analysis/debugging)

### Downbeat Punctuation
- **Crash**: Added on beat 0.0 with accent velocity
- **Kick**: Added on beat 0.0 for emphasis
- **Kind**: `crash_transition`, `kick_transition`
- **Collision detection**: Skips if crash/kick already present

## Performance Considerations

- Transitions use the section's deterministic RNG
- Probability checks (`pickup_rate`, `downbeat_rate`) consume one RNG draw each
- No performance impact when rates are 0.0

## Future Enhancements

Potential future additions:

- `transition_style` param: `safe` (current behavior) vs `bold` (more aggressive fills)
- Configurable pickup window length (1 beat, 2 beats, full bar)
- Different pickup patterns (tom fills, cymbal swells, etc.)
- Section-specific overrides for transition behavior
