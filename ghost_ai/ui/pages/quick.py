from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QVBoxLayout,
)

from ...domain.validation import ValidationError
from ...engine.quick import QuickAction, plan_quick_action
from ...i18n import tr
from ..widgets import Card, FolderField, Page, PreviewDialog, button, clear_layout, label, open_path


class QuickEditor(QDialog):
    def __init__(self, ctx, qa: QuickAction | None, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.qa = qa or QuickAction(name="")
        self.setWindowTitle(tr("qa.new"))
        self.setMinimumWidth(480)
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(self.qa.name)
        form.addRow(tr("qa.name"), self.name)
        self.rules = QListWidget()
        chosen = {s["rule_id"] for s in self.qa.steps if s["type"] == "run_rule"}
        for r in ctx.service.rules():
            it = QListWidgetItem(r.name)
            it.setData(Qt.UserRole, r.id)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if r.id in chosen else Qt.Unchecked)
            self.rules.addItem(it)
        form.addRow(tr("qa.rules"), self.rules)
        opened = next((s["path"] for s in self.qa.steps if s["type"] == "open_folder"), "")
        self.folder = FolderField(opened)
        form.addRow(tr("qa.open"), self.folder)
        lay.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Save).setText(tr("save"))
        bb.button(QDialogButtonBox.Cancel).setText(tr("cancel"))
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _save(self) -> None:
        steps = [{"type": "run_rule", "rule_id": self.rules.item(i).data(Qt.UserRole)}
                 for i in range(self.rules.count()) if self.rules.item(i).checkState() == Qt.Checked]
        if self.folder.text():
            if not self.ctx.service.guard.is_allowed_folder(self.folder.text()):
                QMessageBox.warning(self, "GHOST AI", tr("blocked.outside_allowed"))
                return
            steps.append({"type": "open_folder", "path": self.folder.text()})
        try:
            qa = QuickAction.from_dict({"id": self.qa.id, "name": self.name.text(), "steps": steps})
        except ValidationError as exc:
            QMessageBox.warning(self, "GHOST AI", str(exc))
            return
        self.ctx.store.save_quick_action(qa.id, qa.to_dict())
        self.accept()


class QuickPage(Page):
    def __init__(self, ctx) -> None:
        super().__init__(tr("qa.title"), tr("qa.sub"))
        self.ctx = ctx
        top = QHBoxLayout()
        self.new_btn = button("+ " + tr("qa.new"), "Primary", self.new)
        top.addWidget(self.new_btn)
        top.addStretch(1)
        self.body.addLayout(top)
        self.box = QVBoxLayout()
        self.body.addLayout(self.box)
        self.finish()
        self.refresh()

    def new(self) -> None:
        if not self.ctx.service.rules():
            QMessageBox.information(self, "GHOST AI", tr("qa.needs_rules"))
            return
        if QuickEditor(self.ctx, None, self).exec():
            self.refresh()

    def run(self, qa: QuickAction) -> None:
        plan = plan_quick_action(qa, self.ctx.service)
        if plan.problems:
            QMessageBox.warning(self, "GHOST AI", "\n".join(sorted(set(plan.problems))))
        if plan.actions:
            PreviewDialog(self.ctx, plan.actions, self, title=qa.name).exec()
        for f in plan.open_folders:
            open_path(f)

    def refresh(self) -> None:
        clear_layout(self.box)
        items = self.ctx.store.list_quick_actions()
        if not items:
            self.box.addWidget(label(tr("qa.empty"), "Muted"))
        names = {r.id: r.name for r in self.ctx.service.rules()}
        for d in items:
            try:
                qa = QuickAction.from_dict(d)
            except ValidationError:
                continue
            card = Card(spacing=4)
            card.lay.addWidget(label(qa.name, "H2"))
            desc = [names.get(s["rule_id"], "?") if s["type"] == "run_rule" else "📂 " + s["path"] for s in qa.steps]
            card.lay.addWidget(label(" → ".join(desc) or "-", "Muted"))
            row = QHBoxLayout()
            row.addWidget(button(tr("qa.run"), "Primary", lambda _=False, q=qa: self.run(q)))
            row.addWidget(button(tr("edit"), slot=lambda _=False, q=qa: QuickEditor(self.ctx, q, self).exec()
                                 and self.refresh()))
            row.addStretch(1)
            row.addWidget(button(tr("delete"), "Danger",
                                 lambda _=False, q=qa: (self.ctx.store.delete_quick_action(q.id), self.refresh())))
            card.lay.addLayout(row)
            self.box.addWidget(card)
