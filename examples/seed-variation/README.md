# Seed and variation comparisons

These five configs use the same arrangement with targeted seed or variation
changes. They share a title, so use each build's export folder to tell them apart.

| File | Main override | Expected scope |
|---|---|---|
| [base-song.yaml](base-song.yaml) | None | Reference performance. |
| [section-seed-override.yaml](section-seed-override.yaml) | Chorus `seed: 999` | Chorus engine RNG streams. |
| [section-variation.yaml](section-variation.yaml) | Chorus `variation: 0.6` | Chorus performance choices. |
| [instrument-seed-override.yaml](instrument-seed-override.yaml) | Chorus drums `seed: 777` | Drum RNG stream, then any parts that listen to drums. |
| [instrument-variation.yaml](instrument-variation.yaml) | Chorus drums `variation: 0.8` | Drum performance choices, then dependent parts. |

Build them from the repository root:

```bash
for file in examples/seed-variation/*.yaml; do
  python produzre_entry.py build "$file"
done
```

Use each build's printed export root to locate its MIDI and analysis files.
Compare corresponding chorus sections in a DAW or diff the event TSVs.
Export folders include timestamps, so use the path printed by each build.

See [DETERMINISM.md](../../DETERMINISM.md) for the seed hierarchy, preserved
theme material, and how one instrument's changes can affect another.
