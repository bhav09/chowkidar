"""SQLite registry for model deprecation data, scan results, and notifications."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..config import CHOWKIDAR_HOME


@dataclass
class ModelRecord:
    id: str
    provider: str
    aliases: list[str]
    sunset_date: str | None
    replacement: str | None
    replacement_confidence: str
    breaking_changes: bool
    source_url: str | None
    last_checked_at: str | None
    created_at: str | None


@dataclass
class ScanRecord:
    id: int
    project_path: str
    file_path: str
    variable_name: str | None
    model_value: str
    model_id: str | None
    source_type: str
    last_scanned_at: str | None


class Registry:
    """Manages the local SQLite deprecation registry."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or (CHOWKIDAR_HOME / "registry.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def init_db(self) -> None:
        schema_path = Path(__file__).parent / "schema.sql"
        schema = schema_path.read_text()
        self.conn.executescript(schema)
        self.conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # --- Models ---

    def upsert_model(
        self,
        model_id: str,
        provider: str,
        aliases: list[str] | None = None,
        sunset_date: str | None = None,
        replacement: str | None = None,
        replacement_confidence: str = "medium",
        breaking_changes: bool = False,
        source_url: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        self.conn.execute(
            """INSERT INTO models (id, provider, aliases, sunset_date, replacement,
               replacement_confidence, breaking_changes, source_url, last_checked_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 sunset_date = COALESCE(excluded.sunset_date, models.sunset_date),
                 replacement = COALESCE(excluded.replacement, models.replacement),
                 replacement_confidence = excluded.replacement_confidence,
                 breaking_changes = excluded.breaking_changes,
                 source_url = COALESCE(excluded.source_url, models.source_url),
                 last_checked_at = excluded.last_checked_at,
                 aliases = excluded.aliases
            """,
            (
                model_id, provider, json.dumps(aliases or []),
                sunset_date, replacement, replacement_confidence,
                int(breaking_changes), source_url, now,
            ),
        )
        self.conn.commit()

    def get_model(self, model_id: str) -> ModelRecord | None:
        row = self.conn.execute("SELECT * FROM models WHERE id = ?", (model_id,)).fetchone()
        if row is None:
            alias_row = self.conn.execute(
                "SELECT * FROM models WHERE aliases LIKE ?", (f'%"{model_id}"%',)
            ).fetchone()
            if alias_row is None:
                return None
            row = alias_row
        return self._row_to_model(row)

    def get_deprecated_models(self) -> list[ModelRecord]:
        rows = self.conn.execute(
            "SELECT * FROM models WHERE sunset_date IS NOT NULL ORDER BY sunset_date ASC"
        ).fetchall()
        return [self._row_to_model(r) for r in rows]

    def get_models_by_provider(self, provider: str) -> list[ModelRecord]:
        rows = self.conn.execute(
            "SELECT * FROM models WHERE provider = ?", (provider,)
        ).fetchall()
        return [self._row_to_model(r) for r in rows]

    def get_all_models(self) -> list[ModelRecord]:
        rows = self.conn.execute("SELECT * FROM models ORDER BY provider, id").fetchall()
        return [self._row_to_model(r) for r in rows]

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> ModelRecord:
        return ModelRecord(
            id=row["id"],
            provider=row["provider"],
            aliases=json.loads(row["aliases"]) if row["aliases"] else [],
            sunset_date=row["sunset_date"],
            replacement=row["replacement"],
            replacement_confidence=row["replacement_confidence"],
            breaking_changes=bool(row["breaking_changes"]),
            source_url=row["source_url"],
            last_checked_at=row["last_checked_at"],
            created_at=row["created_at"],
        )

    # --- Scan results ---

    def save_scan_results(self, project_path: str, entries: list[dict[str, str]]) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        self.conn.execute("DELETE FROM scan_results WHERE project_path = ?", (project_path,))
        for entry in entries:
            self.conn.execute(
                """INSERT INTO scan_results
                   (project_path, file_path, variable_name, model_value, model_id, source_type, last_scanned_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    project_path, entry["file"], entry["variable"],
                    entry["model"], entry["canonical"], entry.get("source_type", "env"), now,
                ),
            )
        self.conn.commit()

    def get_scan_results(self, project_path: str) -> list[ScanRecord]:
        rows = self.conn.execute(
            "SELECT * FROM scan_results WHERE project_path = ?", (project_path,)
        ).fetchall()
        return [
            ScanRecord(
                id=r["id"], project_path=r["project_path"], file_path=r["file_path"],
                variable_name=r["variable_name"], model_value=r["model_value"],
                model_id=r["model_id"], source_type=r["source_type"],
                last_scanned_at=r["last_scanned_at"],
            )
            for r in rows
        ]

    # --- Notifications ---

    def log_notification(self, project_path: str, model_id: str, threshold: str) -> None:
        self.conn.execute(
            "INSERT INTO notification_log (project_path, model_id, threshold) VALUES (?, ?, ?)",
            (project_path, model_id, threshold),
        )
        self.conn.commit()

    def is_recently_notified(
        self, project_path: str, model_id: str, threshold: str, cooldown_hours: int = 24
    ) -> bool:
        cutoff = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=cooldown_hours)).isoformat()
        row = self.conn.execute(
            """SELECT 1 FROM notification_log
               WHERE project_path = ? AND model_id = ? AND threshold = ? AND notified_at > ?
               LIMIT 1""",
            (project_path, model_id, threshold, cutoff),
        ).fetchone()
        return row is not None

    def set_snooze(self, model_id: str, days: int) -> None:
        until = (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=days)).isoformat()
        self.conn.execute(
            """INSERT INTO notification_log (project_path, model_id, threshold, snoozed_until)
               VALUES ('*', ?, 'snooze', ?)""",
            (model_id, until),
        )
        self.conn.commit()

    def is_snoozed(self, model_id: str) -> bool:
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        row = self.conn.execute(
            """SELECT 1 FROM notification_log
               WHERE model_id = ? AND threshold = 'snooze' AND snoozed_until > ?
               LIMIT 1""",
            (model_id, now),
        ).fetchone()
        return row is not None

    # --- Pinning ---

    def pin_model(self, model_id: str, reason: str | None = None) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO pinned_models (model_id, reason) VALUES (?, ?)",
            (model_id, reason),
        )
        self.conn.commit()

    def unpin_model(self, model_id: str) -> None:
        self.conn.execute("DELETE FROM pinned_models WHERE model_id = ?", (model_id,))
        self.conn.commit()

    def is_pinned(self, model_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM pinned_models WHERE model_id = ?", (model_id,)
        ).fetchone()
        return row is not None

    def get_pinned_models(self) -> list[tuple[str, str | None]]:
        rows = self.conn.execute("SELECT model_id, reason FROM pinned_models").fetchall()
        return [(r["model_id"], r["reason"]) for r in rows]

    # --- Watched projects ---

    def watch_project(self, project_path: str) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO watched_projects (project_path) VALUES (?)",
            (project_path,),
        )
        self.conn.commit()

    def unwatch_project(self, project_path: str) -> None:
        self.conn.execute(
            "DELETE FROM watched_projects WHERE project_path = ?", (project_path,)
        )
        self.conn.commit()

    def get_watched_projects(self) -> list[str]:
        rows = self.conn.execute("SELECT project_path FROM watched_projects").fetchall()
        return [r["project_path"] for r in rows]

    def update_watch_timestamp(self, project_path: str) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        self.conn.execute(
            "UPDATE watched_projects SET last_scanned_at = ? WHERE project_path = ?",
            (now, project_path),
        )
        self.conn.commit()

    # --- Migration notes ---

    def add_migration_note(
        self, model_id: str, note_type: str, content: str, severity: str = "info",
    ) -> None:
        self.conn.execute(
            "INSERT INTO migration_notes (model_id, note_type, content, severity) VALUES (?, ?, ?, ?)",
            (model_id, note_type, content, severity),
        )
        self.conn.commit()

    def get_migration_notes(self, model_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT note_type, content, severity FROM migration_notes WHERE model_id = ? ORDER BY created_at DESC",
            (model_id,),
        ).fetchall()
        return [{"note_type": r["note_type"], "content": r["content"], "severity": r["severity"]} for r in rows]

    # --- Meta ---

    def last_sync_time(self) -> str | None:
        row = self.conn.execute(
            "SELECT MAX(last_checked_at) as t FROM models"
        ).fetchone()
        return row["t"] if row else None
