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
| `blues-shuffle-lead.yaml` | Blues, A mixolydian, 92 BPM, swung | A 12-bar verse and 8-bar refrain, frequent bend-ins, a leaping contour, and a 12-bar solo that climbs and ends in a whammy dive |
| `country-telecaster-lead.yaml` | Bakersfield country, G major, 132 BPM | The country lick bank: chicken-picked staccato runs and sixth double stops in a traded solo, with a held ending |

## Build

```bash
python produzre_entry.py build examples/lead_gtr/solo/melodic-instrumental-ballad.yaml
```

The export's `analysis/lead_gtr/` folder has the events table and grid.
The build log prints each section's phrase form, for example
`chorus (chorus #2, full): recalled 8 phrase items`.

## Notes

- Every section includes `harmony: {}` so the lead knows the chords.
- The settings used all shape the composed line: `contour_style`,
  `rest_probability`, `vibrato_rate`, `bend_rate`, `dive_rate`,
  `swell_rate`, a numeric `register` range in `params`, and
  `song.arrangement_style` pins (`solo_story`, `solo_ending`,
  `chorus_form`, `lead_fills`, `country_style`). Legacy tuning such as
  `phrase_len_bars` or `resolution_strength` would be ignored.
- Put a numeric register range under `params` (`register: [55, 79]`).
- The hook and licks are drawn from the song seed combined with your local
  project seed, so another project hears different material. In the
  country piece the double stops appear only when the drawn lick bank
  includes a thirds or sixths lick, and only in the solo.
