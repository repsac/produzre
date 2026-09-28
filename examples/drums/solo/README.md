# Solo drums

Full pieces for the drum kit alone: each has an intro, verses, choruses,
a contrasting section and an outro, so you can hear how the drums carry a
form without any other instrument.

| File | Style | What plays it | What it shows |
|---|---|---|---|
| `rock-drum-feature.yaml` | Rock, 4/4, 124 BPM | Composed drummer | Song drum DNA, a different hand voice per section, the backbeat kept in every bar with tom answers at phrase ends, fills into every chorus, a half-time bridge, a drum solo section and a big ending |
| `six-eight-drums.yaml` | Soft rock ballad, 6/8, 96 BPM | Composed drummer | The two-pulse 6/8 feel (kick on the first dotted quarter, snare on the second) with no harmony needed, a snare build into each chorus, a ringing ending |
| `jazz-ride-kit.yaml` | Jazz swing, 4/4, 144 BPM | Composed jazz drummer | Spang-a-lang ride, hi-hat foot on 2 and 4, feathered kick, soft comping, a different ride figure per section, triplet fills in the drum solo, the `jazz-lite` persona |

## Build

```bash
python produzre_entry.py build examples/drums/solo/rock-drum-feature.yaml
```

The export folder holds the full MIDI, the drum stem and, under
`analysis/drums/`, an events table and a text grid of every bar.

## What decides the part

Unless the drums set `voices`, `recipe`, `pattern` or
`riff_accent_rate`, a section sets `intent`, or a `drum_groove` theme
exists, the composer plays the kit. All three pieces only use settings
that shape the composed drummer (`ghost_rate`, `fill_rate`, a drum
`persona`) and arrangement pins (`song.arrangement_style.into_chorus` and
`ending`). The drummer itself (kick figure, hand voice per section, feel)
is drawn from the song seed. Every example uses the shared
`produzre-examples` project, so every machine builds the same drummer as
the one the header comments describe.

`genre: jazz` gives `jazz-ride-kit.yaml` the composed swing drummer. For
the classic drum engine with every voice authored, see
[classic-engine-demo.yaml](../classic-engine-demo.yaml) and the voice demos
listed in the [drum examples README](../README.md).

## What to listen for

- Rock feature: the prechorus moving to the ride, the fill and crash at
  each chorus entrance, sixteenth-note hats in the chorus, the half-time
  bridge under a washy open hat.
- Six-eight: the lilt of two pulses per bar, tom answers at the phrase
  ends, and the snare build into each chorus.
- Jazz ride kit: the ride's skip note on the swung "and" of 2 and 4, the
  foot chick, the stick on the closed hat in the intro, and the ride
  figure changing in the drum solo and the bridge.

Drums alone keep the backbeat in every bar; the last beat of bars 2 and 4
of each four-bar phrase answers on the toms unless a fill is already
there. Composed drums follow section intensity: a verse plays under a
chorus, and each repeat of a section plays a little harder than the one
before.
