"""Harness around Chatterbox TTS for Voice Maker.

Keeps the model weights in a local folder next to the app, loads the model once,
caches the reference voice so each phrase only runs generation, splits long text
into sentences, and writes MP3s with ffmpeg.

Command line use (handy for testing without the GUI):
    python chatterbox_harness.py download
    python chatterbox_harness.py say --ref reference.wav --out hello.mp3 "Hello there!"
"""

import argparse
import os
import re
import shutil
import subprocess
import sys

import numpy as np

FROZEN = getattr(sys, "frozen", False)  # True when running as the packaged .exe
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if FROZEN:
    # Keep the big model and scratch files in the user's profile, not next to the .exe.
    DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "VoiceMaker")
else:
    DATA_DIR = APP_DIR
MODEL_DIR = os.path.join(DATA_DIR, "models", "chatterbox")
REPO_ID = "ResembleAI/chatterbox"
MODEL_FILES = ["ve.safetensors", "t3_cfg.safetensors", "s3gen.safetensors", "tokenizer.json", "conds.pt"]

# Chatterbox stops after ~1000 speech tokens (about 40 s), so long text is spoken in chunks.
MAX_CHUNK_CHARS = 250
CHUNK_GAP_SECONDS = 0.25


def model_is_downloaded(model_dir=MODEL_DIR):
    return all(os.path.exists(os.path.join(model_dir, f)) for f in MODEL_FILES)


def download_model(model_dir=MODEL_DIR, log=print):
    """Fetch the Chatterbox weights from Hugging Face into model_dir (skips files already there)."""
    from huggingface_hub import hf_hub_download

    os.makedirs(model_dir, exist_ok=True)
    for name in MODEL_FILES:
        if os.path.exists(os.path.join(model_dir, name)):
            continue
        log(f"Downloading {name}…")
        hf_hub_download(repo_id=REPO_ID, filename=name, local_dir=model_dir)
    log("Model files ready.")


def pick_device():
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def split_text(text, max_chars=MAX_CHUNK_CHARS):
    """Split text into sentence-sized chunks no longer than max_chars where possible."""
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return [text] if text else []
    sentences = re.split(r"(?<=[.!?;:])\s+", text)
    chunks, current = [], ""
    for sentence in sentences:
        # Very long sentences get broken at commas, then at spaces.
        pieces = [sentence]
        if len(sentence) > max_chars:
            pieces = re.split(r"(?<=,)\s+", sentence)
        for piece in pieces:
            while len(piece) > max_chars:
                cut = piece.rfind(" ", 0, max_chars)
                cut = cut if cut > 0 else max_chars
                chunks.append(piece[:cut].strip())
                piece = piece[cut:].strip()
            if current and len(current) + 1 + len(piece) > max_chars:
                chunks.append(current)
                current = piece
            else:
                current = f"{current} {piece}".strip()
    if current:
        chunks.append(current)
    return chunks


def ffmpeg_exe():
    """The bundled ffmpeg when packaged, otherwise ffmpeg from PATH (None if missing)."""
    name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    bundled = os.path.join(getattr(sys, "_MEIPASS", APP_DIR), name)
    return bundled if os.path.exists(bundled) else shutil.which("ffmpeg")


def run_ffmpeg(args, input=None):
    exe = ffmpeg_exe()
    if not exe:
        raise RuntimeError("ffmpeg was not found.")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0  # no console flash on Windows
    result = subprocess.run(
        [exe, "-y", "-loglevel", "error", *args], input=input, capture_output=True, creationflags=flags
    )
    if result.returncode != 0:
        raise RuntimeError("ffmpeg failed:\n" + result.stderr.decode(errors="replace")[-1500:])


def save_mp3(audio, sample_rate, mp3_path, bitrate="192k"):
    """Write a mono float waveform (-1..1) to an MP3 using ffmpeg."""
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2").tobytes()
    os.makedirs(os.path.dirname(os.path.abspath(mp3_path)), exist_ok=True)
    run_ffmpeg(
        [
            "-f", "s16le", "-ar", str(sample_rate), "-ac", "1", "-i", "pipe:0",
            "-codec:a", "libmp3lame", "-b:a", bitrate,
            mp3_path,
        ],
        input=pcm,
    )


