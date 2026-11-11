"""Path safety. Every file operation goes through PathGuard.

Policy:
* Operations are only allowed inside folders the user explicitly selected ("allowed roots").
* System directories, application data, credential stores and browser profiles are always
  forbidden, even if the user selects them.
* Secret-looking files (keys, password databases, .env, cookie stores) are never touched.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

SECRET_FILE_NAMES = {
    ".env", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "known_hosts", "authorized_keys",
    "cookies", "cookies.sqlite", "login data", "web data", "key3.db", "key4.db", "logins.json",
    "credentials", "credentials.json", "token.json", ".netrc", ".npmrc", ".pypirc", ".git-credentials",
}
SECRET_EXTENSIONS = {"kdbx", "kdb", "pem", "key", "p12", "pfx", "keychain", "keychain-db", "gpg", "asc", "ovpn"}
SECRET_DIR_NAMES = {
    ".ssh", ".gnupg", ".aws", ".azure", ".kube", ".docker", ".password-store", "keychains",
    ".git", "1password", "bitwarden", "keepassxc",
}


def _home() -> Path:
    return Path.home()


def default_forbidden_roots() -> list[Path]:
    home = _home()
    roots: list[Path] = []
    if sys.platform == "win32":
        for var in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramData", "ProgramW6432"):
            v = os.environ.get(var)
            if v:
                roots.append(Path(v))
        roots += [home / "AppData", Path(os.environ.get("SystemDrive", "C:") + "\\") / "$Recycle.Bin"]
    else:
        roots += [Path(p) for p in ("/System", "/Library", "/usr", "/bin", "/sbin", "/etc", "/private",
                                     "/var", "/opt", "/dev", "/proc", "/sys", "/boot", "/Applications")]
        roots += [home / "Library", home / ".config", home / ".local", home / ".cache"]
    return roots


def _norm(p: str | Path) -> Path:
    try:
        return Path(os.path.realpath(os.path.expanduser(str(p))))
    except (OSError, ValueError):
        return Path(os.path.abspath(os.path.expanduser(str(p))))


def _is_within(child: Path, parent: Path) -> bool:
    c, p = os.path.normcase(str(child)), os.path.normcase(str(parent))
    if c == p:
        return True
    return c.startswith(p.rstrip("\\/") + os.sep)


class Blocked(PermissionError):
    """Raised when a path is not allowed. `reason` is a stable machine key."""

    def __init__(self, reason: str, path: str):
        super().__init__(f"{reason}: {path}")
        self.reason = reason
        self.path = path


@dataclass
class PathGuard:
    allowed_roots: list[str] = field(default_factory=list)
    forbidden_roots: list[Path] = field(default_factory=default_forbidden_roots)
    app_data_dir: str = ""  # GHOST's own data (quarantine lives here) - allowed as destination only

    # ---- folder selection -------------------------------------------------
    def check_folder_selectable(self, folder: str | Path) -> None:
        """Raise Blocked if the user may not grant access to this folder."""
        p = _norm(folder)
        if p == Path(p.anchor) or p.parent == p:
            raise Blocked("drive_root", str(p))
        if os.path.normcase(str(p)) == os.path.normcase(str(_norm(_home()))):
            raise Blocked("home_root", str(p))
        self._check_not_forbidden(p)

    def add_root(self, folder: str | Path) -> str:
        self.check_folder_selectable(folder)
        p = str(_norm(folder))
        if not any(os.path.normcase(p) == os.path.normcase(r) for r in self.allowed_roots):
            self.allowed_roots.append(p)
        return p

    def remove_root(self, folder: str) -> None:
        n = os.path.normcase(str(_norm(folder)))
        self.allowed_roots = [r for r in self.allowed_roots if os.path.normcase(r) != n]

    def is_allowed_folder(self, folder: str | Path) -> bool:
        p = _norm(folder)
        return any(_is_within(p, _norm(r)) for r in self.allowed_roots)

    # ---- per-operation checks --------------------------------------------
    def _check_not_forbidden(self, p: Path) -> None:
        for root in self.forbidden_roots:
            if _is_within(p, _norm(root)):
                raise Blocked("system_folder", str(p))
        for part in p.parts:
            if part.lower() in SECRET_DIR_NAMES:
                raise Blocked("secret_folder", str(p))

    def check_file(self, path: str | Path, *, as_destination: bool = False) -> Path:
        p = _norm(path)
        if as_destination and self.app_data_dir and _is_within(p, _norm(self.app_data_dir)):
            return p
        self._check_not_forbidden(p)
        name = p.name.lower()
        ext = p.suffix[1:].lower() if p.suffix else ""
        if name in SECRET_FILE_NAMES or ext in SECRET_EXTENSIONS or name.startswith(".env"):
            raise Blocked("secret_file", str(p))
        if not self.is_allowed_folder(p.parent):
            raise Blocked("outside_allowed", str(p))
        return p
