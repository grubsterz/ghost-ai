"""Starter rule templates (all start as normal reviewed rules)."""

from __future__ import annotations

import os

from .ai.natural import CATEGORIES, standard_folders
from .domain.models import Action, ActionType, Conditions, Rule

TEMPLATE_KEYS = ["images", "docs", "archives", "screenshots", "installers"]


def build_template(key: str, folders: dict[str, str] | None = None) -> Rule:
    f = folders or standard_folders()
    if key == "images":
        return Rule(name="Images → Pictures", watch_dir=f["downloads"],
                    conditions=Conditions(extensions=CATEGORIES["images"][1]),
                    action=Action(ActionType.MOVE, target_dir=f["pictures"]), source="template")
    if key == "docs":
        return Rule(name="Documents → Documents", watch_dir=f["downloads"],
                    conditions=Conditions(extensions=["pdf", "doc", "docx", "odt", "rtf", "txt", "xlsx", "pptx"]),
                    action=Action(ActionType.MOVE, target_dir=f["documents"]), source="template")
    if key == "archives":
        return Rule(name="Archives → Documents/Archives", watch_dir=f["downloads"],
                    conditions=Conditions(extensions=CATEGORIES["archives"][1]),
                    action=Action(ActionType.MOVE, target_dir=os.path.join(f["documents"], "Archives")),
                    source="template")
    if key == "screenshots":
        return Rule(name="Screenshots → Pictures/Screenshots", watch_dir=f["desktop"],
                    conditions=Conditions(extensions=["png", "jpg"], name_contains=["screenshot", "snimka zaslona",
                                                                                 "screen shot"]),
                    action=Action(ActionType.MOVE, target_dir=os.path.join(f["pictures"], "Screenshots")),
                    source="template")
    if key == "installers":
        return Rule(name="Old installers → quarantine", watch_dir=f["downloads"],
                    conditions=Conditions(extensions=CATEGORIES["installers"][1]),
                    action=Action(ActionType.TRASH), source="template", confirm_each=True)
    raise KeyError(key)
