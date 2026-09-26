# Solo drums

Full pieces for the drum kit alone: each has an intro, verses, choruses,
a contrasting section and an outro, so you can hear how the drums carry a
form without any other instrument.

| File | Style | What plays it | What it shows |
|---|---|---|---|
| `rock-drum-feature.yaml` | Rock, 4/4, 124 BPM | Composed drummer | Song drum DNA, a different hand voice per section, tom answers in bars 2 and 4 of each phrase, fills into every chorus, a half-time bridge, a drum solo section and a big ending |
| `six-eight-drums.yaml` | Soft rock ballad, 6/8, 96 BPM | Composed drummer | The two-pulse 6/8 feel (kick on the first dotted quarter, snare on the second), build fills into the choruses, a ringing ending |
| `jazz-ride-kit.yaml` | Jazz swing, 4/4, 144 BPM | Classic drum engine | Every voice authored: spang-a-lang ride placements, hi-hat foot on 2 and 4, cross-stick against full snare, ghost-note placements, tom grooves, flams and drags in the drum solo |

## Build

```bash
python produzre_entry.py build examples/drums/solo/rock-drum-feature.yaml
```

The export folder holds the full MIDI, the drum stem and, under
`analysis/drums/`, an events table and a text grid of every bar.

## What decides the part

Unless the drums set `voices`, `recipe`, `pattern` or
`riff_accent_rate`, a section sets `intent`, or a `drum_groove` theme
exists, the composer plays the kit. The two composed pieces only use
settings that shape the composed drummer (`ghost_rate`, `fill_rate`) and
arrangement pins (`song.arrangement_style.into_chorus` and `ending`).
The drummer itself (kick figure, hand voice per section, feel) is drawn
from the song seed combined with your local project seed, so another
project can hear a different drummer than the one described in the
header comments.

`jazz-ride-kit.yaml` is a classic-engine demo: `composer: false` and the
explicit `voices` blocks keep the older drum engine so every placement is
heard exactly as written. Voice blocks go directly under the drums
instrument, not inside `params`.

## What to listen for

- Rock feature: the prechorus moving to the ride, the fill and crash at
  each chorus entrance, sixteenth-note hats in the chorus, the half-time
  bridge on the hi-hat foot.
- Six-eight: the lilt of two pulses per bar, and tom answers turning each
  phrase.
- Jazz ride kit: the ride's skip note on the swung "and" of 2 and 4, the
  foot chick, and the change from cross-stick in the head to full snare in
  the strain.

Composed drums keep the same velocity scale in every section: section and
instrument `intensity` do not change how hard the composed drummer plays,
so the dynamic shape comes from the hand voice, fills and crashes rather
than from loudness.
