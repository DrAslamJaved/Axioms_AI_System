from __future__ import annotations

import os
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field

from axioms.agent_registry import specialist_profiles
from axioms.assessment_agent import (
    AssessmentRequest,
    AssessmentType,
    BloomLevel,
    Difficulty,
    LearningOutcome,
    build_assessment_blueprint,
    export_instructor_docx,
    export_student_docx,
)
from axioms.assessment_agent_ai import run_agentic_assessment_design
from axioms.audit_log import bind_request_id, log_event, reset_request_id, select_request_id
from axioms.autoeval_agent import (
    AutoEvalRequest,
    EvaluatedAgent,
    evaluate_deliverable,
)
from axioms.autoeval_agent import export_docx as export_autoeval_docx
from axioms.content_agent import ContentFormat, ContentRequest, LanguageMode, build_content_package
from axioms.content_agent import export_docx as export_content_docx
from axioms.content_agent_ai import run_agentic_content_review
from axioms.core import AxiomsCore, BlockedApprovalError, TaskStateError
from axioms.document_ingestion import DocumentIngestionError, DocumentStore
from axioms.episodic_memory import MemoryDecision
from axioms.integration import build_system_readiness_report
from axioms.lecture_agent import LectureRequest, build_lecture_plan, export_docx
from axioms.llm import LLMConfigurationError, get_provider
from axioms.models import AgentName, ApprovalDecision, TaskRequest, TaskStatus
from axioms.personal_kb import (
    FeedbackRecord,
    PreferenceCategory,
    PreferenceProposal,
    ProposalDecision,
)
from axioms.policy import STRICT_MODE
from axioms.portfolio_agent import (
    DataAccessLevel,
    DatasetAsset,
    PortfolioAudience,
    PortfolioEvidence,
    PortfolioRequest,
    RepositoryVisibility,
    build_portfolio_package,
)
from axioms.portfolio_agent import export_docx as export_portfolio_docx
from axioms.portfolio_agent_ai import run_agentic_portfolio_review
from axioms.research_agent import (
    EvidenceSource,
    PublicationKind,
    ResearchRequest,
    VerificationStatus,
    build_research_brief,
)
from axioms.research_agent import export_docx as export_research_docx
from axioms.research_agent_ai import run_agentic_research_brief
from axioms.security import (
    AccessRole,
    auth_mode,
    ensure_role,
    require_api_key,
    require_role,
    resolve_principal,
    resolve_role,
)
from axioms.similarity import ComparisonText, SimilarityRequest, screen_similarity
from axioms.social_media_agent import (
    RecentSocialPost,
    SocialMediaRequest,
    SocialObjective,
    SocialPlatform,
    build_social_media_package,
)
from axioms.social_media_agent import export_docx as export_social_media_docx
from axioms.social_media_agent_ai import run_agentic_social_media_review
from axioms.tools import (
    ArxivClient,
    ArxivError,
    CrossrefClient,
    SemanticScholarClient,
    SemanticScholarError,
    TavilyClient,
    TavilyError,
)
from axioms.usage import UsageStore
from axioms.writing_agent import DocumentType, WritingRequest, build_writing_draft
from axioms.writing_agent import export_docx as export_writing_docx

app = FastAPI(title="Axioms AI System", version="0.2.0")
core = AxiomsCore()
document_store = DocumentStore()
_ARXIV_CLIENT = ArxivClient()
_SEMANTIC_SCHOLAR_CLIENTS: dict[str, SemanticScholarClient] = {}

DOCX_MEDIA = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
ROLE_DEPENDENCY = Depends(resolve_role)
DOCUMENT_FILE = File(...)
DOCUMENT_NON_SENSITIVE_CONFIRMATION = Form(...)


@app.middleware("http")
async def correlate_and_audit_request(request: Request, call_next):
    """Add a safe correlation ID and emit metadata-only local request audit events."""
    request_id = select_request_id(request.headers.get("X-Request-ID"))
    token = bind_request_id(request_id)
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        log_event(
            "http_request_failed",
            method=request.method,
            path=request.url.path,
            status_code=500,
            duration_ms=round((time.perf_counter() - started) * 1_000),
        )
        raise
    else:
        response.headers["X-Request-ID"] = request_id
        log_event(
            "http_request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round((time.perf_counter() - started) * 1_000),
        )
        return response
    finally:
        reset_request_id(token)


def _crossref_client() -> CrossrefClient:
    return CrossrefClient(mailto=os.getenv("CROSSREF_MAILTO") or None)


def _tavily_client() -> TavilyClient:
    return TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


def _arxiv_client() -> ArxivClient:
    """Keep the small in-process arXiv cache and rate gate across API requests."""
    return _ARXIV_CLIENT


def _semantic_scholar_client() -> SemanticScholarClient:
    """Reuse a client per configured key so cache and rate limits survive API requests."""
    api_key = (os.getenv("SEMANTIC_SCHOLAR_API_KEY") or "").strip()
    client = _SEMANTIC_SCHOLAR_CLIENTS.get(api_key)
    if client is None:
        client = SemanticScholarClient(api_key)
        _SEMANTIC_SCHOLAR_CLIENTS[api_key] = client
    return client


