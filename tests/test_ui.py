"""UI smoke tests (offscreen). They build every page in both languages and themes and drive
the main flows through the same service the UI uses."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from conftest import make_rule  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def ctx(tmp_path, service, monkeypatch):
    from ghost_ai.config import AppConfig
    from ghost_ai.ui.context import AppContext

    c = AppContext(service=service, store=service.store, config=AppConfig(), data_dir=tmp_path,
                   log_file=tmp_path / "x.log")
    c.set_setting("onboarded", True)
    return c


@pytest.mark.parametrize("lang,theme", [("en", "dark"), ("hr", "light")])
def test_main_window_builds_all_pages(qapp, ctx, sandbox, lang, theme):
    from ghost_ai.ui.main_window import NAV, MainWindow

    dl, docs = sandbox
    ctx.set_setting("language", lang)
    ctx.set_setting("theme", theme)
    ctx.service.save_rule(make_rule(dl, docs))
    win = MainWindow(ctx)
    win.show()
    for key, _icon, _cls in NAV:
        win.go(key, animate=False)
        qapp.processEvents()
        assert win.stack.currentWidget() is win.pages[key]
    win.resize(800, 600)  # compact sidebar
    qapp.processEvents()
    assert win.side.width() == 72
    win.close()


def test_language_switch_rebuilds(qapp, ctx):
    from ghost_ai.ui.main_window import MainWindow

    win = MainWindow(ctx)
    ctx.set_setting("language", "hr")
    ctx.bus.relanguage.emit()
    qapp.processEvents()
    assert "Pregled" in win.nav_buttons["dashboard"].text()
    win.close()


def test_dashboard_stats_are_real(qapp, ctx, sandbox):
    from ghost_ai.ui.pages.dashboard import DashboardPage

    dl, docs = sandbox
    (dl / "a.pdf").write_text("x")
    rule = make_rule(dl, docs)
    ctx.service.save_rule(rule)
    page = DashboardPage(ctx)
    assert page.s_24.value.text() == "0"
    ctx.service.execute(ctx.service.preview_rule(rule))
    page.refresh()
    assert page.s_24.value.text() == "1"
    assert page.s_rules.value.text() == "1"


def test_import_rules_validates_and_disables(qapp, ctx, tmp_path, sandbox):
    import json

    from ghost_ai.ui.pages.settings import import_rules_file

    dl, docs = sandbox
    good = make_rule(dl, docs).to_dict()
    bad = dict(good, action={"type": "shell", "cmd": "x"})
    p = tmp_path / "rules.json"
    p.write_text(json.dumps({"rules": [good, bad]}))
    ok, rejected = import_rules_file(ctx, str(p))
    assert (ok, rejected) == (1, 1)
    assert ctx.service.rules()[0].enabled is False


def test_rule_editor_saves_valid_rule(qapp, ctx, sandbox):
    from ghost_ai.ui.widgets import RuleEditor

    dl, docs = sandbox
    ed = RuleEditor(ctx)
    ed.name.setText("Invoices")
    ed.watch.edit.setText(str(dl))
    ed.exts.setText("pdf, .PNG")
    ed.target.edit.setText(str(docs))
    ed._save()
    rules = ctx.service.rules()
    assert len(rules) == 1 and rules[0].conditions.extensions == ["pdf", "png"]


def test_rule_editor_rejects_empty_conditions(qapp, ctx, sandbox):
    from ghost_ai.ui.widgets import RuleEditor

    dl, docs = sandbox
    ed = RuleEditor(ctx)
    ed.watch.edit.setText(str(dl))
    ed.target.edit.setText(str(docs))
    ed._save()
    assert ctx.service.rules() == []
    assert ed.error.text()


def test_agent_page_locked_then_runs_approved_command(qapp, ctx):
    import sys
    import time

    from ghost_ai.ui.pages.agent import AgentPage

    page = AgentPage(ctx)
    page.show()
    qapp.processEvents()
    assert page.locked.isVisible() and not page.req_card.isVisible()
    ctx.set_setting("full_access", True)
    page.refresh()
    assert not page.locked.isVisible() and page.req_card.isVisible()

    page.input.setText("$ " + ("Write-Output ghost-ui-ok" if sys.platform == "win32" else "echo ghost-ui-ok"))
    page.propose()
    assert len(page.steps) == 1 and page.steps[0].status == "pending", "nothing runs before the click"
    page.run_step(0)
    deadline = time.time() + 30
    while (page.running or page.steps[0].status in ("pending", "running")) and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.05)
    assert page.steps[0].status == "done"
    assert "ghost-ui-ok" in page.console.toPlainText()
    assert ctx.store.commands()[0]["status"] == "done"
    page.close()


def test_agent_page_blocked_when_paused(qapp, ctx):
    from ghost_ai.ui.pages.agent import AgentPage

    ctx.set_setting("full_access", True)
    ctx.service.set_paused(True)
    page = AgentPage(ctx)
    page.input.setText("$ Get-Date")
    page.propose()
    from unittest.mock import patch
    with patch("ghost_ai.ui.pages.agent.QMessageBox.information"):
        page.run_step(0)
    assert page.steps[0].status == "pending"
    ctx.service.set_paused(False)


def _wait(qapp, cond, timeout=40):
    import time
    end = time.time() + timeout
    while not cond() and time.time() < end:
        qapp.processEvents()
        time.sleep(0.05)
    qapp.processEvents()
    return cond()


def test_auto_mode_runs_safe_steps_and_waits_on_risky(qapp, ctx):
    import json
    import sys

    from ghost_ai.agent.planner import OllamaAgent
    from ghost_ai.ui.pages.agent import AgentPage

    echo = "Write-Output" if sys.platform == "win32" else "echo"
    replies = [
        {"reply": "step 1", "steps": [{"explanation": "safe", "command": f"{echo} auto-one"}]},
        {"reply": "step 2", "steps": [{"explanation": "safe", "command": f"{echo} auto-two"},
                                      {"explanation": "risky", "command": "winget install foo"}]},
        {"reply": "finished", "steps": []},
    ]

    def transport(url, payload, timeout):
        return {"message": {"content": json.dumps(replies.pop(0))}}

    ctx.set_setting("full_access", True)
    page = AgentPage(ctx)
    page.auto_cb.setChecked(True)
    page.agent = OllamaAgent(transport=transport)
    page.input.setText("do something free-form")
    page.sig.plan.emit(page.agent.ask("x", {}))  # what propose() does in a thread
    assert _wait(qapp, lambda: len(page.steps) == 2 and page.steps[0].status == "done" and not page.running)
    assert "auto-one" in page.console.toPlainText() and "auto-two" in page.console.toPlainText()
    assert page.steps[1].status == "pending", "risky step must wait for a click"
    page._skip(page.steps[1])
    page._advance()
    assert _wait(qapp, lambda: page.reply.text() == "finished")


def test_setup_ai_applies_settings_only_after_success(qapp, ctx):
    import sys

    from ghost_ai.agent.commands import CommandStep
    from ghost_ai.agent.planner import AgentPlan
    from ghost_ai.ui.pages.agent import AgentPage

    echo = "Write-Output" if sys.platform == "win32" else "echo"
    ctx.set_setting("full_access", True)
    page = AgentPage(ctx)
    page._show_plan(AgentPlan("", [CommandStep(f"{echo} ok")], "builtin",
                              on_success={"ai_enabled": True, "ai_model": "test-model"}))
    assert ctx.setting("ai_enabled", False) is False
    page.run_step(0)
    assert _wait(qapp, lambda: ctx.setting("ai_model") == "test-model")
    assert ctx.setting("ai_enabled") is True
