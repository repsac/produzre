# Produzre Determinism Contract

**Goal:** "Same YAML + same project = same outputs" with controlled variation via "takes."

## Overview

Produzre guarantees bit-identical reproducibility: given the same configuration and project seed, the system produces identical MIDI outputs across runs. This enables:

- **Reproducible builds**: Share YAML configs and regenerate identical outputs
- **Version control**: Track changes in outputs via diffs
- **Controlled variation**: Use "takes" to explore alternatives while maintaining reproducibility
- **Debugging**: TSV exports include deterministic tags showing decision paths

## RNG Hierarchy

Produzre uses a hierarchical RNG system where each level derives its seed from the parent scope plus stable contextual keys:

```
project_seed (per-user, persistent)
    ↓
song_seed (in YAML: song.seed)
    ↓
take (in YAML: song.take - optional controlled variation)
    ↓
section_rng (section_id + section_type)
    ↓
instrument_rng (section + instrument_name)
        ↓
    voice_rng (section + instrument + voice_name)
            ↓
        event_rng (section + instrument + voice + bar + step)
```

### Scope Definitions

**project_seed**
- Per-user persistent seed stored in `~/.config/produzre/projects.yml`
- Enables collaboration: different users can work on same YAML with different outputs
- Use `produzre project export` to share project seeds for bit-identical collaboration

**song_seed** (`song.seed` in YAML)
- Author-controlled seed for exploration and variation
- Different seeds produce different arrangements
- Same seed always produces same output

**take** (`song.take` in YAML, default: 0)
- Optional take number for controlled micro-variation
- Different takes = different ghost notes, fills, accents
- Same take = identical output (reproducible)
- Use case: "Try another take" for A/B testing variations

**section_rng**
- One RNG per section in the arrangement
- Seeded from: `project_seed + song_seed + take + section_id + section_type`
- Ensures different sections don't interfere with each other's randomness

**instrument_rng**
- One RNG per instrument per section
- Seeded from: `section_rng.state + instrument_name`
- Isolates instruments: adding bass doesn't change drums output

**voice_rng**
- One RNG per voice (kick, snare, hats, etc.) per instrument
- Seeded from: `instrument_rng.state + voice_name + section_id + instrument_name`
- Isolates voices: changing kick pattern doesn't change hats

**event_rng**
- Per-event decisions (velocity humanization, micro-timing)
- Seeded from: `voice_rng.state + bar_idx + step_idx`
- Spatial consistency: same bar position gets same micro-adjustments

## Granular Seed & Variation Overrides

In addition to the song-level `seed` and `take`, you can override seeds and variation at the **section** and **instrument** level:

```yaml
sections:
  chorus:
    seed: 999            # Re-roll all instruments in this section only
    variation: 0.3       # Variation bias for this section
    instruments:
      drums:
        seed: 777        # Re-roll ONLY drums in this section
        variation: 0.5   # Per-instrument variation override
```

**How overrides work:**
- **Section seed**: Replaces the song seed for that section's RNG derivation. All other sections remain unchanged.
- **Instrument seed**: Replaces the section seed for that specific instrument's RNG. All other instruments in the section remain unchanged.
- **Variation**: Cascades from song > section > instrument (most specific wins).

### Repeated Section Differentiation

When the same section appears multiple times in the arrangement, each occurrence automatically produces different output:

```yaml
arrangement:
  - chorus    # Occurrence 1 of chorus
  - verse
  - chorus    # Occurrence 2 — sounds different from occurrence 1
  - chorus    # Occurrence 3 — sounds different from 1 and 2
```

The arrangement position index is mixed into the RNG seed, so repeated sections are differentiated without requiring separate section definitions (no need for `chorus_1`, `chorus_2`, etc.).

## Usage

### Basic Reproducibility

```yaml
# song.yaml
version: 1
song:
  title: "MySong"
  seed: 42  # Reproducible outputs
```

Run multiple times:
```bash
produzre build song.yaml  # Always produces identical MIDI
produzre build song.yaml  # Bit-identical to first run
```

### Exploring Variations

```yaml
song:
  seed: 42      # Try different seeds: 43, 44, 100, etc.
  take: 0       # Try different takes: 0, 1, 2, 3...
```

**Seed vs Take:**
- **Seed**: Changes overall arrangement (different patterns, progressions, structures)
- **Take**: Changes micro-details (different ghost notes, fills, accents) while keeping arrangement

### Controlled Variation with Takes

```yaml
# take-0.yaml
song:
  seed: 42
  take: 0  # First take

# take-1.yaml
song:
  seed: 42
  take: 1  # Second take (different ghost notes, same groove)
```

Takes allow "another take please" workflow:
```bash
produzre build song.yaml  # seed=42, take=0
# Listen to output, want a variation...
# Edit YAML: take: 0 → take: 1
produzre build song.yaml  # seed=42, take=1 (different ghosts, same structure)
```

### TSV Determinism Tags

Event TSV exports include a `kind` column showing the decision path:

