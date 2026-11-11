from __future__ import annotations

import os
from pathlib import PurePath

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QFrame, QHBoxLayout, QInputDialog, QListWidget, QMessageBox, QVBoxLayout,
)

from ...domain.matching import is_temporary_name
from ...domain.models import ActionType, PlannedAction, Status
from ...i18n import explain, tr
from ...safety.guard import Blocked
from ...teach.generalizer import DemoRecorder, DemoStep, generalize
from ..widgets import Card, Page, PreviewDialog, RuleEditor, button, clear_layout, label, pick_folder, pill


class TeachPage(Page):
    def __init__(self, ctx) -> None:
        super().__init__(tr("teach.title"), tr("teach.sub"))
        self.ctx = ctx
        self.recorder = DemoRecorder()
        self.folder = ""

        controls = QHBoxLayout()
        self.pick_btn = button(tr("teach.pick"), slot=self.pick)
        self.start_btn = button(tr("teach.start"), "Primary", self.start)
        self.stop_btn = button(tr("teach.stop"), slot=self.stop)
        for b in (self.pick_btn, self.start_btn, self.stop_btn):
            controls.addWidget(b)
        controls.addStretch(1)
        self.body.addLayout(controls)
        self.folder_label = label("", "Muted")
        self.body.addWidget(self.folder_label)

        self.banner = QFrame()
        self.banner.setObjectName("RecBanner")
        bl = QHBoxLayout(self.banner)
        self.rec_label = label(tr("teach.recording"), "PillDanger", wrap=False)
        bl.addWidget(self.rec_label)
        bl.addStretch(1)
        self.banner.hide()
        self.body.addWidget(self.banner)
        self._blink = QTimer(self)
        self._blink.timeout.connect(lambda: self.rec_label.setVisible(not self.rec_label.isVisible()))

        work = QHBoxLayout()
        left = Card()
        self.files = QListWidget()
        self.files.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.files.setMinimumHeight(240)
        left.lay.addWidget(self.files)
        act = QHBoxLayout()
        self.move_btn = button(tr("teach.move"), slot=lambda: self.do(ActionType.MOVE))
        self.copy_btn = button(tr("teach.copy"), slot=lambda: self.do(ActionType.COPY))
        self.rename_btn = button(tr("teach.rename"), slot=lambda: self.do(ActionType.RENAME))
        for b in (self.move_btn, self.copy_btn, self.rename_btn):
            act.addWidget(b)
        left.lay.addLayout(act)
        self.really = QCheckBox(tr("teach.really"))
        left.lay.addWidget(self.really)
        work.addWidget(left, 3)

        right = Card()
        right.lay.addWidget(label(tr("teach.steps"), "H2"))
        self.steps = QListWidget()
        self.steps.setWordWrap(True)
        right.lay.addWidget(self.steps)
        right.lay.addWidget(button(tr("teach.undo_step"), slot=self.undo_step))
        work.addWidget(right, 2)
        self.body.addLayout(work)

        self.suggest_title = label(tr("teach.suggestions"), "H2")
        self.suggest_title.hide()
        self.body.addWidget(self.suggest_title)
        self.suggest_box = QVBoxLayout()
        self.body.addLayout(self.suggest_box)
        self.finish()
        self._sync()

    # ---- state ------------------------------------------------------------
    def _sync(self) -> None:
        rec = self.recorder.active
        self.start_btn.setEnabled(bool(self.folder) and not rec)
        self.stop_btn.setEnabled(rec)
        self.pick_btn.setEnabled(not rec)
        for b in (self.move_btn, self.copy_btn, self.rename_btn):
            b.setEnabled(rec)
        self.banner.setVisible(rec)
        if rec:
            self._blink.start(700)
        else:
            self._blink.stop()
            self.rec_label.show()

    def _load_files(self) -> None:
        self.files.clear()
        if not self.folder or not os.path.isdir(self.folder):
            return
        with os.scandir(self.folder) as it:
            names = sorted(e.name for e in it if e.is_file() and not is_temporary_name(e.name))
        self.files.addItems(names)

    def _names(self) -> list[str]:
        return [self.files.item(i).text() for i in range(self.files.count())]

    def pick(self) -> None:
        f = pick_folder(self, self.folder)
        if not f:
            return
        f = os.path.normpath(f)
        if not self.ctx.service.guard.is_allowed_folder(f):
            if QMessageBox.question(self, "GHOST AI", tr("folder.grant_q", folders=f)) != QMessageBox.Yes:
                return
            try:
                self.ctx.service.add_folder(f)
            except Blocked as b:
                QMessageBox.warning(self, tr("safety.blocked"), tr(f"blocked.{b.reason}"))
                return
        self.folder = f
        self.folder_label.setText(f)
        self._load_files()
        self._sync()

    def start(self) -> None:
        self.recorder.start(self.folder, self._names())
        self.steps.clear()
        clear_layout(self.suggest_box)
        self.suggest_title.hide()
        self._sync()

    def undo_step(self) -> None:
        if self.recorder.undo_last():
            self.steps.takeItem(self.steps.count() - 1)

    def do(self, atype: ActionType) -> None:
        selected = [i.text() for i in self.files.selectedItems()]
        if not selected:
            return
        target = ""
        if atype in (ActionType.MOVE, ActionType.COPY):
            target = pick_folder(self, self.folder)
            if not target:
                return
            target = os.path.normpath(target)
        for name in selected:
            src = os.path.join(self.folder, name)
            if atype == ActionType.RENAME:
                new, ok = QInputDialog.getText(self, tr("teach.rename"), tr("teach.rename_prompt", name=name),
                                               text=name)
                if not ok or not new.strip() or new == name or "/" in new or "\\" in new:
                    continue
                dst = os.path.join(self.folder, new.strip())
            else:
                dst = os.path.join(target, name)
            step = DemoStep(atype, src, dst)
            if self.really.isChecked() and not self._perform(step):
                continue
            self.recorder.record(step)
            verb = tr(f"action.{atype.value}")
            self.steps.addItem(f"{verb}: {name} → {PurePath(dst).name if atype == ActionType.RENAME else dst}")
        if self.really.isChecked():
            self._load_files()

    def _perform(self, step: DemoStep) -> bool:
        folder = str(PurePath(step.dst).parent)
        if not self.ctx.service.guard.is_allowed_folder(folder):
            if QMessageBox.question(self, "GHOST AI", tr("folder.grant_q", folders=folder)) != QMessageBox.Yes:
                return False
            try:
                self.ctx.service.add_folder(folder)
            except Blocked as b:
                QMessageBox.warning(self, tr("safety.blocked"), tr(f"blocked.{b.reason}"))
                return False
        recs = self.ctx.service.execute([PlannedAction(step.type, step.src, step.dst, rule_name="Teach Mode")])
        if recs and recs[0].status == Status.DONE:
            step.dst = recs[0].dst
            return True
        QMessageBox.warning(self, "GHOST AI", f"{tr('status.' + recs[0].status.value)}: {recs[0].message}")
        return False

    def stop(self) -> None:
        steps = self.recorder.stop()
        self._sync()
        if not steps:
            QMessageBox.information(self, "GHOST AI", tr("teach.no_steps"))
            return
        names = self.recorder.folder_listing.get(self.folder, [])
        proposals = generalize(steps, names)
        clear_layout(self.suggest_box)
        self.suggest_title.show()
        for prop in proposals:
            card = Card(spacing=4)
            head = QHBoxLayout()
            head.addWidget(label(prop.rule.name, "H2", wrap=False))
            kind = "Ok" if prop.confidence >= 0.7 else "Warn"
            head.addWidget(pill(tr("teach.confidence", p=round(prop.confidence * 100)), kind))
            head.addStretch(1)
            card.lay.addLayout(head)
            from ..widgets import rule_summary
            card.lay.addWidget(label(rule_summary(prop.rule), "Muted"))
            for e in prop.explanation:
                card.lay.addWidget(label("• " + explain(e)))
            row = QHBoxLayout()
            row.addWidget(button(tr("teach.review"), "Primary", lambda _=False, p=prop: self.review(p)))
            row.addStretch(1)
            card.lay.addLayout(row)
            self.suggest_box.addWidget(card)

    def review(self, prop) -> None:
        prop.rule.enabled = True
        ed = RuleEditor(self.ctx, prop.rule, self)
        if ed.exec():
            PreviewDialog(self.ctx, self.ctx.service.preview_rule(ed.rule), self).exec()
