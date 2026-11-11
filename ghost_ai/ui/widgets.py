"""Reusable widgets and dialogs."""

from __future__ import annotations

import os
from pathlib import Path, PurePath

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame,
    QGraphicsOpacityEffect, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..domain.matching import render_name
from ..domain.models import (
    Action, ActionRecord, ActionType, CaseMode, Conditions, ConflictPolicy, PlannedAction, Rule, SpaceMode, Status,
    Trigger,
)
from ..i18n import tr
from ..safety.guard import Blocked


# ---------------------------------------------------------------------------
# small building blocks
# ---------------------------------------------------------------------------

def label(text: str, obj: str = "", wrap: bool = True) -> QLabel:
    lb = QLabel(text)
    if obj:
        lb.setObjectName(obj)
    lb.setWordWrap(wrap)
    lb.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return lb


def button(text: str, obj: str = "", slot=None, tip: str = "") -> QPushButton:
    b = QPushButton(text.replace("&", "&&"))  # '&' is a Qt mnemonic marker
    if obj:
        b.setObjectName(obj)
    if slot:
        b.clicked.connect(slot)
    if tip:
        b.setToolTip(tip)
    b.setCursor(Qt.PointingHandCursor)
    return b


def pill(text: str, kind: str = "Muted") -> QLabel:
    lb = QLabel(text)
    lb.setObjectName(f"Pill{kind}")
    return lb


class Card(QFrame):
    def __init__(self, parent: QWidget | None = None, spacing: int = 8) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(18, 16, 18, 16)
        self.lay.setSpacing(spacing)


class StatCard(Card):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.title = label(title, "Muted")
        self.value = label("0", "Big")
        self.lay.addWidget(self.title)
        self.lay.addWidget(self.value)

    def set(self, value: str) -> None:
        self.value.setText(value)


class Page(QScrollArea):
    """Scrollable page with a header - keeps everything reachable on small screens."""

    def __init__(self, title: str, subtitle: str = "") -> None:
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("Page")
        self.body = QVBoxLayout(inner)
        self.body.setContentsMargins(32, 28, 32, 28)
        self.body.setSpacing(16)
        self.title_label = label(title, "H1")
        self.body.addWidget(self.title_label)
        self.subtitle_label = label(subtitle, "Muted")
        if subtitle:
            self.body.addWidget(self.subtitle_label)
        self.setWidget(inner)

    def refresh(self) -> None:  # overridden by pages
        pass

    def finish(self) -> None:
        self.body.addStretch(1)


def clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.hide()  # otherwise it lingers at its old position until the event loop deletes it
            w.setParent(None)
            w.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


def fade_in(widget: QWidget, ms: int = 180) -> None:
    eff = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(eff)
    anim = QPropertyAnimation(eff, b"opacity", widget)
    anim.setDuration(ms)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.finished.connect(lambda: widget.setGraphicsEffect(None))
    anim.start(QPropertyAnimation.DeleteWhenStopped)


def open_path(path: str) -> None:
    QDesktopServices.openUrl(QUrl.fromLocalFile(path))


def open_url(url: str) -> None:
    QDesktopServices.openUrl(QUrl(url))


