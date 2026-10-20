"""Voice Maker: clone a voice from a YouTube clip with Chatterbox TTS and export phrases as MP3.

Flow:
  1. Paste a YouTube link, enter start and end timestamps, click "Get reference clip".
  2. Type phrases (one per line) and click "Generate MP3s".
"""

import os
import queue
import random
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

import voices
from chatterbox_harness import DATA_DIR, FROZEN, VoiceCloner, ffmpeg_exe, run_ffmpeg, unused_path

WORK_DIR = os.path.join(DATA_DIR, "work")
if FROZEN:
    DEFAULT_OUT_DIR = os.path.join(os.path.expanduser("~"), "Documents", "Voice Maker")
else:
    DEFAULT_OUT_DIR = os.path.join(DATA_DIR, "output")


# "Cat legato" post-processing (cat_legato.py): hums through the gaps between words.
LEGATO_CHOICES = ["Off", "Legato (close gaps)", "Meow", "Kitten (higher)"]
LEGATO_PRESETS = {"Off": None, "Legato (close gaps)": "legato", "Meow": "meow", "Kitten (higher)": "kitten"}
# "Cat accent" respelling (cat_accent.py) strengths.
ACCENT_CHOICES = ["Off", "Light", "Medium", "Strong"]
# Extra cat sounds (checkboxes) and how strongly each is applied.
CAT_SOUNDS = [("purr", "Purr at sentence ends", 0.8), ("trill", "Trills (brrp)", 0.3), ("chirp", "Chirps", 0.25)]


def parse_timestamp(text):
    """Turn '83', '83.5', '1:23' or '01:02:03.5' into seconds."""
    text = text.strip()
    if not text:
        raise ValueError("Timestamp is empty")
    parts = text.split(":")
    if len(parts) > 3:
        raise ValueError(f"Bad timestamp: {text}")
    seconds = 0.0
    for part in parts:
        if not re.fullmatch(r"\d+(\.\d+)?", part):
            raise ValueError(f"Bad timestamp: {text}")
        seconds = seconds * 60 + float(part)
    return seconds


def slugify(text, max_len=40):
    slug = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower()
    return slug[:max_len] or "phrase"


