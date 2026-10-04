"""Consent-first Personal Knowledge Base with proposal-only updates."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from axioms.models import AgentName
from axioms.store import database_path


class PreferenceCategory(StrEnum):
    TEACHING_STYLE = "teaching_style"
    RESEARCH_VOICE = "research_voice"
    CONTENT_BRAND = "content_brand"
    RECURRING_TEMPLATE = "recurring_template"


class ProposalDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


SENSITIVE_TERMS = {"student", "grade", "marks", "roll number", "cnic", "phone", "email address"}


def _reject_sensitive_text(*values: str) -> None:
    text = " ".join(values).casefold()
    if any(term in text for term in SENSITIVE_TERMS):
        raise ValueError("Personal KB records must not contain student or personal-identifying information.")


@dataclass(frozen=True, slots=True)
class FeedbackRecord:
    agent: AgentName
    artifact_reference: str
    rating: int
    comment: str | None = None
    feedback_id: str = ""
    created_at: str = ""

    def validate(self) -> None:
        if not self.artifact_reference.strip():
            raise ValueError("Feedback needs an artifact reference.")
        if not 1 <= self.rating <= 5:
            raise ValueError("Feedback rating must be between 1 and 5.")
        _reject_sensitive_text(self.artifact_reference, self.comment or "")


@dataclass(frozen=True, slots=True)
class PreferenceProposal:
    category: PreferenceCategory
    preference_key: str
    preference_value: str
    rationale: str
    feedback_id: str | None = None
    agent_types: tuple[AgentName, ...] = ()
    proposal_id: str = ""
    created_at: str = ""
    decision: ProposalDecision | None = None
    decision_note: str | None = None

    def validate(self) -> None:
        if not self.preference_key.strip() or not self.preference_value.strip() or not self.rationale.strip():
            raise ValueError("Preference key, value, and rationale are required.")
        _reject_sensitive_text(self.preference_key, self.preference_value, self.rationale)
        if len(set(self.agent_types)) != len(self.agent_types):
            raise ValueError("Agent targets cannot contain duplicates.")
        if AgentName.CORE in self.agent_types:
            raise ValueError("Personal KB preferences can target specialist agents only.")


class PersonalKnowledgeStore:
    """SQLite-backed explicit-feedback and approval ledger; no implicit learning is performed."""

    def __init__(self, path=None) -> None:
        self.path = path or database_path()
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS kb_feedback (feedback_id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS kb_proposals (proposal_id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS kb_entries (entry_key TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def record_feedback(self, feedback: FeedbackRecord) -> dict:
        feedback.validate()
        saved = FeedbackRecord(
            **{
                **asdict(feedback),
                "feedback_id": feedback.feedback_id or f"feedback_{uuid4().hex[:12]}",
                "created_at": feedback.created_at or datetime.now(UTC).isoformat(),
            }
        )
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO kb_feedback (feedback_id, payload) VALUES (?, ?)",
                (saved.feedback_id, json.dumps(asdict(saved))),
            )
        return asdict(saved)

    def propose(self, proposal: PreferenceProposal) -> dict:
        proposal.validate()
        saved = PreferenceProposal(
            **{
                **asdict(proposal),
                "proposal_id": proposal.proposal_id or f"kbp_{uuid4().hex[:12]}",
                "created_at": proposal.created_at or datetime.now(UTC).isoformat(),
                "decision": None,
                "decision_note": None,
            }
        )
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO kb_proposals (proposal_id, payload) VALUES (?, ?)",
                (saved.proposal_id, json.dumps(asdict(saved))),
            )
        return asdict(saved)

    def decide(self, proposal_id: str, decision: ProposalDecision, note: str | None = None) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM kb_proposals WHERE proposal_id = ?", (proposal_id,)
            ).fetchone()
            if row is None:
                raise KeyError(proposal_id)
            payload = json.loads(row[0])
            if payload["decision"] is not None:
                raise ValueError("A Personal KB proposal can be decided only once.")
            payload["decision"] = decision.value
            payload["decision_note"] = note
            connection.execute(
                "UPDATE kb_proposals SET payload = ? WHERE proposal_id = ?",
                (json.dumps(payload), proposal_id),
            )
            if decision is ProposalDecision.APPROVE:
                entry_key = f"{payload['category']}:{payload['preference_key']}"
                entry = {
                    "category": payload["category"],
                    "preference_key": payload["preference_key"],
                    "preference_value": payload["preference_value"],
                    "proposal_id": proposal_id,
                    "approved_at": datetime.now(UTC).isoformat(),
                    "agent_types": [str(agent) for agent in payload.get("agent_types", ())],
                }
                connection.execute(
                    "INSERT OR REPLACE INTO kb_entries (entry_key, payload) VALUES (?, ?)",
                    (entry_key, json.dumps(entry)),
                )
        return payload

    def entries(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute("SELECT payload FROM kb_entries ORDER BY entry_key").fetchall()
        return [json.loads(row[0]) for row in rows]

    def entries_for_agent(self, agent: AgentName) -> list[dict]:
        """Return approved, explicitly scoped entries; legacy unscoped entries remain available to all specialists."""
        entries: list[dict] = []
        for entry in self.entries():
            targets = entry.get("agent_types", [])
            if not targets or agent.value in targets:
                entries.append(entry)
        return entries
