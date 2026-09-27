from __future__ import annotations

from axioms.agents import lecture_draft, social_media_draft, writing_draft
from axioms.models import AgentName, ApprovalDecision, TaskRecord, TaskRequest, TaskStatus
from axioms.policy import assess_request
from axioms.routing import build_task_graph
from axioms.store import TaskStore


class AxiomsCore:
    """Small, auditable orchestrator. Tool use and LLMs are intentionally not enabled here."""

    def __init__(self, store: TaskStore | None = None) -> None:
        self.store = store or TaskStore()

    def create_task(self, request: TaskRequest) -> TaskRecord:
        record = TaskRecord(request=request, subtasks=build_task_graph(request))
        for subtask in record.subtasks:
            if subtask.agent is AgentName.LECTURE:
                record.deliverables.append(lecture_draft(request))
            elif subtask.agent is AgentName.WRITING:
                record.deliverables.append(writing_draft(request))
            elif subtask.agent is AgentName.SOCIAL_MEDIA:
                record.deliverables.append(social_media_draft(request))
        policy = assess_request(request)
        record.status = TaskStatus.PENDING_APPROVAL if policy.requires_approval else TaskStatus.PLANNED
        self.store.save(record)
        return record

    def decide(self, task_id: str, decision: ApprovalDecision, note: str | None = None) -> dict:
        payload = self.store.get(task_id)
        if payload is None:
            raise KeyError(task_id)
        status = TaskStatus.APPROVED if decision is ApprovalDecision.APPROVE else TaskStatus.REJECTED
        payload["status"] = status.value
        payload["approval_note"] = note
        for deliverable in payload["deliverables"]:
            deliverable["status"] = status.value
        self.store.save(_record_from_payload(payload))
        return payload


def _record_from_payload(payload: dict) -> TaskRecord:
    """Rehydrate the public task contract without accepting untyped agent names."""
    request = TaskRequest(**payload["request"])
    record = TaskRecord(request=request, task_id=payload["task_id"], created_at=payload["created_at"])
    record.status = TaskStatus(payload["status"])
    record.approval_note = payload.get("approval_note")
    from axioms.models import Deliverable, Subtask

    record.subtasks = [
        Subtask(agent=AgentName(item["agent"]), title=item["title"], instructions=item["instructions"], depends_on=item.get("depends_on", []), checkpoint=item.get("checkpoint", True))
        for item in payload["subtasks"]
    ]
    record.deliverables = [
        Deliverable(agent=AgentName(item["agent"]), title=item["title"], content=item["content"], status=TaskStatus(item["status"]))
        for item in payload["deliverables"]
    ]
    return record
