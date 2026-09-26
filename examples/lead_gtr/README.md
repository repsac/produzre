# Lead guitar examples

The lead is composed by default. Once per song the composer writes a hook,
its answer, a verse idea, a bridge idea and a bank of signature licks,
choosing the most memorable candidates over your chorus and verse chords.
Each section plays a phrase form (a verse period, hook lines in the chorus,
a solo that tells a story), and a returning section repeats what it played
before. See [the composer](../../docs/llm-song-config-reference.md#the-composer).

```bash
python produzre_entry.py build examples/lead_gtr/basics/foreground-comparison.yaml
```

## Basics

- [basics/foreground-comparison.yaml](basics/foreground-comparison.yaml): `foreground: full` (the lead is the melody) against `foreground: auto` (the lead plays around a singer), in a verse and a chorus each.
- [basics/density-comparison.yaml](basics/density-comparison.yaml): `rest_probability` unset, 0.5 and 0.85 over the same remembered verse melody, then a sparse chorus that keeps its hook.

## Advanced

- [advanced/expression-comparison.yaml](advanced/expression-comparison.yaml): the same chorus line played dry, with the default expression, and with vibrato and swells on every long note; then a solo with `dive_rate: 1`.

## Styles

Each style pins a different solo with `song.arrangement_style`:

- [styles/blues-lead.yaml](styles/blues-lead.yaml): an instrumental 12-bar blues; `solo_story: blues`, `solo_ending: hold`.
- [styles/jazz-lead.yaml](styles/jazz-lead.yaml): head, solo, head over ii-V-I changes; `solo_story: melodic`, `solo_ending: trill`, no bends, stepwise contour.
- [styles/rock-solo.yaml](styles/rock-solo.yaml): a band with a singer, octave stabs under the chorus, and a solo with `solo_story: climb`, `solo_ending: slide_off` and `register: full`.
- [styles/metal-lead.yaml](styles/metal-lead.yaml): an instrumental metal song around an authored hook, with a doubled signature riff; `solo_story: trade`, `solo_ending: dive`.
- [solo/](solo/): the lead guitar on its own.

## The classic engine

- [classic-engine-demo.yaml](classic-engine-demo.yaml): `composer: false` selects the 0.9 motif generator, with `phrase_len_bars` 1, 2 and 4, `resolution_strength`, `theme_quote_rate`, `ring_out` and `contour_style`.

## What shapes the composed lead

| Setting | Effect |
|---|---|
| `foreground` | `full`: the lead is the melody. `auto` (default): hooks, fills, counter-lines and solos around a singer. Per section or for the whole song. |
| `register` | The melody range: a named preset (`low`, `mid`, `high`, `very_high`, `full`) or a hard `[low, high]` MIDI range. Solos extend a named range upward. |
| `rest_probability` | Drops answers, developments and fills; never the hook, cadences, or the solo's structural moments. |
| `contour_style` | `stepwise` makes leaps cost more, `leaping` makes them cheaper. A subtle change: the phrase forms and chords still decide most intervals. |
| `bend_rate`, `vibrato_rate`, `dive_rate`, `swell_rate` | Expression: `bend_rate` keeps a share of the composed bends (0 removes them; values above 0.15 add none), the others as in the [reference](../../docs/llm-song-config-reference.md#lead-guitar-controls). |
| `solo: true` or `role: lead` | Makes any section a solo. |
| An authored `melody` theme | Becomes the song's hook; see [themes_demo.yaml](../themes_demo.yaml). |

Song habits, pinned with `song.arrangement_style`
([reference](../../docs/llm-song-config-reference.md#every-song-its-own-band)):
`solo_story` (`climb`, `melodic`, `trade`, `blues`), `solo_ending` (`dive`,
`hold`, `trill`, `slide_off`; a dive only in rock and metal), `counter` (the
lead under a sung chorus: `guide`, `octaves`, `stabs`, `fills`),
`chorus_form` (`lift`, `anthem`, `call`) and `lead_fills` (`sparse`,
`normal`, `chatty`).

`phrase_len_bars`, `theme_quote_rate`, `resolution_strength`, `ring_out` and
`ring_max_beats` tune only the classic engine. With the composer on, the
build log lists them as unused. Lead personas set phrase length, rests,
contour and resolution; persona values never count as your choice, so they
leave the composed line alone.

A lead `seed` changes the performance's humanization, not the composed
notes: the line comes from the song seed.
