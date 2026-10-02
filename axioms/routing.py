from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256

from axioms.models import AgentName, Subtask, TaskRequest

TASK_GRAPH_VERSION = "routing.v1"


class GraphValidationError(ValueError):
    """Raised when a task graph is not a valid, reproducible DAG."""


@dataclass(frozen=True, slots=True)
class TaskGraph:
    version: str
    subtasks: tuple[Subtask, ...]
    execution_layers: tuple[tuple[str, ...], ...]
    digest: str

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "digest": self.digest,
            "execution_layers": [list(layer) for layer in self.execution_layers],
            "nodes": [
                {
                    "node_id": subtask.agent.value,
                    "agent": subtask.agent.value,
                    "title": subtask.title,
                    "depends_on": list(subtask.depends_on),
                    "checkpoint": subtask.checkpoint,
                }
                for subtask in self.subtasks
            ],
        }

LECTURE_KEYWORDS = {"lecture", "lesson", "slides", "teach"}
WRITING_KEYWORDS = {"write", "email", "report", "paper", "letter", "proposal", "draft"}
RESEARCH_KEYWORDS = {"research", "literature", "evidence", "citation", "systematic review"}
ASSESSMENT_KEYWORDS = {"quiz", "assessment", "assignment", "midterm", "final", "rubric"}
CONTENT_KEYWORDS = {"video", "youtube", "workshop", "course module", "thumbnail", "educational content"}
SOCIAL_MEDIA_KEYWORDS = {
    "social media",
    "linkedin",
    "instagram",
    "tiktok",
    "whatsapp",
    "twitter",
    "x thread",
    "post",
    "carousel",
}
PORTFOLIO_KEYWORDS = {
    "portfolio",
    "github",
    "repository",
    "repo",
    "reproducibility",
    "reproduce",
    "case study",
}
AUTOEVAL_KEYWORDS = {
    "evaluate",
    "evaluation",
    "quality check",
    "quality assurance",
    "qa",
    "regression",
    "audit output",
}


def build_task_graph(request: TaskRequest) -> TaskGraph:
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
    if any(keyword in text for keyword in RESEARCH_KEYWORDS):
        subtasks.append(Subtask(agent=AgentName.RESEARCH, title="Prepare evidence-first research brief", instructions="Create a claim-level evidence ledger and expose unverified items for review."))
    if any(keyword in text for keyword in ASSESSMENT_KEYWORDS):
        subtasks.append(Subtask(agent=AgentName.ASSESSMENT, title="Prepare assessment blueprint", instructions="Map source-bounded question frameworks to outcomes, rubrics, and review checks."))
    if any(keyword in text for keyword in CONTENT_KEYWORDS):
        subtasks.append(Subtask(agent=AgentName.CONTENT, title="Prepare educational content package", instructions="Build a reviewable content plan with accuracy, copyright, and accessibility controls."))
    if any(keyword in text for keyword in SOCIAL_MEDIA_KEYWORDS):
        subtasks.append(
            Subtask(
                agent=AgentName.SOCIAL_MEDIA,
                title="Prepare social-media draft package",
                instructions=(
                    "Create platform-native drafts, accessibility notes, a proposed calendar, "
                    "and approval checks without scheduling or publishing."
                ),
            )
        )
    if any(keyword in text for keyword in PORTFOLIO_KEYWORDS):
        subtasks.append(
            Subtask(
                agent=AgentName.PORTFOLIO,
                title="Prepare STEM AI portfolio blueprint",
                instructions=(
                    "Create an evidence-bound repository, README, and reproducibility plan "
                    "without creating, modifying, or publishing any external repository."
                ),
            )
        )
    if any(keyword in text for keyword in AUTOEVAL_KEYWORDS):
        subtasks.append(
            Subtask(
                agent=AgentName.AUTOEVAL,
                title="Prepare AutoEval review report",
                instructions=(
                    "Run declared deterministic checks and report review findings without approving, "
                    "reconfiguring, publishing, or changing any external system."
                ),
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
    _assign_dependencies(subtasks)
    return validate_task_graph(subtasks)


def validate_task_graph(subtasks: list[Subtask], *, version: str = TASK_GRAPH_VERSION) -> TaskGraph:
    """Validate a uniquely named dependency DAG and return deterministic execution layers."""
    if not subtasks:
        raise GraphValidationError("A task graph requires at least one subtask.")
    nodes = {subtask.agent.value: subtask for subtask in subtasks}
    if len(nodes) != len(subtasks):
        raise GraphValidationError("A task graph cannot contain duplicate agent nodes.")
    for node_id, subtask in nodes.items():
        unknown = sorted(set(subtask.depends_on) - set(nodes))
        if unknown:
            raise GraphValidationError(f"Node {node_id} depends on unknown node(s): {', '.join(unknown)}.")
        if node_id in subtask.depends_on:
            raise GraphValidationError(f"Node {node_id} cannot depend on itself.")
    remaining = {node_id: set(subtask.depends_on) for node_id, subtask in nodes.items()}
    layers: list[tuple[str, ...]] = []
    while remaining:
        ready = tuple(sorted(node_id for node_id, dependencies in remaining.items() if not dependencies))
        if not ready:
            raise GraphValidationError("Task graph contains a dependency cycle.")
        layers.append(ready)
        for node_id in ready:
            remaining.pop(node_id)
        for dependencies in remaining.values():
            dependencies.difference_update(ready)
    canonical = {
        "version": version,
        "nodes": [
            {
                "agent": subtask.agent.value,
                "title": subtask.title,
                "instructions": subtask.instructions,
                "depends_on": sorted(subtask.depends_on),
                "checkpoint": subtask.checkpoint,
            }
            for subtask in sorted(subtasks, key=lambda item: item.agent.value)
        ],
    }
    digest = sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return TaskGraph(version=version, subtasks=tuple(subtasks), execution_layers=tuple(layers), digest=digest)


def _assign_dependencies(subtasks: list[Subtask]) -> None:
    """Declare only explicit, reviewable dependencies; independent nodes remain parallel-capable."""
    by_agent = {subtask.agent: subtask for subtask in subtasks}
    research = by_agent.get(AgentName.RESEARCH)
    if research is not None:
        for agent in (AgentName.ASSESSMENT, AgentName.CONTENT):
            if target := by_agent.get(agent):
                target.depends_on.append(research.agent.value)
    content = by_agent.get(AgentName.CONTENT)
    social = by_agent.get(AgentName.SOCIAL_MEDIA)
    if content is not None and social is not None:
        social.depends_on.append(content.agent.value)
    autoeval = by_agent.get(AgentName.AUTOEVAL)
    if autoeval is not None:
        autoeval.depends_on.extend(
            subtask.agent.value for subtask in subtasks if subtask.agent is not AgentName.AUTOEVAL
        )
