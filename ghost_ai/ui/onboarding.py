from __future__ import annotations

from PySide6.QtWidgets import QButtonGroup, QDialog, QHBoxLayout, QRadioButton, QVBoxLayout

from ..i18n import tr
from ..templates import TEMPLATE_KEYS, build_template
from .widgets import PreviewDialog, RuleEditor, button, label


class Onboarding(QDialog):
    """First-run welcome: explains the privacy model and offers a starter rule (reviewed, then previewed)."""

    def __init__(self, ctx, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle(tr("ob.title"))
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.addWidget(label(tr("ob.title"), "H1"))
        for k in ("ob.p1", "ob.p2", "ob.p3"):
            lay.addWidget(label("✓  " + tr(k)))
        lay.addSpacing(8)
        lay.addWidget(label(tr("ob.start"), "H2"))
        self.group = QButtonGroup(self)
        for i, key in enumerate(["images", "docs", "screenshots"]):
            rb = QRadioButton(tr(f"tpl.{key}"))
            rb.setProperty("tpl", key)
            if i == 0:
                rb.setChecked(True)
            self.group.addButton(rb)
            lay.addWidget(rb)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(button(tr("ob.skip"), slot=self._skip))
        row.addWidget(button(tr("ob.create"), "Primary", self._create))
        lay.addLayout(row)

    def _skip(self) -> None:
        self.ctx.set_setting("onboarded", True)
        self.accept()

    def _create(self) -> None:
        self.ctx.set_setting("onboarded", True)
        key = self.group.checkedButton().property("tpl")
        assert key in TEMPLATE_KEYS
        ed = RuleEditor(self.ctx, build_template(key, self.ctx.known_folders()), self)
        if ed.exec():
            PreviewDialog(self.ctx, self.ctx.service.preview_rule(ed.rule), self).exec()
        self.accept()
