"""Cat legato: turn normal speech into a gap-free, hummed, meow-like delivery.

Chatterbox speaks like a person: short silences between words, unvoiced
consonants and a lively pitch contour. The target style keeps the voice
humming through every word boundary, so this module re-synthesises the speech
with the WORLD vocoder and, inside each phrase:

* shortens pauses and fills them with a quiet hum that glides between the
  pitch and timbre of the neighbouring words,
* keeps the voice pitched through consonants (part noise, part hum),
* evens out the pitch and gives every syllable a small "mew" fall, with quick
  glides between syllables instead of jumps,
* optionally raises pitch and formants for a smaller, more cat-like throat.

Pauses longer than PHRASE_GAP seconds are treated as sentence breaks and kept.

Command line:
    python cat_legato.py input.wav output.mp3 [--preset meow] [--pitch 4] ...
"""

import argparse
import os
import sys

import numpy as np

FRAME_MS = 5.0
SILENCE_DB = 40.0  # frames this far below the loud frames count as silence
PHRASE_GAP = 0.30  # pauses longer than this (seconds) stay as sentence breaks
FLUTTER_HZ = 26.0  # pulse rate of purrs and trills
PARAMS = ("pitch", "formant", "flatten", "fall", "hum", "bridge", "floor", "stretch", "slur", "purr", "trill", "chirp")

PRESETS = {
    # Closes gaps and hums through words, voice otherwise unchanged.
    "legato": dict(pitch=0.0, formant=1.0, flatten=0.3, fall=1.5, hum=0.5, bridge=0.04, floor=22.0,
                   stretch=1.0, slur=0.0),
    # Closer to the example: smoother, flatter melody with a mew on every syllable.
    "meow": dict(pitch=3.0, formant=1.10, flatten=0.6, fall=3.0, hum=0.7, bridge=0.03, floor=18.0,
                 stretch=1.6, slur=0.08),
    # Small cat: higher and brighter.
    "kitten": dict(pitch=7.0, formant=1.22, flatten=0.5, fall=4.0, hum=0.7, bridge=0.03, floor=18.0,
                   stretch=1.4, slur=0.06),
}


def _runs(mask):
    """(start, end) index pairs of the True runs in a boolean array."""
    padded = np.concatenate([[False], mask, [False]]).astype(int)
    edges = np.flatnonzero(np.diff(padded))
    return list(zip(edges[::2], edges[1::2]))


def _smooth(values, frames):
    if frames <= 1:
        return values
    kernel = np.hanning(frames + 2)[1:-1]
    kernel /= kernel.sum()
    pad = frames // 2
    padded = np.pad(values, pad, mode="edge")
    return np.convolve(padded, kernel, mode="same")[pad:pad + len(values)]


def _smooth_rows(values, frames):
    """Moving average over rows (time), applied twice for a soft triangular window."""
    if frames <= 1 or len(values) < 2:
        return values
    pad = frames // 2
    for _ in range(2):
        padded = np.pad(values, ((pad, frames - pad), (0, 0)), mode="edge")
        csum = np.cumsum(padded, axis=0)
        values = (csum[frames:] - csum[:-frames]) / frames
    return values


def _warp_formants(sp, alpha):
    """Stretch each spectral envelope along frequency by alpha (>1 = smaller head)."""
    if abs(alpha - 1.0) < 1e-3:
        return sp
    bins = np.arange(sp.shape[1])
    src = np.clip(bins / alpha, 0, sp.shape[1] - 1)
    lo = np.floor(src).astype(int)
    hi = np.minimum(lo + 1, sp.shape[1] - 1)
    frac = src - lo
    log_sp = np.log(sp)
    return np.exp(log_sp[:, lo] * (1 - frac) + log_sp[:, hi] * frac)


def _syllable_bounds(energy_db, start, end, min_frames):
    """Split a phrase at dips in loudness; returns boundary indices including start/end."""
    env = _smooth(energy_db[start:end], 7)
    cuts = [0]
    for i in range(1, len(env) - 1):
        if env[i] <= env[i - 1] and env[i] < env[i + 1]:
            left = env[max(cuts[-1], i - 40):i].max(initial=env[i])
            right = env[i:i + 40].max(initial=env[i])
            if min(left, right) - env[i] >= 3.0 and i - cuts[-1] >= min_frames:
                cuts.append(i)
    if len(env) - cuts[-1] < min_frames and len(cuts) > 1:
        cuts.pop()
    cuts.append(len(env))
    return [start + c for c in cuts]


