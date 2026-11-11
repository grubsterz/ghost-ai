"""Shared application context handed to every page."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QObject, Signal

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

    # ---- settings shortcuts ---------------------------------------------
    def setting(self, key: str, default=None):
        return self.store.get(key, default)

    def set_setting(self, key: str, value) -> None:
        self.store.set(key, value)

    def known_folders(self) -> dict[str, str]:
        return standard_folders()

    def ollama(self) -> OllamaProvider | None:
        if not self.setting("ai_enabled", False):
            return None
        try:
            return OllamaProvider(self.config.ollama_url, self.setting("ai_model", "llama3.2:3b"))
        except ValueError:
            return None
