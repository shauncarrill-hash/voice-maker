"""Render before/after samples of the cat legato effect with the real Chatterbox model.

    python tools/legato_samples.py samples/legato

Writes MP3s plus report.txt with gap/voicing numbers for each file.
"""

import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cat_legato import PRESETS, legato  # noqa: E402
from chatterbox_harness import CHUNK_GAP_SECONDS, MODEL_DIR, download_model, model_is_downloaded, save_mp3  # noqa: E402

TEXT = "Hello there, little one. The moon is out tonight, and the fish are sleeping in the river."
SETTINGS = dict(exaggeration=0.5, cfg_weight=0.5, temperature=0.8)


def stats(y, sr):
    """Share of 10 ms frames that are silent (< -35 dB) and longest silent run inside speech."""
    hop = sr // 100
    frames = len(y) // hop
    rms = np.sqrt(np.mean(y[: frames * hop].reshape(frames, hop) ** 2, axis=1) + 1e-12)
    db = 20 * np.log10(rms / rms.max())
    loud = np.flatnonzero(db > -35)
    inner = db[loud[0]: loud[-1] + 1]
    silent = inner < -35
    longest = run = 0
    for s in silent:
        run = run + 1 if s else 0
        longest = max(longest, run)
    return f"{len(y) / sr:5.2f} s, silent inside speech {silent.mean() * 100:4.1f} %, longest gap {longest * 10} ms"


def main(out_dir):
    import torch
    from chatterbox.tts import ChatterboxTTS

    os.makedirs(out_dir, exist_ok=True)
    if not model_is_downloaded():
        download_model()
    model = ChatterboxTTS.from_local(MODEL_DIR, "cpu")
    sr = model.sr
    gap = np.zeros(int(sr * CHUNK_GAP_SECONDS), dtype=np.float32)
    sentences = re.split(r"(?<=[.!?])\s+", TEXT)
    takes = []
    torch.manual_seed(1)
    for sentence in sentences:
        with torch.inference_mode():
            takes.append(model.generate(sentence, **SETTINGS).squeeze().cpu().numpy().astype(np.float32))

    def join(parts):
        return np.concatenate([p for part in parts for p in (gap, part)][1:])

    # Same Chatterbox takes before and after, processed a sentence at a time like the app does.
    variants = {"1_chatterbox": join(takes)}
    for n, preset in enumerate(("legato", "meow", "kitten"), 2):
        variants[f"{n}_chatterbox+{preset}"] = join([legato(t, sr, **PRESETS[preset]) for t in takes])
    lines = []
    for label, audio in variants.items():
        save_mp3(audio, sr, os.path.join(out_dir, label + ".mp3"))
        lines.append(f"{label:28s} {stats(audio, sr)}")
        print(lines[-1], flush=True)
    with open(os.path.join(out_dir, "report.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "samples/legato")
