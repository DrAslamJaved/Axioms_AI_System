from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from axioms.episodic_memory import EpisodicMemoryStore, MemoryDecision, MemoryProposal


def _proposal() -> MemoryProposal:
    return MemoryProposal(
        task_id="task_123",
        summary="Completed task: Prepare a spectral graph theory lecture | Agents: lecture_design",
        tags=("lecture_design",),
    )


def test_memory_is_unavailable_until_an_explicit_owner_approval(tmp_path: Path) -> None:
    store = EpisodicMemoryStore(tmp_path / "memory.sqlite3")
    pending = store.propose(_proposal())
    assert store.search("spectral") == []

    store.decide(
        pending["proposal_id"],
        MemoryDecision.APPROVE,
        "Dr Aslam",
        "Reusable context",
        retention_days=14,
    )
    recalled = store.search("spectral")
    assert recalled[0]["task_id"] == "task_123"
    assert recalled[0]["approved_by"] == "Dr Aslam"
    assert recalled[0]["retention_days"] == 14
    assert recalled[0]["provenance"]["source_task_id"] == "task_123"
    assert "content" not in recalled[0]


def test_expired_memory_is_removed_and_retains_only_minimal_lifecycle_evidence(tmp_path: Path) -> None:
    now = [datetime(2026, 10, 3, tzinfo=UTC)]
    store = EpisodicMemoryStore(tmp_path / "memory.sqlite3", now=lambda: now[0])
    pending = store.propose(_proposal())
    store.decide(pending["proposal_id"], MemoryDecision.APPROVE, "Dr Aslam", retention_days=1)
    memory_id = store.search("spectral")[0]["memory_id"]

    now[0] += timedelta(days=2)
    assert store.search("spectral") == []
    audit = store.audit(memory_id)
    assert audit["state"] == "expired"
    assert audit["event"]["task_id"] == "task_123"
    assert "summary" not in audit["event"]


def test_deletion_audit_preserves_provenance_without_memory_content(tmp_path: Path) -> None:
    store = EpisodicMemoryStore(tmp_path / "memory.sqlite3")
    pending = store.propose(_proposal())
    store.decide(pending["proposal_id"], MemoryDecision.APPROVE, "Dr Aslam")
    memory_id = store.search("spectral")[0]["memory_id"]

    store.delete(memory_id, "Dr Aslam", "No longer needed")
    audit = store.audit(memory_id)
    assert audit["state"] == "deleted"
    assert audit["event"]["proposal_id"] == pending["proposal_id"]
    assert "summary" not in audit["event"]


def test_rejected_memory_proposal_never_becomes_retrievable(tmp_path: Path) -> None:
    store = EpisodicMemoryStore(tmp_path / "memory.sqlite3")
    pending = store.propose(_proposal())
    store.decide(pending["proposal_id"], MemoryDecision.REJECT, "Dr Aslam")
    assert store.search("spectral") == []


def test_memory_rejects_sensitive_text_and_invalid_recall_queries(tmp_path: Path) -> None:
    store = EpisodicMemoryStore(tmp_path / "memory.sqlite3")
    with pytest.raises(ValueError, match="student"):
        store.propose(
            MemoryProposal(
                task_id="task_sensitive",
                summary="Completed task: Process student grades",
                tags=("assessment_design",),
            )
        )
    with pytest.raises(ValueError, match="at least 3"):
        store.search("AI")
    pending = store.propose(_proposal())
    with pytest.raises(ValueError, match="between 1 and 365"):
        store.decide(pending["proposal_id"], MemoryDecision.APPROVE, "Dr Aslam", retention_days=366)
