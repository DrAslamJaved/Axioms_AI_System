from pathlib import Path
from threading import Barrier, Event, Lock, Thread, current_thread

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


def test_cross_agent_autoeval_consolidates_completed_drafts_without_approving_them(tmp_path: Path) -> None:
    core = _core(tmp_path)
    record = core.create_task(TaskRequest(goal="Prepare a lecture and write an announcement"))
    core.decide(record.task_id, ApprovalDecision.APPROVE, approved_by="Dr Aslam")
    executed = core.execute(record.task_id)

    reviewed = core.create_cross_agent_autoeval(record.task_id)

    assert reviewed["status"] == TaskStatus.AWAITING_REVIEW.value
    assert len(reviewed["deliverables"]) == len(executed["deliverables"]) + 1
    report = reviewed["deliverables"][-1]
    assert report["agent"] == AgentName.AUTOEVAL.value
    assert report["status"] == TaskStatus.PENDING_APPROVAL.value
    assert "Aggregate quality signal" in report["content"]
    assert "Final human review remains required" in report["content"]
    assert any(step["kind"] == StepKind.CROSS_AGENT_AUTOEVAL_CREATED for step in reviewed["agent_trace"])

    repeated = core.create_cross_agent_autoeval(record.task_id)
    assert len(repeated["deliverables"]) == len(reviewed["deliverables"])


def test_cross_agent_autoeval_requires_completed_drafts_awaiting_review(tmp_path: Path) -> None:
    core = _core(tmp_path)
    record = core.create_task(TaskRequest(goal="Prepare a lecture on graph theory"))

    with pytest.raises(TaskStateError, match="completed drafts awaiting final human review"):
        core.create_cross_agent_autoeval(record.task_id)


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


def test_operational_summary_reports_aggregate_local_health_without_exposing_task_content(tmp_path: Path) -> None:
    core = _core(tmp_path)
    record = core.create_task(TaskRequest(goal="Prepare a lecture on spectral graph theory"))
    core.decide(record.task_id, ApprovalDecision.APPROVE, approved_by="Dr Aslam")
    core.enqueue_approved_task(record.task_id, idempotency_key="operations-summary-001")

    summary = core.operational_summary()

    assert summary["tasks"][TaskStatus.APPROVED.value] == 1
    assert summary["dispatch"]["status_counts"]["queued"] == 1
    assert not summary["external_actions_enabled"]
    assert summary["human_review_required"]


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


def test_parallel_execution_is_opt_in_and_keeps_deterministic_graph_order(
    tmp_path: Path, monkeypatch
) -> None:
    core = _core(tmp_path)
    record = core.create_task(TaskRequest(goal="Prepare a lecture and write an announcement"))
    core.decide(record.task_id, ApprovalDecision.APPROVE, approved_by="Dr Aslam")
    original = core_module._run_local_draft
    thread_names: list[str] = []
    barrier = Barrier(2)

    def capture_thread(request, subtask):
        thread_names.append(current_thread().name)
        barrier.wait(timeout=2)
        return original(request, subtask)

    monkeypatch.setattr(core_module, "_run_local_draft", capture_thread)
    executed = core.execute(record.task_id, parallel=True)

    assert [item["agent"] for item in executed["deliverables"]] == [
        AgentName.LECTURE.value,
        AgentName.WRITING.value,
    ]
    assert thread_names and all(name.startswith("axioms-local") for name in thread_names)
    kinds = [step["kind"] for step in executed["agent_trace"]]
    assert kinds.count(StepKind.EXECUTION_LAYER_STARTED) == 1
    assert kinds.count(StepKind.EXECUTION_LAYER_COMPLETED) == 1


