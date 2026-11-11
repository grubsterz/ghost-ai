"""Planning, execution, dry-run and undo of file actions."""

from __future__ import annotations

import logging
import os
import shutil
import threading
import uuid
from datetime import datetime
from pathlib import Path, PurePath
from typing import Callable, Iterable

from ..domain.matching import render_name, rule_matches, unique_name
from ..domain.models import ActionRecord, ActionType, ConflictPolicy, PlannedAction, Rule, Status
from ..safety.guard import Blocked, PathGuard
from ..storage.db import Store
from .filesystem import FileSystem

log = logging.getLogger(__name__)


def new_batch_id() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:6]


class Planner:
    def __init__(self, fs: FileSystem, quarantine_dir: str) -> None:
        self.fs = fs
        self.quarantine_dir = quarantine_dir

    def files_for_rule(self, rule: Rule) -> list[str]:
        if not self.fs.is_dir(rule.watch_dir):
            return []
        return [f for f in self.fs.list_files(rule.watch_dir, rule.recursive) if rule_matches(rule, PurePath(f).name)]

    def plan(self, rule: Rule, files: Iterable[str], now: datetime | None = None,
             reserved: set[str] | None = None) -> list[PlannedAction]:
        """Compute concrete actions. `reserved` collects destinations already taken in this batch."""
        reserved = reserved if reserved is not None else set()
        out: list[PlannedAction] = []
        for src in files:
            name = PurePath(src).name
            if not rule_matches(rule, name):
                continue
            a = rule.action
            new_name = render_name(a, name, now)
            if a.type == ActionType.RENAME:
                folder = str(PurePath(src).parent)
            elif a.type == ActionType.TRASH:
                folder = os.path.join(self.quarantine_dir, uuid.uuid4().hex[:8])
                new_name = name
            else:
                folder = a.target_dir
            dst = os.path.join(folder, new_name)
            pa = PlannedAction(type=a.type, src=src, dst=dst, rule_id=rule.id, rule_name=rule.name)
            if os.path.normcase(os.path.abspath(dst)) == os.path.normcase(os.path.abspath(src)):
                pa.skipped, pa.note = True, "already_in_place"
                out.append(pa)
                continue

            def taken(candidate: str, folder: str = folder) -> bool:
                full = os.path.join(folder, candidate)
                return self.fs.exists(full) or os.path.normcase(full) in reserved

            if taken(new_name):
                if rule.conflict == ConflictPolicy.SKIP:
                    pa.skipped, pa.note = True, "name_conflict"
                    out.append(pa)
                    continue
                new_name = unique_name(new_name, taken)
                pa.dst = os.path.join(folder, new_name)
                pa.note = "renamed_conflict"
            reserved.add(os.path.normcase(pa.dst))
            out.append(pa)
        return out


