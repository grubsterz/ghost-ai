"""Strict validation of rule JSON coming from untrusted sources (AI model, imports).

Only a closed set of keys, types and action kinds is accepted. Anything else is rejected
with a human-readable reason. Model output is never executed - it can only become a Rule
proposal that the user reviews.
"""

from __future__ import annotations

import os
import re
from typing import Any

from .matching import ALLOWED_PLACEHOLDERS, template_placeholders
from .models import Action, ActionType, CaseMode, Conditions, ConflictPolicy, Rule, SpaceMode, Trigger

MAX_STR = 260
MAX_LIST = 25
_EXT_RE = re.compile(r"^[a-z0-9]{1,10}$")
_FORBIDDEN_CHARS = set("\x00\n\r\t|;&`$<>\"")

PROPOSAL_KEYS = {"name", "watch_dir", "conditions", "action"}
OPTIONAL_PROPOSAL_KEYS = {"trigger", "conflict", "recursive", "confirm_each", "enabled", "id", "created_at", "source"}
CONDITION_KEYS = {"extensions", "name_contains", "name_glob"}
ACTION_KEYS = {"type", "target_dir", "rename_template", "case", "spaces"}

# JSON schema handed to Ollama's structured-output `format` field.
PROPOSAL_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "watch_dir": {"type": "string"},
        "conditions": {
            "type": "object",
            "properties": {
                "extensions": {"type": "array", "items": {"type": "string"}},
                "name_contains": {"type": "array", "items": {"type": "string"}},
                "name_glob": {"type": "string"},
            },
            "required": ["extensions", "name_contains", "name_glob"],
        },
        "action": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": [t.value for t in ActionType]},
                "target_dir": {"type": "string"},
                "rename_template": {"type": "string"},
            },
            "required": ["type", "target_dir", "rename_template"],
        },
    },
    "required": ["name", "watch_dir", "conditions", "action"],
}


class ValidationError(ValueError):
    pass


def _check_str(value: Any, field: str, *, allow_empty: bool = True, max_len: int = MAX_STR) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"'{field}' must be text")
    if not allow_empty and not value.strip():
        raise ValidationError(f"'{field}' must not be empty")
    if len(value) > max_len:
        raise ValidationError(f"'{field}' is too long")
    if any(c in _FORBIDDEN_CHARS for c in value):
        raise ValidationError(f"'{field}' contains forbidden characters")
    return value.strip()


def _check_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        raise ValidationError(f"'{field}' must be a list")
    if len(value) > MAX_LIST:
        raise ValidationError(f"'{field}' has too many items")
    items = [v for v in value if not (isinstance(v, str) and not v.strip())]  # models emit "" items
    return [_check_str(v, f"{field}[]", allow_empty=False, max_len=64) for v in items]


def _check_keys(d: Any, allowed: set[str], required: set[str], where: str) -> dict[str, Any]:
    if not isinstance(d, dict):
        raise ValidationError(f"'{where}' must be an object")
    unknown = set(d) - allowed
    if unknown:
        raise ValidationError(f"Unknown field(s) in {where}: {', '.join(sorted(unknown))}")
    missing = required - set(d)
    if missing:
        raise ValidationError(f"Missing field(s) in {where}: {', '.join(sorted(missing))}")
    return d


def _expand(path: str) -> str:
    """'~/Downloads' -> absolute path, so shared rule files work on any machine."""
    return os.path.normpath(os.path.expanduser(path)) if path else path


def validate_template(template: str) -> str:
    template = _check_str(template, "rename_template", allow_empty=True, max_len=120)
    if not template:
        return "{stem}{ext}"
    if "/" in template or "\\" in template or ".." in template:
        raise ValidationError("rename_template must not contain paths")
    bad = template_placeholders(template) - ALLOWED_PLACEHOLDERS
    if bad:
        raise ValidationError(f"Unknown placeholder(s): {', '.join(sorted(bad))}")
    if template.count("{") != template.count("}"):
        raise ValidationError("Unbalanced braces in rename_template")
    if "{ext}" not in template:
        raise ValidationError("rename_template must keep the file extension: include {ext}")
    return template


def validate_rule_dict(data: Any) -> Rule:
    """Validate an untrusted dict and build a Rule. Raises ValidationError."""
    d = _check_keys(data, PROPOSAL_KEYS | OPTIONAL_PROPOSAL_KEYS, PROPOSAL_KEYS, "rule")
    name = _check_str(d["name"], "name", allow_empty=False, max_len=80)
    watch_dir = _expand(_check_str(d["watch_dir"], "watch_dir", allow_empty=False))

    c = _check_keys(d["conditions"], CONDITION_KEYS, set(), "conditions")
    exts = [e.lower().lstrip(".") for e in _check_list(c.get("extensions", []), "extensions")]
    for e in exts:
        if not _EXT_RE.match(e):
            raise ValidationError(f"Invalid extension: {e!r}")
    contains = _check_list(c.get("name_contains", []), "name_contains")
    glob = _check_str(c.get("name_glob", ""), "name_glob", max_len=64)
    if "/" in glob or "\\" in glob:
        raise ValidationError("name_glob must match a file name, not a path")
    conditions = Conditions(extensions=sorted(set(exts)), name_contains=contains, name_glob=glob)
    if conditions.is_empty():
        raise ValidationError("At least one condition (extension, name text or pattern) is required")

    a = _check_keys(d["action"], ACTION_KEYS, {"type"}, "action")
    try:
        atype = ActionType(a["type"])
    except ValueError:
        raise ValidationError(f"Action type not allowed: {a['type']!r}") from None
    target = _expand(_check_str(a.get("target_dir", ""), "target_dir"))
    if atype in (ActionType.MOVE, ActionType.COPY) and not target:
        raise ValidationError(f"'{atype.value}' needs a target folder")
    template = validate_template(a.get("rename_template", "{stem}{ext}"))
    if atype == ActionType.RENAME and template == "{stem}{ext}" and a.get("case", "keep") == "keep" \
            and a.get("spaces", "keep") == "keep":
        raise ValidationError("Rename needs a new name pattern")
    try:
        case = CaseMode(a.get("case", "keep"))
        spaces = SpaceMode(a.get("spaces", "keep"))
        trigger = Trigger(d.get("trigger", "watch"))
        conflict = ConflictPolicy(d.get("conflict", "rename"))
    except ValueError as exc:
        raise ValidationError(str(exc)) from None
    action = Action(type=atype, target_dir=target if atype in (ActionType.MOVE, ActionType.COPY) else "",
                    rename_template=template, case=case, spaces=spaces)

    for flag in ("recursive", "confirm_each", "enabled"):
        if flag in d and not isinstance(d[flag], bool):
            raise ValidationError(f"'{flag}' must be true/false")

    rule = Rule(
        name=name,
        watch_dir=watch_dir,
        conditions=conditions,
        action=action,
        trigger=trigger,
        conflict=conflict,
        recursive=bool(d.get("recursive", False)),
        confirm_each=bool(d.get("confirm_each", False)),
        enabled=bool(d.get("enabled", True)),
        source=_check_str(d.get("source", "import"), "source", max_len=20) or "import",
    )
    if isinstance(d.get("id"), str) and re.fullmatch(r"[a-f0-9]{6,32}", d["id"]):
        rule.id = d["id"]
    return rule
