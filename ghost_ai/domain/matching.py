"""Rule matching and file-name rendering. Pure functions."""

from __future__ import annotations

import fnmatch
import re
from datetime import datetime
from pathlib import PurePath

from .models import Action, CaseMode, Conditions, Rule, SpaceMode

# Partial downloads and editor temp files are never touched.
TEMP_SUFFIXES = {
    "crdownload", "part", "partial", "download", "tmp", "opdownload", "!ut", "aria2", "temp", "dwl", "dwl2",
}
TEMP_PREFIXES = ("~$", ".~lock", ".#")

ALLOWED_PLACEHOLDERS = {"stem", "ext", "date", "time", "year", "month", "day"}
_PLACEHOLDER_RE = re.compile(r"\{([a-z_]+)\}")


def extension_of(name: str) -> str:
    suffix = PurePath(name).suffix
    return suffix[1:].lower() if suffix else ""


def is_temporary_name(name: str) -> bool:
    if name.startswith(TEMP_PREFIXES):
        return True
    if name in {"desktop.ini", "Thumbs.db", ".DS_Store"}:
        return True
    return extension_of(name) in TEMP_SUFFIXES


def matches(conditions: Conditions, file_name: str) -> bool:
    if is_temporary_name(file_name):
        return False
    if conditions.is_empty():
        return False  # an empty rule would match everything - refuse by design
    lower = file_name.lower()
    if conditions.extensions and extension_of(file_name) not in conditions.extensions:
        return False
    if conditions.name_contains and not any(s.lower() in lower for s in conditions.name_contains if s):
        return False
    if conditions.name_glob and not fnmatch.fnmatch(lower, conditions.name_glob.lower()):
        return False
    return True


def rule_matches(rule: Rule, file_name: str) -> bool:
    return matches(rule.conditions, file_name)


def template_placeholders(template: str) -> set[str]:
    return set(_PLACEHOLDER_RE.findall(template))


def render_name(action: Action, file_name: str, now: datetime | None = None) -> str:
    """Render the destination file name. Never returns path separators."""
    now = now or datetime.now()
    p = PurePath(file_name)
    stem, ext = p.stem, p.suffix
    if stem.startswith(".") and not ext:
        stem, ext = file_name, ""
    values = {
        "stem": stem,
        "ext": ext,
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H-%M-%S"),
        "year": now.strftime("%Y"),
        "month": now.strftime("%m"),
        "day": now.strftime("%d"),
    }
    template = action.rename_template or "{stem}{ext}"
    out = _PLACEHOLDER_RE.sub(lambda m: values.get(m.group(1), m.group(0)), template)
    # Apply case/space transforms to the stem part only, keep extension intact.
    out_p = PurePath(out)
    new_stem, new_ext = out_p.stem, out_p.suffix
    if action.case == CaseMode.LOWER:
        new_stem = new_stem.lower()
    elif action.case == CaseMode.UPPER:
        new_stem = new_stem.upper()
    if action.spaces == SpaceMode.UNDERSCORE:
        new_stem = re.sub(r"\s+", "_", new_stem)
    elif action.spaces == SpaceMode.DASH:
        new_stem = re.sub(r"\s+", "-", new_stem)
    result = f"{new_stem}{new_ext}"
    result = result.replace("/", "_").replace("\\", "_").replace(":", "-").strip()
    return result or file_name


def unique_name(name: str, taken: callable) -> str:
    """Return `name` or `name (1)`, `name (2)`... whichever `taken(candidate)` says is free."""
    if not taken(name):
        return name
    p = PurePath(name)
    stem, ext = p.stem, p.suffix
    for i in range(1, 10_000):
        candidate = f"{stem} ({i}){ext}"
        if not taken(candidate):
            return candidate
    raise RuntimeError(f"No free name for {name}")