def _docx_response(write: Callable[[Path], None], filename: str, background: BackgroundTasks) -> FileResponse:
    """Export a DOCX to a unique per-request temp file, then clean it up.

    The MVP wrote every DOCX to a single fixed path (e.g. ``artifacts/lecture_plan.docx``),
    so two concurrent requests could overwrite each other and one caller could receive
    another caller's document. Each request now gets its own temp file, removed after the
    response is sent.
    """

    handle, tmp = tempfile.mkstemp(prefix="axioms_", suffix=".docx")
    os.close(handle)
    path = Path(tmp)
    write(path)
    background.add_task(os.remove, tmp)
    return FileResponse(path, filename=filename, media_type=DOCX_MEDIA)


class TaskIn(BaseModel):
    goal: str = Field(min_length=8, max_length=4000)
    audience: str = "unspecified"
    deadline: str | None = None
    constraints: list[str] = Field(default_factory=list)
    external_delivery: bool = False


class ReferenceDocumentAttachmentIn(BaseModel):
    document_id: str = Field(min_length=5, max_length=100)
    attached_by: str = Field(min_length=2, max_length=200)


class ApprovalIn(BaseModel):
    decision: ApprovalDecision
    approved_by: str = Field(min_length=2, max_length=200)
    note: str | None = Field(default=None, max_length=2000)
    override_blocking: bool = False


class CancellationIn(BaseModel):
    requested_by: str = Field(min_length=2, max_length=200)
    note: str | None = Field(default=None, max_length=2000)


class RecoveryIn(BaseModel):
    recovered_by: str = Field(min_length=2, max_length=200)
    note: str | None = Field(default=None, max_length=2000)
    confirm_execution_stopped: bool = False


class RevisionIn(BaseModel):
    requested_by: str = Field(min_length=2, max_length=200)


class LecturePlanIn(BaseModel):
    topic: str = Field(min_length=2, max_length=300)
    course_level: str = Field(min_length=2, max_length=100)
    duration_minutes: int = Field(ge=30, le=240)
    audience: str = Field(min_length=2, max_length=300)
    prior_knowledge: str = Field(default="Not yet specified", max_length=1000)
    learning_outcomes: list[str] = Field(min_length=2, max_length=6)
    application_context: str | None = Field(default=None, max_length=500)
    include_computational_activity: bool = False

    def to_agent_request(self) -> LectureRequest:
        data = self.model_dump()
        data["learning_outcomes"] = tuple(self.learning_outcomes)
        return LectureRequest(**data)


class WritingDraftIn(BaseModel):
    document_type: DocumentType
    subject: str = Field(min_length=2, max_length=300)
    audience: str = Field(min_length=2, max_length=300)
    purpose: str = Field(min_length=5, max_length=2000)
    key_points: list[str] = Field(min_length=1, max_length=10)
    verified_facts: list[str] = Field(min_length=1, max_length=20)
    tone: str = Field(default="clear, precise, approachable, and intellectually rigorous", max_length=300)
    references: list[str] = Field(default_factory=list, max_length=30)
    external_delivery: bool = False

    def to_agent_request(self) -> WritingRequest:
        data = self.model_dump()
        data["key_points"] = tuple(self.key_points)
        data["verified_facts"] = tuple(self.verified_facts)
        data["references"] = tuple(self.references)
        return WritingRequest(**data)


class EvidenceSourceIn(BaseModel):
    source_id: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=2, max_length=1000)
    authors: list[str] = Field(min_length=1, max_length=30)
    year: int = Field(ge=1600, le=2100)
    publication_kind: PublicationKind
    doi: str | None = Field(default=None, max_length=500)
    url: str | None = Field(default=None, max_length=2000)
    peer_reviewed: bool = False
    supported_claim: str | None = Field(default=None, max_length=2000)
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    verification_evidence: str | None = Field(default=None, max_length=2000)

    def to_evidence_source(self) -> EvidenceSource:
        data = self.model_dump()
        data["authors"] = tuple(self.authors)
        return EvidenceSource(**data)


class ResearchBriefIn(BaseModel):
    research_question: str = Field(min_length=8, max_length=4000)
    scope: str = Field(min_length=5, max_length=4000)
    sources: list[EvidenceSourceIn] = Field(min_length=1, max_length=100)
    analysis_dimensions: list[str] = Field(
        default_factory=lambda: ["methods", "datasets", "metrics", "limitations"],
        min_length=1,
        max_length=10,
    )
    target_venue: str | None = Field(default=None, max_length=300)

    def to_agent_request(self) -> ResearchRequest:
        data = self.model_dump(exclude={"sources", "analysis_dimensions"})
        return ResearchRequest(
            **data,
            sources=tuple(source.to_evidence_source() for source in self.sources),
            analysis_dimensions=tuple(self.analysis_dimensions),
        )


class ResearchDiscoveryIn(BaseModel):
    query: str = Field(min_length=8, max_length=2000)
    max_results: int = Field(default=5, ge=1, le=10)


class LearningOutcomeIn(BaseModel):
    outcome_id: str = Field(min_length=1, max_length=50)
    text: str = Field(min_length=5, max_length=1000)
    bloom_level: BloomLevel

    def to_learning_outcome(self) -> LearningOutcome:
        return LearningOutcome(**self.model_dump())


