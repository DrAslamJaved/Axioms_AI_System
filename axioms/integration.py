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
        IntegrationComponent(
            "arXiv preprint discovery",
            IntegrationState.IMPLEMENTED,
            "Read-only Atom discovery with bounded results, in-process cache, rate gate, provenance, and an explicit preprint-verification boundary.",
        ),
        IntegrationComponent(
            "Semantic Scholar discovery",
            IntegrationState.IMPLEMENTED,
            "Keyed, read-only bibliographic discovery with bounded results, in-process cache, rate gate, provenance, and independent-verification boundary.",
        ),
        IntegrationComponent("Agentic research agent", IntegrationState.IMPLEMENTED, "Tool-using, LLM-synthesising research vertical with bounded generation and AutoEval guardrail."),
        IntegrationComponent(
            "Agentic assessment design",
            IntegrationState.IMPLEMENTED,
            "Bounded LLM instructor review over deterministic, source-scoped blueprints; outcome-reference guardrail and student release remain blocked.",
        ),
        IntegrationComponent(
            "Agentic content creation",
            IntegrationState.IMPLEMENTED,
            "Bounded LLM editorial review over deterministic content packages; outcome-reference guardrail and publication remain blocked.",
        ),
        IntegrationComponent(
            "Agentic social-media review",
            IntegrationState.IMPLEMENTED,
            "Bounded LLM editorial review over deterministic social drafts; fact-reference guardrail with scheduling and publication blocked.",
        ),
        IntegrationComponent(
            "Agentic portfolio review",
            IntegrationState.IMPLEMENTED,
            "Bounded LLM readiness review over evidence-bound portfolio packages; evidence-ID guardrail and GitHub actions remain blocked.",
        ),
        IntegrationComponent(
            "Durable local dispatch",
            IntegrationState.IMPLEMENTED,
            "SQLite-backed approved-task queue with idempotency, atomic worker claims, bounded retry, dead-letter state, and no autonomous worker.",
        ),
        IntegrationComponent(
            "Versioned task graphs",
            IntegrationState.IMPLEMENTED,
            "Deterministic routing.v1 DAGs with explicit dependencies, validation, execution layers, and a persisted graph digest.",
        ),
        IntegrationComponent("Consented episodic memory", IntegrationState.IMPLEMENTED, "Completed non-sensitive task summaries are retained only after a separate owner decision."),
        IntegrationComponent("Similarity screening", IntegrationState.IMPLEMENTED, "Local token-shingle comparison against supplied texts; produces human-review signals, never a plagiarism verdict."),
        IntegrationComponent("Local deployment", IntegrationState.IMPLEMENTED, "FastAPI, Streamlit, and Docker configuration are present."),
        IntegrationComponent("Redis Streams dispatch", IntegrationState.DEFERRED, "Requires distributed-worker deployment, leases, delayed retry, recovery, metrics, and operational tests."),
        IntegrationComponent("Semantic retrieval memory", IntegrationState.DEFERRED, "Requires consent, provenance, retention, deletion, and evaluation controls."),
        IntegrationComponent("Parallel graph execution", IntegrationState.DEFERRED, "Requires checkpoint persistence, cancellation, recovery, resource limits, and operational tests."),
        IntegrationComponent("Live external connectors", IntegrationState.DEFERRED, "Requires least-privilege credentials, dry-run contracts, rate limits, and approval scopes."),
        IntegrationComponent("Cloud deployment", IntegrationState.DEFERRED, "Requires hosting choice, secrets, threat model, backup/restore, and privacy review."),
    )
    return SystemReadinessReport(specialist_agent_count=len(specialist_profiles()), components=components)
