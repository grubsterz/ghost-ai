"""Teach Mode: record what the user demonstrates inside GHOST AI, then propose general rules.

GHOST only records actions the user performs through its own Teach Mode panel (move,
copy, rename of files the user picked). It does not observe the screen, keyboard or other apps.
"""

from __future__ import annotations

import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import PurePath

from ..domain.matching import extension_of
from ..domain.models import Action, ActionType, CaseMode, Conditions, Rule, SpaceMode, Trigger


@dataclass
class DemoStep:
    type: ActionType
    src: str
    dst: str  # full destination path (for rename: same folder, new name)
    ts: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


@dataclass
class Proposal:
    rule: Rule
    confidence: float  # 0..1, shown to the user, honest heuristic
    explanation: list[str]  # stable message keys + args, rendered by the UI
    examples: list[DemoStep]


class DemoRecorder:
    def __init__(self) -> None:
        self.steps: list[DemoStep] = []
        self.active = False
        self.folder_listing: dict[str, list[str]] = {}  # folder -> file names seen when recording started

    def start(self, folder: str, names: list[str]) -> None:
        self.steps.clear()
        self.active = True
        self.folder_listing = {folder: list(names)}

    def record(self, step: DemoStep) -> None:
        if self.active:
            self.steps.append(step)

    def undo_last(self) -> DemoStep | None:
        return self.steps.pop() if self.steps else None

    def stop(self) -> list[DemoStep]:
        self.active = False
        return list(self.steps)


_TOKEN_RE = re.compile(r"[A-Za-zÀ-ž]{3,}")
_DATE_RE = r"\d{4}-\d{2}-\d{2}"


def _common_tokens(stems: list[str]) -> list[str]:
    if len(stems) < 2:
        return []
    sets = [{t.lower() for t in _TOKEN_RE.findall(s)} for s in stems]
    common = set.intersection(*sets) if sets else set()
    return sorted(common)


def infer_rename(old_name: str, new_name: str) -> tuple[str, CaseMode, SpaceMode] | None:
    """Infer a rename template that turns old_name into new_name, or None."""
    old, new = PurePath(old_name), PurePath(new_name)
    o_stem, n_stem, ext = old.stem, new.stem, old.suffix
    if new.suffix.lower() != ext.lower():
        return None
    for case in (CaseMode.KEEP, CaseMode.LOWER, CaseMode.UPPER):
        for spaces in (SpaceMode.KEEP, SpaceMode.UNDERSCORE, SpaceMode.DASH):
            base = o_stem
            if case == CaseMode.LOWER:
                base = base.lower()
            elif case == CaseMode.UPPER:
                base = base.upper()
            if spaces == SpaceMode.UNDERSCORE:
                base = re.sub(r"\s+", "_", base)
            elif spaces == SpaceMode.DASH:
                base = re.sub(r"\s+", "-", base)
            if base not in n_stem or not base:
                continue
            idx = n_stem.find(base)
            prefix, suffix = n_stem[:idx], n_stem[idx + len(base):]
            # Recognise dates so the rule generalises instead of hard-coding today's date.
            prefix = re.sub(_DATE_RE, "{date}", prefix)
            suffix = re.sub(_DATE_RE, "{date}", suffix)
            if any(c in prefix + suffix for c in "/\\"):
                return None
            template = f"{prefix}{{stem}}{suffix}{{ext}}"
            if template == "{stem}{ext}" and case == CaseMode.KEEP and spaces == SpaceMode.KEEP:
                continue
            return template, case, spaces
    return None


def generalize(steps: list[DemoStep], folder_names: list[str] | None = None) -> list[Proposal]:
    """Turn demonstrated steps into rule proposals, one per (action, target) group."""
    groups: dict[tuple, list[DemoStep]] = defaultdict(list)
    for s in steps:
        src_dir = str(PurePath(s.src).parent)
        if s.type == ActionType.RENAME:
            key = (s.type, src_dir, "")
        else:
            key = (s.type, src_dir, str(PurePath(s.dst).parent))
        groups[key].append(s)

    proposals: list[Proposal] = []
    for (atype, src_dir, target), group in groups.items():
        names = [PurePath(s.src).name for s in group]
        exts = sorted({extension_of(n) for n in names if extension_of(n)})
        tokens = _common_tokens([PurePath(n).stem for n in names])
        explanation: list[str] = [f"examples:{len(group)}"]
        confidence = 0.4 + min(len(group), 4) * 0.12

        conditions = Conditions(extensions=exts)
        if tokens:
            conditions.name_contains = tokens[:1]
            explanation.append(f"common_text:{tokens[0]}")
        if exts:
            explanation.append("extensions:" + ",".join(exts))

        # Did the user leave similar files untouched? Then the guess is less certain.
        if folder_names is not None:
            from ..domain.matching import matches
            touched = {n.lower() for n in names}
            untouched = [n for n in folder_names if n.lower() not in touched and matches(conditions, n)]
            if untouched:
                confidence -= 0.25
                explanation.append(f"untouched_similar:{len(untouched)}")

        action = Action(type=atype, target_dir=target)
        if atype == ActionType.RENAME or any(PurePath(s.src).name != PurePath(s.dst).name for s in group):
            inferred = {infer_rename(PurePath(s.src).name, PurePath(s.dst).name) for s in group}
            inferred.discard(None)
            if len(inferred) == 1:
                template, case, spaces = inferred.pop()
                action.rename_template, action.case, action.spaces = template, case, spaces
                explanation.append(f"rename_pattern:{template}")
            elif atype == ActionType.RENAME:
                explanation.append("rename_unclear")
                confidence -= 0.3

        if conditions.is_empty():
            explanation.append("no_condition")
            confidence = 0.1
        if len(group) == 1:
            explanation.append("single_example")

        verb = {"move": "Move", "copy": "Copy", "rename": "Rename", "trash": "Quarantine"}[atype.value]
        what = ", ".join(e.upper() for e in exts) or "files"
        dest = f" → {os.path.basename(target) or target}" if target else ""
        rule = Rule(name=f"{verb} {what}{dest}", watch_dir=src_dir, conditions=conditions, action=action,
                    trigger=Trigger.WATCH, source="teach", enabled=False)
        proposals.append(Proposal(rule=rule, confidence=max(0.05, min(confidence, 0.95)),
                                  explanation=explanation, examples=group))
    proposals.sort(key=lambda p: -p.confidence)
    return proposals
