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
        IntegrationComponent("API-key authentication", IntegrationState.IMPLEMENTED, "Named role-bearing keys distinguish viewers, approvers, and administrators; principal resolution binds approval and memory-governance decisions to the authenticated named key, while only administrators may override a HIGH-risk block."),
        IntegrationComponent(
            "LLM provider seam",
            IntegrationState.IMPLEMENTED,
            "Pluggable Anthropic/OpenAI backends with a DisabledProvider safe default; all specialist agents use bounded synthesis where configured, while AutoEval keeps deterministic checks authoritative and limits LLM use to an optional qualitative summary.",
        ),
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
            "Bounded LLM planning synthesis supports validated Urdu or bilingual internal notes over deterministic content packages; outcome-reference guardrail and publication remain blocked.",
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
            "SQLite-backed approved-task queue with idempotency, atomic leased worker claims, bounded retry, dead-letter state, and no autonomous worker.",
        ),
        IntegrationComponent(
            "Versioned task graphs",
            IntegrationState.IMPLEMENTED,
            "Deterministic routing.v1 DAGs with explicit dependencies, validation, execution layers, and a persisted graph digest.",
        ),
        IntegrationComponent(
            "Opt-in local parallel execution",
            IntegrationState.IMPLEMENTED,
            "Independent validated graph-layer drafts can run locally with deterministic result ordering and a configurable 1–4 worker cap; sequential execution remains the default and final human review is required.",
        ),
        IntegrationComponent(
            "Cooperative local cancellation",
            IntegrationState.IMPLEMENTED,
            "A named human can stop an approved task immediately or a running task at a persisted graph-layer checkpoint; partial drafts are discarded.",
        ),
        IntegrationComponent(
            "Interrupted task recovery",
            IntegrationState.IMPLEMENTED,
            "A named operator can attest that local execution stopped, discard any partial work, and return a stranded task to pending approval for a fresh decision.",
        ),
        IntegrationComponent(
            "Cross-agent AutoEval",
            IntegrationState.IMPLEMENTED,
            "A deterministic, hash-linked consolidation reviews completed local specialist drafts against declared marker contracts; it cannot alter drafts or grant release approval.",
        ),
        IntegrationComponent(
            "Approval-gated task revisions",
            IntegrationState.IMPLEMENTED,
            "A final-review rejection can create a linked new task with the reviewer note as revision context; the rejected task is unchanged and the revision requires fresh approval before execution.",
        ),
        IntegrationComponent(
            "Read-only task lineage",
            IntegrationState.IMPLEMENTED,
            "Authenticated reviewers can inspect a revision family as projected metadata, without drafts, review notes, approval changes, or external action.",
        ),
        IntegrationComponent(
            "Revision comparison",
            IntegrationState.IMPLEMENTED,
            "Authenticated reviewers can compare a linked revision with its direct parent, including the recorded rejection note and typed request differences; it cannot approve, edit, or execute either task.",
        ),
        IntegrationComponent(
            "Approved PKB preference injection",
            IntegrationState.IMPLEMENTED,
            "Owner-approved preferences can be scoped to specialist agents, snapshotted into a proposed task, and appended only to matching local review drafts; they never become facts or bypass governance.",
        ),
        IntegrationComponent(
            "Local operations summary",
            IntegrationState.IMPLEMENTED,
            "A read-only authenticated endpoint exposes aggregate task states and local worker-lease health; it cannot claim, renew, run, recover, or alter work.",
        ),
        IntegrationComponent(
            "SQLite backup restore drill",
            IntegrationState.IMPLEMENTED,
            "An explicit local CLI creates only new backups and validates a disposable restore copy; it never overwrites a live database or schedules backups.",
        ),
        IntegrationComponent("Consented episodic memory", IntegrationState.IMPLEMENTED, "Completed non-sensitive task summaries require a separate owner decision, have a bounded retention period, expire into a minimal tombstone, and retain lifecycle provenance without deleted content."),
        IntegrationComponent("Similarity screening", IntegrationState.IMPLEMENTED, "Local token-shingle comparison against supplied texts; produces human-review signals, never a plagiarism verdict."),
        IntegrationComponent("Conservative document ingestion", IntegrationState.IMPLEMENTED, "Explicitly confirmed non-sensitive PDF, DOCX, and UTF-8 text files are bounded, extracted, and stored locally with metadata-only API responses. An administrator can permanently delete the local content; task attachment snapshots keep only non-content provenance."),
        IntegrationComponent("Reference-document attachment ledger", IntegrationState.IMPLEMENTED, "An approver can attach immutable metadata and a hash for an ingested local document to a proposed task before execution approval; the attachment is traceable, locked after approval, and never injects document text into an agent."),
        IntegrationComponent("Structured local audit events", IntegrationState.IMPLEMENTED, "API requests receive safe correlation IDs and emit JSON lifecycle metadata through a strict allowlist; request bodies, task goals, draft content, and document text are excluded."),
        IntegrationComponent("Provider token accounting", IntegrationState.IMPLEMENTED, "Non-zero provider-reported token totals are appended locally and exposed only through an authenticated aggregate summary. Prompts, outputs, prices, billing data, and remote telemetry are excluded."),
        IntegrationComponent("Local operations summary", IntegrationState.IMPLEMENTED, "Authenticated operators can inspect aggregate task and local dispatch lifecycle counts plus worker-lease health. The summary contains no task, job, or draft content and cannot reclaim work, execute tasks, or send telemetry."),
        IntegrationComponent("Task work-queue projection", IntegrationState.IMPLEMENTED, "The authenticated task-list endpoint returns only lifecycle and count metadata. Goals, drafts, Personal KB values, document metadata, and reviewer notes are excluded; content-bearing single-task review requires an approver or administrator in named-key deployments."),
        IntegrationComponent("Task status polling", IntegrationState.IMPLEMENTED, "An authenticated metadata-only status endpoint supports local review dashboards and polling without exposing task requests, drafts, preferences, documents, or reviewer notes."),
        IntegrationComponent("Approver trace projection", IntegrationState.IMPLEMENTED, "An approver or administrator can inspect a task's read-only lifecycle event kind, agent, and timestamp. Task requests, drafts, document metadata, preference values, reviewer notes, and persisted trace summaries are excluded."),
        IntegrationComponent("Local deployment", IntegrationState.IMPLEMENTED, "FastAPI, Streamlit, and Docker configuration are present. The console includes manual aggregate operations, metadata-only task-status, approver-only trace, paginated task-work-queue, and provider-usage inspectors. Queue navigation is explicitly user-triggered, with prior metadata-only pages held only in the local browser session; there is no auto-refresh, execution control, cost estimation, or telemetry."),
        IntegrationComponent("Redis Streams dispatch", IntegrationState.DEFERRED, "Requires distributed-worker deployment, leases, delayed retry, recovery, metrics, and operational tests."),
        IntegrationComponent("Semantic retrieval memory", IntegrationState.DEFERRED, "Requires consent, provenance, retention, deletion, and evaluation controls."),
        IntegrationComponent("Distributed parallel graph execution", IntegrationState.DEFERRED, "Requires distributed recovery, worker leases, and operational tests."),
        IntegrationComponent("Live external connectors", IntegrationState.DEFERRED, "Requires least-privilege credentials, dry-run contracts, rate limits, and approval scopes."),
        IntegrationComponent("Cloud deployment", IntegrationState.DEFERRED, "Requires hosting choice, secrets, threat model, backup/restore, and privacy review."),
    )
    return SystemReadinessReport(specialist_agent_count=len(specialist_profiles()), components=components)
