# Genre examples

There are 30 genre directories and one cross-genre mashup directory. Start
with a `simple` file to hear the basic arrangement. Use a `full` or named
arrangement for more sections. A `recipe-showcase` file demonstrates genre
selection with instrument and section overrides.

Blues, rock, funk, jazz, and metal have four files each. The other genres have
three. File names, keys, and tempos below come from the checked-in configs.
See [recipes and personas](../../docs/llm-song-config-reference.md#recipes-and-personas)
for how a genre selects defaults.

```bash
python produzre_entry.py build examples/genres/blues/blues-simple.yaml
python produzre_entry.py build examples/genres/rock/rock-full-arrangement.yaml
```

## Browse the songs

| File | Key | BPM |
|---|---|---|
| [alt_rock/alt-rock-full.yaml](alt_rock/alt-rock-full.yaml) | B | 132 |
| [alt_rock/alt-rock-recipe-showcase.yaml](alt_rock/alt-rock-recipe-showcase.yaml) | D | 130 |
| [alt_rock/alt-rock-simple.yaml](alt_rock/alt-rock-simple.yaml) | E | 128 |
| [arena_rock/arena-rock-full.yaml](arena_rock/arena-rock-full.yaml) | E | 136 |
| [arena_rock/arena-rock-recipe-showcase.yaml](arena_rock/arena-rock-recipe-showcase.yaml) | E | 132 |
| [arena_rock/arena-rock-simple.yaml](arena_rock/arena-rock-simple.yaml) | A | 130 |
| [blues/blues-12bar.yaml](blues/blues-12bar.yaml) | G | 88 |
| [blues/blues-recipe-showcase.yaml](blues/blues-recipe-showcase.yaml) | G | 88 |
| [blues/blues-shuffle.yaml](blues/blues-shuffle.yaml) | A | 85 |
| [blues/blues-simple.yaml](blues/blues-simple.yaml) | E | 90 |
| [blues_rock/blues-rock-full.yaml](blues_rock/blues-rock-full.yaml) | G | 115 |
| [blues_rock/blues-rock-recipe-showcase.yaml](blues_rock/blues-rock-recipe-showcase.yaml) | A | 130 |
| [blues_rock/blues-rock-simple.yaml](blues_rock/blues-rock-simple.yaml) | A | 110 |
| [classical/classical-full.yaml](classical/classical-full.yaml) | D | 75 |
| [classical/classical-recipe-showcase.yaml](classical/classical-recipe-showcase.yaml) | C | 72 |
| [classical/classical-simple.yaml](classical/classical-simple.yaml) | C | 80 |
| [country/country-full.yaml](country/country-full.yaml) | C | 115 |
| [country/country-recipe-showcase.yaml](country/country-recipe-showcase.yaml) | G | 110 |
| [country/country-simple.yaml](country/country-simple.yaml) | G | 110 |
| [dance_pop/dance-pop-full.yaml](dance_pop/dance-pop-full.yaml) | Bb | 128 |
| [dance_pop/dance-pop-recipe-showcase.yaml](dance_pop/dance-pop-recipe-showcase.yaml) | C | 122 |
| [dance_pop/dance-pop-simple.yaml](dance_pop/dance-pop-simple.yaml) | Ab | 125 |
| [electronic/electronic-full.yaml](electronic/electronic-full.yaml) | C | 128 |
| [electronic/electronic-recipe-showcase.yaml](electronic/electronic-recipe-showcase.yaml) | D | 128 |
| [electronic/electronic-simple.yaml](electronic/electronic-simple.yaml) | A | 130 |
| [emo/emo-full.yaml](emo/emo-full.yaml) | D | 155 |
| [emo/emo-recipe-showcase.yaml](emo/emo-recipe-showcase.yaml) | C | 155 |
| [emo/emo-simple.yaml](emo/emo-simple.yaml) | G | 160 |
| [folk/folk-full.yaml](folk/folk-full.yaml) | D | 100 |
| [folk/folk-recipe-showcase.yaml](folk/folk-recipe-showcase.yaml) | G | 105 |
| [folk/folk-simple.yaml](folk/folk-simple.yaml) | G | 95 |
| [funk/funk-breakdown.yaml](funk/funk-breakdown.yaml) | F | 108 |
| [funk/funk-groove.yaml](funk/funk-groove.yaml) | E | 105 |
| [funk/funk-recipe-showcase.yaml](funk/funk-recipe-showcase.yaml) | E | 100 |
| [funk/funk-simple.yaml](funk/funk-simple.yaml) | D | 110 |
| [gospel/gospel-full.yaml](gospel/gospel-full.yaml) | G | 105 |
| [gospel/gospel-recipe-showcase.yaml](gospel/gospel-recipe-showcase.yaml) | Bb | 95 |
| [gospel/gospel-simple.yaml](gospel/gospel-simple.yaml) | C | 100 |
| [grunge/grunge-full.yaml](grunge/grunge-full.yaml) | C# | 120 |
| [grunge/grunge-recipe-showcase.yaml](grunge/grunge-recipe-showcase.yaml) | E | 118 |
| [grunge/grunge-simple.yaml](grunge/grunge-simple.yaml) | E | 115 |
| [hard_rock/hard-rock-full.yaml](hard_rock/hard-rock-full.yaml) | A | 145 |
| [hard_rock/hard-rock-recipe-showcase.yaml](hard_rock/hard-rock-recipe-showcase.yaml) | A | 140 |
| [hard_rock/hard-rock-simple.yaml](hard_rock/hard-rock-simple.yaml) | E | 140 |
| [heavy_metal/heavy-metal-full.yaml](heavy_metal/heavy-metal-full.yaml) | B | 170 |
| [heavy_metal/heavy-metal-recipe-showcase.yaml](heavy_metal/heavy-metal-recipe-showcase.yaml) | C | 165 |
| [heavy_metal/heavy-metal-simple.yaml](heavy_metal/heavy-metal-simple.yaml) | E | 160 |
| [jazz/jazz-recipe-showcase.yaml](jazz/jazz-recipe-showcase.yaml) | Bb | 138 |
| [jazz/jazz-simple.yaml](jazz/jazz-simple.yaml) | F | 140 |
| [jazz/jazz-swing.yaml](jazz/jazz-swing.yaml) | Eb | 160 |
| [jazz/jazz-walking-bass.yaml](jazz/jazz-walking-bass.yaml) | Bb | 150 |
| [latin/latin-full.yaml](latin/latin-full.yaml) | D | 110 |
| [latin/latin-recipe-showcase.yaml](latin/latin-recipe-showcase.yaml) | D | 102 |
| [latin/latin-simple.yaml](latin/latin-simple.yaml) | A | 105 |
| [mashup/genre-mashup.yaml](mashup/genre-mashup.yaml) | E | 110 |
| [metal/metal-breakdown.yaml](metal/metal-breakdown.yaml) | C | 180 |
| [metal/metal-chugging.yaml](metal/metal-chugging.yaml) | D | 170 |
| [metal/metal-recipe-showcase.yaml](metal/metal-recipe-showcase.yaml) | E | 155 |
| [metal/metal-simple.yaml](metal/metal-simple.yaml) | E | 160 |
| [new_wave/new-wave-full.yaml](new_wave/new-wave-full.yaml) | F | 128 |
| [new_wave/new-wave-recipe-showcase.yaml](new_wave/new-wave-recipe-showcase.yaml) | F | 135 |
| [new_wave/new-wave-simple.yaml](new_wave/new-wave-simple.yaml) | D | 130 |
| [pop/pop-full.yaml](pop/pop-full.yaml) | G | 120 |
| [pop/pop-recipe-showcase.yaml](pop/pop-recipe-showcase.yaml) | C | 118 |
| [pop/pop-simple.yaml](pop/pop-simple.yaml) | C | 115 |
| [pop_rock/pop-rock-full.yaml](pop_rock/pop-rock-full.yaml) | C | 125 |
| [pop_rock/pop-rock-recipe-showcase.yaml](pop_rock/pop-rock-recipe-showcase.yaml) | D | 120 |
| [pop_rock/pop-rock-simple.yaml](pop_rock/pop-rock-simple.yaml) | D | 120 |
| [prog_rock/prog-rock-full.yaml](prog_rock/prog-rock-full.yaml) | D | 135 |
| [prog_rock/prog-rock-recipe-showcase.yaml](prog_rock/prog-rock-recipe-showcase.yaml) | E | 120 |
| [prog_rock/prog-rock-simple.yaml](prog_rock/prog-rock-simple.yaml) | F# | 140 |
| [punk/punk-full.yaml](punk/punk-full.yaml) | E | 185 |
| [punk/punk-recipe-showcase.yaml](punk/punk-recipe-showcase.yaml) | E | 175 |
| [punk/punk-simple.yaml](punk/punk-simple.yaml) | A | 180 |
| [reggae/reggae-full.yaml](reggae/reggae-full.yaml) | D | 76 |
| [reggae/reggae-recipe-showcase.yaml](reggae/reggae-recipe-showcase.yaml) | A | 78 |
| [reggae/reggae-simple.yaml](reggae/reggae-simple.yaml) | A | 80 |
| [rnb/rnb-full.yaml](rnb/rnb-full.yaml) | Bb | 95 |
| [rnb/rnb-recipe-showcase.yaml](rnb/rnb-recipe-showcase.yaml) | Eb | 90 |
| [rnb/rnb-simple.yaml](rnb/rnb-simple.yaml) | F | 90 |
| [rock/rock-full-arrangement.yaml](rock/rock-full-arrangement.yaml) | G | 140 |
| [rock/rock-recipe-showcase.yaml](rock/rock-recipe-showcase.yaml) | A | 125 |
| [rock/rock-simple.yaml](rock/rock-simple.yaml) | D | 120 |
| [rock/rock-verse-chorus.yaml](rock/rock-verse-chorus.yaml) | E | 130 |
| [ska/ska-full.yaml](ska/ska-full.yaml) | G | 160 |
| [ska/ska-recipe-showcase.yaml](ska/ska-recipe-showcase.yaml) | D | 160 |
| [ska/ska-simple.yaml](ska/ska-simple.yaml) | C | 155 |
| [soft_rock/soft-rock-full.yaml](soft_rock/soft-rock-full.yaml) | G | 100 |
| [soft_rock/soft-rock-recipe-showcase.yaml](soft_rock/soft-rock-recipe-showcase.yaml) | G | 100 |
| [soft_rock/soft-rock-simple.yaml](soft_rock/soft-rock-simple.yaml) | C | 95 |
| [soul/soul-full.yaml](soul/soul-full.yaml) | Ab | 90 |
| [soul/soul-recipe-showcase.yaml](soul/soul-recipe-showcase.yaml) | Ab | 92 |
| [soul/soul-simple.yaml](soul/soul-simple.yaml) | Eb | 85 |
| [techno/techno-full.yaml](techno/techno-full.yaml) | A | 138 |
| [techno/techno-recipe-showcase.yaml](techno/techno-recipe-showcase.yaml) | D | 130 |
| [techno/techno-simple.yaml](techno/techno-simple.yaml) | F | 135 |

## Adapt a song

Change `song.key` to transpose the harmony and degree-based material. Change
`bpm` for tempo. Add or repeat section ids in `arrangement` to change the form.
Section `intensity` sets the energy arc; an instrument's intensity can override
it. Change `seed` for new material or `take` for another performance of the same
themes.

A genre recipe supplies defaults for supported engines. Explicit instrument
params override it. See [mashup/genre-mashup.yaml](mashup/genre-mashup.yaml) for
independent genre choices, and the [config reference](../../docs/llm-song-config-reference.md#recipes-and-personas)
for precedence and recipe selection.

To build a family:

```bash
for file in examples/genres/reggae/*.yaml; do
  python produzre_entry.py build "$file"
done
```

The [example index](../README.md) has validation commands and links to the
instrument guides.
