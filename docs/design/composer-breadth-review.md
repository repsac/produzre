# Composer review: solos and genre breadth

Reviewed `e80f0aa` (the requested `9ad9677~1` baseline), `9ad9677`, and
`2fb024d`. Changes in this review are uncommitted.

The recent restraint work is useful, but the larger problems were routing
and idiom. A solo lead could spend seven verse bars waiting for a singer.
Country could receive minor-pentatonic power riffs and octave-pumping bass.
Reggae's guitar already knew how to skank, but its drummer did not know a
one-drop. Acoustic picking had a thumb pattern, but its melody often sat
below the thumb in velocity and its patterns were shared across pieces.

This review uses performed MIDI events and harmonic context, with six
level-matched sketch-synth audio pairs for owner listening. It does not
claim a subjective listening win. The synthesizer is especially limited for
brushes, chicken picking, string noise and independent guitar bends.

## Corpus and routing

The matched main corpus has 78 pieces: five seeds for each solo instrument,
ten songs each for country, funk, reggae, jazz, pop and metal, plus three
meter probes. Ten additional probes cover forced signature riffs in 6/8,
7/8 and 12/8, jazz in 3/4, and each solo instrument in 6/8 and 7/8.
The main corpus was rendered at all three revisions; additional meter
probes compare the requested baseline with this work.

`tools/album_diversity.py` now supplies country and pop diatonic harmony,
reggae major-key cycles, funk seventh-chord vamps, and jazz ii-V-I and
turnaround harmony. Metal retains the existing rock corpus. It supports
`--instruments` and `--meter`, fingerprints acoustic guitar, and no longer
wraps 5/4 into a 16-step bar. Album seed 2 now changes the part seeds as well
as keys and progressions. Each CLI invocation gets an isolated render
folder. Album runs in this review were sequential.

`tools/rhythm_review.py` accepts `--genre` or `--configs`, records every
instrument's performed notes, and reports solo note coverage and dynamics.
`tools/breadth_review.py` runs both analyses on the same configurations.
The similarity measure remains a modal-bar, onset/pitch-class measure.
It does not measure whole-song resemblance, melodic contour across bars,
voicing register, dynamics, or the value of an intentional rest.

| Use case | What actually runs |
|---|---|
| Unconfigured solo drums | Song drum DNA and arrangement planning, drum performer, drum humanization. Composed drums skip groove memory. This review adds hand-voice answers and a four-bar dynamic contour. |
| Authored drum demo | `voices`, recipe, pattern, section intent, or a drum-groove theme retains the older engine. The hats, kick, snare and bridge demos deliberately use these controls. |
| Solo fingerpicked acoustic | Previously the engine's fixed pattern plus shared melody guide and groove memory. Now an unpinned fingerpicking part gets per-piece two-bar picking DNA, a top voice, thumb roots/fifths, phrase-end variation and a closing hold. Composed picking skips groove memory. |
| Authored acoustic demo | Explicit `picking_pattern`, another technique, recipe, `composer: false`, or an authored melody retains the engine. The style-comparison example therefore keeps all four demonstrated styles. |
| Solo lead | Already received hook, phrase and lick DNA, but default `foreground: auto` selected vocal accompaniment. A lone enabled lead now defaults to `full`. Explicit `foreground: auto` still wins. This reuses the existing melodic form rather than inventing a second lead composer. |
| Band | Lead, drums, then rhythm are composed in the prepass. Engines perform those plans; bass ownership is decided before recipe merging. Explicit part selectors keep their engines. |

## Musical evidence by use case

Bars are local to the named section. Beat positions are zero-based quarter
notes. `01` below means `Album_<genre>_01` in the saved corpus.

