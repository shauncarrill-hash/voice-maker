"""Voice pack: every line of a game in every saved voice, at several pitches, plus a manifest.

Each line is spoken once per voice (with the voice's settings and seed) and the pitch variants
are made from that same take, so "Long Johnson -4" and "Long Johnson +8" say a line the same way,
just lower or higher, and extra pitches cost almost no time.

Lines file: a CSV with an id and a text column (a header row "id,text" is optional), or a plain
text file with one line per row (ids are then made from the text). The id is what the game uses
to find a recording, so keep it when the wording changes.

Output in out_dir:
    <voice>/<pitch>/<id>.ogg      e.g. long_johnson/+4/shop_greet_01.ogg
    manifest.json                 voices (name, gender, pitches) and every line's text and files

Running it again only renders what is missing or changed (new lines, edited text, changed voice
settings), so it can be stopped and restarted.

Command line (through voice_maker.py or VoiceMaker.exe):
    pack lines.csv --out-dir voice_pack
    pack lines.csv --out-dir voice_pack --pitches -8 -4 0 4 8 --voices "Long Johnson" Tabby --format ogg
"""

import csv
import hashlib
import json
import os
import re
import time
import zlib

import voices as library
from chatterbox_harness import save_audio

DEFAULT_PITCHES = (-8, -4, 0, 4, 8)
FORMATS = ("ogg", "mp3", "wav")
SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


def read_lines(path):
    """Return [(id, text)] from a CSV (id,text) or a plain text file (one line per row)."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        content = f.read()
    rows = []
    if path.lower().endswith(".csv"):
        for row in csv.reader(content.splitlines()):
            if len(row) < 2 or not row[0].strip() or row[0].startswith("#"):
                continue
            if not rows and [c.strip().lower() for c in row[:2]] == ["id", "text"]:
                continue  # header
            rows.append((row[0].strip(), ",".join(row[1:]).strip()))
    else:
        for line in content.splitlines():
            text = line.strip()
            if text and not text.startswith("#"):
                slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:40] or "line"
                rows.append((f"{slug}_{zlib.crc32(text.encode()):08x}"[:52], text))
    seen = set()
    for line_id, text in rows:
        if not SAFE_ID.match(line_id):
            raise ValueError(f"Line id {line_id!r} can only use letters, digits, _ . and -")
        if line_id in seen:
            raise ValueError(f"Line id {line_id!r} is used twice in {path}")
        if not text:
            raise ValueError(f"Line {line_id!r} has no text")
        seen.add(line_id)
    return rows


def pitch_folder(pitch):
    return f"{pitch:+d}" if pitch else "0"


def voice_seed(voice):
    """The voice's saved seed, or a fixed one made from its name so re-runs repeat."""
    return voice["settings"]["seed"] or zlib.crc32(voice["name"].encode()) % 1_000_000 + 1


def _take_hash(text, voice, seed):
    settings = {k: v for k, v in voice["settings"].items() if k != "gender"}
    blob = json.dumps([text, settings, seed, os.path.getmtime(voice["reference"])], sort_keys=True)
    return hashlib.sha1(blob.encode()).hexdigest()[:12]


def make_pack(cloner, lines, out_dir, voices=None, pitches=DEFAULT_PITCHES, fmt="ogg", force=False, log=print):
    """Render lines ([(id, text)]) in every voice and pitch; returns the manifest path."""
    voices = voices if voices is not None else library.list_voices()
    if not voices:
        raise RuntimeError("No saved voices yet. Save some voices first.")
    if fmt not in FORMATS:
        raise ValueError(f"Format must be one of {', '.join(FORMATS)}")
    pitches = sorted({int(p) for p in pitches})
    os.makedirs(out_dir, exist_ok=True)
    manifest_path = os.path.join(out_dir, "manifest.json")
    old = {}
    if os.path.exists(manifest_path) and not force:
        with open(manifest_path, encoding="utf-8") as f:
            old = json.load(f).get("lines", {})

    manifest = {"format": fmt, "pitches": pitches, "voices": [], "lines": {}}
    for line_id, text in lines:
        manifest["lines"][line_id] = {"text": text, "files": {}}
    for voice in voices:
        slug = library.slugify(voice["name"])
        manifest["voices"].append({
            "name": voice["name"], "id": slug, "gender": voice["settings"].get("gender"), "seed": voice_seed(voice),
            "variants": [{"id": f"{slug}_{pitch_folder(p)}", "pitch": p, "folder": f"{slug}/{pitch_folder(p)}"}
                         for p in pitches],
        })

    def save_manifest():
        tmp = manifest_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        os.replace(tmp, manifest_path)

    total, done, rendered, spent = len(voices) * len(lines), 0, 0, 0.0
    for voice in voices:
        slug, seed = library.slugify(voice["name"]), voice_seed(voice)
        base_pitch = voice["settings"]["pitch"]
        reference_set = False
        for line_id, text in lines:
            done += 1
            take = _take_hash(text, voice, seed)
            entries = {}
            for p in pitches:
                rel = f"{slug}/{pitch_folder(p)}/{line_id}.{fmt}"
                entries[f"{slug}_{pitch_folder(p)}"] = {"path": rel, "pitch": p, "take": take}
            previous = old.get(line_id, {}).get("files", {})
            if all(previous.get(k, {}).get("take") == take and os.path.exists(os.path.join(out_dir, e["path"]))
                   for k, e in entries.items()):
                for k, e in entries.items():
                    e["seconds"] = previous[k].get("seconds")
                manifest["lines"][line_id]["files"].update(entries)
                continue
            if not reference_set:
                cloner.set_reference(voice["reference"], exaggeration=voice["settings"]["exaggeration"])
                reference_set = True
            started = time.time()
            kwargs = library.speak_kwargs(voice["settings"])
            kwargs.pop("pitch")
            kwargs["seed"] = seed
            takes = cloner.speak_variants(text, [base_pitch + p for p in pitches], **kwargs)
            for (k, e), p in zip(entries.items(), pitches):
                wav = takes[base_pitch + p]
                save_audio(wav, cloner.sample_rate, os.path.join(out_dir, e["path"]))
                e["seconds"] = round(len(wav) / cloner.sample_rate, 2)
            manifest["lines"][line_id]["files"].update(entries)
            save_manifest()
            spent += time.time() - started
            rendered += 1
            left = (total - done) * spent / rendered  # assumes the rest still need rendering
            log(f"{voice['name']} {done}/{total}: {line_id}  (about {left / 60:.0f} min left)")
    save_manifest()
    return manifest_path