def test_parallel_execution_obeys_the_configured_local_worker_cap(tmp_path: Path, monkeypatch) -> None:
    core = AxiomsCore(TaskStore(tmp_path / "test.sqlite3"), max_parallel_workers=2)
    record = core.create_task(TaskRequest(goal="Prepare a lecture, write a report, and build a portfolio"))
    core.decide(record.task_id, ApprovalDecision.APPROVE, approved_by="Dr Aslam")
    original = core_module._run_local_draft
    two_workers_started = Event()
    release_workers = Event()
    lock = Lock()
    active_workers = 0
    max_active_workers = 0

    def observe_concurrency(request, subtask):
        nonlocal active_workers, max_active_workers
        with lock:
            active_workers += 1
            max_active_workers = max(max_active_workers, active_workers)
            if active_workers == 2:
                two_workers_started.set()
        assert release_workers.wait(timeout=2)
        try:
            return original(request, subtask)
        finally:
            with lock:
                active_workers -= 1

    monkeypatch.setattr(core_module, "_run_local_draft", observe_concurrency)
    result: dict = {}
    thread = Thread(target=lambda: result.update(core.execute(record.task_id, parallel=True)))
    thread.start()
    assert two_workers_started.wait(timeout=2)
    release_workers.set()
    thread.join(timeout=2)

    assert not thread.is_alive()
    assert max_active_workers == 2
    assert result["status"] == TaskStatus.AWAITING_REVIEW.value


def test_parallel_worker_limit_rejects_invalid_configuration(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="between 1 and 4"):
        AxiomsCore(TaskStore(tmp_path / "test.sqlite3"), max_parallel_workers=5)


def test_execution_rejects_a_task_with_a_changed_graph_digest(tmp_path: Path) -> None:
    core = _core(tmp_path)
    record = core.create_task(TaskRequest(goal="Prepare a lecture on graph theory"))
    core.decide(record.task_id, ApprovalDecision.APPROVE, approved_by="Dr Aslam")
    payload = core.store.get(record.task_id)
    assert payload is not None
    payload["graph_digest"] = "0" * 64
    core.store.save(core_module._record_from_payload(payload))

    with pytest.raises(TaskStateError, match="integrity check failed"):
        core.execute(record.task_id)


def test_approved_task_can_be_cancelled_before_execution(tmp_path: Path) -> None:
    core = _core(tmp_path)
    record = core.create_task(TaskRequest(goal="Prepare a lecture on graph theory"))
    core.decide(record.task_id, ApprovalDecision.APPROVE, approved_by="Dr Aslam")

    cancelled = core.request_cancellation(record.task_id, "Dr Aslam", "Scope changed")

    assert cancelled["status"] == TaskStatus.CANCELLED.value
    assert cancelled["deliverables"] == []
    assert cancelled["agent_trace"][-1]["kind"] == StepKind.CANCELLATION_REQUESTED.value
    with pytest.raises(TaskStateError, match="Only an approved task"):
        core.execute(record.task_id)


def test_cancelled_queued_task_is_not_run_by_the_local_worker(tmp_path: Path) -> None:
    core = _core(tmp_path)
    record = core.create_task(TaskRequest(goal="Prepare a lecture on graph theory"))
    core.decide(record.task_id, ApprovalDecision.APPROVE, approved_by="Dr Aslam")
    core.enqueue_approved_task(record.task_id, idempotency_key="cancelled-dispatch-001")
    core.request_cancellation(record.task_id, "Dr Aslam")

    result = core.run_one_dispatched_task("local-worker")

    assert result is not None
    assert result["task"]["status"] == TaskStatus.CANCELLED.value
    assert result["job"]["status"] == "dead_letter"


