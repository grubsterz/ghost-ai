#!/usr/bin/env bash
# Builds "dist/GHOST AI.app" and a .dmg on macOS (Apple Silicon).
# Usage: bash packaging/build_macos.sh
# NOTE: this script has not been run yet - it was written on Windows. Please report problems.
set -euo pipefail
cd "$(dirname "$0")/.."

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip >/dev/null
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pip install "llama-cpp-python>=0.3.16" --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/metal
.venv/bin/python -m pytest

QT_QPA_PLATFORM=offscreen .venv/bin/python tools/make_icons.py

# .icns from the 1024 px PNG
ICONSET=packaging/ghost.iconset
rm -rf "$ICONSET" && mkdir -p "$ICONSET"
for s in 16 32 128 256 512; do
  sips -z $s $s packaging/ghost.png --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
  d=$((s*2)); sips -z $d $d packaging/ghost.png --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o packaging/ghost.icns
rm -rf "$ICONSET"

.venv/bin/python -m PyInstaller packaging/ghost_ai.spec --noconfirm --clean --distpath dist --workpath build

VERSION=$(.venv/bin/python -c "import ghost_ai; print(ghost_ai.__version__)")
DMG="dist/GHOST-AI-${VERSION}-macos-arm64.dmg"
rm -f "$DMG"
hdiutil create -volname "GHOST AI" -srcfolder "dist/GHOST AI.app" -ov -format UDZO "$DMG"
echo "Built: dist/GHOST AI.app"
echo "DMG:   $DMG"
echo "The app is not signed/notarized. First launch: right-click → Open."
