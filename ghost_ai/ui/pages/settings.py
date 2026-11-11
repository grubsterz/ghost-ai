from __future__ import annotations

import json
from datetime import datetime

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLineEdit, QMessageBox, QWidget,
)

from ... import __version__
from ...ai.natural import OllamaProvider
from ...domain.validation import ValidationError, validate_rule_dict
from ...i18n import tr
from ...voice.stt import voice_available
from ..widgets import Card, Page, button, label, open_path


class _Sig(QObject):
    done = Signal(bool, list)


class _Probe(QRunnable):
    def __init__(self, p, s) -> None:
        super().__init__()
        self.p, self.s = p, s

    def run(self) -> None:
        self.s.done.emit(*self.p.status())


class SettingsPage(Page):
    def __init__(self, ctx) -> None:
        super().__init__(tr("set.title"))
        self.ctx = ctx

        look = Card()
        form = QFormLayout()
        self.lang = QComboBox()
        self.lang.addItem("Hrvatski", "hr")
        self.lang.addItem("English", "en")
        self.lang.setCurrentIndex(0 if ctx.setting("language", "en") == "hr" else 1)
        self.lang.currentIndexChanged.connect(self._lang)
        form.addRow(tr("set.language"), self.lang)
        self.theme = QComboBox()
        self.theme.addItem(tr("theme.dark"), "dark")
        self.theme.addItem(tr("theme.light"), "light")
        self.theme.setCurrentIndex(1 if ctx.setting("theme", "dark") == "light" else 0)
        self.theme.currentIndexChanged.connect(self._theme)
        form.addRow(tr("set.theme"), self.theme)
        self.scale = QComboBox()
        for s in (0.9, 1.0, 1.15, 1.3, 1.5):
            self.scale.addItem(f"{round(s * 100)} %", s)
        cur = ctx.setting("scale", 1.0)
        self.scale.setCurrentIndex(next((i for i in range(self.scale.count()) if self.scale.itemData(i) == cur), 1))
        self.scale.currentIndexChanged.connect(self._scale)
        form.addRow(tr("set.scale"), self.scale)
        look.lay.addLayout(form)
        self.body.addWidget(look)

        ai = Card()
        ai.lay.addWidget(label(tr("set.ai"), "H2"))
        self.ai_on = QCheckBox(tr("set.ai_enable"))
        self.ai_on.setChecked(bool(ctx.setting("ai_enabled", False)))
        self.ai_on.toggled.connect(lambda v: (ctx.set_setting("ai_enabled", v), ctx.bus.changed.emit()))
        ai.lay.addWidget(self.ai_on)
        erow = QHBoxLayout()
        self.engine = QComboBox()
        self.engine.addItem(tr("set.engine_builtin"), "builtin")
        self.engine.addItem(tr("set.engine_ollama"), "ollama")
        self.engine.setCurrentIndex(0 if ctx.setting("ai_engine", "builtin") == "builtin" else 1)
        self.engine.currentIndexChanged.connect(self._engine)
        erow.addWidget(label(tr("set.engine"), wrap=False))
        erow.addWidget(self.engine, 1)
        ai.lay.addLayout(erow)
        brow = QHBoxLayout()
        self.builtin_status = label("", "Muted")
        brow.addWidget(self.builtin_status, 1)
        self.builtin_btn = button(tr("agent.ai_setup"), "Primary", self._setup_builtin)
        brow.addWidget(self.builtin_btn)
        self.builtin_row = QWidget()
        self.builtin_row.setLayout(brow)
        ai.lay.addWidget(self.builtin_row)
        arow = QHBoxLayout()
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.addItem(ctx.setting("ai_model", "llama3.2:3b"))
        self.model.currentTextChanged.connect(lambda t: ctx.set_setting("ai_model", t.strip()))
        arow.addWidget(label(tr("set.ai_model"), wrap=False))
        arow.addWidget(self.model, 1)
        arow.addWidget(button(tr("set.ai_test"), slot=self._test))
        self.ollama_row = QWidget()
        self.ollama_row.setLayout(arow)
        ai.lay.addWidget(self.ollama_row)
        self.ai_status = label("", "Muted")
        ai.lay.addWidget(self.ai_status)
        self.ollama_help = label(tr("set.ai_help"), "Muted")
        ai.lay.addWidget(self.ollama_help)
        self.body.addWidget(ai)

        full = Card()
        full.lay.addWidget(label(tr("set.full_access"), "H2"))
        self.full_label = label("", "Muted")
        full.lay.addWidget(self.full_label)
        frow = QHBoxLayout()
        self.full_btn = button("", slot=self._toggle_full)
        frow.addWidget(self.full_btn)
        frow.addStretch(1)
        full.lay.addLayout(frow)
        self.body.addWidget(full)

        voice = Card()
        voice.lay.addWidget(label(tr("set.voice"), "H2"))
        vrow = QHBoxLayout()
        self.whisper = QComboBox()
        for m in ("tiny", "base", "small", "medium"):
            self.whisper.addItem(m)
        self.whisper.setCurrentText(ctx.setting("whisper_model", "small"))
        self.whisper.currentTextChanged.connect(lambda t: ctx.set_setting("whisper_model", t))
        vrow.addWidget(label(tr("set.voice_model"), wrap=False))
        vrow.addWidget(self.whisper)
        vrow.addStretch(1)
        voice.lay.addLayout(vrow)
        if not voice_available()[0]:
            voice.lay.addWidget(label(tr("voice.unavailable"), "Muted"))
        self.body.addWidget(voice)

        rules = Card()
        rules.lay.addWidget(label(tr("set.rules_io"), "H2"))
        rrow = QHBoxLayout()
        rrow.addWidget(button(tr("set.export"), slot=self._export))
        rrow.addWidget(button(tr("set.import"), slot=self._import))
        rrow.addStretch(1)
        rules.lay.addLayout(rrow)
        self.body.addWidget(rules)

        store = Card()
        store.lay.addWidget(label(tr("set.storage"), "H2"))
        store.lay.addWidget(label(str(ctx.data_dir), "Muted"))
        store.lay.addWidget(label(tr("set.telemetry")))
        srow = QHBoxLayout()
        srow.addWidget(button(tr("set.open_data"), slot=lambda: open_path(str(ctx.data_dir))))
        srow.addWidget(button(tr("set.onboarding"), slot=self._onboarding))
        srow.addStretch(1)
        store.lay.addLayout(srow)
        store.lay.addWidget(label(tr("about.version", v=__version__), "Muted"))
        self.body.addWidget(store)
        self.finish()
        self._sig = _Sig()
        self._sig.done.connect(self._tested)
        self.refresh()

    def _engine(self) -> None:
        self.ctx.set_setting("ai_engine", self.engine.currentData())
        self.ctx.bus.changed.emit()
        self.refresh()

    def _setup_builtin(self) -> None:
        from ..ai_setup import AiSetupDialog
        if AiSetupDialog(self.ctx, self.window()).exec():
            self.ai_on.setChecked(True)
        self.refresh()

    def refresh(self) -> None:
        from ...ai.embedded import MODELS, describe, engine_available
        from ...i18n import language
        builtin = self.ctx.setting("ai_engine", "builtin") == "builtin"
        self.builtin_row.setVisible(builtin)
        self.ollama_row.setVisible(not builtin)
        self.ollama_help.setVisible(not builtin)
        self.ai_status.setVisible(not builtin)
        eng = self.ctx.engine()
        key = self.ctx.setting("builtin_model", "smart")
        if not engine_available():
            self.builtin_status.setText(tr("ai.no_engine"))
        elif eng is not None:
            self.builtin_status.setText(tr("ai.ready_model", model=describe(key, language())))
        else:
            self.builtin_status.setText(tr("ai.not_downloaded"))
        self.builtin_btn.setText(tr("ai.change") if eng is not None else tr("agent.ai_setup"))
        on = bool(self.ctx.setting("full_access", False))
        self.full_label.setText(tr("set.full_on") if on else tr("set.full_off"))
        self.full_btn.setText(tr("agent.disable") if on else tr("agent.enable"))
        self.full_btn.setObjectName("" if on else "Primary")
        self.full_btn.style().unpolish(self.full_btn)
        self.full_btn.style().polish(self.full_btn)

    def _toggle_full(self) -> None:
        on = bool(self.ctx.setting("full_access", False))
        if not on and QMessageBox.warning(self, tr("agent.enable"), tr("agent.enable_q"),
                                          QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        self.ctx.set_setting("full_access", not on)
        self.refresh()
        self.ctx.bus.changed.emit()

    def _lang(self) -> None:
        self.ctx.set_setting("language", self.lang.currentData())
        self.ctx.bus.relanguage.emit()

    def _theme(self) -> None:
        self.ctx.set_setting("theme", self.theme.currentData())
        self.ctx.bus.restyle.emit()

    def _scale(self) -> None:
        self.ctx.set_setting("scale", self.scale.currentData())
        self.ctx.bus.restyle.emit()

    def _onboarding(self) -> None:
        from ..onboarding import Onboarding
        Onboarding(self.ctx, self.window()).exec()

    def _test(self) -> None:
        try:
            p = OllamaProvider(self.ctx.config.ollama_url, self.model.currentText())
        except ValueError as exc:
            self.ai_status.setText(str(exc))
            return
        self.ai_status.setText("…")
        QThreadPool.globalInstance().start(_Probe(p, self._sig))

    def _tested(self, ok: bool, models: list) -> None:
        model = self.model.currentText()
        if not ok:
            self.ai_status.setText(tr("status.ai_off"))
            return
        for m in models:
            if self.model.findText(m) < 0:
                self.model.addItem(m)
        has = any(m == model or m.split(":")[0] == model for m in models)
        self.ai_status.setText(tr("status.ai_ready", model=model) if has else tr("status.ai_nomodel", model=model))

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, tr("set.export"),
                                              f"ghost-ai-rules-{datetime.now():%Y-%m-%d}.json", "JSON (*.json)")
        if not path:
            return
        data = {"app": "GHOST AI", "version": 1, "rules": [r.to_dict() for r in self.ctx.service.rules()],
                "quick_actions": self.ctx.store.list_quick_actions()}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, tr("set.import"), "", "JSON (*.json)")
        if not path:
            return
        ok, bad = import_rules_file(self.ctx, path)
        QMessageBox.information(self, "GHOST AI", tr("set.imported", ok=ok, bad=bad) + "\n" +
                                tr("set.imported_disabled"))


def import_rules_file(ctx, path: str) -> tuple[int, int]:
    """Import rules from JSON. Every rule is validated and imported switched OFF.
    Folders are not granted automatically - the user enables each rule after review."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return 0, 1
    items = data.get("rules", []) if isinstance(data, dict) else data if isinstance(data, list) else []
    ok = bad = 0
    for item in items[:500]:
        try:
            rule = validate_rule_dict(item)
        except ValidationError:
            bad += 1
            continue
        rule.enabled = False
        rule.source = "import"
        ctx.store.save_rule(rule)
        ok += 1
    ctx.bus.changed.emit()
    return ok, bad
