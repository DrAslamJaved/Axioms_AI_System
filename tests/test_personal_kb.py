from pathlib import Path

import pytest

from axioms.models import AgentName
from axioms.personal_kb import (
    FeedbackRecord,
    PersonalKnowledgeStore,
    PreferenceCategory,
    PreferenceProposal,
    ProposalDecision,
)


def proposal() -> PreferenceProposal:
    return PreferenceProposal(
        category=PreferenceCategory.TEACHING_STYLE,
        preference_key="explanation_sequence",
        preference_value="intuition then formal development then application",
        rationale="The owner explicitly requested this sequence.",
    )


def test_kb_proposal_changes_nothing_until_explicit_approval(tmp_path: Path) -> None:
    store = PersonalKnowledgeStore(tmp_path / "kb.sqlite3")
    pending = store.propose(proposal())
    assert pending["decision"] is None
    assert store.entries() == []
    decided = store.decide(pending["proposal_id"], ProposalDecision.APPROVE, "Reviewed")
    assert decided["decision"] == "approve"
    assert store.entries()[0]["preference_value"] == "intuition then formal development then application"


def test_rejected_proposal_never_becomes_a_kb_entry(tmp_path: Path) -> None:
    store = PersonalKnowledgeStore(tmp_path / "kb.sqlite3")
    pending = store.propose(proposal())
    store.decide(pending["proposal_id"], ProposalDecision.REJECT)
    assert store.entries() == []


def test_approved_entries_can_be_scoped_to_specialist_agents(tmp_path: Path) -> None:
    store = PersonalKnowledgeStore(tmp_path / "kb.sqlite3")
    pending = store.propose(
        PreferenceProposal(
            category=PreferenceCategory.TEACHING_STYLE,
            preference_key="example_sequence",
            preference_value="Start with a concrete intuition before notation.",
            rationale="Owner preference for lecture drafts.",
            agent_types=(AgentName.LECTURE,),
        )
    )
    store.decide(pending["proposal_id"], ProposalDecision.APPROVE)
    assert store.entries_for_agent(AgentName.LECTURE)[0]["agent_types"] == [AgentName.LECTURE.value]
    assert store.entries_for_agent(AgentName.WRITING) == []


def test_sensitive_information_is_rejected_from_feedback_and_kb(tmp_path: Path) -> None:
    store = PersonalKnowledgeStore(tmp_path / "kb.sqlite3")
    with pytest.raises(ValueError, match="student"):
        store.record_feedback(FeedbackRecord(AgentName.LECTURE, "student grades", 5))
    with pytest.raises(ValueError, match="student"):
        store.propose(
            PreferenceProposal(
                PreferenceCategory.TEACHING_STYLE,
                "student names",
                "store them",
                "Do not retain students.",
            )
        )
