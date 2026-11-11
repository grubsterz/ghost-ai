from __future__ import annotations

from PySide6.QtCore import QThreadPool, QRunnable, QObject, Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QListWidget, QListWidgetItem

from ...domain.models import Status
from ...i18n import tr
from ..widgets import Card, Page, StatCard, button, label, pill, short_path


class _AiProbe(QObject):
    done = Signal(bool, list)


class _ProbeTask(QRunnable):
    def __init__(self, provider, sig: _AiProbe) -> None:
        super().__init__()
        self.provider, self.sig = provider, sig

    def run(self) -> None:
        ok, models = self.provider.status()
        self.sig.done.emit(ok, models)


class DashboardPage(Page):
    def __init__(self, ctx) -> None:
        super().__init__(tr("dash.title"), tr("tagline"))
        self.ctx = ctx
        # status row
        status = Card()
        row = QHBoxLayout()
        self.engine_pill = pill("")
        self.ai_pill = pill("")
        row.addWidget(label(tr("dash.engine"), "Muted", wrap=False))
        row.addWidget(self.engine_pill)
        row.addSpacing(18)
        row.addWidget(label(tr("dash.ai"), "Muted", wrap=False))
        row.addWidget(self.ai_pill)
        row.addStretch(1)
        self.pause_btn = button("", slot=self._toggle_pause)
        row.addWidget(self.pause_btn)
        status.lay.addLayout(row)
        self.body.addWidget(status)

        grid = QGridLayout()
        grid.setSpacing(14)
        self.s_rules = StatCard(tr("dash.rules_active"))
        self.s_24 = StatCard(tr("dash.actions_24h"))
        self.s_7d = StatCard(tr("dash.actions_7d"))
        self.s_undo = StatCard(tr("dash.undone"))
        for i, w in enumerate((self.s_rules, self.s_24, self.s_7d, self.s_undo)):
            grid.addWidget(w, 0, i)
        self.body.addLayout(grid)

        self.empty = Card()
        self.empty.lay.addWidget(label(tr("dash.empty")))
        er = QHBoxLayout()
        er.addWidget(button(tr("dash.new_rule"), "Primary", lambda: ctx.bus.navigate.emit("files")))
        er.addWidget(button(tr("dash.teach"), slot=lambda: ctx.bus.navigate.emit("teach")))
        er.addWidget(button(tr("dash.ask"), slot=lambda: ctx.bus.navigate.emit("natural")))
        er.addStretch(1)
        self.empty.lay.addLayout(er)
        self.body.addWidget(self.empty)

        recent = Card()
        rh = QHBoxLayout()
        rh.addWidget(label(tr("dash.recent"), "H2"))
        rh.addStretch(1)
        self.undo_btn = button(tr("undo_last"), slot=self._undo)
        rh.addWidget(self.undo_btn)
        recent.lay.addLayout(rh)
        self.recent = QListWidget()
        self.recent.setMinimumHeight(220)
        recent.lay.addWidget(self.recent)
        self.body.addWidget(recent, 1)

        self._probe = _AiProbe()
        self._probe.done.connect(self._ai_result)
        self.refresh()

    def _toggle_pause(self) -> None:
        self.ctx.service.set_paused(not self.ctx.service.paused)

    def _undo(self) -> None:
        self.ctx.service.undo_last()

    def refresh(self) -> None:
        svc = self.ctx.service
        rules = svc.rules()
        st = svc.store.stats()
        self.s_rules.set(str(sum(1 for r in rules if r.enabled)))
        self.s_24.set(str(st["done_24h"]))
        self.s_7d.set(str(st["done_7d"]))
        self.s_undo.set(str(st["undone_total"]))
        self.empty.setVisible(not rules)
        if svc.paused:
            self.engine_pill.setText(tr("status.paused"))
            self.engine_pill.setObjectName("PillWarn")
            self.pause_btn.setText(tr("dash.resume_all"))
        elif svc.watching and svc.watched_folders():
            self.engine_pill.setText(tr("status.watching", n=len(svc.watched_folders())))
            self.engine_pill.setObjectName("PillOk")
            self.pause_btn.setText(tr("dash.pause_all"))
        else:
            self.engine_pill.setText(tr("status.idle"))
            self.engine_pill.setObjectName("PillMuted")
            self.pause_btn.setText(tr("dash.pause_all"))
        self.engine_pill.style().unpolish(self.engine_pill)
        self.engine_pill.style().polish(self.engine_pill)

        self.recent.clear()
        recs = svc.store.records(limit=30, include_dry_run=False)
        if not recs:
            self.recent.addItem(QListWidgetItem(tr("none_yet")))
        for r in recs:
            mark = {"done": "✓", "undone": "↶", "skipped": "–", "failed": "✕", "blocked": "⛔"}.get(r.status.value, "·")
            where = short_path(r.dst) if r.type.value != "trash" else tr("safety.quarantine")
            text = f"{mark}  {r.ts[11:16]}  {tr('action.' + r.type.value)}  {short_path(r.src, 1)}  →  {where}"
            if r.status not in (Status.DONE,):
                text += f"   [{tr('status.' + r.status.value)}]"
            it = QListWidgetItem(text)
            it.setToolTip(f"{r.src}\n→ {r.dst}\n{r.rule_name} {r.message}")
            self.recent.addItem(it)
        self.undo_btn.setEnabled(svc.store.last_undoable_batch() is not None)
        self._refresh_ai()

    def _refresh_ai(self) -> None:
        import time
        now = time.monotonic()
        if now - getattr(self, "_last_probe", -999) < 20:
            return
        self._last_probe = now
        provider = self.ctx.ollama()
        if provider is None:
            self._ai_result(False, [], disabled=True)
            return
        QThreadPool.globalInstance().start(_ProbeTask(provider, self._probe))

    def _ai_result(self, ok: bool, models: list, disabled: bool = False) -> None:
        model = self.ctx.setting("ai_model", "llama3.2:3b")
        if ok and any(m == model or m.split(":")[0] == model for m in models):
            self.ai_pill.setText(tr("status.ai_ready", model=model))
            self.ai_pill.setObjectName("PillOk")
        elif ok:
            self.ai_pill.setText(tr("status.ai_nomodel", model=model))
            self.ai_pill.setObjectName("PillWarn")
        else:
            self.ai_pill.setText(tr("status.ai_off"))
            self.ai_pill.setObjectName("PillMuted")
        self.ai_pill.style().unpolish(self.ai_pill)
        self.ai_pill.style().polish(self.ai_pill)
