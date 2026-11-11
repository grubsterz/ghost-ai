from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QInputDialog, QListWidget, QMessageBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from ...domain.models import Status
from ...engine.executor import empty_quarantine, quarantine_size
from ...i18n import tr
from ...safety.guard import Blocked
from ..widgets import Card, Page, button, clear_layout, human_size, label, open_path, pick_folder


class SafetyPage(Page):
    def __init__(self, ctx) -> None:
        super().__init__(tr("safety.title"))
        self.ctx = ctx

        prom = Card(spacing=4)
        prom.lay.addWidget(label(tr("safety.promises"), "H2"))
        for i in range(1, 8):
            prom.lay.addWidget(label("✓  " + tr(f"safety.p{i}")))
        self.body.addWidget(prom)

        pause = Card()
        prow = QHBoxLayout()
        self.pause_label = label("", "H2")
        prow.addWidget(self.pause_label)
        prow.addStretch(1)
        self.pause_btn = button("", slot=lambda: ctx.service.set_paused(not ctx.service.paused))
        prow.addWidget(self.pause_btn)
        pause.lay.addLayout(prow)
        self.body.addWidget(pause)

        self.appr_card = Card()
        self.appr_card.lay.addWidget(label(tr("safety.approvals"), "H2"))
        self.appr_box = QVBoxLayout()
        self.appr_card.lay.addLayout(self.appr_box)
        self.body.addWidget(self.appr_card)

        fold = Card()
        fold.lay.addWidget(label(tr("safety.folders"), "H2"))
        self.folders = QListWidget()
        self.folders.setMaximumHeight(150)
        fold.lay.addWidget(self.folders)
        frow = QHBoxLayout()
        frow.addWidget(button(tr("safety.add_folder"), slot=self.add_folder))
        frow.addWidget(button(tr("remove"), slot=self.remove_folder))
        frow.addStretch(1)
        fold.lay.addLayout(frow)
        self.body.addWidget(fold)

        q = Card()
        q.lay.addWidget(label(tr("safety.quarantine"), "H2"))
        self.q_info = label("", "Muted")
        q.lay.addWidget(self.q_info)
        qrow = QHBoxLayout()
        qrow.addWidget(button(tr("safety.q_open"), slot=lambda: open_path(ctx.service.quarantine_dir)))
        self.q_empty = button(tr("safety.q_empty"), "Danger", self.empty_q)
        qrow.addWidget(self.q_empty)
        qrow.addStretch(1)
        q.lay.addLayout(qrow)
        self.body.addWidget(q)

        j = Card()
        jh = QHBoxLayout()
        jh.addWidget(label(tr("safety.journal"), "H2"))
        jh.addStretch(1)
        jh.addWidget(button(tr("safety.undo_sel"), slot=self.undo_selected))
        jh.addWidget(button(tr("safety.logs"), slot=lambda: open_path(str(ctx.log_file))))
        j.lay.addLayout(jh)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([tr("col.time"), tr("col.action"), tr("col.file"), tr("col.to"),
                                              tr("col.status"), tr("col.rule")])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumHeight(260)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        j.lay.addWidget(self.table)
        self.body.addWidget(j)
        self.finish()
        self.refresh()

    def add_folder(self) -> None:
        f = pick_folder(self)
        if not f:
            return
        try:
            self.ctx.service.add_folder(os.path.normpath(f))
        except Blocked as b:
            QMessageBox.warning(self, tr("safety.blocked"), tr(f"blocked.{b.reason}") + f"\n\n{b.path}")

    def remove_folder(self) -> None:
        it = self.folders.currentItem()
        if it:
            self.ctx.service.remove_folder(it.text())

    def empty_q(self) -> None:
        n, _ = quarantine_size(self.ctx.service.quarantine_dir)
        if not n:
            return
        word = tr("safety.q_word")
        text, ok = QInputDialog.getText(self, tr("safety.q_empty"), tr("safety.q_confirm", n=n))
        if ok and text.strip() == word:
            empty_quarantine(self.ctx.service.quarantine_dir)
            self.refresh()

    def undo_selected(self) -> None:
        rows = {i.row() for i in self.table.selectedItems()}
        for row in sorted(rows):
            rid = self.table.item(row, 0).data(Qt.UserRole)
            self.ctx.service.undo_record(int(rid))

    def refresh(self) -> None:
        svc = self.ctx.service
        self.pause_label.setText(tr("status.paused") if svc.paused else tr("status.watching",
                                                                        n=len(svc.watched_folders())))
        self.pause_btn.setText(tr("dash.resume_all") if svc.paused else tr("dash.pause_all"))
        self.pause_btn.setObjectName("Primary" if svc.paused else "Danger")
        self.pause_btn.style().unpolish(self.pause_btn)
        self.pause_btn.style().polish(self.pause_btn)

        clear_layout(self.appr_box)
        self.appr_card.setVisible(bool(svc.approvals))
        for a in list(svc.approvals):
            row = QHBoxLayout()
            row.addWidget(label(f"{tr('action.' + a.plan.type.value)}: {a.plan.src} → {a.plan.dst}"), 1)
            row.addWidget(button(tr("safety.approve"), "Primary", lambda _=False, i=a.id: svc.approve(i)))
            row.addWidget(button(tr("safety.reject"), slot=lambda _=False, i=a.id: svc.reject(i)))
            self.appr_box.addLayout(row)

        self.folders.clear()
        self.folders.addItems(svc.folders())
        n, size = quarantine_size(svc.quarantine_dir)
        self.q_info.setText(tr("safety.q_info", n=n, size=human_size(size)) + f"\n{svc.quarantine_dir}")
        self.q_empty.setEnabled(n > 0)

        recs = svc.store.records(limit=300, include_dry_run=False)
        self.table.setRowCount(len(recs))
        for i, r in enumerate(recs):
            vals = [r.ts.replace("T", " "), tr(f"action.{r.type.value}"), r.src, r.dst, tr(f"status.{r.status.value}"),
                    r.rule_name]
            for jx, v in enumerate(vals):
                it = QTableWidgetItem(v)
                it.setToolTip(f"{v}\n{r.message}" if r.message else v)
                if jx == 0:
                    it.setData(Qt.UserRole, r.id)
                if r.status in (Status.FAILED, Status.BLOCKED) and jx == 4:
                    it.setForeground(Qt.red)
                self.table.setItem(i, jx, it)
        self.table.resizeColumnToContents(0)
