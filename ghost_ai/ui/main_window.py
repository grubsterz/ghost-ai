from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QHBoxLayout, QLabel, QMainWindow, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from .. import i18n
from ..i18n import tr
from .pages.about import AboutPage
from .pages.dashboard import DashboardPage
from .pages.files import FilesPage
from .pages.natural import NaturalPage
from .pages.quick import QuickPage
from .pages.safety import SafetyPage
from .pages.settings import SettingsPage
from .pages.teach import TeachPage
from .theme import build_qss
from .widgets import fade_in, label, pill

ASSETS = Path(__file__).resolve().parent.parent / "assets"

NAV = [
    ("dashboard", "◈", DashboardPage), ("files", "▤", FilesPage), ("teach", "◉", TeachPage),
    ("natural", "✦", NaturalPage), ("quick", "↯", QuickPage), ("safety", "⛨", SafetyPage),
    ("settings", "⚙︎", SettingsPage), ("about", "ⓘ", AboutPage),
]


def app_icon() -> QIcon:
    from .logo import logo_icon
    return logo_icon()


class MainWindow(QMainWindow):
    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle("GHOST AI")
        self.setWindowIcon(app_icon())
        self.resize(1180, 760)
        self.setMinimumSize(760, 520)
        self._compact = False
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._refresh_current)
        ctx.bus.changed.connect(lambda: self._refresh_timer.start(120))
        ctx.bus.navigate.connect(self.go)
        ctx.bus.restyle.connect(self.apply_style)
        ctx.bus.relanguage.connect(self.rebuild)
        ctx.service.on_change.append(ctx.bus.changed.emit)  # may fire from worker thread → queued signal
        for i, key in enumerate(["dashboard", "files", "teach", "natural", "quick", "safety", "settings"], start=1):
            QShortcut(QKeySequence(f"Ctrl+{i}"), self, activated=lambda k=key: self.go(k))
        self.rebuild()

    # ---- building ---------------------------------------------------------
    def rebuild(self) -> None:
        current = getattr(self, "_current", "dashboard")
        i18n.set_language(self.ctx.setting("language", "en"))
        root = QWidget()
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        side = QWidget()
        side.setObjectName("Sidebar")
        side.setFixedWidth(232)
        self.side = side
        sv = QVBoxLayout(side)
        sv.setContentsMargins(14, 22, 14, 16)
        sv.setSpacing(4)
        brand = QHBoxLayout()
        logo = QLabel()
        from .logo import logo_pixmap
        logo.setPixmap(logo_pixmap(34, background=False))
        brand.addWidget(logo)
        self.brand_a = label("GHOST", "Brand", wrap=False)
        self.brand_b = label("AI", "BrandAccent", wrap=False)
        brand.addWidget(self.brand_a)
        brand.addWidget(self.brand_b)
        brand.addStretch(1)
        sv.addLayout(brand)
        self.tagline = label(tr("tagline"), "Tagline")
        sv.addWidget(self.tagline)
        sv.addSpacing(18)

        self.stack = QStackedWidget()
        self.pages: dict[str, QWidget] = {}
        self.nav_buttons: dict[str, QPushButton] = {}
        group = QButtonGroup(self)
        group.setExclusive(True)
        for key, icon, cls in NAV:
            b = QPushButton()
            b.setObjectName("Nav")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setProperty("icon_text", icon)
            b.setProperty("label_text", tr(f"nav.{key}"))
            b.setAccessibleName(tr(f"nav.{key}"))
            b.setToolTip(tr(f"nav.{key}"))
            b.clicked.connect(lambda _=False, k=key: self.go(k))
            group.addButton(b)
            sv.addWidget(b)
            self.nav_buttons[key] = b
            page = cls(self.ctx)
            self.pages[key] = page
            self.stack.addWidget(page)
        sv.addStretch(1)
        self.engine_pill = pill("")
        self.engine_pill.setWordWrap(True)
        sv.addWidget(self.engine_pill)

        h.addWidget(side)
        h.addWidget(self.stack, 1)
        old = self.centralWidget()
        self.setCentralWidget(root)
        if old is not None:
            old.deleteLater()
        self.apply_style()
        self._apply_compact(self.width() < 980, force=True)
        self.go(current, animate=False)

    def apply_style(self) -> None:
        app = QApplication.instance()
        app.setStyleSheet(build_qss(self.ctx.setting("theme", "dark"), float(self.ctx.setting("scale", 1.0))))

    def _apply_compact(self, compact: bool, force: bool = False) -> None:
        if compact == self._compact and not force:
            return
        self._compact = compact
        self.side.setFixedWidth(72 if compact else 232)
        for w in (self.brand_a, self.brand_b, self.tagline, self.engine_pill):
            w.setVisible(not compact)
        for b in self.nav_buttons.values():
            icon, text = b.property("icon_text"), b.property("label_text")
            b.setText(f"  {icon}" if compact else f"  {icon}    {text}")

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "side"):
            self._apply_compact(self.width() < 980)

    # ---- navigation -------------------------------------------------------
    def go(self, key: str, animate: bool = True) -> None:
        if key not in self.pages:
            return
        self._current = key
        self.nav_buttons[key].setChecked(True)
        page = self.pages[key]
        self.stack.setCurrentWidget(page)
        page.refresh()
        self._update_status()
        if animate:
            fade_in(page.widget())

    def _refresh_current(self) -> None:
        page = self.stack.currentWidget()
        if page is not None:
            page.refresh()
        self._update_status()

    def _update_status(self) -> None:
        svc = self.ctx.service
        if svc.paused:
            text, kind = tr("status.paused"), "Warn"
        elif svc.watching and svc.watched_folders():
            text, kind = tr("status.watching", n=len(svc.watched_folders())), "Ok"
        else:
            text, kind = tr("status.idle"), "Muted"
        if svc.approvals:
            text += f"\n{tr('safety.approvals')}: {len(svc.approvals)}"
            kind = "Warn"
        self.engine_pill.setText(text)
        self.engine_pill.setObjectName(f"Pill{kind}")
        self.engine_pill.style().unpolish(self.engine_pill)
        self.engine_pill.style().polish(self.engine_pill)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.ctx.service.stop_watching()
        super().closeEvent(event)
