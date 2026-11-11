from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QMessageBox, QSizePolicy, QVBoxLayout

from ...domain.models import Trigger
from ...i18n import tr
from ...templates import TEMPLATE_KEYS, build_template
from ..widgets import Card, PreviewDialog, RuleEditor, Page, button, clear_layout, label, pill


class FilesPage(Page):
    def __init__(self, ctx) -> None:
        super().__init__(tr("files.title"), tr("files.sub"))
        self.ctx = ctx
        top = QHBoxLayout()
        top.addWidget(button("+ " + tr("dash.new_rule"), "Primary", self.new_rule))
        top.addStretch(1)
        self.body.addLayout(top)

        tpl = Card()
        tpl.lay.addWidget(label(tr("files.templates"), "H2"))
        grid = QGridLayout()
        grid.setSpacing(8)
        for i, key in enumerate(TEMPLATE_KEYS):
            b = button(tr(f"tpl.{key}"), slot=lambda _=False, k=key: self.from_template(k))
            b.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            b.setToolTip(tr(f"tpl.{key}"))
            grid.addWidget(b, i // 2, i % 2)
        tpl.lay.addLayout(grid)
        self.body.addWidget(tpl)

        self.list_box = QVBoxLayout()
        self.list_box.setSpacing(10)
        self.body.addLayout(self.list_box)
        self.finish()
        self.refresh()

    def new_rule(self) -> None:
        if RuleEditor(self.ctx, parent=self).exec():
            self.refresh()

    def from_template(self, key: str) -> None:
        rule = build_template(key, self.ctx.known_folders())
        ed = RuleEditor(self.ctx, rule, parent=self)
        if ed.exec():
            self.preview(ed.rule)

    def edit(self, rule) -> None:
        if RuleEditor(self.ctx, rule, parent=self).exec():
            self.refresh()

    def delete(self, rule) -> None:
        if QMessageBox.question(self, "GHOST AI", tr("rule.delete_q", name=rule.name)) == QMessageBox.Yes:
            self.ctx.service.delete_rule(rule.id)

    def toggle(self, rule) -> None:
        rule.enabled = not rule.enabled
        self.ctx.service.save_rule(rule)

    def preview(self, rule) -> None:
        plans = self.ctx.service.preview_rule(rule)
        PreviewDialog(self.ctx, plans, self).exec()

    def refresh(self) -> None:
        from ..widgets import rule_summary

        clear_layout(self.list_box)
        rules = self.ctx.service.rules()
        if not rules:
            self.list_box.addWidget(label(tr("dash.empty"), "Muted"))
        for rule in rules:
            card = Card(spacing=6)
            head = QHBoxLayout()
            head.addWidget(label(rule.name, "H2", wrap=False))
            if not rule.enabled:
                head.addWidget(pill(tr("rule.disabled_badge"), "Warn"))
            if rule.trigger == Trigger.MANUAL:
                head.addWidget(pill(tr("rule.manual_badge")))
            if rule.confirm_each:
                head.addWidget(pill(tr("rule.ask_badge")))
            if self.ctx.service.missing_folders(rule):
                head.addWidget(pill(tr("blocked.outside_allowed"), "Danger"))
            head.addStretch(1)
            head.addStretch(1)
            card.lay.addLayout(head)
            card.lay.addWidget(label(rule_summary(rule), "Muted"))
            row = QHBoxLayout()
            row.addWidget(button(tr("run_now"), slot=lambda _=False, r=rule: self.preview(r)))
            row.addWidget(button(tr("edit"), slot=lambda _=False, r=rule: self.edit(r)))
            row.addWidget(button(tr("rule.turn_off") if rule.enabled else tr("rule.turn_on"), slot=lambda _=False, r=rule: self.toggle(r)))
            row.addStretch(1)
            row.addWidget(button(tr("delete"), "Danger", lambda _=False, r=rule: self.delete(r)))
            card.lay.addLayout(row)
            self.list_box.addWidget(card)
