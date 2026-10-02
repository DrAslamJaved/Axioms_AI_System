from __future__ import annotations

from axioms.agents import (
    autoeval_draft,
    lecture_draft,
    portfolio_draft,
    social_media_draft,
    specialist_draft,
    writing_draft,
)
from axioms.dispatch import DispatchJob, DurableDispatchStore
from axioms.episodic_memory import EpisodicMemoryStore, MemoryDecision, MemoryProposal
from axioms.models import (
    AgentName,
    AgentStep,
    ApprovalDecision,
    Deliverable,
    RiskTier,
    StepKind,
    Subtask,
    TaskRecord,
    TaskRequest,
    TaskStatus,
)
from axioms.personal_kb import PersonalKnowledgeStore
from axioms.policy import assess_request
from axioms.routing import build_task_graph
from axioms.store import TaskStore


class BlockedApprovalError(RuntimeError):
    """Raised when a HIGH-risk blocking task is approved without an explicit override."""



class TaskStateError(RuntimeError):
    """Raised when a task lifecycle transition is not permitted."""


class AxiomsCore:
    """A bounded, human-governed task runtime.

    Task planning, execution and final review are separate persisted stages.  The
    runtime deliberately produces reviewable local drafts only; it has no
    external-write tools and cannot publish, send, schedule or modify accounts.
    """

    def __init__(
        self,
        store: TaskStore | None = None,
        kb_store: PersonalKnowledgeStore | None = None,
        memory_store: EpisodicMemoryStore | None = None,
        dispatch_store: DurableDispatchStore | None = None,
    ) -> None:
        self.store = store or TaskStore()
        self.kb_store = kb_store or PersonalKnowledgeStore(self.store.path)
        self.memory_store = memory_store or EpisodicMemoryStore(self.store.path)
        self.dispatch_store = dispatch_store or DurableDispatchStore(self.store.path)

    def create_task(self, request: TaskRequest) -> TaskRecord:
        record = TaskRecord(request=request, subtasks=build_task_graph(request))
        policy = assess_request(request)
        record.status = TaskStatus.PENDING_APPROVAL if policy.requires_approval else TaskStatus.PLANNED
        record.risk_tier = policy.risk_tier
        record.policy_reason = policy.reason
        record.agent_trace.append(
            AgentStep(
                kind=StepKind.PLAN_CREATED,
                summary=f"Planned {len(record.subtasks)} specialist subtask(s); execution is held for approval.",
            )
        )
        self.store.save(record)
        return record

    def decide(
        self,
        task_id: str,
        decision: ApprovalDecision,
        note: str | None = None,
        approved_by: str | None = None,
        *,
        override_blocking: bool = False,
    ) -> dict:
        payload = self.store.get(task_id)
        if payload is None:
            raise KeyError(task_id)
        current_status = TaskStatus(payload["status"])
        if current_status in {TaskStatus.REJECTED, TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.RUNNING}:
            raise TaskStateError(f"Task {task_id} cannot be decided while it is {current_status.value}.")
        if current_status is TaskStatus.AWAITING_REVIEW:
            return self._record_final_review(payload, decision, note, approved_by)
        if current_status not in {TaskStatus.PLANNED, TaskStatus.PENDING_APPROVAL, TaskStatus.APPROVED}:
            raise TaskStateError(f"Task {task_id} is not ready for approval.")
        if (
            decision is ApprovalDecision.APPROVE
            and payload.get("risk_tier") == RiskTier.HIGH.value
            and not override_blocking
        ):
            raise BlockedApprovalError(
                f"Task {task_id} is classified HIGH risk (blocking). "
                "The data-governance issue must be resolved before approval. "
                "Pass override_blocking=true to approve with an explicit acknowledgement."
            )
        status = TaskStatus.APPROVED if decision is ApprovalDecision.APPROVE else TaskStatus.REJECTED
        payload["status"] = status.value
        payload["approval_note"] = note
        payload["approved_by"] = approved_by
        record = _record_from_payload(payload)
        record.agent_trace.append(
            AgentStep(
                kind=StepKind.APPROVAL_RECORDED,
                summary=(
                    "Execution authorised by a human approver."
                    if status is TaskStatus.APPROVED
                    else "Task rejected before execution."
                ),
            )
        )
        self.store.save(record)
        return record.to_dict()

    def execute(self, task_id: str) -> dict:
        """Run an approved plan locally and return its drafts for final review."""
        payload = self.store.get(task_id)
        if payload is None:
            raise KeyError(task_id)
        if TaskStatus(payload["status"]) is not TaskStatus.APPROVED:
            raise TaskStateError("Only an approved task may be executed.")

        record = _record_from_payload(payload)
        record.status = TaskStatus.RUNNING
        record.agent_trace.append(
            AgentStep(kind=StepKind.EXECUTION_STARTED, summary="Approved task execution started.")
        )
        self.store.save(record)
        try:
            deliverables: list[Deliverable] = []
            for subtask in record.subtasks:
                record.agent_trace.append(
                    AgentStep(
                        kind=StepKind.AGENT_DISPATCHED,
                        agent=subtask.agent,
                        summary=f"Dispatched {subtask.agent.value} for: {subtask.title}",
                    )
                )
                deliverable = _run_local_draft(record.request, subtask)
                deliverables.append(deliverable)
                record.agent_trace.append(
                    AgentStep(
                        kind=StepKind.DELIVERABLE_CREATED,
                        agent=subtask.agent,
                        summary=f"Created review-only deliverable: {deliverable.title}",
                    )
                )
        except (TypeError, ValueError) as error:
            record.status = TaskStatus.FAILED
            record.agent_trace.append(AgentStep(kind=StepKind.EXECUTION_FAILED, summary=str(error)))
            self.store.save(record)
            raise

        record.deliverables.extend(deliverables)
        record.status = TaskStatus.AWAITING_REVIEW
        record.agent_trace.append(
            AgentStep(
                kind=StepKind.REVIEW_REQUIRED,
                summary="All drafts are ready for final human review; no external action was performed.",
            )
        )
        self.store.save(record)
        return record.to_dict()

    def run_one_dispatched_task(self, worker_id: str) -> dict | None:
        """Claim and run one approved local job; no external action is available to the worker."""
        job = self.dispatch_store.claim_next(worker_id)
        if job is None:
            return None
        payload = self.store.get(job.task_id)
        if payload is None:
            finished = self.dispatch_store.finish(
                job.job_id,
                worker_id=worker_id,
                succeeded=False,
                error="Task no longer exists.",
                retryable=False,
            )
            return {"job": finished.to_dict(), "task": None}
        if TaskStatus(payload["status"]) is not TaskStatus.APPROVED:
            finished = self.dispatch_store.finish(
                job.job_id,
                worker_id=worker_id,
                succeeded=False,
                error=f"Task is {payload['status']}, not approved.",
                retryable=False,
            )
            return {"job": finished.to_dict(), "task": payload}

        record = _record_from_payload(payload)
        record.agent_trace.append(
            AgentStep(
                kind=StepKind.DISPATCH_EXECUTION_STARTED,
                summary=f"Claimed durable dispatch job {job.job_id} for local execution by {worker_id}.",
            )
        )
        self.store.save(record)
        try:
            task = self.execute(job.task_id)
        except Exception as error:  # noqa: BLE001 - the worker must not strand a claimed job
            retryable = self._retry_failed_local_task(job.task_id, job.job_id, str(error))
            finished = self.dispatch_store.finish(
                job.job_id,
                worker_id=worker_id,
                succeeded=False,
                error=f"{type(error).__name__}: {error}",
                retryable=retryable,
            )
            return {"job": finished.to_dict(), "task": self.store.get(job.task_id)}
        finished = self.dispatch_store.finish(job.job_id, worker_id=worker_id, succeeded=True)
        return {"job": finished.to_dict(), "task": task}

    def _retry_failed_local_task(self, task_id: str, job_id: str, error: str) -> bool:
        """Restore only clean local failures to approved state for the queue's bounded retry budget."""
        payload = self.store.get(task_id)
        if payload is None or TaskStatus(payload["status"]) is not TaskStatus.FAILED:
            return False
        record = _record_from_payload(payload)
        if record.deliverables:
            return False
        record.status = TaskStatus.APPROVED
        record.agent_trace.append(
            AgentStep(
                kind=StepKind.DISPATCH_RETRY_SCHEDULED,
                summary=f"Local execution failed for {job_id}; restored approved task for bounded retry: {error}",
            )
        )
        self.store.save(record)
        return True

    def enqueue_approved_task(
        self, task_id: str, *, idempotency_key: str, max_attempts: int = 2
    ) -> DispatchJob:
        """Persist an approved local task for a worker; this never starts execution itself."""
        payload = self.store.get(task_id)
        if payload is None:
            raise KeyError(task_id)
        if TaskStatus(payload["status"]) is not TaskStatus.APPROVED:
            raise TaskStateError("Only an approved task may be queued for dispatch.")
        job = self.dispatch_store.enqueue(
            task_id, idempotency_key=idempotency_key, max_attempts=max_attempts
        )
        record = _record_from_payload(payload)
        if not any(step.summary.endswith(job.job_id) for step in record.agent_trace):
            record.agent_trace.append(
                AgentStep(
                    kind=StepKind.DISPATCH_QUEUED,
                    summary=f"Approved local task queued for durable worker dispatch: {job.job_id}",
                )
            )
            self.store.save(record)
        return job

    def propose_episodic_memory(self, task_id: str) -> dict:
        """Create a human-review proposal from a completed, non-sensitive task episode."""
        payload = self.store.get(task_id)
        if payload is None:
            raise KeyError(task_id)
        if TaskStatus(payload["status"]) is not TaskStatus.COMPLETED:
            raise TaskStateError("Only a completed task may be proposed for episodic memory.")
        if payload.get("risk_tier") == RiskTier.HIGH.value:
            raise TaskStateError("HIGH-risk task episodes are never eligible for episodic memory.")
        agents = sorted({item["agent"] for item in payload["subtasks"]})
        summary = f"Completed task: {payload['request']['goal']} | Agents: {', '.join(agents)}"
        return self.memory_store.propose(
            MemoryProposal(task_id=task_id, summary=summary, tags=tuple(agents))
        )

    def decide_episodic_memory(
        self, proposal_id: str, decision: MemoryDecision, decided_by: str, note: str | None = None
    ) -> dict:
        return self.memory_store.decide(proposal_id, decision, decided_by, note)

    def recall_episodic_memory(self, query: str, *, limit: int = 5) -> list[dict]:
        return self.memory_store.search(query, limit=limit)

    def _record_final_review(
        self, payload: dict, decision: ApprovalDecision, note: str | None, reviewer: str | None
    ) -> dict:
        record = _record_from_payload(payload)
        record.status = TaskStatus.COMPLETED if decision is ApprovalDecision.APPROVE else TaskStatus.REJECTED
        record.approval_note = note
        record.reviewed_by = reviewer
        deliverable_status = TaskStatus.APPROVED if decision is ApprovalDecision.APPROVE else TaskStatus.REJECTED
        for deliverable in record.deliverables:
            deliverable.status = deliverable_status
        record.agent_trace.append(
            AgentStep(
                kind=StepKind.REVIEW_RECORDED,
                summary=("Final human review accepted the drafts." if decision is ApprovalDecision.APPROVE else "Final human review rejected the drafts."),
            )
        )
        self.store.save(record)
        return record.to_dict()


