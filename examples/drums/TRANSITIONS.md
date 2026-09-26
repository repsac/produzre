# Drum transitions

How the composed band gets from one section to the next.
[transitions-demo.yaml](transitions-demo.yaml) plays a whole song with the
habits pinned; [transitions/](transitions/) has one short song per way
into a chorus.

## Arrangement habits

Each song draws habits that the drums and rhythm guitar agree on. Pin any
of them with `song.arrangement_style`
([reference](../../docs/llm-song-config-reference.md#every-song-its-own-band)):

```yaml
song:
  arrangement_style:
    into_chorus: stop     # stop | build | fill | push | drop
    intro: riff_alone     # full | riff_alone
    ending: cold          # ring | cold | big
```

### Into a chorus

The last bar before a chorus:

| `into_chorus` | Drums | Rhythm guitar | Demo |
|---|---|---|---|
| `stop` | Kick and crash on 1, silence, a two-note snare pickup | One chord, silence, a chuck and an upstroke | [into-chorus-stop.yaml](transitions/into-chorus-stop.yaml) |
| `build` | The big fill | Straight eighth strums, the last two accented | [into-chorus-build.yaml](transitions/into-chorus-build.yaml) |
| `fill` | The big fill | Its figure, then three chucks and an upstroke | [into-chorus-fill.yaml](transitions/into-chorus-fill.yaml) |
| `push` | The groove, then crash and kick on the last "and", ringing over the downbeat | Its figure, then a held chord on the same "and" | [into-chorus-push.yaml](transitions/into-chorus-push.yaml) |
| `drop` | Silence, then a snare hit on the last beat and a floor-tom pickup | One chord held for the bar | [into-chorus-drop.yaml](transitions/into-chorus-drop.yaml) |

The bass keeps its own line through these bars. Every other section
boundary gets the drummer's big fill in the last bar, and every new section
opens with a crash (see [PHRASING.md](PHRASING.md) for the exceptions).

### Intros and endings

- `intro: riff_alone`: in a song that opens with an intro, the guitar plays
  alone for the first half; the drums enter with a fill and a crash.
  An intro without a rhythm or acoustic guitar plays from the top.
- `ending: ring`: the last bar is one crash and kick, left to ring.
- `ending: cold`: the band stops on the last downbeat and the crash is
  choked.
- `ending: big`: a hit, a swelling roll around the kit, and a final crash.

With `fill_rate: 0` in the last section, a big ending plays as a ring.

## The transition planner

`song.params.transitions` runs after every part is written and adjusts
section boundaries for the whole band: occasional pickups before a new
section, velocity ramps, and a blended first bar after a large energy
change. Its settings (`strength`, `pickup_rate`, `turnaround_rate`,
`ramp_bars`, `bridge_start_bars`) are in the
[transitions reference](../../docs/llm-song-config-reference.md#transitions).
Pickups it adds show up in the events TSV as `pickup_transition`.

## The classic engine's transition controls

Drum `pickup_rate` (a snare roll before a new section type) and
`downbeat_rate` (crash and kick on its first beat) belong to the classic
engine. With the composed drummer they are logged as unused. Set
`composer: false` in the drum params to use them;
[classic-engine-demo.yaml](classic-engine-demo.yaml) turns each one off in
one section.
