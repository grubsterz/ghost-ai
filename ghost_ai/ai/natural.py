"""Natural-language → rule proposal.

Two providers:
* OllamaProvider - optional local model (http://127.0.0.1:11434), structured JSON output.
* KeywordProvider - built-in, deterministic HR/EN phrase parser that works with no model.

Whatever a provider returns is untrusted text. It is parsed as JSON, validated against a strict
schema (domain.validation) and turned into a Rule *proposal* the user must review. Nothing a model
says is ever executed as code or shell.
"""

from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from ..domain.models import Rule
from ..domain.validation import PROPOSAL_JSON_SCHEMA, ValidationError, validate_rule_dict

log = logging.getLogger(__name__)


@dataclass
class ParseResult:
    rule: Rule | None
    provider: str
    error: str = ""
    raw: str = ""
    warnings: list[str] = field(default_factory=list)


class Provider(Protocol):
    name: str

    def propose(self, text: str, known_folders: dict[str, str]) -> ParseResult: ...


# ---------------------------------------------------------------------------
# Known folders and categories
# ---------------------------------------------------------------------------

def standard_folders(home: Path | None = None) -> dict[str, str]:
    home = home or Path.home()
    names = {
        "downloads": "Downloads", "desktop": "Desktop", "documents": "Documents",
        "pictures": "Pictures", "music": "Music", "videos": "Videos" if os.name == "nt" else "Movies",
    }
    out = {}
    for key, folder in names.items():
        p = home / folder
        if key == "desktop" and not p.exists():
            od = home / "OneDrive" / "Desktop"
            if od.exists():
                p = od
        if key == "documents" and not p.exists():
            od = home / "OneDrive" / "Documents"
            if od.exists():
                p = od
        out[key] = str(p)
    return out


FOLDER_WORDS = {
    "downloads": ["downloads", "download", "preuzimanja", "preuzimanje", "preuzete", "skinute"],
    "desktop": ["desktop", "radna povrsina", "radnu povrsinu", "radne povrsine", "radnoj povrsini"],
    "documents": ["documents", "dokumenti", "dokumente", "dokumentima", "dokumenata"],
    "pictures": ["pictures", "photos folder", "mapa slike", "mapu slike", "u slike", "iz slika"],
    "music": ["music folder", "mapa glazba", "mapu glazba", "u glazbu"],
    "videos": ["videos folder", "movies folder", "mapu videa", "u videe", "u videozapise"],
}

CATEGORIES = {
    "images": (["slike", "slika", "fotografije", "fotke", "images", "image", "photos", "pictures", "screenshots",
                "snimke zaslona"], ["jpg", "jpeg", "png", "gif", "webp", "heic", "bmp", "tiff"]),
    "documents": (["dokumente", "dokumenti", "documents", "docs"], ["pdf", "doc", "docx", "txt", "odt", "rtf", "xlsx",
                                                                    "xls", "pptx", "ppt", "csv"]),
    "videos": (["video", "videe", "videozapise", "videos", "filmove", "movies"], ["mp4", "mov", "mkv", "avi", "webm"]),
    "music": (["glazbu", "pjesme", "music", "songs", "audio", "mp3ice"], ["mp3", "wav", "flac", "m4a", "ogg", "aac"]),
    "archives": (["arhive", "arhiva", "zipove", "archives", "zips", "compressed"], ["zip", "rar", "7z", "tar", "gz"]),
    "installers": (["instalacije", "instalere", "installers", "setup"], ["exe", "msi", "dmg", "pkg"]),
}

KNOWN_EXTS = sorted({e for _, exts in CATEGORIES.values() for e in exts} | {"json", "html", "epub", "psd", "svg", "ai"},
                    key=len, reverse=True)


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c)).replace("đ", "d")


