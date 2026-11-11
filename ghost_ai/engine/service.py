"""AutomationService - the single entry point the UI talks to.

Owns the guard, planner, executor and the folder watcher. Qt-free so it can be tested."""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import PurePath
from typing import Callable

from ..domain.models import ActionRecord, PlannedAction, Rule, Trigger
from ..safety.guard import Blocked, PathGuard
from ..storage.db import Store
from .executor import Executor, Planner, new_batch_id
from .filesystem import FileSystem, RealFileSystem
from .stability import PendingTracker

log = logging.getLogger(__name__)


@dataclass
class PendingApproval:
    id: int
    plan: PlannedAction
    created: float = field(default_factory=time.time)


class AutomationService:
    def __init__(self, store: Store, app_data_dir: str, fs: FileSystem | None = None,
                 settle_seconds: float = 2.0) -> None:
        self.store = store
        self.fs = fs or RealFileSystem()
        self.app_data_dir = app_data_dir
        self.quarantine_dir = os.path.join(app_data_dir, "quarantine")
        os.makedirs(self.quarantine_dir, exist_ok=True)
        self.guard = PathGuard(allowed_roots=[], app_data_dir=app_data_dir)
        for f in store.folders():
            try:
                self.guard.add_root(f)
            except Blocked:
                log.warning("stored folder no longer allowed: %s", f)
        self.planner = Planner(self.fs, self.quarantine_dir)
        self.executor = Executor(self.fs, self.guard, store, self.quarantine_dir)
        if store.get("paused", False):
            self.executor.paused.set()
        self.tracker = PendingTracker(self.fs, settle_seconds=settle_seconds)
        self.approvals: list[PendingApproval] = []
        self._approval_seq = 0
        self._recent_outputs: dict[str, float] = {}
        self._tracker_lock = threading.Lock()
        self._observer = None
        self._worker: threading.Thread | None = None
        self._stop = threading.Event()
        self.on_change: list[Callable[[], None]] = []
        self.watch_error: str = ""
        self.executor.listeners.append(self._remember_output)

    # ---- notifications ----------------------------------------------------
    def _changed(self) -> None:
        for cb in list(self.on_change):
            try:
                cb()
            except Exception:
                log.exception("on_change callback failed")

    def _remember_output(self, rec: ActionRecord) -> None:
        self._recent_outputs[os.path.normcase(rec.dst)] = time.time()

    # ---- folders ----------------------------------------------------------
    def add_folder(self, folder: str) -> str:
        p = self.guard.add_root(folder)
        self.store.add_folder(p)
        self._changed()
        return p

    def remove_folder(self, folder: str) -> None:
        self.guard.remove_root(folder)
        self.store.remove_folder(folder)
        self.restart_watching()
        self._changed()

    def folders(self) -> list[str]:
        return list(self.guard.allowed_roots)

    def missing_folders(self, rule: Rule) -> list[str]:
        """Folders the rule needs that the user has not granted yet."""
        needed = [rule.watch_dir]
        if rule.action.target_dir:
            needed.append(rule.action.target_dir)
        return [f for f in needed if not self.guard.is_allowed_folder(f)]

    # ---- rules ------------------------------------------------------------
    def rules(self) -> list[Rule]:
        return self.store.list_rules()

    def save_rule(self, rule: Rule) -> None:
        for f in self.missing_folders(rule):
            raise Blocked("outside_allowed", f)
        self.store.save_rule(rule)
        self.restart_watching()
        self._changed()

    def delete_rule(self, rule_id: str) -> None:
        self.store.delete_rule(rule_id)
        self.restart_watching()
        self._changed()

    # ---- manual runs ------------------------------------------------------
    def preview_rule(self, rule: Rule) -> list[PlannedAction]:
        if self.missing_folders(rule):
            return []
        return self.planner.plan(rule, self.planner.files_for_rule(rule))

    def preview_rules(self, rules: list[Rule]) -> list[PlannedAction]:
        reserved: set[str] = set()
        claimed: set[str] = set()
        out: list[PlannedAction] = []
        for rule in rules:
            if self.missing_folders(rule):
                continue
            files = [f for f in self.planner.files_for_rule(rule) if os.path.normcase(f) not in claimed]
            plans = self.planner.plan(rule, files, reserved=reserved)
            claimed.update(os.path.normcase(p.src) for p in plans)
            out += plans
        return out

    def execute(self, plans: list[PlannedAction], dry_run: bool = False) -> list[ActionRecord]:
        recs = self.executor.execute(plans, dry_run=dry_run)
        self._changed()
        return recs

    def undo_last(self) -> list[ActionRecord]:
        batch = self.store.last_undoable_batch()
        recs = self.executor.undo_batch(batch) if batch else []
        self._changed()
        return recs

    def undo_record(self, record_id: int) -> ActionRecord | None:
        rec = self.store.record(record_id)
        if rec is None or not rec.undoable:
            return None
        out = self.executor.undo_record(rec)
        self._changed()
        return out

    # ---- pause ------------------------------------------------------------
    @property
    def paused(self) -> bool:
        return self.executor.paused.is_set()

    def set_paused(self, paused: bool) -> None:
        (self.executor.paused.set if paused else self.executor.paused.clear)()
        self.store.set("paused", paused)
        self._changed()

    # ---- approvals --------------------------------------------------------
    def approve(self, approval_id: int) -> list[ActionRecord]:
        item = next((a for a in self.approvals if a.id == approval_id), None)
        if not item:
            return []
        self.approvals.remove(item)
        return self.execute([item.plan])

    def reject(self, approval_id: int) -> None:
        self.approvals = [a for a in self.approvals if a.id != approval_id]
        self._changed()

    # ---- watching ---------------------------------------------------------
    def watch_rules(self) -> list[Rule]:
        return [r for r in self.rules() if r.enabled and r.trigger == Trigger.WATCH and not self.missing_folders(r)]

    def handle_new_file(self, path: str) -> list[ActionRecord]:
        """Called once a file is complete. First matching watch rule wins."""
        key = os.path.normcase(path)
        t = self._recent_outputs.get(key)
        if t and time.time() - t < 30:
            return []  # GHOST put it there itself - don't loop
        parent = PurePath(path).parent
        for rule in self.watch_rules():
            wd = PurePath(rule.watch_dir)
            in_scope = os.path.normcase(str(parent)) == os.path.normcase(str(wd)) or (
                rule.recursive and os.path.normcase(str(wd)) in {os.path.normcase(str(p)) for p in PurePath(path).parents})
            if not in_scope:
                continue
            plans = [p for p in self.planner.plan(rule, [path]) if not p.skipped]
            if not plans:
                continue
            if rule.confirm_each:
                self._approval_seq += 1
                self.approvals.append(PendingApproval(self._approval_seq, plans[0]))
                self._changed()
                return []
            return self.execute(plans)
        return []

    def notify_path(self, path: str) -> None:
        with self._tracker_lock:
            self.tracker.observe(path, time.monotonic())

    def poll_once(self) -> None:
        with self._tracker_lock:
            ready = self.tracker.poll(time.monotonic())
        for path in ready:
            try:
                self.handle_new_file(path)
            except Exception:
                log.exception("failed handling %s", path)

    def start_watching(self) -> bool:
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
        except ImportError:
            self.watch_error = "watchdog_missing"
            return False
        service = self

        class Handler(FileSystemEventHandler):
            def on_created(self, event):  # noqa: N802
                if not event.is_directory:
                    service.notify_path(event.src_path)

            def on_moved(self, event):  # noqa: N802
                if not event.is_directory:
                    service.notify_path(event.dest_path)

            def on_modified(self, event):  # noqa: N802
                if not event.is_directory:
                    service.notify_path(event.src_path)

        self.stop_watching()
        dirs = {os.path.normcase(r.watch_dir): r for r in self.watch_rules() if os.path.isdir(r.watch_dir)}
        observer = Observer()
        for _key, rule in dirs.items():
            try:
                observer.schedule(Handler(), rule.watch_dir, recursive=rule.recursive)
            except OSError as exc:
                log.warning("cannot watch %s: %s", rule.watch_dir, exc)
        observer.daemon = True
        observer.start()
        self._observer = observer
        self._stop.clear()
        self._worker = threading.Thread(target=self._loop, name="ghost-worker", daemon=True)
        self._worker.start()
        self.watch_error = ""
        log.info("watching %d folder(s)", len(dirs))
        return True

    def _loop(self) -> None:
        while not self._stop.wait(0.5):
            self.poll_once()

    def stop_watching(self) -> None:
        self._stop.set()
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=3)
            self._observer = None
        if self._worker is not None:
            self._worker.join(timeout=3)
            self._worker = None

    @property
    def watching(self) -> bool:
        return self._observer is not None

    def watched_folders(self) -> list[str]:
        return sorted({r.watch_dir for r in self.watch_rules()})

    def restart_watching(self) -> None:
        if self._observer is not None:
            self.start_watching()

    def new_batch(self) -> str:
        return new_batch_id()
