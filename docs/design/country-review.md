# Country review: a band identity per song

Baseline: `e4adde4`. Changes are uncommitted on `dev`; nothing was pushed.
The clean, attached `idiom-baseline/produzre` worktree was reused at that
revision. Both checkouts used the same configurations and local project
seed, `352484703`. Album seeds ran sequentially. The supporting scripts,
full MIDI, rhythm audits and audio live under `exports/country-review`.

## Shared style, independent players

A new `composer/country.py` chooses one of six country directions on
`composer.country.style`, independent of all existing streams:

| Style | Direction, not a fixed part |
|---|---|
| `honky_tonk` | Shared shuffle, Carter/chuck figures, chicken picking, thirds and Travis phrases |
| `bakersfield` | Straight, driving bass, low strings, hybrid picking and bright third/sixth figures |
| `outlaw` | Train/chuck figures, softer snares, optional common-tone bass pedal, banjo/Travis vocabulary |
| `two_step` | Dancing bass, offbeat guitar answers, thirds and sixths |
| `ballad` | Longer bass gates, fewer attacks, arpeggio/Carter/hybrid guitar choices, steel-like lead language |
| `country_rock` | Eighth-note bass shapes, strummed choruses, backbeat or train lift and four-quarter chorus kicks |

Pin a style with:

```yaml
song:
  arrangement_style:
    country_style: bakersfield
```

The pin reaches the lead before its lick bank is built, and reaches bass,
comp and drum DNA. Part seeds re-roll that player while retaining the
band's style. Separate player streams choose figures within each direction;
verse and chorus bass rhythms and guitar figures contrast. Existing
patterns, recipes, composer opt-outs, arrangement habits and performance
controls retain their precedence. Honky-tonk's shared swing comes through
the drummer's existing groove clock, whose explicit timing overrides still
win. A solo without drums does not gain that drummer-owned swing clock.

The first benchmark album draws honky-tonk for 01/02, ballad for 03/05/09,
outlaw for 04, two-step for 06/10, and country rock for 07/08. Bakersfield
is exercised by the pinned-style tests. This is a weighted vocabulary
choice, not automatic instrumentation or reharmonization.

## What changed and what the bars do

Positions below are zero-based quarter-note beats. Performed swing and
humanization can move the grid positions slightly. Song numbers refer to
album seed 1.

**Bass.** A player now chooses a recurring rhythm as well as a role:
two-beat, dotted spacing, pickup into 3, driving eighths, sparse holds,
optional short grace approaches, and root/fifth/octave/fifth motion.
Walk type and frequency remain independent. Outlaw pedals are used only
when the pedal belongs to the current chord, avoiding a sustained wrong
bass note. The existing boom-chick role remains the weighted home.

Country 01, verse bar 1, plays G2 at 0, B2 around 1.67 and D2 at 2.01;
chorus bar 1 answers with G2/D3 at 0/2 and shorter .65-beat gates. Country
03, verse bar 1, holds Eb2 for 2.95 beats, then plays G2 on 4; its chorus
holds Eb2 for 3.5 beats. These contrasting rhythms exist before any walk
or grace is added. The album-2 verse-bass regression is reversed in the
measurements below.

**Rhythm guitar.** The forced four-cell country shape is gone. Eight
families now provide their own interchangeable cells: Carter scratch,
alternating muted chucks, train, low-string riffs, two-step offbeats,
arpeggios, hybrid double stops and full strumming. Sub-style changes the
odds; each song draws different cells and section figures. A phrase can
still walk or slide into the next chord. Country comping shortens a
conflicting chord gesture underneath an anticipated held lead note.

Country 01, verse bar 1, uses Carter root/arpeggio/strum gestures, then a
short walk at about 3.66. Its chorus begins with root, upper double stop,
fifth, then a full strum and walk. Country 03 also chooses Carter for its
verse, with a root/arpeggio pickup, upper dyad and two short bass-string
walk gestures. Its bridge draws the arpeggio family. A ballad does not
have to choose arpeggios in every section, and two songs choosing Carter
do not receive the same bar.

**Lead.** Country generation now has chicken-pick, third/sixth double-stop,
steel, banjo, hybrid, Travis and chromatic-approach shapes. Its major-mode
ladder is major pentatonic (including the sixth), with a .12-beat b3-to-3
passing approach. Licks target the third or sixth; sustained arrivals
still defer to the active chord. Explicit minor-mode songs retain their
minor-mode pitch context. The existing hook, phrase memory and register
arc remain intact.

