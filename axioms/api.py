from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field

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
from axioms.core import AxiomsCore
from axioms.lecture_agent import LectureRequest, build_lecture_plan, export_docx
from axioms.models import ApprovalDecision, TaskRequest
from axioms.research_agent import (
    EvidenceSource,
    PublicationKind,
    ResearchRequest,
    VerificationStatus,
    build_research_brief,
)
from axioms.research_agent import export_docx as export_research_docx
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "human-governed-mvp"}


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
