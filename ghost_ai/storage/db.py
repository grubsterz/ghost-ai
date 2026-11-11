"""Local SQLite storage: rules, action journal, quick actions, allowed folders, settings."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

from ..domain.models import ActionRecord, ActionType, Rule, Status

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS rules (
    id TEXT PRIMARY KEY, data TEXT NOT NULL, position INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL, batch_id TEXT NOT NULL, type TEXT NOT NULL,
    src TEXT NOT NULL, dst TEXT NOT NULL, status TEXT NOT NULL,
    rule_id TEXT NOT NULL DEFAULT '', rule_name TEXT NOT NULL DEFAULT '', message TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS journal_ts ON journal(ts);
CREATE INDEX IF NOT EXISTS journal_batch ON journal(batch_id);
CREATE TABLE IF NOT EXISTS quick_actions (id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS folders (path TEXT PRIMARY KEY, added TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS commands (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, command TEXT NOT NULL, status TEXT NOT NULL,
    exit_code INTEGER, output TEXT NOT NULL DEFAULT '', request TEXT NOT NULL DEFAULT ''
);
"""


class Store:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.executescript(SCHEMA)
            self._db.execute("INSERT OR IGNORE INTO meta VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
            self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def _exec(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._db.execute(sql, params)
            self._db.commit()
            return cur

    def _query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._db.execute(sql, params).fetchall()

    # ---- rules ------------------------------------------------------------
    def save_rule(self, rule: Rule) -> None:
        pos = self._query("SELECT position FROM rules WHERE id=?", (rule.id,))
        position = pos[0]["position"] if pos else (self._query("SELECT COALESCE(MAX(position),0)+1 p FROM rules")[0]["p"])
        self._exec("INSERT OR REPLACE INTO rules (id, data, position) VALUES (?,?,?)",
                   (rule.id, json.dumps(rule.to_dict()), position))

    def delete_rule(self, rule_id: str) -> None:
        self._exec("DELETE FROM rules WHERE id=?", (rule_id,))

    def get_rule(self, rule_id: str) -> Rule | None:
        rows = self._query("SELECT data FROM rules WHERE id=?", (rule_id,))
        return Rule.from_dict(json.loads(rows[0]["data"])) if rows else None

    def list_rules(self) -> list[Rule]:
        return [Rule.from_dict(json.loads(r["data"])) for r in self._query("SELECT data FROM rules ORDER BY position")]

    # ---- journal ----------------------------------------------------------
    def add_record(self, rec: ActionRecord) -> ActionRecord:
        cur = self._exec(
            "INSERT INTO journal (ts,batch_id,type,src,dst,status,rule_id,rule_name,message) VALUES (?,?,?,?,?,?,?,?,?)",
            (rec.ts, rec.batch_id, rec.type.value, rec.src, rec.dst, rec.status.value, rec.rule_id,
             rec.rule_name, rec.message),
        )
        rec.id = cur.lastrowid
        return rec

    def set_status(self, record_id: int, status: Status, message: str = "") -> None:
        self._exec("UPDATE journal SET status=?, message=? WHERE id=?", (status.value, message, record_id))

    @staticmethod
    def _row_to_record(r: sqlite3.Row) -> ActionRecord:
        return ActionRecord(id=r["id"], ts=r["ts"], batch_id=r["batch_id"], type=ActionType(r["type"]),
                            src=r["src"], dst=r["dst"], status=Status(r["status"]), rule_id=r["rule_id"],
                            rule_name=r["rule_name"], message=r["message"])

    def records(self, limit: int = 200, include_dry_run: bool = True) -> list[ActionRecord]:
        where = "" if include_dry_run else "WHERE status != 'dry_run'"
        rows = self._query(f"SELECT * FROM journal {where} ORDER BY id DESC LIMIT ?", (limit,))
        return [self._row_to_record(r) for r in rows]

    def record(self, record_id: int) -> ActionRecord | None:
        rows = self._query("SELECT * FROM journal WHERE id=?", (record_id,))
        return self._row_to_record(rows[0]) if rows else None

    def batch(self, batch_id: str) -> list[ActionRecord]:
        rows = self._query("SELECT * FROM journal WHERE batch_id=? ORDER BY id", (batch_id,))
        return [self._row_to_record(r) for r in rows]

    def last_undoable_batch(self) -> str | None:
        rows = self._query("SELECT batch_id FROM journal WHERE status='done' ORDER BY id DESC LIMIT 1")
        return rows[0]["batch_id"] if rows else None

    def stats(self) -> dict[str, int]:
        since = (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")
        week = (datetime.now() - timedelta(days=7)).isoformat(timespec="seconds")

        def count(sql: str, params: tuple = ()) -> int:
            return int(self._query(sql, params)[0][0])

        return {
            "done_24h": count("SELECT COUNT(*) FROM journal WHERE status='done' AND ts>=?", (since,)),
            "done_7d": count("SELECT COUNT(*) FROM journal WHERE status='done' AND ts>=?", (week,)),
            "done_total": count("SELECT COUNT(*) FROM journal WHERE status IN ('done','undone')"),
            "undone_total": count("SELECT COUNT(*) FROM journal WHERE status='undone'"),
            "failed_total": count("SELECT COUNT(*) FROM journal WHERE status IN ('failed','blocked')"),
        }

    def clear_journal(self) -> None:
        self._exec("DELETE FROM journal")

    # ---- quick actions ----------------------------------------------------
    def save_quick_action(self, qa_id: str, data: dict[str, Any]) -> None:
        self._exec("INSERT OR REPLACE INTO quick_actions (id, data) VALUES (?,?)", (qa_id, json.dumps(data)))

    def delete_quick_action(self, qa_id: str) -> None:
        self._exec("DELETE FROM quick_actions WHERE id=?", (qa_id,))

    def list_quick_actions(self) -> list[dict[str, Any]]:
        return [json.loads(r["data"]) for r in self._query("SELECT data FROM quick_actions ORDER BY rowid")]

    # ---- folders ----------------------------------------------------------
    def add_folder(self, path: str) -> None:
        self._exec("INSERT OR IGNORE INTO folders (path, added) VALUES (?,?)",
                   (path, datetime.now().isoformat(timespec="seconds")))

    def remove_folder(self, path: str) -> None:
        self._exec("DELETE FROM folders WHERE path=?", (path,))

    def folders(self) -> list[str]:
        return [r["path"] for r in self._query("SELECT path FROM folders ORDER BY added")]

    # ---- full-access command log ------------------------------------------
    def add_command(self, command: str, status: str, exit_code: int | None, output: str, request: str = "") -> None:
        self._exec("INSERT INTO commands (ts, command, status, exit_code, output, request) VALUES (?,?,?,?,?,?)",
                   (datetime.now().isoformat(timespec="seconds"), command, status, exit_code, output[-20000:],
                    request[:500]))

    def commands(self, limit: int = 200) -> list[dict[str, Any]]:
        rows = self._query("SELECT * FROM commands ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows]

    # ---- settings ---------------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        rows = self._query("SELECT value FROM settings WHERE key=?", (key,))
        return json.loads(rows[0]["value"]) if rows else default

    def set(self, key: str, value: Any) -> None:
        self._exec("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, json.dumps(value)))

    def iter_settings(self) -> Iterator[tuple[str, Any]]:
        for r in self._query("SELECT key, value FROM settings"):
            yield r["key"], json.loads(r["value"])