```tsv
instrument  section_id  bar  beat    pitch  velocity  kind
drums       verse       1    1.000   36     80        kick
drums       verse       1    2.000   38     75        snare
drums       verse       1    2.750   38     45        snare_ghost
drums       verse       1    3.000   36     78        kick
drums       verse       4    4.000   47     82        fill
```

**Common kind tags:**
- Drums: `kick`, `snare`, `snare_ghost`, `hat`, `hat_close`, `open_hat`, `ride`, `crash`, `fill`, `crash_transition`, `kick_transition`
- Bass (future): `root`, `fifth`, `passing`, `ornament`

Use for debugging:
```bash
# Compare ghost note placements between takes
grep "snare_ghost" take-0.tsv > ghosts-0.txt
grep "snare_ghost" take-1.tsv > ghosts-1.txt
diff ghosts-0.txt ghosts-1.txt
```

## Implementation

### For Engine Authors

Engines receive deterministic RNGs from the orchestrator:

```python
def render_into_timeline(
    *,
    rng: random.Random,        # Section-level RNG (from orchestrator)
    section: SectionConfig,
    instrument_name: str,
    timeline: InstrumentTimeline,
    **kwargs
) -> None:
    # 1. Create instrument-specific RNG
    from produzre.rng import make_instrument_rng
    instrument_rng = make_instrument_rng(rng, instrument_name)

    # 2. Create voice-specific RNGs
    from produzre.rng import make_voice_rng
    kick_rng = make_voice_rng(instrument_rng, "kick", section.id, instrument_name)
    snare_rng = make_voice_rng(instrument_rng, "snare", section.id, instrument_name)

    # 3. Use voice RNGs for decisions
    if kick_rng.random() < 0.25:
        # Add syncopated kick
        timeline.add_note(beat=1.75, pitch=36, velocity=80, kind="kick")

    if snare_rng.random() < 0.3:
        # Add ghost note
        timeline.add_note(beat=2.75, pitch=38, velocity=45, kind="snare_ghost")
```

### RNG Module API

```python
from produzre.rng import (
    stable_seed_int,        # Create deterministic seeds
    make_section_rng,       # Create section RNG
    make_instrument_rng,    # Create instrument RNG
    make_voice_rng,         # Create voice RNG
    make_event_seed,        # Create event-level seed
    make_bar_rng,           # Create bar-level RNG
)

# Example: Bar-level variation
bar_rng = make_bar_rng(voice_rng, bar_idx=2)
bar_accent_boost = bar_rng.uniform(0.0, 0.2)
```

## Verification

### Testing Reproducibility

```bash
# Build same config twice
produzre build song.yaml --song-name test1
produzre build song.yaml --song-name test2

# Compare TSV outputs (should be identical)
diff exports/test1_*/analysis/drums/*.events.tsv \
     exports/test2_*/analysis/drums/*.events.tsv
# Output: (no differences) = success!
```

### Testing Take Variation

```bash
# Build with different takes
produzre build song-take0.yaml --song-name take0
produzre build song-take1.yaml --song-name take1

# Verify different outputs
diff exports/take0_*/analysis/drums/*.events.tsv \
     exports/take1_*/analysis/drums/*.events.tsv
# Output: (differences found) = success!

# Verify same take produces identical outputs
produzre build song-take0.yaml --song-name take0-test1
produzre build song-take0.yaml --song-name take0-test2
diff exports/take0-test1_*/analysis/drums/*.events.tsv \
     exports/take0-test2_*/analysis/drums/*.events.tsv
# Output: (no differences) = success!
```

## Design Rationale

### Why Hierarchical RNG?

**Problem**: Flat RNG coupling
```python
# BAD: All decisions share one RNG
if rng.random() < 0.5:
    add_kick()
if rng.random() < 0.3:
    add_ghost()
# Changing kick probability changes ghost placement!
```

**Solution**: Hierarchical scoping
```python
# GOOD: Independent RNG streams
kick_rng = make_voice_rng(instrument_rng, "kick", ...)
snare_rng = make_voice_rng(instrument_rng, "snare", ...)

if kick_rng.random() < 0.5:
    add_kick()
if snare_rng.random() < 0.3:
    add_ghost()
# Kick and ghost decisions are independent!
```

### Why Takes?

**Problem**: Seed changes everything
```yaml
seed: 42  # Great verse, okay chorus
seed: 43  # Okay verse, great chorus
# Can't keep the great verse and great chorus together!
```

**Solution**: Takes preserve structure, vary micro-details
```yaml
seed: 42, take: 0  # Great verse, okay chorus
seed: 42, take: 1  # Great verse, slightly different chorus
seed: 42, take: 2  # Great verse, another chorus variation
# Structure stays, details vary
```

### Why Deterministic Tags?

**Problem**: Hard to debug probabilistic decisions
```
"Why did this ghost note appear here but not in the other take?"
"Which decision path created this fill?"
```

**Solution**: TSV `kind` column traces decision source
```tsv
kind: snare_ghost     → from ghost_rate probability
kind: fill            → from phrase-end fill logic
kind: crash_transition → from section transition detection
```

