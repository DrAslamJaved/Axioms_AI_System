import pytest

from axioms.models import AgentName, Subtask, TaskRequest
from axioms.routing import GraphValidationError, build_task_graph, validate_task_graph


def test_routing_graph_is_versioned_hashed_and_exposes_explicit_dependencies() -> None:
    request = TaskRequest(
        goal="Research literature, prepare an assessment, YouTube video, social media post, and quality evaluation"
    )
    first = build_task_graph(request)
    second = build_task_graph(request)
    nodes = {subtask.agent.value: subtask for subtask in first.subtasks}
    assert first.version == "routing.v1"
    assert first.digest == second.digest
    assert nodes[AgentName.ASSESSMENT.value].depends_on == [AgentName.RESEARCH.value]
    assert nodes[AgentName.CONTENT.value].depends_on == [AgentName.RESEARCH.value]
    assert nodes[AgentName.SOCIAL_MEDIA.value].depends_on == [AgentName.CONTENT.value]
    assert set(nodes[AgentName.AUTOEVAL.value].depends_on) == {
        AgentName.RESEARCH.value,
        AgentName.ASSESSMENT.value,
        AgentName.CONTENT.value,
        AgentName.SOCIAL_MEDIA.value,
    }
    assert first.execution_layers[0] == (AgentName.RESEARCH.value,)


def test_task_graph_validation_rejects_unknown_dependencies_and_cycles() -> None:
    unknown = [
        Subtask(AgentName.LECTURE, "Lecture", "Draft", depends_on=["missing"]),
    ]
    with pytest.raises(GraphValidationError, match="unknown"):
        validate_task_graph(unknown)
    cyclic = [
        Subtask(AgentName.LECTURE, "Lecture", "Draft", depends_on=[AgentName.WRITING.value]),
        Subtask(AgentName.WRITING, "Writing", "Draft", depends_on=[AgentName.LECTURE.value]),
    ]
    with pytest.raises(GraphValidationError, match="cycle"):
        validate_task_graph(cyclic)