class AssessmentBlueprintIn(BaseModel):
    topic: str = Field(min_length=2, max_length=300)
    course_level: str = Field(min_length=2, max_length=100)
    assessment_type: AssessmentType
    duration_minutes: int = Field(ge=10, le=240)
    total_marks: int = Field(ge=1, le=500)
    question_count: int = Field(ge=1, le=20)
    learning_outcomes: list[LearningOutcomeIn] = Field(min_length=1, max_length=12)
    approved_source_scope: str = Field(min_length=5, max_length=4000)
    difficulties: list[Difficulty] = Field(default_factory=lambda: [Difficulty.MODERATE])
    require_handwritten_work: bool = True
    require_reflection: bool = True
    include_personalised_context: bool = True

    def to_agent_request(self) -> AssessmentRequest:
        data = self.model_dump(exclude={"learning_outcomes", "difficulties"})
        return AssessmentRequest(
            **data,
            learning_outcomes=tuple(item.to_learning_outcome() for item in self.learning_outcomes),
            difficulties=tuple(self.difficulties),
        )


class ContentPackageIn(BaseModel):
    topic: str = Field(min_length=2, max_length=300)
    format: ContentFormat
    audience: str = Field(min_length=2, max_length=300)
    duration_minutes: int = Field(ge=3, le=240)
    approved_source_scope: str = Field(min_length=5, max_length=4000)
    learning_outcomes: list[str] = Field(min_length=1, max_length=6)
    language_mode: LanguageMode = LanguageMode.ENGLISH
    application_context: str | None = Field(default=None, max_length=1000)
    keywords: list[str] = Field(default_factory=list, max_length=8)

    def to_agent_request(self) -> ContentRequest:
        data = self.model_dump()
        data["learning_outcomes"] = tuple(self.learning_outcomes)
        data["keywords"] = tuple(self.keywords)
        return ContentRequest(**data)


class RecentSocialPostIn(BaseModel):
    platform: SocialPlatform
    topic: str = Field(min_length=2, max_length=300)
    hours_since_publication: int = Field(ge=0, le=8760)

    def to_agent_request(self) -> RecentSocialPost:
        return RecentSocialPost(**self.model_dump())


class SocialMediaPackageIn(BaseModel):
    topic: str = Field(min_length=2, max_length=300)
    audience: str = Field(min_length=2, max_length=300)
    platforms: list[SocialPlatform] = Field(min_length=1, max_length=5)
    objective: SocialObjective = SocialObjective.EDUCATE
    approved_source_scope: str = Field(min_length=5, max_length=4000)
    verified_facts: list[str] = Field(min_length=1, max_length=8)
    brand_voice: str = Field(default="clear, respectful, and evidence-aware", max_length=300)
    call_to_action: str | None = Field(default=None, max_length=500)
    calendar_weeks: int = Field(default=4, ge=1, le=4)
    recent_posts: list[RecentSocialPostIn] = Field(default_factory=list, max_length=100)

    def to_agent_request(self) -> SocialMediaRequest:
        data = self.model_dump(exclude={"platforms", "verified_facts", "recent_posts"})
        return SocialMediaRequest(
            **data,
            platforms=tuple(self.platforms),
            verified_facts=tuple(self.verified_facts),
            recent_posts=tuple(item.to_agent_request() for item in self.recent_posts),
        )


class PortfolioEvidenceIn(BaseModel):
    evidence_id: str = Field(min_length=1, max_length=50)
    claim: str = Field(min_length=5, max_length=2000)
    source_reference: str = Field(min_length=3, max_length=2000)
    verified: bool

    def to_agent_request(self) -> PortfolioEvidence:
        return PortfolioEvidence(**self.model_dump())


class DatasetAssetIn(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    access_level: DataAccessLevel
    licence_or_permission: str | None = Field(default=None, max_length=1000)
    attribution: str | None = Field(default=None, max_length=1000)

    def to_agent_request(self) -> DatasetAsset:
        return DatasetAsset(**self.model_dump())


class PortfolioPackageIn(BaseModel):
    project_title: str = Field(min_length=2, max_length=300)
    research_summary: str = Field(min_length=10, max_length=4000)
    target_audience: PortfolioAudience
    repository_visibility: RepositoryVisibility
    verified_evidence: list[PortfolioEvidenceIn] = Field(min_length=1, max_length=12)
    dataset_assets: list[DatasetAssetIn] = Field(default_factory=list, max_length=30)
    include_demo_plan: bool = True
    include_notebook_plan: bool = True

    def to_agent_request(self) -> PortfolioRequest:
        data = self.model_dump(exclude={"verified_evidence", "dataset_assets"})
        return PortfolioRequest(
            **data,
            verified_evidence=tuple(item.to_agent_request() for item in self.verified_evidence),
            dataset_assets=tuple(item.to_agent_request() for item in self.dataset_assets),
        )


class AutoEvalReportIn(BaseModel):
    evaluated_agent: EvaluatedAgent
    deliverable_title: str = Field(min_length=2, max_length=300)
    artifact_text: str = Field(min_length=1, max_length=20000)
    required_elements: list[str] = Field(min_length=1, max_length=20)
    evidence_markers: list[str] = Field(default_factory=list, max_length=20)
    public_facing: bool = False
    declared_sensitive_data: bool = False

    def to_agent_request(self) -> AutoEvalRequest:
        data = self.model_dump()
        data["required_elements"] = tuple(self.required_elements)
        data["evidence_markers"] = tuple(self.evidence_markers)
        return AutoEvalRequest(**data)


class FeedbackIn(BaseModel):
    agent: AgentName
    artifact_reference: str = Field(min_length=2, max_length=500)
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)

    def to_record(self) -> FeedbackRecord:
        return FeedbackRecord(**self.model_dump())


