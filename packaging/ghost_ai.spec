# PyInstaller spec for GHOST AI (Windows .exe folder build and macOS .app bundle).
# Build with:  pyinstaller packaging/ghost_ai.spec --noconfirm
import os
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent
ICON_WIN = str(ROOT / "packaging" / "ghost.ico")
ICON_MAC = str(ROOT / "packaging" / "ghost.icns")

# Only the Qt modules GHOST uses - keeps the bundle small.
excludes = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore", "PySide6.QtQuick",
    "PySide6.QtQml", "PySide6.QtMultimedia", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtPdf", "PySide6.QtBluetooth", "PySide6.QtSql", "PySide6.QtTest", "tkinter",
]

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT)],
    datas=[],
    hiddenimports=["watchdog.observers", "watchdog.observers.read_directory_changes", "watchdog.observers.fsevents"],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="GHOST AI",
    console=bool(os.environ.get("GHOST_DEBUG_CONSOLE")),
    icon=ICON_WIN if sys.platform == "win32" else None,
    argv_emulation=False,
    target_arch=None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="GHOST AI")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="GHOST AI.app",
        icon=ICON_MAC if Path(ICON_MAC).exists() else None,
        bundle_identifier="com.grubsterz.ghostai",
        info_plist={
            "CFBundleShortVersionString": "0.2.0",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "12.0",
            # Shown by macOS only if the optional voice feature is used.
            "NSMicrophoneUsageDescription": "GHOST AI uses the microphone only while you hold the Speak button, "
                                            "to turn your voice into text locally.",
        },
    )
