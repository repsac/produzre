# `produzre.analysis`

The `produzre.analysis` subpackage contains **human-readable, deterministic debug exports** and **helpers for parsing those exports back into structured data**.

Produzre generates MIDI, but MIDI is not ideal for debugging because it is event-based, requires DAW tooling to inspect, and can be affected by quantization / PPQ interpretation.

This package exists to make the internal musical decisions *visible*:

- **Grid views** that look like step sequencer lanes (good for quick visual inspection).
- **Event TSVs** that are machine-parseable (good for diffing, tests, and downstream tooling).
- **Formatting/parsing utilities** so the exports are stable and consistent.

> **Design principle:** analysis exports are intended to be reproducible when `song.yaml + project seed + song seed` are the same. If "humanize" is enabled, the analysis format should still be stable (the randomness must come from deterministic RNG).

---

## What this subpackage provides

### 1) Grid formatting (`grid_format.py`)
A **step-grid renderer** that converts a timeline of note events into a compact ASCII representation.

Typical output:

```text
BAR 1   |1...............|
HAT_C   |x---x---x---x---|
KICK    |x---------------|
SNARE   |--------x-------|
TOM_M   |----------------|
```

Key goals:

- **Monospace-friendly** output (aligned columns) for terminal/README/commit diffs.
- Makes accents and variant hits visible (e.g., accented hats rendered differently).
- Supports arbitrary meters and pattern sizes as long as the timeline exports define the step grid.

### 2) TSV event export and parsing (`tsv_events.py`)
A minimal, explicit **TSV** representation of events.

This is primarily used to:

- Diff two exports to see *exactly* which events changed.
- Drive unit tests (e.g., “same YAML + same project = same events”).
- Support external tools (plotters, validators, converters).

The intent is that:

- TSV is stable, predictable, and does not require MIDI parsing.
- The exported schema is backwards-evolvable (new columns can be added with sane defaults).

---

## Output locations and naming

Analysis exports are written alongside other export artifacts.

A typical export structure looks like:

```text
exports/<run_id>/
  <SongTitle>.mid
  <SongTitle>.yaml
  instruments/
    drums/
      <SongTitle>_drums.mid
      <SongTitle>_drums.grid.txt
      <SongTitle>_drums.events.tsv
    bass/
      <SongTitle>_bass.mid
      ...
  sections/
    ...
  patterns/
    ...
```

The exact folder structure is controlled by the export layer, but the analysis files produced by this package follow these conventions:

- `*_*.grid.txt` → an ASCII grid view
- `*_*.events.tsv` → TSV event dump

---

## File formats

### Grid files (`*.grid.txt`)
Grid files are designed for fast scanning.

Common conventions:

- Each lane is labeled (`KICK`, `SNARE`, `HAT_C`, `HAT_O`, etc.).
- Steps are rendered with a fixed-width pattern:
  - `x` = hit
  - `-` = rest
  - digits or symbols may represent accents/variants depending on formatter settings
- A `BAR n` header line separates bars and shows step numbers.

Grid exports are intentionally not meant to be lossless; they are a **debug visualization**.

### Event TSV (`*.events.tsv`)
TSV is intended to be a structured, lossless-ish representation of what Produzre generated.

A typical schema includes:

- `track` / `instrument`
- `voice` (e.g., `snare`, `hats_closed`, `kick`)
- `start_beat`, `end_beat`
- `pitch`
- `velocity`
- Optional columns for tags/flags (e.g., accent, ghost intent, humanize offsets)

Exact columns can evolve, but **the export should remain deterministic** for a fixed seed.

---

## Drums Grid Expectations

When validating drums output, the grid should contain specific lanes based on the groove template settings. This section documents expected grid structure for regression testing.

### Required Lanes (Always Present)

These lanes should appear in every drums grid:

- **`KICK`** - Kick drum (GM pitches 35/36)
- **`SNARE`** - Snare drum (GM pitches 38/40)
- **`HAT_C`** - Closed hi-hat (GM pitch 42)

### Optional Lanes (Template-Dependent)

These lanes appear based on groove template and section parameters:

- **`HAT_O`** - Open hi-hat (GM pitch 46)
  - Appears when `open_hat_rate > 0` or `hats_open_rate > 0`
  - Typically on offbeats and bar-end pickups

- **`HAT_P`** - Pedal hi-hat / foot chick (GM pitch 44)
  - Appears when `hats_pedal_rate > 0`
  - Typically on beats 2 and 4 (backbeats)

- **`RIDE`** - Ride cymbal (GM pitch 51)
  - Appears when template has `use_ride: true`
  - Replaces `HAT_C` as the timekeeping pattern

- **`CRASH`** - Crash cymbal (GM pitch 49)
  - Appears when `crash_start: true` (bar 1 downbeat)
  - Appears when `crash_phrase_end_rate > 0` (last bar, probabilistic)

- **`TOM_L`, `TOM_M`, `TOM_H`** - Low/mid/high toms (GM pitches 45/47/50)
  - Appears in fills (future implementation)

### Velocity Symbols

Grid cells use single characters to indicate hit velocity:

