from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from axioms.models import TaskRecord


def database_path() -> Path:
    url = os.getenv("AXIOMS_DATABASE_URL", "sqlite:///data/axioms.sqlite3")
    if not url.startswith("sqlite:///"):
        raise ValueError("The Foundation MVP supports only sqlite:/// database URLs.")
    path = Path(url.removeprefix("sqlite:///"))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


class TaskStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or database_path()
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS tasks (task_id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )

    def _connect(self) -> sqlite3.Connection:
        # check_same_thread=False lets the connection be used across the ASGI
        # threadpool; WAL + a busy timeout keep concurrent readers/writers from
        # failing with "database is locked" under real load.
        connection = sqlite3.connect(self.path, check_same_thread=False, timeout=5.0)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def save(self, record: TaskRecord) -> None:
        payload = json.dumps(record.to_dict())
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO tasks (task_id, payload) VALUES (?, ?)",
                (record.task_id, payload),
            )

    def save_if_status(self, record: TaskRecord, expected_status: str) -> bool:
        """Persist a record only when its stored lifecycle status has not changed.

        This small compare-and-swap primitive prevents a running executor from
        overwriting a cancellation request made at a graph-layer checkpoint.
        """
        payload = json.dumps(record.to_dict())
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT payload FROM tasks WHERE task_id = ?", (record.task_id,)
            ).fetchone()
            if row is None or json.loads(row[0]).get("status") != expected_status:
                return False
            connection.execute("UPDATE tasks SET payload = ? WHERE task_id = ?", (payload, record.task_id))
        return True

    def get(self, task_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        return json.loads(row[0]) if row else None
