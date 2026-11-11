import os
import time
from pathlib import Path

import pytest

from conftest import make_rule
from ghost_ai.domain.models import ActionType, ConflictPolicy, Status, Trigger
from ghost_ai.engine.filesystem import MemoryFileSystem
from ghost_ai.engine.stability import PendingTracker
from ghost_ai.safety.guard import Blocked, PathGuard


def test_dry_run_changes_nothing(service, sandbox):
    dl, docs = sandbox
    (dl / "a.pdf").write_text("x")
    rule = make_rule(dl, docs)
    plans = service.preview_rule(rule)
    recs = service.execute(plans, dry_run=True)
    assert [r.status for r in recs] == [Status.DRY_RUN]
    assert (dl / "a.pdf").exists() and not (docs / "a.pdf").exists()
    assert service.store.records() == [], "dry-run is not journaled as a real action"


def test_move_conflict_and_undo(service, sandbox):
    dl, docs = sandbox
    (dl / "a.pdf").write_text("new")
    (docs / "a.pdf").write_text("old")
    (dl / "b.txt").write_text("ignored")
    rule = make_rule(dl, docs)
    recs = service.execute(service.preview_rule(rule))
    assert recs[0].status == Status.DONE
    assert (docs / "a (1).pdf").read_text() == "new"
    assert (docs / "a.pdf").read_text() == "old", "existing file never overwritten"
    assert (dl / "b.txt").exists()

    undone = service.undo_last()
    assert undone[0].status == Status.UNDONE
    assert (dl / "a.pdf").read_text() == "new"
    assert not (docs / "a (1).pdf").exists()


def test_conflict_skip_policy(service, sandbox):
    dl, docs = sandbox
    (dl / "a.pdf").write_text("1")
    (docs / "a.pdf").write_text("2")
    rule = make_rule(dl, docs, conflict=ConflictPolicy.SKIP)
    recs = service.execute(service.preview_rule(rule))
    assert recs[0].status == Status.SKIPPED and (dl / "a.pdf").exists()


def test_two_files_same_target_name_in_one_batch(service, sandbox, tmp_path):
    dl, docs = sandbox
    (dl / "a.pdf").write_text("1")
    (dl / "A.PDF").write_text("2") if os.name != "nt" else None
    (dl / "sub").mkdir()
    (dl / "sub" / "a.pdf").write_text("3")
    rule = make_rule(dl, docs, recursive=True)
    recs = service.execute(service.preview_rule(rule))
    names = sorted(p.name for p in docs.iterdir())
    assert len(names) == len([r for r in recs if r.status == Status.DONE])
    assert len(set(n.lower() for n in names)) == len(names)


def test_copy_undo_quarantines_instead_of_deleting(service, sandbox):
    dl, docs = sandbox
    (dl / "a.pdf").write_text("x")
    rule = make_rule(dl, docs, atype=ActionType.COPY)
    service.execute(service.preview_rule(rule))
    assert (dl / "a.pdf").exists() and (docs / "a.pdf").exists()
    service.undo_last()
    assert not (docs / "a.pdf").exists()
    q = list(Path(service.quarantine_dir).rglob("a.pdf"))
    assert q, "undone copy goes to quarantine, never deleted"


def test_trash_goes_to_quarantine_and_restores(service, sandbox):
    dl, _ = sandbox
    (dl / "old.zip").write_text("x")
    rule = make_rule(dl, None, exts=("zip",), atype=ActionType.TRASH)
    recs = service.execute(service.preview_rule(rule))
    assert recs[0].status == Status.DONE and not (dl / "old.zip").exists()
    assert Path(recs[0].dst).exists()
    service.undo_last()
    assert (dl / "old.zip").exists()


def test_rename_rule(service, sandbox):
    dl, _ = sandbox
    (dl / "My Scan.jpg").write_text("x")
    rule = make_rule(dl, None, exts=("jpg",), atype=ActionType.RENAME)
    rule.action.rename_template = "scan_{stem}{ext}"
    service.execute(service.preview_rule(rule))
    assert (dl / "scan_My Scan.jpg").exists()


