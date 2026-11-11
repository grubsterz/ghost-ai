"""Download-completeness detection.

A new file is only processed once it has a non-temporary name, its size has stayed
the same for `settle_seconds`, and no other program holds it open."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePath

from ..domain.matching import is_temporary_name
from .filesystem import FileSystem


@dataclass
class _Entry:
    size: int
    since: float


@dataclass
class PendingTracker:
    fs: FileSystem
    settle_seconds: float = 2.0
    max_wait_seconds: float = 3600.0
    _pending: dict[str, _Entry] = field(default_factory=dict)
    _first_seen: dict[str, float] = field(default_factory=dict)

    def observe(self, path: str, now: float) -> None:
        if is_temporary_name(PurePath(path).name):
            return
        self._first_seen.setdefault(path, now)
        self._pending.setdefault(path, _Entry(size=-1, since=now))

    def forget(self, path: str) -> None:
        self._pending.pop(path, None)
        self._first_seen.pop(path, None)

    @property
    def pending(self) -> list[str]:
        return list(self._pending)

    def poll(self, now: float) -> list[str]:
        """Return files that are now ready; they are removed from the pending set."""
        ready: list[str] = []
        for path, entry in list(self._pending.items()):
            if not self.fs.is_file(path):
                self.forget(path)  # renamed (e.g. .crdownload -> .pdf) or deleted
                continue
            if now - self._first_seen.get(path, now) > self.max_wait_seconds:
                self.forget(path)
                continue
            try:
                size = self.fs.size(path)
            except OSError:
                continue
            if size != entry.size:
                self._pending[path] = _Entry(size=size, since=now)
                continue
            if now - entry.since >= self.settle_seconds and self.fs.can_open_exclusive(path):
                ready.append(path)
                self.forget(path)
        return ready
