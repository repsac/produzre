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
walking bass plays a walking line (a quarter note on every beat, stepping
into each chord change) whatever the recipe, density or drum locks. Funk and
metal choices change articulation and activity. Acoustic personas change
picking/strumming behavior, muting, percussion, and expression.

With the composer on (the default), a persona is a starting point, not a
part. Only settings you write yourself count as your choice:

- Drum personas set the composed drummer's touch and timing (jitter,
  velocity variation, push or pull against the beat). Its patterns and
  feel come from the song's drum DNA, so persona fill, hat and voice rates
  and persona swing do not change them. Your own `fill_rate`,
  `hat_density`, `kick_density`, `ghost_rate` and `swing` do.
- Lead personas set phrase length, contour, rests and resolution for the
  classic lead generator. The composed lead is shaped only by the
  `rest_probability` and `contour_style` you set yourself.
- Rhythm guitar personas move the composed comping's timing against the
  beat; its figures, strums and dynamics stay the song's own.

Set `composer: false` on an instrument to hear a persona on its classic
engine. A persona under `instruments` applies to the whole song; a
`persona` on a section's instrument replaces it for that section only. Either
way it is the base layer: recipes, your global instrument params and the
section's own params all win over it.

The actual preset values are in
[produzre/resources/personas](../../produzre/resources/personas).
The [config reference](../../docs/llm-song-config-reference.md) explains their
units and controls. See [shared timing](../../docs/llm-song-config-reference.md#shared-timing)
for swing and [bass controls](../../docs/llm-song-config-reference.md#bass-controls)
for the tight persona's locking defaults.

## Compare the examples

- [bass/persona-tight.yaml](bass/persona-tight.yaml): the tight baseline for the pocket and walking comparisons, over drums.
- [bass/persona-pocket.yaml](bass/persona-pocket.yaml): `persona: pocket`, a few milliseconds behind the beat; key, tempo, seed, drums and progression match.
- [bass/persona-walking.yaml](bass/persona-walking.yaml): `persona: walking`, a walking quarter-note line over the same E dorian progression and seed.
- [drums/persona-tight.yaml](drums/persona-tight.yaml), [drums/persona-rock.yaml](drums/persona-rock.yaml), [drums/persona-jazz-lite.yaml](drums/persona-jazz-lite.yaml): the same composed drummer and band with three drum personas; the hits match and the timing and velocity differ (tight on the grid, rock about 5 ms ahead, jazz-lite about 20 ms ahead with the widest spread).

```bash
for file in examples/personas/drums/*.yaml examples/personas/bass/*.yaml; do
  python produzre_entry.py build "$file"
done
```

Keep the same sound patch while comparing personas so you can hear the
performance changes.
