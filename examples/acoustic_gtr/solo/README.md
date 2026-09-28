# Solo acoustic guitar

Full pieces for acoustic guitar alone, from composed fingerstyle to the
engine's strumming, hybrid and percussive techniques.

| File | Style | What plays it | What it shows |
|---|---|---|---|
| `fingerpicked-folk-song.yaml` | Country-folk, A major (G shapes, capo 2), 4/4, 100 BPM | Composed fingerstyle | Per-piece picking DNA (thumb style, right-hand figures), a capo, a top-voice melody over an independent Travis thumb, a second figure and higher melody in the chorus, a closing held bar |
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
comes from the song seed. Every example uses the shared `produzre-examples`
project, so the thumb style and figures described in each header are the
ones everyone hears; the same song in your own project draws its own.

An explicit `picking_pattern` or another technique keeps the acoustic
engine, which is what `strum-and-slap-acoustic.yaml` uses to show all of
its techniques in one song.

## Capo and shapes

A `capo` changes the chord shapes, not the key: the thumb, inner voice and
melody all sound in the song's key, over shapes fingered above the capo.
The folk song is in A and fingers G, C and D shapes with `capo: 2`, the
usual folk way to keep open-string ring in a key the open shapes do not
cover. Barre shapes sit at their lowest position on the neck, and picked
melodies stay at or below A5, so `voicing_style: barre` works with any
picking pattern. These pieces leave `voicing_style` to the persona: the
default natural persona prefers open shapes, and the percussive persona's
`auto` also picks an open shape when one exists.
