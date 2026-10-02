"""Bounded, instructor-facing LLM review for the Assessment Design Agent."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from axioms.assessment_agent import (
    AssessmentBlueprint,
    AssessmentRequest,
    build_assessment_blueprint,
)
from axioms.autoeval_agent import AutoEvalRequest, EvaluatedAgent, evaluate_deliverable
from axioms.llm import LLMDisabledError, LLMMessage, LLMProvider, LLMResult


class AssessmentStepKind(StrEnum):
    PLAN = "plan"
    SYNTHESIS = "synthesis"
    GUARDRAIL = "guardrail"
    NOTE = "note"


@dataclass(frozen=True, slots=True)
class AssessmentAgentStep:
    kind: AssessmentStepKind
    summary: str
    detail: str

    def to_dict(self) -> dict:
        return {"kind": self.kind.value, "summary": self.summary, "detail": self.detail}


@dataclass(frozen=True, slots=True)
class AgenticAssessmentConfig:
    max_tokens: int = 700
    temperature: float = 0.1


@dataclass(frozen=True, slots=True)
class AgenticAssessmentResult:
    blueprint: AssessmentBlueprint
    design_review: str | None
    generation_enabled: bool
    agent_trace: tuple[AssessmentAgentStep, ...]
    autoeval: dict | None
    instructor_review_required: bool = True
    student_release_blocked: bool = True

    def to_dict(self) -> dict:
        return {
            "blueprint": self.blueprint.to_dict(),
            "design_review": self.design_review,
            "generation_enabled": self.generation_enabled,
            "agent_trace": [step.to_dict() for step in self.agent_trace],
            "autoeval": self.autoeval,
            "instructor_review_required": self.instructor_review_required,
            "student_release_blocked": self.student_release_blocked,
        }


ASSESSMENT_SYSTEM_PROMPT = """You are the Axioms Assessment Design Agent assisting an instructor.

You must obey every rule below:
1. Work only with the provided learning outcomes, marks, assessment type, and approved source scope.
2. Produce an instructor-facing design review, not student-facing questions, model answers, worked solutions, or an answer key.
3. Do not invent course facts, source material, data, or citations.
4. Check constructive alignment, mark allocation, difficulty, and AI-resistance evidence requirements.
5. Never claim an assessment is AI-proof; describe the safeguards as reviewable mitigations.
6. End with a compact instructor checklist. The output remains a draft requiring instructor approval.
"""


def _messages(blueprint: AssessmentBlueprint) -> list[LLMMessage]:
    request = blueprint.request
    outcomes = "\n".join(
        f"- {outcome.outcome_id} ({outcome.bloom_level.value}): {outcome.text}"
        for outcome in request.learning_outcomes
    )
    questions = "\n".join(
        f"- Q{question.number}: {question.marks} marks; {question.outcome_id}; "
        f"{question.bloom_level.value}; {question.difficulty.value}"
        for question in blueprint.questions
    )
    user = f"""Assessment context
- Topic: {request.topic}
- Course level: {request.course_level}
- Type: {request.assessment_type.value}
- Duration: {request.duration_minutes} minutes
- Total marks: {request.total_marks}
- Approved source scope: {request.approved_source_scope}

Learning outcomes
{outcomes}

Deterministic blueprint allocation
{questions}

AI-resilience controls already required
{chr(10).join(f'- {item}' for item in blueprint.ai_resilience_review)}

Write the constrained instructor-facing design review now."""
    return [LLMMessage("system", ASSESSMENT_SYSTEM_PROMPT), LLMMessage("user", user)]


def _guardrail(blueprint: AssessmentBlueprint, review: str, trace: list[AssessmentAgentStep]) -> dict:
    outcome_ids = tuple(outcome.outcome_id for outcome in blueprint.request.learning_outcomes)
    report = evaluate_deliverable(
        AutoEvalRequest(
            evaluated_agent=EvaluatedAgent.ASSESSMENT,
            deliverable_title="Agentic assessment design review",
            artifact_text=review,
            required_elements=outcome_ids,
            evidence_markers=outcome_ids,
            public_facing=False,
            declared_sensitive_data=False,
        )
    )
    summary = {
        "quality_signal_percent": report.quality_signal_percent,
        "missing_required_elements": list(report.missing_required_elements),
        "artifact_sha256": report.artifact_sha256,
    }
    detail = (
        f"Outcome-reference check {report.quality_signal_percent}%. "
        + (
            "All declared outcomes are referenced."
            if not report.missing_required_elements
            else "Missing outcome IDs: " + ", ".join(report.missing_required_elements)
        )
    )
    trace.append(AssessmentAgentStep(AssessmentStepKind.GUARDRAIL, "AutoEval outcome check", detail))
    return summary


def run_agentic_assessment_design(
    request: AssessmentRequest,
    *,
    provider: LLMProvider,
    config: AgenticAssessmentConfig | None = None,
) -> AgenticAssessmentResult:
    """Plan deterministically, then optionally generate a constrained instructor review."""
    settings = config or AgenticAssessmentConfig()
    blueprint = build_assessment_blueprint(request)
    trace = [
        AssessmentAgentStep(
            AssessmentStepKind.PLAN,
            "Deterministic assessment blueprint created",
            f"{len(blueprint.questions)} item(s), {blueprint.allocated_marks}/{request.total_marks} marks allocated.",
        )
    ]
    try:
        result: LLMResult = provider.complete(
            _messages(blueprint), max_tokens=settings.max_tokens, temperature=settings.temperature
        )
    except LLMDisabledError:
        trace.append(
            AssessmentAgentStep(
                AssessmentStepKind.NOTE,
                "Design review skipped: LLM disabled",
                "The deterministic blueprint remains available for instructor review.",
            )
        )
        return AgenticAssessmentResult(
            blueprint=blueprint,
            design_review=None,
            generation_enabled=False,
            agent_trace=tuple(trace),
            autoeval=None,
        )
    except Exception as error:  # noqa: BLE001 - provider errors are traceable, not fatal to the blueprint
        trace.append(
            AssessmentAgentStep(
                AssessmentStepKind.NOTE,
                "Design review skipped: provider error",
                f"{type(error).__name__}: {error}",
            )
        )
        return AgenticAssessmentResult(
            blueprint=blueprint,
            design_review=None,
            generation_enabled=False,
            agent_trace=tuple(trace),
            autoeval=None,
        )

    review = result.text
    trace.append(
        AssessmentAgentStep(
            AssessmentStepKind.SYNTHESIS,
            "Bounded instructor-facing assessment review generated",
            f"provider={result.provider} model={result.model} stop={result.stop_reason}",
        )
    )
    autoeval = _guardrail(blueprint, review, trace)
    return AgenticAssessmentResult(
        blueprint=blueprint,
        design_review=review,
        generation_enabled=True,
        agent_trace=tuple(trace),
        autoeval=autoeval,
    )
