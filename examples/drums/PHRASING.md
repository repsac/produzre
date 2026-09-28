# Drum phrasing

How the composed drummer decides where phrases end, and what you can change.
[phrasing-demo.yaml](phrasing-demo.yaml) plays each case.

## Four-bar phrases

The band thinks in four-bar phrases. Groove memory restates the section's
most typical bar through each phrase and leaves the phrase's last bar to
the performer, so that bar is where fills, turnarounds and pickups go
(see [groove memory](../../docs/llm-song-config-reference.md#groove-memory)).

Within a section the drummer fills:

- at phrase ends, every 4 or 8 bars (the song's habit, or `fill_rate`);
- with a one-beat fill every 2 or 4 bars, if the song's drummer has that
  habit (or `fill_rate` of 0.75 or more asks for it);
- in the section's last bar, with the transition into the next section.
  Before a chorus that bar follows the song's `into_chorus` habit; see
  [TRANSITIONS.md](TRANSITIONS.md).

| Section | Phrase fills with `fill_rate: 0.6` |
|---|---|
| 8 bars | bars 4 and 8 |
| 6 bars | bar 4, then bar 6 (the section's end) |
| 12 bars | bars 4, 8 and 12 |
| 4 bars | bar 4 (the section's end) |

`fill_rate: 0` removes every fill, including the one into the next
section.

When the drums play alone, the backbeat stays in every bar and the last
beat of bars 2 and 4 of each four-bar phrase answers on the toms (unless a
fill is already there); see [solo/](solo/). See [fills-demo.yaml](fills-demo.yaml) for the rates side by side.

## Crashes

Most drummers crash at every section start and draw a phrase-crash
spacing of 4, 8 or 16 bars. Country, reggae and jazz drummers crash only
on section starts, only on choruses, or not at all, sometimes on the ride
or a china instead.

## Meters

Phrases count bars in every meter. In compound meters the drummer plays
on the dotted-quarter pulse: 6/8 puts the backbeat on its "4" (the second
pulse), 12/8 on pulses 2 and 4, and fills are whole pulses. In 7/8 the
backbeat falls on the 2+2+3 group starts. Fills keep inside the bar. A
drum-only section takes its grouping from the meter, so it needs no
harmony progression. `song.meter_grouping` or a section's
`meter_grouping` changes the grouping; see
[meter and beat units](../../docs/llm-song-config-reference.md#meter-and-beat-units).

The text views number bars on the song's own bar grid, so a 6/8 section in
a 4/4 song shows its fills at 4/4 bar numbers. Use `start_beat_abs` in the
events TSV, or `QUICKREF.txt`, for exact positions.

## The classic engine's phrase controls

`phrase_len_bars`, `phrase_end_emphasis`, `fill_length` and `fill_chatter`
belong to the classic engine. With the composed drummer they are logged as
unused. Set `composer: false` in the drum params to use them;
[classic-engine-demo.yaml](classic-engine-demo.yaml) plays two-bar and
six-bar phrases, short and long fills, and fill chatter.
