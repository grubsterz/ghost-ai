import json
import os

import pytest

from ghost_ai.ai.natural import KeywordProvider, OllamaProvider, extract_json, propose_rule
from ghost_ai.domain.models import ActionType, CaseMode, SpaceMode
from ghost_ai.domain.validation import ValidationError
from ghost_ai.engine.quick import QuickAction, plan_quick_action
from ghost_ai.teach.generalizer import DemoRecorder, DemoStep, generalize, infer_rename

FOLDERS = {"downloads": "/u/Downloads", "documents": "/u/Documents", "pictures": "/u/Pictures",
           "desktop": "/u/Desktop", "music": "/u/Music", "videos": "/u/Videos"}


# ---- Teach Mode ------------------------------------------------------------

def test_generalize_moves_to_extension_rule():
    rec = DemoRecorder()
    rec.start("/u/Downloads", ["a.pdf", "b.pdf", "c.jpg"])
    rec.record(DemoStep(ActionType.MOVE, "/u/Downloads/a.pdf", "/u/Documents/a.pdf"))
    rec.record(DemoStep(ActionType.MOVE, "/u/Downloads/b.pdf", "/u/Documents/b.pdf"))
    steps = rec.stop()
    props = generalize(steps, ["a.pdf", "b.pdf", "c.jpg"])
    assert len(props) == 1
    r = props[0].rule
    assert r.conditions.extensions == ["pdf"]
    assert r.action.type == ActionType.MOVE
    assert r.enabled is False, "taught rules start disabled until the user approves"
    assert props[0].confidence > 0.5


def test_generalize_lowers_confidence_when_similar_files_untouched():
    steps = [DemoStep(ActionType.MOVE, "/u/Downloads/a.pdf", "/u/Documents/a.pdf")]
    full = generalize(steps, ["a.pdf"])[0].confidence
    partial = generalize(steps, ["a.pdf", "b.pdf", "c.pdf"])[0].confidence
    assert partial < full


def test_generalize_common_name_token():
    steps = [DemoStep(ActionType.MOVE, "/d/Invoice March.pdf", "/i/Invoice March.pdf"),
             DemoStep(ActionType.MOVE, "/d/invoice_april.pdf", "/i/invoice_april.pdf")]
    r = generalize(steps)[0].rule
    assert r.conditions.name_contains == ["invoice"]


def test_infer_rename_patterns():
    assert infer_rename("Scan 1.jpg", "2026-11-11 Scan 1.jpg") == ("{date} {stem}{ext}", CaseMode.KEEP, SpaceMode.KEEP)
    assert infer_rename("My File.txt", "my_file.txt") == ("{stem}{ext}", CaseMode.LOWER, SpaceMode.UNDERSCORE)
    assert infer_rename("a.txt", "b.pdf") is None


def test_generalize_rename():
    steps = [DemoStep(ActionType.RENAME, "/d/IMG 1.jpg", "/d/holiday_IMG 1.jpg"),
             DemoStep(ActionType.RENAME, "/d/IMG 2.jpg", "/d/holiday_IMG 2.jpg")]
    r = generalize(steps)[0].rule
    assert r.action.type == ActionType.RENAME and r.action.rename_template == "holiday_{stem}{ext}"


# ---- Natural language -------------------------------------------------------

@pytest.mark.parametrize("text,atype,ext,src,dst", [
    ("Premjesti sve PDF-ove iz Preuzimanja u Dokumente", "move", "pdf", "downloads", "documents"),
    ("move images from Downloads to Pictures", "move", "png", "downloads", "pictures"),
    ("kopiraj slike s radne površine u mapu Slike", "copy", "jpg", "desktop", "pictures"),
    ("Move zip files into Documents", "move", "zip", "downloads", "documents"),
])
def test_keyword_parser(text, atype, ext, src, dst):
    res = KeywordProvider().propose(text, FOLDERS)
    assert res.rule is not None, res.error
    assert res.rule.action.type.value == atype
    assert ext in res.rule.conditions.extensions
    assert res.rule.watch_dir == os.path.normpath(FOLDERS[src])
    assert res.rule.action.target_dir == os.path.normpath(FOLDERS[dst])


def test_keyword_parser_refuses_vague_request():
    res = KeywordProvider().propose("napravi mi kavu", FOLDERS)
    assert res.rule is None and res.error


def test_extract_json_from_chatty_output():
    raw = 'Sure! Here you go:\n```json\n{"a": {"b": "}"}}\n```'
    assert extract_json(raw) == {"a": {"b": "}"}}
    with pytest.raises(ValidationError):
        extract_json("no json here")


def fake_transport(response_obj):
    calls = []

    def t(url, payload, timeout):
        calls.append((url, payload))
        if url.endswith("/api/tags"):
            return {"models": [{"name": "llama3.2:3b"}]}
        return {"response": json.dumps(response_obj) if not isinstance(response_obj, str) else response_obj}
    t.calls = calls
    return t


def test_ollama_valid_proposal_and_schema_sent():
    obj = {"name": "PDF", "watch_dir": "/u/Downloads",
           "conditions": {"extensions": ["pdf"], "name_contains": [], "name_glob": ""},
           "action": {"type": "move", "target_dir": "/u/Documents", "rename_template": "{stem}{ext}"}}
    tr = fake_transport(obj)
    p = OllamaProvider(transport=tr)
    res = p.propose("move pdfs", FOLDERS)
    assert res.rule is not None and res.rule.source == "natural"
    assert tr.calls[0][1]["format"]["required"], "structured output schema is sent"
    assert p.status() == (True, ["llama3.2:3b"])


def test_ollama_malicious_output_rejected_and_falls_back():
    evil = {"name": "x", "watch_dir": "/u/Downloads", "conditions": {"extensions": ["pdf"]},
            "action": {"type": "shell", "command": "rm -rf ~"}}
    res = propose_rule("premjesti pdf iz preuzimanja u dokumente", FOLDERS, OllamaProvider(transport=fake_transport(evil)))
    assert res.provider == "keywords" and res.rule is not None
    assert res.rule.action.type == ActionType.MOVE
    assert any(w.startswith("ollama_failed") for w in res.warnings)


def test_ollama_url_must_be_local():
    with pytest.raises(ValueError):
        OllamaProvider(base_url="https://evil.example.com")


# ---- Quick actions ----------------------------------------------------------

def test_quick_action_validation_and_plan(service, sandbox):
    from conftest import make_rule
    dl, docs = sandbox
    (dl / "a.pdf").write_text("x")
    rule = make_rule(dl, docs)
    service.save_rule(rule)
    qa = QuickAction.from_dict({"name": "Tidy", "steps": [{"type": "run_rule", "rule_id": rule.id},
                                                          {"type": "open_folder", "path": str(docs)}]})
    plan = plan_quick_action(qa, service)
    assert len(plan.actions) == 1 and plan.open_folders == [str(docs)] and not plan.problems
    with pytest.raises(ValidationError):
        QuickAction.from_dict({"name": "bad", "steps": [{"type": "shell", "cmd": "calc"}]})


def test_destination_folder_name_is_not_a_file_category():
    res = KeywordProvider().propose("Premjesti sve PDF-ove iz Preuzimanja u Dokumente", FOLDERS)
    assert res.rule.conditions.extensions == ["pdf"]
    res = KeywordProvider().propose("move images from Downloads to Documents", FOLDERS)
    assert "pdf" not in res.rule.conditions.extensions and "png" in res.rule.conditions.extensions
