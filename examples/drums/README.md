# Drums Engine Test Examples

This directory contains test YAML files for the Produzre drums engine, designed for quick validation and regression testing.

## Quick Start

### Running a Quick Validation

```bash
# From the repository root — use any demo file for a quick check
python -m produzre.cli build examples/drums/hats-demo.yaml -v
```

### Validating Changes

After making changes to the drums engine, verify stability:

```bash
# Build the same file twice
python -m produzre.cli build examples/drums/hats-demo.yaml -v
python -m produzre.cli build examples/drums/hats-demo.yaml -v

# Compare last two outputs
python scripts/diff_last_two.py
```

If the diff shows no changes, your modifications are deterministic and stable.

## Artifacts

After running a build, artifacts are exported to:

```
exports/[SongTitle]_[Timestamp]/
├── [SongTitle].mid               # Full song MIDI file
├── analysis/
│   └── drums/
│       ├── [SongTitle]_drums.events.tsv   # Event-level data (TSV format)
│       └── [SongTitle]_drums.grid.txt     # Visual grid representation
└── instruments/
    └── drums.mid                 # Drums-only MIDI file
```

### Analysis Files

**`*_drums.events.tsv`** - Tab-separated event data:
- Columns: `section`, `instrument`, `start_beat_abs`, `duration_beats`, `pitch`, `velocity`, `note`, `kind`
- One row per drum hit
- Useful for programmatic analysis

**`*_drums.grid.txt`** - Human-readable grid visualization:
- Shows drum pattern as a piano-roll style grid
- One row per drum voice (KICK, SNARE, HAT_C, HAT_O, CRASH, etc.)
- Characters indicate velocity: `X` (loud), `^` (accent), `x` (normal), `g` (ghost), `.` (soft)
- Grid resolution: 16th notes (16 steps per bar in 4/4)

## Expected Grid Lanes

A well-formed drums output should contain these lanes in the grid:

**Required lanes** (always present):
- `KICK` - Kick drum (GM pitch 35/36)
- `SNARE` - Snare drum (GM pitch 38/40)
- `HAT_C` - Closed hi-hat (GM pitch 42)

**Optional lanes** (depending on template settings):
- `HAT_O` - Open hi-hat (GM pitch 46)
- `HAT_P` - Pedal hi-hat / foot chick (GM pitch 44)
- `RIDE` - Ride cymbal (GM pitch 51)
- `CRASH` - Crash cymbal (GM pitch 49)
- `TOM_L`, `TOM_M`, `TOM_H` - Toms (GM pitches 45, 47, 50)

**Analysis expectations**:
- Grid should show consistent pattern structure across bars
- Ghost notes appear as `g` characters (velocity < 70)
- Accents appear as `^` (velocity 92-109) or `X` (velocity >= 110)
- Grid header shows: `INSTRUMENT: drums`, meter, and subdivision

## CLI Commands

```bash
# Validate YAML syntax
python -m produzre.cli validate examples/drums/hats-demo.yaml

# Show resolved configuration (useful for debugging)
python -m produzre.cli show-config examples/drums/hats-demo.yaml --format json

# Dry-run (validate without writing files)
python -m produzre.cli build examples/drums/hats-demo.yaml --dry-run -v

# Build with verbose output
python -m produzre.cli build examples/drums/hats-demo.yaml -v
```

## Test Files

The drums directory contains multiple demo YAMLs that serve as both examples and regression tests:

- **`hats-demo.yaml`** - Hi-hat patterns (open/closed/pedal variations, density, accents)
- **`kick-demo.yaml`** - Kick patterns (syncopation, double-kick, extra kicks)
- **`snare-demo.yaml`** - Snare patterns and ghost notes
- **`fills-demo.yaml`** - Fill patterns (short/medium/long, chatter, persona-based types)
- **`transitions-demo.yaml`** - Section transition effects (pickups, downbeats)
- **`phrasing-demo.yaml`** - Phrase boundary fill placement
- **`performance-demo.yaml`** - Performance ornaments (chokes, flams, drags)
- **`energy-demo.yaml`** - Intensity-driven dynamic variation
- **`cymbals-demo.yaml`** - Cymbal usage (crashes, rides)
- **`toms-demo.yaml`** - Tom patterns in fills
- **`take-demo.yaml`** - Take-based micro-variation
- **`bridge-demo.yaml`** - Bridge section behavior

## Debugging Tips

### Grid shows unexpected lanes

If you see unexpected drum voices in the grid:
1. Check the groove template in `produzre/engine/drums/groove.py`
2. Verify `pitches` mapping in `produzre/engine/drums/__init__.py`
3. Review GM drum mapping in `produzre/analysis/grid_format.py`

### Events differ between runs

Drums generation uses a deterministic RNG seeded by the YAML `seed` parameter. If outputs differ:
1. Ensure the YAML file has a fixed `seed` value
2. Check for non-deterministic code in voice modules (kick, snare, hats)
3. Verify RNG threading in `produzre/engine/drums/patterns/kit.py`

### Missing ghost notes or accents

Ghost notes (`g`) and accents (`^`, `X`) are velocity-mapped in `grid_format.py`:
- Ghost: velocity < 70
- Normal: velocity 70-91
- Accent: velocity 92-109
- Loud: velocity >= 110

Check `vel_for()` in `produzre/engine/drums/patterns/utils.py` for velocity calculation logic.

## Related Documentation

- Main drums engine: `produzre/engine/drums/__init__.py`
- Pattern generation: `produzre/engine/drums/patterns/`
- Analysis exports: `produzre/analysis/README.md`
- Groove templates: `produzre/engine/drums/groove.py`
