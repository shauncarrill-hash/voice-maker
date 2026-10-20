"""Intelligibility check: how many of a take's words a listener would make out.

A small speech-to-text model (Whisper base.en, about 300 MB, fetched once into the models folder)
writes down what it hears, and the take scores the share of the intended words it got, from 0
(nothing recognisable) to 1 (every word). Extra words count against it too, so babble and repeats
score lower. Cat voices need not score 1: a take a person understands usually scores 0.6 or more.

Used to pick the clearest of several takes (VoiceCloner.speak_variants tries=) and to tune a
saved voice's settings (voices.py "voice tune").

Command line: python intelligibility.py take.mp3 "the words it should say"
"""

import difflib
import os
import re

import numpy as np

from chatterbox_harness import DATA_DIR, decode_audio, pick_device

MODEL_ID = "openai/whisper-base.en"
MODEL_DIR = os.path.join(DATA_DIR, "models", "whisper-base.en")
MODEL_FILES = ["config.json", "generation_config.json", "model.safetensors", "preprocessor_config.json",
               "tokenizer.json", "tokenizer_config.json", "vocab.json", "merges.txt", "special_tokens_map.json",
               "added_tokens.json", "normalizer.json"]
NUMBERS = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six",
           "7": "seven", "8": "eight", "9": "nine", "10": "ten"}


def words(text):
    """Lowercase words without punctuation, "it's" -> "its", digits spelled out."""
    found = re.findall(r"[a-z0-9']+", text.lower().replace("-", " "))
    return [NUMBERS.get(w, w) for w in (w.replace("'", "") for w in found) if w]


def match(heard, meant):
    """0..1: how well the words heard match the words meant (order matters, extra words count against)."""
    a, b = words(heard), words(meant)
    if not b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


class Judge:
    """Loads Whisper once and scores takes."""

    def __init__(self, device=None, model_dir=MODEL_DIR, log=print):
        self.device = device
        self.model_dir = model_dir
        self.log = log
        self.model = None

    def load(self):
        if self.model is not None:
            return
        if not all(os.path.exists(os.path.join(self.model_dir, f)) for f in MODEL_FILES):
            from huggingface_hub import hf_hub_download

            self.log("Downloading the speech checker (about 300 MB, first time only)…")
            os.makedirs(self.model_dir, exist_ok=True)
            for name in MODEL_FILES:
                if not os.path.exists(os.path.join(self.model_dir, name)):
                    hf_hub_download(repo_id=MODEL_ID, filename=name, local_dir=self.model_dir)
        from transformers import WhisperForConditionalGeneration, WhisperProcessor

        self.device = self.device or pick_device()
        self.processor = WhisperProcessor.from_pretrained(self.model_dir)
        self.model = WhisperForConditionalGeneration.from_pretrained(self.model_dir).to(self.device).eval()

    def transcribe(self, audio, sample_rate):
        """What Whisper hears in a mono float waveform."""
        import torch

        self.load()
        audio = np.asarray(audio, dtype=np.float32).reshape(-1)
        if sample_rate != 16000 and len(audio):
            n = int(len(audio) * 16000 / sample_rate)
            audio = np.interp(np.linspace(0, len(audio) - 1, n), np.arange(len(audio)), audio).astype(np.float32)
        if len(audio) < 1600:
            return ""
        features = self.processor(audio[: 30 * 16000], sampling_rate=16000, return_tensors="pt").input_features
        with torch.inference_mode():
            ids = self.model.generate(features.to(self.device), max_new_tokens=120)
        return self.processor.batch_decode(ids, skip_special_tokens=True)[0].strip()

    def score(self, audio, sample_rate, text):
        """(0..1 score, what was heard) for a take that should say text."""
        heard = self.transcribe(audio, sample_rate)
        return match(heard, text), heard


if __name__ == "__main__":
    import sys

    path, text = sys.argv[1], " ".join(sys.argv[2:])
    s, heard = Judge().score(decode_audio(path, 24000), 24000, text)
    print(f"Heard: {heard}\nScore: {s:.2f}")
