#!/bin/bash
# Builds dist/myDB.app and dist/myDB-<version>-<arch>.dmg. Must run on macOS.
# Used by GitHub Actions (.github/workflows/build-mac-dmg.yml); also works locally.
set -euo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
VERSION=$("$PY" -c "import re;print(re.search(r'__version__ = \"(.+)\"', open('mydb/__init__.py').read()).group(1))")
ARCH=$(uname -m)
"$PY" -c "import tkinter; print('Tk', tkinter.TkVersion)"

# 1) isolated build environment (inside build/, which git ignores)
"$PY" -m venv build/venv
build/venv/bin/pip install -q --upgrade pip
build/venv/bin/pip install -q -r requirements.txt pyinstaller

# 2) app icon (.icns) from packaging/icon.png
ICONSET=build/myDB.iconset
rm -rf "$ICONSET"; mkdir -p "$ICONSET"
for s in 16 32 128 256 512; do
  sips -z $s $s packaging/icon.png --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
  sips -z $((s*2)) $((s*2)) packaging/icon.png --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o build/myDB.icns

# 3) the .app bundle
build/venv/bin/pyinstaller --noconfirm --clean --windowed \
  --name myDB --osx-bundle-identifier com.crc.mydb \
  --icon build/myDB.icns --add-data "data:data" \
  --distpath dist --workpath build/pyinstaller --specpath build \
  myDB.py
PLIST=dist/myDB.app/Contents/Info.plist
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $VERSION" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleVersion string $VERSION" "$PLIST" 2>/dev/null \
  || /usr/libexec/PlistBuddy -c "Set :CFBundleVersion $VERSION" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :NSHumanReadableCopyright string myDB quick CSV search" "$PLIST" 2>/dev/null || true
codesign --force --deep --sign - dist/myDB.app   # ad-hoc signature (Info.plist changed)
codesign --verify --deep --strict dist/myDB.app

# 4) drag-to-Applications disk image
STAGE=build/dmg
rm -rf "$STAGE"; mkdir -p "$STAGE"
cp -R dist/myDB.app "$STAGE/"
ln -s /Applications "$STAGE/Applications"
DMG="dist/myDB-$VERSION-$ARCH.dmg"
rm -f "$DMG"
hdiutil create -volname "myDB $VERSION" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
echo "Built $DMG"