- **`X`** - Loud hit (velocity >= 110)
- **`^`** - Accent (velocity 92-109)
- **`x`** - Normal hit (velocity 70-91)
- **`g`** - Ghost note (velocity < 70)
  - Common on SNARE lane when `ghost_rate > 0`
- **`.`** - Soft hit (velocity < 55, rare except on hats)
- **`-`** - Rest / no hit

### Grid Structure Validation

A well-formed drums grid should:

1. **Header** - Show `INSTRUMENT: drums`, meter (e.g., `4.00 beats/bar`), and subdivision (e.g., `16 steps/bar`)
2. **Bar separators** - Each bar starts with `BAR n |` followed by step labels (e.g., `1e&a2e&a3e&a4e&a`)
3. **Lane alignment** - All lanes are left-aligned with consistent spacing
4. **Sorted lanes** - Lanes appear in alphabetical order: `CRASH`, `HAT_C`, `HAT_O`, `HAT_P`, `KICK`, `RIDE`, `SNARE`, `TOM_H`, `TOM_L`, `TOM_M`

### Example Grid (Minimal)

```text
INSTRUMENT: drums
METER: 4.00 beats/bar   SUBDIV: 16 steps/bar

BAR 1   |1e&a2e&a3e&a4e&a|
HAT_C   |x-x-x-x-x-x-x-x-|
KICK    |x-------x-------|
SNARE   |----x-------x---|
```

### Example Grid (With Ghosts and Open Hats)

```text
INSTRUMENT: drums
METER: 4.00 beats/bar   SUBDIV: 16 steps/bar

BAR 1   |1e&a2e&a3e&a4e&a|
CRASH   |x---------------|
HAT_C   |x-x-x-x-x-x-x-x-|
HAT_O   |----------------|
KICK    |x-------x-------|
SNARE   |----x-g-----x-g-|

BAR 2   |1e&a2e&a3e&a4e&a|
CRASH   |----------------|
HAT_C   |x-x-x-x-x-x-x---|
HAT_O   |--------------x-|
KICK    |x-------x-------|
SNARE   |----x-g-----x-g-|
```

### Common Validation Errors

**Missing required lanes:**
- If `KICK`, `SNARE`, or `HAT_C` are missing, check pitch mapping in `produzre/engine/drums/__init__.py`

**Unexpected lanes:**
- If unknown pitches appear (e.g., `P60`), check GM drum mapping in `grid_format.py:GM_DRUM_NAMES`

**Inconsistent ghost notes:**
- Ghost notes (`g`) should appear when `ghost_rate > 0` and `ghost_steps` are eligible
- Check `default_ghost_steps()` in `produzre/engine/drums/patterns/snare.py`

**Open hats not appearing:**
- Verify `hats_open_rate > 0` or `open_hat_rate > 0` in template/section
- Check eligible steps in `generate_top_cymbal_events()` in `produzre/engine/drums/patterns/hats.py`

---

## When to use which

Use **grid** when:

- You want to quickly see the groove shape.
- You want to validate placement rules (backbeat, syncopation, fills).
- You’re tuning density, accents, and per-voice params.

Use **events TSV** when:

- You want to debug “why did this change?”
- You need exact beat/velocity/pitch data.
- You are writing tests or regression checks.

---

## Typical workflows

### Compare two builds
Because TSV is deterministic (for fixed seeds), diffs are meaningful.

```bash
# build A
python -m produzre.cli build examples/song.yaml

# build B (after a change)
python -m produzre.cli build examples/song.yaml

# diff the event dumps
diff -u exports/<runA>/instruments/drums/<Song>_drums.events.tsv \
        exports/<runB>/instruments/drums/<Song>_drums.events.tsv
```

### Validate a new drum feature
1. Adjust a parameter (e.g., hats open rate, ghost rate).
2. Rebuild.
3. Inspect `*_drums.grid.txt`.
4. If results are subtle, inspect the TSV for velocity/pitch differences.

---

## Determinism notes

Produzre aims for:

> **same YAML + same project = same output**

Even when the output “sounds human”, randomness should be sourced from deterministic RNG seeded by:

- project seed (user’s project registry)
- song seed (from YAML)
- section and instrument sub-seeds (derived deterministically)

If analysis exports differ between two runs using the same configuration, it usually means:

- a non-deterministic RNG call path exists,
- a seed was not passed through consistently, or
- a build is picking up environment-specific jitter.

This subpackage is often the first place you’ll notice such issues.

---

## Extending the analysis layer

If you add new instruments or new per-voice semantics, keep these principles:

- Grid formatters should remain **simple** and **monospace-friendly**.
- TSV columns should be additive, not breaking.
- Prefer adding new tags/columns over encoding meaning into fragile strings.

Possible future expansions:

- A JSON export format for web visualization.
- A “phrase summary” report (fills per section, accent counts, density histograms).
- Regression test helpers (assert expected groove shapes).

---

## Module overview

- `grid_format.py`
  - Converts timeline events to ASCII lane grids.
  - Responsible for alignment, symbols, and readability.

- `tsv_events.py`
  - Reads/writes TSV event dumps.
  - Provides parsing helpers to load TSV into Python structures.

If you’re debugging a groove problem, start with the grid.
If you’re debugging a determinism problem, start with the TSV.
