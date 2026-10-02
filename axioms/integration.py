"""Read-only system readiness report for the human-governed Axioms MVP."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum

from axioms.agent_registry import specialist_profiles


class IntegrationState(StrEnum):
    IMPLEMENTED = "implemented"
    DEFERRED = "deferred"


@dataclass(frozen=True, slots=True)
class IntegrationComponent:
    name: str
    state: IntegrationState
    detail: str


@dataclass(frozen=True, slots=True)
class SystemReadinessReport:
    specialist_agent_count: int
    components: tuple[IntegrationComponent, ...]
    external_actions_enabled: bool = False
    human_approval_required: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


def build_system_readiness_report() -> SystemReadinessReport:
    """State only implemented capabilities; deferred infrastructure is never represented as active."""
    components = (
        IntegrationComponent("Axioms Core runtime", IntegrationState.IMPLEMENTED, "Persisted plan → approval → execution → final-review lifecycle with per-step agent traces."),
        IntegrationComponent("Specialist registry", IntegrationState.IMPLEMENTED, "Eight review-first profiles with API endpoints."),
        IntegrationComponent("Human approval boundary", IntegrationState.IMPLEMENTED, "Risk-tier classification (LOW/ELEVATED/HIGH) with blocking enforcement on HIGH-risk tasks."),
        IntegrationComponent("API-key authentication", IntegrationState.IMPLEMENTED, "Named multi-key and single-key modes with principal resolution for authenticated approver identity."),
        IntegrationComponent("LLM provider seam", IntegrationState.IMPLEMENTED, "Pluggable Anthropic/OpenAI backends with DisabledProvider safe default. Optional dependency."),
        IntegrationComponent("Crossref DOI verification", IntegrationState.IMPLEMENTED, "Real external metadata verification tool with injectable transport for offline testing."),
        IntegrationComponent("Tavily evidence discovery", IntegrationState.IMPLEMENTED, "Read-only search candidates with provenance and an explicit verification boundary; disabled until configured."),
        IntegrationComponent("Agentic research agent", IntegrationState.IMPLEMENTED, "Tool-using, LLM-synthesising research vertical with bounded generation and AutoEval guardrail."),
        IntegrationComponent("Local deployment", IntegrationState.IMPLEMENTED, "FastAPI, Streamlit, and Docker configuration are present."),
        IntegrationComponent("Redis Streams dispatch", IntegrationState.DEFERRED, "Requires idempotency, retry, dead-letter, trace, and operational tests."),
        IntegrationComponent("Semantic retrieval memory", IntegrationState.DEFERRED, "Requires consent, provenance, retention, deletion, and evaluation controls."),
        IntegrationComponent("LangGraph orchestration", IntegrationState.DEFERRED, "Requires versioned task graphs, failure handling, and checkpoint tests."),
        IntegrationComponent("Live external connectors", IntegrationState.DEFERRED, "Requires least-privilege credentials, dry-run contracts, rate limits, and approval scopes."),
        IntegrationComponent("Cloud deployment", IntegrationState.DEFERRED, "Requires hosting choice, secrets, threat model, backup/restore, and privacy review."),
    )
    return SystemReadinessReport(specialist_agent_count=len(specialist_profiles()), components=components)
