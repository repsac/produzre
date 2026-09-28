# Song examples

Start with [songs/](songs/README.md) to hear what Produzre writes: twelve
complete songs across genres and meters. Then pick a genre or an instrument.
Run commands from the repository root:

```bash
python produzre_entry.py build examples/songs/iron-horse-road.yaml
python produzre_entry.py build examples/genres/country/country.yaml
python produzre_entry.py build examples/drums/solo/rock-drum-feature.yaml
```

The build log prints the export directory. Open its full-song MIDI in a DAW
and play it. The [root README](../README.md#output-files) describes the output files.

Every example sets `project: produzre-examples` in its `song:` block. That is
a built-in project with a fixed seed, so every build of an example produces
the same MIDI on every machine, and the drummer, picking figure or lick bank a
header describes is the one you hear. To hear your own project's take on an
example, copy it and change or remove `song.project`.

## Find an example

| Directory or file | What to try |
|---|---|
| [songs](songs/README.md) | Twelve complete songs with their own genre, meter and band: riff rock, an instrumental anthem, pop, funk, honky-tonk, a country waltz, reggae, a jazz waltz, folk, 12/8 blues, 7/8 prog and metal. |
| [genres](genres/README.md) | One complete, current song for each of 30 genres, plus a mashup that changes genre section by section. |
| [composer](composer/) | The composer showcases: `band_with_singer.yaml` plays around a singer, `instrumental_anthem.yaml` makes the lead the melody, `funk_instrumental.yaml` shows two-bar grooves. |
| [drums](drums/README.md) | The composed drummer's feel knobs, fills, phrasing, section types and into-chorus devices ([transitions/](drums/transitions/)); kit voices on the classic engine; [solo drum pieces](drums/solo/README.md). |
| [bass](bass/README.md) | Articulation, walking, drum locking, fills, slap and grooves on the bass engine; [solo bass pieces](bass/solo/README.md). |
| [rhythm_gtr](rhythm_gtr/README.md) | Composed comping feel, the signature riff, and the classic pattern engine. |
| [lead_gtr](lead_gtr/README.md) | Foreground, density, expression, solo stories and lead styles; [solo lead pieces](lead_gtr/solo/README.md). |
| [acoustic_gtr](acoustic_gtr/README.md) | Picking, strumming and percussion; [solo acoustic pieces](acoustic_gtr/solo/README.md), including composed fingerstyle. |
| [orchestration](orchestration/README.md) | Bass, drums and guitar locking together. |
| [personas](personas/README.md) | Instrument character presets for timing and touch. |
| [seed-variation](seed-variation/README.md) | Takes, section and instrument seed overrides. |
| [themes_demo.yaml](themes_demo.yaml), [theme_showcase.yaml](theme_showcase.yaml) | Authored riffs and melodies with explicit bass, drum and rhythm-guitar coupling. |
| [seed-variation-basic.yaml](seed-variation-basic.yaml), [seed-variation-advanced.yaml](seed-variation-advanced.yaml) | Song-level seed settings. |
| [minimal.yaml](minimal.yaml), [tiny.yaml](tiny.yaml) | The smallest configs, for quick checks. |

Every instrument folder keeps one explicit classic-engine demo
(`composer: false`) for the older generators' knobs. Everything else uses
settings the current composer honors.

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
python produzre_entry.py build examples/songs/iron-horse-road.yaml --strict-determinism
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
