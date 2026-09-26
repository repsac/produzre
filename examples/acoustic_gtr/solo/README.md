# Solo acoustic guitar

Full pieces for acoustic guitar alone, from composed fingerstyle to the
engine's strumming, hybrid and percussive techniques.

| File | Style | What plays it | What it shows |
|---|---|---|---|
| `fingerpicked-folk-song.yaml` | Country-folk, G major, 4/4, 100 BPM | Composed fingerstyle | Per-piece picking DNA (thumb style, right-hand figure, melody placement), a top-voice melody over an independent thumb, a second figure and higher melody in the chorus, a closing held chord |
| `waltz-fingerstyle-minor.yaml` | Folk waltz, A minor, 3/4, 84 BPM | Composed fingerstyle | The fingerstyle in 3/4, a minor-key melody with the harmonic minor's E major, a relative-major chorus, `melody_amount` and `phrase_variation` per section |
| `strum-and-slap-acoustic.yaml` | Pop, E minor, 4/4, 112 BPM | Acoustic engine | Every technique: `roll`, `travis` and `cinematic` picking patterns, hybrid picking and strumming, full strumming with muted chucks, and a percussive breakdown with body taps |

## Build

```bash
python produzre_entry.py build examples/acoustic_gtr/solo/fingerpicked-folk-song.yaml
```

The export's `analysis/acoustic_gtr/` folder has the events table (the
`kind` column separates thumb, inner voice and melody notes), a grid and
tablature.

## What decides the part

When the acoustic guitar is the only instrument in a section (besides
`harmony: {}`), its technique is `fingerpicking`, and no `picking_pattern`,
`recipe` or authored melody theme is set, the composed fingerstyle plays
it. The two fingerstyle pieces set `technique: fingerpicking` for every
section, because choruses otherwise default to strumming. The picking DNA
comes from the song seed combined with your local project seed, so the
thumb style you hear can differ from another project's.

An explicit `picking_pattern` or another technique keeps the acoustic
engine, which is what `strum-and-slap-acoustic.yaml` uses to show all of
its techniques in one song.

## Known limits

- `capo` does not transpose the composed fingerstyle correctly (the thumb,
  inner voice and melody move by different amounts), so these pieces do
  not use it.
- `voicing_style: barre` with a picked melody can push the melody above the
  guitar's range; the cinematic bridge uses open shapes instead.
