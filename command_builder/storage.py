from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from .models import BackupData, HistoryEntry, ImportMode, ImportResult, Profile, ProfilePayload


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso_now() -> str:
    return utc_now().isoformat()


class Storage:
    def __init__(self, database_path: Path):
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                INSERT OR IGNORE INTO metadata(key, value) VALUES ('schema_version', '1');

                CREATE TABLE IF NOT EXISTS profiles (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    script_path TEXT NOT NULL,
                    prefix TEXT NOT NULL,
                    shell TEXT NOT NULL,
                    arguments_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS history (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    profile_id TEXT,
                    profile_name TEXT NOT NULL,
                    shell TEXT NOT NULL,
                    command TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS history_created_at_idx ON history(created_at DESC);
                CREATE INDEX IF NOT EXISTS history_profile_id_idx ON history(profile_id);
                """
            )
            connection.commit()

    @staticmethod
    def _profile_from_row(row: sqlite3.Row) -> Profile:
        return Profile(
            id=row["id"],
            name=row["name"],
            script_path=row["script_path"],
            prefix=row["prefix"],
            shell=row["shell"],
            arguments=json.loads(row["arguments_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _history_from_row(row: sqlite3.Row) -> HistoryEntry:
        return HistoryEntry(
            id=row["id"],
            created_at=row["created_at"],
            profile_id=row["profile_id"],
            profile_name=row["profile_name"],
            shell=row["shell"],
            command=row["command"],
            snapshot=json.loads(row["snapshot_json"]),
        )

    def list_profiles(self) -> list[Profile]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM profiles ORDER BY updated_at DESC, name COLLATE NOCASE"
            ).fetchall()
        return [self._profile_from_row(row) for row in rows]

    def get_profile(self, profile_id: str) -> Profile | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM profiles WHERE id = ?", (profile_id,)
            ).fetchone()
        return self._profile_from_row(row) if row else None

    def create_profile(self, payload: ProfilePayload) -> Profile:
        profile_id = str(uuid.uuid4())
        now = iso_now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO profiles(
                    id, name, script_path, prefix, shell, arguments_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile_id,
                    payload.name,
                    payload.script_path,
                    payload.prefix.value,
                    payload.shell.value,
                    json.dumps(
                        [item.model_dump(mode="json") for item in payload.arguments],
                        ensure_ascii=False,
                    ),
                    now,
                    now,
                ),
            )
            connection.commit()
        return self.get_profile(profile_id)  # type: ignore[return-value]

    def update_profile(self, profile_id: str, payload: ProfilePayload) -> Profile | None:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE profiles
                SET name = ?, script_path = ?, prefix = ?, shell = ?,
                    arguments_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    payload.name,
                    payload.script_path,
                    payload.prefix.value,
                    payload.shell.value,
                    json.dumps(
                        [item.model_dump(mode="json") for item in payload.arguments],
                        ensure_ascii=False,
                    ),
                    iso_now(),
                    profile_id,
                ),
            )
            connection.commit()
            if cursor.rowcount == 0:
                return None
        return self.get_profile(profile_id)

    def delete_profile(self, profile_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
            connection.commit()
            return cursor.rowcount > 0

    def add_history(self, profile: Profile, command: str) -> HistoryEntry:
        history_id = str(uuid.uuid4())
        created_at = iso_now()
        snapshot = profile.model_dump(mode="json")
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO history(
                    id, created_at, profile_id, profile_name, shell, command, snapshot_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    history_id,
                    created_at,
                    profile.id,
                    profile.name,
                    profile.shell.value,
                    command,
                    json.dumps(snapshot, ensure_ascii=False),
                ),
            )
            connection.commit()
        return self.get_history(history_id)  # type: ignore[return-value]

    def get_history(self, history_id: str) -> HistoryEntry | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM history WHERE id = ?", (history_id,)
            ).fetchone()
        return self._history_from_row(row) if row else None

    def list_history(self, query: str = "", limit: int = 500) -> list[HistoryEntry]:
        with self.connect() as connection:
            if query:
                pattern = f"%{query}%"
                rows = connection.execute(
                    """
                    SELECT * FROM history
                    WHERE profile_name LIKE ? OR command LIKE ?
                    ORDER BY created_at DESC LIMIT ?
                    """,
                    (pattern, pattern, limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM history ORDER BY created_at DESC LIMIT ?", (limit,)
                ).fetchall()
        return [self._history_from_row(row) for row in rows]

    def delete_history(self, history_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute("DELETE FROM history WHERE id = ?", (history_id,))
            connection.commit()
            return cursor.rowcount > 0

    def clear_history(self) -> int:
        with self.connect() as connection:
            cursor = connection.execute("DELETE FROM history")
            connection.commit()
            return cursor.rowcount

    def export_backup(self) -> BackupData:
        return BackupData(
            schema_version=1,
            exported_at=utc_now(),
            profiles=self.list_profiles(),
            history=self.list_history(limit=1_000_000),
        )

    @staticmethod
    def _unique_name(name: str, used_names: set[str]) -> str:
        if name.casefold() not in used_names:
            used_names.add(name.casefold())
            return name
        number = 2
        while True:
            candidate = f"{name}（导入 {number}）"
            if candidate.casefold() not in used_names:
                used_names.add(candidate.casefold())
                return candidate
            number += 1

    def import_backup(self, backup: BackupData, mode: ImportMode) -> ImportResult:
        # Revalidate because callers can mutate an already-created Pydantic model.
        backup = BackupData.model_validate(backup.model_dump(mode="json"))
        with self.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                if mode == ImportMode.REPLACE:
                    connection.execute("DELETE FROM history")
                    connection.execute("DELETE FROM profiles")
                    used_names: set[str] = set()
                    used_profile_ids: set[str] = set()
                    used_history_ids: set[str] = set()
                else:
                    used_names = {
                        row[0].casefold()
                        for row in connection.execute("SELECT name FROM profiles").fetchall()
                    }
                    used_profile_ids = {
                        row[0] for row in connection.execute("SELECT id FROM profiles").fetchall()
                    }
                    used_history_ids = {
                        row[0] for row in connection.execute("SELECT id FROM history").fetchall()
                    }

                profile_id_map: dict[str, str] = {}
                profile_name_map: dict[str, str] = {}
                for profile in backup.profiles:
                    new_id = profile.id
                    if new_id in used_profile_ids:
                        new_id = str(uuid.uuid4())
                    used_profile_ids.add(new_id)
                    profile_id_map[profile.id] = new_id
                    name = self._unique_name(profile.name, used_names)
                    profile_name_map[profile.id] = name
                    connection.execute(
                        """
                        INSERT INTO profiles(
                            id, name, script_path, prefix, shell, arguments_json,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            new_id,
                            name,
                            profile.script_path,
                            profile.prefix.value,
                            profile.shell.value,
                            json.dumps(
                                [item.model_dump(mode="json") for item in profile.arguments],
                                ensure_ascii=False,
                            ),
                            profile.created_at.isoformat(),
                            profile.updated_at.isoformat(),
                        ),
                    )

                for item in backup.history:
                    new_id = item.id
                    if new_id in used_history_ids:
                        new_id = str(uuid.uuid4())
                    used_history_ids.add(new_id)
                    profile_id = profile_id_map.get(item.profile_id or "")
                    snapshot: dict[str, Any] = dict(item.snapshot)
                    if item.profile_id in profile_id_map:
                        snapshot["id"] = profile_id_map[item.profile_id]
                        snapshot["name"] = profile_name_map[item.profile_id]
                    profile_name = profile_name_map.get(
                        item.profile_id or "", item.profile_name
                    )
                    connection.execute(
                        """
                        INSERT INTO history(
                            id, created_at, profile_id, profile_name, shell,
                            command, snapshot_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            new_id,
                            item.created_at.isoformat(),
                            profile_id,
                            profile_name,
                            item.shell.value,
                            item.command,
                            json.dumps(snapshot, ensure_ascii=False),
                        ),
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return ImportResult(
            profiles_imported=len(backup.profiles),
            history_imported=len(backup.history),
        )
