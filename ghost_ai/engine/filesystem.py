"""File-system adapter. The engine only touches disk through this interface,
so tests and dry-runs can use an in-memory implementation."""

from __future__ import annotations

import os
import shutil
from pathlib import Path, PurePath
from typing import Protocol


class FileSystem(Protocol):
    def exists(self, path: str) -> bool: ...
    def is_file(self, path: str) -> bool: ...
    def is_dir(self, path: str) -> bool: ...
    def size(self, path: str) -> int: ...
    def list_files(self, folder: str, recursive: bool = False) -> list[str]: ...
    def makedirs(self, folder: str) -> None: ...
    def move(self, src: str, dst: str) -> None: ...
    def copy(self, src: str, dst: str) -> None: ...
    def can_open_exclusive(self, path: str) -> bool: ...


class RealFileSystem:
    def exists(self, path: str) -> bool:
        return os.path.lexists(path)

    def is_file(self, path: str) -> bool:
        return os.path.isfile(path)

    def is_dir(self, path: str) -> bool:
        return os.path.isdir(path)

    def size(self, path: str) -> int:
        return os.path.getsize(path)

    def list_files(self, folder: str, recursive: bool = False) -> list[str]:
        out: list[str] = []
        if recursive:
            for root, dirs, files in os.walk(folder):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                out += [os.path.join(root, f) for f in files]
        else:
            with os.scandir(folder) as it:
                out = [e.path for e in it if e.is_file(follow_symlinks=False)]
        return sorted(out)

    def makedirs(self, folder: str) -> None:
        os.makedirs(folder, exist_ok=True)

    def move(self, src: str, dst: str) -> None:
        if os.path.lexists(dst):
            raise FileExistsError(dst)
        shutil.move(src, dst)

    def copy(self, src: str, dst: str) -> None:
        if os.path.lexists(dst):
            raise FileExistsError(dst)
        shutil.copy2(src, dst)

    def can_open_exclusive(self, path: str) -> bool:
        """True if no other process holds the file open for writing (best effort)."""
        try:
            if os.name == "nt":
                # Renaming onto itself fails while another process has the file open without sharing.
                os.rename(path, path)
            with open(path, "rb"):
                pass
            return True
        except OSError:
            return False


class MemoryFileSystem:
    """In-memory file system for tests. Paths are plain strings with '/' or '\\'."""

    def __init__(self) -> None:
        self.files: dict[str, int] = {}
        self.dirs: set[str] = set()
        self.locked: set[str] = set()

    @staticmethod
    def _n(p: str) -> str:
        return str(PurePath(p))

    def add(self, path: str, size: int = 1) -> None:
        p = self._n(path)
        self.files[p] = size
        self.makedirs(str(PurePath(p).parent))

    def exists(self, path: str) -> bool:
        p = self._n(path)
        return p in self.files or p in self.dirs

    def is_file(self, path: str) -> bool:
        return self._n(path) in self.files

    def is_dir(self, path: str) -> bool:
        return self._n(path) in self.dirs

    def size(self, path: str) -> int:
        return self.files[self._n(path)]

    def list_files(self, folder: str, recursive: bool = False) -> list[str]:
        f = PurePath(folder)
        out = []
        for p in self.files:
            pp = PurePath(p)
            if pp.parent == f or (recursive and f in pp.parents):
                out.append(p)
        return sorted(out)

    def makedirs(self, folder: str) -> None:
        p = PurePath(folder)
        while str(p) not in self.dirs and p != p.parent:
            self.dirs.add(str(p))
            p = p.parent

    def move(self, src: str, dst: str) -> None:
        s, d = self._n(src), self._n(dst)
        if d in self.files:
            raise FileExistsError(d)
        if s not in self.files:
            raise FileNotFoundError(s)
        self.makedirs(str(PurePath(d).parent))
        self.files[d] = self.files.pop(s)

    def copy(self, src: str, dst: str) -> None:
        s, d = self._n(src), self._n(dst)
        if d in self.files:
            raise FileExistsError(d)
        self.makedirs(str(PurePath(d).parent))
        self.files[d] = self.files[s]

    def can_open_exclusive(self, path: str) -> bool:
        return self._n(path) not in self.locked


def same_volume(a: str, b: str) -> bool:
    return Path(a).anchor.lower() == Path(b).anchor.lower()
