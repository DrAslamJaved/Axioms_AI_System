"""Bounded, instructor-facing LLM review for the Content Creation Agent."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from axioms.autoeval_agent import AutoEvalRequest, EvaluatedAgent, evaluate_deliverable
from axioms.content_agent import ContentPackage, ContentRequest, build_content_package
from axioms.llm import LLMDisabledError, LLMMessage, LLMProvider, LLMResult


class ContentStepKind(StrEnum):
    PLAN = "plan"
    SYNTHESIS = "synthesis"
    GUARDRAIL = "guardrail"
    NOTE = "note"


@dataclass(frozen=True, slots=True)
class ContentAgentStep:
    kind: ContentStepKind
    summary: str
    detail: str

    def to_dict(self) -> dict:
        return {"kind": self.kind.value, "summary": self.summary, "detail": self.detail}


@dataclass(frozen=True, slots=True)
class AgenticContentConfig:
    max_tokens: int = 700
    temperature: float = 0.1


@dataclass(frozen=True, slots=True)
class AgenticContentResult:
    package: ContentPackage
    editorial_review: str | None
    generation_enabled: bool
    agent_trace: tuple[ContentAgentStep, ...]
    autoeval: dict | None
    editorial_approval_required: bool = True
    publication_blocked: bool = True

    def to_dict(self) -> dict:
        return {
            "package": self.package.to_dict(),
            "editorial_review": self.editorial_review,
            "generation_enabled": self.generation_enabled,
            "agent_trace": [step.to_dict() for step in self.agent_trace],
            "autoeval": self.autoeval,
            "editorial_approval_required": self.editorial_approval_required,
            "publication_blocked": self.publication_blocked,
        }


CONTENT_SYSTEM_PROMPT = """You are the Axioms Content Creation Agent assisting an instructor or editor.

You must obey every rule below:
1. Work only with the supplied content blueprint, learning outcomes, format, audience, language mode, and approved source scope.
2. Produce an internal editorial review, not a student-facing script, final publication copy, factual teaching content, or a publishing plan.
3. Do not invent claims, examples, citations, source material, accessibility compliance, copyright permission, or platform performance.
4. Review learning-outcome alignment, timing, source-boundary reminders, accessibility, language review, and publication checks.
5. Do not schedule, upload, publish, share, or authorize any external action.
6. End with a compact editor checklist. The output remains a draft requiring human editorial approval.
"""


def _messages(package: ContentPackage) -> list[LLMMessage]:
    request = package.request
    outcomes = "\n".join(f"- {outcome}" for outcome in request.learning_outcomes)
    segments = "\n".join(
        f"- {segment.title}: {segment.minutes} minutes; purpose: {segment.purpose}"
        for segment in package.segments
    )
    user = f"""Content context
- Topic: {request.topic}
- Format: {request.format.value}
- Audience: {request.audience}
- Duration: {request.duration_minutes} minutes
- Language mode: {request.language_mode.value}
- Approved source scope: {request.approved_source_scope}

Learning outcomes
{outcomes}

Deterministic content plan
{segments}

Publication safeguards already required
{chr(10).join(f'- {item}' for item in package.accuracy_checks)}

Write the constrained internal editorial review now."""
    return [LLMMessage("system", CONTENT_SYSTEM_PROMPT), LLMMessage("user", user)]


def _guardrail(package: ContentPackage, review: str, trace: list[ContentAgentStep]) -> dict:
    report = evaluate_deliverable(
        AutoEvalRequest(
            evaluated_agent=EvaluatedAgent.CONTENT,
            deliverable_title="Agentic content editorial review",
            artifact_text=review,
            required_elements=package.request.learning_outcomes,
            evidence_markers=package.request.learning_outcomes,
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
        f"Learning-outcome reference check {report.quality_signal_percent}%. "
        + (
            "All declared outcomes are referenced."
            if not report.missing_required_elements
            else "Missing outcomes: " + "; ".join(report.missing_required_elements)
        )
    )
    trace.append(ContentAgentStep(ContentStepKind.GUARDRAIL, "AutoEval outcome check", detail))
    return summary


def run_agentic_content_review(
    request: ContentRequest,
    *,
    provider: LLMProvider,
    config: AgenticContentConfig | None = None,
) -> AgenticContentResult:
    """Plan deterministically, then optionally generate a bounded editorial review."""
    settings = config or AgenticContentConfig()
    package = build_content_package(request)
    trace = [
        ContentAgentStep(
            ContentStepKind.PLAN,
            "Deterministic content package created",
            f"{len(package.segments)} segment(s), {package.allocated_minutes}/{request.duration_minutes} minutes allocated.",
        )
    ]
    try:
        result: LLMResult = provider.complete(
            _messages(package), max_tokens=settings.max_tokens, temperature=settings.temperature
        )
    except LLMDisabledError:
        trace.append(
            ContentAgentStep(
                ContentStepKind.NOTE,
                "Editorial review skipped: LLM disabled",
                "The deterministic content package remains available for human editorial review.",
            )
        )
        return AgenticContentResult(
            package=package,
            editorial_review=None,
            generation_enabled=False,
            agent_trace=tuple(trace),
            autoeval=None,
        )
    except Exception as error:  # noqa: BLE001 - provider errors are traceable, not fatal to the package
        trace.append(
            ContentAgentStep(
                ContentStepKind.NOTE,
                "Editorial review skipped: provider error",
                f"{type(error).__name__}: {error}",
            )
        )
        return AgenticContentResult(
            package=package,
            editorial_review=None,
            generation_enabled=False,
            agent_trace=tuple(trace),
            autoeval=None,
        )

    review = result.text
    trace.append(
        ContentAgentStep(
            ContentStepKind.SYNTHESIS,
            "Bounded internal editorial review generated",
            f"provider={result.provider} model={result.model} stop={result.stop_reason}",
        )
    )
    autoeval = _guardrail(package, review, trace)
    return AgenticContentResult(
        package=package,
        editorial_review=review,
        generation_enabled=True,
        agent_trace=tuple(trace),
        autoeval=autoeval,
    )