class PreferenceProposalIn(BaseModel):
    category: PreferenceCategory
    preference_key: str = Field(min_length=2, max_length=100)
    preference_value: str = Field(min_length=2, max_length=1000)
    rationale: str = Field(min_length=5, max_length=2000)
    feedback_id: str | None = Field(default=None, max_length=100)
    agent_types: list[AgentName] = Field(default_factory=list, max_length=8)

    def to_proposal(self) -> PreferenceProposal:
        data = self.model_dump()
        data["agent_types"] = tuple(self.agent_types)
        return PreferenceProposal(**data)


class ProposalDecisionIn(BaseModel):
    decision: ProposalDecision
    note: str | None = Field(default=None, max_length=2000)


class MemoryDecisionIn(BaseModel):
    decision: MemoryDecision
    approved_by: str = Field(min_length=2, max_length=200)
    note: str | None = Field(default=None, max_length=2000)
    retention_days: int = Field(default=30, ge=1, le=365)


class MemoryDeleteIn(BaseModel):
    deleted_by: str = Field(min_length=2, max_length=200)
    note: str | None = Field(default=None, max_length=2000)


class ComparisonTextIn(BaseModel):
    reference_id: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=50000)

    def to_comparison_text(self) -> ComparisonText:
        return ComparisonText(**self.model_dump())


class SimilarityScreenIn(BaseModel):
    submitted_text: str = Field(min_length=1, max_length=100000)
    comparison_texts: list[ComparisonTextIn] = Field(min_length=1, max_length=50)
    shingle_size: int = Field(default=3, ge=1, le=8)
    review_threshold: float = Field(default=0.2, ge=0.0, le=1.0)

    def to_similarity_request(self) -> SimilarityRequest:
        return SimilarityRequest(
            submitted_text=self.submitted_text,
            comparison_texts=tuple(item.to_comparison_text() for item in self.comparison_texts),
            shingle_size=self.shingle_size,
            review_threshold=self.review_threshold,
        )


class DispatchIn(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=200)
    max_attempts: int = Field(default=2, ge=1, le=3)


class DispatchClaimIn(BaseModel):
    worker_id: str = Field(min_length=2, max_length=200)


class DispatchFinishIn(BaseModel):
    worker_id: str = Field(min_length=2, max_length=200)
    succeeded: bool
    error: str | None = Field(default=None, max_length=2000)
    retryable: bool = True


class DispatchRenewIn(BaseModel):
    worker_id: str = Field(min_length=2, max_length=200)
    lease_seconds: int = Field(default=120, ge=30, le=900)


class DispatchRunIn(BaseModel):
    worker_id: str = Field(min_length=2, max_length=200)


@app.get("/health")
def health() -> dict[str, str]:
    try:
        provider_name = get_provider().name
    except Exception:  # noqa: BLE001 - readiness reports provider configuration without failing
        provider_name = "misconfigured"
    return {
        "status": "ok",
        "mode": "human-governed",
        "auth": auth_mode(),
        "llm_provider": provider_name,
        "approval_mode": os.getenv("AXIOMS_APPROVAL_MODE", STRICT_MODE),
    }


@app.get("/agents")
def list_agents() -> list[dict]:
    return [profile.to_dict() for profile in specialist_profiles()]


@app.get("/system/readiness")
def system_readiness() -> dict:
    return build_system_readiness_report().to_dict()


@app.get("/operations/summary")
def operations_summary(_auth: None = Depends(require_api_key)) -> dict:
    """Return read-only aggregate task and local-worker health for human operators."""
    return core.operational_summary()


@app.get("/usage/summary")
def usage_summary(_auth: None = Depends(require_api_key)) -> dict:
    """Return aggregate local provider token counts; never prompts, outputs, or billing estimates."""
    return UsageStore().summary()


@app.post("/documents")
async def ingest_document(
    document: UploadFile = DOCUMENT_FILE,
    confirmed_non_sensitive: bool = DOCUMENT_NON_SENSITIVE_CONFIRMATION,
    _auth: None = Depends(require_role(AccessRole.APPROVER)),
) -> dict:
    """Extract and retain one explicitly non-sensitive local reference document.

    The extracted content is not returned, attached to an agent, or sent to an
    external provider. A later, separately approved task-attachment feature is
    required before any agent can use it as context.
    """
    try:
        content = await document.read()
        return document_store.ingest(
            content,
            document.filename or "",
            confirmed_non_sensitive=confirmed_non_sensitive,
        ).to_dict()
    except DocumentIngestionError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    finally:
        await document.close()


