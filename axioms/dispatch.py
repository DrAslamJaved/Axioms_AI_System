"""Durable, local-only dispatch records for approved Axioms tasks.

This is a queue foundation, not an autonomous worker. A worker must explicitly
claim a job, run only an already-approved local task, and report success or a
bounded retryable failure. The queue has no external-action capability.
"""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import uuid4


class DispatchStatus(StrEnum):
    QUEUED = "queued"
    CLAIMED = "claimed"
    SUCCEEDED = "succeeded"
    DEAD_LETTER = "dead_letter"


class DispatchStateError(RuntimeError):
    """Raised when a durable dispatch transition is invalid."""


@dataclass(frozen=True, slots=True)
class DispatchJob:
    job_id: str
    task_id: str
    idempotency_key: str
    status: DispatchStatus
    attempts: int
    max_attempts: int
    worker_id: str | None
    last_error: str | None
    created_at: str
    updated_at: str

    def to_dict(self) -> dict:
        return asdict(self)


class DurableDispatchStore:
    """SQLite-backed job state with atomic claim, bounded retry, and dead-letter states."""

    def __init__(self, path: Path) -> None:
        self.path = path
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS dispatch_jobs (
                    job_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL,
                    max_attempts INTEGER NOT NULL,
                    worker_id TEXT,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, check_same_thread=False, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def enqueue(self, task_id: str, *, idempotency_key: str, max_attempts: int = 2) -> DispatchJob:
        key = idempotency_key.strip()
        if not key:
            raise ValueError("An idempotency key is required.")
        if not 1 <= max_attempts <= 3:
            raise ValueError("max_attempts must be between 1 and 3.")
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT * FROM dispatch_jobs WHERE idempotency_key = ?", (key,)
            ).fetchone()
            if existing is not None:
                job = _job_from_row(existing)
                if job.task_id != task_id:
                    raise DispatchStateError("The idempotency key is already bound to a different task.")
                return job
            now = _now()
            job = DispatchJob(
                job_id=f"job_{uuid4().hex[:12]}",
                task_id=task_id,
                idempotency_key=key,
                status=DispatchStatus.QUEUED,
                attempts=0,
                max_attempts=max_attempts,
                worker_id=None,
                last_error=None,
                created_at=now,
                updated_at=now,
            )
            connection.execute(
                """
                INSERT INTO dispatch_jobs (
                    job_id, task_id, idempotency_key, status, attempts, max_attempts,
                    worker_id, last_error, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.job_id,
                    job.task_id,
                    job.idempotency_key,
                    job.status.value,
                    job.attempts,
                    job.max_attempts,
                    job.worker_id,
                    job.last_error,
                    job.created_at,
                    job.updated_at,
                ),
            )
        return job

    def get(self, job_id: str) -> DispatchJob | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM dispatch_jobs WHERE job_id = ?", (job_id,)).fetchone()
        return _job_from_row(row) if row is not None else None

    def claim_next(self, worker_id: str) -> DispatchJob | None:
        worker = worker_id.strip()
        if not worker:
            raise ValueError("A worker ID is required.")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM dispatch_jobs WHERE status = ? ORDER BY created_at, job_id LIMIT 1",
                (DispatchStatus.QUEUED.value,),
            ).fetchone()
            if row is None:
                return None
            job = _job_from_row(row)
            now = _now()
            connection.execute(
                """
                UPDATE dispatch_jobs
                SET status = ?, attempts = ?, worker_id = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (DispatchStatus.CLAIMED.value, job.attempts + 1, worker, now, job.job_id),
            )
        return self.get(job.job_id)

    def finish(self, job_id: str, *, worker_id: str, succeeded: bool, error: str | None = None) -> DispatchJob:
        worker = worker_id.strip()
        if not worker:
            raise ValueError("A worker ID is required.")
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM dispatch_jobs WHERE job_id = ?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(job_id)
            job = _job_from_row(row)
            if job.status is not DispatchStatus.CLAIMED:
                raise DispatchStateError(f"Job {job_id} is not claimed.")
            if job.worker_id != worker:
                raise DispatchStateError(f"Job {job_id} is claimed by a different worker.")
            if succeeded:
                status = DispatchStatus.SUCCEEDED
                last_error = None
            else:
                status = DispatchStatus.QUEUED if job.attempts < job.max_attempts else DispatchStatus.DEAD_LETTER
                last_error = (error or "Worker reported a failed local execution.").strip()
            now = _now()
            connection.execute(
                """
                UPDATE dispatch_jobs
                SET status = ?, worker_id = NULL, last_error = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (status.value, last_error, now, job_id),
            )
        result = self.get(job_id)
        assert result is not None
        return result


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _job_from_row(row: sqlite3.Row) -> DispatchJob:
    return DispatchJob(
        job_id=row["job_id"],
        task_id=row["task_id"],
        idempotency_key=row["idempotency_key"],
        status=DispatchStatus(row["status"]),
        attempts=row["attempts"],
        max_attempts=row["max_attempts"],
        worker_id=row["worker_id"],
        last_error=row["last_error"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
