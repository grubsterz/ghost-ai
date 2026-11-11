"""Application paths and configuration (non-secret, local only)."""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)


def data_dir() -> Path:
    override = os.environ.get("GHOST_AI_HOME")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "GHOST AI"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "GHOST AI"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "ghost-ai"


@dataclass
class Links:
    website: str = "https://github.com/grubsterz/ghost-ai"
    rivoxo: str = "https://trophonia.com/rivoxo"
    source: str = "https://github.com/grubsterz/ghost-ai"


@dataclass
class AppConfig:
    """Lives in <data>/config.json so links and defaults can be changed without rebuilding."""

    links: Links = field(default_factory=Links)
    ollama_url: str = "http://127.0.0.1:11434"
    settle_seconds: float = 2.0
    telemetry: bool = False  # there is no telemetry code at all; kept explicit for transparency

    @classmethod
    def load(cls, path: Path) -> "AppConfig":
        cfg = cls()
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                links = raw.get("links", {})
                cfg.links = Links(**{k: str(v) for k, v in links.items() if k in Links.__dataclass_fields__})
                cfg.ollama_url = str(raw.get("ollama_url", cfg.ollama_url))
                cfg.settle_seconds = float(raw.get("settle_seconds", cfg.settle_seconds))
            except (OSError, ValueError, TypeError) as exc:
                log.warning("config.json ignored: %s", exc)
        else:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(asdict(cfg), indent=2), encoding="utf-8")
            except OSError:
                pass
        return cfg


def setup_logging(folder: Path) -> Path:
    from logging.handlers import RotatingFileHandler

    folder.mkdir(parents=True, exist_ok=True)
    log_file = folder / "ghost-ai.log"
    handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    return log_file
