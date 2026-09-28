# Solo lead guitar

Full instrumental pieces for one electric lead guitar with no band. A lone
enabled lead defaults to `foreground: full`, so the composer treats it as
the singer: it writes a hook, an answer, a verse idea, a bridge idea and
signature licks from one song DNA, and shapes every section with a phrase
form (verse period, prechorus climb, chorus hook lines, solo story, outro
hook and held tonic).

| File | Style | What it shows |
|---|---|---|
| `melodic-instrumental-ballad.yaml` | Soft rock ballad, D major, 72 BPM | A singing melody with a stepwise contour, vibrato and volume swells, a returning chorus, and a final chorus modulated up a whole step |
| `blues-shuffle-lead.yaml` | Blues, A mixolydian, 92 BPM, swung | A 12-bar verse and 8-bar refrain, frequent bend-ins, a leaping contour, and a 12-bar solo told as a blues (`solo_story: blues`): call and response in the signature licks, ending on a held note |
| `country-telecaster-lead.yaml` | Bakersfield country, G major, 132 BPM | The country lick bank: chicken-picked staccato fills with a sixth double stop answering the melody in verses and choruses, and a traded solo with a held ending |

## Build

```bash
python produzre_entry.py build examples/lead_gtr/solo/melodic-instrumental-ballad.yaml
```

The export's `analysis/lead_gtr/` folder has the events table and grid.
The build log prints each section's phrase form, for example
`chorus (chorus #2, full): recalled 8 phrase items`.

## Notes

- Every section includes `harmony: {}` so the lead knows the chords.
- The settings used all shape the composed line: `register`, `contour_style`,
  `rest_probability`, `vibrato_rate`, `bend_rate`, `dive_rate`,
  `swell_rate`, and `song.arrangement_style` pins (`solo_story`,
  `solo_ending`, `chorus_form`, `lead_fills`, `country_style`). Legacy
  tuning such as `phrase_len_bars` or `resolution_strength` would be
  ignored.
- A numeric register range (`register: [55, 79]`) is a hard MIDI range. Set
  it on the instrument, as these pieces do, or under `params`.
- `bend_rate` 0.15 plays the composed bends as written; lower keeps a share
  of them, higher also bends other notes of half a beat or longer (the
  blues piece uses 0.45).
- A country lead answers its own melody with the song's licks at phrase
  ends, in verses and choruses, and plays double stops when the drawn lick
  bank has a thirds or sixths lick.
- Every example uses the shared `produzre-examples` project, so the hook
  and licks described in each header are the ones everyone hears. The same
  song in your own project draws different material; a lead `seed`
  re-rolls the lead's verse and bridge ideas, licks and phrase choices
  while the hook stays the song's.