@app.get("/documents/{document_id}")
def get_document_metadata(document_id: str, _auth: None = Depends(require_api_key)) -> dict:
    """Return reference-document metadata only; extracted text remains local and non-public."""
    document = document_store.get_metadata(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document.to_dict()


@app.delete("/documents/{document_id}")
def delete_document(
    document_id: str,
    _auth: None = Depends(require_role(AccessRole.ADMIN)),
    principal: str | None = Depends(resolve_principal),
) -> dict:
    """Permanently delete an ingested document's local text and metadata.

    Existing task attachment snapshots remain as non-content provenance.  This
    endpoint never deletes tasks, alters approval history, or exposes text.
    """
    if not document_store.delete(document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    log_event("reference_document_deleted", document_id=document_id, principal=principal)
    return {"document_id": document_id, "status": "deleted"}


@app.post("/tasks/{task_id}/reference-documents")
def attach_reference_document(
    task_id: str,
    payload: ReferenceDocumentAttachmentIn,
    _auth: None = Depends(require_role(AccessRole.APPROVER)),
    principal: str | None = Depends(resolve_principal),
) -> dict:
    """Attach one pre-ingested document's metadata to a task before execution approval."""
    document = document_store.get_metadata(payload.document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        result = core.attach_reference_document(
            task_id,
            document.to_dict(),
            attached_by=principal or payload.attached_by,
        )
        log_event(
            "reference_document_attached",
            task_id=task_id,
            document_id=document.document_id,
            principal=principal or payload.attached_by,
        )
        return result
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Task not found") from error
    except (TaskStateError, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/feedback")
def record_feedback(payload: FeedbackIn, _auth: None = Depends(require_api_key)) -> dict:
    try:
        return core.kb_store.record_feedback(payload.to_record())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/personal-kb/proposals")
def create_preference_proposal(payload: PreferenceProposalIn, _auth: None = Depends(require_api_key)) -> dict:
    try:
        return core.kb_store.propose(payload.to_proposal())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/personal-kb/proposals/{proposal_id}/decision")
def decide_preference_proposal(
    proposal_id: str, payload: ProposalDecisionIn, _auth: None = Depends(require_role(AccessRole.APPROVER))
) -> dict:
    try:
        return core.kb_store.decide(proposal_id, payload.decision, payload.note)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Personal KB proposal not found") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/personal-kb/entries")
def list_personal_kb_entries(_auth: None = Depends(require_api_key)) -> list[dict]:
    return core.kb_store.entries()


@app.post("/tasks/{task_id}/memory-proposal")
def propose_episodic_memory(task_id: str, _auth: None = Depends(require_api_key)) -> dict:
    try:
        return core.propose_episodic_memory(task_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Task not found") from error
    except TaskStateError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/episodic-memory/proposals/{proposal_id}/decision")
def decide_episodic_memory(
    proposal_id: str,
    payload: MemoryDecisionIn,
    _auth: None = Depends(require_role(AccessRole.APPROVER)),
    principal: str | None = Depends(resolve_principal),
) -> dict:
    try:
        return core.decide_episodic_memory(
            proposal_id,
            payload.decision,
            principal or payload.approved_by,
            payload.note,
            retention_days=payload.retention_days,
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Episodic-memory proposal not found") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/episodic-memory/search")
def search_episodic_memory(
    query: str, limit: int = 5, _auth: None = Depends(require_api_key)
) -> list[dict]:
    try:
        return core.recall_episodic_memory(query, limit=limit)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.delete("/episodic-memory/{memory_id}")
def delete_episodic_memory(
    memory_id: str,
    payload: MemoryDeleteIn,
    _auth: None = Depends(require_role(AccessRole.APPROVER)),
    principal: str | None = Depends(resolve_principal),
) -> dict:
    """Delete one searchable episodic-memory entry by its authenticated owner."""
    try:
        return core.delete_episodic_memory(memory_id, principal or payload.deleted_by, payload.note)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Episodic-memory entry not found") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/episodic-memory/{memory_id}/audit")
def audit_episodic_memory(memory_id: str, _auth: None = Depends(require_api_key)) -> dict:
    """Expose lifecycle provenance while never returning deleted or expired memory content."""
    try:
        return core.audit_episodic_memory(memory_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Episodic-memory audit record not found") from error


@app.post("/similarity/screen")
def similarity_screen(payload: SimilarityScreenIn, _auth: None = Depends(require_api_key)) -> dict:
    """Screen supplied texts locally and return review signals, never an originality verdict."""
    try:
        return screen_similarity(payload.to_similarity_request()).to_dict()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/tasks")
def create_task(payload: TaskIn, _auth: None = Depends(require_api_key)) -> dict:
    return core.create_task(TaskRequest(**payload.model_dump())).to_dict()


@app.post("/lecture-plans")
def create_lecture_plan(payload: LecturePlanIn, _auth: None = Depends(require_api_key)) -> dict:
    try:
        return build_lecture_plan(payload.to_agent_request()).to_dict()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/lecture-plans/docx")
def create_lecture_plan_docx(
    payload: LecturePlanIn, background: BackgroundTasks, _auth: None = Depends(require_api_key)
) -> FileResponse:
    try:
        plan = build_lecture_plan(payload.to_agent_request())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _docx_response(lambda path: export_docx(plan, path), "lecture_plan.docx", background)


@app.post("/writing-drafts")
def create_writing_draft(payload: WritingDraftIn, _auth: None = Depends(require_api_key)) -> dict:
    try:
        return build_writing_draft(payload.to_agent_request()).to_dict()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/writing-drafts/docx")
def create_writing_draft_docx(
    payload: WritingDraftIn, background: BackgroundTasks, _auth: None = Depends(require_api_key)
) -> FileResponse:
    try:
        draft = build_writing_draft(payload.to_agent_request())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _docx_response(lambda path: export_writing_docx(draft, path), "writing_draft.docx", background)


@app.post("/research-briefs")
def create_research_brief(payload: ResearchBriefIn, _auth: None = Depends(require_api_key)) -> dict:
    try:
        return build_research_brief(payload.to_agent_request()).to_dict()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/research/discover")
def discover_research_sources(payload: ResearchDiscoveryIn, _auth: None = Depends(require_api_key)) -> dict:
    """Return read-only, unverified evidence candidates from Tavily."""
    try:
        return _tavily_client().discover(payload.query, max_results=payload.max_results).to_dict()
    except TavilyError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/research/discover/arxiv")
def discover_arxiv_preprints(payload: ResearchDiscoveryIn, _auth: None = Depends(require_api_key)) -> dict:
    """Return cached, rate-limited, read-only arXiv preprint candidates for later verification."""
    try:
        return _arxiv_client().discover(payload.query, max_results=payload.max_results).to_dict()
    except ArxivError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/research/discover/semantic-scholar")
def discover_semantic_scholar_papers(
    payload: ResearchDiscoveryIn, _auth: None = Depends(require_api_key)
) -> dict:
    """Return cached, rate-limited bibliographic candidates for later independent verification."""
    try:
        return _semantic_scholar_client().discover(payload.query, max_results=payload.max_results).to_dict()
    except SemanticScholarError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/research-briefs/agentic")
def create_agentic_research_brief(payload: ResearchBriefIn, _auth: None = Depends(require_api_key)) -> dict:
    """Run the tool-using, LLM-synthesising research agent (safe with no LLM key)."""
    try:
        provider = get_provider()
    except LLMConfigurationError as error:
        raise HTTPException(
            status_code=503,
            detail=f"LLM provider misconfigured: {error}. The agent cannot synthesise until this is resolved.",
        ) from error
    try:
        result = run_agentic_research_brief(
            payload.to_agent_request(),
            provider=provider,
            crossref=_crossref_client(),
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return result.to_dict()


@app.post("/research-briefs/docx")
def create_research_brief_docx(
    payload: ResearchBriefIn, background: BackgroundTasks, _auth: None = Depends(require_api_key)
) -> FileResponse:
    try:
        brief = build_research_brief(payload.to_agent_request())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _docx_response(lambda path: export_research_docx(brief, path), "research_brief.docx", background)


@app.post("/research-briefs/bibtex")
def create_research_bibtex(payload: ResearchBriefIn, _auth: None = Depends(require_api_key)) -> PlainTextResponse:
    try:
        brief = build_research_brief(payload.to_agent_request())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return PlainTextResponse(brief.verified_bibtex(), media_type="application/x-bibtex")


@app.post("/assessment-blueprints")
def create_assessment_blueprint(payload: AssessmentBlueprintIn, _auth: None = Depends(require_api_key)) -> dict:
    try:
        return build_assessment_blueprint(payload.to_agent_request()).to_dict()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/assessment-blueprints/agentic")
def create_agentic_assessment_blueprint(
    payload: AssessmentBlueprintIn, _auth: None = Depends(require_api_key)
) -> dict:
    """Generate an instructor-only assessment review with a safe disabled-LLM fallback."""
    try:
        provider = get_provider()
    except LLMConfigurationError as error:
        raise HTTPException(status_code=503, detail=f"LLM provider misconfigured: {error}") from error
    try:
        return run_agentic_assessment_design(payload.to_agent_request(), provider=provider).to_dict()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/assessment-blueprints/student-docx")
def create_assessment_student_docx(
    payload: AssessmentBlueprintIn, background: BackgroundTasks, _auth: None = Depends(require_api_key)
) -> FileResponse:
    try:
        blueprint = build_assessment_blueprint(payload.to_agent_request())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _docx_response(
        lambda path: export_student_docx(blueprint, path), "student_assessment_blueprint.docx", background
    )


@app.post("/assessment-blueprints/instructor-docx")
def create_assessment_instructor_docx(
    payload: AssessmentBlueprintIn, background: BackgroundTasks, _auth: None = Depends(require_api_key)
) -> FileResponse:
    try:
        blueprint = build_assessment_blueprint(payload.to_agent_request())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _docx_response(
        lambda path: export_instructor_docx(blueprint, path), "instructor_assessment_blueprint.docx", background
    )


@app.post("/content-packages")
def create_content_package(payload: ContentPackageIn, _auth: None = Depends(require_api_key)) -> dict:
    try:
        return build_content_package(payload.to_agent_request()).to_dict()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/content-packages/agentic")
def create_agentic_content_review(payload: ContentPackageIn, _auth: None = Depends(require_api_key)) -> dict:
    """Generate an internal editorial review with a safe disabled-LLM fallback."""
    try:
        provider = get_provider()
    except LLMConfigurationError as error:
        raise HTTPException(status_code=503, detail=f"LLM provider misconfigured: {error}") from error
    try:
        return run_agentic_content_review(payload.to_agent_request(), provider=provider).to_dict()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/content-packages/docx")
def create_content_package_docx(
    payload: ContentPackageIn, background: BackgroundTasks, _auth: None = Depends(require_api_key)
) -> FileResponse:
    try:
        package = build_content_package(payload.to_agent_request())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _docx_response(lambda path: export_content_docx(package, path), "content_package.docx", background)


@app.post("/social-media-packages")
def create_social_media_package(payload: SocialMediaPackageIn, _auth: None = Depends(require_api_key)) -> dict:
    try:
        return build_social_media_package(payload.to_agent_request()).to_dict()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/social-media-packages/agentic")
def create_agentic_social_media_review(
    payload: SocialMediaPackageIn, _auth: None = Depends(require_api_key)
) -> dict:
    """Generate an internal review; this endpoint cannot schedule or publish posts."""
    try:
        provider = get_provider()
    except LLMConfigurationError as error:
        raise HTTPException(status_code=503, detail=f"LLM provider misconfigured: {error}") from error
    try:
        return run_agentic_social_media_review(payload.to_agent_request(), provider=provider).to_dict()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/social-media-packages/docx")
def create_social_media_package_docx(
    payload: SocialMediaPackageIn, background: BackgroundTasks, _auth: None = Depends(require_api_key)
) -> FileResponse:
    try:
        package = build_social_media_package(payload.to_agent_request())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _docx_response(
        lambda path: export_social_media_docx(package, path), "social_media_package.docx", background
    )


@app.post("/portfolio-packages")
def create_portfolio_package(payload: PortfolioPackageIn, _auth: None = Depends(require_api_key)) -> dict:
    try:
        return build_portfolio_package(payload.to_agent_request()).to_dict()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/portfolio-packages/agentic")
def create_agentic_portfolio_review(
    payload: PortfolioPackageIn, _auth: None = Depends(require_api_key)
) -> dict:
    """Generate an internal readiness review; this endpoint cannot act on GitHub."""
    try:
        provider = get_provider()
    except LLMConfigurationError as error:
        raise HTTPException(status_code=503, detail=f"LLM provider misconfigured: {error}") from error
    try:
        return run_agentic_portfolio_review(payload.to_agent_request(), provider=provider).to_dict()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/portfolio-packages/docx")
def create_portfolio_package_docx(
    payload: PortfolioPackageIn, background: BackgroundTasks, _auth: None = Depends(require_api_key)
) -> FileResponse:
    try:
        package = build_portfolio_package(payload.to_agent_request())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _docx_response(lambda path: export_portfolio_docx(package, path), "portfolio_package.docx", background)


@app.post("/autoeval-reports")
def create_autoeval_report(payload: AutoEvalReportIn, _auth: None = Depends(require_api_key)) -> dict:
    try:
        provider = get_provider()
        return evaluate_deliverable(payload.to_agent_request(), provider=provider).to_dict()
    except LLMConfigurationError as error:
        raise HTTPException(status_code=503, detail=f"LLM provider misconfigured: {error}") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/autoeval-reports/docx")
def create_autoeval_report_docx(
    payload: AutoEvalReportIn, background: BackgroundTasks, _auth: None = Depends(require_api_key)
) -> FileResponse:
    try:
        provider = get_provider()
        report = evaluate_deliverable(payload.to_agent_request(), provider=provider)
    except LLMConfigurationError as error:
        raise HTTPException(status_code=503, detail=f"LLM provider misconfigured: {error}") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _docx_response(lambda path: export_autoeval_docx(report, path), "autoeval_report.docx", background)


@app.get("/tasks")
def list_tasks(
    status: Annotated[TaskStatus | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    _auth: None = Depends(require_api_key),
) -> dict:
    """List task metadata for a human work queue; this endpoint cannot mutate tasks."""
    try:
        return core.store.list(status, limit=limit, cursor=cursor)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/tasks/{task_id}/status")
def get_task_status(task_id: str, _auth: None = Depends(require_api_key)) -> dict:
    """Return safe lifecycle metadata for polling; never task requests, drafts, or notes."""
    task = core.store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    status = TaskStatus(task["status"])
    return {
        "task_id": task["task_id"],
        "created_at": task["created_at"],
        "status": status.value,
        "risk_tier": task.get("risk_tier"),
        "deliverable_count": len(task.get("deliverables", [])),
        "final_review_required": status is TaskStatus.AWAITING_REVIEW,
    }


@app.get("/tasks/{task_id}/trace")
def get_task_trace(task_id: str, _auth: None = Depends(require_role(AccessRole.APPROVER))) -> dict:
    """Return an approver-only, content-free lifecycle trace; this endpoint cannot act on a task."""
    try:
        return core.task_trace(task_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Task not found") from error


@app.get("/tasks/{task_id}")
def get_task(task_id: str, _auth: None = Depends(require_role(AccessRole.APPROVER))) -> dict:
    """Return a content-bearing task record only to an authorized reviewer."""
    task = core.store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.get("/tasks/{task_id}/lineage")
def get_task_lineage(task_id: str, _auth: None = Depends(require_api_key)) -> dict:
    """Return the read-only revision family metadata for a human reviewer."""
    try:
        return core.task_lineage(task_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Task not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/tasks/{task_id}/revision-comparison")
def compare_task_revision(task_id: str, _auth: None = Depends(require_api_key)) -> dict:
    """Return the direct task-request diff and approval boundary for one linked revision."""
    try:
        return core.compare_revision(task_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Task not found") from error
    except TaskStateError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/tasks/{task_id}/dispatch")
def dispatch_approved_task(
    task_id: str, payload: DispatchIn, _auth: None = Depends(require_api_key)
) -> dict:
    """Queue an already-approved local task; no task execution starts in this request."""
    try:
        return core.enqueue_approved_task(
            task_id,
            idempotency_key=payload.idempotency_key,
            max_attempts=payload.max_attempts,
        ).to_dict()
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Task not found") from error
    except (TaskStateError, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/dispatch/jobs/{job_id}")
def get_dispatch_job(job_id: str, _auth: None = Depends(require_api_key)) -> dict:
    job = core.dispatch_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Dispatch job not found")
    return job.to_dict()


@app.post("/dispatch/jobs/claim")
def claim_dispatch_job(payload: DispatchClaimIn, _auth: None = Depends(require_api_key)) -> dict | None:
    """Atomically claim one queued job for a named worker; this cannot execute an external action."""
    try:
        job = core.dispatch_store.claim_next(payload.worker_id)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return job.to_dict() if job is not None else None


@app.post("/dispatch/jobs/{job_id}/finish")
def finish_dispatch_job(
    job_id: str, payload: DispatchFinishIn, _auth: None = Depends(require_api_key)
) -> dict:
    """Record a worker outcome; failures are retried only within the fixed job budget."""
    try:
        return core.dispatch_store.finish(
            job_id,
            worker_id=payload.worker_id,
            succeeded=payload.succeeded,
            error=payload.error,
            retryable=payload.retryable,
        ).to_dict()
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Dispatch job not found") from error
    except (ValueError, RuntimeError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/dispatch/jobs/{job_id}/renew")
def renew_dispatch_lease(
    job_id: str, payload: DispatchRenewIn, _auth: None = Depends(require_api_key)
) -> dict:
    """Extend a still-valid local lease held by the named worker only."""
    try:
        return core.dispatch_store.renew_lease(
            job_id, worker_id=payload.worker_id, lease_seconds=payload.lease_seconds
        ).to_dict()
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Dispatch job not found") from error
    except (ValueError, RuntimeError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/dispatch/run-one")
def run_one_dispatch_job(payload: DispatchRunIn, _auth: None = Depends(require_api_key)) -> dict | None:
    """Run one claimed, already-approved task using local deterministic drafting only."""
    try:
        return core.run_one_dispatched_task(payload.worker_id)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/tasks/{task_id}/execute")
def execute_task(
    task_id: str, parallel: bool = False, _auth: None = Depends(require_api_key)
) -> dict:
    """Run approved local drafts; ``parallel=true`` is opt-in for independent graph layers only."""
    try:
        result = core.execute(task_id, parallel=parallel)
        log_event("task_execution_completed", task_id=task_id, status=result["status"])
        return result
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Task not found") from error
    except TaskStateError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/tasks/{task_id}/cross-agent-autoeval")
def create_cross_agent_autoeval(task_id: str, _auth: None = Depends(require_api_key)) -> dict:
    """Create one review-only quality consolidation for completed local drafts."""
    try:
        return core.create_cross_agent_autoeval(task_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Task not found") from error
    except TaskStateError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/tasks/{task_id}/revise")
def create_task_revision(
    task_id: str,
    payload: RevisionIn,
    _auth: None = Depends(require_role(AccessRole.APPROVER)),
    principal: str | None = Depends(resolve_principal),
) -> dict:
    """Create a separate, approval-gated revision from a final reviewer rejection."""
    requester = principal or payload.requested_by
    try:
        return core.create_revision(task_id, requester)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Task not found") from error
    except TaskStateError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/tasks/{task_id}/cancel")
def cancel_task(
    task_id: str,
    payload: CancellationIn,
    _auth: None = Depends(require_role(AccessRole.APPROVER)),
    principal: str | None = Depends(resolve_principal),
) -> dict:
    """Request safe cancellation before or at the next local graph-layer checkpoint."""
    requester = principal or payload.requested_by
    try:
        return core.request_cancellation(task_id, requester, payload.note)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Task not found") from error
    except (TaskStateError, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/tasks/{task_id}/recover")
def recover_task(
    task_id: str,
    payload: RecoveryIn,
    _auth: None = Depends(require_role(AccessRole.APPROVER)),
    principal: str | None = Depends(resolve_principal),
) -> dict:
    """Recover a human-confirmed interrupted local task; fresh approval is required to rerun it."""
    operator = principal or payload.recovered_by
    try:
        return core.recover_interrupted_task(
            task_id,
            operator,
            payload.note,
            confirm_execution_stopped=payload.confirm_execution_stopped,
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Task not found") from error
    except (TaskStateError, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/tasks/{task_id}/approval")
def approval(
    task_id: str,
    payload: ApprovalIn,
    _auth: None = Depends(require_role(AccessRole.APPROVER)),
    principal: str | None = Depends(resolve_principal),
    role: AccessRole | None = ROLE_DEPENDENCY,
) -> dict:
    # In named-key mode the principal is derived from the key and overrides the body.
    approver = principal or payload.approved_by
    if payload.override_blocking:
        ensure_role(role, AccessRole.ADMIN)
    try:
        result = core.decide(
            task_id,
            payload.decision,
            payload.note,
            approved_by=approver,
            override_blocking=payload.override_blocking,
        )
        log_event(
            "task_approval_recorded",
            task_id=task_id,
            principal=approver,
            risk_tier=result["risk_tier"],
            decision=payload.decision.value,
            override_blocking=payload.override_blocking,
            status=result["status"],
        )
        return result
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Task not found") from error
    except BlockedApprovalError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except TaskStateError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
