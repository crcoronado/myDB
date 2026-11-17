#!/bin/bash
# One-time setup on macOS (Apple Silicon or Intel). Creates ./.venv with the dependencies.
set -euo pipefail
cd "$(dirname "$0")"

PY=""
for c in python3.13 python3.12 python3.11 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c "import tkinter; assert tkinter.TkVersion >= 8.6" 2>/dev/null; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  echo "No Python 3.11+ with Tk 8.6 found."
  echo "Install one of:"
  echo "  • python.org installer (macOS 64-bit universal2) – includes Tk:  https://www.python.org/downloads/macos/"
  echo "  • Homebrew:  brew install python@3.13 python-tk@3.13"
  exit 1
fi
echo "Using $($PY --version) at $(command -v $PY)"
"$PY" -m venv .venv
.venv/bin/pip install --upgrade pip >/dev/null
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests
echo
echo "Done. Start myDB with:  ./run_mac.command   (or double-click it in Finder)"
