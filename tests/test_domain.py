from datetime import datetime

import pytest

from ghost_ai.domain.matching import is_temporary_name, matches, render_name, unique_name
from ghost_ai.domain.models import Action, ActionType, CaseMode, Conditions, Rule, SpaceMode
from ghost_ai.domain.validation import ValidationError, validate_rule_dict


def test_matching_by_extension_and_name():
    c = Conditions(extensions=["pdf"], name_contains=["invoice"])
    assert matches(c, "Invoice-2026.PDF")
    assert not matches(c, "report.pdf")
    assert not matches(c, "invoice.docx")


def test_glob_and_empty_conditions():
    assert matches(Conditions(name_glob="scan_*"), "scan_001.jpg")
    assert not matches(Conditions(), "anything.txt"), "empty rule must never match everything"


@pytest.mark.parametrize("name", ["file.pdf.crdownload", "movie.mkv.part", "~$report.docx", "x.tmp", "desktop.ini"])
def test_temporary_files_ignored(name):
    assert is_temporary_name(name)
    assert not matches(Conditions(name_glob="*"), name)


def test_render_name_template_and_transforms():
    now = datetime(2026, 11, 11, 9, 30, 0)
    a = Action(type=ActionType.RENAME, rename_template="{date} {stem}{ext}", case=CaseMode.LOWER,
               spaces=SpaceMode.UNDERSCORE)
    assert render_name(a, "My Report.PDF", now) == "2026-11-11_my_report.PDF"


def test_render_name_cannot_escape_folder():
    a = Action(type=ActionType.RENAME, rename_template="../{stem}{ext}")
    assert "/" not in render_name(a, "a.txt") and "\\" not in render_name(a, "a.txt")


def test_unique_name():
    taken = {"a.pdf", "a (1).pdf"}
    assert unique_name("a.pdf", lambda n: n in taken) == "a (2).pdf"


def test_rule_roundtrip():
    r = Rule(name="x", watch_dir="/tmp/a", conditions=Conditions(extensions=["pdf"]),
             action=Action(type=ActionType.MOVE, target_dir="/tmp/b"))
    assert Rule.from_dict(r.to_dict()).to_dict() == r.to_dict()


VALID = {
    "name": "PDFs", "watch_dir": "/x/Downloads",
    "conditions": {"extensions": ["PDF"], "name_contains": [], "name_glob": ""},
    "action": {"type": "move", "target_dir": "/x/Docs", "rename_template": "{stem}{ext}"},
}


def test_validation_accepts_valid():
    rule = validate_rule_dict(VALID)
    assert rule.conditions.extensions == ["pdf"]


@pytest.mark.parametrize("mutate,msg", [
    (lambda d: d["action"].update(type="shell"), "not allowed"),
    (lambda d: d["action"].update(type="run", command="rm -rf /"), "Unknown field"),
    (lambda d: d.update(exec="calc.exe"), "Unknown field"),
    (lambda d: d["action"].update(target_dir="C:/x; del *"), "forbidden"),
    (lambda d: d["action"].update(rename_template="{stem}{evil}{ext}"), "placeholder"),
    (lambda d: d["action"].update(rename_template="../../{stem}"), "paths"),
    (lambda d: d["conditions"].update(extensions=["p df"]), "extension"),
    (lambda d: d["conditions"].update(extensions=[]), "condition"),
    (lambda d: d["action"].update(target_dir=""), "target"),
    (lambda d: d.update(name=123), "text"),
])
def test_validation_rejects_untrusted(mutate, msg):
    import copy
    d = copy.deepcopy(VALID)
    mutate(d)
    with pytest.raises(ValidationError, match=msg):
        validate_rule_dict(d)


def test_example_rule_files_are_valid():
    import json
    from pathlib import Path

    files = list((Path(__file__).resolve().parents[1] / "examples" / "rules").glob("*.json"))
    assert files
    for f in files:
        for item in json.loads(f.read_text(encoding="utf-8"))["rules"]:
            rule = validate_rule_dict(item)
            assert "~" not in rule.watch_dir and "~" not in rule.action.target_dir