| Piece, section, bar | Character, problem, and result |
|---|---|
| Solo drums, pop 01, verse bars 1-4 | The original kick figure is recognizable, but the same ride/snare orchestration repeats. The new second and fourth bars answer the snare figure on toms without changing the kick attacks. The statement/answer contour is quieter, stronger, then released across four bars. This is an arranged drum performance, not yet a freely developing extended drum solo. |
| Solo acoustic, country 01, verse bars 1-2 | The old thumb alternates G2/D3, but the sampled melodic notes average velocity 50.8 against 67.4 for other picks. The new verse has G2/D3 thumb notes at velocities averaging 53.9 and a D4/B3/D4 top line averaging 74.8. The inner voice averages 39.2. Bars alternate 9 and 7 notes and recall that figure. |
| Solo acoustic, country 01, chorus bar 1 and final outro bar | The chorus raises the top voice to G4 and adds inner-string pinches while the thumb continues. The ending holds the final harmony instead of running the picking loop to the export boundary. Other explicit picking patterns remain untouched. |
| Solo lead, pop 01, verse bars 1-8 | Before, bars 1-7 contain no lead attacks and bar 8 has four fill notes. After, a six-note G-major idea states and develops through the verse. The chorus uses hook/answer phrases rather than long background guide tones. The existing outro liquidates the hook and resolves to the sounding chord. Some full verses still phrase too continuously; a dedicated unaccompanied breath grammar remains worthwhile. |
| Country 01, intro bar 1 and verse bar 1 | Before, G-major harmony carries G/Bb power moves, and the bass doubles the riff. After, the bass states G2 and D2 at beats 0 and 2, with a scale walk toward the next chord. Guitar root/chick gestures meet the kick and snare. This is a clear idiomatic improvement despite increased shared vocabulary across songs. |
| Country 01, chorus bar 1 | Root, arpeggio, short strum/upstroke and fifth replace power-riff language. The chorus lifts through voicing and dynamic weight, with roughly the same attack count as the verse. Country's existing chicken-pick and pedal-steel lick entries remain; generated licks still borrow too much general pentatonic grammar. Independently bent double stops are not implemented. |
| Funk 01, verse bar 1 and chorus bar 1 | The verse leaves short chucks around the bass's 0, .75, 1.5 and 2.75 figure. The chorus's dyads, chucks and walk give 11 gestures in this bar. Album choruses average 13.8 gestures/bar. I kept that density: short articulation and interlocking make it different from continuous heavy strumming. The common bridge figures remain a sameness problem. |
| Reggae 01, chorus bars 1-2 | Short guitar stabs at .5, 1.5, 2.5 and 3.5 now interlock with kick and rim at beat 2. The drums leave beat 0 open. Unison scoring drops sharply, although this is the intended one-drop relationship. The bass engine retains its own sparse line; its downbeat entrance is not forbidden by a drum one-drop. |
| Jazz 01, verse bars 1-2 and chorus bar 1 | The old drummer could be a rock timekeeper and the bass a pumping role. The new drummer uses seeded swing hand figures, feathered kicks and snare comping; the bass keeps the walking-capable engine. The chorus leaves more comping space. The verse's first bass bar can still rest before the line enters, and repeated guitar comp figures remain too similar across the album. |
| Pop 01, verse and chorus bar 1 | The verse's root/arpeggio/strum pattern supports a clear chord identity. Chorus sus gestures resolve to the third, with stronger chords and upper upstrokes. I retained these rather than reducing chorus density globally. Pop no longer randomly chooses the minor-power riff grammar. |
| Metal 01, verse bars 1-2 and chorus bar 1 | The verse's long moved power chord at .75 is its riff identity, followed by a chug at 2.5 and a tail. Open guitar tails retain the bass answer. The chorus still drives with slides, chugs and power chords. I did not apply country/reggae density rules here. Some strong offbeats remain independent of the kick. |

## Theory findings, ranked

1. **Sparse bass approaches became sustained wrong harmony. Fixed.** In
   pop 09, verse bar 1, an E# bass attack at beat 1.5 lasted under B-major
   accompaniment until the approaching F# chord. Being the last selected
   attack did not make it a brief passing note. Automatic approaches now
   require a chord change within one quarter note. This preserves walking
   bass's beat-four approach and prevents a multi-beat passing-tone pedal.
   Pop verse clash candidates fall from 4 to 0; chorus candidates from 19
   to 6. Five of those six remaining pairs come from one separate legacy
   transition: pop 08, chorus bar 8, plays B1 for .6 beats under Bb major,
   then C#2 and Eb2. This fixed-interval turnaround lacks harmonic context
   and is still a poor default here. Its post-render planner receives the
   next bass notes rather than the current chord map; that needs a separate
   context-aware transition change, not another approach-rate adjustment.
