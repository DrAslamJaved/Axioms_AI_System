"""Consent-first episodic memory for completed, non-sensitive task summaries."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import uuid4

from axioms.store import database_path


class MemoryDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


SENSITIVE_TERMS = {"student", "grade", "marks", "roll number", "cnic", "phone", "email address"}
DEFAULT_RETENTION_DAYS = 30
MAX_RETENTION_DAYS = 365


def reject_sensitive_text(*values: str) -> None:
    text = " ".join(values).casefold()
    if any(term in text for term in SENSITIVE_TERMS):
        raise ValueError("Episodic memory must not contain student or personal-identifying information.")


@dataclass(frozen=True, slots=True)
class MemoryProposal:
    task_id: str
    summary: str
    tags: tuple[str, ...]
    proposal_id: str = ""
    created_at: str = ""
    decision: MemoryDecision | None = None
    decision_note: str | None = None
    decided_by: str | None = None

    def validate(self) -> None:
        if not self.task_id.strip() or not self.summary.strip() or not self.tags:
            raise ValueError("A memory proposal needs its task, summary, and at least one tag.")
        reject_sensitive_text(self.summary, *self.tags)


class EpisodicMemoryStore:
    """Consent-first SQLite memory with bounded retention and minimal lifecycle evidence."""

    def __init__(self, path=None, now: Callable[[], datetime] | None = None) -> None:
        self.path = path or database_path()
        self._now = now or (lambda: datetime.now(UTC))
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS episode_memory_proposals "
                "(proposal_id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS episode_memory_entries "
                "(memory_id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS episode_memory_deletions "
                "(memory_id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS episode_memory_expirations "
                "(memory_id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def propose(self, proposal: MemoryProposal) -> dict:
        proposal.validate()
        saved = MemoryProposal(
            **{
                **asdict(proposal),
                "proposal_id": proposal.proposal_id or f"memory_{uuid4().hex[:12]}",
                "created_at": proposal.created_at or self._now().isoformat(),
                "decision": None,
                "decision_note": None,
                "decided_by": None,
            }
        )
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO episode_memory_proposals (proposal_id, payload) VALUES (?, ?)",
                (saved.proposal_id, json.dumps(asdict(saved))),
            )
        return asdict(saved)

    def decide(
        self,
        proposal_id: str,
        decision: MemoryDecision,
        decided_by: str,
        note: str | None = None,
        *,
        retention_days: int = DEFAULT_RETENTION_DAYS,
    ) -> dict:
        if not decided_by.strip():
            raise ValueError("An episodic-memory decision needs an identified approver.")
        _validate_retention_days(retention_days)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM episode_memory_proposals WHERE proposal_id = ?", (proposal_id,)
            ).fetchone()
            if row is None:
                raise KeyError(proposal_id)
            payload = json.loads(row[0])
            if payload["decision"] is not None:
                raise ValueError("An episodic-memory proposal can be decided only once.")
            payload["decision"] = decision.value
            payload["decision_note"] = note
            payload["decided_by"] = decided_by
            payload["retention_days"] = retention_days if decision is MemoryDecision.APPROVE else None
            connection.execute(
                "UPDATE episode_memory_proposals SET payload = ? WHERE proposal_id = ?",
                (json.dumps(payload), proposal_id),
            )
            if decision is MemoryDecision.APPROVE:
                approved_at = self._now()
                entry = {
                    "memory_id": f"episode_{uuid4().hex[:12]}",
                    "task_id": payload["task_id"],
                    "summary": payload["summary"],
                    "tags": payload["tags"],
                    "provenance": {
                        "proposal_id": proposal_id,
                        "source_task_id": payload["task_id"],
                        "approved_at": approved_at.isoformat(),
                        "approved_by": decided_by,
                    },
                    "approved_at": approved_at.isoformat(),
                    "approved_by": decided_by,
                    "retention_days": retention_days,
                    "expires_at": (approved_at + timedelta(days=retention_days)).isoformat(),
                }
                connection.execute(
                    "INSERT INTO episode_memory_entries (memory_id, payload) VALUES (?, ?)",
                    (entry["memory_id"], json.dumps(entry)),
                )
        return payload

    def search(self, query: str, *, limit: int = 5) -> list[dict]:
        normalized = query.strip().casefold()
        if len(normalized) < 3:
            raise ValueError("Memory search requires at least 3 characters.")
        if not 1 <= limit <= 20:
            raise ValueError("Memory-search limit must be between 1 and 20.")
        with self._connect() as connection:
            self._expire_due_entries(connection)
            rows = connection.execute(
                "SELECT payload FROM episode_memory_entries ORDER BY rowid DESC"
            ).fetchall()
        matches = [json.loads(row[0]) for row in rows]
        return [
            item
            for item in matches
            if normalized in item["summary"].casefold() or any(normalized in tag.casefold() for tag in item["tags"])
        ][:limit]

    def delete(self, memory_id: str, deleted_by: str, note: str | None = None) -> dict:
        owner = deleted_by.strip()
        if not owner:
            raise ValueError("An episodic-memory deletion needs an identified owner.")
        with self._connect() as connection:
            self._expire_due_entries(connection)
            row = connection.execute("SELECT payload FROM episode_memory_entries WHERE memory_id = ?", (memory_id,)).fetchone()
            if row is None:
                raise KeyError(memory_id)
            entry = json.loads(row[0])
            deletion = {
                **self._minimal_lifecycle_payload(entry),
                "event": "deleted",
                "deleted_at": self._now().isoformat(),
                "deleted_by": owner,
                "note": note,
            }
            connection.execute("INSERT INTO episode_memory_deletions (memory_id, payload) VALUES (?, ?)", (memory_id, json.dumps(deletion)))
            connection.execute("DELETE FROM episode_memory_entries WHERE memory_id = ?", (memory_id,))
        return deletion

    def audit(self, memory_id: str) -> dict:
        """Return lifecycle provenance without exposing deleted or expired memory content."""
        with self._connect() as connection:
            self._expire_due_entries(connection)
            row = connection.execute(
                "SELECT payload FROM episode_memory_entries WHERE memory_id = ?", (memory_id,)
            ).fetchone()
            if row is not None:
                entry = json.loads(row[0])
                return {
                    "memory_id": memory_id,
                    "state": "active",
                    "provenance": entry["provenance"],
                    "retention_days": entry["retention_days"],
                    "expires_at": entry["expires_at"],
                }
            for table, state in (
                ("episode_memory_deletions", "deleted"),
                ("episode_memory_expirations", "expired"),
            ):
                row = connection.execute(
                    f"SELECT payload FROM {table} WHERE memory_id = ?", (memory_id,)
                ).fetchone()
                if row is not None:
                    return {"memory_id": memory_id, "state": state, "event": json.loads(row[0])}
        raise KeyError(memory_id)

    def _expire_due_entries(self, connection: sqlite3.Connection) -> None:
        """Remove expired entries at read/write boundaries and retain only a minimal tombstone."""
        rows = connection.execute("SELECT memory_id, payload FROM episode_memory_entries").fetchall()
        now = self._now()
        for memory_id, raw_payload in rows:
            entry = json.loads(raw_payload)
            expires_at = _entry_expiry(entry)
            if entry.get("expires_at") != expires_at.isoformat():
                entry["expires_at"] = expires_at.isoformat()
                entry.setdefault("retention_days", DEFAULT_RETENTION_DAYS)
                entry.setdefault(
                    "provenance",
                    {
                        "proposal_id": entry.get("proposal_id"),
                        "source_task_id": entry["task_id"],
                        "approved_at": entry["approved_at"],
                        "approved_by": entry["approved_by"],
                    },
                )
                connection.execute(
                    "UPDATE episode_memory_entries SET payload = ? WHERE memory_id = ?",
                    (json.dumps(entry), memory_id),
                )
            if expires_at <= now:
                expiration = {
                    **self._minimal_lifecycle_payload(entry),
                    "event": "expired",
                    "expired_at": now.isoformat(),
                    "reason": "approved retention period elapsed",
                }
                connection.execute(
                    "INSERT OR IGNORE INTO episode_memory_expirations (memory_id, payload) VALUES (?, ?)",
                    (memory_id, json.dumps(expiration)),
                )
                connection.execute("DELETE FROM episode_memory_entries WHERE memory_id = ?", (memory_id,))

    @staticmethod
    def _minimal_lifecycle_payload(entry: dict) -> dict:
        provenance = entry.get("provenance", {})
        return {
            "memory_id": entry["memory_id"],
            "task_id": entry["task_id"],
            "proposal_id": provenance.get("proposal_id", entry.get("proposal_id")),
            "approved_at": provenance.get("approved_at", entry.get("approved_at")),
            "retention_days": entry.get("retention_days", DEFAULT_RETENTION_DAYS),
            "expires_at": entry.get("expires_at"),
        }


def _validate_retention_days(retention_days: int) -> None:
    if not 1 <= retention_days <= MAX_RETENTION_DAYS:
        raise ValueError(f"Memory retention must be between 1 and {MAX_RETENTION_DAYS} days.")


def _entry_expiry(entry: dict) -> datetime:
    retention_days = entry.get("retention_days", DEFAULT_RETENTION_DAYS)
    _validate_retention_days(retention_days)
    raw_expiry = entry.get("expires_at")
    if raw_expiry:
        return _parse_utc(raw_expiry)
    return _parse_utc(entry["approved_at"]) + timedelta(days=retention_days)


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