def decode_audio(path, sample_rate=24000):
    """Decode any audio file to mono float32 at sample_rate with ffmpeg."""
    exe = ffmpeg_exe()
    if not exe:
        raise RuntimeError("ffmpeg was not found.")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    out = subprocess.run(
        [exe, "-loglevel", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(sample_rate), "pipe:1"],
        capture_output=True, check=True, creationflags=flags,
    ).stdout
    return np.frombuffer(out, dtype=np.float32)


def keep_loudest_parts(wav_path, out_path, max_seconds=5.0, below_peak_db=15.0, gap_seconds=0.15,
                       sample_rate=24000):
    """Save only the loud stretches of a clip, joined by short gaps (at most max_seconds).

    Made for animal clips: a cat's yowls with quiet humming in between. Chatterbox copies the
    delivery of its reference, so the humming would otherwise come out as moaning.
    """
    import wave

    audio = decode_audio(wav_path, sample_rate)
    hop = sample_rate // 50  # 20 ms
    frames = len(audio) // hop
    if frames == 0:
        raise ValueError("The reference clip is empty.")
    rms = np.sqrt(np.mean(audio[: frames * hop].reshape(frames, hop) ** 2, axis=1) + 1e-12)
    db = 20 * np.log10(rms)
    smooth = np.convolve(db, np.ones(5) / 5, mode="same")
    loud = smooth > smooth.max() - below_peak_db
    # Group loud frames into stretches of at least 0.2 s, padded by 40 ms on each side.
    parts, start = [], None
    for i, on in enumerate(np.append(loud, False)):
        if on and start is None:
            start = i
        elif not on and start is not None:
            if i - start >= 10:
                parts.append((max(0, (start - 2) * hop), min(len(audio), (i + 2) * hop)))
            start = None
    if not parts:
        parts = [(0, len(audio))]
    gap = np.zeros(int(gap_seconds * sample_rate), dtype=np.float32)
    pieces, total = [], 0
    limit = int(max_seconds * sample_rate)
    for a, b in parts:
        piece = audio[a:b][: limit - total]
        if pieces:
            pieces.append(gap)
        pieces.append(piece)
        total += len(piece) + len(gap)
        if total >= limit:
            break
    out = np.concatenate(pieces)
    out = out / (np.max(np.abs(out)) or 1.0) * 0.9
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with wave.open(out_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes((out * 32767).astype("<i2").tobytes())
    return out_path


class VoiceCloner:
    """Loads Chatterbox once and speaks text in the voice of a reference clip."""

    def __init__(self, device=None, model_dir=MODEL_DIR, log=print):
        self.device = device
        self.model_dir = model_dir
        self.log = log
        self.model = None
        self._reference = None  # (path, mtime) of the clip the cached voice came from

    @property
    def sample_rate(self):
        return self.model.sr

    def load(self):
        if self.model is not None:
            return
        if not model_is_downloaded(self.model_dir):
            self.log("Chatterbox model not found locally, downloading (a few GB, first run only)…")
            download_model(self.model_dir, log=self.log)
        from chatterbox.tts import ChatterboxTTS

        self.device = self.device or pick_device()
        self.log(f"Loading Chatterbox on {self.device}…")
        self.model = ChatterboxTTS.from_local(self.model_dir, self.device)
        self.log("Chatterbox loaded.")

    def set_reference(self, wav_path, exaggeration=0.5, loud_parts_only=False):
        """Analyse the reference clip once; later phrases reuse the result.

        loud_parts_only: use only the clip's loudest stretches (a cat's yowls) as the voice.
        """
        self.load()
        key = (os.path.abspath(wav_path), os.path.getmtime(wav_path), loud_parts_only)
        if key != self._reference:
            if loud_parts_only:
                self.log("Keeping only the loudest parts of the reference…")
                wav_path = keep_loudest_parts(wav_path, os.path.join(DATA_DIR, "work", "reference_loud.wav"))
            self.log("Analysing reference voice…")
            self.model.prepare_conditionals(wav_path, exaggeration=exaggeration)
            self._reference = key

    def speak(self, text, exaggeration=0.5, cfg_weight=0.5, temperature=0.8, legato=None, cat_sounds=None,
              accent=None):
        """Return a mono float32 waveform at self.sample_rate for text.

        legato: name of a cat_legato preset ("legato", "meow", "kitten") or None for plain speech.
        cat_sounds: optional {"purr": 0..1, "trill": 0..1, "chirp": 0..1} added on top of the preset.
        accent: None, or a cat_accent strength ("light", "medium", "strong") to respell the text with first
        ("river" -> "rriwerr").
        """
        if accent:
            from cat_accent import cat_accent

            text = cat_accent(text, accent)
            self.log(f"Cat accent: {text}")
        if cat_sounds and any(cat_sounds.values()) and not legato:
            legato = "legato"
        if self._reference is None:
            raise RuntimeError("Call set_reference() with a voice clip first.")
        import torch

        if legato:
            from cat_legato import PRESETS, legato as hum_through

            settings = {**PRESETS[legato], **(cat_sounds or {})}
            # One sentence at a time so the pauses between sentences survive the effect
            # ("..." from the cat accent stays inside its sentence).
            chunks = [piece for sentence in re.split(r"(?<=[^.][.!?])\s+", text) for piece in split_text(sentence)]
        else:
            chunks = split_text(text)
        parts = []
        gap = np.zeros(int(self.sample_rate * CHUNK_GAP_SECONDS), dtype=np.float32)
        for chunk in chunks:
            with torch.inference_mode():
                wav = self.model.generate(
                    chunk,
                    exaggeration=exaggeration,
                    cfg_weight=cfg_weight,
                    temperature=temperature,
                )
            wav = wav.squeeze().cpu().numpy().astype(np.float32)
            if legato:
                self.log("Applying cat legato…")
                wav = hum_through(wav, self.sample_rate, **settings)
            if parts:
                parts.append(gap)
            parts.append(wav)
        if not parts:
            raise ValueError("Nothing to say: the text is empty.")
        return np.concatenate(parts)

    def speak_to_mp3(self, text, mp3_path, **kwargs):
        save_mp3(self.speak(text, **kwargs), self.sample_rate, mp3_path)
        return mp3_path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Chatterbox voice cloning harness")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("download", help="download the model weights into ./models/chatterbox")
    say = sub.add_parser("say", help="speak text in the voice of a reference clip")
    say.add_argument("text")
    say.add_argument("--ref", required=True, help="reference voice clip (wav/mp3)")
    say.add_argument("--out", required=True, help="output MP3 path")
    say.add_argument("--device", choices=["cuda", "mps", "cpu"])
    say.add_argument("--model-dir", default=MODEL_DIR)
    say.add_argument("--exaggeration", type=float, default=0.5)
    say.add_argument("--cfg-weight", type=float, default=0.5)
    say.add_argument("--loud-parts-only", action="store_true",
                     help="use only the reference's loudest stretches, e.g. a cat's yowls without the humming")
    say.add_argument("--legato", choices=["legato", "meow", "kitten"], help="hum through word gaps (cat voice)")
    say.add_argument("--cat-accent", nargs="?", const="medium", choices=["light", "medium", "strong"],
                     help="respell the text the way a cat would say it (default strength: medium)")
    for sound in ("purr", "trill", "chirp"):
        say.add_argument(f"--{sound}", type=float, default=0.0, help=f"0..1 amount of cat {sound}s (implies --legato)")
    args = parser.parse_args(argv)

    if args.cmd == "download":
        download_model()
        return 0
    cloner = VoiceCloner(device=args.device, model_dir=args.model_dir)
    cloner.set_reference(args.ref, exaggeration=args.exaggeration, loud_parts_only=args.loud_parts_only)
    cloner.speak_to_mp3(args.text, args.out, exaggeration=args.exaggeration, cfg_weight=args.cfg_weight,
                        legato=args.legato, cat_sounds={"purr": args.purr, "trill": args.trill, "chirp": args.chirp},
                        accent=args.cat_accent)
    print(f"Saved {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
