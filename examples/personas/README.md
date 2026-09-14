# Instrument personas

A persona is a named set of parameter defaults. Choose one for an instrument,
then override the controls you want to hear differently.

```yaml
instruments:
  drums:
    persona: rock
    params:
      fill_rate: 0.2
  bass:
    persona: pocket
    params:
      density: 0.65
```

`params.persona` is also accepted; see [preset order](../../docs/llm-song-config-reference.md#recipes-and-personas)
for section overrides and how recipes combine with personas.

## Available characters

| Instrument | Personas |
|---|---|
| Drums | `tight` (default), `experimental`, `rock`, `metal`, `funk-lite`, `jazz-lite` |
| Bass | `tight` (default), `pocket`, `loose`, `funk`, `metal`, `walking`, `dub` |
| Rhythm guitar | `tight` (default), `loose`, `aggressive`, `funky`, `jangly` |
| Lead guitar | `balanced` (default), `melodic`, `shredder`, `bluesy`, `ambient` |
| Acoustic guitar | `natural` (default), `precise`, `expressive`, `percussive`, `delicate` |

Tight players use restrained timing variation. Pocket and dub bass sit later;
walking bass favors continuous chord movement. Funk and metal choices change
articulation and activity. Lead personas change phrase length, contour,
resolution, and rests. Acoustic personas change picking/strumming behavior,
muting, percussion, and expression.

The actual preset values are in
[produzre/resources/personas](../../produzre/resources/personas).
The [config reference](../../docs/llm-song-config-reference.md) explains their
units and controls. See [shared timing](../../docs/llm-song-config-reference.md#shared-timing)
for swing and [bass controls](../../docs/llm-song-config-reference.md#bass-controls)
for the tight persona's locking defaults.

## Compare the examples

- [bass/persona-pocket.yaml](bass/persona-pocket.yaml): compare `persona: pocket` with `tight`; key, tempo, seed, intensity, and progression are identical.
- [bass/persona-tight.yaml](bass/persona-tight.yaml): hear the tight baseline for the pocket and walking comparisons.
- [bass/persona-walking.yaml](bass/persona-walking.yaml): compare `persona: walking` with `tight` over the same E dorian progression and seed.
- [drums/persona-demo.yaml](drums/persona-demo.yaml): hear six drum personas, then a rock override with `swing: 0.25` and `fill_rate: 0.8`; section intensity changes too.

```bash
for file in examples/personas/drums/*.yaml examples/personas/bass/*.yaml; do
  python produzre_entry.py build "$file"
done
```

Keep the same sound patch while comparing personas so you can hear the
performance changes.
