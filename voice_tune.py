"""Voice tuning: find settings for a saved voice that keep the cat hum but say words people can follow.

Each candidate below is a set of settings, from the most cat-like to the plainest. Every one keeps
the legato hum, so the voice still rises and falls without gaps. For each candidate a few test
lines are spoken with a couple of seeds, and the speech-to-text check (intelligibility.py) scores
how many words it makes out. The most cat-like candidate that reaches the target wins (or the
clearest one, if none does). Its settings and best seed are saved to the voice, along with
tries=3 so later lines are also picked from three takes.

Command line (through voice_maker.py or VoiceMaker.exe):
    voice tune Sarah --out-dir tuning
    voice tune --all --out-dir tuning
"""

import os

import voices as library
from chatterbox_harness import save_mp3

# Short, like the game's lines (2 to 4 words each).
TEST_LINES = [
    "Welcome, trader!",
    "Kneel to the Crown.",
    "Darling, move aside.",
    "Ejecting cargo!",
]
TARGET = 0.8  # average share of words understood that counts as clear enough
GENTLE = dict(accent=None, purr=0.2, trill=0.0, chirp=0.0)
CANDIDATES = [
    ("saved settings", {}),
    ("light accent", dict(accent="light")),
    ("no accent", dict(accent=None)),
    ("no accent, softer cat sounds", dict(accent=None, purr=0.4, trill=0.1, chirp=0.1)),
    ("gentle meow", dict(GENTLE, legato="meow", legato_params=dict(hum=0.5, slur=0.03, stretch=1.3))),
    ("calm gentle meow", dict(GENTLE, legato="meow", legato_params=dict(hum=0.5, slur=0.03, stretch=1.3),
                              exaggeration=0.3, cfg_weight=0.3)),
    ("hummed speech", dict(GENTLE, legato="legato", exaggeration=0.35, cfg_weight=0.5)),
    ("calm hummed speech", dict(GENTLE, legato="legato", legato_params=dict(hum=0.4), exaggeration=0.25,
                                cfg_weight=0.3)),
]


def tune(cloner, voice, out_dir=None, lines=TEST_LINES, seeds=2, candidates=None, target=TARGET, save=True,
         log=print):
    """Try the candidates on voice; returns (label, settings, seed, score, report lines).

    With out_dir, the winner's takes are saved there as <voice>/<n>.mp3 plus report.txt.
    """
    from intelligibility import Judge

    judge = getattr(cloner, "judge", None) or Judge(device=cloner.device, log=log)
    cloner.judge = judge
    cloner.set_reference(voice["reference"], exaggeration=voice["settings"]["exaggeration"])
    base_seed = voice["settings"]["seed"] or 1000
    results, report = [], []
    for label, change in (candidates or CANDIDATES):
        settings = {**voice["settings"], **change, "tries": 1}
        if not settings["legato"]:
            settings["legato"] = "legato"  # always keep the hum
        kwargs = library.speak_kwargs(settings)
        pitch = kwargs.pop("pitch")
        per_seed = []
        for k in range(seeds):
            seed = base_seed + 101 * k
            total, takes = 0.0, []
            for line in lines:
                wav = cloner.speak_variants(line, [pitch], **{**kwargs, "seed": seed})[pitch]
                score, heard = judge.score(wav, cloner.sample_rate, library.cat_text(line, settings))
                total += score
                takes.append((line, wav, score, heard))
            per_seed.append((total / len(lines), seed, takes))
        mean = sum(s for s, _, _ in per_seed) / len(per_seed)
        best_score, best_seed, best_takes = max(per_seed, key=lambda r: r[0])
        results.append((label, settings, mean, best_seed, best_takes))
        report.append(f"{label}: {mean:.0%} understood (best seed {best_seed}: {best_score:.0%})")
        for line, _, score, heard in best_takes:
            report.append(f"    {score:.0%}  {line!r} heard as {heard!r}")
        log(report[-len(best_takes) - 1])
    clear = [r for r in results if r[2] >= target]
    label, settings, mean, seed, takes = clear[0] if clear else max(results, key=lambda r: r[2])
    report.append(f"Picked: {label} ({mean:.0%})" + ("" if clear else f", nothing reached {target:.0%}"))
    if save:
        keep = {k: settings[k] for k in library.DEFAULT_SETTINGS if k != "gender"}
        library.update_settings(voice["name"], **{**keep, "seed": seed, "tries": 3})
    if out_dir:
        folder = os.path.join(out_dir, library.slugify(voice["name"]))
        os.makedirs(folder, exist_ok=True)
        for n, (line, wav, score, heard) in enumerate(takes, 1):
            save_mp3(wav, cloner.sample_rate, os.path.join(folder, f"{n}.mp3"))
        with open(os.path.join(folder, "report.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(report) + "\n")
    log(report[-1])
    return label, settings, seed, mean, report
