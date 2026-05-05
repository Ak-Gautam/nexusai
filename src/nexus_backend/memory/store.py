from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from pathlib import Path


SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS app_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        event_type TEXT NOT NULL,
        payload TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS task_run (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        command TEXT NOT NULL,
        status TEXT NOT NULL,
        summary TEXT NOT NULL
    )
    """,
)


@dataclass(frozen=True)
class DatabaseStatus:
    path: Path
    ready: bool


def initialize_database(database_path: Path) -> DatabaseStatus:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)
        connection.commit()
    return DatabaseStatus(path=database_path, ready=True)


def log_event(database_path: Path, event_type: str, payload: str) -> None:
    _write_row(
        database_path=database_path,
        statement="INSERT INTO app_log(created_at, event_type, payload) VALUES (?, ?, ?)",
        values=(_timestamp(), event_type, payload),
    )


def log_task_run(database_path: Path, command: str, status: str, summary: str) -> None:
    _write_row(
        database_path=database_path,
        statement="INSERT INTO task_run(created_at, command, status, summary) VALUES (?, ?, ?, ?)",
        values=(_timestamp(), command, status, summary),
    )


def _write_row(database_path: Path, statement: str, values: tuple[str, ...]) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute(statement, values)
        connection.commit()


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()