def shift_pitch(audio, sample_rate, semitones):
    """Raise (or lower, if negative) the voice by semitones, keeping its timbre."""
    import pyworld as pw

    x = np.asarray(audio, dtype=np.float64).reshape(-1)
    if not len(x) or not semitones:
        return np.asarray(audio, dtype=np.float32)
    f0, t = pw.harvest(x, sample_rate, f0_floor=60.0, f0_ceil=1000.0, frame_period=FRAME_MS)
    sp = pw.cheaptrick(x, f0, t, sample_rate)
    ap = pw.d4c(x, f0, t, sample_rate)
    y = pw.synthesize(f0 * 2.0 ** (semitones / 12.0), sp, ap, sample_rate, frame_period=FRAME_MS)[: len(x)]
    peak = np.abs(y).max()
    return (y * min(1.0, np.abs(x).max() / peak) if peak > 0 else y).astype(np.float32)


def legato(audio, sample_rate, pitch=0.0, formant=1.0, flatten=0.3, fall=1.5, hum=0.5,
           bridge=0.04, floor=22.0, stretch=1.0, slur=0.0, purr=0.0, trill=0.0,
           chirp=0.0, break_len=0.22):
    """Return the hummed, gap-free version of a mono float waveform (same sample rate).

    pitch: semitones up (negative = down). formant: envelope stretch, 1.1 = 10 % smaller vocal tract.
    flatten: 0 keeps the speaker's melody, 1 makes each phrase monotone (before the mew falls).
    fall: semitones each syllable glides down. hum: 0..1, how much consonants turn into hum.
    bridge: seconds of hum left where a short pause was. floor: dB the hum may dip below
    the phrase's loud parts. stretch: how much longer vowels are held (1.6 = 60 % longer).
    slur: seconds over which the timbre is smoothed, so vowels change shape less (0 = off).
    purr, trill, chirp: 0..1 extra cat sounds, see _cat_sounds.
    break_len: seconds of silence kept at sentence breaks.
    """
    import pyworld as pw

    x = np.asarray(audio, dtype=np.float64).reshape(-1)
    if not len(x):
        return np.zeros(0, dtype=np.float32)
    f0, t = pw.harvest(x, sample_rate, f0_floor=60.0, f0_ceil=1000.0, frame_period=FRAME_MS)
    sp = pw.cheaptrick(x, f0, t, sample_rate)
    ap = pw.d4c(x, f0, t, sample_rate)
    fps = 1000.0 / FRAME_MS

    energy_db = 10 * np.log10(sp.sum(axis=1) + 1e-20)
    loud = np.percentile(energy_db, 95)
    silent = energy_db < loud - SILENCE_DB

    # Rebuild the frame list: drop leading/trailing silence, shrink pauses.
    keep, breaks = [], []
    silent_runs = _runs(silent)
    if not silent_runs or silent_runs[0][0] > 0:
        silent_runs.insert(0, (0, 0))
    if silent_runs[-1][1] < len(silent):
        silent_runs.append((len(silent), len(silent)))
    for (_, prev_end), (a, b) in zip(silent_runs[:-1], silent_runs[1:]):
        keep.extend(range(prev_end, a))
        breaks.extend([False] * (a - prev_end))
        if b == len(silent):
            break  # trailing silence
        long_gap = (b - a) / fps > PHRASE_GAP
        n = min(b - a, int((break_len if long_gap else bridge) * fps))
        mid = (a + b - n) // 2
        keep.extend(range(mid, mid + n))
        breaks.extend([long_gap] * n)
    if not keep:
        return np.zeros(0, dtype=np.float32)
    keep = np.array(keep)
    breaks = np.array(breaks, dtype=bool)
    f0, sp, ap, silent, energy_db = f0[keep], sp[keep], ap[keep], silent[keep], energy_db[keep]

    new_f0 = np.zeros_like(f0)
    syllables = []  # (start, end, ends_phrase) frame ranges
    for p0, p1 in _runs(~breaks):
        seg = slice(p0, p1)
        voiced = f0[seg] > 0
        if voiced.sum() < 3:
            continue
        idx = np.arange(p0, p1)
        lf = np.log2(np.where(f0[seg] > 0, f0[seg], 1.0))
        # Pitch everywhere in the phrase, gliding across unvoiced and silent frames.
        lf = np.interp(idx, idx[voiced], lf[voiced])
        lf = _smooth(lf, 9)
        centre = np.median(lf[voiced])
        lf = centre + (lf - centre) * (1.0 - flatten)

        # A mew on each syllable: a quick lift at the onset, then a fall.
        bounds = _syllable_bounds(energy_db, p0, p1, int(0.09 * fps))
        syllables += [(s0, s1, s1 == p1) for s0, s1 in zip(bounds[:-1], bounds[1:])]
        contour = np.zeros(p1 - p0)
        for s0, s1 in zip(bounds[:-1], bounds[1:]):
            n = s1 - s0
            pos_in = np.linspace(0, 1, n)
            shape = np.where(pos_in < 0.15, pos_in / 0.15, 1 - (pos_in - 0.15) / 0.85)
            contour[s0 - p0:s1 - p0] = (shape * fall - fall * 0.4) / 12.0
        lf = lf + _smooth(contour, 7) + pitch / 12.0
        new_f0[seg] = 2.0 ** _smooth(lf, 7)

        # Hum through the gaps: borrow the neighbouring words' timbre at reduced level.
        log_sp = np.log(sp[seg])
        quiet = silent[seg]
        if quiet.any() and (~quiet).any():
            for b in range(log_sp.shape[1]):
                log_sp[quiet, b] = np.interp(idx[quiet], idx[~quiet], log_sp[~quiet, b])
        if slur > 0:
            # Let vowels hold their shape: smooth the timbre over time but keep each frame's loudness.
            energy = np.log(np.exp(log_sp).sum(axis=1, keepdims=True))
            log_sp = _smooth_rows(log_sp, max(1, int(slur * fps)))
            log_sp += energy - np.log(np.exp(log_sp).sum(axis=1, keepdims=True))
        # Keep the phrase from dropping more than `floor` dB below its loud parts.
        e = 10 * np.log10(np.exp(log_sp).sum(axis=1))
        target = np.percentile(e, 90) - floor
        lift = np.clip(target - e, 0, None)
        lift = _smooth(lift, 9)
        log_sp += (lift / 10 * np.log(10))[:, None]
        sp[seg] = np.exp(log_sp)

        # Consonants and bridges: mostly periodic so the voice keeps humming.
        a = ap[seg]
        unvoiced = ~voiced
        a[unvoiced] = a[unvoiced] * (1 - hum) + (a[unvoiced] * 0.15) * hum
        a[quiet] = np.minimum(a[quiet], 0.2)
        ap[seg] = a

    sp = _warp_formants(sp, formant)
    sp[breaks] = 1e-16
    if abs(stretch - 1.0) > 1e-3:
        # Hold the vowels longer, keep consonants and breaks at their own length.
        vowel = (f0 > 0) & ~silent & ~breaks
        weight = np.where(_smooth(vowel.astype(float), 5) > 0.5, stretch, 1.0)
        out_pos = np.concatenate([[0.0], np.cumsum(weight)[:-1]])
        src = np.interp(np.arange(0, out_pos[-1] + 1), out_pos, np.arange(len(weight)))
        lo = np.floor(src).astype(int)
        hi = np.minimum(lo + 1, len(weight) - 1)
        frac = (src - lo)[:, None]
        new_f0 = np.where(new_f0[lo] > 0, new_f0[lo], new_f0[hi])
        sp = np.exp(np.log(sp[lo]) * (1 - frac) + np.log(sp[hi]) * frac)
        ap = ap[lo] * (1 - frac) + ap[hi] * frac
        ends = np.append(out_pos, out_pos[-1] + weight[-1]).round().astype(int)
        syllables = [(ends[s0], ends[s1], last) for s0, s1, last in syllables]
    flutter = None
    if purr or trill or chirp:
        new_f0, ap, flutter = _cat_sounds(new_f0, ap, syllables, fps, purr, trill, chirp)
    y = pw.synthesize(new_f0, np.ascontiguousarray(sp), np.ascontiguousarray(np.clip(ap, 0.001, 0.999)),
                      sample_rate, FRAME_MS)
    if flutter is not None:
        # Rolled "brrr" sounds: a fast tremolo whose depth follows the per-frame flutter amount.
        depth = np.interp(np.arange(len(y)) / sample_rate, np.arange(len(flutter)) / fps, flutter)
        y *= 1 - depth * (0.5 + 0.5 * np.cos(2 * np.pi * FLUTTER_HZ * np.arange(len(y)) / sample_rate))
    peak = np.max(np.abs(y)) or 1.0
    return (y / peak * 0.89).astype(np.float32)


