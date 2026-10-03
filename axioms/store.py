from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from axioms.models import TaskRecord, TaskStatus


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

    def list(
        self, status: TaskStatus | str | None = None, *, limit: int = 50, cursor: str | None = None
    ) -> dict:
        """Return a bounded, read-only task page in stable descending task-ID order."""
        if not 1 <= limit <= 200:
            raise ValueError("Task-list limit must be between 1 and 200.")
        normalized_status = TaskStatus(status).value if status is not None else None
        clauses: list[str] = []
        parameters: list[str | int] = []
        if normalized_status is not None:
            clauses.append("json_extract(payload, '$.status') = ?")
            parameters.append(normalized_status)
        if cursor is not None:
            normalized_cursor = cursor.strip()
            if not normalized_cursor:
                raise ValueError("Task-list cursor cannot be blank.")
            clauses.append("task_id < ?")
            parameters.append(normalized_cursor)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        parameters.append(limit + 1)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT task_id, payload FROM tasks"
                f"{where} ORDER BY task_id DESC LIMIT ?",
                parameters,
            ).fetchall()
        page = rows[:limit]
        return {
            "items": [json.loads(row[1]) for row in page],
            "next_cursor": page[-1][0] if len(rows) > limit and page else None,
        }

    def lineage(self, task_id: str) -> dict:
        """Return a read-only revision family without drafts or review notes.

        A lineage is rooted at the earliest available task and includes every
        descendant revision. It is deliberately a metadata view: detailed task
        content remains available only from the individual task record.
        """
        with self._connect() as connection:
            rows = connection.execute("SELECT task_id, payload FROM tasks").fetchall()
        tasks = {row[0]: json.loads(row[1]) for row in rows}
        if task_id not in tasks:
            raise KeyError(task_id)

        root_id = task_id
        ancestors_seen: set[str] = set()
        while parent_id := tasks[root_id].get("revision_of"):
            if root_id in ancestors_seen:
                raise ValueError("Task revision lineage contains a cycle.")
            ancestors_seen.add(root_id)
            if parent_id not in tasks:
                raise ValueError("Task revision lineage has a missing ancestor.")
            root_id = parent_id

        children: dict[str, list[str]] = {}
        for candidate_id, payload in tasks.items():
            if parent_id := payload.get("revision_of"):
                children.setdefault(parent_id, []).append(candidate_id)
        for descendants in children.values():
            descendants.sort(key=lambda candidate_id: _lineage_sort_key(tasks[candidate_id]))

        lineage: list[dict] = []
        pending = [root_id]
        visited: set[str] = set()
        while pending:
            current_id = pending.pop(0)
            if current_id in visited:
                raise ValueError("Task revision lineage contains a cycle.")
            visited.add(current_id)
            lineage.append(_lineage_item(tasks[current_id]))
            pending.extend(children.get(current_id, []))
        return {
            "requested_task_id": task_id,
            "root_task_id": root_id,
            "items": lineage,
        }

    def status_counts(self) -> dict[str, int]:
        """Return aggregate task lifecycle counts without exposing task content."""
        counts = {status.value: 0 for status in TaskStatus}
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT json_extract(payload, '$.status') AS status, COUNT(*) AS count "
                "FROM tasks GROUP BY json_extract(payload, '$.status')"
            ).fetchall()
        for status, count in rows:
            if status in counts:
                counts[status] = count
        return counts


def _lineage_sort_key(payload: dict) -> tuple[str, str]:
    return (payload.get("created_at", ""), payload["task_id"])


def _lineage_item(payload: dict) -> dict:
    """Project only review-queue metadata, never deliverables or reviewer notes."""
    return {
        "task_id": payload["task_id"],
        "revision_of": payload.get("revision_of"),
        "revision_requested_by": payload.get("revision_requested_by"),
        "created_at": payload["created_at"],
        "status": payload["status"],
        "risk_tier": payload.get("risk_tier"),
        "goal": payload["request"]["goal"],
        "reviewed_by": payload.get("reviewed_by"),
    }
