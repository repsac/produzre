# Song examples

Start with [minimal.yaml](minimal.yaml) for one short section, or
[rock-simple.yaml](genres/rock/rock-simple.yaml) for a recipe-based arrangement.
Run commands from the repository root:

```bash
python produzre_entry.py build examples/minimal.yaml
python produzre_entry.py build examples/genres/rock/rock-full-arrangement.yaml
```

The build log prints the export directory. Open its full-song MIDI in a DAW
and play it. The [root README](../README.md#output-files) describes the output files.

## Find an example

| Directory or file | What to try |
|---|---|
| [genres](genres/README.md) | Short songs, longer arrangements, and recipe comparisons across 30 genres, plus a mashup. |
| [bass](bass/README.md) | Articulation, walking, drum locking, fills, slap, and solos. |
| [drums](drums/README.md) | Kit voices, ghosts, fills, transitions, and timing. |
| [rhythm_gtr](rhythm_gtr/README.md) | Strum accents and sustained chords. |
| [lead_gtr](lead_gtr/README.md) | Phrase length, contour, rests, and resolution. |
| [acoustic_gtr](acoustic_gtr/README.md) | Picking, strumming, and percussion. |
| [orchestration](orchestration/README.md) | Bass and drums playing together. |
| [personas](personas/README.md) | Instrument character presets. |
| [seed-variation](seed-variation/README.md) | Section and instrument seed overrides. |
| [themes_demo.yaml](themes_demo.yaml) | An authored riff and melody with explicit bass, drum, and rhythm-guitar coupling. |
| [seed-variation-basic.yaml](seed-variation-basic.yaml), [seed-variation-advanced.yaml](seed-variation-advanced.yaml) | Song-level seed and variation settings. |
| [tiny.yaml](tiny.yaml) | A small config for quick checks. |

## Change one thing at a time

Copy an example and change its key, tempo, section order, or instrument list.
See the [file structure](../docs/llm-song-config-reference.md#file-structure)
and [preset order](../docs/llm-song-config-reference.md#recipes-and-personas)
when changing the instrument list or genre.

The [config reference](../docs/llm-song-config-reference.md) lists the complete
schema, parameter ranges, and defaults. It also explains section types,
intensity, themes, timing, and custom engine registration. Avoid copying
controls between engines without checking that reference.

## Check a config

```bash
python produzre_entry.py validate examples/minimal.yaml
python produzre_entry.py show-config examples/minimal.yaml --format json
python produzre_entry.py build examples/minimal.yaml --dry-run -v
python produzre_entry.py build examples/themes_demo.yaml --strict-determinism
```

A dry run checks loading, planning, and rendering without writing exports.
For strict determinism checks and seed controls, see [DETERMINISM.md](../DETERMINISM.md).

To check every example in Bash:

```bash
find examples -name '*.yaml' -print0 | while IFS= read -r -d '' file; do
  python produzre_entry.py build "$file" --dry-run || exit 1
done
```

If a track is silent, check that it is enabled and listed in the section.
For a missing dependency error, check the [required instrument setup](../docs/llm-song-config-reference.md#file-structure).
Use `-v` to inspect recipe selection and rendering decisions.
