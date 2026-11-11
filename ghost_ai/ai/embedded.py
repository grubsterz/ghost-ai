"""Built-in local AI: llama.cpp runs *inside* GHOST AI - nothing else to install.

The only extra thing is the model file (a .gguf data file, 1-2 GB) which GHOST downloads once, on the
user's click, into its data folder. After that everything runs offline on the CPU.

`EmbeddedEngine.transport` speaks the same tiny subset of the Ollama HTTP API that GHOST uses
(/api/tags, /api/generate, /api/chat with a JSON-schema `format`), so the existing, validated
providers (OllamaProvider, OllamaAgent) work unchanged on top of it.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import threading
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelInfo:
    key: str
    file: str
    url: str
    size: int  # bytes, used to verify the download
    label_en: str
    label_hr: str


MODELS: dict[str, ModelInfo] = {
    "smart": ModelInfo(
        "smart", "Qwen2.5-7B-Instruct-Q4_K_M.gguf",
        "https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF/resolve/main/Qwen2.5-7B-Instruct-Q4_K_M.gguf",
        4683074240, "Smart - Qwen2.5 7B (4.7 GB, best for 'do anything', needs 8 GB RAM)",
        "Pametni - Qwen2.5 7B (4,7 GB, najbolji za „bilo što”, treba 8 GB RAM-a)"),
    "standard": ModelInfo(
        "standard", "qwen2.5-3b-instruct-q4_k_m.gguf",
        "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf",
        2104932768, "Standard - Qwen2.5 3B (2.1 GB, good for file rules)", "Standardni - Qwen2.5 3B (2,1 GB, dobar za pravila datoteka)"),
    "small": ModelInfo(
        "small", "qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf",
        1117320736, "Small - Qwen2.5 1.5B (1.1 GB, for older PCs)", "Mali - Qwen2.5 1.5B (1,1 GB, za starija računala)"),
}
MODEL_PREFIX = "ghost-builtin:"


def engine_available() -> bool:
    return importlib.util.find_spec("llama_cpp") is not None


def models_dir(data_dir: str | Path) -> Path:
    return Path(data_dir) / "models"


def model_path(data_dir: str | Path, key: str) -> Path:
    return models_dir(data_dir) / MODELS[key].file


def is_downloaded(data_dir: str | Path, key: str) -> bool:
    p = model_path(data_dir, key)
    return p.exists() and p.stat().st_size == MODELS[key].size


class DownloadCancelled(Exception):
    pass


def download_model(data_dir: str | Path, key: str, progress: Callable[[int, int], None] | None = None,
                   cancel: threading.Event | None = None, opener: Callable[..., Any] = urllib.request.urlopen) -> Path:
    """Download (resumable) into <data>/models. Verifies the exact size before using the file."""
    info = MODELS[key]
    dest = model_path(data_dir, key)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if is_downloaded(data_dir, key):
        return dest
    part = dest.with_suffix(dest.suffix + ".part")
    have = part.stat().st_size if part.exists() else 0
    req = urllib.request.Request(info.url, headers={"User-Agent": "GHOST-AI", **({"Range": f"bytes={have}-"} if have else {})})
    with opener(req, timeout=60) as resp:
        if have and getattr(resp, "status", 200) != 206:
            have = 0  # server ignored the range - start over
        mode = "ab" if have else "wb"
        with open(part, mode) as f:
            done = have
            while True:
                if cancel is not None and cancel.is_set():
                    raise DownloadCancelled()
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, info.size)
    if part.stat().st_size != info.size:
        raise OSError(f"download incomplete: {part.stat().st_size} of {info.size} bytes")
    os.replace(part, dest)
    return dest


class EmbeddedEngine:
    """Loads the model lazily on first use and serialises generation (one request at a time)."""

    def __init__(self, data_dir: str | Path, key: str = "standard", n_ctx: int = 8192) -> None:
        self.data_dir = Path(data_dir)
        self.key = key
        self.n_ctx = n_ctx
        self._llm = None
        self._lock = threading.Lock()

    @property
    def model_name(self) -> str:
        return MODEL_PREFIX + self.key

    def ready(self) -> bool:
        return engine_available() and is_downloaded(self.data_dir, self.key)

    def _load(self):
        if self._llm is None:
            from llama_cpp import Llama

            threads = max(2, (os.cpu_count() or 4) // 2)
            log.info("loading built-in model %s with %d threads", self.key, threads)
            self._llm = Llama(model_path=str(model_path(self.data_dir, self.key)), n_ctx=self.n_ctx,
                              n_threads=threads, verbose=False)
        return self._llm

    def chat(self, messages: list[dict[str, str]], schema: dict[str, Any] | None, max_tokens: int = 1024) -> str:
        with self._lock:
            llm = self._load()
            kwargs: dict[str, Any] = {"messages": messages, "temperature": 0.0, "max_tokens": max_tokens}
            if schema:
                kwargs["response_format"] = {"type": "json_object", "schema": schema}
            out = llm.create_chat_completion(**kwargs)
            return out["choices"][0]["message"]["content"] or ""

    # ---- Ollama-compatible transport ---------------------------------------
    def transport(self, url: str, payload: dict[str, Any] | None, timeout: float) -> dict[str, Any]:
        if url.endswith("/api/tags"):
            if not self.ready():
                raise OSError("built-in model not downloaded")
            return {"models": [{"name": self.model_name}]}
        if not self.ready():
            raise OSError("built-in model not downloaded")
        assert payload is not None
        if url.endswith("/api/generate"):
            msgs = []
            if payload.get("system"):
                msgs.append({"role": "system", "content": payload["system"]})
            msgs.append({"role": "user", "content": payload.get("prompt", "")})
            return {"response": self.chat(msgs, payload.get("format"))}
        if url.endswith("/api/chat"):
            content = self.chat(list(payload.get("messages", [])), payload.get("format"))
            return {"message": {"role": "assistant", "content": content}}
        raise ValueError(f"unsupported endpoint {url}")


def describe(key: str, lang: str) -> str:
    m = MODELS[key]
    return m.label_hr if lang == "hr" else m.label_en


def to_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)