2. **Genre labels did not constrain arrangement vocabulary. Fixed in the
   defaults, not globally quantized.** Country, reggae, jazz and pop no
   longer randomly request minor-pentatonic power riffs. Explicit
   `riff_driven: true` remains available. Rock, blues, metal and occasional
   funk mixture retain their vocabulary. Country gets boom-chick bass and
   root/fifth comp grammar; missing reggae/jazz comp tiers first reuse their
   own vocabulary rather than a rock fallback.
3. **Solo lead was answering a nonexistent singer. Fixed.** Phrase DNA
   existed, but the wrong foreground role made most solo verse bars empty.
   Full foreground now applies automatically only to a lone enabled lead.
4. **The acoustic melody was subordinate to its accompaniment. Improved.**
   Thumb, inner voice and melody now have distinct dynamic roles and
   seeded form. The top line spells chord tones and the thumb implies
   root/fifth harmony. It is still conservative chord-tone writing, with
   no fretboard solver or fully independent contrapuntal bass line.
5. **Not every exposed semitone or tritone is a mistake.** Jazz 01's
   Imaj7 voicing contains its written major seventh; removing that interval
   would remove the harmony. Pop's resolving sus4 is also intentional.
   The remaining pop 01 chorus bar 3 pair is G4 over the D-major third,
   anticipating G as a chord tone of the following E-minor chord. Country
   02 chorus bar 8 similarly holds F# against the C#-major third before the
   return to F# harmony. I kept these anticipations rather than choking
   every exposed suspension. Short blues mixture remains valid in rock/funk. The audit ignores pitch
   bend trajectories and can miss notes held into a bar, so zero candidates
   is not proof of harmonic perfection.

## Technical findings, ranked

1. **Odd-meter swing clocks disagreed. Fixed.** Drums swung bar-relative
   positions, while other instruments swung section-relative positions.
   In 7/8 the guitar's .5-beat attack moved to about .655 in one bar but
   stayed near .5 in the next. Shared swing now resets each bar. Group
   starts remain protected; ordinary 4/4 swing is unchanged.
2. **The riff pocket ignored effective drum DNA. Fixed.** The prepass now
   publishes the DNA after section/part reseeding and feel controls.
   `_riff_pocket` and bass kick roles use it. Pocket extraction also excludes
   kick steps suppressed by a snare. Signature recall still deliberately
   uses a verse pocket so the song retains its riff across sections; it is
   not a promise to match every chorus or fill.
3. **Triplet fills were spaced as sixteenths. Fixed.** The triplet offset
   was multiplied by .75 a second time. Its attacks now divide the beat
   into thirds. This changes some measured near-misses in otherwise
   untouched funk and metal.
4. **Ownership and absent-part edges. Fixed.** Disabled instruments no
   longer establish a band. A solo drummer no longer waits through a
   riff-alone intro for a nonexistent guitarist. `fill_rate: 0` keeps
   normal groove bars instead of composing fills or deleting entire fill
   bars. An absent lead clears its previous section payload before rhythm
   composition. `yield_to_lead` still sees composed lead before guitar;
   user-owned lead is not silently predicted or rewritten.
5. **Measurement blind spots. Improved and documented.** The corpus now
   includes solo parts and appropriate harmony, acoustic fingerprints,
   meter-aware token grids, coverage and dynamics, independent album seed
   streams, and isolated CLI render roots. Modal-bar similarity still
   treats idiomatic common anchors as similarity and ignores dynamic
   answers. Read it alongside the actual bar sheets.

## Measurements

B = requested baseline `e80f0aa`; C = starting checkout `2fb024d`;
A = this review. Lower similarity means fewer shared modal-bar tokens, not
necessarily better music. The acoustic and lead rows each contain five
songs; each band row contains ten.

| Use case | Similarity B | C | A |
|---|---:|---:|---:|
| Solo drums | .256 | .256 | .228 |
| Solo acoustic | .359 | .359 | .404 |
| Solo lead | .049 | .049 | .098 |
| Country band | .180 | .180 | .281 |
| Funk band | .232 | .235 | .233 |
| Reggae band | .232 | .232 | .286 |
| Jazz band | .285 | .283 | .256 |
| Pop band | .174 | .165 | .179 |
| Metal band | .208 | .210 | .211 |