## Future Extensions

### Cross-Instrument Coordination (Phase 14)

Voice RNGs enable predictable cross-instrument rhythm coupling:

```python
# Drums exports rhythm features
drums_rng = make_voice_rng(instrument_rng, "kick", section.id, "drums")
kick_pattern = generate_kicks(drums_rng, ...)

# Bass uses same RNG seed to follow kicks
bass_rng = make_voice_rng(instrument_rng, "root", section.id, "bass")
# Because drums and bass use different instrument_rng parents,
# they're independent - but we can explicitly share features
bass_notes = follow_kick_pattern(bass_rng, kick_pattern)
```

### Distributed Collaboration

Project seed export/import enables bit-identical collaboration:

```bash
# Alice exports her project seed
produzre project export my-song > my-song-project.json

# Bob imports Alice's project seed
produzre project import my-song-project.json

# Now Alice and Bob generate identical outputs from same YAML
```

## Summary

**Guarantees:**
- ✅ Same YAML + same project = bit-identical outputs
- ✅ Different takes = reproducible variations
- ✅ Independent instruments/voices (no coupling)
- ✅ TSV tags trace decision paths

**Best Practices:**
- Use `seed` for exploring different arrangements
- Use `take` for micro-variations of same arrangement
- Check TSV `kind` column for debugging probabilistic decisions
- Export project seeds for collaboration

## Automated Validation Tools

### CLI Strict Determinism Mode

The `--strict-determinism` flag validates deterministic builds by building the song twice and comparing MIDI outputs byte-for-byte:

```bash
# Validate determinism during build
python3 -m produzre.cli build examples/rhythm_gtr/sustained-chords-demo.yaml --strict-determinism
```

**Output Example:**
```
=== Strict Determinism Check ===
Building song a second time to verify deterministic output...
✓ Determinism check PASSED - 120 MIDI files are byte-identical
Build 1: exports/SustainedChordsDemo_20260203_164413
Build 2: exports/SustainedChordsDemo_20260203_164413_1
```

**Exit Codes:**
- `0`: Determinism validated (all files match)
- `1`: Determinism failed (files differ or error occurred)

**What it checks:**
- Full song MIDI file
- All per-instrument stems
- All per-section MIDI clips
- All pattern MIDI files
- Sequencer YAML files

**Performance impact:**
- Doubles build time (song built twice)
- Minimal memory overhead (only hashes stored)
- Both build directories preserved for inspection

### Python Test Suite

The `tests/test_midi_determinism.py` module provides comprehensive determinism testing:

```bash
# Run all determinism tests
python3 tests/test_midi_determinism.py

# Or use pytest
pytest tests/test_midi_determinism.py -v
```

**Test Coverage:**
1. `test_full_song_determinism()`: Full song MIDI byte-identical across builds
2. `test_stems_determinism()`: Per-instrument stem MIDI determinism
3. `test_all_midi_files_determinism()`: All MIDI files (stems, sections, patterns)
4. `test_different_seeds_produce_different_outputs()`: Seed variation verification
5. `test_multiple_demo_determinism()`: Cross-demo validation

**MIDI Comparison Method:**
```python
import hashlib

def get_midi_hash(midi_path: Path) -> str:
    """Compute SHA256 hash of a MIDI file for comparison."""
    with open(midi_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()
```

### CI/CD Integration

Add determinism validation to continuous integration:

```yaml
# .github/workflows/test.yml
- name: Test MIDI Determinism
  run: |
    python3 tests/test_midi_determinism.py
    python3 -m produzre.cli build examples/rhythm_gtr/sustained-chords-demo.yaml --strict-determinism
```

### Regression Testing Workflow

1. **Build golden reference:**
```bash
python3 -m produzre.cli build song.yaml
mv exports/Song_* tests/golden/song-v1/
```

2. **Make code changes** (refactoring, new features, etc.)

3. **Validate determinism:**
```bash
python3 -m produzre.cli build song.yaml --strict-determinism
```

4. **Compare against golden:**
```bash
python3 tests/test_midi_determinism.py
```

### Troubleshooting Determinism Failures

If determinism validation fails:

**Check seeds:**
```yaml
song:
  seed: 42  # Must be set for reproducibility
```

**Check RNG usage in engines:**
```python
# ✓ GOOD: Use provided rng parameter
if rng.random() < 0.5:
    add_event()

# ✗ BAD: Create new Random()
import random
if random.random() < 0.5:  # Non-deterministic!
    add_event()
```

**Check file iteration order:**
```python
# ✓ GOOD: Sorted iteration
for file_path in sorted(directory.glob("*.mid")):
    process(file_path)

# ✗ BAD: Unsorted iteration
for file_path in directory.glob("*.mid"):  # Order may vary!
    process(file_path)
```

**Check timestamps:**
```python
# ✓ GOOD: Deterministic metadata
metadata = {"version": 1, "build": build_number}

# ✗ BAD: Non-deterministic timestamps
import datetime
metadata = {"timestamp": datetime.now()}  # Non-deterministic!
```
