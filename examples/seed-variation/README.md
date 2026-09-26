# Seed and take comparisons

These four configs are the same song with one targeted change each. They
share the song seed on purpose, so only the named change differs; each has
its own title, so their exports are easy to tell apart.

| File | Change | What changes in the build |
|---|---|---|
| [base-song.yaml](base-song.yaml) | None | Reference performance. |
| [section-seed-override.yaml](section-seed-override.yaml) | Chorus `seed: 999` | The chorus drummer and rhythm guitar figures are re-rolled and the bass follows; the last bar of each verse, which leads into the chorus, changes too. |
| [instrument-seed-override.yaml](instrument-seed-override.yaml) | Chorus drums `seed: 777` | A different drummer in the chorus only; the other parts keep their notes. |
| [song-take.yaml](song-take.yaml) | `take: 1` | The same parts with new timing and velocity humanization. |

Build them from the repository root:

```bash
for file in examples/seed-variation/*.yaml; do
  python produzre_entry.py build "$file"
done
```

Use each build's printed export root to locate its MIDI and analysis files,
then compare corresponding sections in a DAW or diff the event TSVs.

A `seed` on an instrument or section re-rolls the composed drummer and the
rhythm guitar's figures. The composed lead is written from the song seed,
so a lead `seed` changes only its humanization. `variation` does not change
composed parts; only some classic engines read it.

See [DETERMINISM.md](../../DETERMINISM.md) for the seed hierarchy, the
per-user project seed that is mixed into every song seed, preserved theme
material, and how one instrument's changes can affect another.
