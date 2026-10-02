from pathlib import Path

import pytest

from axioms.core import AxiomsCore, BlockedApprovalError, TaskStateError
from axioms.models import AgentName, ApprovalDecision, StepKind, TaskRequest, TaskStatus
from axioms.store import TaskStore


def _core(tmp_path: Path) -> AxiomsCore:
    return AxiomsCore(TaskStore(tmp_path / "test.sqlite3"))


def test_task_creation_persists_a_plan_without_executing_agents(tmp_path: Path) -> None:
    record = _core(tmp_path).create_task(TaskRequest(goal="Prepare a graduate lecture on graph theory"))
    assert [task.agent for task in record.subtasks] == [AgentName.LECTURE]
    assert record.status is TaskStatus.PENDING_APPROVAL
    assert record.deliverables == []
    assert [step.kind for step in record.agent_trace] == [StepKind.PLAN_CREATED]


def test_approved_task_executes_then_requires_final_review(tmp_path: Path) -> None:
    core = _core(tmp_path)
    record = core.create_task(TaskRequest(goal="Write a formal research report"))

    approved = core.decide(record.task_id, ApprovalDecision.APPROVE, "Authorised", "Dr Aslam")
    assert approved["status"] == TaskStatus.APPROVED.value
    assert approved["deliverables"] == []

    executed = core.execute(record.task_id)
    assert executed["status"] == TaskStatus.AWAITING_REVIEW.value
    assert executed["deliverables"][0]["status"] == TaskStatus.PENDING_APPROVAL.value
    kinds = [step["kind"] for step in executed["agent_trace"]]
    assert kinds[:3] == [
        StepKind.PLAN_CREATED,
        StepKind.APPROVAL_RECORDED,
        StepKind.EXECUTION_STARTED,
    ]
    assert kinds.count(StepKind.AGENT_DISPATCHED) == len(executed["deliverables"])
    assert kinds.count(StepKind.DELIVERABLE_CREATED) == len(executed["deliverables"])
    assert kinds[-1] is StepKind.REVIEW_REQUIRED

    completed = core.decide(record.task_id, ApprovalDecision.APPROVE, "Final check", "Dr Aslam")
    assert completed["status"] == TaskStatus.COMPLETED.value
    assert completed["reviewed_by"] == "Dr Aslam"
    assert completed["deliverables"][0]["status"] == TaskStatus.APPROVED.value


def test_execution_requires_recorded_approval(tmp_path: Path) -> None:
    core = _core(tmp_path)
    record = core.create_task(TaskRequest(goal="Prepare a lecture and write an announcement"))
    with pytest.raises(TaskStateError, match="Only an approved task"):
        core.execute(record.task_id)


def test_mixed_goal_dispatches_every_planned_specialist(tmp_path: Path) -> None:
    core = _core(tmp_path)
    record = core.create_task(TaskRequest(goal="Prepare a lecture and write an announcement"))
    core.decide(record.task_id, ApprovalDecision.APPROVE, approved_by="Dr Aslam")
    executed = core.execute(record.task_id)
    assert {item["agent"] for item in executed["deliverables"]} == {
        AgentName.LECTURE,
        AgentName.WRITING,
    }
    dispatched = [step for step in executed["agent_trace"] if step["kind"] == StepKind.AGENT_DISPATCHED]
    assert len(dispatched) == 2


def test_specialist_handoffs_are_only_created_during_execution(tmp_path: Path) -> None:
    core = _core(tmp_path)
    record = core.create_task(TaskRequest(goal="Research literature and prepare a quiz plus a YouTube video"))
    core.decide(record.task_id, ApprovalDecision.APPROVE, approved_by="Dr Aslam")
    executed = core.execute(record.task_id)
    assert {item["agent"] for item in executed["deliverables"]} == {
        AgentName.RESEARCH,
        AgentName.ASSESSMENT,
        AgentName.CONTENT,
    }
    assert all("Typed endpoint" in item["content"] for item in executed["deliverables"])


def test_high_risk_task_remains_blocked_without_explicit_override(tmp_path: Path) -> None:
    core = _core(tmp_path)
    record = core.create_task(TaskRequest(goal="Export student grades for the registrar"))
    with pytest.raises(BlockedApprovalError):
        core.decide(record.task_id, ApprovalDecision.APPROVE, approved_by="Dr Aslam")