Country's +.101 is substantial, not a small regression. I retained it for
the audible structural change from accidental rock to root/fifth country,
but country diversity is unfinished. Reggae's +.054 likewise buys an
actual one-drop. Acoustic +.045 accompanies a stronger melodic voice and
stable picking form. Solo lead's +.049 accompanies removal of empty verses:
its original low score was not evidence of a successful solo album.
An early jazz draft approached .98 drum similarity; it was rejected and
replaced with varied hand and comping figures.

Across solo verses, drums retain 16.05 notes/bar and add 50 tom-answer notes
in 80 bars. Acoustic changes 7.97 to 8.12 notes/bar. Lead changes 1.25 to
5.72 notes/bar, with attack-bearing bars rising from 25% to 100%. These are
coverage measures, not a target that every bar must contain new attacks.

| Band verses | Attacks/bar B to A | Accent unison B to A | Silent beats/bar B to A |
|---|---:|---:|---:|
| Country | 7.45 to 7.55 | 60.4% to 98.2% | .91 to .89 |
| Funk | 8.20 to 8.18 | 44.9% to 44.3% | 2.48 to 2.48 |
| Reggae | 5.67 to 5.50 | 73.1% to 6.3% | 3.02 to 3.01 |
| Jazz | 9.11 to 8.84 | 46.2% to 35.5% | 2.24 to 2.32 |
| Pop | 7.96 to 7.66 | 75.7% to 79.9% | .39 to .32 |
| Metal | 9.14 to 7.36 | 49.1% to 57.8% | 1.20 to 1.67 |

After this review, chorus attacks/bar are country 7.35, funk 13.8, reggae
4.02, jazz 2.95, pop 9.80, and metal 10.67. A chorus therefore does not need
one universal density rule. Country lifts through weight and voicing;
reggae keeps the offbeat space; jazz opens comping space; funk keeps short
sixteenth activity; pop and metal retain their existing denser lift. Solo
acoustic adds inner notes and a higher melody, solo drums change voices and
dynamics, and solo lead uses the full hook grammar.

The forced grouped-riff probes hit all group starts after the existing
rhythm fixes: 6/8 32/32, 7/8 48/48, 12/8 64/64. Baseline 7/8 and 12/8 hit
32/48 and 32/64. Loud-accent unison remains 56.3%, 33.3%, and 47.6%,
respectively. In 7/8, group starts are muted chugs while the optional
between-group power chords are louder. Raising every chug merely to win
this metric would change the riff's musical hierarchy. I fixed the timing
clock but kept that contrast.

The pocket scorer is a rock-riff selector, not a universal groove judge.
Reggae 01's chorus provides the clearest counterexample: four guitar
upbeats between a one-drop kick/rim produce almost zero unison and still
express the intended relationship. Jazz comping similarly need not double
the kick. A future interlocking score should reward genre-specific
complementary positions and phrase stability, rather than reward arbitrary
non-coincidence. No universal interlocking weight was added here.

## Validation and reproduction

- Full suite: **682 passed**.
- All **171 example YAMLs** build, including section and pattern exports.
- Twelve representative configs pass `--strict-determinism` and byte-identical
  MIDI comparisons under `PYTHONHASHSEED=1` and `77`.
- New property tests cover solo routing, acoustic melody/thumb roles,
  explicit pattern and composer opt-outs, zero melody amount, compound/odd
  meters, drum answers, one-drop placement, country root/fifth motion,
  per-song jazz variation, effective drum DNA, absent lead payloads,
  disabled instruments, zero fills, sparse approaches, and meter-aware
  fingerprints. Existing walking-bass tests remain intact.
- No commits or pushes. Validation logs and all raw renders are under
  `exports/breadth-review/validation` and `exports/breadth-review`.

```bash
.venv/bin/python tools/album_diversity.py --genre country --songs 10 --out /tmp/country-review
.venv/bin/python tools/album_diversity.py --genre country --instruments acoustic_gtr --songs 5 --out /tmp/fingerstyle-review
.venv/bin/python tools/rhythm_review.py --genre reggae --out /tmp/reggae-review
.venv/bin/python tools/rhythm_review.py --configs examples/acoustic_gtr/style-comparison.yaml --out /tmp/authored-review
.venv/bin/python tools/breadth_review.py --out /tmp/breadth-review
```

