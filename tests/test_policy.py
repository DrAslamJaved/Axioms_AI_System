from axioms.models import TaskRequest
from axioms.policy import assess_request


def test_external_post_requires_approval() -> None:
    decision = assess_request(TaskRequest(goal="Post a course announcement on LinkedIn"))
    assert decision.requires_approval
    assert "External" in decision.reason


def test_student_data_requires_approval() -> None:
    decision = assess_request(TaskRequest(goal="Analyse student grade distribution"))
    assert decision.requires_approval
    assert "Sensitive" in decision.reason

