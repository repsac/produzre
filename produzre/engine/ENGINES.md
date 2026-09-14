# Writing an engine

An engine is a Python module that adds notes to an instrument timeline. Register
it in YAML; the orchestrator handles loading, planning order, dependencies,
rendering, and export. The built-in [arpeggiator](arpeggiator/__init__.py) is a
small example.

## Registration

Add an entry to the song's top-level `engines` block, or to a user engine registry:

```yaml
engines:
  synth_pad:
    engine: my_package.engines.synth_pad
    priority: 5
    channel: 5
    program: 89
    enabled: true
    requires: [harmony.plan]
    provides: []
    roles: [pad, texture]
```

Install the module in the Python environment that runs Produzre so the loader can import it. A
leading dot, as in `.engine.arpeggiator`, means relative to `produzre`.
Built-in entries live in [resources/engines.yml](../resources/engines.yml).
A song entry can override individual registry fields, such as a channel or program.

| Field | Meaning |
|---|---|
| `engine` | Python module containing `render_into_timeline`. |
| `priority` | Ascending execution order. Ties retain section instrument order. |
| `channel` | Zero-based MIDI channel, 0-15. General MIDI drums use 9. |
| `program` | Zero-based MIDI program, 0-127, or null for no program change. |
| `enabled` | Whether this engine can run. |
| `requires` | Plan keys required before the engine's planning/render calls. |
| `provides` | Advertised keys; the engine must actually publish them. |
| `roles` | Role tags; `planning` excludes a planning-only engine from MIDI export. |

Built-in priorities are harmony 0, drums 1, bass 2, rhythm guitar 3, lead and
acoustic guitar 4, and arpeggiator 6. Module constants
`ENGINE_DEFAULT_PRIORITY`, `ENGINE_DEFAULT_CHANNEL`, and
`ENGINE_DEFAULT_PROGRAM` provide fallbacks where the loader uses them.

List the registered engine in each section where you want it to play:

```yaml
sections:
  verse:
    type: verse
    bars: 4
    harmony: {progression: "I V vi IV"}
    instruments:
      harmony: {}
      synth_pad: {intensity: 0.6}
```

## Rendering interface

All arguments arrive by keyword. Accept `**kwargs` so new context fields
don't break your engine. You may use an explicit keyword-only signature or the
`*args, **kwargs` convention and reject positional arguments.

| Argument | Contents |
|---|---|
| `cfg` | Root config, including `song`, engine registry, and raw preset data. |
| `section` | Current planned section occurrence. |
| `instrument_name`, `instrument_cfg` | Engine key and merged global/section settings. |
| `harmony_plan` | Chord slots, or None. Slots use section-relative beats. |
| `rhythm_grid` | Section duration, meter, and subdivisions. |
| `section_start_beat` | Absolute song beat where this occurrence starts. |
| `timeline` | `InstrumentTimeline` to append to. |
| `rng` | Deterministic instrument RNG. |
| `plan` | Shared `PerformancePlan`. |
| `transition_context` | Adjacent section types, energy, and arrangement position. |
| `rhythm_features` | Features already published by rendered instruments. |
| `feedback_collector` | Optional feedback for later sections. |
| `logger` | Build logger. |

Timeline notes use absolute quarter-note beats. Add `section_start_beat` exactly
once. A 7/8 bar has 3.5 beats. Use `rhythm_grid.beats_per_bar`, section meter,
and each chord slot's `start_beat`/`end_beat` instead of assuming four beats.