def human_size(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def short_path(path: str, keep: int = 2) -> str:
    parts = PurePath(path).parts
    return str(PurePath(*parts[-keep:])) if len(parts) > keep else path


def rule_summary(rule: Rule) -> str:
    c = rule.conditions
    what = ", ".join(e.upper() for e in c.extensions[:5]) + ("…" if len(c.extensions) > 5 else "")
    if c.name_contains:
        what = (what + " " if what else "") + "“" + "/".join(c.name_contains) + "”"
    if c.name_glob:
        what = (what + " " if what else "") + c.name_glob
    what = what or tr("rule.what_any")
    src = short_path(rule.watch_dir, 1)
    a = rule.action
    if a.type in (ActionType.MOVE, ActionType.COPY):
        return tr(f"rule.summary_{a.type.value}", what=what, src=src, dst=short_path(a.target_dir))
    if a.type == ActionType.RENAME:
        return tr("rule.summary_rename", what=what, src=src, tpl=a.rename_template)
    return tr("rule.summary_trash", what=what, src=src)


def pick_folder(parent: QWidget, start: str = "") -> str:
    return QFileDialog.getExistingDirectory(parent, tr("browse"), start or str(Path.home()))


def ensure_folders(parent: QWidget, ctx, rule: Rule) -> bool:
    """Ask the user to grant any folder the rule needs. Returns True when everything is allowed."""
    missing = ctx.service.missing_folders(rule)
    if not missing:
        return True
    ans = QMessageBox.question(parent, "GHOST AI", tr("folder.grant_q", folders="\n".join(f"• {m}" for m in missing)))
    if ans != QMessageBox.Yes:
        return False
    try:
        for m in missing:
            ctx.service.add_folder(m)
    except Blocked as b:
        QMessageBox.warning(parent, tr("safety.blocked"), tr(f"blocked.{b.reason}") + f"\n\n{b.path}")
        return False
    return True


# ---------------------------------------------------------------------------
# Rule editor
# ---------------------------------------------------------------------------

def _split(text: str) -> list[str]:
    return [t.strip().lstrip(".").lower() for t in text.replace(";", ",").split(",") if t.strip()]


class FolderField(QWidget):
    def __init__(self, value: str = "") -> None:
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit(value)
        lay.addWidget(self.edit, 1)
        lay.addWidget(button(tr("browse"), slot=self._pick))

    def _pick(self) -> None:
        f = pick_folder(self, self.edit.text())
        if f:
            self.edit.setText(os.path.normpath(f))

    def text(self) -> str:
        return self.edit.text().strip()


class RuleEditor(QDialog):
    def __init__(self, ctx, rule: Rule | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle(tr("rule.editor_title"))
        self.setMinimumWidth(560)
        base = rule or Rule(name="", watch_dir=ctx.known_folders().get("downloads", ""), conditions=Conditions(),
                            action=Action(ActionType.MOVE))
        self.rule = base
        lay = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        self.name = QLineEdit(base.name)
        self.watch = FolderField(base.watch_dir)
        self.exts = QLineEdit(", ".join(base.conditions.extensions))
        self.exts.setPlaceholderText(tr("rule.exts_ph"))
        self.contains = QLineEdit(", ".join(base.conditions.name_contains))
        self.contains.setPlaceholderText(tr("rule.contains_ph"))
        self.glob = QLineEdit(base.conditions.name_glob)
        self.glob.setPlaceholderText(tr("rule.glob_ph"))
        self.action = QComboBox()
        for t in ActionType:
            self.action.addItem(tr(f"action.{t.value}"), t.value)
        self.action.setCurrentIndex(list(ActionType).index(base.action.type))
        self.target = FolderField(base.action.target_dir)
        self.template = QLineEdit(base.action.rename_template)
        self.template.setToolTip(tr("rule.template_help"))
        self.case = QComboBox()
        for c in CaseMode:
            self.case.addItem(tr(f"case.{c.value}"), c.value)
        self.case.setCurrentIndex(list(CaseMode).index(base.action.case))
        self.spaces = QComboBox()
        for s in SpaceMode:
            self.spaces.addItem(tr(f"spaces.{s.value}"), s.value)
        self.spaces.setCurrentIndex(list(SpaceMode).index(base.action.spaces))
        self.trigger = QComboBox()
        for t in Trigger:
            self.trigger.addItem(tr(f"trigger.{t.value}"), t.value)
        self.trigger.setCurrentIndex(list(Trigger).index(base.trigger))
        self.conflict = QComboBox()
        for c in ConflictPolicy:
            self.conflict.addItem(tr(f"conflict.{c.value}"), c.value)
        self.conflict.setCurrentIndex(list(ConflictPolicy).index(base.conflict))
        self.recursive = QCheckBox(tr("rule.recursive"))
        self.recursive.setChecked(base.recursive)
        self.confirm = QCheckBox(tr("rule.confirm_each"))
        self.confirm.setChecked(base.confirm_each)
        self.enabled = QCheckBox(tr("rule.enabled"))
        self.enabled.setChecked(base.enabled)
        self.example = label("", "Muted")

        form.addRow(tr("rule.name"), self.name)
        form.addRow(tr("rule.watch"), self.watch)
        form.addRow(label(tr("rule.when"), "H2"))
        form.addRow(tr("rule.exts"), self.exts)
        form.addRow(tr("rule.contains"), self.contains)
        form.addRow(tr("rule.glob"), self.glob)
        form.addRow(label(tr("rule.then"), "H2"))
        form.addRow(tr("rule.action"), self.action)
        self.target_row_label = QLabel(tr("rule.target"))
        form.addRow(self.target_row_label, self.target)
        form.addRow(tr("rule.template"), self.template)
        form.addRow(tr("rule.case"), self.case)
        form.addRow(tr("rule.spaces"), self.spaces)
        form.addRow(tr("rule.example"), self.example)
        form.addRow(tr("rule.trigger"), self.trigger)
        form.addRow(tr("rule.conflict"), self.conflict)
        form.addRow("", self.recursive)
        form.addRow("", self.confirm)
        form.addRow("", self.enabled)
        lay.addLayout(form)
        self.error = label("", "PillDanger")
        self.error.hide()
        lay.addWidget(self.error)
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Save).setText(tr("save"))
        bb.button(QDialogButtonBox.Save).setObjectName("Primary")
        bb.button(QDialogButtonBox.Cancel).setText(tr("cancel"))
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        for w in (self.template, self.exts):
            w.textChanged.connect(self._update)
        for w in (self.action, self.case, self.spaces):
            w.currentIndexChanged.connect(self._update)
        self._update()

    def _build(self) -> Rule:
        atype = ActionType(self.action.currentData())
        r = Rule(
            id=self.rule.id, created_at=self.rule.created_at, source=self.rule.source,
            name=self.name.text().strip() or "Rule",
            watch_dir=os.path.normpath(self.watch.text()) if self.watch.text() else "",
            conditions=Conditions(extensions=_split(self.exts.text()),
                                  name_contains=[s.strip() for s in self.contains.text().split(",") if s.strip()],
                                  name_glob=self.glob.text().strip()),
            action=Action(type=atype,
                          target_dir=os.path.normpath(self.target.text()) if self.target.text() and atype in (
                              ActionType.MOVE, ActionType.COPY) else "",
                          rename_template=self.template.text().strip() or "{stem}{ext}",
                          case=CaseMode(self.case.currentData()), spaces=SpaceMode(self.spaces.currentData())),
            trigger=Trigger(self.trigger.currentData()), conflict=ConflictPolicy(self.conflict.currentData()),
            recursive=self.recursive.isChecked(), confirm_each=self.confirm.isChecked(),
            enabled=self.enabled.isChecked(),
        )
        return r

    def _update(self) -> None:
        atype = ActionType(self.action.currentData())
        needs_target = atype in (ActionType.MOVE, ActionType.COPY)
        self.target.setVisible(needs_target)
        self.target_row_label.setVisible(needs_target)
        exts = _split(self.exts.text())
        sample = f"My File.{exts[0] if exts else 'pdf'}"
        r = self._build()
        new = render_name(r.action, sample) if atype != ActionType.TRASH else sample
        self.example.setText(f"{sample}  →  {new}")

    def _save(self) -> None:
        from ..domain.validation import ValidationError, validate_rule_dict

        r = self._build()
        d = r.to_dict()
        try:
            validate_rule_dict(d)
        except ValidationError as exc:
            self.error.setText(str(exc))
            self.error.show()
            return
        if not ensure_folders(self, self.ctx, r):
            return
        try:
            self.ctx.service.save_rule(r)
        except Blocked as b:
            self.error.setText(tr(f"blocked.{b.reason}") + f" {b.path}")
            self.error.show()
            return
        self.rule = r
        self.accept()


# ---------------------------------------------------------------------------
# Dry-run preview dialog
# ---------------------------------------------------------------------------

class PreviewDialog(QDialog):
    """Shows exactly what will happen. Applying is a separate, explicit click."""

    def __init__(self, ctx, plans: list[PlannedAction], parent: QWidget | None = None, title: str = "") -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.plans = plans
        self.records: list[ActionRecord] = []
        self.setWindowTitle(title or tr("pv.title"))
        self.resize(820, 460)
        lay = QVBoxLayout(self)
        lay.addWidget(label(tr("pv.title"), "H2"))
        active = [p for p in plans if not p.skipped]
        skipped = len(plans) - len(active)
        lay.addWidget(label(tr("pv.count", n=len(active), s=skipped) if plans else tr("pv.nothing"), "Muted"))
        table = QTableWidget(len(plans), 4)
        table.setHorizontalHeaderLabels([tr("pv.action"), tr("pv.from"), tr("pv.to"), tr("pv.note")])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setAlternatingRowColors(True)
        for i, p in enumerate(plans):
            vals = [tr(f"action.{p.type.value}"), p.src,
                    p.dst if p.type != ActionType.TRASH else tr("safety.quarantine"),
                    tr(f"note.{p.note}") if p.note else ""]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(v)
                it.setToolTip(v)
                table.setItem(i, j, it)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        lay.addWidget(table, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(button(tr("cancel"), slot=self.reject))
        self.apply_btn = button(tr("pv.apply", n=len(active)), "Primary", self._apply)
        self.apply_btn.setEnabled(bool(active) and not ctx.service.paused)
        if ctx.service.paused:
            self.apply_btn.setToolTip(tr("status.paused"))
        row.addWidget(self.apply_btn)
        lay.addLayout(row)

    def _apply(self) -> None:
        self.records = self.ctx.service.execute([p for p in self.plans if not p.skipped])
        ok = sum(1 for r in self.records if r.status == Status.DONE)
        QMessageBox.information(self, "GHOST AI", tr("done.summary", ok=ok, bad=len(self.records) - ok))
        self.accept()