def _run_local_draft(request: TaskRequest, subtask: Subtask) -> Deliverable:
    """Dispatch only local, deterministic drafting functions in this runtime phase."""
    if subtask.agent is AgentName.LECTURE:
        return lecture_draft(request)
    if subtask.agent is AgentName.WRITING:
        return writing_draft(request)
    if subtask.agent is AgentName.SOCIAL_MEDIA:
        return social_media_draft(request)
    if subtask.agent is AgentName.PORTFOLIO:
        return portfolio_draft(request)
    if subtask.agent is AgentName.AUTOEVAL:
        return autoeval_draft(request)
    if subtask.agent in {AgentName.RESEARCH, AgentName.ASSESSMENT, AgentName.CONTENT}:
        return specialist_draft(request, subtask.agent)
    raise ValueError(f"No local draft runner is registered for {subtask.agent.value}.")


def _record_from_payload(payload: dict) -> TaskRecord:
    """Rehydrate the public task contract without accepting untyped agent names."""
    request = TaskRequest(**payload["request"])
    record = TaskRecord(request=request, task_id=payload["task_id"], created_at=payload["created_at"])
    record.status = TaskStatus(payload["status"])
    record.approval_note = payload.get("approval_note")
    record.approved_by = payload.get("approved_by")
    if payload.get("risk_tier"):
        record.risk_tier = RiskTier(payload["risk_tier"])
    record.policy_reason = payload.get("policy_reason")
    record.subtasks = [
        Subtask(agent=AgentName(item["agent"]), title=item["title"], instructions=item["instructions"], depends_on=item.get("depends_on", []), checkpoint=item.get("checkpoint", True))
        for item in payload["subtasks"]
    ]
    record.deliverables = [
        Deliverable(agent=AgentName(item["agent"]), title=item["title"], content=item["content"], status=TaskStatus(item["status"]))
        for item in payload["deliverables"]
    ]
    record.agent_trace = [
        AgentStep(
            kind=StepKind(item["kind"]),
            summary=item["summary"],
            agent=AgentName(item["agent"]) if item.get("agent") else None,
            created_at=item["created_at"],
        )
        for item in payload.get("agent_trace", [])
    ]
    record.reviewed_by = payload.get("reviewed_by")
    return record