`instrument_cfg` can contain unset fields such as `intensity=None`. Resolve
instrument intensity, then section intensity, then your engine fallback.
Engine options normally live in `instrument_cfg.extra` after parsing;
`produzre.groove.effective_params_dict` also handles compatible dict forms.
If your engine supports recipes, call `merge_recipe_params`; it preserves
the [preset order](../../docs/llm-song-config-reference.md#recipes-and-personas).

## A working pad renderer

```python
from produzre.melody import chord_pitch_classes

ENGINE_DEFAULT_PRIORITY = 5
ENGINE_DEFAULT_CHANNEL = 5
ENGINE_DEFAULT_PROGRAM = 89


def render_into_timeline(*, cfg, section, instrument_cfg, harmony_plan,
                         section_start_beat, timeline, **kwargs):
    if not harmony_plan:
        return
    intensity = getattr(instrument_cfg, "intensity", None)
    if intensity is None:
        intensity = getattr(section, "intensity", None)
    intensity = 0.5 if intensity is None else intensity
    velocity = max(1, min(127, round(60 + 40 * intensity)))
    key = section.key or cfg.song.key
    mode = section.mode or cfg.song.mode
    for slot in harmony_plan.chord_slots:
        for pc in chord_pitch_classes(slot.numeral, key, mode):
            timeline.add_note(
                start_beat=section_start_beat + slot.start_beat,
                duration_beats=slot.end_beat - slot.start_beat,
                pitch=60 + pc,
                velocity=velocity,
                kind="pad",
            )
```

`add_note` accepts `start_beat`, `duration_beats`, `pitch`, `velocity`, optional
`channel`, and optional `kind`. Omitting channel uses the engine registry's
channel. There is no timeline `add_cc` or `add_program_change` API; set the
program in the registry. A new controller-event model would require exporter
work too.

The orchestrator applies shared feel after pitched engines render, clips notes
to section boundaries, and exports sorted events. Drums apply their timing
internally. Avoid applying shared swing or `push_pull` a second time in a custom
pitched engine. Engine-specific strum spread may still precede that pass.

## Planning interface

`contribute_plan` is optional. All planning hooks finish before the first
engine renders. Hooks run in priority order; a planning dependency must be
published by an earlier hook. Rendering can see every completed hook.
Planning and rendering share the instrument RNG, so draws during planning
affect that engine's later choices.

```python
def contribute_plan(*, plan, section_ctx, rng, logger):
    section = section_ctx["section"]
    grid = section_ctx["rhythm_grid"]
    plan.set(f"synth_pad.intent.{section.id}", {
        "duration_beats": grid.total_beats,
        "role": "pad",
    })
```

`section_ctx` contains `cfg`, `section`, `instrument_name`, `instrument_cfg`,
`harmony_plan`, `rhythm_grid`, `section_start_beat`, `transition_context`, and
`rhythm_features`. Rendered drum features are not yet available during this pass.

`plan.has(key)`, `plan.get(key, default)`, and `plan.set(key, value)` are the main
store operations. `plan.merge` supports `replace`, `extend`, and `deepmerge`
strategies; check [orchestrate/plan.py](../orchestrate/plan.py) for exact names.
Missing required keys raise a dependency error. Add the provider to the section
or adjust priorities. Advertising a key in `provides` does not create its value.

## Shared plan data

| Key | Provider and purpose |
|---|---|
| `harmony.plan` | Harmony's serialized chord slots for the current section. |
| `rhythm.grid`, `rhythm.accents` | Drum planning grid and accent intent. |
| `groove.cues`, `groove.kick_pattern`, `groove.backbeat` | Drum coordination cues. |
| `groove.humanize.<section>` | Final drum timing settings for the shared clock. |
| `ensemble.<section>` | Roles, density multipliers, lead windows, and fill owner. |
| `lead_rest_ratio.<section>` | Lead rest target used by rhythm accompaniment. |
| `melody.guide`, `melody.guide.<section>` | Shared melodic targets, generated before rendering. |
| `themes.bank` | Song-level `ThemeBank`. |
| `themes.realized.<section>` | Active realized notes by role. |
| `themes.realized_by_name.<section>` | Every named theme realization. |
| `bass.foundation`, `bass.line` | Bass planning intent. |
| `rhythm.texture`, `rhythm.chords` | Rhythm-guitar intent for inspection or custom consumers. |
| `arpeggiator.pattern` | Arpeggiator intent. |
| `transitions.map` | Transition directives, indexed by occurrence with compatibility aliases. |
| `suggested_density`, `suggested_energy` | Negotiation suggestions. |

The planner refreshes the global harmony and melody aliases for each section. Keys ending
in a section id describe the current/latest occurrence, not a permanent history
of all repeats. Store occurrence-indexed data separately if your engine needs it.
Intent keys such as `rhythm.texture` currently have no built-in consumer.

Rendered drums return `RhythmFeatures`: kick `strong_beats`, `accent_beats`,
`hat_beats`, `fill_windows`, `silence_windows`, `density_per_bar`, and
`syncopation_beats`. Beats are local to the section. Bass reads these features
for locking and fill avoidance. Renderers can also return negotiation features;
see the bass engine for that interface.

See [drum constraints](../../docs/llm-song-config-reference.md#drum-controls)
for limb limits, fill ducking, and the pedal-hat density threshold.

## Feedback and testing

A renderer can suggest changes for later sections:

```python
collector = kwargs.get("feedback_collector")
if collector is not None:
    collector.add_feedback(
        engine_name="synth_pad", feedback_type="density",
        plan_key="suggested_density", adjustment={"suggested_density": 0.6},
        target_section_id="chorus", priority=0.5,
        reason="Leave room for the hook",
    )
```

Negotiable keys are `transitions.map`, `rhythm.accents`, `suggested_density`, and
`suggested_energy`. The orchestrator collects and applies feedback at section boundaries,
leaving earlier notes in place.

Use the supplied RNG or stable children from [rng.py](../rng.py). Never use
unseeded randomness, and sort unordered inputs before they affect decisions.
See [DETERMINISM.md](../../DETERMINISM.md).

Test a short section, an odd meter, a section boundary, and an unset intensity.
Verify positive durations, pitch/velocity range, dependency behavior, and the
meaning of each control. Then run:

```bash
python produzre_entry.py build my-song.yaml --dry-run -v
python produzre_entry.py build my-song.yaml --strict-determinism
python -m pytest -q
```

The [test guide](../../tests/README.md) explains snapshot updates and release
checks. Audition the exported MIDI too, and check whether the phrase sounds convincing.
