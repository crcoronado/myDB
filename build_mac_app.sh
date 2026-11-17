#!/bin/bash
# Builds dist/myDB.app (native arm64 on an M-series Mac). Run install_mac.sh first.
set -euo pipefail
cd "$(dirname "$0")"
.venv/bin/pip install pyinstaller >/dev/null
.venv/bin/pyinstaller --noconfirm --clean --windowed \
  --name myDB \
  --osx-bundle-identifier com.crc.mydb \
  --add-data "data:data" \
  myDB.py
echo
echo "Built: dist/myDB.app"
echo "1) Drag it to /Applications"
echo "2) Open it once, then enable it in System Settings → Privacy & Security → Accessibility"
echo "3) Quit and reopen myDB. Optional: add it to System Settings → General → Login Items"