The durable [metrics and selected bars](composer-breadth-review-metrics.json)
include all three revisions. Complete final per-bar results are in
`exports/breadth-review/complete/metrics.json`; additional meter results
are in `exports/breadth-review/probes-final/metrics.json`. The frozen corpus
is in `exports/breadth-review/current/corpus.json`.

## Audio pairs

Each pair has 70 seconds, matched RMS and shared peak headroom. Before is
`e80f0aa`; after is the final source. `sources.json` records MIDI paths and
normalization. These are previews for comparing composition, not finished
instrument sounds.

| Use case | Before | After |
|---|---|---|
| Solo drums | [MP3](../../exports/breadth-review/previews/Album_pop_01_drums-before.mp3) | [MP3](../../exports/breadth-review/previews/Album_pop_01_drums-after.mp3) |
| Fingerpicked acoustic | [MP3](../../exports/breadth-review/previews/Album_country_01_acoustic_gtr-before.mp3) | [MP3](../../exports/breadth-review/previews/Album_country_01_acoustic_gtr-after.mp3) |
| Solo lead | [MP3](../../exports/breadth-review/previews/Album_pop_01_lead_gtr-before.mp3) | [MP3](../../exports/breadth-review/previews/Album_pop_01_lead_gtr-after.mp3) |
| Country band | [MP3](../../exports/breadth-review/previews/Album_country_01-before.mp3) | [MP3](../../exports/breadth-review/previews/Album_country_01-after.mp3) |
| Reggae band | [MP3](../../exports/breadth-review/previews/Album_reggae_01-before.mp3) | [MP3](../../exports/breadth-review/previews/Album_reggae_01-after.mp3) |
| Jazz band | [MP3](../../exports/breadth-review/previews/Album_jazz_01-before.mp3) | [MP3](../../exports/breadth-review/previews/Album_jazz_01-after.mp3) |

## Deliberate limits and next work

1. The bass transition planner needs the current and incoming chord maps.
   Its pop 08 whole-step turnaround is the highest-priority remaining
   harmonic defect; changing sparse engine approaches does not fix a later
   transition overlay. Country also needs more independently seeded idiomatic figures: walking
   connections, country-specific generated lead licks, and hybrid-picked
   sixths or double stops. The current monophonic lead cleanup and single
   channel bend model cannot honestly promise independent pedal-steel
   voices. Existing named country licks were left intact.
2. Solo drums now have orchestration and dynamic answers, but need longer
   rhythmic development, controlled displacement and returns to a theme.
   Authored voice demos should remain authored.
3. Solo acoustic needs a string/fret model, more passing-note melody and
   independent bass motion. Explicit legacy picking patterns retain their
   older meter adaptation, including the bar-length ambiguity between 3/4
   and 6/8; the new unpinned composer uses real meter groups.
4. Solo lead would benefit from explicit unaccompanied phrase breaths and
   chord-spelling arpeggios. Existing hook, cadence and modulation machinery
   was retained, and authored melodies are not rewritten.
5. Bass tail answers retain the guitar's tail vocabulary; they are not yet
   independent motivic replies. The earlier rock bass similarity rise is
   partly real common root-chug rhythm and partly the modal-bar metric's
   blindness to the guitar/bass exchange. I did not remove those replies
   to improve a number.
6. Funk's common bridge figures, jazz's limited comp vocabulary, genre-aware
   interlocking evaluation, and a clash scanner that tracks bends and
   cross-bar holds are higher-value follow-ups than universal chorus
   thinning. Existing dense funk and driving metal passages were preserved.

## Follow-up: individual players within the idioms

Baseline: `820b832`, built in the managed `idiom-baseline/produzre`
worktree. The changes below are uncommitted on top of that revision.
The local project seed is `352484703`; the loader combines it with each
YAML song seed before composing. Both checkouts used that same project.
Album seeds 1 and 2 ran sequentially, with ten songs per use case per
album. The rhythm audit uses 93 matched configurations: those six
seed-1 albums, ten additional songs each for pop, funk and metal, and
country in 3/4, 6/8 and 7/8.

The [follow-up measurements](composer-idiom-review-metrics.json) retain
both album reports, player DNA, selected performed bars, configuration
hashes, and the harmonic overlay audit. Full configurations, MIDI,
audit rows, validation logs and audio are under
`exports/idiom-review/{baseline,final,validation,previews}`. The measurement
runner is `exports/idiom-review/measure.py`; it invokes the unchanged
`album_diversity.py` CLI, then `breadth_review.py`, which calls
`rhythm_review.inspect` on the saved configurations.

