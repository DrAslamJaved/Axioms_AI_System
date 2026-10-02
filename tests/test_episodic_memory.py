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

    store.decide(pending["proposal_id"], MemoryDecision.APPROVE, "Dr Aslam", "Reusable context")
    recalled = store.search("spectral")
    assert recalled[0]["task_id"] == "task_123"
    assert recalled[0]["approved_by"] == "Dr Aslam"
    assert "content" not in recalled[0]


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
