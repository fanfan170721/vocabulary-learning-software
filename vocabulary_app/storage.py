"""Versioned local storage. Every write is committed as one SQLite transaction."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Iterator


SCHEMA_VERSION = 1


class _Connection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise ValueError("The learning archive was created by a newer application version. Upgrade first.")
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if version == 0 and tables:
                if tables != {"records"} or [row[1] for row in connection.execute("PRAGMA table_info(records)")] != ["kind", "id", "data"]:
                    raise ValueError("The old archive structure is incompatible. Keep the original file and export it with the corresponding application version before importing.")
                self.backup("before-schema-1")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS records ("
                "kind TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL, "
                "PRIMARY KEY (kind, id))"
            )
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10, factory=_Connection)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def get(connection: sqlite3.Connection, kind: str, identifier: str):
        row = connection.execute(
            "SELECT data FROM records WHERE kind=? AND id=?", (kind, identifier)
        ).fetchone()
        return json.loads(row[0]) if row else None

    @staticmethod
    def all(connection: sqlite3.Connection, kind: str) -> list[dict]:
        return [json.loads(row[0]) for row in connection.execute(
            "SELECT data FROM records WHERE kind=? ORDER BY rowid", (kind,)
        )]

    @staticmethod
    def put(connection: sqlite3.Connection, kind: str, identifier: str, data: dict):
        connection.execute(
            "INSERT INTO records(kind,id,data) VALUES(?,?,?) "
            "ON CONFLICT(kind,id) DO UPDATE SET data=excluded.data",
            (kind, identifier, json.dumps(data, ensure_ascii=False, allow_nan=False)),
        )

    @staticmethod
    def delete(connection: sqlite3.Connection, kind: str, identifier: str):
        connection.execute("DELETE FROM records WHERE kind=? AND id=?", (kind, identifier))

    def backup(self, label: str = "backup") -> Path:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        target = self.path.parent / "backups" / f"{label}-{stamp}.sqlite3"
        target.parent.mkdir(parents=True, exist_ok=True)
        source = self.connect()
        destination = sqlite3.connect(target)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()
        return target