def test_running_task_stops_at_checkpoint_and_discards_partial_drafts(tmp_path: Path, monkeypatch) -> None:
    core = _core(tmp_path)
    record = core.create_task(TaskRequest(goal="Research literature and prepare an assessment"))
    core.decide(record.task_id, ApprovalDecision.APPROVE, approved_by="Dr Aslam")
    original = core_module._run_local_draft
    first_layer_started = Event()
    release_first_layer = Event()
    result: dict = {}

    def pause_research(request, subtask):
        if subtask.agent is AgentName.RESEARCH:
            first_layer_started.set()
            assert release_first_layer.wait(timeout=2)
        return original(request, subtask)

    def execute() -> None:
        result.update(core.execute(record.task_id))

    monkeypatch.setattr(core_module, "_run_local_draft", pause_research)
    thread = Thread(target=execute)
    thread.start()
    assert first_layer_started.wait(timeout=2)
    pending = core.request_cancellation(record.task_id, "Dr Aslam", "Stop after this safe checkpoint")
    assert pending["status"] == TaskStatus.CANCELLATION_REQUESTED.value
    release_first_layer.set()
    thread.join(timeout=2)

    assert not thread.is_alive()
    assert result["status"] == TaskStatus.CANCELLED.value
    assert result["deliverables"] == []
    assert result["agent_trace"][-1]["kind"] == StepKind.EXECUTION_CANCELLED.value


def test_interrupted_running_task_requires_human_attestation_and_fresh_approval(tmp_path: Path) -> None:
    core = _core(tmp_path)
    record = core.create_task(TaskRequest(goal="Prepare a lecture on graph theory"))
    core.decide(record.task_id, ApprovalDecision.APPROVE, approved_by="Dr Aslam")
    payload = core.store.get(record.task_id)
    assert payload is not None
    payload["status"] = TaskStatus.RUNNING.value
    core.store.save(core_module._record_from_payload(payload))

    with pytest.raises(ValueError, match="confirmation"):
        core.recover_interrupted_task(record.task_id, "Dr Aslam")

    recovered = core.recover_interrupted_task(
        record.task_id,
        "Dr Aslam",
        "Local process exited during execution",
        confirm_execution_stopped=True,
    )

    assert recovered["status"] == TaskStatus.PENDING_APPROVAL.value
    assert recovered["approved_by"] is None
    assert recovered["deliverables"] == []
    assert recovered["agent_trace"][-1]["kind"] == StepKind.EXECUTION_RECOVERED.value
    with pytest.raises(TaskStateError, match="Only an approved task"):
        core.execute(record.task_id)
    core.decide(record.task_id, ApprovalDecision.APPROVE, approved_by="Dr Aslam")
    assert core.execute(record.task_id)["status"] == TaskStatus.AWAITING_REVIEW.value


def test_recovery_finalises_a_stranded_cancellation_request(tmp_path: Path) -> None:
    core = _core(tmp_path)
    record = core.create_task(TaskRequest(goal="Prepare a lecture on graph theory"))
    core.decide(record.task_id, ApprovalDecision.APPROVE, approved_by="Dr Aslam")
    payload = core.store.get(record.task_id)
    assert payload is not None
    payload["status"] = TaskStatus.CANCELLATION_REQUESTED.value
    core.store.save(core_module._record_from_payload(payload))

    recovered = core.recover_interrupted_task(
        record.task_id, "Dr Aslam", confirm_execution_stopped=True
    )

    assert recovered["status"] == TaskStatus.CANCELLED.value
    assert recovered["deliverables"] == []
    assert recovered["agent_trace"][-1]["kind"] == StepKind.EXECUTION_CANCELLED.value


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


def test_owner_can_delete_a_consented_episodic_memory_entry(tmp_path: Path) -> None:
    core = _core(tmp_path)
    record = core.create_task(TaskRequest(goal="Prepare a lecture on spectral graph theory"))
    core.decide(record.task_id, ApprovalDecision.APPROVE, approved_by="Dr Aslam")
    core.execute(record.task_id)
    core.decide(record.task_id, ApprovalDecision.APPROVE, approved_by="Dr Aslam")
    proposal = core.propose_episodic_memory(record.task_id)
    core.decide_episodic_memory(proposal["proposal_id"], MemoryDecision.APPROVE, "Dr Aslam")
    entry = core.recall_episodic_memory("spectral")[0]
    deleted = core.delete_episodic_memory(entry["memory_id"], "Dr Aslam", "No longer needed")
    assert deleted["memory_id"] == entry["memory_id"]
    assert core.recall_episodic_memory("spectral") == []


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
