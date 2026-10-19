@echo off
rem One-time setup: virtual environment, packages, and the Chatterbox model weights.
cd /d "%~dp0"
py -3.11 -m venv .venv || goto :error
.venv\Scripts\python -m pip install --upgrade pip || goto :error
.venv\Scripts\pip install -r requirements.txt || goto :error
rem For an NVIDIA GPU, swap in the CUDA build of PyTorch (matches chatterbox-tts 0.1.7):
.venv\Scripts\pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
.venv\Scripts\python chatterbox_harness.py download || goto :error
echo Done. Start the app with: .venv\Scripts\python voice_maker.py
pause
exit /b 0
:error
echo Setup failed, see the messages above.
pause
exit /b 1