def download_clip(url, start, end, out_wav):
    """Download only [start, end] of the video's audio and save it as mono 24 kHz WAV."""
    import yt_dlp
    from yt_dlp.utils import download_range_func

    os.makedirs(os.path.dirname(out_wav), exist_ok=True)
    tmp_dir = tempfile.mkdtemp(dir=os.path.dirname(out_wav))
    try:
        options = {
            "format": "bestaudio/best",
            "noplaylist": True,
            "outtmpl": os.path.join(tmp_dir, "clip.%(ext)s"),
            "download_ranges": download_range_func(None, [(start, end)]),
            "force_keyframes_at_cuts": True,
            "ffmpeg_location": ffmpeg_exe(),
            "quiet": True,
            "noprogress": True,
        }
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.download([url])
        except yt_dlp.utils.DownloadError as exc:
            if "not a bot" not in str(exc) and "Sign in" not in str(exc):
                raise
            # YouTube sometimes wants a signed-in session; borrow cookies from a local browser.
            for browser in ("firefox", "edge", "chrome", "brave"):
                try:
                    with yt_dlp.YoutubeDL({**options, "cookiesfrombrowser": (browser,)}) as ydl:
                        ydl.download([url])
                    break
                except Exception:
                    continue
            else:
                raise RuntimeError(
                    "YouTube asked to confirm you're not a bot. Sign in to YouTube in Firefox or Edge, "
                    "close the browser, and try again. Or download the audio yourself and use "
                    "'Use a local audio file instead'."
                ) from exc
        files = os.listdir(tmp_dir)
        if not files:
            raise RuntimeError("The download finished but no audio file was saved.")
        run_ffmpeg([
            "-i", os.path.join(tmp_dir, files[0]),
            "-t", str(end - start),
            "-ac", "1", "-ar", "24000",
            out_wav,
        ])
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Voice Maker")
        self.root.minsize(620, 560)
        self.events = queue.Queue()
        self.cloner = VoiceCloner(log=self.set_status)
        self.reference_wav = None
        self.busy = False

        pad = {"padx": 8, "pady": 4}

        # Step 1: reference clip
        step1 = ttk.LabelFrame(root, text="1. Reference voice from YouTube")
        step1.pack(fill="x", **pad)
        ttk.Label(step1, text="YouTube link:").grid(row=0, column=0, sticky="w", **pad)
        self.url_var = tk.StringVar()
        ttk.Entry(step1, textvariable=self.url_var, width=60).grid(row=0, column=1, columnspan=3, sticky="we", **pad)
        ttk.Label(step1, text="Start (e.g. 1:05):").grid(row=1, column=0, sticky="w", **pad)
        self.start_var = tk.StringVar(value="0:00")
        ttk.Entry(step1, textvariable=self.start_var, width=12).grid(row=1, column=1, sticky="w", **pad)
        ttk.Label(step1, text="End (e.g. 1:20):").grid(row=1, column=2, sticky="w", **pad)
        self.end_var = tk.StringVar(value="0:15")
        ttk.Entry(step1, textvariable=self.end_var, width=12).grid(row=1, column=3, sticky="w", **pad)
        self.clip_btn = ttk.Button(step1, text="Get reference clip", command=self.on_get_clip)
        self.clip_btn.grid(row=2, column=0, sticky="w", **pad)
        ttk.Button(step1, text="Use a local audio file instead…", command=self.on_pick_local).grid(row=2, column=1, columnspan=2, sticky="w", **pad)
        self.ref_label = ttk.Label(step1, text="No reference clip yet. 10 to 20 seconds of clean speech works best.")
        self.ref_label.grid(row=3, column=0, columnspan=4, sticky="w", **pad)
        self.cat_clip_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            step1, text="Cat clip: use only the yowls, with Meow, all cat sounds and a Medium accent",
            variable=self.cat_clip_var, command=self.on_cat_clip,
        ).grid(row=4, column=0, columnspan=4, sticky="w", **pad)
        saved = ttk.Frame(step1)
        saved.grid(row=5, column=0, columnspan=4, sticky="w", **pad)
        ttk.Label(saved, text="Saved voice:").pack(side="left")
        self.voice_var = tk.StringVar()
        self.voice_box = ttk.Combobox(saved, textvariable=self.voice_var, state="readonly", width=28)
        self.voice_box.pack(side="left", padx=4)
        self.voice_box.bind("<<ComboboxSelected>>", lambda _: self.on_use_voice())
        self.save_voice_btn = ttk.Button(saved, text="Save clip as a voice…", command=self.on_save_voice)
        self.save_voice_btn.pack(side="left", padx=4)
        ttk.Button(saved, text="Remember these settings", command=self.on_update_voice).pack(side="left")
        self.refresh_voices()
        step1.columnconfigure(1, weight=1)

        # Step 2: phrases
        step2 = ttk.LabelFrame(root, text="2. Phrases to speak (one MP3 per line)")
        step2.pack(fill="both", expand=True, **pad)
        self.text = tk.Text(step2, height=8, wrap="word")
        self.text.pack(fill="both", expand=True, **pad)

        opts = ttk.Frame(step2)
        opts.pack(fill="x", **pad)
        ttk.Label(opts, text="Exaggeration").grid(row=0, column=0, sticky="w")
        self.exag_var = tk.DoubleVar(value=0.5)
        ttk.Scale(opts, from_=0.25, to=2.0, variable=self.exag_var, length=160).grid(row=0, column=1, padx=4)
        self.exag_lbl = ttk.Label(opts, width=5)
        self.exag_lbl.grid(row=0, column=2)
        ttk.Label(opts, text="CFG / pace").grid(row=0, column=3, sticky="w", padx=(16, 0))
        self.cfg_var = tk.DoubleVar(value=0.5)
        ttk.Scale(opts, from_=0.0, to=1.0, variable=self.cfg_var, length=160).grid(row=0, column=4, padx=4)
        self.cfg_lbl = ttk.Label(opts, width=5)
        self.cfg_lbl.grid(row=0, column=5)
        ttk.Label(opts, text="Pitch").grid(row=0, column=6, sticky="w", padx=(16, 0))
        self.pitch_var = tk.DoubleVar(value=0.0)
        ttk.Scale(opts, from_=-12.0, to=12.0, variable=self.pitch_var, length=140,
                  command=lambda v: self.pitch_var.set(round(float(v)))).grid(row=0, column=7, padx=4)
        self.pitch_lbl = ttk.Label(opts, width=7)
        self.pitch_lbl.grid(row=0, column=8)
        self.pitch_var.trace_add("write", lambda *_: self.pitch_lbl.config(text=f"{self.pitch_var.get():+.0f} st"))
        self.pitch_lbl.config(text="+0 st")
        ttk.Label(opts, text="Seed").grid(row=1, column=6, sticky="w", padx=(16, 0), pady=(6, 0))
        self.seed_var = tk.StringVar()
        ttk.Entry(opts, textvariable=self.seed_var, width=10).grid(row=1, column=7, sticky="w", padx=4, pady=(6, 0))
        ttk.Label(opts, text="empty = random").grid(row=1, column=8, sticky="w", pady=(6, 0))
        ttk.Label(opts, text="Cat legato").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.legato_var = tk.StringVar(value=LEGATO_CHOICES[0])
        ttk.Combobox(opts, textvariable=self.legato_var, values=LEGATO_CHOICES, state="readonly", width=24).grid(
            row=1, column=1, columnspan=3, sticky="w", padx=4, pady=(6, 0))
        sounds = ttk.Frame(opts)
        sounds.grid(row=2, column=0, columnspan=6, sticky="w", pady=(4, 0))
        self.sound_vars = {}
        for key, label, _ in CAT_SOUNDS:
            self.sound_vars[key] = tk.BooleanVar(value=False)
            ttk.Checkbutton(sounds, text=label, variable=self.sound_vars[key]).pack(side="left", padx=(0, 12))
        ttk.Label(sounds, text="Cat accent").pack(side="left", padx=(0, 4))
        self.accent_var = tk.StringVar(value=ACCENT_CHOICES[0])
        ttk.Combobox(sounds, textvariable=self.accent_var, values=ACCENT_CHOICES, state="readonly", width=10).pack(
            side="left")
        self.thesaurus_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(sounds, text="Easier words (sleep → doze)", variable=self.thesaurus_var).pack(
            side="left", padx=(12, 0))
        self.stop_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts, text="Stop at the last word (cut trailing babble)", variable=self.stop_var).grid(
            row=1, column=4, columnspan=2, sticky="w", pady=(6, 0))
        for var, lbl in ((self.exag_var, self.exag_lbl), (self.cfg_var, self.cfg_lbl)):
            var.trace_add("write", lambda *_, v=var, l=lbl: l.config(text=f"{v.get():.2f}"))
            lbl.config(text=f"{var.get():.2f}")

        out = ttk.Frame(step2)
        out.pack(fill="x", **pad)
        ttk.Label(out, text="Save to:").pack(side="left")
        self.out_var = tk.StringVar(value=DEFAULT_OUT_DIR)
        ttk.Entry(out, textvariable=self.out_var).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(out, text="Browse…", command=self.on_browse).pack(side="left")
        ttk.Button(out, text="Open folder", command=self.on_open_folder).pack(side="left", padx=4)

        buttons = ttk.Frame(step2)
        buttons.pack(fill="x", **pad)
        self.gen_btn = ttk.Button(buttons, text="Generate MP3s", command=self.on_generate)
        self.gen_btn.pack(side="left")
        self.load_btn = ttk.Button(buttons, text="Download / load voice model", command=self.on_load_model)
        self.load_btn.pack(side="left", padx=8)
        self.all_btn = ttk.Button(buttons, text="Generate with every saved voice", command=self.on_generate_all)
        self.all_btn.pack(side="left")

        # Status
        self.progress = ttk.Progressbar(root, mode="indeterminate")
        self.progress.pack(fill="x", **pad)
        self.status = ttk.Label(root, text="Ready.")
        self.status.pack(fill="x", **pad)

        self.root.after(100, self.poll_events)

    # ---- helpers -------------------------------------------------------
    def set_status(self, msg):
        self.events.put(("status", msg))

    def set_busy(self, busy):
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.clip_btn.config(state=state)
        self.gen_btn.config(state=state)
        self.load_btn.config(state=state)
        self.all_btn.config(state=state)
        self.save_voice_btn.config(state=state)
        if busy:
            self.progress.start(12)
        else:
            self.progress.stop()

    def run_in_background(self, fn):
        if self.busy:
            return
        self.set_busy(True)

        def worker():
            try:
                fn()
            except Exception as exc:  # show any failure to the user
                self.events.put(("error", str(exc)))
            finally:
                self.events.put(("done", None))

        threading.Thread(target=worker, daemon=True).start()

    def poll_events(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "status":
                    self.status.config(text=payload)
                elif kind == "ref":
                    self.ref_label.config(text=payload)
                elif kind == "error":
                    self.status.config(text="Error.")
                    messagebox.showerror("Voice Maker", payload)
                elif kind == "voices":
                    self.refresh_voices(payload)
                elif kind == "done":
                    self.set_busy(False)
        except queue.Empty:
            pass
        self.root.after(100, self.poll_events)

    # ---- actions -------------------------------------------------------
    def on_get_clip(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Voice Maker", "Paste a YouTube link first.")
            return
        try:
            start = parse_timestamp(self.start_var.get())
            end = parse_timestamp(self.end_var.get())
        except ValueError as exc:
            messagebox.showwarning("Voice Maker", str(exc))
            return
        if end <= start:
            messagebox.showwarning("Voice Maker", "End time must be after the start time.")
            return

        def task():
            self.set_status("Downloading audio section…")
            out_wav = os.path.join(WORK_DIR, "reference.wav")
            download_clip(url, start, end, out_wav)
            self.reference_wav = out_wav
            length = end - start
            note = " (only about the first 10 s are used by Chatterbox)" if length > 20 else ""
            self.events.put(("ref", f"Reference clip ready: {length:.1f} s{note}  →  {out_wav}"))
            self.set_status("Reference clip ready. Type phrases and click Generate MP3s.")

        self.run_in_background(task)

    def on_cat_clip(self):
        """Ticking "Cat clip" also picks the settings that worked best with a cat's voice."""
        if self.cat_clip_var.get():
            self.legato_var.set("Meow")
            for var in self.sound_vars.values():
                var.set(True)
            self.accent_var.set("Medium")

    def on_load_model(self):
        def task():
            self.cloner.load()
            self.set_status(f"Voice model ready on {self.cloner.device}.")

        self.run_in_background(task)

    def on_pick_local(self):
        path = filedialog.askopenfilename(
            title="Choose a reference audio file",
            filetypes=[("Audio", "*.wav *.mp3 *.m4a *.flac *.ogg"), ("All files", "*.*")],
        )
        if path:
            self.reference_wav = path
            self.voice_var.set("")
            self.ref_label.config(text=f"Reference clip: {path}")

    # ---- saved voices --------------------------------------------------
    def current_settings(self):
        accent = self.accent_var.get()
        seed = self.seed_var.get().strip()
        if seed and not seed.isdigit():
            messagebox.showwarning("Voice Maker", "Seed must be a whole number, or empty for a random take.")
            return None
        return dict(
            seed=int(seed) if seed else None,
            exaggeration=round(self.exag_var.get(), 2),
            cfg_weight=round(self.cfg_var.get(), 2),
            pitch=round(self.pitch_var.get()),
            legato=LEGATO_PRESETS[self.legato_var.get()],
            accent=None if accent == "Off" else accent.lower(),
            thesaurus=self.thesaurus_var.get(),
            **{key: amount if self.sound_vars[key].get() else 0.0 for key, _, amount in CAT_SOUNDS},
        )

    def refresh_voices(self, select=None):
        self.voice_box.config(values=[v["name"] for v in voices.list_voices()])
        if select:
            self.voice_var.set(select)

    def on_use_voice(self):
        """Picking a saved voice makes it the reference and restores its remembered settings."""
        voice = voices.get_voice(self.voice_var.get())
        s = voice["settings"]
        self.reference_wav = voice["reference"]
        self.cat_clip_var.set(False)  # its reference was already cut down when it was saved
        self.exag_var.set(s["exaggeration"])
        self.cfg_var.set(s["cfg_weight"])
        self.pitch_var.set(s["pitch"])
        self.seed_var.set(str(s["seed"] or ""))
        self.legato_var.set(next(k for k, v in LEGATO_PRESETS.items() if v == s["legato"]))
        self.accent_var.set((s["accent"] or "off").capitalize())
        self.thesaurus_var.set(s["thesaurus"])
        for key, var in self.sound_vars.items():
            var.set(s[key] > 0)
        self.ref_label.config(text=f"Voice: {voice['name']}  ({voice['source']})")

    def on_save_voice(self):
        if not self.reference_wav or not os.path.exists(self.reference_wav):
            messagebox.showwarning("Voice Maker", "Get a reference clip first.")
            return
        name = simpledialog.askstring("Voice Maker", "Name for this voice:", parent=self.root)
        if not name or not name.strip():
            return
        name = name.strip()
        clip, cat_clip, settings = self.reference_wav, self.cat_clip_var.get(), self.current_settings()
        if settings is None:
            return
        url = self.url_var.get().strip()
        source = f"{url} {self.start_var.get()}-{self.end_var.get()}" if clip == os.path.join(WORK_DIR, "reference.wav") and url else None

        def task():
            self.set_status(f"Saving voice {name}…")
            voices.save_voice(name, clip, cat_clip, source, **settings)
            self.events.put(("voices", name))
            self.set_status(f"Saved voice {name}. Pick it any time under Saved voice.")

        self.run_in_background(task)

    def on_update_voice(self):
        if not self.voice_var.get():
            messagebox.showwarning("Voice Maker", "Pick a saved voice first.")
            return
        settings = self.current_settings()
        if settings is None:
            return
        voices.update_settings(self.voice_var.get(), **settings)
        self.set_status(f"{self.voice_var.get()} will use these settings from now on.")

    def on_generate_all(self):
        phrases = self.phrases()
        saved = voices.list_voices()
        if not saved:
            messagebox.showwarning("Voice Maker", "Save a voice first (step 1).")
            return
        if not phrases:
            messagebox.showwarning("Voice Maker", "Type at least one phrase.")
            return
        out_dir = self.out_var.get().strip() or DEFAULT_OUT_DIR
        end_at_words = self.stop_var.get()

        def task():
            for voice in saved:
                folder = os.path.join(out_dir, voices.slugify(voice["name"]))
                os.makedirs(folder, exist_ok=True)
                for i, phrase in enumerate(phrases, 1):
                    self.set_status(f"{voice['name']} {i}/{len(phrases)}: {phrase[:50]}")
                    seed = voice["settings"]["seed"] or random.randrange(1, 1_000_000)
                    voices.speak_as(self.cloner, voice, phrase,
                                    unused_path(os.path.join(folder, f"{i:02d}_{slugify(phrase)}_seed{seed}.mp3")),
                                    end_at_words=end_at_words, seed=seed)
            self.set_status(f"Done. One folder per voice in {out_dir}")

        self.run_in_background(task)

    def on_browse(self):
        path = filedialog.askdirectory(initialdir=self.out_var.get() or DATA_DIR)
        if path:
            self.out_var.set(path)

    def on_open_folder(self):
        path = self.out_var.get()
        os.makedirs(path, exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def phrases(self):
        return [line.strip() for line in self.text.get("1.0", "end").splitlines() if line.strip()]

    def on_generate(self):
        if not self.reference_wav or not os.path.exists(self.reference_wav):
            messagebox.showwarning("Voice Maker", "Get a reference clip first (step 1).")
            return
        phrases = self.phrases()
        if not phrases:
            messagebox.showwarning("Voice Maker", "Type at least one phrase.")
            return
        out_dir = self.out_var.get().strip() or DEFAULT_OUT_DIR
        settings = self.current_settings()
        if settings is None:
            return
        reference = self.reference_wav
        end_at_words = self.stop_var.get()
        loud_parts_only = self.cat_clip_var.get()

        def task():
            os.makedirs(out_dir, exist_ok=True)
            self.cloner.set_reference(reference, exaggeration=settings["exaggeration"], loud_parts_only=loud_parts_only)
            for i, phrase in enumerate(phrases, 1):
                self.set_status(f"Generating {i}/{len(phrases)}: {phrase[:50]}")
                seed = settings["seed"] or random.randrange(1, 1_000_000)
                name = f"{i:02d}_{slugify(phrase)}_seed{seed}.mp3"
                self.cloner.speak_to_mp3(phrase, unused_path(os.path.join(out_dir, name)), end_at_words=end_at_words,
                                         **{**voices.speak_kwargs(settings), "seed": seed})
            self.set_status(f"Done. Saved {len(phrases)} MP3 file(s) to {out_dir}")

        self.run_in_background(task)


def run_command_line(args):
    """Command line mode, e.g. VoiceMaker.exe say --ref clip.wav --out hi.mp3 "Hi"
    or VoiceMaker.exe clip URL START END out.wav. Errors are printed (to the log
    when packaged) instead of raised, so a windowed .exe never hangs on an error box."""
    import traceback

    import chatterbox_harness

    try:
        if args[0] == "clip":
            _, url, start, end, out_wav = args
            download_clip(url, parse_timestamp(start), parse_timestamp(end), os.path.abspath(out_wav))
            print(f"Saved {out_wav}")
            return 0
        if args[0] in ("voice", "compare"):
            return voices.main(args, download=lambda url, start, end, out: download_clip(
                url, parse_timestamp(start), parse_timestamp(end), out))
        return chatterbox_harness.main(args)
    except SystemExit as exc:  # --help, or an argument error already printed by argparse
        return exc.code or 0
    except BaseException:
        traceback.print_exc()
        return 1


def main():
    if FROZEN and sys.stdout is None:
        # A windowed .exe has no console; send library output (progress bars, warnings) to a log file.
        os.makedirs(DATA_DIR, exist_ok=True)
        sys.stdout = sys.stderr = open(os.path.join(DATA_DIR, "voice_maker.log"), "a", encoding="utf-8", buffering=1)
        print(f"Voice Maker started {' '.join(sys.argv[1:]) or '(window)'}")
    if len(sys.argv) > 1 and sys.argv[1] in ("download", "say", "clip", "voice", "compare"):
        sys.exit(run_command_line(sys.argv[1:]))
    if not ffmpeg_exe():
        tk.Tk().withdraw()
        messagebox.showerror("Voice Maker", "ffmpeg was not found on your PATH. Install it first (see README).")
        return
    try:
        root = tk.Tk()
        App(root)
        root.mainloop()
    except Exception:  # a windowed .exe has nowhere else to show this
        import traceback

        traceback.print_exc()
        messagebox.showerror("Voice Maker", traceback.format_exc())
        raise
    print("Voice Maker window closed")


if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()
    main()
