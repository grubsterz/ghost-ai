"""Render the painted logo to packaging/ghost.png (1024) and packaging/ghost.ico (multi-size)."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from ghost_ai.ui.logo import logo_pixmap  # noqa: E402

app = QApplication.instance() or QApplication([])
out = ROOT / "packaging"
out.mkdir(exist_ok=True)
logo_pixmap(1024).save(str(out / "ghost.png"))
logo_pixmap(256).save(str(out / "ghost.ico"))
print(out / "ghost.png", out / "ghost.ico")
