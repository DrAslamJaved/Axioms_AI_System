from __future__ import annotations

from axioms.models import AgentName, Subtask, TaskRequest

LECTURE_KEYWORDS = {"lecture", "lesson", "course", "slides", "quiz", "assessment", "teach"}
WRITING_KEYWORDS = {"write", "email", "report", "paper", "letter", "proposal", "draft"}


def build_task_graph(request: TaskRequest) -> list[Subtask]:
    """Create an explicit, inspectable DAG without pretending to infer hidden intent."""
    text = request.goal.casefold()
    subtasks: list[Subtask] = []
    if any(keyword in text for keyword in LECTURE_KEYWORDS):
        subtasks.append(
            Subtask(
                agent=AgentName.LECTURE,
                title="Prepare lecture draft",
                instructions="Create an outline, timing plan, intuition-first explanation, and review checklist.",
            )
        )
    if any(keyword in text for keyword in WRITING_KEYWORDS):
        subtasks.append(
            Subtask(
                agent=AgentName.WRITING,
                title="Prepare writing draft",
                instructions="Create a structured draft with assumptions and items needing factual verification.",
            )
        )
    if not subtasks:
        subtasks.append(
            Subtask(
                agent=AgentName.WRITING,
                title="Clarify and structure request",
                instructions="Create a concise requirements brief and identify missing facts before drafting.",
            )
        )
    return subtasks

