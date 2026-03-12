# Seed & Variation Examples

These 5 files demonstrate granular seed and variation control. They are all
identical copies of the same song with **one change each**, so you can A/B
compare builds.

## Files

| File | Change | What differs in output |
|------|--------|----------------------|
| `base-song.yaml` | None (baseline) | Reference output |
| `section-seed-override.yaml` | `chorus.seed: 999` | All chorus instruments re-rolled |
| `section-variation.yaml` | `chorus.variation: 0.6` | Chorus has variation bias |
| `instrument-seed-override.yaml` | `chorus.drums.seed: 777` | Only chorus drums re-rolled |
| `instrument-variation.yaml` | `chorus.drums.variation: 0.8` | Only chorus drums get variation |

## How to test

Build all 5 and compare:

```bash
for f in examples/seed-variation/*.yaml; do
  produzre build "$f"
done
```

Then compare the MIDI output in your DAW or use the text exports to diff:

```bash
diff exports/Seed\ Variation\ Base/  exports/Seed\ Variation\ Base\ 2/
```

## What to expect

- **Section seed override**: The chorus sounds completely different; intro, verse,
  and outro are identical to the base.
- **Section variation**: The chorus has subtle differences from the base; other
  sections are identical.
- **Instrument seed override**: Only the drums in the chorus change; bass, guitar,
  and all other sections match the base.
- **Instrument variation**: Only the drums in the chorus have variation bias;
  everything else matches the base.
