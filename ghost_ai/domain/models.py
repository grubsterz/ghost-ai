"""Core domain types. Pure data, no I/O, no Qt."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class ActionType(StrEnum):
    MOVE = "move"
    COPY = "copy"
    RENAME = "rename"
    TRASH = "trash"  # moves into GHOST quarantine, never deletes


class ConflictPolicy(StrEnum):
    RENAME = "rename"  # "report (1).pdf"
    SKIP = "skip"


class Trigger(StrEnum):
    WATCH = "watch"  # runs automatically when a new file appears
    MANUAL = "manual"  # only via "Run now" or a Quick Action


class CaseMode(StrEnum):
    KEEP = "keep"
    LOWER = "lower"
    UPPER = "upper"


class SpaceMode(StrEnum):
    KEEP = "keep"
    UNDERSCORE = "underscore"
    DASH = "dash"


@dataclass(slots=True)
class Conditions:
    """All non-empty criteria must match (AND). Inside a list, any value may match (OR)."""

    extensions: list[str] = field(default_factory=list)  # lowercase, without dot
    name_contains: list[str] = field(default_factory=list)  # case-insensitive substrings
    name_glob: str = ""  # fnmatch pattern against the full file name

    def is_empty(self) -> bool:
        return not (self.extensions or self.name_contains or self.name_glob)

    def to_dict(self) -> dict[str, Any]:
        return {
            "extensions": list(self.extensions),
            "name_contains": list(self.name_contains),
            "name_glob": self.name_glob,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Conditions":
        return cls(
            extensions=[str(e).lower().lstrip(".") for e in d.get("extensions", [])],
            name_contains=[str(s) for s in d.get("name_contains", [])],
            name_glob=str(d.get("name_glob", "")),
        )


@dataclass(slots=True)
class Action:
    type: ActionType
    target_dir: str = ""  # for move / copy
    rename_template: str = "{stem}{ext}"  # for rename (also applied on move/copy if set)
    case: CaseMode = CaseMode.KEEP
    spaces: SpaceMode = SpaceMode.KEEP

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "target_dir": self.target_dir,
            "rename_template": self.rename_template,
            "case": self.case.value,
            "spaces": self.spaces.value,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Action":
        return cls(
            type=ActionType(d["type"]),
            target_dir=str(d.get("target_dir", "")),
            rename_template=str(d.get("rename_template", "{stem}{ext}")) or "{stem}{ext}",
            case=CaseMode(d.get("case", "keep")),
            spaces=SpaceMode(d.get("spaces", "keep")),
        )


def new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass(slots=True)
class Rule:
    name: str
    watch_dir: str
    conditions: Conditions
    action: Action
    id: str = field(default_factory=new_id)
    enabled: bool = True
    trigger: Trigger = Trigger.WATCH
    conflict: ConflictPolicy = ConflictPolicy.RENAME
    recursive: bool = False
    confirm_each: bool = False  # ask before every automatic action
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    source: str = "manual"  # manual | teach | natural | template | import

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "watch_dir": self.watch_dir,
            "conditions": self.conditions.to_dict(),
            "action": self.action.to_dict(),
            "enabled": self.enabled,
            "trigger": self.trigger.value,
            "conflict": self.conflict.value,
            "recursive": self.recursive,
            "confirm_each": self.confirm_each,
            "created_at": self.created_at,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Rule":
        return cls(
            id=str(d.get("id") or new_id()),
            name=str(d["name"]),
            watch_dir=str(d["watch_dir"]),
            conditions=Conditions.from_dict(d.get("conditions", {})),
            action=Action.from_dict(d["action"]),
            enabled=bool(d.get("enabled", True)),
            trigger=Trigger(d.get("trigger", "watch")),
            conflict=ConflictPolicy(d.get("conflict", "rename")),
            recursive=bool(d.get("recursive", False)),
            confirm_each=bool(d.get("confirm_each", False)),
            created_at=str(d.get("created_at") or datetime.now().isoformat(timespec="seconds")),
            source=str(d.get("source", "manual")),
        )


@dataclass(slots=True)
class PlannedAction:
    """A concrete operation computed from a rule and a file. Nothing has happened yet."""

    type: ActionType
    src: str
    dst: str
    rule_id: str = ""
    rule_name: str = ""
    skipped: bool = False
    note: str = ""


class Status(StrEnum):
    DONE = "done"
    DRY_RUN = "dry_run"
    SKIPPED = "skipped"
    FAILED = "failed"
    BLOCKED = "blocked"
    UNDONE = "undone"


@dataclass(slots=True)
class ActionRecord:
    """A journal entry - what actually happened (or would have, in dry-run)."""

    type: ActionType
    src: str
    dst: str
    status: Status
    batch_id: str
    rule_id: str = ""
    rule_name: str = ""
    message: str = ""
    ts: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    id: int | None = None

    @property
    def undoable(self) -> bool:
        return self.status == Status.DONE
