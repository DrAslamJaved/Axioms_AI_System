from pathlib import Path

import pytest

from axioms import core as core_module
from axioms.core import AxiomsCore, BlockedApprovalError, TaskStateError
from axioms.episodic_memory import MemoryDecision
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
    assert record.graph_version == "routing.v1"
    assert record.graph_digest is not None


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


def test_only_approved_tasks_can_be_durably_queued_with_an_idempotent_trace(tmp_path: Path) -> None:
    core = _core(tmp_path)
    record = core.create_task(TaskRequest(goal="Prepare a lecture on spectral graph theory"))
    with pytest.raises(TaskStateError, match="Only an approved task"):
        core.enqueue_approved_task(record.task_id, idempotency_key="lecture-dispatch-001")
    core.decide(record.task_id, ApprovalDecision.APPROVE, approved_by="Dr Aslam")
    first = core.enqueue_approved_task(record.task_id, idempotency_key="lecture-dispatch-001")
    repeated = core.enqueue_approved_task(record.task_id, idempotency_key="lecture-dispatch-001")
    assert repeated.job_id == first.job_id
    task = core.store.get(record.task_id)
    assert task is not None
    assert [step["kind"] for step in task["agent_trace"]].count(StepKind.DISPATCH_QUEUED) == 1


def test_local_worker_executes_one_claimed_approved_job_then_requires_final_review(tmp_path: Path) -> None:
    core = _core(tmp_path)
    record = core.create_task(TaskRequest(goal="Prepare a lecture on spectral graph theory"))
    core.decide(record.task_id, ApprovalDecision.APPROVE, approved_by="Dr Aslam")
    core.enqueue_approved_task(record.task_id, idempotency_key="worker-success-001")
    result = core.run_one_dispatched_task("local-worker")
    assert result is not None
    assert result["job"]["status"] == "succeeded"
    assert result["task"]["status"] == TaskStatus.AWAITING_REVIEW.value
    assert any(step["kind"] == StepKind.DISPATCH_EXECUTION_STARTED for step in result["task"]["agent_trace"])


def test_local_worker_retries_clean_local_failure_within_job_budget(tmp_path: Path, monkeypatch) -> None:
    core = _core(tmp_path)
    record = core.create_task(TaskRequest(goal="Prepare a lecture on spectral graph theory"))
    core.decide(record.task_id, ApprovalDecision.APPROVE, approved_by="Dr Aslam")
    core.enqueue_approved_task(record.task_id, idempotency_key="worker-retry-001", max_attempts=2)
    original = core_module._run_local_draft
    calls = [0]

    def fail_once(request, subtask):
        calls[0] += 1
        if calls[0] == 1:
            raise ValueError("temporary local failure")
        return original(request, subtask)

    monkeypatch.setattr(core_module, "_run_local_draft", fail_once)
    failed = core.run_one_dispatched_task("local-worker")
    assert failed is not None
    assert failed["job"]["status"] == "queued"
    assert failed["task"]["status"] == TaskStatus.APPROVED.value
    assert any(step["kind"] == StepKind.DISPATCH_RETRY_SCHEDULED for step in failed["task"]["agent_trace"])
    succeeded = core.run_one_dispatched_task("local-worker")
    assert succeeded is not None
    assert succeeded["job"]["status"] == "succeeded"
    assert succeeded["job"]["attempts"] == 2


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


def test_completed_low_risk_task_enters_memory_only_after_a_second_approval(tmp_path: Path) -> None:
    core = _core(tmp_path)
    record = core.create_task(TaskRequest(goal="Prepare a lecture on spectral graph theory"))
    core.decide(record.task_id, ApprovalDecision.APPROVE, approved_by="Dr Aslam")
    core.execute(record.task_id)
    core.decide(record.task_id, ApprovalDecision.APPROVE, approved_by="Dr Aslam")

    proposal = core.propose_episodic_memory(record.task_id)
    assert core.recall_episodic_memory("spectral") == []
    core.decide_episodic_memory(proposal["proposal_id"], MemoryDecision.APPROVE, "Dr Aslam")
    assert core.recall_episodic_memory("spectral")[0]["task_id"] == record.task_id


def test_high_risk_task_is_never_eligible_for_episodic_memory(tmp_path: Path) -> None:
    core = _core(tmp_path)
    record = core.create_task(TaskRequest(goal="Prepare a lecture using student grades"))
    core.decide(
        record.task_id,
        ApprovalDecision.APPROVE,
        approved_by="Dr Aslam",
        override_blocking=True,
    )
    core.execute(record.task_id)
    core.decide(record.task_id, ApprovalDecision.APPROVE, approved_by="Dr Aslam")
    with pytest.raises(TaskStateError, match="never eligible"):
        core.propose_episodic_memory(record.task_id)
