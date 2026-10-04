"""Bounded internal review for the Social Media Agent; it never posts or schedules."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from axioms.autoeval_agent import AutoEvalRequest, EvaluatedAgent, evaluate_deliverable
from axioms.llm import LLMDisabledError, LLMMessage, LLMProvider, LLMResult
from axioms.social_media_agent import (
    SocialMediaPackage,
    SocialMediaRequest,
    build_social_media_package,
)


class SocialMediaStepKind(StrEnum):
    PLAN = "plan"
    SYNTHESIS = "synthesis"
    GUARDRAIL = "guardrail"
    NOTE = "note"


@dataclass(frozen=True, slots=True)
class SocialMediaAgentStep:
    kind: SocialMediaStepKind
    summary: str
    detail: str

    def to_dict(self) -> dict:
        return {"kind": self.kind.value, "summary": self.summary, "detail": self.detail}


@dataclass(frozen=True, slots=True)
class AgenticSocialMediaConfig:
    max_tokens: int = 700
    temperature: float = 0.1


@dataclass(frozen=True, slots=True)
class AgenticSocialMediaResult:
    package: SocialMediaPackage
    editorial_review: str | None
    generation_enabled: bool
    agent_trace: tuple[SocialMediaAgentStep, ...]
    autoeval: dict | None
    human_approval_required: bool = True
    external_action_blocked: bool = True

    def to_dict(self) -> dict:
        return {
            "package": self.package.to_dict(),
            "editorial_review": self.editorial_review,
            "generation_enabled": self.generation_enabled,
            "agent_trace": [step.to_dict() for step in self.agent_trace],
            "autoeval": self.autoeval,
            "human_approval_required": self.human_approval_required,
            "external_action_blocked": self.external_action_blocked,
        }


SOCIAL_MEDIA_SYSTEM_PROMPT = """You are the Axioms Social Media Agent assisting an academic editor.

You must obey every rule below:
1. Work only with the supplied platform drafts, verified facts, approved source scope, audience, objective, and brand voice.
2. Produce an internal editorial review, not revised post copy, final campaign material, or an engagement plan.
3. Do not invent facts, academic credentials, metrics, citations, source material, endorsements, permissions, or platform outcomes.
4. Check factual-source boundaries, platform fit, accessibility, the 48-hour cooldown, recipient consent, and accurate credential representation.
5. Reject engagement bait, misleading hooks, mass direct messages, scraping, and unapproved account automation.
6. Never schedule, upload, publish, share, message, or authorize an external action.
7. End with a compact editor checklist. The output remains a draft requiring explicit human approval.
"""


def _messages(package: SocialMediaPackage) -> list[LLMMessage]:
    request = package.request
    facts = "\n".join(f"- {fact}" for fact in request.verified_facts)
    drafts = "\n".join(
        f"- {draft.platform.value}: {draft.format}; headline: {draft.headline}"
        for draft in package.platform_drafts
    )
    user = f"""Social media context
- Topic: {request.topic}
- Audience: {request.audience}
- Objective: {request.objective.value}
- Brand voice: {request.brand_voice}
- Approved source scope: {request.approved_source_scope}
- Calendar weeks: {request.calendar_weeks}

Verified facts
{facts}

Deterministic platform drafts
{drafts}

External-action safeguards already required
{chr(10).join(f'- {item}' for item in package.publication_checks)}

Write the constrained internal editorial review now."""
    return [LLMMessage("system", SOCIAL_MEDIA_SYSTEM_PROMPT), LLMMessage("user", user)]


def _guardrail(
    package: SocialMediaPackage, review: str, trace: list[SocialMediaAgentStep]
) -> dict:
    report = evaluate_deliverable(
        AutoEvalRequest(
            evaluated_agent=EvaluatedAgent.SOCIAL_MEDIA,
            deliverable_title="Agentic social-media editorial review",
            artifact_text=review,
            required_elements=package.request.verified_facts,
            evidence_markers=package.request.verified_facts,
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
        f"Verified-fact reference check {report.quality_signal_percent}%. "
        + (
            "All declared facts are referenced."
            if not report.missing_required_elements
            else "Missing facts: " + "; ".join(report.missing_required_elements)
        )
    )
    trace.append(SocialMediaAgentStep(SocialMediaStepKind.GUARDRAIL, "AutoEval fact check", detail))
    return summary


def run_agentic_social_media_review(
    request: SocialMediaRequest,
    *,
    provider: LLMProvider,
    config: AgenticSocialMediaConfig | None = None,
) -> AgenticSocialMediaResult:
    """Build deterministic drafts, then optionally generate a bounded internal review."""
    settings = config or AgenticSocialMediaConfig()
    package = build_social_media_package(request, provider=provider)
    trace = [
        SocialMediaAgentStep(
            SocialMediaStepKind.PLAN,
            "Deterministic social-media package created",
            f"{len(package.platform_drafts)} platform draft(s); all external actions remain blocked.",
        )
    ]
    try:
        result: LLMResult = provider.complete(
            _messages(package), max_tokens=settings.max_tokens, temperature=settings.temperature
        )
    except LLMDisabledError:
        trace.append(
            SocialMediaAgentStep(
                SocialMediaStepKind.NOTE,
                "Editorial review skipped: LLM disabled",
                "The deterministic social-media package remains available for human review.",
            )
        )
        return AgenticSocialMediaResult(
            package=package,
            editorial_review=None,
            generation_enabled=False,
            agent_trace=tuple(trace),
            autoeval=None,
        )
    except Exception as error:  # noqa: BLE001 - provider errors are traceable, not fatal to drafts
        trace.append(
            SocialMediaAgentStep(
                SocialMediaStepKind.NOTE,
                "Editorial review skipped: provider error",
                f"{type(error).__name__}: {error}",
            )
        )
        return AgenticSocialMediaResult(
            package=package,
            editorial_review=None,
            generation_enabled=False,
            agent_trace=tuple(trace),
            autoeval=None,
        )

    review = result.text
    trace.append(
        SocialMediaAgentStep(
            SocialMediaStepKind.SYNTHESIS,
            "Bounded internal social-media review generated",
            f"provider={result.provider} model={result.model} stop={result.stop_reason}",
        )
    )
    autoeval = _guardrail(package, review, trace)
    return AgenticSocialMediaResult(
        package=package,
        editorial_review=review,
        generation_enabled=True,
        agent_trace=tuple(trace),
        autoeval=autoeval,
    )
