"""Voice Maker: clone a voice from a YouTube clip with Chatterbox TTS and export phrases as MP3.

Flow:
  1. Paste a YouTube link, enter start and end timestamps, click "Get reference clip".
  2. Type phrases (one per line) and click "Generate MP3s".
"""

import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from chatterbox_harness import DATA_DIR, FROZEN, VoiceCloner, ffmpeg_exe, run_ffmpeg

WORK_DIR = os.path.join(DATA_DIR, "work")
if FROZEN:
    DEFAULT_OUT_DIR = os.path.join(os.path.expanduser("~"), "Documents", "Voice Maker")
else:
    DEFAULT_OUT_DIR = os.path.join(DATA_DIR, "output")


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
            self.ref_label.config(text=f"Reference clip: {path}")

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

    def on_generate(self):
        if not self.reference_wav or not os.path.exists(self.reference_wav):
            messagebox.showwarning("Voice Maker", "Get a reference clip first (step 1).")
            return
        phrases = [line.strip() for line in self.text.get("1.0", "end").splitlines() if line.strip()]
        if not phrases:
            messagebox.showwarning("Voice Maker", "Type at least one phrase.")
            return
        out_dir = self.out_var.get().strip() or DEFAULT_OUT_DIR
        exaggeration = self.exag_var.get()
        cfg_weight = self.cfg_var.get()
        reference = self.reference_wav

        def task():
            os.makedirs(out_dir, exist_ok=True)
            self.cloner.set_reference(reference, exaggeration=exaggeration)
            for i, phrase in enumerate(phrases, 1):
                self.set_status(f"Generating {i}/{len(phrases)}: {phrase[:50]}")
                name = f"{i:02d}_{slugify(phrase)}.mp3"
                self.cloner.speak_to_mp3(
                    phrase,
                    os.path.join(out_dir, name),
                    exaggeration=exaggeration,
                    cfg_weight=cfg_weight,
                )
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
        return chatterbox_harness.main(args)
    except BaseException:
        traceback.print_exc()
        return 1


def main():
    if FROZEN and sys.stdout is None:
        # A windowed .exe has no console; send library output (progress bars, warnings) to a log file.
        os.makedirs(DATA_DIR, exist_ok=True)
        sys.stdout = sys.stderr = open(os.path.join(DATA_DIR, "voice_maker.log"), "a", encoding="utf-8", buffering=1)
    if len(sys.argv) > 1 and sys.argv[1] in ("download", "say", "clip"):
        sys.exit(run_command_line(sys.argv[1:]))
    if not ffmpeg_exe():
        tk.Tk().withdraw()
        messagebox.showerror("Voice Maker", "ffmpeg was not found on your PATH. Install it first (see README).")
        return
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()
    main()
