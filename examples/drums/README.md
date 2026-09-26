# Drum examples

Build a demo and assign a General MIDI drum kit to channel 10 in your DAW:

```bash
python produzre_entry.py build examples/drums/fills-demo.yaml
```

The drums are composed by default: each song draws its own drummer (kick
patterns, a groove per section type, ghost notes, fills, crash habits and
a feel) and the band locks to it. The build log prints the drummer and
what it plays in each section. [PERFORMANCE.md](PERFORMANCE.md) explains
what you can shape and what belongs to the classic engine.

## The composed drummer

Most demos play with a bass and rhythm guitar, as a band drummer would.

- [groove-shaping-demo.yaml](groove-shaping-demo.yaml): the four drum settings the composed drummer honors, one per verse: `ghost_rate`, `kick_density`, `hat_density` (and `fill_rate`).
- [fills-demo.yaml](fills-demo.yaml): `fill_rate` 0, 0.2, 0.6 and 0.9 over the same verse.
- [phrasing-demo.yaml](phrasing-demo.yaml): where phrase fills land in 8, 6 and 12-bar sections, in 6/8 and in 7/8. Notes: [PHRASING.md](PHRASING.md).
- [section-types-demo.yaml](section-types-demo.yaml): the groove changes per section type, intro to outro.
- [transitions-demo.yaml](transitions-demo.yaml): a riff-alone intro, walk-ups, stop-time into every chorus, and a cold ending, pinned with `song.arrangement_style`. Notes: [TRANSITIONS.md](TRANSITIONS.md).
- [transitions/](transitions/): five short songs, one per `into_chorus` value (`stop`, `build`, `fill`, `push`, `drop`), with the same band.
- [take-demo.yaml](take-demo.yaml): `song.take` for a new performance of the same parts, and a drum `seed` for a new drummer.
- [solo/](solo/): the drums on their own, as a feature.

## The classic engine

Part selectors hand a section to the classic drum engine: `composer: false`,
`voices`, `recipe`, `pattern`, `riff_accent_rate`, a section `intent`, or a
`drum_groove` theme.

- [classic-engine-demo.yaml](classic-engine-demo.yaml): `composer: false` with the engine-only knobs: chokes, flams and drags, `fill_length`, `phrase_len_bars`, `phrase_end_emphasis`, `fill_chatter`, `pickup_rate`, `downbeat_rate`, and section `energy`.
- [bridge-demo.yaml](bridge-demo.yaml): the five section intents (`drop`, `half_time`, `build`, `open`, `stomp`) between composed sections.
- [hats-demo.yaml](hats-demo.yaml): open and pedal hat rates 1.0 against 0.5, with different placements and accent boosts.
- [kick-demo.yaml](kick-demo.yaml): `double.rate` 0, 1.0 and 0.3 alongside different syncopated kick placements.
- [snare-demo.yaml](snare-demo.yaml): cross-stick, rimshot and normal snare with ghost rates 0.3, 0.15 and 0.5.
- [cymbals-demo.yaml](cymbals-demo.yaml): a ride chorus with `bell_rate: 0.3`, splash and china additions, and an outro crash on beat 1.
- [toms-demo.yaml](toms-demo.yaml): `groove.rate: 0.2` against `fills.rate: 0.8`, then groove and fill toms together at 0.4 and 0.5.

Kit-voice controls go under `drums.voices`. Placements count quarter notes
from 1 within a bar: `2&` means 1.5 beats after the bar starts. In 6/8, the
fourth eighth note is also placement `2&`.

```yaml
# Inside an instruments block (this selects the classic engine):
drums:
  voices:
    snare:
      ghosts: {rate: 0.3, placements: ["2a", "4e"]}
      articulation: {default: crossstick}
    hats:
      open: {rate: 0.25, placements: ["4&"]}
      pedal: {rate: 0.4, placements: ["2", "4"]}
```

Physical constraints may remove a requested hit, such as a third hand
strike or a pedal hat during dense kicks. See the
[drum reference](../../docs/llm-song-config-reference.md#drum-controls) for
every voice control and the
[shared timing reference](../../docs/llm-song-config-reference.md#shared-timing)
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
The [output guide](../../README.md#output-files) defines the TSV columns;
the `kind` column names each hit (`fill`, `snare_ghost`, `crash`,
`snare_pickup`, and so on).

Common GM pitches are kick 35/36, cross-stick 37, snare 38/40, closed hat 42,
open hat 46, pedal hat 44, ride 51, ride bell 53, crash 49, and toms
45/47/50. Grid symbols represent velocity; consult
[grid_format.py](../../produzre/analysis/grid_format.py) for the exact
display thresholds.

## Check a change

```bash
python produzre_entry.py build examples/drums/fills-demo.yaml --strict-determinism
```

This checks repeatability. The drum golden tests build frozen copies under
`tests/fixtures/`, so editing these demos does not change them. Listen to
the MIDI too, and check whether the groove suits the song. See
[testing](../../tests/README.md) for baseline updates.