def _cat_sounds(f0, ap, syllables, fps, purr, trill, chirp):
    """Add purrs, trills and chirps. Returns (f0, ap, flutter depth per frame).

    purr: 0..1, a low, breathy rolled purr on the last syllable of each phrase plus a faint
    rumble throughout. trill / chirp: 0..1, the share of syllables that start with a rolled
    "brrp" rising into the vowel / a quick upward pitch flick ("mrrp?").
    """
    n = len(f0)
    voiced = f0 > 0
    lf = np.log2(np.where(voiced, f0, 1.0))
    ap = ap.copy()
    flutter = np.full(n, 0.2 * purr)
    rng = np.random.default_rng(n)  # same input, same result
    for s0, s1, last in syllables:
        s0, s1 = min(s0, n), min(s1, n)  # rounding after the vowel stretch can overshoot by a frame
        length = s1 - s0
        if length < 4:
            continue
        if trill and rng.random() < trill:
            k = min(length, int(0.13 * fps))
            fade = np.linspace(1, 0, k) ** 0.7
            flutter[s0:s0 + k] = np.maximum(flutter[s0:s0 + k], 0.85 * fade)
            lf[s0:s0 + k] += -4.0 / 12 * fade
        if chirp and rng.random() < chirp:
            k = min(length, int(0.15 * fps))
            lf[s0:s0 + k] += 7.0 / 12 * np.sin(np.linspace(0, np.pi, k))
        if purr and last:
            k = min(length, int(0.5 * fps))
            ramp = np.linspace(0, 1, k)
            flutter[s1 - k:s1] = np.maximum(flutter[s1 - k:s1], 0.9 * purr * ramp)
            lf[s1 - k:s1] -= 6.0 / 12 * purr * ramp
            ap[s1 - k:s1] = ap[s1 - k:s1] + (1 - ap[s1 - k:s1]) * (0.35 * purr * ramp)[:, None]
    flutter[~voiced] = 0
    return np.where(voiced, 2.0 ** _smooth(lf, 3), 0.0), ap, np.clip(_smooth(flutter, 5), 0, 0.95)


def load_audio(path, sample_rate=24000):
    """Decode any audio file to mono float32 with ffmpeg."""
    import subprocess

    from chatterbox_harness import ffmpeg_exe

    out = subprocess.run(
        [ffmpeg_exe(), "-loglevel", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(sample_rate), "pipe:1"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(out, dtype=np.float32)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Make speech hum through word gaps like a meowing cat")
    parser.add_argument("input")
    parser.add_argument("output", help=".mp3 or .wav")
    parser.add_argument("--preset", choices=sorted(PRESETS), default="meow")
    for name in PARAMS:
        parser.add_argument(f"--{name}", type=float)
    args = parser.parse_args(argv)

    settings = dict(PRESETS[args.preset])
    settings.update({k: v for k, v in vars(args).items() if k in PARAMS and v is not None})
    sr = 24000
    y = legato(load_audio(args.input, sr), sr, **settings)
    if args.output.lower().endswith(".wav"):
        import wave

        with wave.open(args.output, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes((np.clip(y, -1, 1) * 32767).astype("<i2").tobytes())
    else:
        from chatterbox_harness import save_mp3

        save_mp3(y, sr, args.output)
    print(f"Saved {os.path.abspath(args.output)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
