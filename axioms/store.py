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
        return sqlite3.connect(self.path)

    def save(self, record: TaskRecord) -> None:
        payload = json.dumps(record.to_dict())
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO tasks (task_id, payload) VALUES (?, ?)",
                (record.task_id, payload),
            )

    def get(self, task_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        return json.loads(row[0]) if row else None

