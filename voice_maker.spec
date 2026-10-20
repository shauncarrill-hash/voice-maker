# PyInstaller recipe for the standalone Voice Maker app.
# Build: pyinstaller voice_maker.spec   (set FFMPEG_BIN to an ffmpeg executable to bundle it)
import os

from PyInstaller.utils.hooks import collect_all, copy_metadata

datas, binaries, hiddenimports = [], [], []

# Packages that load data files (model configs, watermark weights, mel filters) at runtime.
for pkg in ["chatterbox", "perth", "s3tokenizer", "librosa", "conformer", "diffusers", "yt_dlp", "pyloudnorm", "omegaconf", "pyworld"]:
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# transformers, chatterbox and others look up installed package versions at import time.
for dist in [
    "chatterbox-tts", "torch", "torchaudio", "transformers", "tokenizers", "huggingface-hub", "safetensors",
    "diffusers", "numpy", "tqdm", "regex", "requests", "filelock", "packaging", "pyyaml", "librosa",
    "resemble-perth", "s3tokenizer", "setuptools",
]:
    try:
        datas += copy_metadata(dist)
    except Exception:
        print(f"no metadata for {dist}")

hiddenimports += ["pkg_resources", "tkinter", "chatterbox_harness", "cat_legato", "cat_accent", "cat_thesaurus", "voices"]

ffmpeg = os.environ.get("FFMPEG_BIN")
if ffmpeg:
    binaries.append((ffmpeg, "."))

a = Analysis(
    ["voice_maker.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["gradio", "matplotlib", "IPython", "jupyter", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VoiceMaker",
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="VoiceMaker", upx=False)
