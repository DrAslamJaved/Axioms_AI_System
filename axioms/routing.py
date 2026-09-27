from __future__ import annotations

from axioms.models import AgentName, Subtask, TaskRequest

LECTURE_KEYWORDS = {"lecture", "lesson", "course", "slides", "quiz", "assessment", "teach"}
WRITING_KEYWORDS = {"write", "email", "report", "paper", "letter", "proposal", "draft"}
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
    return subtasks
