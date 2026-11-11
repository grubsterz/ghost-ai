"""'Do anything' page - full-access mode. Every command is shown, editable, and runs only on click."""

from __future__ import annotations

import os
import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QGridLayout, QHBoxLayout, QInputDialog, QLineEdit, QListWidget, QMessageBox, QPlainTextEdit, QVBoxLayout,
)

from ...agent.commands import CommandRunner, CommandStep, assess, github_login, open_terminal_with, tool_status
from ...agent.planner import AgentPlan, OllamaAgent, builtin_plan
from ...i18n import language, tr
from ..widgets import Card, Page, button, clear_layout, label, pill

EXAMPLES = {
    "hr": ["instaliraj 7zip", "instaliraj VLC", "ažuriraj sve programe", "moji repoi", "kloniraj grubsterz/ghost-ai",
           "koliko ima mjesta na disku", "$ Get-Date"],
    "en": ["install 7zip", "install VLC", "update all apps", "my repos", "clone grubsterz/ghost-ai",
           "how much free disk space", "$ Get-Date"],
}


class _Sig(QObject):
    line = Signal(str)
    step_done = Signal(object)
    plan = Signal(object)
    login = Signal(str, dict)


class AgentPage(Page):
    def __init__(self, ctx) -> None:
        super().__init__(tr("agent.title"), tr("agent.sub"))
        self.ctx = ctx
        self.steps: list[CommandStep] = []
        self.request = ""
        self.runner = CommandRunner()
        self.running = False
        self.run_all = False
        self.agent: OllamaAgent | None = None
        self.sig = _Sig()
        self.sig.line.connect(self._append)
        self.sig.step_done.connect(self._step_done)
        self.sig.plan.connect(self._show_plan)
        self.sig.login.connect(self._show_login)

        # locked state
        self.locked = Card()
        self.locked.lay.addWidget(label(tr("agent.locked"), "H2"))
        self.locked.lay.addWidget(label(tr("agent.locked_text")))
        lrow = QHBoxLayout()
        lrow.addWidget(button(tr("agent.enable"), "Primary", self.enable))
        lrow.addStretch(1)
        self.locked.lay.addLayout(lrow)
        self.body.addWidget(self.locked)

        # status
        self.status_card = Card()
        srow = QHBoxLayout()
        self.tools_box = QHBoxLayout()
        srow.addLayout(self.tools_box)
        srow.addStretch(1)
        self.gh_label = label("", "Muted", wrap=False)
        srow.addWidget(self.gh_label)
        self.gh_btn = button(tr("agent.gh_login"), slot=lambda: open_terminal_with("gh auth login --web"))
        srow.addWidget(self.gh_btn)
        srow.addWidget(button("↻", slot=self._probe, tip=tr("agent.refresh")))
        self.status_card.lay.addLayout(srow)
        self.body.addWidget(self.status_card)

        # request
        self.req_card = Card()
        self.input = QLineEdit()
        self.input.setPlaceholderText(tr("agent.placeholder"))
        self.input.returnPressed.connect(self.propose)
        self.req_card.lay.addWidget(self.input)
        rrow = QHBoxLayout()
        self.go = button(tr("agent.propose"), "Primary", self.propose)
        rrow.addWidget(self.go)
        rrow.addWidget(button(tr("agent.new"), slot=self.reset))
        rrow.addStretch(1)
        self.mode = label("", "Muted", wrap=False)
        rrow.addWidget(self.mode)
        self.req_card.lay.addLayout(rrow)
        ex = QGridLayout()
        ex.setSpacing(2)
        for i, e in enumerate(EXAMPLES[language()]):
            ex.addWidget(button(e, "Ghost", lambda _=False, t=e: (self.input.setText(t), self.propose())), i // 4, i % 4)
        self.req_card.lay.addLayout(ex)
        self.body.addWidget(self.req_card)

        self.reply = label("", "")
        self.body.addWidget(self.reply)
        self.steps_box = QVBoxLayout()
        self.steps_box.setSpacing(8)
        self.body.addLayout(self.steps_box)

        self.ctrl = QHBoxLayout()
        self.run_all_btn = button(tr("agent.run_all"), "Primary", self.start_run_all)
        self.stop_btn = button(tr("agent.stop"), "Danger", self.stop)
        self.cont_btn = button(tr("agent.continue"), slot=self.continue_ai)
        for b in (self.run_all_btn, self.stop_btn, self.cont_btn):
            self.ctrl.addWidget(b)
        self.ctrl.addStretch(1)
        self.body.addLayout(self.ctrl)

        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.console.setMinimumHeight(200)
        self.console.setPlaceholderText(tr("agent.console"))
        self.body.addWidget(self.console)

        self.hist_title = label(tr("agent.history"), "H2")
        self.body.addWidget(self.hist_title)
        self.history = QListWidget()
        self.history.setMaximumHeight(160)
        self.body.addWidget(self.history)
        self.finish()
        self._probe()
        self.refresh()

    # ---- enable -----------------------------------------------------------
    def enable(self) -> None:
        ans = QMessageBox.warning(self, tr("agent.enable"), tr("agent.enable_q"), QMessageBox.Yes | QMessageBox.No,
                                  QMessageBox.No)
        if ans == QMessageBox.Yes:
            self.ctx.set_setting("full_access", True)
            self.refresh()

    # ---- status -----------------------------------------------------------
    def _probe(self) -> None:
        threading.Thread(target=lambda: self.sig.login.emit(github_login(), tool_status()), daemon=True).start()

    def _show_login(self, user: str, tools: dict) -> None:
        clear_layout(self.tools_box)
        for name, ok in tools.items():
            self.tools_box.addWidget(pill(("✓ " if ok else "✕ ") + name, "Ok" if ok else "Muted"))
        if not tools.get("gh"):
            self.gh_label.setText(tr("agent.gh_missing"))
            self.gh_btn.hide()
        elif user:
            self.gh_label.setText(tr("agent.gh_as", user=user))
            self.gh_btn.hide()
        else:
            self.gh_label.setText(tr("agent.gh_no"))
            self.gh_btn.show()

    # ---- planning ---------------------------------------------------------
    def reset(self) -> None:
        self.steps = []
        self.agent = None
        self.reply.setText("")
        self.console.clear()
        self._render()

    def propose(self) -> None:
        text = self.input.text().strip()
        if not text or self.running:
            return
        self.request = text
        plan = builtin_plan(text)
        if plan is not None and plan.reply == "github_login":
            open_terminal_with("gh auth login --web")
            self.reply.setText(tr("agent.gh_opened"))
            return
        if plan is not None:
            self.agent = None
            self._show_plan(plan)
            return
        provider = self.ctx.ollama()
        if provider is None:
            self.reply.setText(tr("agent.need_ai"))
            return
        if self.agent is None:
            self.agent = OllamaAgent(self.ctx.config.ollama_url, self.ctx.setting("ai_model", "llama3.2:3b"))
        self.go.setEnabled(False)
        self.reply.setText(tr("nl.thinking"))
        agent = self.agent
        threading.Thread(target=lambda: self.sig.plan.emit(agent.ask(text, tool_status())), daemon=True).start()

    def continue_ai(self) -> None:
        if not self.agent or self.running:
            return
        ran = [s for s in self.steps if s.status != "pending"]
        self.cont_btn.setEnabled(False)
        self.reply.setText(tr("nl.thinking"))
        agent = self.agent
        threading.Thread(target=lambda: self.sig.plan.emit(agent.report(ran, tool_status())), daemon=True).start()

    def _show_plan(self, plan: AgentPlan) -> None:
        self.go.setEnabled(True)
        if plan.error:
            self.reply.setText(tr("nl.err.generic", e=plan.error))
            self._render()
            return
        msg = plan.reply or ""
        if not plan.steps and not msg:
            msg = tr("agent.nothing")
        if plan.steps:
            msg = (msg + "\n" if msg else "") + tr("agent.review")
        self.reply.setText(msg)
        self.steps = plan.steps
        self._render()

    # ---- rendering --------------------------------------------------------
    def _render(self) -> None:
        clear_layout(self.steps_box)
        self.cmd_edits: list[QLineEdit] = []
        for i, s in enumerate(self.steps):
            card = Card(spacing=6)
            head = QHBoxLayout()
            head.addWidget(label(f"{tr('agent.step')} {i + 1}", "H2", wrap=False))
            kind = {"done": "Ok", "failed": "Danger", "stopped": "Warn", "running": "Warn"}.get(s.status, "Muted")
            head.addWidget(pill(tr(f"agent.st.{s.status}"), kind))
            for r in assess(s.command):
                head.addWidget(pill(tr(f"risk.{r.key}"), "Danger" if r.level == "high" else "Warn"))
            head.addStretch(1)
            card.lay.addLayout(head)
            if s.explanation:
                card.lay.addWidget(label(s.explanation, "Muted"))
            edit = QLineEdit(s.command)
            edit.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
            edit.setReadOnly(s.status != "pending")
            edit.setAccessibleName(tr("agent.command"))
            edit.textChanged.connect(lambda t, st=s: setattr(st, "command", t))
            card.lay.addWidget(edit)
            self.cmd_edits.append(edit)
            if s.status == "pending":
                row = QHBoxLayout()
                row.addWidget(button(tr("agent.run"), "Primary", lambda _=False, idx=i: self.run_step(idx)))
                row.addWidget(button(tr("agent.skip"), slot=lambda _=False, st=s: self._skip(st)))
                row.addStretch(1)
                card.lay.addLayout(row)
            self.steps_box.addWidget(card)
        self._sync()

    def _sync(self) -> None:
        pending = any(s.status == "pending" for s in self.steps)
        self.run_all_btn.setVisible(pending and not self.running and len(self.steps) > 1)
        self.stop_btn.setVisible(self.running)
        ran = any(s.status not in ("pending",) for s in self.steps)
        self.cont_btn.setVisible(self.agent is not None and ran and not pending and not self.running)
        self.cont_btn.setEnabled(True)
        self.go.setEnabled(not self.running)

    def _skip(self, step: CommandStep) -> None:
        step.status = "skipped"
        self.ctx.store.add_command(step.command, "skipped", None, "", self.request)
        self._render()

    # ---- running ----------------------------------------------------------
    def _confirm(self, step: CommandStep) -> bool:
        risks = assess(step.command)
        if any(r.level == "high" for r in risks):
            word = tr("safety.q_word")
            text, ok = QInputDialog.getText(
                self, tr("agent.danger_title"),
                tr("agent.danger_q", risks=", ".join(tr(f"risk.{r.key}") for r in risks), cmd=step.command, word=word))
            return ok and text.strip() == word
        return True

    def run_step(self, idx: int) -> None:
        if self.running or idx >= len(self.steps):
            return
        if self.ctx.service.paused:
            QMessageBox.information(self, "GHOST AI", tr("status.paused"))
            self.run_all = False
            return
        step = self.steps[idx]
        if step.status != "pending":
            return
        if not self._confirm(step):
            self.run_all = False
            return
        self.running = True
        step.status = "running"
        self._render()
        self.console.appendPlainText(f"\n$ {step.command}")
        cwd = os.path.expanduser("~")

        def work() -> None:
            self.runner.run(step, cwd, self.sig.line.emit)
            self.sig.step_done.emit(step)

        threading.Thread(target=work, daemon=True).start()

    def start_run_all(self) -> None:
        self.run_all = True
        self._next()

    def _next(self) -> None:
        nxt = next((i for i, s in enumerate(self.steps) if s.status == "pending"), None)
        if nxt is None:
            self.run_all = False
            return
        self.run_step(nxt)

    def _append(self, line: str) -> None:
        self.console.insertPlainText(line) if line.endswith("\n") else self.console.appendPlainText(line)
        self.console.ensureCursorVisible()

    def _step_done(self, step: CommandStep) -> None:
        self.running = False
        self.console.appendPlainText(tr("agent.exit", code=step.exit_code, status=tr(f"agent.st.{step.status}")))
        self.ctx.store.add_command(step.command, step.status, step.exit_code, step.output, self.request)
        self._render()
        self.refresh_history()
        if self.run_all and step.status == "done":
            self._next()
        else:
            self.run_all = False
            self._sync()

    def stop(self) -> None:
        self.run_all = False
        self.runner.stop()

    # ---- refresh ----------------------------------------------------------
    def refresh_history(self) -> None:
        self.history.clear()
        for c in self.ctx.store.commands(50):
            mark = {"done": "✓", "failed": "✕", "skipped": "–", "stopped": "■"}.get(c["status"], "·")
            self.history.addItem(f"{mark}  {c['ts'].replace('T', ' ')[5:16]}  {c['command']}")

    def refresh(self) -> None:
        on = bool(self.ctx.setting("full_access", False))
        self.locked.setVisible(not on)
        for w in (self.status_card, self.req_card, self.console, self.history, self.hist_title, self.reply):
            w.setVisible(on)
        self.mode.setText(tr("agent.mode_ai", model=self.ctx.setting("ai_model", "")) if self.ctx.ollama()
                          else tr("agent.mode_builtin"))
        self.refresh_history()
        self._sync()
        if not on:
            for b in (self.run_all_btn, self.stop_btn, self.cont_btn):
                b.hide()
