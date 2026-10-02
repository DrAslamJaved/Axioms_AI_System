from __future__ import annotations

from axioms.agents import (
    autoeval_draft,
    lecture_draft,
    portfolio_draft,
    social_media_draft,
    specialist_draft,
    writing_draft,
)
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

    def __init__(self, store: TaskStore | None = None, kb_store: PersonalKnowledgeStore | None = None) -> None:
        self.store = store or TaskStore()
        self.kb_store = kb_store or PersonalKnowledgeStore(self.store.path)

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
            for subtask in record.subtasks:
                record.agent_trace.append(
                    AgentStep(
                        kind=StepKind.AGENT_DISPATCHED,
                        agent=subtask.agent,
                        summary=f"Dispatched {subtask.agent.value} for: {subtask.title}",
                    )
                )
                deliverable = _run_local_draft(record.request, subtask)
                record.deliverables.append(deliverable)
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

        record.status = TaskStatus.AWAITING_REVIEW
        record.agent_trace.append(
            AgentStep(
                kind=StepKind.REVIEW_REQUIRED,
                summary="All drafts are ready for final human review; no external action was performed.",
            )
        )
        self.store.save(record)
        return record.to_dict()

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
