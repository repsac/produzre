# Instruments playing together

[rhythm-lock-demo.yaml](rhythm-lock-demo.yaml) changes bass/drum coordination
across sections. Build it from the repository root:

```bash
python produzre_entry.py build examples/orchestration/rhythm-lock-demo.yaml
```

## Locking and space

See [bass controls](../../docs/llm-song-config-reference.md#bass-controls)
for the difference between added kick locking and the kick-led renderer.

```yaml
# Inside an instruments block:
bass:
  params:
    lock_to_kick: 0.8
    fill_avoid_drums: 0.8
```

Drums render early enough to publish actual onsets, density, and fill windows.
Bass and guitars can use those features. Shared phrase planning also reserves
lead windows and lowers accompaniment activity. Explicit density and rest
settings let you shape that relationship further.

For a quieter backing part under a solo, lower rhythm-guitar `density` and
bass `density`. For a more active lead, lower `rest_probability`; this is the lead's control for leaving gaps. Instrument `intensity` changes dynamics,
while `fill_rate` changes fill activity. Bass `fill_avoid_drums` helps keep
bass fills away from drum fills.

## Themes and transitions

[themes_demo.yaml](../themes_demo.yaml) enables bass, rhythm-guitar, and drum
theme coupling; see [theme controls](../../docs/llm-song-config-reference.md#themes) for their different roles.

Section roles and energy shape entrances, exits, and phrase development.
Repeated sections can develop while preserving the song's themes. See [seed boundaries](../../DETERMINISM.md) for how changes travel between parts.

See the [config reference](../../docs/llm-song-config-reference.md#transitions)
for transition controls, [DETERMINISM.md](../../DETERMINISM.md) for seed
boundaries, and the [engine guide](../../produzre/engine/ENGINES.md) for plan
and feedback APIs.
