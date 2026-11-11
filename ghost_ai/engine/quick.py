"""Quick Actions: user-defined sequences of safe, pre-approved steps.

Allowed steps (closed set):
* {"type": "run_rule", "rule_id": "..."}   - apply an existing rule to files already in its folder
* {"type": "open_folder", "path": "..."}   - open an allowed folder in the system file manager
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..domain.models import PlannedAction, new_id
from ..domain.validation import ValidationError

STEP_TYPES = {"run_rule", "open_folder"}


@dataclass
class QuickAction:
    name: str
    steps: list[dict[str, str]] = field(default_factory=list)
    id: str = field(default_factory=new_id)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "steps": [dict(s) for s in self.steps]}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "QuickAction":
        if not isinstance(d, dict) or not isinstance(d.get("name"), str) or not d["name"].strip():
            raise ValidationError("quick action needs a name")
        steps = d.get("steps", [])
        if not isinstance(steps, list) or len(steps) > 20:
            raise ValidationError("invalid steps")
        clean = []
        for s in steps:
            if not isinstance(s, dict) or s.get("type") not in STEP_TYPES:
                raise ValidationError(f"step type not allowed: {s!r}"[:120])
            if s["type"] == "run_rule":
                if not isinstance(s.get("rule_id"), str):
                    raise ValidationError("run_rule needs rule_id")
                clean.append({"type": "run_rule", "rule_id": s["rule_id"]})
            else:
                if not isinstance(s.get("path"), str):
                    raise ValidationError("open_folder needs path")
                clean.append({"type": "open_folder", "path": s["path"]})
        qa = cls(name=d["name"].strip()[:80], steps=clean)
        if isinstance(d.get("id"), str) and d["id"]:
            qa.id = d["id"][:32]
        return qa


@dataclass
class QuickPlan:
    actions: list[PlannedAction]
    open_folders: list[str]
    problems: list[str]


def plan_quick_action(qa: QuickAction, service) -> QuickPlan:  # service: AutomationService
    rules = []
    folders: list[str] = []
    problems: list[str] = []
    for step in qa.steps:
        if step["type"] == "run_rule":
            rule = service.store.get_rule(step["rule_id"])
            if rule is None:
                problems.append("missing_rule")
            elif service.missing_folders(rule):
                problems.append("folder_not_allowed")
            else:
                rules.append(rule)
        elif step["type"] == "open_folder":
            if service.guard.is_allowed_folder(step["path"]):
                folders.append(step["path"])
            else:
                problems.append("folder_not_allowed")
    return QuickPlan(service.preview_rules(rules), folders, problems)
