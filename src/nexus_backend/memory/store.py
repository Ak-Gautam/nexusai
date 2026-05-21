from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from dataclasses import asdict
from datetime import UTC
from datetime import datetime
from pathlib import Path
import json
import uuid


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
    """
    CREATE TABLE IF NOT EXISTS conversation_thread (
        id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        title TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conversation_message (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        thread_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        FOREIGN KEY(thread_id) REFERENCES conversation_thread(id)
    )
    """,
)


@dataclass(frozen=True)
class DatabaseStatus:
    path: Path
    ready: bool


@dataclass(frozen=True)
class ConversationThread:
    id: str
    created_at: str
    updated_at: str
    title: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class ConversationMessage:
    id: int
    thread_id: str
    created_at: str
    role: str
    content: str
    metadata: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


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


def create_thread(database_path: Path, title: str = "Nexus thread") -> ConversationThread:
    now = _timestamp()
    thread = ConversationThread(id=str(uuid.uuid4()), created_at=now, updated_at=now, title=title)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO conversation_thread(id, created_at, updated_at, title) VALUES (?, ?, ?, ?)",
            (thread.id, thread.created_at, thread.updated_at, thread.title),
        )
        connection.commit()
    return thread


def get_thread(database_path: Path, thread_id: str) -> ConversationThread | None:
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT id, created_at, updated_at, title FROM conversation_thread WHERE id = ?",
            (thread_id,),
        ).fetchone()
    if row is None:
        return None
    return ConversationThread(id=row[0], created_at=row[1], updated_at=row[2], title=row[3])


def list_threads(database_path: Path, limit: int = 50) -> list[ConversationThread]:
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT id, created_at, updated_at, title
            FROM conversation_thread
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [ConversationThread(id=row[0], created_at=row[1], updated_at=row[2], title=row[3]) for row in rows]


def append_message(
    database_path: Path,
    thread_id: str,
    role: str,
    content: str,
    metadata: dict[str, object] | None = None,
) -> ConversationMessage:
    now = _timestamp()
    metadata_json = json.dumps(metadata or {}, ensure_ascii=True)
    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO conversation_message(thread_id, created_at, role, content, metadata_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (thread_id, now, role, content, metadata_json),
        )
        connection.execute(
            "UPDATE conversation_thread SET updated_at = ? WHERE id = ?",
            (now, thread_id),
        )
        connection.commit()
        message_id = int(cursor.lastrowid)
    return ConversationMessage(
        id=message_id,
        thread_id=thread_id,
        created_at=now,
        role=role,
        content=content,
        metadata=json.loads(metadata_json),
    )


def get_messages(database_path: Path, thread_id: str, limit: int = 40) -> list[ConversationMessage]:
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT id, thread_id, created_at, role, content, metadata_json
            FROM conversation_message
            WHERE thread_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (thread_id, limit),
        ).fetchall()
    messages = [
        ConversationMessage(
            id=row[0],
            thread_id=row[1],
            created_at=row[2],
            role=row[3],
            content=row[4],
            metadata=_parse_metadata(row[5]),
        )
        for row in rows
    ]
    return list(reversed(messages))


def _write_row(database_path: Path, statement: str, values: tuple[str, ...]) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute(statement, values)
        connection.commit()


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _parse_metadata(value: str) -> dict[str, object]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
