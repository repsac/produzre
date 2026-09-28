# Genre examples

One complete song per genre: 30 genres plus a cross-genre mashup. Each file
is a full arrangement (intro, verses, choruses, a bridge or solo, and an
outro) written for the current composer: per-song drum, bass and comping
DNA, genre idioms, and the arrangement habits in
[Every song its own band](../../docs/llm-song-config-reference.md#every-song-its-own-band).
Each header explains what the song shows, which habits it pins and why,
and what to listen for.

```bash
python produzre_entry.py build examples/genres/hard_rock/hard-rock.yaml
python produzre_entry.py build examples/genres/country/country.yaml
```

Every file sets `project: produzre-examples`, a built-in project with a
fixed seed, so everyone who builds an example gets the same MIDI and the
headers describe exactly what you hear. Copy a file and change its key,
tempo, seed or `song.arrangement_style` to make your own song in that
genre. See
[recipes and personas](../../docs/llm-song-config-reference.md#recipes-and-personas)
for how a genre selects defaults.

## Browse the songs

| Genre | File | Title | Key | BPM | Meter | What it is |
|---|---|---|---|---|---|---|
| alt_rock | [alt-rock.yaml](alt_rock/alt-rock.yaml) | Radio Tower Weather | E major | 124 | 4/4 | A mixolydian verse and a big chorus in E at 124 BPM. |
| arena_rock | [arena-rock.yaml](arena_rock/arena-rock.yaml) | Lighters Over Lakeside | A major | 126 | 4/4 | A stadium anthem in A major at 126 BPM, with a singer. |
| blues | [blues.yaml](blues/blues.yaml) | Lowdown Kitchen Shuffle | A major | 96 | 4/4 | A 12-bar shuffle in A with a singer, answered by the guitar. |
| blues_rock | [blues-rock.yaml](blues_rock/blues-rock.yaml) | Mudflap Boogie Engine | E major | 118 | 4/4 | A riff in E, a 12-bar solo, and a singer's chorus. |
| classical | [classical.yaml](classical/classical.yaml) | Rondo for a Garden Party | G major | 112 | 3/4 | A rondo for violin, piano and cello in G major, 3/4, 112 BPM. |
| country | [country.yaml](country/country.yaml) | Jukebox on Route Nine | G major | 116 | 4/4 | A honky-tonk shuffle in G at 116 BPM, with a singer. |
| dance_pop | [dance-pop.yaml](dance_pop/dance-pop.yaml) | Glitter on the Night Bus | F major | 122 | 4/4 | A four-on-the-floor single in F at 122 BPM, with a singer. |
| electronic | [electronic.yaml](electronic/electronic.yaml) | Afterglow Frequency | A minor | 126 | 4/4 | A four-on-the-floor club track in A minor at 126 BPM. |
| emo | [emo.yaml](emo/emo.yaml) | Notebook Margins in July | G major | 158 | 4/4 | Fast, bright and heartbroken, in G major at 158 BPM, with a singer. |
| folk | [folk.yaml](folk/folk.yaml) | Lantern by the Ferry Road | D major | 100 | 4/4 | A fingerpicked song in D at 100 BPM, with a singer and harmonica. |
| funk | [funk.yaml](funk/funk.yaml) | Sixteen Shades of Grease | E dorian | 102 | 4/4 | A two-chord E dorian groove at 102 BPM, with a singer. |
| gospel | [gospel.yaml](gospel/gospel.yaml) | Sunday Morning Glory Road | Ab major | 96 | 6/8 | A slow 6/8 praise song in Ab at 96 BPM, with a singer. |
| grunge | [grunge.yaml](grunge/grunge.yaml) | Wet Flannel Static | D minor | 116 | 4/4 | Quiet verse, loud chorus, in D minor at 116 BPM, with a singer. |
| hard_rock | [hard-rock.yaml](hard_rock/hard-rock.yaml) | Gravel and Thunder | A minor | 132 | 4/4 | A riff-driven band with a singer, in A minor at 132 BPM. |
| heavy_metal | [heavy-metal.yaml](heavy_metal/heavy-metal.yaml) | Anvil of the Night | E minor | 168 | 4/4 | A chugging riff in E minor at 168 BPM, with a singer. |
| jazz | [jazz.yaml](jazz/jazz.yaml) | Backdoor Blue Room | Bb major | 156 | 4/4 | A medium-up swing tune in Bb for guitar trio (plus a comping guitar). |
| latin | [latin.yaml](latin/latin.yaml) | Calle de la Luna | A minor | 100 | 4/4 | An instrumental in A minor with a clave-driven band and a nylon guitar. |
| mashup | [genre-mashup.yaml](mashup/genre-mashup.yaml) | Crossfade City | E minor | 100 | 4/4 | One song in E minor that changes genre section by section. |
| metal | [metal.yaml](metal/metal.yaml) | Iron Meridian | E minor | 168 | 4/4 | A riff-driven song in E minor with a singer, a breakdown and a solo. |
| new_wave | [new-wave.yaml](new_wave/new-wave.yaml) | Glass Radio | D major | 134 | 4/4 | A synth-and-guitar song in D major with a singer. |
| pop | [pop.yaml](pop/pop.yaml) | Paper Planes Tonight | E major | 116 | 4/4 | A hook-first song in E major with piano, acoustic guitar and a singer. |
| pop_rock | [pop-rock.yaml](pop_rock/pop-rock.yaml) | Summer on Fifth Street | A major | 124 | 4/4 | A guitar-band song in A major with a singer and a melodic solo. |
| prog_rock | [prog-rock.yaml](prog_rock/prog-rock.yaml) | Seven Gates of Morning | D dorian | 132 | 7/8 | An instrumental in D dorian that moves between 7/8, 4/4 and 5/4. |
| punk | [punk.yaml](punk/punk.yaml) | No Time for Sirens | E major | 184 | 4/4 | A fast, short three-chord song in E major with a singer. |
| reggae | [reggae.yaml](reggae/reggae.yaml) | Hillside Riddim | G major | 74 | 4/4 | A roots song in G major with a one-drop drummer and a dub bass. |
| rnb | [rnb.yaml](rnb/rnb.yaml) | Velvet After Midnight | Ab major | 86 | 4/4 | A slow-jam in Ab major on seventh chords, with a Rhodes and a singer. |
| rock | [rock.yaml](rock/rock.yaml) | Highway Sixty Nights | A mixolydian | 132 | 4/4 | A riff-driven classic rock song in A mixolydian with a singer. |
| ska | [ska.yaml](ska/ska.yaml) | Two Tone Tuesday | Bb major | 158 | 4/4 | An upbeat two-tone song in Bb major with a singer. |
| soft_rock | [soft-rock.yaml](soft_rock/soft-rock.yaml) | Harbor Lights Again | D major | 84 | 4/4 | A mid-tempo ballad in D major with acoustic guitar and a singer. |
| soul | [soul.yaml](soul/soul.yaml) | Sweet Mercy Street | C major | 104 | 4/4 | A Stax-style song in C major with an organ, a singer, and a key change. |
| techno | [techno.yaml](techno/techno.yaml) | Concrete Pulse | A minor | 130 | 4/4 | A hypnotic A minor track at 130 BPM built on a four-on-the-floor kit. |
