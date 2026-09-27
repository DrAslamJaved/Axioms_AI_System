from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from axioms.core import AxiomsCore
from axioms.models import ApprovalDecision, TaskRequest

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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "human-governed-mvp"}


@app.post("/tasks")
def create_task(payload: TaskIn) -> dict:
    return core.create_task(TaskRequest(**payload.model_dump())).to_dict()


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

