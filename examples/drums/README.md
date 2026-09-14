# Drum examples

Build a demo and assign a General MIDI drum kit to channel 10 in your DAW:

```bash
python produzre_entry.py build examples/drums/hats-demo.yaml -v
```

## Choose a demo

### Kit voices

- [hats-demo.yaml](hats-demo.yaml): compare open and pedal hat rates 1.0 with 0.5, plus different placements and accent boosts.
- [kick-demo.yaml](kick-demo.yaml): compare `double.rate` 0, 1.0, and 0.3 alongside different syncopated kick placements.
- [snare-demo.yaml](snare-demo.yaml): hear crossstick, rimshot, and normal snare with ghost rates 0.3, 0.15, and 0.5.

### Fills and transitions

- [fills-demo.yaml](fills-demo.yaml): compare `fill_rate` 0 with 1.0, then short, medium, and long fills and `fill_chatter: 0.4`.
- [transitions-demo.yaml](transitions-demo.yaml): compare `pickup_rate: 0.7` with 0 and `downbeat_rate: 0.8` with 0 around section changes.
- [phrasing-demo.yaml](phrasing-demo.yaml): compare two-bar and four-bar phrase endings, a six-bar section, and a final 6/8 section.
- [performance-demo.yaml](performance-demo.yaml): hear chokes, flams, and drags separately, then combined; the first section sets all three rates to 0.

### Arrangement and color

- [energy-demo.yaml](energy-demo.yaml): compare automatic energy with forced `low`, `high`, and numeric 0.75 while also changing section intensity.
- [cymbals-demo.yaml](cymbals-demo.yaml): hear a ride chorus with `bell_rate: 0.3`, splash/china additions, and an outro crash on beat 1.
- [toms-demo.yaml](toms-demo.yaml): compare `groove.rate: 0.2` with `fills.rate: 0.8`, then combine groove and fill toms at 0.4 and 0.5.
- [take-demo.yaml](take-demo.yaml): start at `take: 0`, then rebuild with `take: 1` to compare a new performance of the repeated verse and chorus.
- [bridge-demo.yaml](bridge-demo.yaml): compare `drop`, `half_time`, `build`, `open`, and `stomp` intents through contrasting sections.

## Change the kit part

Voice controls go under `drums.voices`. Placements count quarter notes from 1
within a bar: `2&` means 1.5 beats after the bar starts. In 6/8, the fourth
eighth note is also placement `2&`. The engine uses quarter-note beat units
for every meter.

```yaml
# Inside an instruments block:
drums:
  voices:
    snare:
      ghosts: {rate: 0.3, placements: ["2a", "4e"]}
      articulation: {default: crossstick}
    hats:
      open: {rate: 0.25, placements: ["4&"]}
      pedal: {rate: 0.4, placements: ["2", "4"]}
  params:
    fill_rate: 0.2
```

Recipes can set voices too; see [preset order](../../docs/llm-song-config-reference.md#recipes-and-personas).
Energy supplies values only when a recipe
or user setting leaves them open. Physical constraints may remove an otherwise
requested hit, such as a third hand strike or a pedal hat during dense kicks.

See the [drum reference](../../docs/llm-song-config-reference.md#drum-controls)
for every voice control and the [shared timing reference](../../docs/llm-song-config-reference.md#shared-timing)
for swing and pocket units.

## Inspect the output

The build log prints the export root. Drum files are below it:

```text
<Song>.mid
instruments/drums/<Song>_drums.mid
analysis/drums/<Song>_drums.events.tsv
analysis/drums/<Song>_drums.grid.txt
```

Enable text views through `exports.midi_text`.
The [output guide](../../README.md#output-files) defines the TSV columns.
The grid shows the voices that played in this groove.

Common GM pitches are kick 35/36, crossstick 37, snare 38/40, closed hat 42,
open hat 46, pedal hat 44, ride 51, crash 49, and toms 45/47/50. Grid symbols
represent velocity; consult [grid_format.py](../../produzre/analysis/grid_format.py)
for the exact display thresholds.

## Check a change

```bash
python produzre_entry.py build examples/drums/hats-demo.yaml --strict-determinism
python tests/test_golden_drums.py
```

The first command checks repeatability. The second checks the three saved
hats, kick, and fill outputs. Listen to the MIDI too, and check whether
the groove suits the song. See [testing](../../tests/README.md) for baseline updates.