Country 01's chorus bar 2 has a late Travis answer, G4-D5-A4-D5-E5, ending
on the major sixth. Country 03's solo bar 7 opens with an unbent Eb5/C6
sixth, then continues through F5-G5-Ab5. The two notes of a double stop
now survive the composer, performer and final timeline cleanup. Marked
staccato country picks keep their gate when swung, instead of being
shortened twice into nearly inaudible notes.

Steel gestures are single-note bends and releases. A held companion note
cannot remain unbent on this engine's one pitch-bend channel, so no such
independent string bend is claimed. Double stops are explicitly unbent.

**Drums.** Each style draws personal kick pickups, timekeeper cells,
train/backbeat sections and snare touch. Choruses can lift through an
open hat/backbeat, a train figure, ride/bell, or four-quarter feet. Soft
snare velocities approximate a brush touch; this does not select a true
brush sample or kit. The prior sparse crash/ride/china policies remain.

Country 01 changes from hat/backbeat in its verse to open-hat/train in the
chorus. In verse bar 1 the kick plays 0, .655 and 2; chorus bar 1 moves
the pickup to 1.655, with quieter train taps between the backbeats.
Country 03 has softer train snare, sparse hats in verse bar 1 and a ride
bell chorus. The chorus changes the hand voice while its long bass gives
the sustained part room.

**Waltz.** Country bass still plays only beat 1 and alternates root/fifth
across bars. Pedal and four-beat rhythm choices cannot override this.
Ordinary guitar bars answer on 2 and 3. Existing phrase/ending gestures
remain available. The ten-song 3/4 album and meter property tests exercise
this after transitions, not only inside the bass helper.

## Matched measurements

The unchanged `tools/album_diversity.py` ran ten-song country albums with
`--album-seed 1` and `--album-seed 2`, sequentially, at each revision.
Both improve. These are all per-part similarity scores, including the
parts that get worse:

| Part | Album 1 before | Album 1 after | Album 2 before | Album 2 after |
|---|---:|---:|---:|---:|
| Drums verse | .302 | .308 | .347 | .302 |
| Drums chorus | .374 | .278 | .374 | .276 |
| Drums bridge | .335 | .330 | .382 | .286 |
| Bass verse | .238 | .126 | .383 | .125 |
| Bass chorus | .201 | .135 | .244 | .135 |
| Bass bridge | .227 | .091 | .257 | .157 |
| Rhythm guitar verse | .289 | .088 | .270 | .071 |
| Rhythm guitar chorus | .204 | .095 | .248 | .128 |
| Rhythm guitar bridge | .091 | .102 | .099 | .140 |
| Lead chorus | .315 | .047 | .194 | .036 |
| **Overall** | **.258** | **.160** | **.280** | **.166** |

The ten-song country waltz album improves from .712 to .694. It stays
relatively similar because bass on 1 and chords on 2/3 are intentionally
shared. The ten-song solo-country-lead score stays .074: this metric mostly
sees recurring hook bars, while the new lick language occurs in answers
and solos. It is not a complete measure of lead identity.

Across the 720 country band bars, guitar gestures decrease from 7.60 to
6.61 per bar; bass notes increase modestly from 3.06 to 3.26. The lead
has attacks in 132 of 240 chorus bars versus 156 before, with 570 notes
versus 594. Some of its similarity improvement therefore reflects the
choice of spaced fills instead of continuous guide lines, not only the
new pitch vocabulary. Chorus drum similarity improves on both albums,
but album-1 verse drums and both guitar bridges remain counterexamples.
I did not add attacks to force those individual cells lower.

Hard rock remains .168, reggae .258, jazz .254 and pop .179. All ten
full-song MIDI files in each of these four control albums are byte-identical
before and after, not merely equal under the similarity metric.

### Pocket and harmonic exposure

`rhythm_review.inspect`, through the existing `breadth_review.py` runner,
audited the same country configurations at both revisions. The new parts
have zero sustained clash candidates, down from one, and 16 near misses,
down from 33. The initial implementation exposed six clash pairs under
anticipated lead notes; the final comp shortening removes those without
changing their attacks.

