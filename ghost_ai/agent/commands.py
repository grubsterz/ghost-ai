"""Full-access mode: run system commands - only after the user approved each one.

Nothing here runs on its own. The UI shows every command (editable), its risk warnings,
and runs it only on an explicit click. Everything is logged in the `commands` table."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

MAX_COMMAND = 4000


@dataclass
class CommandStep:
    command: str
    explanation: str = ""
    status: str = "pending"  # pending | running | done | failed | skipped | stopped
    exit_code: int | None = None
    output: str = ""


@dataclass
class Risk:
    level: str  # "high" (typed confirmation) | "medium" (warning)
    key: str


# (regex, level, key) - checked case-insensitively. Not a sandbox: it only decides how loudly to warn.
_RISKS: list[tuple[str, str, str]] = [
    (r"\bformat(\.com)?\s+[a-z]:", "high", "format_disk"),
    (r"\b(diskpart|mkfs|dd\s+if=)", "high", "disk_tool"),
    (r"\brm\s+(-[a-z]*r[a-z]*f|-[a-z]*f[a-z]*r|-rf|-fr)\b", "high", "recursive_delete"),
    (r"remove-item\b.*-recurse", "high", "recursive_delete"),
    (r"\b(rd|rmdir)\s+/s\b", "high", "recursive_delete"),
    (r"\bdel\s+.*(/s|/q)", "high", "recursive_delete"),
    (r"\b(reg\s+delete|remove-itemproperty|bcdedit|vssadmin\s+delete|cipher\s+/w)", "high", "system_config"),
    (r"(iex|invoke-expression)\b|\|\s*(sh|bash|zsh|iex|pwsh|powershell)\b", "high", "remote_script"),
    (r"\b(shutdown|restart-computer|stop-computer|reboot|halt)\b", "medium", "power"),
    (r"\b(sudo|runas|start-process\b.*-verb\s+runas)\b", "medium", "elevation"),
    (r"\b(set-executionpolicy|netsh\s+advfirewall|set-mppreference|ufw\s+disable|spctl\s+--master-disable)",
     "high", "security_setting"),
    (r"\b(git\s+push\b.*(--force|-f\b)|gh\s+repo\s+delete)", "high", "github_destructive"),
    (r"\b(git\s+push|gh\s+(pr|release|repo)\s+(create|edit|merge))", "medium", "github_write"),
    (r"\b(winget|choco|brew|apt|apt-get|dnf|pip|npm)\s+(install|uninstall|remove|upgrade)\b", "medium", "installs"),
    (r"\b(curl|wget|invoke-webrequest|iwr|irm|invoke-restmethod)\b", "medium", "network"),
    (r"(\.ssh|id_rsa|\.aws|login data|cookies|\.kdbx|\.env\b|keychain)", "high", "secrets"),
]


def assess(command: str) -> list[Risk]:
    c = command.lower()
    seen: set[str] = set()
    out: list[Risk] = []
    for pattern, level, key in _RISKS:
        if key not in seen and re.search(pattern, c):
            seen.add(key)
            out.append(Risk(level, key))
    out.sort(key=lambda r: r.level != "high")
    return out


def needs_typed_confirmation(command: str) -> bool:
    return any(r.level == "high" for r in assess(command))


def shell_name() -> str:
    return "PowerShell" if sys.platform == "win32" else os.path.basename(os.environ.get("SHELL", "/bin/zsh"))


def shell_argv(command: str) -> list[str]:
    if sys.platform == "win32":
        exe = shutil.which("pwsh") or "powershell"
        return [exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command",
                "[Console]::OutputEncoding=[Text.Encoding]::UTF8; " + command]
    sh = os.environ.get("SHELL", "/bin/zsh")
    if not os.path.exists(sh):
        sh = "/bin/sh"
    return [sh, "-lc", command]


class CommandRunner:
    """Runs one approved command, streaming output. `stop()` kills it."""

    def __init__(self, timeout: float = 1800.0) -> None:
        self.timeout = timeout
        self._proc: subprocess.Popen | None = None
        self._stopped = False

    def run(self, step: CommandStep, cwd: str, on_output: Callable[[str], None] | None = None) -> CommandStep:
        if not step.command.strip() or len(step.command) > MAX_COMMAND or "\x00" in step.command:
            step.status, step.output = "failed", "invalid command"
            return step
        self._stopped = False
        step.status = "running"
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        env = dict(os.environ)
        env.setdefault("GH_PROMPT_DISABLED", "1")
        try:
            self._proc = subprocess.Popen(
                shell_argv(step.command), cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, creationflags=flags, env=env,
            )
        except OSError as exc:
            step.status, step.output = "failed", str(exc)
            return step
        chunks: list[str] = []
        start = time.monotonic()

        def kill_on_timeout() -> None:
            while self._proc and self._proc.poll() is None:
                if time.monotonic() - start > self.timeout:
                    self.stop()
                    return
                time.sleep(0.5)

        threading.Thread(target=kill_on_timeout, daemon=True).start()
        assert self._proc.stdout is not None
        for raw in iter(self._proc.stdout.readline, b""):
            line = raw.decode("utf-8", errors="replace")
            if len(chunks) < 5000:
                chunks.append(line)
            if on_output:
                on_output(line)
        code = self._proc.wait()
        step.exit_code = code
        step.output = "".join(chunks)[-20000:]
        step.status = "stopped" if self._stopped else ("done" if code == 0 else "failed")
        self._proc = None
        return step

    def stop(self) -> None:
        p = self._proc
        if p and p.poll() is None:
            self._stopped = True
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True,
                               creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                p.kill()


def tool_status() -> dict[str, bool]:
    names = ["git", "gh"] + (["winget"] if sys.platform == "win32" else ["brew"])
    return {n: shutil.which(n) is not None for n in names}


def github_login() -> str:
    """GitHub user name if `gh` is logged in, else ''."""
    if not shutil.which("gh"):
        return ""
    try:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        r = subprocess.run(["gh", "api", "user", "--jq", ".login"], capture_output=True, text=True, timeout=8,
                           creationflags=flags)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def open_terminal_with(command: str) -> None:
    """Open a visible terminal running an interactive command (e.g. `gh auth login`)."""
    if sys.platform == "win32":
        subprocess.Popen(["cmd", "/c", "start", "GHOST AI", "cmd", "/k", command])
    elif sys.platform == "darwin":
        script = f'tell application "Terminal" to do script "{command}"'
        subprocess.Popen(["osascript", "-e", script, "-e", 'tell application "Terminal" to activate'])
    else:
        subprocess.Popen(["x-terminal-emulator", "-e", command])
