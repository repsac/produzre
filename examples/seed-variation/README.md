# Seed and take comparisons

These four configs are the same song with one targeted change each. They
share the song seed on purpose, so only the named change differs; each has
its own title, so their exports are easy to tell apart.

| File | Change | What changes in the build |
|---|---|---|
| [base-song.yaml](base-song.yaml) | None | Reference performance. |
| [section-seed-override.yaml](section-seed-override.yaml) | Chorus `seed: 999` | The chorus drummer, bass line and rhythm guitar figures are re-rolled in both choruses; the other sections keep their notes. |
| [instrument-seed-override.yaml](instrument-seed-override.yaml) | Chorus drums `seed: 777` | A different drummer in the chorus only; the other parts keep their notes (the chorus bass velocities follow the new drummer's accents). |
| [song-take.yaml](song-take.yaml) | `take: 1` | The same parts with new velocities; only the intro pickup and a few bass and strum details change. |

Build them from the repository root:

```bash
for file in examples/seed-variation/*.yaml; do
  python produzre_entry.py build "$file"
done
```

Use each build's printed export root to locate its MIDI and analysis files,
then compare corresponding sections in a DAW or diff the event TSVs.

A section `seed` re-rolls that section's composed parts (drummer, bass line,
rhythm guitar figures, lead). An instrument `seed` re-rolls only that part in
that section and wins over the section seed; a lead `seed` re-rolls the
composed lead, while the song's hook stays, since it belongs to the song.
`variation` does not change composed parts; only some classic engines read
it.

Every example uses the shared `produzre-examples` project, which has the same
seed on every machine, so these builds and the differences described above
are the same for everyone. See [DETERMINISM.md](../../DETERMINISM.md) for the
seed hierarchy, projects, preserved theme material, and how one
instrument's changes can affect another.