### 1. Country bass

The home vocabulary is still boom-chick. Its verse weight is 60 percent,
with chord-tone walking, root/fifth/octave answers and train pickups as
alternatives. The chorus chooses a different role. Each section also
chooses fifth direction, and the piece chooses walk type and frequency.
Walking figures have seeded chord-tone paths; train players choose their
pickup position. A chromatic neighbor lasts .22 beats on the final
upbeat. New draws use separate `composer.bass.country` and
`composer.bass.country.figures` streams.

In the first ten-song album, five verses use boom-chick and five walk;
the 100-seed property check confirms boom-chick is the most frequent
verse role. All 100 tested players contrast verse and chorus. Country 01,
verse bar 1, plays G2-B2-D2-G2 on quarters; its chorus returns to G2-D3 on
beats 1 and 3. Country 02 walks F#2-C#3-F#2-A#2 in verse bar 1 and has a
train-pickup bridge. These are different paths within the walking role,
not just different role names. The two-song preview below compares their
first eight verse bars.

### 2. Country and reggae drummers

Country chooses two-beat, four-quarter or pickup kicks, with contrasting
verse/chorus feet and timekeepers and separate train figures by section.
The first album has seven two-beat verses, two four-quarter verses and
one pickup verse. The train vocabulary remains present.

Reggae keeps the one-drop as the weighted home. Rockers uses kicks on
1 and 3; steppers uses all four quarters. The cross-stick remains on 3,
with optional weak rim pickups, varied ghosting, hat figures/openings and
shorter fills. Reggae 01 moves from a one-drop verse to rockers in the
chorus; reggae 02 moves from steppers to one-drop. The first album has
five one-drop, three steppers and two rockers verses.

Idiom drums now choose chorus accents, section accents, or none, voiced
as crash, ride or china. Transition and ending gestures can also carry
the selected accent; the none policy suppresses them. Country's first
album chooses no cymbal accents in three songs, section accents in three,
and chorus accents in four. Reggae chooses those policies in one, five
and four songs respectively. Jazz's existing feathered-kick and swing
comping vocabulary remains, with the same new accent policy.

### 3. Arrangement habits

Independent genre-weighted draws replace the forced values for phrase
fills, intro, solo ending and song ending. Existing arrangement draws
and explicit `song.arrangement_style` overrides retain their precedence.
Country phrase ends in the first album are six walkups, three slides and
one plain ending; intros split five full and five guitar-first. Reggae
has nine plain phrase ends and one slide, with seven full intros. Jazz
has seven plain phrase ends and three walkups, with six full intros.
All three genres vary solo and song endings as well.

I reused the existing phrase-fill vocabulary rather than adding a new
reggae-only arrangement value. Occasional reggae guitar slides remain
possible; its drum pickups/fills are independently seeded. Explicit
arrangement settings can still request the existing rock gestures.

### 4. Fingerpicked acoustic

`PickingDNA` chooses Travis, monotonic, sparse root or walking thumbs;
pinch, p-i-m-a, forward, banjo or held-top figures; and onbeat, syncopated
or anticipated placement. The chorus chooses another hand figure. The
old contour/mask stream remains independent of these choices.

Acoustic 01 uses a walking thumb and a held top in the verse, then a
p-i-m-a figure in the chorus. Acoustic 02 uses Travis thumb with p-i-m-a
in the verse and pinches in the chorus. Verse bar 1 of acoustic 01 has
G2 bass, two held D4 melody notes and quieter inner tones; its chorus
moves the tune onto subdivisions instead of only raising its register.
Across the ten pieces, notes per bar fall from 9.28 to 8.36. The melody
retains its stronger velocity layer. The 100-seed property check covers
all four thumb styles, five figures and three placement choices.

Explicit picking patterns, other techniques and authored melodies still
use their existing routing. The acoustic style-comparison demo and the
drum hats and kick demos produce byte-identical MIDI at both revisions.

### 5. Meter

Country bass plays only beat 1 in 3/4, alternating root and fifth across
bars. In 6/8 and odd meters it follows group starts; these rules take
priority over the chosen four-beat vocabulary. The guitar's ordinary
3/4 bar is a bass gesture on 1 followed by chord strums on 2 and 3.
Phrase endings and authored arrangement gestures can still depart from
that ordinary guitar bar.