class KeywordProvider:
    """Deterministic parser for simple sentences like
    'premjesti PDF-ove iz Preuzimanja u Dokumente' / 'move images from Downloads to Pictures'."""

    name = "keywords"

    def propose(self, text: str, known_folders: dict[str, str]) -> ParseResult:
        t = " " + _fold(text) + " "

        if re.search(r"\b(kopiraj|copy|duplicate)\b", t):
            atype = "copy"
        elif re.search(r"\b(preimenuj|rename)\b", t):
            atype = "rename"
        elif re.search(r"\b(obrisi|izbrisi|delete|remove|trash|smece)\b", t):
            atype = "trash"
        else:
            atype = "move"

        def find_folder(segment: str) -> str | None:
            best = None
            for key, fwords in FOLDER_WORDS.items():
                for w in fwords:
                    i = segment.find(w)
                    if i >= 0 and (best is None or i < best[0]):
                        best = (i, key)
            return known_folders.get(best[1]) if best else None

        src = dst = None
        m_from = re.search(r"\b(iz|from|sa|s)\b(.*?)(\b(u|to|into|na|do)\b|$)", t)
        m_to = re.search(r"\b(u|to|into|na)\b(?!.*\b(u|to|into|na)\b)(.*)$", t)
        if m_from:
            src = find_folder(m_from.group(2))
        if m_to:
            dst = find_folder(m_to.group(3))
        if src is None:
            src = known_folders.get("downloads")
        warnings = []
        if not m_from or find_folder(m_from.group(2)) is None:
            warnings.append("assumed_downloads")

        # Folder phrases ("iz Preuzimanja", "u Dokumente") must not count as file categories.
        cond_text = t
        for m in (m_from, m_to):
            if m:
                g = m.group(2) if m is m_from else m.group(3)
                cond_text = cond_text.replace(g, " ", 1) if g.strip() else cond_text
        exts: list[str] = []
        for _cat, (cwords, cexts) in CATEGORIES.items():
            if any(re.search(rf"\b{re.escape(w)}\b", cond_text) for w in cwords):
                exts += cexts
        for e in KNOWN_EXTS:
            if re.search(rf"(?<![a-z0-9]){e}(?:-?(ovi|ove|ova|a|e|s|ice|ovima))?\b", cond_text):
                exts.append(e)
        if "jpg" in exts:
            exts.append("jpeg")
        exts = sorted(set(exts))

        contains: list[str] = []
        m = re.search(r"(?:koje u imenu imaju|u imenu|s imenom|sadrze|containing|named|with the name|"
                      r"whose name contains|name contains)\s+[\"'“„]?([a-z0-9_\-]{2,30})", t)
        if m:
            contains.append(m.group(1))
        else:
            m = re.search(r"[\"'“„]([^\"'”“]{2,30})[\"'”“]", text)
            if m:
                contains.append(m.group(1).strip())

        template = "{stem}{ext}"
        case = "keep"
        spaces = "keep"
        if atype == "rename":
            if re.search(r"\b(datum|date)\b", t):
                template = "{date} {stem}{ext}" if re.search(r"\b(ispred|prefix|before|na pocetak)\b", t) \
                    else "{stem} {date}{ext}"
            if re.search(r"\b(mala slova|lowercase|lower case)\b", t):
                case = "lower"
            if re.search(r"(razmak\w*|spaces?)\b.*\b(podvlak\w*|underscores?)", t):
                spaces = "underscore"

        if not exts and not contains:
            return ParseResult(None, self.name, error="no_condition", raw=text)
        if atype in ("move", "copy") and not dst:
            return ParseResult(None, self.name, error="no_target", raw=text)

        label = ", ".join(e.upper() for e in exts[:4]) + ("…" if len(exts) > 4 else "") or contains[0]
        data = {
            "name": f"{atype.capitalize()} {label}",
            "watch_dir": src or "",
            "conditions": {"extensions": exts, "name_contains": contains, "name_glob": ""},
            "action": {"type": atype, "target_dir": dst or "", "rename_template": template,
                       "case": case, "spaces": spaces},
            "source": "natural",
        }
        try:
            return ParseResult(validate_rule_dict(data), self.name, raw=json.dumps(data), warnings=warnings)
        except ValidationError as exc:
            return ParseResult(None, self.name, error=str(exc), raw=json.dumps(data))


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You convert a user's request about organizing files into ONE JSON object.
You never write code or shell commands. Allowed action types: move, copy, rename, trash.
Fields:
- name: short title (max 60 chars)
- watch_dir: absolute folder path to watch. Known folders: {folders}
- conditions.extensions: lowercase file extensions without dots, e.g. ["pdf"]
- conditions.name_contains: words that must appear in the file name (may be empty)
- conditions.name_glob: optional pattern like "invoice*" (usually "")
- action.type: move | copy | rename | trash
- action.target_dir: absolute destination folder for move/copy, otherwise ""
- action.rename_template: new file name using only {{stem}} {{ext}} {{date}} {{time}} {{year}} {{month}} {{day}};
  use "{{stem}}{{ext}}" to keep the name.
