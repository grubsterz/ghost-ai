"""Turns a request into proposed command steps. Proposals only - nothing is executed here.

* builtin_plan(): deterministic HR/EN patterns (install, uninstall, update, clone, repos, disk...) - no model needed
* OllamaAgent: free-form requests via a local model, multi-turn (sees the output of steps you ran)
"""

from __future__ import annotations

import json
import os
import platform
import re
import sys
from dataclasses import dataclass, field
from typing import Any

from ..ai.natural import Transport, _fold, extract_json, http_json, is_local_url, standard_folders
from ..domain.validation import ValidationError
from ..i18n import tr
from .commands import MAX_COMMAND, CommandStep, shell_name
from .desktop import desktop_plan

MAX_STEPS = 8
_SAFE_NAME = re.compile(r"^[\w .+\-/]{1,80}$")


@dataclass
class AgentPlan:
    reply: str
    steps: list[CommandStep]
    provider: str
    error: str = ""


def _q(s: str) -> str:
    """Quote for the platform shell (names are already restricted to safe characters)."""
    return f"'{s}'" if sys.platform != "win32" else f'"{s}"'


def _clean_name(raw: str) -> str | None:
    name = raw.strip().strip("\"'„“”.!?").strip()
    name = re.sub(r"^(program|aplikaciju|aplikacija|app|the|a|an)\s+", "", name, flags=re.I)
    return name if _SAFE_NAME.match(name) else None


def builtin_plan(text: str, is_windows: bool | None = None) -> AgentPlan | None:
    win = sys.platform == "win32" if is_windows is None else is_windows
    raw = text.strip()
    if raw.startswith(("$", ">")):
        cmd = raw[1:].strip()
        return AgentPlan("", [CommandStep(cmd, tr("agentx.own"))], "builtin") if cmd else None
    t = _fold(raw)
    docs = standard_folders().get("documents", os.path.expanduser("~"))
    if re.search(r"\b(github login|prijavi (me )?(se )?na github|log ?in to github)\b", t):
        return AgentPlan("github_login", [], "builtin")

    m = re.match(r"^(?:molim te\s+|please\s+)?(?:deinstaliraj|uninstall|makni program|ukloni program|remove app)\s+(.+)$",
                 t)
    if m and (name := _clean_name(m.group(1))):
        cmd = (f"winget uninstall {_q(name)}" if win else f"brew uninstall {name.lower().replace(' ', '-')}")
        return AgentPlan("", [CommandStep(cmd, tr("agentx.uninstall", name=name))], "builtin")

    m = re.match(r"^(?:molim te\s+|please\s+)?(?:instaliraj|install|skini i instaliraj|download and install|"
                 r"instaliraj mi|nabavi)\s+(.+)$", t)
    if m and (name := _clean_name(m.group(1))):
        if win:
            steps = [CommandStep(f"winget search {_q(name)} --accept-source-agreements",
                                 tr("agentx.find_win", name=name)),
                     CommandStep(f"winget install {_q(name)} --accept-package-agreements --accept-source-agreements",
                                 tr("agentx.install_win", name=name))]
        else:
            slug = name.lower().replace(" ", "-")
            steps = [CommandStep(f"brew search {slug}", tr("agentx.find_mac", name=name)),
                     CommandStep(f"brew install --cask {slug} || brew install {slug}", tr("agentx.install", name=name))]
        return AgentPlan("", steps, "builtin")

    if re.search(r"\b(azuriraj|update|upgrade|nadogradi)\s+(sve|all)\b", t):
        cmd = ("winget upgrade --all --accept-package-agreements --accept-source-agreements" if win
               else "brew update && brew upgrade")
        return AgentPlan("", [CommandStep("winget upgrade" if win else "brew outdated", tr("agentx.list_updates")),
                              CommandStep(cmd, tr("agentx.update_all"))], "builtin")

    desk = desktop_plan(raw, t, win)
    if desk:
        return AgentPlan("", desk, "builtin")

    m = re.match(r"^(?:kloniraj|clone)\s+(?:repo\s+|repozitorij\s+|repository\s+)?([\w.\-]+(?:/[\w.\-]+)?)", t)
    if m:
        repo = m.group(1)
        target = os.path.join(docs, repo.split("/")[-1])
        return AgentPlan("", [CommandStep(f"gh repo clone {repo} {_q(target)}",
                                          tr("agentx.clone", repo=repo))], "builtin")

    if re.search(r"\b(moji repo\w*|my repos?|my repositories|list (my )?repos?|popis repo\w*)\b", t):
        return AgentPlan("", [CommandStep("gh repo list --limit 50", tr("agentx.repos"))], "builtin")

    m = re.match(r"^(?:napravi|kreiraj|create)\s+(?:novi\s+|new\s+)?(?:privatni\s+|private\s+|javni\s+|public\s+)?(?:github\s+)?"
                 r"(?:repo|repozitorij|repository)\s+([\w.\-]+)", t)
    if m:
        public = re.search(r"\b(javni|public)\b", t) is not None
        return AgentPlan("", [CommandStep(f"gh repo create {m.group(1)} {'--public' if public else '--private'}",
                                          tr("agentx.create_repo", name=m.group(1)))], "builtin")

    if re.search(r"\b(koliko (ima )?(mjesta|prostora)|disk space|free space|slobodno mjesto)\b", t):
        cmd = ("Get-PSDrive -PSProvider FileSystem | Select-Object Name, @{n='Free GB';e={[math]::Round($_.Free/1GB,1)}}, "
               "@{n='Used GB';e={[math]::Round($_.Used/1GB,1)}}" if win else "df -h")
        return AgentPlan("", [CommandStep(cmd, tr("agentx.disk"))], "builtin")

    if re.search(r"\b(github login|prijavi (me )?(se )?na github|log ?in to github)\b", t):
        return AgentPlan("github_login", [], "builtin")
    return None


