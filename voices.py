"""Voice library: named voices saved from reference clips, each remembering its best settings.

Each voice is a folder in <data dir>/voices/<slug>/ holding reference.wav (cleaned up, and cut
down to the loudest stretches for a cat clip) and voice.json (name, where the clip came from,
and the generation settings). The folder stays on this computer; it is not part of the repo.

Command line (through voice_maker.py or VoiceMaker.exe):
    voice add "Long Johnson" --youtube URL 0:08 0:18 --cat-clip
    voice add "Tabby" --file tabby.wav --cat-clip --exaggeration 0.4
    voice list
    voice remove "Tabby"
    compare --out-dir compare "Hello there little one."
"""

import argparse
import json
import os
import random
import re
import shutil
import tempfile

from chatterbox_harness import DATA_DIR, clean_clip, keep_loudest_parts, run_ffmpeg, unused_path

VOICES_DIR = os.path.join(DATA_DIR, "voices")

DEFAULT_SETTINGS = dict(gender=None, exaggeration=0.5, cfg_weight=0.5, pitch=0.0, seed=None, legato=None, accent=None, thesaurus=False,
                        purr=0.0, trill=0.0, chirp=0.0)
# What worked best with a cat's voice: yowls only, Meow, all three cat sounds, Medium accent.
GENDERS = ("male", "female")
CAT_CLIP_SETTINGS = dict(legato="meow", accent="medium", purr=0.8, trill=0.3, chirp=0.25)

def slugify(name):
    return re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower() or "voice"


def save_voice(name, clip_path, cat_clip=False, source=None, clean=True, **settings):
    """Store clip_path as a named voice, cleaned up first unless clean=False (already done). Returns the voice."""
    folder = os.path.join(VOICES_DIR, slugify(name))
    os.makedirs(folder, exist_ok=True)
    reference = os.path.join(folder, "reference.wav")
    tmp = tempfile.mkdtemp(dir=folder)
    try:
        cleaned = os.path.join(tmp, "clean.wav")
        if clean:
            clean_clip(clip_path, cleaned)
        else:
            run_ffmpeg(["-i", clip_path, "-ac", "1", "-ar", "24000", cleaned])
        if cat_clip:
            keep_loudest_parts(cleaned, reference)
        else:
            shutil.move(cleaned, reference)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    chosen = {**DEFAULT_SETTINGS, **(CAT_CLIP_SETTINGS if cat_clip else {})}
    chosen.update({k: v for k, v in settings.items() if k in DEFAULT_SETTINGS and v is not None})
    voice = {"name": name, "cat_clip": cat_clip, "source": source or os.path.abspath(clip_path), "settings": chosen}
    with open(os.path.join(folder, "voice.json"), "w", encoding="utf-8") as f:
        json.dump(voice, f, indent=2)
    return _with_paths(voice, folder)


def update_settings(name, **settings):
    """Change a saved voice's remembered settings."""
    voice = get_voice(name)
    voice["settings"].update({k: v for k, v in settings.items() if k in DEFAULT_SETTINGS})
    stored = {k: voice[k] for k in ("name", "cat_clip", "source", "settings")}
    with open(os.path.join(voice["folder"], "voice.json"), "w", encoding="utf-8") as f:
        json.dump(stored, f, indent=2)
    return voice


def _with_paths(voice, folder):
    voice = {**voice, "settings": {**DEFAULT_SETTINGS, **voice["settings"]}}  # voices saved before a setting existed
    return {**voice, "folder": folder, "reference": os.path.join(folder, "reference.wav")}


def list_voices():
    voices = []
    if os.path.isdir(VOICES_DIR):
        for slug in sorted(os.listdir(VOICES_DIR)):
            meta = os.path.join(VOICES_DIR, slug, "voice.json")
            if os.path.exists(meta):
                with open(meta, encoding="utf-8") as f:
                    voices.append(_with_paths(json.load(f), os.path.join(VOICES_DIR, slug)))
    return voices


def get_voice(name):
    for voice in list_voices():
        if voice["name"].lower() == name.lower() or os.path.basename(voice["folder"]) == slugify(name):
            return voice
    raise KeyError(f"No saved voice called {name!r}. Saved voices: {', '.join(v['name'] for v in list_voices())}")


def remove_voice(name):
    shutil.rmtree(get_voice(name)["folder"])


def speak_kwargs(settings):
    """Turn a voice's settings into VoiceCloner.speak keyword arguments."""
    return dict(
        exaggeration=settings["exaggeration"],
        cfg_weight=settings["cfg_weight"],
        pitch=settings["pitch"],
        seed=settings["seed"],
        legato=settings["legato"],
        accent=settings["accent"],
        thesaurus=settings["thesaurus"],
        cat_sounds={k: settings[k] for k in ("purr", "trill", "chirp")},
    )


def speak_as(cloner, voice, text, mp3_path, **extra):
    """Speak text in a saved voice with its remembered settings (extra: more speak() arguments)."""
    cloner.set_reference(voice["reference"], exaggeration=voice["settings"]["exaggeration"])
    return cloner.speak_to_mp3(text, mp3_path, **{**speak_kwargs(voice["settings"]), **extra})


