"""The genuinely agentic research vertical.

This is the upgrade from "deterministic template filler" to "auditable agent".
Given a research question and candidate sources, :func:`run_agentic_research_brief`
runs a short, bounded, fully logged agent loop:

1. **Tool use.** For every source with a DOI, the agent calls Crossref (a real
   external registry) and independently checks the metadata. A source the caller
   left ``UNVERIFIED`` is promoted to ``METADATA_VERIFIED`` only when Crossref
   confirms the title; genuine discrepancies (wrong title, a "peer reviewed"
   flag on a preprint) are surfaced, never silently accepted.
2. **Governance gate (unchanged).** The upgraded sources are passed through the
   existing :func:`build_research_brief`. Only ``CLAIM_VERIFIED`` sources -- a
   judgement that still requires a human, because deciding whether a source
   *supports a specific claim* is not something a metadata lookup can settle --
   are eligible for synthesis.
3. **Bounded generation.** If a provider is enabled and there are claim-verified
   sources, the LLM is asked to synthesise, and its prompt is constructed from
   the verified claims *only*. It literally cannot cite what it was not given.
   With no provider, the step is skipped and the deterministic brief is returned
   unchanged.
4. **Guardrail.** The synthesis is run back through the deterministic AutoEval
   checker to confirm it grounds on the supplied source IDs.

Every tool call, state change, generation and check is recorded in an ordered
``agent_trace`` so the whole run can be audited and replayed. The agent never
publishes, sends, or performs any external action: the output is a draft held
for human approval.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from axioms.autoeval_agent import AutoEvalRequest, EvaluatedAgent, evaluate_deliverable
from axioms.llm import LLMDisabledError, LLMMessage, LLMProvider, LLMResult
from axioms.research_agent import (
    EvidenceSource,
    ResearchBrief,
    ResearchRequest,
    VerificationStatus,
    build_research_brief,
)
from axioms.tools import CrossrefClient, CrossrefError, titles_match


class StepKind(StrEnum):
    TOOL_CALL = "tool_call"
    STATE_TRANSITION = "state_transition"
    SYNTHESIS = "synthesis"
    GUARDRAIL = "guardrail"
    NOTE = "note"


@dataclass(frozen=True, slots=True)
class AgentStep:
    kind: StepKind
    summary: str
    detail: str

    def to_dict(self) -> dict:
        return {"kind": self.kind.value, "summary": self.summary, "detail": self.detail}


@dataclass(frozen=True, slots=True)
class AgenticResearchConfig:
    title_match_threshold: float = 0.6
    synthesis_max_tokens: int = 1200
    synthesis_temperature: float = 0.2


@dataclass(frozen=True, slots=True)
class AgenticResearchResult:
    brief: ResearchBrief
    synthesis: str | None
    synthesis_enabled: bool
    agent_trace: tuple[AgentStep, ...]
    discrepancies: tuple[str, ...]
    autoeval: dict | None
    human_review_required: bool = True

    def to_dict(self) -> dict:
        return {
            "brief": self.brief.to_dict(),
            "synthesis": self.synthesis,
            "synthesis_enabled": self.synthesis_enabled,
            "agent_trace": [step.to_dict() for step in self.agent_trace],
            "discrepancies": list(self.discrepancies),
            "autoeval": self.autoeval,
            "human_review_required": self.human_review_required,
        }


SYNTHESIS_SYSTEM_PROMPT = (
    "You are the Axioms research-synthesis agent. You will be given a research "
    "question and a numbered list of claims, each already verified against its "
    "source and tagged with a source ID such as [S01].\n"
    "Rules you must follow exactly:\n"
    "1. Use ONLY the verified claims provided. Do not add facts, figures, or "
    "sources from your own knowledge.\n"
    "2. Cite every statement with the source ID it comes from, e.g. [S01].\n"
    "3. If the verified claims are insufficient to answer part of the question, "
    "say so explicitly rather than guessing.\n"
    "4. Do not make novelty, superiority, or comparative-performance claims that "
    "are not directly stated in a verified claim.\n"
    "5. End with a short 'Limitations' note describing what the verified evidence "
    "does not cover.\n"
    "This is a draft for human review; it is not a published conclusion."
)


def _build_synthesis_messages(
    request: ResearchRequest, verified_claims: tuple[str, ...]
) -> list[LLMMessage]:
    numbered = "\n".join(f"{index}. {claim}" for index, claim in enumerate(verified_claims, start=1))
    user = (
        f"Research question:\n{request.research_question}\n\n"
        f"Scope:\n{request.scope}\n\n"
        f"Analysis dimensions: {', '.join(request.analysis_dimensions)}\n\n"
        f"Verified claims (the only material you may use):\n{numbered}\n\n"
        "Write a constrained synthesis that obeys every rule in the system prompt."
    )
    return [LLMMessage("system", SYNTHESIS_SYSTEM_PROMPT), LLMMessage("user", user)]


def _verify_sources(
    request: ResearchRequest,
    crossref: CrossrefClient,
    config: AgenticResearchConfig,
    trace: list[AgentStep],
    discrepancies: list[str],
) -> ResearchRequest:
    """Run the Crossref tool over every source; return a request with any upgrades."""

    upgraded: list[EvidenceSource] = []
    for source in request.sources:
        if not source.doi:
            trace.append(
                AgentStep(StepKind.NOTE, f"{source.source_id}: no DOI", "Cannot metadata-verify without a DOI.")
            )
            upgraded.append(source)
            continue
        trace.append(
            AgentStep(StepKind.TOOL_CALL, f"Crossref lookup {source.source_id}", f"DOI {source.doi}")
        )
        try:
            record = crossref.lookup(source.doi)
        except CrossrefError as error:
            trace.append(
                AgentStep(
                    StepKind.NOTE,
                    f"{source.source_id}: Crossref unavailable",
                    f"{error} — metadata verification skipped; source left as-is.",
                )
            )
            upgraded.append(source)
            continue

        match = titles_match(source.title, record.title, threshold=config.title_match_threshold)
        if record.is_preprint and source.peer_reviewed:
            note = (
                f"{source.source_id}: caller marked peer-reviewed, but Crossref type is "
                f"'{record.work_type}' (a preprint)."
            )
            discrepancies.append(note)
            trace.append(AgentStep(StepKind.GUARDRAIL, f"{source.source_id}: preprint/peer-review mismatch", note))
        if not match:
            note = (
                f"{source.source_id}: caller title differs from Crossref title "
                f"('{record.title}'). Not auto-verified."
            )
            discrepancies.append(note)
            trace.append(AgentStep(StepKind.NOTE, f"{source.source_id}: title mismatch", note))
            upgraded.append(source)
            continue

        if source.verification_status is VerificationStatus.UNVERIFIED:
            promoted = replace(
                source,
                verification_status=VerificationStatus.METADATA_VERIFIED,
                verification_evidence=record.summary(),
            )
            trace.append(
                AgentStep(
                    StepKind.STATE_TRANSITION,
                    f"{source.source_id}: unverified → metadata_verified",
                    f"Title confirmed by Crossref. {record.summary()}",
                )
            )
            upgraded.append(promoted)
        else:
            trace.append(
                AgentStep(
                    StepKind.NOTE,
                    f"{source.source_id}: Crossref corroborates metadata",
                    f"Existing status '{source.verification_status.value}' left unchanged. {record.summary()}",
                )
            )
            upgraded.append(source)
    return replace(request, sources=tuple(upgraded))


def _run_synthesis(
    request: ResearchRequest,
    brief: ResearchBrief,
    provider: LLMProvider,
    config: AgenticResearchConfig,
    trace: list[AgentStep],
) -> str | None:
    if not brief.verified_claims:
        trace.append(
            AgentStep(
                StepKind.NOTE,
                "Synthesis skipped: no claim-verified sources",
                "No source has recorded claim-level verification, so there is nothing to synthesise. "
                "Verify claims to unlock constrained synthesis.",
            )
        )
        return None
    messages = _build_synthesis_messages(request, brief.verified_claims)
    try:
        result: LLMResult = provider.complete(
            messages,
            max_tokens=config.synthesis_max_tokens,
            temperature=config.synthesis_temperature,
        )
    except LLMDisabledError:
        trace.append(
            AgentStep(
                StepKind.NOTE,
                "Synthesis skipped: LLM disabled",
                "AXIOMS_LLM_PROVIDER is disabled. The deterministic brief is returned unchanged.",
            )
        )
        return None
    except Exception as error:  # noqa: BLE001 - provider failures are captured in the agent trace
        trace.append(
            AgentStep(
                StepKind.NOTE,
                "Synthesis skipped: provider error",
                f"{type(error).__name__}: {error}",
            )
        )
        return None
    trace.append(
        AgentStep(
            StepKind.SYNTHESIS,
            f"Bounded synthesis over {len(brief.verified_claims)} verified claim(s)",
            f"provider={result.provider} model={result.model} stop={result.stop_reason}",
        )
    )
    return result.text


def _guardrail_check(
    request: ResearchRequest,
    brief: ResearchBrief,
    synthesis: str,
    trace: list[AgentStep],
) -> dict:
    verified_ids = tuple(
        source.source_id
        for source in request.sources
        if source.verification_status is VerificationStatus.CLAIM_VERIFIED
    )[:20]
    report = evaluate_deliverable(
        AutoEvalRequest(
            evaluated_agent=EvaluatedAgent.RESEARCH,
            deliverable_title="Agentic research synthesis",
            artifact_text=synthesis,
            required_elements=verified_ids,
            evidence_markers=verified_ids,
            public_facing=False,
            declared_sensitive_data=False,
        )
    )
    summary = {
        "quality_signal_percent": report.quality_signal_percent,
        "missing_required_elements": list(report.missing_required_elements),
        "checks": [{"name": c.name, "status": c.status.value} for c in report.checks],
        "artifact_sha256": report.artifact_sha256,
    }
    detail = (
        f"Grounding check {report.quality_signal_percent}%. "
        + (
            "All verified source IDs are cited."
            if not report.missing_required_elements
            else "Uncited verified sources: " + ", ".join(report.missing_required_elements)
        )
    )
    trace.append(AgentStep(StepKind.GUARDRAIL, "AutoEval grounding check on synthesis", detail))
    return summary


def run_agentic_research_brief(
    request: ResearchRequest,
    *,
    provider: LLMProvider,
    crossref: CrossrefClient | None = None,
    config: AgenticResearchConfig | None = None,
) -> AgenticResearchResult:
    """Run the bounded, auditable research agent. Never performs an external action."""

    request.validate()
    config = config or AgenticResearchConfig()
    crossref = crossref or CrossrefClient()
    trace: list[AgentStep] = []
    discrepancies: list[str] = []

    verified_request = _verify_sources(request, crossref, config, trace, discrepancies)
    brief = build_research_brief(verified_request)
    synthesis = _run_synthesis(verified_request, brief, provider, config, trace)
    autoeval = _guardrail_check(verified_request, brief, synthesis, trace) if synthesis else None

    return AgenticResearchResult(
        brief=brief,
        synthesis=synthesis,
        synthesis_enabled=synthesis is not None,
        agent_trace=tuple(trace),
        discrepancies=tuple(discrepancies),
        autoeval=autoeval,
    )
