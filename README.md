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

**Easier words:** a small cat thesaurus swaps words a cat's mouth would struggle with (lots of p, b, f, v or th) for plain synonyms it can say, before the accent is applied: "Please sleep before the battle, my friends" becomes "Kindly doze before the war, my mates". Only words in its list change, and only for synonyms that fit wherever the word does. Preview with `python cat_thesaurus.py "your text"`, or add `--cat-words` on the command line.

**Stop at the last word** (on by default): Chatterbox sometimes keeps going after the text is done, pausing and then murmuring an echo of the last word. With this ticked, each line ends at its last word with a short fade. A long pause only counts as the end once the line has had time to be said, so pauses in the middle (such as "...") are kept. Untick it, or add `--keep-tail` on the command line, to keep everything.

**Saved voices:** once a reference clip sounds right, click *Save clip as a voice…* and give it a name. The clip is cleaned up (rumble and hiss removed, silence trimmed, loudness evened out) and stored with the current settings in a `voices` folder on your computer (next to the models: `%LOCALAPPDATA%\VoiceMaker\voices` for the .exe), never in the repo. Pick a voice from *Saved voice* to make it the reference and bring its settings back; *Remember these settings* updates them. *Generate with every saved voice* speaks your phrases in each voice, one folder per voice, so you can compare them.

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
