"""Bounded internal review for the STEM AI Portfolio Agent."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from axioms.autoeval_agent import AutoEvalRequest, EvaluatedAgent, evaluate_deliverable
from axioms.llm import LLMDisabledError, LLMMessage, LLMProvider, LLMResult
from axioms.portfolio_agent import PortfolioPackage, PortfolioRequest, build_portfolio_package


class PortfolioStepKind(StrEnum):
    PLAN = "plan"
    SYNTHESIS = "synthesis"
    GUARDRAIL = "guardrail"
    NOTE = "note"


@dataclass(frozen=True, slots=True)
class PortfolioAgentStep:
    kind: PortfolioStepKind
    summary: str
    detail: str

    def to_dict(self) -> dict:
        return {"kind": self.kind.value, "summary": self.summary, "detail": self.detail}


@dataclass(frozen=True, slots=True)
class AgenticPortfolioConfig:
    max_tokens: int = 700
    temperature: float = 0.1


@dataclass(frozen=True, slots=True)
class AgenticPortfolioResult:
    package: PortfolioPackage
    portfolio_review: str | None
    generation_enabled: bool
    agent_trace: tuple[PortfolioAgentStep, ...]
    autoeval: dict | None
    human_approval_required: bool = True
    github_action_blocked: bool = True

    def to_dict(self) -> dict:
        return {
            "package": self.package.to_dict(),
            "portfolio_review": self.portfolio_review,
            "generation_enabled": self.generation_enabled,
            "agent_trace": [step.to_dict() for step in self.agent_trace],
            "autoeval": self.autoeval,
            "human_approval_required": self.human_approval_required,
            "github_action_blocked": self.github_action_blocked,
        }


PORTFOLIO_SYSTEM_PROMPT = """You are the Axioms STEM AI Portfolio Agent assisting a researcher.

You must obey every rule below:
1. Work only with the supplied portfolio blueprint, verified evidence records, dataset access details, requested visibility, and repository plan.
2. Produce an internal portfolio-readiness review, not a final README, public portfolio copy, repository content, or deployment plan.
3. Do not invent claims, citations, performance values, research outcomes, licences, permissions, data access, credentials, GitHub metadata, or external links.
4. Check evidence-to-claim traceability, reproducibility, visibility and data-access compatibility, licence/attribution reminders, and removal of sensitive material.
5. Do not create repositories, change visibility, add collaborators, commit, push, open pull requests, deploy, or publish anything.
6. End with a compact researcher checklist. The output remains a draft requiring explicit human approval.
"""


def _messages(package: PortfolioPackage) -> list[LLMMessage]:
    request = package.request
    evidence = "\n".join(
        f"- [{item.evidence_id}] {item.claim} (source: {item.source_reference})"
        for item in request.verified_evidence
    )
    assets = "\n".join(
        f"- {asset.name}: {asset.access_level.value}; permission: {asset.licence_or_permission or 'not supplied'}; "
        f"attribution: {asset.attribution or 'not supplied'}"
        for asset in request.dataset_assets
    ) or "- No dataset assets declared."
    structure = "\n".join(f"- {item.path}: {item.purpose}" for item in package.repository_structure)
    user = f"""Portfolio context
- Project title: {request.project_title}
- Audience: {request.target_audience.value}
- Proposed repository visibility: {request.repository_visibility.value}
- Research summary: {request.research_summary}

Verified evidence records
{evidence}

Declared dataset assets
{assets}

Deterministic repository plan
{structure}

Publication safeguards already required
{chr(10).join(f'- {item}' for item in package.publication_checks)}

Write the constrained internal portfolio-readiness review now."""
    return [LLMMessage("system", PORTFOLIO_SYSTEM_PROMPT), LLMMessage("user", user)]


def _guardrail(package: PortfolioPackage, review: str, trace: list[PortfolioAgentStep]) -> dict:
    evidence_ids = tuple(item.evidence_id for item in package.request.verified_evidence)
    report = evaluate_deliverable(
        AutoEvalRequest(
            evaluated_agent=EvaluatedAgent.PORTFOLIO,
            deliverable_title="Agentic portfolio-readiness review",
            artifact_text=review,
            required_elements=evidence_ids,
            evidence_markers=evidence_ids,
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
        f"Evidence-ID reference check {report.quality_signal_percent}%. "
        + (
            "All declared evidence IDs are referenced."
            if not report.missing_required_elements
            else "Missing evidence IDs: " + ", ".join(report.missing_required_elements)
        )
    )
    trace.append(PortfolioAgentStep(PortfolioStepKind.GUARDRAIL, "AutoEval evidence check", detail))
    return summary


def run_agentic_portfolio_review(
    request: PortfolioRequest,
    *,
    provider: LLMProvider,
    config: AgenticPortfolioConfig | None = None,
) -> AgenticPortfolioResult:
    """Build an evidence-bound plan, then optionally generate an internal readiness review."""
    settings = config or AgenticPortfolioConfig()
    package = build_portfolio_package(request, provider=provider)
    trace = [
        PortfolioAgentStep(
            PortfolioStepKind.PLAN,
            "Deterministic portfolio package created",
            f"{len(package.repository_structure)} planned repository item(s); GitHub actions remain blocked.",
        )
    ]
    try:
        result: LLMResult = provider.complete(
            _messages(package), max_tokens=settings.max_tokens, temperature=settings.temperature
        )
    except LLMDisabledError:
        trace.append(
            PortfolioAgentStep(
                PortfolioStepKind.NOTE,
                "Portfolio review skipped: LLM disabled",
                "The deterministic portfolio package remains available for human review.",
            )
        )
        return AgenticPortfolioResult(
            package=package,
            portfolio_review=None,
            generation_enabled=False,
            agent_trace=tuple(trace),
            autoeval=None,
        )
    except Exception as error:  # noqa: BLE001 - provider errors are traceable, not fatal to the plan
        trace.append(
            PortfolioAgentStep(
                PortfolioStepKind.NOTE,
                "Portfolio review skipped: provider error",
                f"{type(error).__name__}: {error}",
            )
        )
        return AgenticPortfolioResult(
            package=package,
            portfolio_review=None,
            generation_enabled=False,
            agent_trace=tuple(trace),
            autoeval=None,
        )

    review = result.text
    trace.append(
        PortfolioAgentStep(
            PortfolioStepKind.SYNTHESIS,
            "Bounded internal portfolio-readiness review generated",
            f"provider={result.provider} model={result.model} stop={result.stop_reason}",
        )
    )
    autoeval = _guardrail(package, review, trace)
    return AgenticPortfolioResult(
        package=package,
        portfolio_review=review,
        generation_enabled=True,
        agent_trace=tuple(trace),
        autoeval=autoeval,
    )
