"""One-click setup of the built-in local AI: pick a model, download it once, done. No other programs."""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import threading

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QButtonGroup, QDialog, QHBoxLayout, QProgressBar, QRadioButton, QVBoxLayout

from ..ai.embedded import MODELS, DownloadCancelled, describe, download_model, engine_available, is_downloaded
from ..i18n import language, tr
from .widgets import button, human_size, label


def total_ram_gb() -> float:
    try:
        if sys.platform == "win32":
            class MemStatus(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = MemStatus()
            m.dwLength = ctypes.sizeof(MemStatus)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return m.ullTotalPhys / 1024 ** 3
        if sys.platform == "darwin":
            return int(subprocess.check_output(["sysctl", "-n", "hw.memsize"])) / 1024 ** 3
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024 ** 3
    except Exception:
        return 8.0


def recommended_model() -> str:
    ram = total_ram_gb()
    return "smart" if ram >= 12 else ("standard" if ram >= 6 else "small")


class _Sig(QObject):
    progress = Signal(int, int)
    done = Signal(str)


class AiSetupDialog(QDialog):
    def __init__(self, ctx, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.cancel = threading.Event()
        self.setWindowTitle(tr("ai.setup_title"))
        self.setMinimumWidth(720)
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.addWidget(label(tr("ai.setup_title"), "H2"))
        lay.addWidget(label(tr("ai.setup_text")))
        if not engine_available():
            lay.addWidget(label(tr("ai.no_engine"), "PillWarn"))
        rec = recommended_model()
        lay.addWidget(label(tr("ai.your_ram", ram=round(total_ram_gb())), "Muted"))
        current = ctx.setting("builtin_model")
        default_key = current if current in MODELS and is_downloaded(ctx.data_dir, current) else rec
        self.group = QButtonGroup(self)
        for key in MODELS:
            text = describe(key, language())
            if key == rec:
                text += "  ★ " + tr("ai.recommended")
            if is_downloaded(ctx.data_dir, key):
                text += "  ✓ " + tr("ai.downloaded")
            rb = QRadioButton(text)
            rb.setProperty("key", key)
            rb.setChecked(key == default_key)
            self.group.addButton(rb)
            lay.addWidget(rb)
        lay.addWidget(label(tr("ai.privacy"), "Muted"))
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.hide()
        lay.addWidget(self.bar)
        self.status = label("", "Muted")
        lay.addWidget(self.status)
        row = QHBoxLayout()
        row.addStretch(1)
        self.cancel_btn = button(tr("cancel"), slot=self._cancel)
        row.addWidget(self.cancel_btn)
        self.go_btn = button(tr("ai.download"), "Primary", self._go)
        self.go_btn.setEnabled(engine_available())
        row.addWidget(self.go_btn)
        lay.addLayout(row)
        self.sig = _Sig()
        self.sig.progress.connect(self._progress)
        self.sig.done.connect(self._done)
        self.thread: threading.Thread | None = None

    def _key(self) -> str:
        return self.group.checkedButton().property("key")

    def _go(self) -> None:
        key = self._key()
        self.go_btn.setEnabled(False)
        for b in self.group.buttons():
            b.setEnabled(False)
        self.bar.show()
        self.cancel.clear()

        def work() -> None:
            try:
                download_model(self.ctx.data_dir, key, lambda d, t: self.sig.progress.emit(d // 1024 ** 2, t // 1024 ** 2),
                               self.cancel)
                self.sig.done.emit("")
            except DownloadCancelled:
                self.sig.done.emit("cancelled")
            except Exception as exc:  # shown to the user
                self.sig.done.emit(str(exc))

        self.thread = threading.Thread(target=work, daemon=True)
        self.thread.start()

    def _progress(self, done_mb: int, total_mb: int) -> None:
        self.bar.setValue(int(done_mb * 1000 / max(total_mb, 1)))
        self.status.setText(f"{human_size(done_mb * 1024 ** 2)} / {human_size(total_mb * 1024 ** 2)}")

    def _done(self, err: str) -> None:
        if err == "cancelled":
            self.reject()
            return
        if err:
            self.status.setText(tr("ai.failed", e=err))
            self.go_btn.setEnabled(True)
            for b in self.group.buttons():
                b.setEnabled(True)
            return
        self.ctx.set_setting("builtin_model", self._key())
        self.ctx.set_setting("ai_engine", "builtin")
        self.ctx.set_setting("ai_enabled", True)
        self.ctx.bus.changed.emit()
        self.accept()

    def _cancel(self) -> None:
        if self.thread and self.thread.is_alive():
            self.cancel.set()  # partial file is kept and resumed next time
        else:
            self.reject()

    def closeEvent(self, e) -> None:  # noqa: N802
        self.cancel.set()
        super().closeEvent(e)
