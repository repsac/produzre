# Lead guitar examples

These songs isolate phrasing choices, then place the lead in blues, rock,
and jazz arrangements.

- [advanced/contour-comparison.yaml](advanced/contour-comparison.yaml): compare `contour_style: stepwise`, `balanced`, and `leaping` at intensity 0.7 and rest probability 0.2.
- [advanced/phrase-length-comparison.yaml](advanced/phrase-length-comparison.yaml): compare `phrase_len_bars` 1, 2, and 4 across eight-bar sections.
- [basics/density-comparison.yaml](basics/density-comparison.yaml): compare `rest_probability` 0.5, 0.25, and 0.1 as lead intensity rises from 0.5 to 0.9.
- [basics/resolution-comparison.yaml](basics/resolution-comparison.yaml): compare `resolution_strength` 0.2, 0.5, and 0.8 with the same contour and rest settings.
- [styles/blues-lead.yaml](styles/blues-lead.yaml): hear a 12-bar E blues move from stepwise verse phrases to a balanced solo, with rests dropping from 0.35 to 0.2.
- [styles/jazz-lead.yaml](styles/jazz-lead.yaml): hear an F major head return after a solo; the solo lowers `rest_probability` from 0.3 to 0.15.
- [styles/rock-solo.yaml](styles/rock-solo.yaml): hear a D minor verse and chorus lead into a leaping solo with `rest_probability: 0.05` and four-bar phrases.

```bash
python produzre_entry.py build examples/lead_gtr/basics/density-comparison.yaml
```

## What to listen for

The density comparison changes `rest_probability` and intensity. Count gaps
as well as notes. Planning can reserve only part of a section for lead, so
listen for how the lead uses its available space.

The resolution comparison changes `resolution_strength`. Higher values favor
chord tones and stronger phrase endings. The contour comparison changes
`contour_style`: stepwise, balanced, or leaping. Registers and chord targets
still limit the available intervals.

The phrase-length comparison changes `phrase_len_bars`. Later phrases develop
the opening motif; a short cycle produces more frequent returns. The style
examples change genre vocabulary and arrangement, including featured solos.

## Themes and phrasing

Use [themes_demo.yaml](../themes_demo.yaml) to hear an authored hook across
sections; see [theme controls](../../docs/llm-song-config-reference.md#themes) for quotation settings.

For more space, raise `rest_probability`. For a featured part, set direct
`solo: true` or `role: lead` and choose an appropriate register. The personas
are balanced, melodic, shredder, bluesy, and ambient.

The [lead reference](../../docs/llm-song-config-reference.md#lead-guitar-controls)
lists defaults and ranges for contour, rests, resolution, phrase length,
and intensity.
