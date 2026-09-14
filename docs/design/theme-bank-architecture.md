# Theme bank architecture

The theme system in 0.9.0 stores
rhythm and scale degrees so a song can reuse recognizable material across
sections and instruments. The bank belongs to the song; each arrangement
occurrence gets a treatment and a realization over its own harmony.

## Data model

[model.py](../../produzre/themes/model.py) defines:

| Type | Fields |
|---|---|
| `ThemeEvent` | `offset_beats`, `duration_beats`, `degree`, `accidental`, `octave`, `accent`. |
| `Theme` | `name`, `role`, `length_beats`, `events`, `base_register`, `tags`. |
| `ThemeBank` | Named themes and a stable `seed_material_hash`. |

Offsets and durations use quarter-note beats. Degree is 1-7; None means a rest.
Accidentals are semitone offsets from the selected mode degree. Octave is an
integer displacement. Events and themes are frozen dataclasses. The planner
assembles and finalizes the bank before rendering.

Roles are `riff`, `melody`, and `bass_motif`. `drum_groove` is reserved but rejected
by the YAML loader. Default MIDI registers are riff 40-55, melody 64-79, and
bass motif 28-48. Serialization includes rhythm, degrees, octaves, accents,
register, and tags. The bank hash also preserves declaration order because
that order selects the active theme for repeated roles.

## Planning and composition

The song planner reads the top-level `themes` block. If it is empty and
`song.themes_auto` is true, [compose.py](../../produzre/themes/compose.py)
creates `auto_riff` and `auto_hook`. See [theme controls](../llm-song-config-reference.md#themes) for automatic
composition and authored-bank precedence.

Automatic composition uses the [song-material RNG](../../DETERMINISM.md#seed-scopes).

The riff lasts one song-meter bar and starts and ends on the tonic. The hook
lasts two bars: a question with a half cadence, followed by a related answer
that resolves to the tonic. Genre weights choose rhythmic families and color
notes. Melodic motion prefers steps and balances leaps with nearby motion.
The composer truncates or pads cells on their original eighth/sixteenth grid,
keeping those subdivisions in odd meters.

A theme retains its duration in quarter notes across a section meter change.
It can cross the new barline because the planner keeps the song's original material.

## Authored material

```yaml
themes:
  main_riff:
    role: riff
    register: [40, 64]
    events: "1:.5 .:.5 b3:1 4:1 1:1"
  chorus_hook:
    role: melody
    allow_development: true
    degrees: [5, 6, 5, 2, 1]
    rhythm: [1, 1, 1, 1, 4]
```

The [theme controls](../llm-song-config-reference.md#themes) describe both input
forms, duration checks, octave suffixes, and rests. The loader also rejects
all-rest themes, reversed or out-of-MIDI registers, and unknown keys.

The loader records an authored theme's development lock with the `locked` tag.
The arc quotes a locked theme in every section. Pitch realization still respects harmony, register, and section clipping.
See the [configuration reference](../llm-song-config-reference.md#themes) for
all public fields and coupling controls.

## Treatments

[transform.py](../../produzre/themes/transform.py) implements pure operations
that return a new theme: `quote`, `thin`, `fragment`, `displace`, `augment`,
`diminish`, `sequence`, `invert`, and `octave_shift`. Transformations retain
pitch and rhythm identity to different degrees. Fragment clips events that
cross its boundary; displacement splits wrapped events instead of dropping
sustained time. Augmentation factors must be finite and positive.

[arc.py](../../produzre/themes/arc.py) chooses the default treatment:

| Section type | Treatment |
|---|---|
| Intro | First fragment. |
| Verse | Quote. |
| Prechorus / pre-chorus | Displace by half a beat. |
| Chorus / hook | Quote; later melody statements shift up an octave. |
| Bridge | Invert. |
| Solo | Sequence up two scale steps. |
| Breakdown | Thin. |
| Outro | Last fragment. |
| Other | Quote. |

Repeat counting is by section type in arrangement order, not only by section
id. Locked authored themes bypass this table. A narrow register may fold an
octave lift back into range, so an octave treatment need not change every note.
The table is internal policy; there is no YAML arc override yet.

## Realization

[realize.py](../../produzre/themes/realize.py) loops the treated theme across
the section and clips notes at the requested endpoint. Empty/zero-length
sections return no notes. Invalid nonpositive or nonfinite theme lengths raise
an error instead of entering an endless loop.

Each pitch starts from the section tonic, mode degree, accidental, and octave
near the chosen register. Octave folding keeps it in range. Borrowed chord
numerals use shared spelling: accidental prefixes reference the major scale.
This aligns bass, guitars, guide, and themes on chords such as minor-key bVII.

Interior non-chord notes can move by a semitone toward the current chord when
the preceding note is already a chord tone. Tonic degrees, genre blue notes, and the final sounded
note of each statement keep their pitch. This adjustment only affects
eligible interior notes.

## Engine integration

After all engine planning hooks and before any MIDI rendering, the orchestrator
realizes every named theme once for that occurrence. It publishes:

| Plan key | Value |
|---|---|
| `themes.bank` | The song's bank. |
| `themes.realized_by_name.<section>` | All named realized-note lists. |
| `themes.realized.<section>` | First declared theme for each role. |
| `melody.guide.<section>` and `melody.guide` | Targets built from the active melody theme, or the standalone melody planner when no melody theme exists. |

The guide reuses the already computed melody realization. Realization is not
cached across repeated sections because harmony, treatment, and occurrence can
differ. The orchestrator updates section-id keys for each occurrence.

See [theme coupling](../llm-song-config-reference.md#themes) for each engine's
listener controls and defaults. Acoustic treble melody and arpeggiator apex
notes use the guide. Drum coupling runs before kit constraints, so added
kicks still follow the groove's spacing and limb limits. The default leaves
one-drop and other genre grooves free of extra theme kicks.

## Demo and verification

```bash
python tools/demo_themes.py examples/themes_demo.yaml
python tools/demo_themes.py examples/themes_demo.yaml --midi exports/themes_demo.mid
python tools/demo_themes.py examples/themes_demo.yaml --transform "chorus=octave_shift:octaves=1"
python -m pytest -q tests/test_themes.py tests/test_release_fixes.py
```

The demo uses the same default arc and authored locks as the song build. An
explicit demo transform overrides that default for inspection. Its optional
MIDI lets you audition the themes on their own.

Tests cover stable serialization, changed seeds, take-independent material,
octave shifts, odd-meter grid positions, transform boundaries, invalid inputs,
role selection, and realized pitches reaching bass output. Strict build checks
cover MIDI reproducibility. Golden files capture intentional output changes;
see [the release report](../reviews/2026-09-13-fix-pass-report.md).

## Not yet built

- MIDI motif import or a `source` field.
- Drum patterns stored and realized as `drum_groove` themes.
- Per-section theme selection, theme overrides, or configurable arrangement arcs.
- Chord-relative theme degrees; current degrees are key/mode-relative.
- Per-engine theme routing beyond the active first theme for each role.
- Density, velocity, and register treatment envelopes controlled from YAML.
- Cross-occurrence realization caching.
- Theme extraction, scoring, or selection from an external composition model.
- A two-stage interface for composing a bank, auditioning it, and orchestrating
  a chosen revision. YAML authoring and the demo provide the current workflow.