def test_pause_blocks_execution(service, sandbox):
    dl, docs = sandbox
    (dl / "a.pdf").write_text("x")
    service.set_paused(True)
    recs = service.execute(service.preview_rule(make_rule(dl, docs)))
    assert recs[0].status == Status.BLOCKED and (dl / "a.pdf").exists()
    service.set_paused(False)


def test_rule_outside_allowed_folders_is_refused(service, sandbox, tmp_path):
    dl, _ = sandbox
    other = tmp_path / "elsewhere"
    other.mkdir()
    with pytest.raises(Blocked):
        service.save_rule(make_rule(dl, other))
    assert service.preview_rule(make_rule(dl, other)) == []


def test_secret_files_never_touched(service, sandbox):
    dl, docs = sandbox
    (dl / "id_rsa").write_text("secret")
    (dl / "vault.kdbx").write_text("secret")
    rule = make_rule(dl, docs, exts=("kdbx",))
    rule.conditions.name_glob = ""
    recs = service.execute(service.preview_rule(rule))
    assert recs[0].status == Status.BLOCKED and recs[0].message == "secret_file"
    assert (dl / "vault.kdbx").exists()


def test_guard_forbids_system_and_roots(tmp_path):
    g = PathGuard()
    with pytest.raises(Blocked):
        g.check_folder_selectable(Path.home())
    with pytest.raises(Blocked):
        g.check_folder_selectable(Path(Path.home().anchor))
    sysdir = os.environ.get("SystemRoot", "/System")
    with pytest.raises(Blocked):
        g.check_folder_selectable(sysdir)
    with pytest.raises(Blocked):
        g.check_folder_selectable(Path.home() / ".ssh")
    g.add_root(tmp_path)
    with pytest.raises(Blocked):
        g.check_file(tmp_path.parent / "x.txt")
    assert g.check_file(tmp_path / "x.txt")


def test_stability_tracker_waits_for_complete_download():
    fs = MemoryFileSystem()
    t = PendingTracker(fs, settle_seconds=2)
    fs.add("/d/movie.mp4.crdownload", 10)
    t.observe("/d/movie.mp4.crdownload", 0)
    assert t.pending == []
    fs.add("/d/a.pdf", 10)
    t.observe("/d/a.pdf", 0)
    assert t.poll(0) == []
    fs.files[str(Path("/d/a.pdf"))] = 20  # still growing
    assert t.poll(1) == []
    assert t.poll(2.5) == []
    fs.locked.add(str(Path("/d/a.pdf")))
    assert t.poll(4) == [], "locked by another program"
    fs.locked.clear()
    assert t.poll(4.5) == ["/d/a.pdf"]


def test_watch_rule_handles_new_file_and_confirm_each(service, sandbox):
    dl, docs = sandbox
    rule = make_rule(dl, docs)
    service.save_rule(rule)
    f = dl / "new.pdf"
    f.write_text("x")
    recs = service.handle_new_file(str(f))
    assert recs and recs[0].status == Status.DONE and (docs / "new.pdf").exists()

    rule.confirm_each = True
    service.save_rule(rule)
    g = dl / "second.pdf"
    g.write_text("y")
    assert service.handle_new_file(str(g)) == []
    assert len(service.approvals) == 1
    service.approve(service.approvals[0].id)
    assert (docs / "second.pdf").exists()


def test_manual_rule_not_triggered_by_watcher(service, sandbox):
    dl, docs = sandbox
    service.save_rule(make_rule(dl, docs, trigger=Trigger.MANUAL))
    (dl / "a.pdf").write_text("x")
    assert service.handle_new_file(str(dl / "a.pdf")) == []


def test_real_watcher_end_to_end(service, sandbox):
    dl, docs = sandbox
    service.save_rule(make_rule(dl, docs))
    assert service.start_watching()
    time.sleep(0.5)
    (dl / "live.pdf").write_text("hello")
    deadline = time.time() + 10
    while time.time() < deadline and not (docs / "live.pdf").exists():
        time.sleep(0.2)
    assert (docs / "live.pdf").exists()
    stats = service.store.stats()
    assert stats["done_24h"] == 1