class Executor:
    """Executes planned actions through the guard and the file-system adapter, journaling everything."""

    def __init__(self, fs: FileSystem, guard: PathGuard, store: Store, quarantine_dir: str) -> None:
        self.fs = fs
        self.guard = guard
        self.store = store
        self.quarantine_dir = quarantine_dir
        self.paused = threading.Event()  # set() = everything paused
        self._lock = threading.Lock()
        self.listeners: list[Callable[[ActionRecord], None]] = []

    def _emit(self, rec: ActionRecord) -> None:
        for cb in list(self.listeners):
            try:
                cb(rec)
            except Exception:  # a broken listener must never stop the engine
                log.exception("listener failed")

    def _check(self, pa: PlannedAction) -> None:
        self.guard.check_file(pa.src)
        self.guard.check_file(pa.dst, as_destination=True)

    def execute(self, plans: list[PlannedAction], dry_run: bool = False, batch_id: str | None = None,
                journal_dry_run: bool = False) -> list[ActionRecord]:
        batch_id = batch_id or new_batch_id()
        records: list[ActionRecord] = []
        with self._lock:
            for pa in plans:
                rec = ActionRecord(type=pa.type, src=pa.src, dst=pa.dst, status=Status.DONE, batch_id=batch_id,
                                   rule_id=pa.rule_id, rule_name=pa.rule_name, message=pa.note)
                if pa.skipped:
                    rec.status = Status.SKIPPED
                elif self.paused.is_set() and not dry_run:
                    rec.status, rec.message = Status.BLOCKED, "paused"
                else:
                    try:
                        self._check(pa)
                        if dry_run:
                            rec.status = Status.DRY_RUN
                        else:
                            self._apply(pa)
                    except Blocked as b:
                        rec.status, rec.message = Status.BLOCKED, b.reason
                    except OSError as exc:
                        rec.status, rec.message = Status.FAILED, f"{type(exc).__name__}: {exc}"
                        log.warning("action failed %s -> %s: %s", pa.src, pa.dst, exc)
                if not dry_run or journal_dry_run:
                    self.store.add_record(rec)
                    log.info("%s %s %s -> %s", rec.status, rec.type, rec.src, rec.dst)
                records.append(rec)
                if not dry_run:
                    self._emit(rec)
        return records

    def _apply(self, pa: PlannedAction) -> None:
        if not self.fs.exists(pa.src):
            raise FileNotFoundError(pa.src)
        self.fs.makedirs(str(PurePath(pa.dst).parent))
        if pa.type == ActionType.COPY:
            self.fs.copy(pa.src, pa.dst)
        else:  # move, rename and trash are all moves
            self.fs.move(pa.src, pa.dst)

    # ---- undo -------------------------------------------------------------
    def undo_record(self, rec: ActionRecord) -> ActionRecord:
        if rec.status != Status.DONE or rec.id is None:
            raise ValueError("not_undoable")
        with self._lock:
            try:
                if not self.fs.exists(rec.dst):
                    raise FileNotFoundError(rec.dst)
                if rec.type == ActionType.COPY:
                    # Never delete: the copy goes to quarantine.
                    q = os.path.join(self.quarantine_dir, uuid.uuid4().hex[:8], PurePath(rec.dst).name)
                    self.guard.check_file(rec.dst)
                    self.fs.makedirs(str(PurePath(q).parent))
                    self.fs.move(rec.dst, q)
                    msg = q
                else:
                    folder = str(PurePath(rec.src).parent)
                    name = unique_name(PurePath(rec.src).name, lambda c: self.fs.exists(os.path.join(folder, c)))
                    back = os.path.join(folder, name)
                    self.guard.check_file(back)
                    self.fs.makedirs(folder)
                    self.fs.move(rec.dst, back)
                    msg = back
                self.store.set_status(rec.id, Status.UNDONE, msg)
                rec.status, rec.message = Status.UNDONE, msg
            except Blocked as b:
                rec.message = f"undo_blocked: {b.reason}"
                self.store.set_status(rec.id, Status.DONE, rec.message)
            except OSError as exc:
                rec.message = f"undo_failed: {exc}"
                self.store.set_status(rec.id, Status.DONE, rec.message)
        self._emit(rec)
        return rec

    def undo_batch(self, batch_id: str) -> list[ActionRecord]:
        out = []
        for rec in reversed(self.store.batch(batch_id)):
            if rec.status == Status.DONE:
                out.append(self.undo_record(rec))
        return out


def quarantine_size(quarantine_dir: str) -> tuple[int, int]:
    """(file count, bytes) in quarantine."""
    count = total = 0
    for root, _dirs, files in os.walk(quarantine_dir):
        for f in files:
            count += 1
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return count, total


def empty_quarantine(quarantine_dir: str) -> int:
    """PERMANENTLY delete quarantined files. Only called after explicit user confirmation."""
    count, _ = quarantine_size(quarantine_dir)
    p = Path(quarantine_dir)
    if p.exists():
        shutil.rmtree(p)
    p.mkdir(parents=True, exist_ok=True)
    return count
