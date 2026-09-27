from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from axioms.core import AxiomsCore
from axioms.lecture_agent import LectureRequest, build_lecture_plan, export_docx
from axioms.models import ApprovalDecision, TaskRequest
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
