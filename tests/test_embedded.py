import io
import json

import pytest

from ghost_ai.ai import embedded
from ghost_ai.ai.embedded import MODELS, EmbeddedEngine, download_model, is_downloaded
from ghost_ai.ai.natural import OllamaProvider
from ghost_ai.agent.planner import OllamaAgent


class FakeResp(io.BytesIO):
    def __init__(self, data: bytes, status: int = 200):
        super().__init__(data)
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def tiny_model(monkeypatch):
    info = MODELS["small"]
    monkeypatch.setitem(MODELS, "small", embedded.ModelInfo("small", "tiny.gguf", "https://x/tiny.gguf", 10,
                                                            info.label_en, info.label_hr))
    return MODELS["small"]


def test_download_verifies_size_and_resumes(tmp_path, tiny_model):
    calls = []

    def opener(req, timeout):
        rng = req.headers.get("Range")
        calls.append(rng)
        if rng:
            return FakeResp(b"56789"[: 10 - int(rng.split("=")[1].rstrip("-")) ], status=206)
        return FakeResp(b"01234")  # connection "drops" after 5 bytes

    with pytest.raises(OSError):
        download_model(tmp_path, "small", opener=opener)
    assert not is_downloaded(tmp_path, "small")
    path = download_model(tmp_path, "small", opener=opener)
    assert path.read_bytes() == b"0123456789" and calls[-1] == "bytes=5-"
    assert is_downloaded(tmp_path, "small")


def test_engine_speaks_ollama_api(tmp_path, tiny_model, monkeypatch):
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "tiny.gguf").write_bytes(b"x" * 10)
    monkeypatch.setattr(embedded, "engine_available", lambda: True)
    eng = EmbeddedEngine(tmp_path, "small")
    seen = []

    def fake_chat(messages, schema, max_tokens=1024):
        seen.append((messages, schema))
        if schema and "steps" in schema.get("properties", {}):
            return json.dumps({"reply": "ok", "steps": [{"explanation": "v", "command": "git --version"}]})
        return json.dumps({"name": "PDF", "watch_dir": "/u/Downloads",
                           "conditions": {"extensions": ["pdf"], "name_contains": [""], "name_glob": ""},
                           "action": {"type": "move", "target_dir": "/u/Documents", "rename_template": "{stem}{ext}"}})

    monkeypatch.setattr(eng, "chat", fake_chat)
    p = OllamaProvider(model=eng.model_name, transport=eng.transport)
    assert p.status() == (True, ["ghost-builtin:small"])
    res = p.propose("move pdfs", {"downloads": "/u/Downloads", "documents": "/u/Documents"})
    assert res.rule is not None and res.rule.conditions.name_contains == [], "blank items from small models are dropped"
    assert seen[0][0][0]["role"] == "system" and seen[0][1]["required"]
    agent = OllamaAgent(model=eng.model_name, transport=eng.transport)
    plan = agent.ask("git version?", {})
    assert plan.steps[0].command == "git --version"


def test_engine_not_ready_reports_unavailable(tmp_path):
    eng = EmbeddedEngine(tmp_path, "smart")
    assert OllamaProvider(model=eng.model_name, transport=eng.transport).status() == (False, [])


def test_tab_in_command_is_rejected():
    from ghost_ai.agent.planner import parse_agent_json
    from ghost_ai.domain.validation import ValidationError
    with pytest.raises(ValidationError):
        parse_agent_json('{"reply": "", "steps": [{"explanation": "x", "command": "dir C:\\Users\test"}]}')


def test_context_prefers_builtin_engine(tmp_path, service, tiny_model, monkeypatch):
    from ghost_ai.config import AppConfig
    from ghost_ai.ui.context import AppContext

    monkeypatch.setattr("ghost_ai.ui.context.engine_available", lambda: True)
    ctx = AppContext(service=service, store=service.store, config=AppConfig(), data_dir=tmp_path,
                     log_file=tmp_path / "l.log")
    ctx.set_setting("ai_enabled", True)
    ctx.set_setting("builtin_model", "small")
    assert ctx.ollama() is None and ctx.make_agent() is None, "no model downloaded yet"
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "tiny.gguf").write_bytes(b"x" * 10)
    assert ctx.ollama().model == "ghost-builtin:small"
    assert ctx.make_agent() is not None
    ctx.set_setting("ai_engine", "ollama")
    assert ctx.ollama().model == "llama3.2:3b"
