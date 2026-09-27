# Songs

Twelve complete songs, each with its own genre, meter and band. The other
example folders show one feature at a time; these read like a set list.
Each file opens with a header that describes the song, explains any
setting chosen on purpose, and lists what to listen for. Copy one and change
its key, tempo, chords or form to start your own.

Build one from the repository root:

```bash
python produzre_entry.py build examples/songs/iron-horse-road.yaml
```

The build log prints the export directory; open the full-song MIDI in a DAW.
Songs marked "singer" leave room for a vocal that is not rendered: the lead
guitar plays fills, counter-lines or harmonies (each song's chorus form)
and a solo around it (`foreground: auto`). In the other songs, the lead
plays the melody (`foreground: full`).

| Song | Genre | Key, tempo, meter | Listen for |
|---|---|---|---|
| [Iron Horse Road](iron-horse-road.yaml) | Hard rock, singer | A minor, 124, 4/4 | A signature riff alone, then the band in unison with it; final chorus up a whole step |
| [Glass Mountain](glass-mountain.yaml) | Arena rock instrumental | D major, 116, 4/4 | One hook in intro and every chorus; a 16-bar solo that climbs and ends on a dive |
| [Streetlight Summer](streetlight-summer.yaml) | Pop | G major, 112, 4/4 | Small first verse, prechorus climbing to V, the chorus hook three times, half-step key change |
| [Backstreet Strut](backstreet-strut.yaml) | Funk instrumental | E dorian, 98, 4/4 | Riff and slap bass in unison, sixteenth-note chanks, ghost notes, a drums-and-bass breakdown |
| [Two Dollar Jukebox](two-dollar-jukebox.yaml) | Honky-tonk country, singer | G major, 152, 4/4 | Shuffle across the band, bass pickups into the changes, chicken-picking fills, II7 to V, final key change |
| [Porch Light Waltz](porch-light-waltz.yaml) | Country waltz, singer | D major, 96, 3/4 | Bass on 1, guitar on 2 and 3, fingerpicked verses and strummed choruses |
| [Harbour Road](harbour-road.yaml) | Roots reggae | A minor, 74, 4/4 | One-drop verses, an authored riddim bass line, offbeat skank, a dub section |
| [Blue Lantern](blue-lantern.yaml) | Jazz waltz | F major, 150, 3/4 | Walking bass, seventh-chord comping, an AABA head built on ii-V-I |
| [Juniper Hollow](juniper-hollow.yaml) | Folk, singer | D major, 96, 4/4 | Travis picking alone, then bass, drums and a second guitar entering one at a time |
| [Cold Coffee Blues](cold-coffee-blues.yaml) | Slow blues, singer | G major, 80, 12/8 | Four slow beats split in three, an authored twelve-bar bass line, licks answering the voice |
| [Clockwork Tide](clockwork-tide.yaml) | Prog rock instrumental | F# minor, 132, 7/8 and 5/4 | Verses grouped 2+2+3, chorus regrouped 3+2+2, a 5/4 bridge |
| [Furnace Heart](furnace-heart.yaml) | Metal, singer | E minor, 168, 4/4 | Chugging riff doubled by the bass, the flat-second bite, a half-time breakdown |

Every song lets the composer draw its own band from the seed: the drummer,
the rhythm-guitar figures, the licks and the arrangement habits. All the
examples use the built-in `produzre-examples` project (`song.project`), so
everyone who builds them gets the same MIDI, and each header describes that
band. Where a song needs one particular habit, the header names the pin
(`arrangement_style`) or the part seed that gives it. A different song
`seed` keeps the chords and form but hands the song to a new band. See the
[config reference](../../docs/llm-song-config-reference.md) for every
setting used here.
