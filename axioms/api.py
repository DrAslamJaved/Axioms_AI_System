from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
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
from axioms.autoeval_agent import (
    AutoEvalRequest,
    EvaluatedAgent,
    evaluate_deliverable,
)
from axioms.autoeval_agent import export_docx as export_autoeval_docx
from axioms.content_agent import ContentFormat, ContentRequest, LanguageMode, build_content_package
from axioms.content_agent import export_docx as export_content_docx
from axioms.core import AxiomsCore
from axioms.integration import build_system_readiness_report
from axioms.lecture_agent import LectureRequest, build_lecture_plan, export_docx
from axioms.models import ApprovalDecision, TaskRequest
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
from axioms.research_agent import (
    EvidenceSource,
    PublicationKind,
    ResearchRequest,
    VerificationStatus,
    build_research_brief,
)
from axioms.research_agent import export_docx as export_research_docx
from axioms.social_media_agent import (
    RecentSocialPost,
    SocialMediaRequest,
    SocialObjective,
    SocialPlatform,
    build_social_media_package,
)
from axioms.social_media_agent import export_docx as export_social_media_docx
from axioms.writing_agent import DocumentType, WritingRequest, build_writing_draft
from axioms.writing_agent import export_docx as export_writing_docx

app = FastAPI(title="Axioms AI System", version="0.1.0")
core = AxiomsCore()


class TaskIn(BaseModel):
    goal: str = Field(min_length=8, max_length=4000)
    audience: str = "unspecified"
    deadline: str | None = None
    constraints: list[str] = Field(default_factory=list)
    external_delivery: bool = False


class ApprovalIn(BaseModel):
    decision: ApprovalDecision
    note: str | None = Field(default=None, max_length=2000)


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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "human-governed-mvp"}


@app.get("/agents")
def list_agents() -> list[dict]:
    return [profile.to_dict() for profile in specialist_profiles()]


@app.get("/system/readiness")
def system_readiness() -> dict:
    return build_system_readiness_report().to_dict()


@app.post("/tasks")
def create_task(payload: TaskIn) -> dict:
    return core.create_task(TaskRequest(**payload.model_dump())).to_dict()


@app.post("/lecture-plans")
def create_lecture_plan(payload: LecturePlanIn) -> dict:
    try:
        return build_lecture_plan(payload.to_agent_request()).to_dict()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/lecture-plans/docx")
def create_lecture_plan_docx(payload: LecturePlanIn) -> FileResponse:
    try:
        plan = build_lecture_plan(payload.to_agent_request())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    destination = Path("artifacts") / "lecture_plan.docx"
    export_docx(plan, destination)
    return FileResponse(
        destination,
        filename="lecture_plan.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.post("/writing-drafts")
def create_writing_draft(payload: WritingDraftIn) -> dict:
    try:
        return build_writing_draft(payload.to_agent_request()).to_dict()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/writing-drafts/docx")
def create_writing_draft_docx(payload: WritingDraftIn) -> FileResponse:
    try:
        draft = build_writing_draft(payload.to_agent_request())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    destination = Path("artifacts") / "writing_draft.docx"
    export_writing_docx(draft, destination)
    return FileResponse(
        destination,
        filename="writing_draft.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.post("/research-briefs")
def create_research_brief(payload: ResearchBriefIn) -> dict:
    try:
        return build_research_brief(payload.to_agent_request()).to_dict()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/research-briefs/docx")
def create_research_brief_docx(payload: ResearchBriefIn) -> FileResponse:
    try:
        brief = build_research_brief(payload.to_agent_request())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    destination = Path("artifacts") / "research_brief.docx"
    export_research_docx(brief, destination)
    return FileResponse(
        destination,
        filename="research_brief.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.post("/research-briefs/bibtex")
def create_research_bibtex(payload: ResearchBriefIn) -> PlainTextResponse:
    try:
        brief = build_research_brief(payload.to_agent_request())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return PlainTextResponse(brief.verified_bibtex(), media_type="application/x-bibtex")


@app.post("/assessment-blueprints")
def create_assessment_blueprint(payload: AssessmentBlueprintIn) -> dict:
    try:
        return build_assessment_blueprint(payload.to_agent_request()).to_dict()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/assessment-blueprints/student-docx")
def create_assessment_student_docx(payload: AssessmentBlueprintIn) -> FileResponse:
    try:
        blueprint = build_assessment_blueprint(payload.to_agent_request())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    destination = Path("artifacts") / "student_assessment_blueprint.docx"
    export_student_docx(blueprint, destination)
    return FileResponse(
        destination,
        filename="student_assessment_blueprint.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.post("/assessment-blueprints/instructor-docx")
def create_assessment_instructor_docx(payload: AssessmentBlueprintIn) -> FileResponse:
    try:
        blueprint = build_assessment_blueprint(payload.to_agent_request())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    destination = Path("artifacts") / "instructor_assessment_blueprint.docx"
    export_instructor_docx(blueprint, destination)
    return FileResponse(
        destination,
        filename="instructor_assessment_blueprint.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.post("/content-packages")
def create_content_package(payload: ContentPackageIn) -> dict:
    try:
        return build_content_package(payload.to_agent_request()).to_dict()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/content-packages/docx")
def create_content_package_docx(payload: ContentPackageIn) -> FileResponse:
    try:
        package = build_content_package(payload.to_agent_request())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    destination = Path("artifacts") / "content_package.docx"
    export_content_docx(package, destination)
    return FileResponse(
        destination,
        filename="content_package.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.post("/social-media-packages")
def create_social_media_package(payload: SocialMediaPackageIn) -> dict:
    try:
        return build_social_media_package(payload.to_agent_request()).to_dict()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/social-media-packages/docx")
def create_social_media_package_docx(payload: SocialMediaPackageIn) -> FileResponse:
    try:
        package = build_social_media_package(payload.to_agent_request())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    destination = Path("artifacts") / "social_media_package.docx"
    export_social_media_docx(package, destination)
    return FileResponse(
        destination,
        filename="social_media_package.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.post("/portfolio-packages")
def create_portfolio_package(payload: PortfolioPackageIn) -> dict:
    try:
        return build_portfolio_package(payload.to_agent_request()).to_dict()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/portfolio-packages/docx")
def create_portfolio_package_docx(payload: PortfolioPackageIn) -> FileResponse:
    try:
        package = build_portfolio_package(payload.to_agent_request())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    destination = Path("artifacts") / "portfolio_package.docx"
    export_portfolio_docx(package, destination)
    return FileResponse(
        destination,
        filename="portfolio_package.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.post("/autoeval-reports")
def create_autoeval_report(payload: AutoEvalReportIn) -> dict:
    try:
        return evaluate_deliverable(payload.to_agent_request()).to_dict()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/autoeval-reports/docx")
def create_autoeval_report_docx(payload: AutoEvalReportIn) -> FileResponse:
    try:
        report = evaluate_deliverable(payload.to_agent_request())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    destination = Path("artifacts") / "autoeval_report.docx"
    export_autoeval_docx(report, destination)
    return FileResponse(
        destination,
        filename="autoeval_report.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.get("/tasks/{task_id}")
def get_task(task_id: str) -> dict:
    task = core.store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.post("/tasks/{task_id}/approval")
def approval(task_id: str, payload: ApprovalIn) -> dict:
    try:
        return core.decide(task_id, payload.decision, payload.note)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Task not found") from error