def render_all(cloner, text, out_dir, voices=None, log=print):
    """Say text in every saved voice; returns the MP3 paths (one per voice)."""
    voices = voices if voices is not None else list_voices()
    if not voices:
        raise RuntimeError("No saved voices yet. Save one first.")
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for voice in voices:
        log(f"Speaking as {voice['name']}…")
        seed = voice["settings"]["seed"] or random.randrange(1, 1_000_000)
        path = unused_path(os.path.join(out_dir, f"{slugify(voice['name'])}_seed{seed}.mp3"))
        paths.append(speak_as(cloner, voice, text, path, seed=seed))
    return paths


def main(argv, download=None):
    """voice add/list/remove and compare. download(url, start, end, out_wav) fetches a YouTube clip;
    start and end are timestamps as typed, e.g. "0:08"."""
    from chatterbox_harness import VoiceCloner

    parser = argparse.ArgumentParser(prog="voice", description="Saved voices")
    sub = parser.add_subparsers(dest="cmd", required=True)
    voice = sub.add_parser("voice", help="manage saved voices")
    vsub = voice.add_subparsers(dest="action", required=True)
    add = vsub.add_parser("add", help="save a clip as a named voice")
    add.add_argument("name")
    src = add.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", help="local audio file")
    src.add_argument("--youtube", nargs=3, metavar=("URL", "START", "END"), help="YouTube link and start/end times")
    add.add_argument("--cat-clip", action="store_true", help="keep only the yowls and use the cat settings")
    add.add_argument("--raw", action="store_true", help="skip the clean-up pass (declip, denoise, even loudness)")
    for key, value in DEFAULT_SETTINGS.items():
        flag = "--" + key.replace("_", "-")
        if key == "gender":
            add.add_argument(flag, choices=GENDERS, help="for a game picking voices to match a character")
        elif key in ("legato", "accent"):
            add.add_argument(flag)
        elif key == "seed":
            add.add_argument(flag, type=int, help="repeat takes: the seed of a take you liked")
        elif key == "thesaurus":
            add.add_argument("--cat-words", dest="thesaurus", action="store_const", const=True,
                             help="swap hard-to-say words for easier synonyms")
        else:
            add.add_argument(flag, type=float)
    vsub.add_parser("list", help="show saved voices")
    rm = vsub.add_parser("remove", help="delete a saved voice")
    rm.add_argument("name")
    gender = vsub.add_parser("gender", help="mark a saved voice male or female")
    gender.add_argument("name")
    gender.add_argument("gender", choices=GENDERS)
    pack = sub.add_parser("pack", help="every game line in every saved voice at several pitches, plus a manifest")
    pack.add_argument("lines", help="CSV with id,text columns, or a text file with one line per row")
    pack.add_argument("--out-dir", required=True)
    pack.add_argument("--pitches", nargs="+", type=int, default=[-8, -4, 0, 4, 8], help="semitones (default: -8 -4 0 4 8)")
    pack.add_argument("--voices", nargs="+", metavar="NAME", help="only these voices (default: all)")
    pack.add_argument("--format", choices=["ogg", "mp3", "wav"], default="ogg")
    pack.add_argument("--speakers", help="CSV of speaker_id,group,voice,pitch: record each speaker's lines in its voice")
    pack.add_argument("--force", action="store_true", help="render everything again, even lines already done")
    pack.add_argument("--status", help='only record lines whose status column is this (e.g. "existing"); the rest keep their files')
    compare = sub.add_parser("compare", help="say one line in every saved voice")
    compare.add_argument("text")
    compare.add_argument("--out-dir", required=True)
    compare.add_argument("--voices", nargs="+", metavar="NAME", help="only these voices (default: all)")
    compare.add_argument("--device", choices=["cuda", "mps", "cpu"])
    pack.add_argument("--device", choices=["cuda", "mps", "cpu"])
    args = parser.parse_args(argv)

    if args.cmd == "pack":
        import voice_pack

        chosen = [get_voice(n) for n in args.voices] if args.voices else None
        only = {i for i, _, _ in voice_pack.read_lines(args.lines, args.status)} if args.status else None
        path = voice_pack.make_pack(VoiceCloner(device=args.device), voice_pack.read_lines(args.lines), args.out_dir,
                                    chosen, args.pitches, args.format, args.force,
                                    speakers=voice_pack.read_speakers(args.speakers) if args.speakers else None,
                                    only=only)
        print(f"Saved {path}")
    elif args.cmd == "compare":
        chosen = [get_voice(n) for n in args.voices] if args.voices else None
        paths = render_all(VoiceCloner(device=args.device), args.text, args.out_dir, chosen)
        print("\n".join(f"Saved {p}" for p in paths))
    elif args.action == "list":
        for v in list_voices():
            print(f"{v['name']}: {v['source']}  {v['settings']}")
    elif args.action == "gender":
        update_settings(args.name, gender=args.gender)
        print(f"{args.name} is {args.gender}")
    elif args.action == "remove":
        remove_voice(args.name)
        print(f"Removed {args.name}")
    else:
        settings = {k: getattr(args, k) for k in DEFAULT_SETTINGS}
        if args.youtube:
            url, start, end = args.youtube
            tmp = tempfile.mkdtemp()
            try:
                clip = os.path.join(tmp, "clip.wav")
                download(url, start, end, clip)
                v = save_voice(args.name, clip, args.cat_clip, f"{url} {start}-{end}", clean=not args.raw, **settings)
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        else:
            v = save_voice(args.name, args.file, args.cat_clip, clean=not args.raw, **settings)
        print(f"Saved voice {v['name']} -> {v['reference']}")
    return 0