AGENT_SYSTEM = """You are GHOST AI's command assistant on the user's own computer.
OS: {os}. Shell: {shell}. Available tools: {tools}. Home: {home}. Documents: {docs}.
The user approves every command before it runs and sees its output.
Reply with ONE JSON object: {{"reply": "<short answer in the user's language>", "steps": [{{"explanation": "...", "command": "..."}}]}}
Rules:
- Each command must be a single {shell} command line. Prefer winget (Windows) / brew (macOS) for installing software
  and the GitHub CLI `gh` (already logged in if available) for GitHub.
- Use as few steps as possible (max {max_steps}). Use non-interactive flags (e.g. --accept-package-agreements).
- Never read or print passwords, tokens, keys, cookies or browser data. Never disable security features.
- You can open links (Start-Process '<url>' / Start-Process chrome '<url>' on Windows, open / open -a "Google Chrome"
  on macOS), start apps, open a terminal, start installed Steam games (steam://rungameid/<appid>), close apps
  gracefully (CloseMainWindow / osascript quit) and manage files. Commands run without a console window, so start
  GUI programs with Start-Process (Windows) or open (macOS) so they appear on the user's screen.
- If the request needs nothing to run, return an empty "steps" list and answer in "reply".
- When you receive command output, decide the next steps or finish with an empty "steps" list."""

AGENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "steps": {"type": "array", "items": {"type": "object", "properties": {
            "explanation": {"type": "string"}, "command": {"type": "string"}}, "required": ["explanation", "command"]}},
    },
    "required": ["reply", "steps"],
}


def parse_agent_json(raw: str) -> tuple[str, list[CommandStep]]:
    obj = extract_json(raw)
    reply = obj.get("reply", "")
    steps = obj.get("steps", [])
    if not isinstance(reply, str) or not isinstance(steps, list):
        raise ValidationError("bad agent JSON")
    out: list[CommandStep] = []
    for s in steps[:MAX_STEPS]:
        if not isinstance(s, dict):
            raise ValidationError("bad step")
        cmd, expl = s.get("command", ""), s.get("explanation", "")
        if not isinstance(cmd, str) or not isinstance(expl, str):
            raise ValidationError("bad step types")
        cmd = cmd.strip()
        if not cmd:
            continue
        if len(cmd) > MAX_COMMAND or "\x00" in cmd:
            raise ValidationError("command too long")
        out.append(CommandStep(cmd, expl.strip()[:300]))
    return reply.strip()[:2000], out


@dataclass
class OllamaAgent:
    base_url: str = "http://127.0.0.1:11434"
    model: str = "llama3.2:3b"
    transport: Transport = http_json
    timeout: float = 120.0
    messages: list[dict[str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not is_local_url(self.base_url):
            raise ValueError("Ollama URL must be local (privacy)")

    def _system(self, tools: dict[str, bool]) -> str:
        return AGENT_SYSTEM.format(
            os=f"{platform.system()} {platform.release()} ({platform.machine()})", shell=shell_name(),
            tools=", ".join(k for k, v in tools.items() if v) or "none", home=os.path.expanduser("~"),
            docs=standard_folders().get("documents", ""), max_steps=MAX_STEPS)

    def reset(self) -> None:
        self.messages = []

    def ask(self, text: str, tools: dict[str, bool]) -> AgentPlan:
        if not self.messages:
            self.messages.append({"role": "system", "content": self._system(tools)})
        self.messages.append({"role": "user", "content": text[:4000]})
        payload = {"model": self.model, "messages": list(self.messages), "format": AGENT_SCHEMA, "stream": False,
                   "options": {"temperature": 0}}
        try:
            resp = self.transport(f"{self.base_url}/api/chat", payload, self.timeout)
        except Exception as exc:  # network/timeout - reported to the user
            self.messages.pop()
            return AgentPlan("", [], "ollama", error=f"ollama_unreachable: {exc}")
        raw = str(resp.get("message", {}).get("content", ""))
        self.messages.append({"role": "assistant", "content": raw})
        try:
            reply, steps = parse_agent_json(raw)
        except ValidationError as exc:
            return AgentPlan("", [], "ollama", error=str(exc))
        return AgentPlan(reply, steps, "ollama")

    def report(self, steps: list[CommandStep], tools: dict[str, bool]) -> AgentPlan:
        lines = []
        for s in steps:
            out = s.output[-3000:] if s.output else ""
            lines.append(f"$ {s.command}\n[status: {s.status}, exit code: {s.exit_code}]\n{out}")
        return self.ask("Results of the approved steps:\n\n" + "\n\n".join(lines) +
                        "\n\nWhat next? Return an empty steps list if the task is finished.", tools)


def history_json(messages: list[dict[str, str]]) -> str:
    return json.dumps(messages, ensure_ascii=False)
