# Produzre Engine Authoring Guide

This guide explains how to create custom instrument engines for Produzre without modifying orchestration code.

## Table of Contents

1. [Engine Specification](#engine-specification)
2. [Writing a Custom Engine](#writing-a-custom-engine)
3. [The render_into_timeline Interface](#the-render_into_timeline-interface)
4. [The contribute_plan Interface](#the-contribute_plan-interface-optional)
5. [Plan Keys and Data Structures](#plan-keys-and-data-structures)
6. [Priority and Dependencies](#priority-and-dependencies)
7. [Example: Custom Synth Engine](#example-custom-synth-engine)
8. [Registration and Testing](#registration-and-testing)

---

## Engine Specification

Engines are registered in `produzre/resources/engines.yml` (or overridden in project-level configs). Each engine entry defines:

```yaml
my_instrument:
  engine: ".engine.my_instrument"  # Python module path (relative to produzre)
  priority: 5                       # Execution order (lower = earlier)
  channel: 4                        # MIDI channel (0-15)
  program: 80                       # GM program number (optional)
  enabled: true                     # Whether engine is active
  requires: ["harmony.plan"]        # Plan keys this engine depends on
  provides: ["my.feature"]          # Plan keys this engine exports
  roles: ["lead", "texture"]        # Musical roles (for documentation)
```

### Field Descriptions

- **engine**: Python import path (relative to `produzre` package). Use dot notation with leading dot for relative imports.
- **priority**: Integer execution order. Lower values run first. Typical values:
  - `0`: Structural engines (harmony)
  - `1-2`: Rhythm section (drums, bass)
  - `3-5`: Melodic/harmonic instruments
  - `10+`: Effects or post-processing
- **channel**: MIDI channel (0-15). Channel 9 is reserved for drums (GM standard).
- **program**: Optional MIDI program change number (0-127). Set to `null` if not applicable.
- **enabled**: Boolean. Set to `false` to disable without removing from config.
- **requires**: List of plan keys this engine needs (e.g., `["harmony.plan", "rhythm.grid"]`). Validated before execution.
- **provides**: List of plan keys this engine exports via `contribute_plan`.
- **roles**: Descriptive tags for documentation (e.g., `["rhythm", "foundation", "lead"]`).

---

## Writing a Custom Engine

A Produzre engine is a Python module with one or two functions:

1. **`render_into_timeline(...)`** (required): Generates MIDI events
2. **`contribute_plan(...)`** (optional): Exports structural data to PerformancePlan

### Module Structure

```python
# produzre/engine/my_instrument/__init__.py

"""My custom instrument engine."""

# Optional: Module-level constants (used as defaults if not in YAML)
ENGINE_DEFAULT_PRIORITY = 5
ENGINE_DEFAULT_CHANNEL = 4
ENGINE_DEFAULT_PROGRAM = 80


def render_into_timeline(*args, **kwargs):
    """Generate MIDI events for this instrument.

    This function is called once per section. It should add events to
    the provided timeline using section-relative beat positions.

    Args (all via kwargs):
        cfg: RootConfig - Global configuration
        section: SectionConfig - Current section configuration
        instrument_name: str - Name of this instrument
        instrument_cfg: InstrumentConfig - Per-section instrument settings
        harmony_plan: Optional[HarmonySectionPlan] - Chord structure
        rhythm_grid: RhythmGrid - Beat subdivision grid
        section_start_beat: float - Song-relative start beat
        rng: random.Random - Deterministic RNG for this section
        timeline: InstrumentTimeline - Timeline to add events to
        transition_context: dict - Section boundary metadata
        rhythm_features: dict - Shared rhythm data from other instruments
        feedback_collector: FeedbackCollector - For negotiation feedback
        logger: logging.Logger - For debug output

    Returns:
        None (mutates timeline in place)
    """
    if args:
        raise TypeError("render_into_timeline only supports keyword arguments")

    # Extract parameters
    cfg = kwargs.get("cfg")
    section = kwargs.get("section")
    timeline = kwargs.get("timeline")
    section_start_beat = kwargs.get("section_start_beat", 0.0)
    rng = kwargs.get("rng")
    logger = kwargs.get("logger")

    # Your rendering logic here
    # Example: Add a note at beat 0
    timeline.add_note(
        start_beat=section_start_beat + 0.0,
        duration_beats=1.0,
        pitch=60,  # Middle C
        velocity=80,
    )


def contribute_plan(*args, **kwargs):
    """Export structural data to the PerformancePlan (optional).

Called during an ordered planning pass before any engine renders MIDI. Earlier
providers in priority order are available to later planning hooks, and all
completed planning hooks are visible to every render call. Use this to share
derived data such as roles, activity windows, groove patterns, and phrase
boundaries.

    Args (all via kwargs):
        plan: PerformancePlan - Central data store
        section_ctx: dict - Section metadata
        rng: random.Random - Deterministic RNG
        logger: logging.Logger - For debug output

    Returns:
        None (mutates plan in place)
    """
    if args:
        raise TypeError("contribute_plan only supports keyword arguments")

    plan = kwargs.get("plan")
    section_ctx = kwargs.get("section_ctx", {})
    logger = kwargs.get("logger")

    if plan is None:
        return

    # Export data to plan
    plan.set("my.feature", {"some": "data"})

    if logger:
        logger.debug("[MY_ENGINE] Exported my.feature to plan")
```

---

## The render_into_timeline Interface

### Required Signature

```python
def render_into_timeline(*args, **kwargs) -> None:
```

All parameters are passed as keyword arguments. Engines **must** reject positional arguments:

```python
if args:
    raise TypeError("render_into_timeline only supports keyword arguments")
```

### Available Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `cfg` | `RootConfig` | Global song configuration (key, mode, BPM, etc.) |
| `section` | `SectionConfig` | Current section (type, bars, harmony, instruments) |
| `instrument_name` | `str` | Name of this instrument (e.g., "bass", "lead_gtr") |
| `instrument_cfg` | `InstrumentConfig` | Per-section settings (intensity, style, etc.) |
| `harmony_plan` | `Optional[HarmonySectionPlan]` | Chord structure (if harmony defined) |
| `rhythm_grid` | `RhythmGrid` | Beat subdivision grid for timing |
| `section_start_beat` | `float` | Song-relative start beat of this section |
| `rng` | `random.Random` | Deterministic RNG (same seed = same output) |
| `timeline` | `InstrumentTimeline` | Timeline to add events to |
| `transition_context` | `dict` | Boundary metadata (prev/next section types, energy) |
| `rhythm_features` | `dict` | Shared rhythm data from other instruments |
| `feedback_collector` | `FeedbackCollector` | For providing negotiation feedback |
| `logger` | `logging.Logger` | For debug output |

### Adding Events to Timeline

```python
# Add a note
timeline.add_note(
    start_beat=section_start_beat + local_beat,  # Song-relative position
    duration_beats=0.5,                          # Note length
    pitch=60,                                    # MIDI note number (0-127)
    velocity=80,                                 # Velocity (0-127)
)

# Add a control change
timeline.add_cc(
    beat=section_start_beat + local_beat,
    controller=64,  # Sustain pedal
    value=127,      # On
)

# Add a program change
timeline.add_program_change(
    beat=section_start_beat + 0.0,
    program=80,  # Synth lead
)
```

### Using Harmony Plan

```python
harmony_plan = kwargs.get("harmony_plan")

if harmony_plan and harmony_plan.chord_slots:
    for slot in harmony_plan.chord_slots:
        # slot.index: Sequential index (0, 1, 2, ...)
        # slot.numeral: Roman numeral ("I", "bVII", "V")
        # slot.start_beat: Local beat position (section-relative)
        # slot.end_beat: End of chord slot

        # Example: Arpeggiate chord tones
        root_midi = compute_root_from_numeral(slot.numeral, cfg.song.key)
        timeline.add_note(
            start_beat=section_start_beat + slot.start_beat,
            duration_beats=0.5,
            pitch=root_midi,
            velocity=80,
        )
```

### Deterministic RNG

Always use the provided `rng` for random decisions:

```python
rng = kwargs.get("rng")

# Good: Deterministic
if rng.random() < 0.5:
    add_variation()

# Bad: Non-deterministic
import random
if random.random() < 0.5:  # DON'T DO THIS
    add_variation()
```

---

## The contribute_plan Interface (Optional)

Use `contribute_plan` to export structural data before rendering. This enables engine-to-engine coordination.

### When to Use

- You want other engines to lock to your rhythm patterns (like drums)
- You generate phrase boundaries or cues
- You compute structural data that melodic engines need

### Required Signature

```python
def contribute_plan(*args, **kwargs) -> None:
```

### Available Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `plan` | `PerformancePlan` | Central data store for engine communication |
| `section_ctx` | `dict` | Section metadata (cfg, section, harmony_plan, etc.) |
| `rng` | `random.Random` | Deterministic RNG |
| `logger` | `logging.Logger` | For debug output |

### Example: Exporting Rhythm Data

```python
def contribute_plan(*args, **kwargs):
    if args:
        raise TypeError("contribute_plan only supports keyword arguments")

    plan = kwargs.get("plan")
    section_ctx = kwargs.get("section_ctx", {})
    logger = kwargs.get("logger")

    if plan is None:
        return

    # Extract section info
    section = section_ctx.get("section")
    rhythm_grid = section_ctx.get("rhythm_grid")

    # Compute accent beats (strong beats for coordination)
    accent_beats = []
    beats_per_bar = rhythm_grid.beats_per_bar
    num_bars = int(rhythm_grid.total_beats / beats_per_bar)

    for bar in range(num_bars):
        bar_start = bar * beats_per_bar
        accent_beats.append(bar_start)  # Downbeat
        accent_beats.append(bar_start + beats_per_bar - 1)  # Last beat

    # Export to plan
    plan.set("my_instrument.accents", {
        "accent_beats": accent_beats,
        "num_accents": len(accent_beats),
    })

    if logger:
        logger.debug(f"[MY_ENGINE] Exported {len(accent_beats)} accent beats")
```

---

## Plan Keys and Data Structures

The PerformancePlan is a shared key-value store for engine communication. Keys use dot notation for namespacing.

### Reserved Plan Keys

| Key | Provided By | Description |
|-----|-------------|-------------|
| `harmony.plan` | harmony | Chord structure (HarmonySectionPlan) |
| `rhythm.grid` | drums | Step grid (16th note resolution) |
| `rhythm.accents` | drums | Strong beat positions |
| `transitions.map` | orchestrator | Section-level transition directives |
| `suggested_density` | negotiation | Density hints from other engines |
| `suggested_energy` | negotiation | Energy hints from other engines |

### Accessing Plan Data

```python
# Check if key exists
if plan.has("rhythm.grid"):
    grid_data = plan.get("rhythm.grid")

# Get with default
density = plan.get("suggested_density.verse1", default=0.5)

# Set data
plan.set("my_instrument.feature", data)
```

### Data Structure Examples

**harmony.plan** (serialized HarmonySectionPlan):
```python
{
    "section_id": "verse1",
    "meter": {"numerator": 4, "denominator": 4},
    "total_beats": 32.0,
    "chord_rate": 4.0,
    "chord_slots": [
        {
            "index": 0,
            "numeral": "i",
            "start_beat": 0.0,
            "end_beat": 4.0,
        },
        # ... more slots
    ]
}
```

**rhythm.grid**:
```python
{
    "beats_per_bar": 4.0,
    "total_beats": 32.0,
    "steps_per_beat": 4,  # 16th notes
    "steps_per_bar": 16,
    "total_steps": 128,
    "step_duration_beats": 0.25,
}
```

**rhythm.accents**:
```python
{
    "accent_beats": [0.0, 1.0, 3.0, 4.0, 5.0, 7.0, ...],  # Beat positions
    "num_accents": 24,
    "source": "drums",
}
```

---

## Priority and Dependencies

### Execution Order

Engines execute in **priority order** (ascending). Lower priority values run first:

```yaml
harmony:
  priority: 0  # Runs first (provides chord structure)

drums:
  priority: 1  # Runs second (provides rhythm)

bass:
  priority: 2  # Runs third (needs harmony and rhythm)
  requires: ["harmony.plan"]

lead_gtr:
  priority: 4  # Runs last (needs harmony)
  requires: ["harmony.plan"]
```

### Dependency Validation

Before an engine runs, the orchestrator validates that all required plan keys exist:

```yaml
my_instrument:
  requires: ["harmony.plan", "rhythm.grid"]
```

If `harmony.plan` is missing, the build fails with:
```
ConfigError: Engine 'my_instrument' has unsatisfied dependencies:
  - Missing 'harmony.plan' (provided by: 'harmony')

Possible solutions:
  1. Enable the 'harmony' engine
  2. Add 'harmony' to the section instruments
  3. Adjust priorities so 'harmony' runs before 'my_instrument'
```

### Best Practices

- **Structural engines** (harmony, meter): priority 0
- **Rhythm section** (drums, percussion): priority 1-2
- **Bass instruments**: priority 2-3 (after drums, before melody)
- **Melodic/harmonic instruments**: priority 3-5
- **Effects/post-processing**: priority 10+

---

## Example: Custom Synth Engine

Let's create a simple synth pad engine that plays held chords.

### 1. Create the Module

`produzre/engine/synth_pad/__init__.py`:

```python
"""Simple synth pad engine - plays sustained chords."""

from typing import Any
import logging

ENGINE_DEFAULT_PRIORITY = 5
ENGINE_DEFAULT_CHANNEL = 5
ENGINE_DEFAULT_PROGRAM = 89  # GM Pad 2 (warm)


def render_into_timeline(*args: Any, **kwargs: Any) -> None:
    """Render sustained pad chords based on harmony plan."""
    if args:
        raise TypeError("render_into_timeline only supports keyword arguments")

    cfg = kwargs.get("cfg")
    section = kwargs.get("section")
    harmony_plan = kwargs.get("harmony_plan")
    section_start_beat = kwargs.get("section_start_beat", 0.0)
    timeline = kwargs.get("timeline")
    instrument_cfg = kwargs.get("instrument_cfg")
    logger = kwargs.get("logger")

    if harmony_plan is None or not harmony_plan.chord_slots:
        if logger:
            logger.debug("synth_pad: no harmony plan, skipping")
        return

    # Get intensity from config
    intensity = getattr(instrument_cfg, "intensity", 0.5)
    velocity = int(60 + (intensity * 40))  # 60-100 range

    # Play each chord as a sustained triad
    for slot in harmony_plan.chord_slots:
        # Parse root from Roman numeral (simplified)
        root_midi = _parse_root_midi(slot.numeral, cfg.song.key)

        # Build triad
        is_minor = slot.numeral.strip().lower() == slot.numeral.strip()
        third_offset = 3 if is_minor else 4

        chord_notes = [
            root_midi + 12,  # Root (octave up for pad register)
            root_midi + 12 + third_offset,  # Third
            root_midi + 12 + 7,  # Fifth
        ]

        # Add sustained notes for chord duration
        duration = slot.end_beat - slot.start_beat

        for pitch in chord_notes:
            timeline.add_note(
                start_beat=section_start_beat + slot.start_beat,
                duration_beats=duration,
                pitch=pitch,
                velocity=velocity,
            )

    if logger:
        logger.info(
            f"synth_pad: added {len(harmony_plan.chord_slots) * 3} pad notes "
            f"(intensity={intensity:.2f})"
        )


def _parse_root_midi(numeral: str, key: str) -> int:
    """Parse Roman numeral to MIDI note number (simplified)."""
    # This is a simplified example - use produzre.engine.bass.harmony
    # for production-quality parsing

    KEY_TO_MIDI = {
        "C": 48, "D": 50, "E": 52, "F": 53,
        "G": 55, "A": 57, "B": 59,
    }

    DEGREE_OFFSETS = [0, 2, 4, 5, 7, 9, 11]  # Major scale

    # Parse degree from numeral (very simplified)
    numeral_upper = numeral.strip().upper().lstrip("B#")
    roman_to_degree = {"I": 0, "II": 1, "III": 2, "IV": 3,
                       "V": 4, "VI": 5, "VII": 6}

    degree_index = roman_to_degree.get(numeral_upper, 0)
    tonic = KEY_TO_MIDI.get(key.upper(), 48)

    return tonic + DEGREE_OFFSETS[degree_index]
```

### 2. Register in engines.yml

Add to `produzre/resources/engines.yml`:

```yaml
synth_pad:
  engine: ".engine.synth_pad"
  priority: 5
  channel: 5
  program: 89  # GM Pad 2 (warm)
  enabled: true
  requires: ["harmony.plan"]
  provides: ["pad.texture"]
  roles: ["pad", "texture"]
```

### 3. Use in Song YAML

```yaml
version: 1
song:
  title: "Synth Pad Example"
  bpm: 90
  key: C
  mode: ionian
  exports_root: "exports"

sections:
  verse:
    type: verse
    bars: 4
    harmony:
      progression: "I V vi IV"
    instruments:
      harmony:
        intensity: 0.7
      synth_pad:
        intensity: 0.6
      bass:
        intensity: 0.7

arrangement:
  - verse
```

---

## Registration and Testing

### Project-Level Override

You can override engine settings in your project YAML:

```yaml
version: 1
song:
  # ... song settings

engines:
  # Override synth_pad channel
  synth_pad:
    channel: 6
    program: 90  # Different pad sound

sections:
  # ... sections
```

### Custom Engine Module Path

For engines outside the produzre package:

```yaml
engines:
  my_custom:
    engine: "my_package.engines.custom_synth"  # Absolute import
    priority: 5
    channel: 7
    program: 80
    requires: ["harmony.plan"]
```

### Testing Your Engine

1. **Add logging** to see what your engine is doing:
   ```python
   if logger:
       logger.debug(f"[MY_ENGINE] Generated {event_count} events")
   ```

2. **Test with dry-run**:
   ```bash
   python -m produzre.cli build my_song.yaml --dry-run -v
   ```

3. **Check event counts**:
   Look for the instrument summary in output:
   ```
   Instrument event summary:
     synth_pad: 12 events
   ```

4. **Verify MIDI output**:
   ```bash
   python -m produzre.cli build my_song.yaml
   # Check exports/my_song.mid in DAW
   ```

5. **Use deterministic seeds**:
   ```yaml
   song:
     seed: 42  # Same seed = same output
   ```

---

## Negotiation Feedback (Phase N8)

Engines can provide feedback to influence subsequent sections:

```python
def render_into_timeline(*args, **kwargs):
    # ... rendering logic

    feedback_collector = kwargs.get("feedback_collector")
    if feedback_collector:
        # Suggest higher density for next section
        feedback_collector.add_feedback(
            engine_name="my_instrument",
            feedback_type="density",
            plan_key="suggested_density",
            adjustment={"suggested_density": 0.8},
            target_section_id="chorus1",  # Specific section
            priority=0.6,
            reason="Build energy for chorus",
        )
```

### Whitelisted Feedback Keys

Only these plan keys can be modified via negotiation:
- `transitions.map` - Transition adjustments
- `rhythm.accents` - Rhythm hints
- `suggested_density` - Density suggestions
- `suggested_energy` - Energy suggestions

---

## Summary Checklist

To create a custom engine:

- [ ] Create module with `render_into_timeline()` function
- [ ] Use keyword-only arguments (`if args: raise TypeError(...)`)
- [ ] Add events using `timeline.add_note()` with song-relative beats
- [ ] Use provided `rng` for deterministic randomness
- [ ] Optional: Add `contribute_plan()` to export structural data
- [ ] Register in `engines.yml` with priority and dependencies
- [ ] Test with `--dry-run -v` to verify execution
- [ ] Check MIDI output in DAW

**No orchestration code changes required!** The engine framework handles loading, ordering, dependency validation, and execution automatically.
