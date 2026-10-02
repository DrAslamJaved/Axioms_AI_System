"""Consent-first episodic memory for completed, non-sensitive task summaries."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from axioms.store import database_path


class MemoryDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


SENSITIVE_TERMS = {"student", "grade", "marks", "roll number", "cnic", "phone", "email address"}


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
    """SQLite ledger where memory is unavailable until an owner approves it."""

    def __init__(self, path=None) -> None:
        self.path = path or database_path()
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS episode_memory_proposals "
                "(proposal_id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS episode_memory_entries "
                "(memory_id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
            connection.execute("CREATE TABLE IF NOT EXISTS episode_memory_deletions (memory_id TEXT PRIMARY KEY, payload TEXT NOT NULL)")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def propose(self, proposal: MemoryProposal) -> dict:
        proposal.validate()
        saved = MemoryProposal(
            **{
                **asdict(proposal),
                "proposal_id": proposal.proposal_id or f"memory_{uuid4().hex[:12]}",
                "created_at": proposal.created_at or datetime.now(UTC).isoformat(),
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
        self, proposal_id: str, decision: MemoryDecision, decided_by: str, note: str | None = None
    ) -> dict:
        if not decided_by.strip():
            raise ValueError("An episodic-memory decision needs an identified approver.")
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
            connection.execute(
                "UPDATE episode_memory_proposals SET payload = ? WHERE proposal_id = ?",
                (json.dumps(payload), proposal_id),
            )
            if decision is MemoryDecision.APPROVE:
                entry = {
                    "memory_id": f"episode_{uuid4().hex[:12]}",
                    "task_id": payload["task_id"],
                    "summary": payload["summary"],
                    "tags": payload["tags"],
                    "proposal_id": proposal_id,
                    "approved_at": datetime.now(UTC).isoformat(),
                    "approved_by": decided_by,
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
            row = connection.execute("SELECT payload FROM episode_memory_entries WHERE memory_id = ?", (memory_id,)).fetchone()
            if row is None:
                raise KeyError(memory_id)
            entry = json.loads(row[0])
            deletion = {"memory_id": memory_id, "task_id": entry["task_id"], "deleted_at": datetime.now(UTC).isoformat(), "deleted_by": owner, "note": note}
            connection.execute("INSERT INTO episode_memory_deletions (memory_id, payload) VALUES (?, ?)", (memory_id, json.dumps(deletion)))
            connection.execute("DELETE FROM episode_memory_entries WHERE memory_id = ?", (memory_id,))
        return deletion
