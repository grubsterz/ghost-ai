"""Shared application context handed to every page."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from ..ai.embedded import MODEL_PREFIX, MODELS, EmbeddedEngine, engine_available, is_downloaded
from ..ai.natural import OllamaProvider, standard_folders
from ..config import AppConfig
from ..engine.service import AutomationService
from ..storage.db import Store


class Bus(QObject):
    """Qt signals so background threads can safely tell the UI something changed."""

    changed = Signal()
    navigate = Signal(str)
    restyle = Signal()
    relanguage = Signal()


@dataclass
class AppContext:
    service: AutomationService
    store: Store
    config: AppConfig
    data_dir: Path
    log_file: Path
    bus: Bus = field(default_factory=Bus)
    _engines: dict = field(default_factory=dict)

    # ---- settings shortcuts ---------------------------------------------
    def setting(self, key: str, default=None):
        return self.store.get(key, default)

    def set_setting(self, key: str, value) -> None:
        self.store.set(key, value)

    def known_folders(self) -> dict[str, str]:
        return standard_folders()

    # ---- local AI -----------------------------------------------------------
    # ai_engine: "builtin" (llama.cpp inside GHOST, default) or "ollama" (advanced, separate app)
    def engine(self) -> EmbeddedEngine | None:
        key = self.setting("builtin_model", "smart")
        if key not in MODELS or not engine_available() or not is_downloaded(self.data_dir, key):
            return None
        if key not in self._engines:
            self._engines[key] = EmbeddedEngine(self.data_dir, key)
        return self._engines[key]

    def ai_label(self) -> str:
        if self.setting("ai_engine", "builtin") == "builtin":
            return MODEL_PREFIX + self.setting("builtin_model", "smart")
        return self.setting("ai_model", "llama3.2:3b")

    def ollama(self) -> OllamaProvider | None:
        """The active local-AI provider for rules (name kept for compatibility), or None."""
        if not self.setting("ai_enabled", False):
            return None
        try:
            if self.setting("ai_engine", "builtin") == "builtin":
                eng = self.engine()
                if eng is None:
                    return None
                return OllamaProvider(model=eng.model_name, transport=eng.transport, timeout=600)
            return OllamaProvider(self.config.ollama_url, self.setting("ai_model", "llama3.2:3b"))
        except ValueError:
            return None

    def make_agent(self):
        from ..agent.planner import OllamaAgent

        if not self.setting("ai_enabled", False):
            return None
        if self.setting("ai_engine", "builtin") == "builtin":
            eng = self.engine()
            return OllamaAgent(model=eng.model_name, transport=eng.transport, timeout=900) if eng else None
        try:
            return OllamaAgent(self.config.ollama_url, self.setting("ai_model", "llama3.2:3b"))
        except ValueError:
            return None