If the request is not about files, return {{"name":"","watch_dir":"","conditions":{{"extensions":[],"name_contains":[],"name_glob":""}},"action":{{"type":"move","target_dir":"","rename_template":"{{stem}}{{ext}}"}}}}.
The user may write in Croatian or English."""


def extract_json(text: str) -> dict[str, Any]:
    """Pull the first JSON object out of model text. Raises ValidationError."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\s*|\s*```$", "", text)
    start = text.find("{")
    if start < 0:
        raise ValidationError("model returned no JSON")
    depth = 0
    in_str = esc = False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            esc = (c == "\\") and not esc
            if c == '"' and not esc:
                in_str = False
            elif c != "\\":
                esc = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(text[start:i + 1])
                except json.JSONDecodeError as exc:
                    raise ValidationError(f"invalid JSON: {exc.msg}") from None
                if not isinstance(obj, dict):
                    raise ValidationError("JSON must be an object")
                return obj
    raise ValidationError("unterminated JSON")


Transport = Callable[[str, dict[str, Any] | None, float], dict[str, Any]]


def http_json(url: str, payload: dict[str, Any] | None, timeout: float) -> dict[str, Any]:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"},
                                 method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - local URL from settings
        return json.loads(resp.read().decode("utf-8"))


def is_local_url(url: str) -> bool:
    return bool(re.match(r"^https?://(127\.0\.0\.1|localhost|\[::1\])(:\d+)?(/|$)", url))


class OllamaProvider:
    name = "ollama"

    def __init__(self, base_url: str = "http://127.0.0.1:11434", model: str = "llama3.2:3b",
                 transport: Transport = http_json, timeout: float = 60.0) -> None:
        if not is_local_url(base_url):
            raise ValueError("Ollama URL must be local (privacy)")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.transport = transport
        self.timeout = timeout

    def status(self) -> tuple[bool, list[str]]:
        """(reachable, installed model names)."""
        try:
            data = self.transport(f"{self.base_url}/api/tags", None, 2.0)
            return True, [m.get("name", "") for m in data.get("models", [])]
        except (urllib.error.URLError, OSError, ValueError, TimeoutError):
            return False, []

    def propose(self, text: str, known_folders: dict[str, str]) -> ParseResult:
        folders = ", ".join(f"{k}={v}" for k, v in known_folders.items())
        payload = {
            "model": self.model,
            "system": SYSTEM_PROMPT.format(folders=folders),
            "prompt": text[:2000],
            "format": PROPOSAL_JSON_SCHEMA,
            "stream": False,
            "options": {"temperature": 0},
        }
        try:
            resp = self.transport(f"{self.base_url}/api/generate", payload, self.timeout)
        except (urllib.error.URLError, OSError, ValueError, TimeoutError) as exc:
            return ParseResult(None, self.name, error=f"ollama_unreachable: {exc}")
        raw = str(resp.get("response", ""))
        try:
            obj = extract_json(raw)
            if not obj.get("name"):
                return ParseResult(None, self.name, error="not_a_file_task", raw=raw)
            obj["source"] = "natural"
            return ParseResult(validate_rule_dict(obj), self.name, raw=raw)
        except ValidationError as exc:
            return ParseResult(None, self.name, error=str(exc), raw=raw)


def propose_rule(text: str, known_folders: dict[str, str], ollama: OllamaProvider | None) -> ParseResult:
    """Try the local model first (if configured), fall back to the keyword parser."""
    if ollama is not None:
        res = ollama.propose(text, known_folders)
        if res.rule is not None:
            return res
        log.info("ollama could not produce a valid rule (%s); using keyword parser", res.error)
        fallback = KeywordProvider().propose(text, known_folders)
        fallback.warnings.append(f"ollama_failed:{res.error[:120]}")
        return fallback
    return KeywordProvider().propose(text, known_folders)
