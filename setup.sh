#!/usr/bin/env bash
# One-time setup: virtual environment, packages, and the Chatterbox model weights.
set -e
cd "$(dirname "$0")"
PY=${PYTHON:-python3.11}
"$PY" -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
.venv/bin/python chatterbox_harness.py download
echo "Done. Start the app with: .venv/bin/python voice_maker.py"