Raw accented-guitar coincidence with kick/snare **falls from .9489 to
.8690**, so an unconditional numeric pocket pass would be inaccurate.
There are 2,138 accented guitar gestures now, versus 2,135 before; the
coincident count is 1,858 versus 2,026. The denominator is effectively
unchanged. The missing unisons largely belong to new offbeat answers.

For example, country 06, verse bar 1, formerly scores 4/4 accents matched.
The new two-step bar scores 2/3: guitar root and fifth frame dyads/upstrokes
at .5, 1.5 and 2.5, then a strum at 3.5. The drummer keeps the quarter-note
backbeat and selected pickups. Its .5 dyad is an intentional answer,
not a mistimed unison. Country 03, verse bar 1, moves the other way,
from 2/3 to 4/4. I retained these differences because forcing every guitar
accent onto the kick or snare would erase the requested two-step and
hybrid-picking character. The lower near-miss count is useful supporting
evidence, but owner listening still decides whether the interlocks work.

[Machine-readable measurements and selected bars](country-review-metrics.json)
include both album reports, style/player choices, the coincidence counts,
clash counts, and the SHA-256 hashes of all 40 unchanged control MIDIs.
Full audit rows and exact configurations are retained under
`exports/country-review/{baseline,final}/rhythm`.

## Listening

The three band pairs use different drawn styles: country 01 honky-tonk,
03 ballad, and 04 outlaw. These and the waltz are 65-second excerpts.
The unaccompanied country-04 lead preview contains the full piece so its
later lick development can be heard. Each before/after pair is matched
in RMS level and shares peak headroom. These are deterministic sketch-synth
renders, not a claim of realistic brush, twang or pedal-steel samples.

| Piece | Before, e4adde4 | After |
|---|---|---|
| Country 01, honky-tonk | [MP3](../../exports/country-review/previews/Album_country_01-before.mp3) | [MP3](../../exports/country-review/previews/Album_country_01-after.mp3) |
| Country 03, ballad | [MP3](../../exports/country-review/previews/Album_country_03-before.mp3) | [MP3](../../exports/country-review/previews/Album_country_03-after.mp3) |
| Country 04, outlaw | [MP3](../../exports/country-review/previews/Album_country_04-before.mp3) | [MP3](../../exports/country-review/previews/Album_country_04-after.mp3) |
| Country 01, 3/4 | [MP3](../../exports/country-review/previews/Album_country_01_Waltz-before.mp3) | [MP3](../../exports/country-review/previews/Album_country_01_Waltz-after.mp3) |
| Country 04, solo lead | [MP3](../../exports/country-review/previews/Album_country_04_lead_gtr-before.mp3) | [MP3](../../exports/country-review/previews/Album_country_04_lead_gtr-after.mp3) |
| Six-song country sampler | [MP3](../../exports/country-review/previews/country-sampler-before.mp3) | [MP3](../../exports/country-review/previews/country-sampler-after.mp3) |

Sampler order: 01, 03, 04, 06, 07, 10. Each contributes its first eight
verse bars, followed by a one-second gap. This includes two two-step
songs so the comparison tests variation within a style as well as
between styles. No progressions or keys were altered to make the styles
sound different. `previews/sources.json` records the source MIDI, lengths,
levels and sampler order.

## Verification and deliberate limits

- Full suite: 712 passing tests, including the new style, ownership,
  vocabulary and complete double-stop-pipeline properties.
- All 171 examples build with section and pattern exports enabled.
- Strict determinism plus matching MIDI under `PYTHONHASHSEED=1` and `77`
  for all ten country songs, a waltz, solo lead, and four control genres.
- Existing meter tests still cover 3/4, 6/8, 7/8 and 5/4; a rendered waltz
  verifies that post-render transitions do not add a second bass attack.
- Generated licks, riff cells and bass rhythms vary across seeds within
  every pinned style. A loaded YAML test verifies the style pin reaches
  the players and explicit bass walking settings retain engine ownership.

Western swing is left out: a credible version needs coordinated harmony
and jazz voicings rather than a new label on these existing progressions.
Independent string bends, a true brush kit and a fretboard fingering
solver remain unsupported. Explicit harmony and authored patterns are
not rewritten to fit a style. Other genres retain their measured MIDI.
The non-country lead stays monophonic, and the country exception permits
only marked unbent double stops. The solo hook generator and its form
were left alone; this work changes the country lick vocabulary and band
choices rather than replacing the melody composer.
