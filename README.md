# Voice Maker

A small desktop app: paste a YouTube link, pick a start and end time, and it grabs that bit of audio as the reference voice for [Chatterbox TTS](https://github.com/resemble-ai/chatterbox). Then type phrases (one per line) and it saves each one as an MP3 in the cloned voice.

> Only clone voices you have permission to use, and use the results lawfully. Don't use it to impersonate or mislead people. Chatterbox adds an inaudible watermark to everything it generates.

## Download (Windows, no Python needed)

Get the latest build from the [Releases page](https://github.com/shauncarrill-hash/voice-maker/releases/tag/latest):

- **VoiceMaker-windows-cpu.zip** works on any Windows PC. Unzip it and run `VoiceMaker\VoiceMaker.exe`.
- **VoiceMaker-windows-nvidia.7z.001, .002, …** is much faster if you have an NVIDIA graphics card. Download every part into one folder, open the `.001` file with [7-Zip](https://www.7-zip.org/), extract, and run `VoiceMaker\VoiceMaker.exe`.

Everything (ffmpeg, the YouTube downloader, the AI engine) is inside. The voice model (about 3 GB) downloads to `%LOCALAPPDATA%\VoiceMaker` the first time you generate, and MP3s save to `Documents\Voice Maker` by default. If something goes wrong, `%LOCALAPPDATA%\VoiceMaker\voice_maker.log` has the details.

The builds are made by GitHub Actions (`.github/workflows/build-windows.yml`) on every push to `main`, using `voice_maker.spec`.

## Running from source

### Files

- `voice_maker.py`: the app window.
- `cat_accent.py`: the optional "Cat accent" text respelling.
- `cat_legato.py`: the optional "Cat legato" effect (WORLD vocoder via `pyworld`).
- `chatterbox_harness.py`: the Chatterbox integration. It downloads the model into `models/chatterbox/` next to the app, loads it once, analyses the reference clip once and reuses it for every phrase, splits long text into sentences, and writes MP3s.
- `setup.bat` / `setup.sh`: one-time setup (virtual environment, packages, model download).
- `run.bat`: starts the app on Windows.
- `voice_maker.spec`: PyInstaller recipe for the .exe.

### Setup

You need **Python 3.11** and **ffmpeg** on your PATH (`winget install ffmpeg`, `brew install ffmpeg`, or `sudo apt install ffmpeg python3-tk`).

**Windows:** double-click `setup.bat`, then `run.bat`. The setup installs the NVIDIA (CUDA) build of PyTorch, which also runs on CPU if you have no NVIDIA card.

**macOS / Linux:** `./setup.sh`, then `.venv/bin/python voice_maker.py`.

The setup downloads about 3 GB of model weights from Hugging Face once. If you skip that step, the app downloads them the first time you generate, or when you click **Download / load voice model**.

With an NVIDIA GPU each phrase takes a few seconds. On CPU it works but expect tens of seconds per phrase.

## Using it

1. Paste the YouTube link, enter start and end times (`1:05`, `01:02:03` or plain seconds like `65`), and click **Get reference clip**. 10 to 20 seconds of one person speaking clearly with no music works best (Chatterbox uses the first 10 seconds). You can also pick a local audio file instead.
2. Type phrases, one per line, and click **Generate MP3s**.
3. MP3s land in `output/` next to the script (change it with **Browse…**), named like `01_hello_there.mp3`.

**Sliders:** *Exaggeration* raises emotion and intensity (0.5 is neutral). *CFG / pace* at lower values (about 0.3) gives slower, more deliberate speech, which helps if the reference speaker talks fast.

**Cat legato:** post-processing for a cat-like, hummed delivery. The voice keeps humming through the gaps between words, holds vowels longer and slides down a little on each syllable, like a meow. *Legato* only closes the gaps, *Meow* is the full effect, and *Kitten* is higher and brighter. Pauses between sentences are kept. The tick boxes add extra cat sounds on top: a low rolled *purr* at the end of each sentence, *trills* (a rolled "brrp" rising into some syllables) and *chirps* (a quick upward pitch flick, "mrrp?"). On the command line add `--legato meow` (and `--purr 0.8 --trill 0.3 --chirp 0.25`), or run `python cat_legato.py in.mp3 out.mp3 --preset meow` on any recording (flags such as `--pitch 5 --stretch 2 --fall 4` fine-tune it).

**Cat clip:** tick this when the reference is an animal. It keeps only the clip's loudest stretches (a cat's yowls, joined into about 5 seconds) and drops the quiet humming between them, which Chatterbox would otherwise copy as moaning. It also selects Meow, all three cat sounds and the Medium accent, the combination that worked best with a cat's voice. On the command line it's `--loud-parts-only`.

**Cat accent:** respells the text before it is spoken, the way a cat's mouth would shape it, following what is known about cat vocal anatomy. Cats already make m, w, k, glottal catches, rolled trills and hisses, but their small, stiff lips can't seal for p and b or reach the teeth for f and v. *Light* holds long vowels, rolls the r, turns f into h and v into w, adds a glottal catch before vowel-initial words and turns commas into pauses. *Medium* (the usual choice) also turns b and word-initial p into m, other p into a catch, and s, z, sh, ch and j into one hiss. *Strong* also turns th into d and l into w. With Medium, "the fish are sleeping in the river" becomes "the hish 'arre shleee'ing 'in the rriwerr". Preview any line with `python cat_accent.py --strength medium "your text"`, or add `--cat-accent medium` on the command line.

**Pitch:** the slider raises or lowers the voice in semitones (−12 to +12), keeping its timbre. It adds to the Meow and Kitten presets' own pitch and works with Cat legato off too. On the command line it's `--pitch 3` (or `--pitch -4`), and each saved voice remembers it.

**Seed:** Chatterbox makes every take a little different. Each MP3's name ends with the seed it used (`01_hello_there_seed48213.mp3`); type that number in the Seed box to get the same take again, and save or update a voice with it so the voice always uses it. Empty means a new random take each time. The same seed, phrase and settings give the same audio on the same computer; with a different phrase the seed keeps the delivery steadier but can't make it identical. On the command line it's `--seed 48213`.

**Best of N takes:** set "Best of" above 1 and Voice Maker makes that many takes of each sentence and keeps the one a speech-to-text check (Whisper, about 300 MB, downloaded the first time) understands best. The log shows what it heard and a score from 0 to 1. On the command line it's `--tries 3`; a saved voice remembers it.

**Tune a voice:** `voice tune Sarah --out-dir tuning` (or `voice tune --all`) tries eight sets of settings on four short game lines, from the most cat-like to the plainest. Every set keeps the legato hum, so the voice still rises and falls without going silent. It saves the most cat-like set that gets at least 80% of the words understood, along with the best seed and Best of 3, and writes the winning takes and a `report.txt` with every score to `tuning\<voice>`. Add `--dry-run` to only see the report.

**Easier words:** a small cat thesaurus swaps words a cat's mouth would struggle with (lots of p, b, f, v or th) for plain synonyms it can say, before the accent is applied: "Please sleep before the battle, my friends" becomes "Kindly doze before the war, my mates". Only words in its list change, and only for synonyms that fit wherever the word does. Preview with `python cat_thesaurus.py "your text"`, or add `--cat-words` on the command line.

**Stop at the last word** (on by default): Chatterbox sometimes keeps going after the text is done, pausing and then murmuring an echo of the last word. With this ticked, each line ends at its last word with a short fade. A long pause only counts as the end once the line has had time to be said, so pauses in the middle (such as "...") are kept. Untick it, or add `--keep-tail` on the command line, to keep everything.

**Clean up clip** (on by default): every downloaded clip gets a clean-up pass that repairs clipped, crunchy peaks, removes clicks and pops, cuts low rumble and high codec hiss, reduces background noise, trims silence at the ends and evens out the loudness. The untouched download is kept next to it as `reference_raw.wav`. Untick it to use the clip as downloaded; on the command line add `--raw` to `clip` or `voice add`.

**Saved voices:** once a reference clip sounds right, click *Save clip as a voice…* and give it a name. The clip is cleaned up (rumble and hiss removed, silence trimmed, loudness evened out) and stored with the current settings in a `voices` folder on your computer (next to the models: `%LOCALAPPDATA%\VoiceMaker\voices` for the .exe), never in the repo. Pick a voice from *Saved voice* to make it the reference and bring its settings back; *Remember these settings* updates them. *Generate with every saved voice* speaks your phrases in each voice, one folder per voice, so you can compare them.

## Game voice packs

*Make game voice pack…* (or `pack` on the command line) speaks every line of a game in every saved voice at several pitches, for a game that gives each character a voice: say 7 voices × pitches −8, −4, 0, +4 and +8 gives 35 voice/pitch combinations. Each line is spoken once per voice, with the voice's settings and seed, and the pitch variants are made from that same take, so every pitch says the line the same way and the extra pitches cost almost no time. Mark each voice male or female (*Gender* next to *Saved voice*, or `voice gender NAME female`) so the game can match a character's portrait.

The lines file is a CSV with an `id` and a `text` column, for example:

```csv
id,text
shop_greet_01,"Welcome to the station, pilot."
shop_buy_fuel,Fuel's loaded. Safe travels.
```

The id is what the game looks up, so keep it when you change the wording. (A plain text file with one line per row works too; ids are then made from the text.) The output folder gets `<voice>/<pitch>/<id>.ogg` (OGG Vorbis, which Godot imports directly; `--format mp3` or `wav` also work) and a `manifest.json` listing each voice's name, gender and pitch variants, and each line's text and file per variant with its length. Running it again only renders lines that are new or changed (or whose voice settings changed), so a long run can be stopped and restarted, and adding a line costs one take per voice.

```bash
.venv/bin/python voice_maker.py pack lines.csv --out-dir voice_pack
.venv/bin/python voice_maker.py pack lines.csv --out-dir voice_pack --pitches -8 -4 0 4 8 --voices "Long Johnson" Tabby
```

**Speakers:** give the lines CSV a `speaker` column and pass a speaker table (`--speakers speakers.csv`, or say yes when the app asks) to record each character only in its own voice. The table has `speaker_id,name,group,gender,voice,pitch` columns. A speaker with a voice (and optionally a pitch) gets its lines only in that voice and pitch. A shared speaker such as `pirates` is recorded in the voices of every speaker whose `group` it is. A speaker with voice `*`, or with no voice anywhere, is recorded in every voice and pitch, for characters the game gives a voice when they first speak (station masters). The manifest lists each line's speaker.

**A part at a time:** `--status existing` records only the lines whose `status` column says `existing` (say, the lines already in the game). The other lines keep any files they already have, and a later run without `--status` records the rest.

Each take is about 10 to 20 seconds on a mid-range NVIDIA card, so 300 lines in 7 voices is an overnight run. Close the Voice Maker window first if you run it from the command line: two copies of the model don't fit on an 8 GB card.

## Command line

The harness works without the window too:

```bash
.venv/bin/python chatterbox_harness.py download
.venv/bin/python chatterbox_harness.py say --ref work/reference.wav --out hello.mp3 "Hello there!"
```

Saved voices work from the command line too (`VoiceMaker.exe` takes the same commands):

```bash
.venv/bin/python voice_maker.py voice add "Long Johnson" --youtube "https://www.youtube.com/watch?v=kkwiQmGWK4c" 0:08 0:18 --cat-clip
.venv/bin/python voice_maker.py voice add "Tabby" --file tabby.wav --cat-clip --accent strong
.venv/bin/python voice_maker.py voice list
.venv/bin/python voice_maker.py say --voice "Long Johnson" --out hello.mp3 "Hello there!"
.venv/bin/python voice_maker.py compare --out-dir compare "Hello there little one."
```

`say --voice` uses the voice's saved settings; any flag you add (for example `--cat-accent strong`) overrides them for that run. `compare` writes one MP3 per voice; add `--voices "Tabby" "Long Johnson"` to pick some.

## Troubleshooting

- **YouTube download fails:** update yt-dlp (`.venv/bin/pip install -U yt-dlp`); YouTube changes often.
- **"ffmpeg was not found":** install ffmpeg and reopen your terminal.
- **Voice doesn't sound right:** try a cleaner clip with no background music or other voices.
