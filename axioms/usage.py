"""Content-free, local accounting for provider-reported LLM token metadata."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from axioms.audit_log import current_request_id
from axioms.store import database_path


class UsageStore:
    """Store content-free provider usage with an optional safe request correlation ID."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or database_path()
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS llm_usage_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recorded_at TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL,
                    request_id TEXT
                )
                """
            )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(llm_usage_events)")}
            if "request_id" not in columns:
                connection.execute("ALTER TABLE llm_usage_events ADD COLUMN request_id TEXT")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, check_same_thread=False, timeout=5.0)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def record(self, *, provider: str, model: str, input_tokens: int, output_tokens: int) -> None:
        """Append provider-reported metadata without prompts, outputs, or prices."""
        if not provider.strip() or not model.strip():
            raise ValueError("Usage events require non-empty provider and model names.")
        if input_tokens < 0 or output_tokens < 0:
            raise ValueError("Usage token counts must be non-negative.")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO llm_usage_events
                (recorded_at, provider, model, input_tokens, output_tokens, request_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(UTC).isoformat(),
                    provider,
                    model,
                    input_tokens,
                    output_tokens,
                    current_request_id(),
                ),
            )

    def summary(self) -> dict:
        """Return aggregate local counts only; no event-level or content-level read API exists."""
        with self._connect() as connection:
            total = connection.execute(
                "SELECT COUNT(*), COALESCE(SUM(input_tokens), 0), COALESCE(SUM(output_tokens), 0) "
                "FROM llm_usage_events"
            ).fetchone()
            rows = connection.execute(
                """
                SELECT provider, model, COUNT(*), SUM(input_tokens), SUM(output_tokens)
                FROM llm_usage_events
                GROUP BY provider, model
                ORDER BY provider ASC, model ASC
                """
            ).fetchall()
        return {
            "request_count": total[0],
            "input_tokens": total[1],
            "output_tokens": total[2],
            "by_provider": [
                {
                    "provider": row[0],
                    "model": row[1],
                    "request_count": row[2],
                    "input_tokens": row[3],
                    "output_tokens": row[4],
                }
                for row in rows
            ],
        }


def record_provider_usage(*, provider: str, model: str, input_tokens: int, output_tokens: int) -> None:
    """Persist only non-zero real-provider usage; unavailable metadata remains absent."""
    if input_tokens == 0 and output_tokens == 0:
        return
    UsageStore().record(
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
