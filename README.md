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

**Cat legato:** post-processing for a cat-like, hummed delivery. The voice keeps humming through the gaps between words, holds vowels longer and slides down a little on each syllable, like a meow. *Legato* only closes the gaps, *Meow* is the full effect, and *Kitten* is higher and brighter. Pauses between sentences are kept. On the command line add `--legato meow`, or run `python cat_legato.py in.mp3 out.mp3 --preset meow` on any recording (flags such as `--pitch 5 --stretch 2 --fall 4` fine-tune it).

## Command line

The harness works without the window too:

```bash
.venv/bin/python chatterbox_harness.py download
.venv/bin/python chatterbox_harness.py say --ref work/reference.wav --out hello.mp3 "Hello there!"
```

## Troubleshooting

- **YouTube download fails:** update yt-dlp (`.venv/bin/pip install -U yt-dlp`); YouTube changes often.
- **"ffmpeg was not found":** install ffmpeg and reopen your terminal.
- **Voice doesn't sound right:** try a cleaner clip with no background music or other voices.