The complete 3/4 probe also exposed a post-render pickup in absolute bar
60. The transition pass now preserves this country-waltz bass pulse, so
neither a pickup nor a turnaround reintroduces a second bass attack.
Property tests cover all four bass roles in 3/4, 6/8, 7/8 and 5/4, plus a
rendered full-song waltz. The audio pair includes the corrected guitar.

### 6. Harmonic transition context

Bass turnarounds now receive the current and incoming resolved chord
maps, the current section's absolute offset, meter/grouping and explicit
register bounds. Strong attacks use current chord tones. Non-chord scale
neighbors last at most .22 beats; notes stop at chord boundaries. The
incoming root supplies the destination without being held prematurely
under the old chord. Beat positions are deduplicated and a pre-existing
bass sustain is released at the edit boundary.

The transition evaluator also used a section-ID dictionary that mapped
repeated verses and choruses to their last occurrence. It now follows the
ordered timing/section pairs. This makes earlier transitions land at their
actual boundaries and uses the correct resolved key when a section moves.
Calls to the low-level helper without harmony retain its legacy fallback.

Pop 08, final chorus bar 8 (absolute bar 68), previously played B1-C#2-Eb2
under Bb major. It now plays Bb1-D2-D2 at local beats 2, 3 and 3.5, lasting
.85, .47 and .47 beats, before the incoming Eb harmony. The five sustained
bass/guitar clash pairs in that bar fall to zero.

A separate chord-map audit counts held non-chord overlay notes, not every
seventh or tritone in a voicing. Before/after counts are country 18/0
(including the meter probes), reggae 6/0, jazz 5/0, pop 5/0, hard rock 5/0,
funk 8/0 and metal 5/0. This catches defects that guitar-overlap scoring
misses when the guitar happens to rest. Jazz 03, bridge bar 8, still has
an E bass against D# in an Emaj7 voicing: both are chord tones. I retained
that intended major seventh rather than suppressing it to improve a
clash counter.

### Similarity results

Lower means less shared modal-bar material. These are matched albums,
not selected best seeds.

| Use case | Album 1 before | Album 1 after | Album 2 before | Album 2 after |
|---|---:|---:|---:|---:|
| Country band | 0.281 | 0.258 | 0.266 | 0.280 |
| Reggae band | 0.286 | 0.258 | 0.296 | 0.253 |
| Jazz band | 0.256 | 0.254 | 0.228 | 0.228 |
| Solo acoustic, country | 0.425 | 0.298 | 0.439 | 0.250 |
| Solo drums, pop | 0.210 | 0.210 | 0.204 | 0.204 |
| Hard rock band | 0.168 | 0.168 | 0.198 | 0.198 |

The original five-piece acoustic comparison is also reproduced exactly:
0.404 before, 0.299 after. The five-piece solo-drum control remains 0.228.
Country improves modestly when averaging both albums (0.274 to 0.269),
but album 2 regresses. The fixed two-beat anchor still makes sparse bass
bars resemble each other, and a new role choice does not guarantee a
lower album score. I did not add gratuitous attacks or select a different
album seed to hide this. Country needs owner listening before calling
its variety problem fully solved. Reggae and acoustic improve on both
albums; jazz and the unchanged solo-drum/hard-rock controls stay close or
identical.

### Pocket and clashes

The audit's pocket score is guitar-accent coincidence with kick/snare,
not a general measure of groove. Both whole-song and ordinary groove-bar
results are shown. The latter uses verse/chorus bars 2-6 in both revisions,
excluding entrances and section-ending devices.

| Genre | All-bar coincidence before/after | Groove-bar coincidence before/after | Sustained clash pairs before/after |
|---|---:|---:|---:|
| Country | 0.9581 / 0.9489 | 0.9757 / 0.9769 | 3 / 1 |
| Reggae | 0.0645 / 0.0782 | 0.0438 / 0.1114 | 0 / 0 |
| Jazz | 0.4457 / 0.4478 | 0.3948 / 0.3984 | 119 / 104 |
| Hard rock | 0.6698 / 0.6692 | 0.7036 / 0.7045 | 3 / 2 |
| Pop | 0.7882 / 0.7878 | 0.8114 / 0.8077 | 6 / 1 |
| Funk | 0.6305 / 0.6336 | 0.6167 / 0.6196 | 0 / 0 |
| Metal | 0.6034 / 0.5992 | 0.6249 / 0.6249 | 0 / 0 |

