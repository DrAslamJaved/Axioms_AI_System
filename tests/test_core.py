from pathlib import Path

from axioms.core import AxiomsCore
from axioms.models import AgentName, ApprovalDecision, TaskRequest, TaskStatus
from axioms.store import TaskStore


def test_lecture_request_routes_to_lecture_agent(tmp_path: Path) -> None:
    core = AxiomsCore(TaskStore(tmp_path / "test.sqlite3"))
    record = core.create_task(TaskRequest(goal="Prepare a graduate lecture on graph theory"))
    assert [task.agent for task in record.subtasks] == [AgentName.LECTURE]
    assert record.status is TaskStatus.PENDING_APPROVAL


def test_writing_request_has_human_approval_gate(tmp_path: Path) -> None:
    core = AxiomsCore(TaskStore(tmp_path / "test.sqlite3"))
    record = core.create_task(TaskRequest(goal="Write a formal research report"))
    assert record.deliverables[0].status is TaskStatus.PENDING_APPROVAL
    updated = core.decide(record.task_id, ApprovalDecision.APPROVE, "Reviewed")
    assert updated["status"] == TaskStatus.APPROVED.value
    assert updated["deliverables"][0]["status"] == TaskStatus.APPROVED.value


def test_mixed_goal_creates_parallel_specialist_subtasks(tmp_path: Path) -> None:
    core = AxiomsCore(TaskStore(tmp_path / "test.sqlite3"))
    record = core.create_task(TaskRequest(goal="Prepare a lecture and write an announcement"))
    assert {task.agent for task in record.subtasks} == {AgentName.LECTURE, AgentName.WRITING}


def test_social_media_request_routes_to_review_only_agent(tmp_path: Path) -> None:
    core = AxiomsCore(TaskStore(tmp_path / "test.sqlite3"))
    record = core.create_task(TaskRequest(goal="Prepare a LinkedIn post about graph theory"))
    assert [task.agent for task in record.subtasks] == [AgentName.SOCIAL_MEDIA]
    assert "does not connect" in record.deliverables[0].content


def test_portfolio_request_routes_to_review_only_agent(tmp_path: Path) -> None:
    core = AxiomsCore(TaskStore(tmp_path / "test.sqlite3"))
    record = core.create_task(TaskRequest(goal="Prepare a GitHub portfolio repository for my AI project"))
    assert [task.agent for task in record.subtasks] == [AgentName.PORTFOLIO]
    assert "does not create" in record.deliverables[0].content


def test_autoeval_request_routes_to_non_reconfiguring_agent(tmp_path: Path) -> None:
    core = AxiomsCore(TaskStore(tmp_path / "test.sqlite3"))
    record = core.create_task(TaskRequest(goal="Run a quality assurance evaluation on this artifact"))
    assert [task.agent for task in record.subtasks] == [AgentName.AUTOEVAL]
    assert "cannot approve" in record.deliverables[0].content


def test_core_routes_remaining_specialists_to_typed_endpoint_handoffs(tmp_path: Path) -> None:
    core = AxiomsCore(TaskStore(tmp_path / "test.sqlite3"))
    record = core.create_task(
        TaskRequest(goal="Research literature and prepare a quiz plus a YouTube video")
    )
    assert {task.agent for task in record.subtasks} == {
        AgentName.RESEARCH,
        AgentName.ASSESSMENT,
        AgentName.CONTENT,
    }
    assert all("Typed endpoint" in item.content for item in record.deliverables)
