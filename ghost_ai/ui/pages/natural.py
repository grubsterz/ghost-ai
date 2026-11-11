from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPlainTextEdit, QVBoxLayout

from ...ai.natural import propose_rule
from ...i18n import language, tr
from ...voice.stt import VoiceRecorder, voice_available
from ..widgets import Card, Page, PreviewDialog, RuleEditor, button, clear_layout, label, pill, rule_summary

EXAMPLES = {
    "en": ["Move all PDFs from Downloads to Documents", "Copy images from Desktop to Pictures",
           "Move zip files from Downloads into Documents"],
    "hr": ["Premjesti sve PDF-ove iz Preuzimanja u Dokumente", "Kopiraj slike s radne površine u mapu Slike",
           "Premjesti arhive iz Preuzimanja u Dokumente"],
}


class _Sig(QObject):
    done = Signal(object)
    text = Signal(str)
    error = Signal(str)


class _Job(QRunnable):
    def __init__(self, fn, sig_ok, sig_err) -> None:
        super().__init__()
        self.fn, self.ok, self.err = fn, sig_ok, sig_err

    def run(self) -> None:
        try:
            self.ok.emit(self.fn())
        except Exception as exc:  # surfaced to the user, never swallowed
            self.err.emit(str(exc))


class NaturalPage(Page):
    def __init__(self, ctx) -> None:
        super().__init__(tr("nl.title"), tr("nl.sub"))
        self.ctx = ctx
        box = Card()
        self.input = QPlainTextEdit()
        self.input.setPlaceholderText(tr("nl.placeholder"))
        self.input.setFixedHeight(90)
        box.lay.addWidget(self.input)
        row = QHBoxLayout()
        self.go = button(tr("nl.go"), "Primary", self.suggest)
        row.addWidget(self.go)
        self.mic = button(tr("voice.start"), slot=self.toggle_mic)
        row.addWidget(self.mic)
        row.addStretch(1)
        self.status = label("", "Muted")
        row.addWidget(self.status)
        box.lay.addLayout(row)

        self.mic_banner = QFrame()
        self.mic_banner.setObjectName("RecBanner")
        ml = QHBoxLayout(self.mic_banner)
        self.mic_label = label(tr("voice.recording"), "PillDanger", wrap=False)
        ml.addWidget(self.mic_label)
        ml.addStretch(1)
        self.mic_banner.hide()
        box.lay.addWidget(self.mic_banner)
        self._blink = QTimer(self)
        self._blink.timeout.connect(lambda: self.mic_label.setVisible(not self.mic_label.isVisible()))

        ok, _why = voice_available()
        if not ok:
            self.mic.setEnabled(False)
            self.mic.setToolTip(tr("voice.unavailable"))
            box.lay.addWidget(label(tr("voice.unavailable"), "Muted"))
        self.body.addWidget(box)

        ex = Card(spacing=4)
        ex.lay.addWidget(label(tr("nl.examples"), "Muted"))
        for e in EXAMPLES[language()]:
            ex.lay.addWidget(button("“" + e + "”", "Ghost", lambda _=False, t=e: self.input.setPlainText(t)))
        self.body.addWidget(ex)

        self.result = QVBoxLayout()
        self.body.addLayout(self.result)
        self.finish()

        self._sig = _Sig()
        self._sig.done.connect(self._show)
        self._sig.error.connect(self._error)
        self._vsig = _Sig()
        self._vsig.done.connect(self._transcribed)
        self._vsig.error.connect(lambda e: self._error(tr("voice.error", e=e)))
        self.voice: VoiceRecorder | None = None

    # ---- text → rule ------------------------------------------------------
    def suggest(self) -> None:
        text = self.input.toPlainText().strip()
        if not text:
            return
        self.go.setEnabled(False)
        self.status.setText(tr("nl.thinking"))
        folders = self.ctx.known_folders()
        provider = self.ctx.ollama()
        QThreadPool.globalInstance().start(
            _Job(lambda: propose_rule(text, folders, provider), self._sig.done, self._sig.error))

    def _error(self, msg: str) -> None:
        self.go.setEnabled(True)
        self.mic.setEnabled(voice_available()[0])
        self.status.setText("")
        clear_layout(self.result)
        self.result.addWidget(label(msg, "PillWarn"))

    def _show(self, res) -> None:
        self.go.setEnabled(True)
        self.status.setText("")
        clear_layout(self.result)
        if res.rule is None:
            key = f"nl.err.{res.error}"
            msg = tr(key) if res.error in ("no_condition", "no_target") else tr("nl.err.generic", e=res.error)
            self.result.addWidget(label(msg, "PillWarn"))
            return
        card = Card()
        head = QHBoxLayout()
        head.addWidget(label(res.rule.name, "H2", wrap=False))
        who = tr("nl.provider_ollama", model=self.ctx.setting("ai_model", "")) if res.provider == "ollama" \
            else tr("nl.provider_keywords")
        head.addWidget(pill(who))
        head.addStretch(1)
        card.lay.addLayout(head)
        card.lay.addWidget(label(rule_summary(res.rule)))
        card.lay.addWidget(label(f"{res.rule.watch_dir}  →  {res.rule.action.target_dir or '-'}", "Muted"))
        for w in res.warnings:
            k = w.split(":")[0]
            card.lay.addWidget(label("• " + tr(f"nl.warn.{k}"), "Muted"))
        row = QHBoxLayout()
        row.addWidget(button(tr("teach.review"), "Primary", lambda: self._review(res.rule)))
        row.addStretch(1)
        card.lay.addLayout(row)
        self.result.addWidget(card)

    def _review(self, rule) -> None:
        ed = RuleEditor(self.ctx, rule, self)
        if ed.exec():
            PreviewDialog(self.ctx, self.ctx.service.preview_rule(ed.rule), self).exec()

    # ---- voice ------------------------------------------------------------
    def toggle_mic(self) -> None:
        if self.voice and self.voice.recording:
            audio = self.voice.stop()
            self._mic_ui(False)
            self.mic.setEnabled(False)
            self.status.setText(tr("voice.transcribing"))
            lang = self.ctx.setting("voice_lang", language())
            QThreadPool.globalInstance().start(
                _Job(lambda: self.voice.transcribe(audio, lang), self._vsig.done, self._vsig.error))
            return
        try:
            if self.voice is None:
                self.voice = VoiceRecorder(self.ctx.setting("whisper_model", "small"))
            self.voice.start()
        except Exception as exc:
            self._error(tr("voice.error", e=exc))
            return
        self._mic_ui(True)

    def _mic_ui(self, on: bool) -> None:
        self.mic.setText(tr("voice.stop") if on else tr("voice.start"))
        self.mic_banner.setVisible(on)
        (self._blink.start(600) if on else self._blink.stop())
        self.mic_label.show()

    def _transcribed(self, text: str) -> None:
        self.mic.setEnabled(True)
        self.status.setText("")
        if text:
            self.input.setPlainText(text)
            self.suggest()