The strict request that every raw pocket statistic not regress is **not
met**. Country's whole-song drop includes five newly guitar-first intros,
where there is deliberately no drummer to coincide with. Its groove-bar
near misses improve from 15 to 14. Reggae's whole-song near misses rise
from 226 to 310: the checker counts a late skank .25 beats before a new
quarter-note kick as a near miss. Its ordinary verse/chorus near misses
remain zero. I retained those idiomatic interlocks. Small pop and metal
coincidence changes also come from transitions now applied at the proper
occurrences and their resulting velocity/accent classification. Raw
counts remain available; these caveats are not a claim of an unqualified
pocket pass. Sustained clash counts do not regress in any audited band.

### Listening pairs

These are level-matched sketch-synth MP3s, not a subjective listening
verdict or production instrument renders. The first seven pairs are 65
seconds. Pop 08 is the final chorus through the outro, starting at beat
240 (112.5 seconds at 128 BPM). Peak headroom and stereo decoding were
checked. `previews/sources.json` identifies the exact source MIDI, excerpt
and common gain for each pair.

| Piece | Before at 820b832 | After |
|---|---|---|
| Country 01 | [MP3](../../exports/idiom-review/previews/Album_country_01-before.mp3) | [MP3](../../exports/idiom-review/previews/Album_country_01-after.mp3) |
| Country 02 | [MP3](../../exports/idiom-review/previews/Album_country_02-before.mp3) | [MP3](../../exports/idiom-review/previews/Album_country_02-after.mp3) |
| Reggae 01 | [MP3](../../exports/idiom-review/previews/Album_reggae_01-before.mp3) | [MP3](../../exports/idiom-review/previews/Album_reggae_01-after.mp3) |
| Reggae 02 | [MP3](../../exports/idiom-review/previews/Album_reggae_02-before.mp3) | [MP3](../../exports/idiom-review/previews/Album_reggae_02-after.mp3) |
| Acoustic 01 | [MP3](../../exports/idiom-review/previews/Album_country_01_acoustic_gtr-before.mp3) | [MP3](../../exports/idiom-review/previews/Album_country_01_acoustic_gtr-after.mp3) |
| Acoustic 02 | [MP3](../../exports/idiom-review/previews/Album_country_02_acoustic_gtr-before.mp3) | [MP3](../../exports/idiom-review/previews/Album_country_02_acoustic_gtr-after.mp3) |
| Country 3/4 | [MP3](../../exports/idiom-review/previews/Country_3_4-before.mp3) | [MP3](../../exports/idiom-review/previews/Country_3_4-after.mp3) |
| Pop 08, final chorus into outro | [MP3](../../exports/idiom-review/previews/Album_pop_08-before.mp3) | [MP3](../../exports/idiom-review/previews/Album_pop_08-after.mp3) |
| Country 01 then 02, eight verse bars each | [MP3](../../exports/idiom-review/previews/country-two-songs-before.mp3) | [MP3](../../exports/idiom-review/previews/country-two-songs-after.mp3) |

### Validation and remaining limits

Property tests cover seeded bass/drum variation, section contrast,
nonconstant arrangement habits and override precedence, picking DNA and
performed figure changes, meter-specific bass attacks, a full waltz after
transitions, and harmonic/register-safe turnarounds across chord changes.
The full suite passes with 699 tests; all 171 examples build. Fourteen representative
configurations pass strict determinism and produce identical MIDI with
`PYTHONHASHSEED=1` and `77`. Validation artifacts are in
`exports/idiom-review/validation`.

I left authored picking/drum demonstrations, the hard-rock vocabulary,
solo-pop-drum development and the jazz player's existing comping grammar
alone. The transition timing/harmony fix applies across genres, so an
unchanged similarity score does not imply every full-song MIDI byte is
unchanged. Existing jazz seventh colors and the remaining non-overlay
lead/comp clash candidates also remain. There is no fretboard solver,
independent string-bend model or freely developing acoustic counterpoint
in this change. Nothing was committed or pushed.
