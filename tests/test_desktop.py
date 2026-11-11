import subprocess
import sys

import pytest

from ghost_ai.agent.commands import CommandRunner, CommandStep, assess
from ghost_ai.agent.planner import builtin_plan

CASES = [
    ("otvori youtube.com u chromeu", "Start-Process chrome 'https://youtube.com'"),
    ("open https://github.com/grubsterz/ghost-ai", "Start-Process 'https://github.com/grubsterz/ghost-ai'"),
    ("idi na trophonia.com", "https://trophonia.com"),
    ("pusti lofi hip hop na youtubeu", "youtube.com/results?search_query=lofi+hip+hop"),
    ("youtube minecraft", "search_query=minecraft"),
    ("pretraži vrijeme zagreb", "google.com/search?q=vrijeme+zagreb"),
    ("otvori terminal", "Start-Process wt"),
    ("otvori mapu preuzimanja", "Start-Process explorer"),
    ("otvori kalkulator", "'Calculator'"),
    ("pokreni spotify", "'Spotify'"),
    ("zatvori chrome", "'chrome'"),
    ("ugasi spotify", "CloseMainWindow"),
    ("pokreni igru counter-strike", "steam://rungameid"),
    ("upali igricu Age of Empires", "'age of empires'"),
    ("zaključaj računalo", "LockWorkStation"),
    ("ugasi računalo", "shutdown /s /t 60"),
    ("restartaj računalo", "shutdown /r /t 60"),
    ("otkaži gašenje", "shutdown /a"),
]


@pytest.mark.parametrize("text,expect", CASES)
def test_desktop_recipes_windows(text, expect):
    plan = builtin_plan(text, is_windows=True)
    assert plan is not None, text
    assert expect in plan.steps[0].command, plan.steps[0].command


@pytest.mark.parametrize("text,expect", [
    ("otvori youtube.com u chromeu", "open -a 'Google Chrome' 'https://youtube.com'"),
    ("zatvori chrome", 'quit app "Google Chrome"'),
    ("otvori terminal", "open -a Terminal"),
    ("pokreni igru portal", "steam://rungameid"),
])
def test_desktop_recipes_macos(text, expect):
    assert expect in builtin_plan(text, is_windows=False).steps[0].command


def test_install_still_wins_over_open():
    assert "winget" in builtin_plan("instaliraj spotify", is_windows=True).steps[-1].command


def test_injection_in_names_is_refused_or_quoted():
    assert builtin_plan("zatvori chrome'; Remove-Item C:\\ -Recurse; '", is_windows=True) is None
    p = builtin_plan("pretraži '; Remove-Item x", is_windows=True)
    assert "Remove-Item" not in p.steps[0].command.split("'")[0]  # only inside the URL-encoded query


def test_close_and_power_are_flagged():
    assert "closes_apps" in {r.key for r in assess(builtin_plan("zatvori chrome", is_windows=True).steps[0].command)}
    assert "power" in {r.key for r in assess(builtin_plan("ugasi računalo", is_windows=True).steps[0].command)}


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell syntax check")
def test_all_windows_commands_are_valid_powershell():
    cmds = [builtin_plan(t, is_windows=True).steps[0].command for t, _ in CASES]
    script = "\n".join(
        "$e=$null; [void][System.Management.Automation.Language.Parser]::ParseInput(@'\n" + c +
        "\n'@, [ref]$null, [ref]$e); if ($e) { 'ERR: ' + $e[0].Message }" for c in cmds)
    out = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True,
                         timeout=60).stdout
    assert "ERR" not in out, out


@pytest.mark.skipif(sys.platform != "win32", reason="runs real PowerShell")
def test_close_and_game_with_unknown_names_do_nothing(tmp_path):
    r = CommandRunner(timeout=60)
    s = r.run(builtin_plan("zatvori nepostojeciprogramxyz", is_windows=True).steps[0], str(tmp_path))
    assert s.status == "done" and "Not running" in s.output
    s = r.run(builtin_plan("pokreni igru nepostojecaigraxyz", is_windows=True).steps[0], str(tmp_path))
    assert s.status == "done" and ("No installed Steam game" in s.output or "not installed" in s.output)
