from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class AgentName(StrEnum):
    CORE = "axioms_core"
    RESEARCH = "research"
    PORTFOLIO = "stem_ai_portfolio"
    LECTURE = "lecture_design"
    ASSESSMENT = "assessment_design"
    CONTENT = "content_creation"
    WRITING = "writing_communication"
    SOCIAL_MEDIA = "social_media"
    AUTOEVAL = "autoeval"


class TaskStatus(StrEnum):
    PLANNED = "planned"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    RUNNING = "running"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class ApprovalDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


class RiskTier(StrEnum):
    LOW = "low"
    ELEVATED = "elevated"
    HIGH = "high"


class StepKind(StrEnum):
    PLAN_CREATED = "plan_created"
    APPROVAL_RECORDED = "approval_recorded"
    EXECUTION_STARTED = "execution_started"
    AGENT_DISPATCHED = "agent_dispatched"
    DELIVERABLE_CREATED = "deliverable_created"
    REVIEW_REQUIRED = "review_required"
    REVIEW_RECORDED = "review_recorded"
    EXECUTION_FAILED = "execution_failed"


@dataclass(slots=True)
class TaskRequest:
    goal: str
    audience: str = "unspecified"
    deadline: str | None = None
    constraints: list[str] = field(default_factory=list)
    external_delivery: bool = False


@dataclass(slots=True)
class Subtask:
    agent: AgentName
    title: str
    instructions: str
    depends_on: list[str] = field(default_factory=list)
    checkpoint: bool = True


@dataclass(slots=True)
class Deliverable:
    title: str
    agent: AgentName
    content: str
    status: TaskStatus = TaskStatus.PENDING_APPROVAL


@dataclass(slots=True)
class AgentStep:
    kind: StepKind
    summary: str
    agent: AgentName | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass(slots=True)
class TaskRecord:
    request: TaskRequest
    task_id: str = field(default_factory=lambda: f"task_{uuid4().hex[:12]}")
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    status: TaskStatus = TaskStatus.PLANNED
    subtasks: list[Subtask] = field(default_factory=list)
    deliverables: list[Deliverable] = field(default_factory=list)
    agent_trace: list[AgentStep] = field(default_factory=list)
    approval_note: str | None = None
    approved_by: str | None = None
    reviewed_by: str | None = None
    risk_tier: RiskTier = RiskTier.LOW
    policy_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
