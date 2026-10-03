from pathlib import Path

import pytest

from axioms.models import TaskRecord, TaskRequest, TaskStatus
from axioms.store import TaskStore


def _save(store: TaskStore, task_id: str, status: TaskStatus) -> None:
    record = TaskRecord(request=TaskRequest(goal=f"Task {task_id}"), task_id=task_id)
    record.status = status
    store.save(record)


def test_task_list_filters_and_paginates_without_skipping_the_cursor_item(tmp_path: Path) -> None:
    store = TaskStore(tmp_path / "tasks.sqlite3")
    _save(store, "task_d", TaskStatus.PENDING_APPROVAL)
    _save(store, "task_c", TaskStatus.AWAITING_REVIEW)
    _save(store, "task_b", TaskStatus.AWAITING_REVIEW)
    _save(store, "task_a", TaskStatus.AWAITING_REVIEW)

    first = store.list(TaskStatus.AWAITING_REVIEW, limit=2)
    second = store.list(TaskStatus.AWAITING_REVIEW, limit=2, cursor=first["next_cursor"])

    assert [item["task_id"] for item in first["items"]] == ["task_c", "task_b"]
    assert first["next_cursor"] == "task_b"
    assert [item["task_id"] for item in second["items"]] == ["task_a"]
    assert second["next_cursor"] is None


def test_task_list_validates_status_limit_and_cursor(tmp_path: Path) -> None:
    store = TaskStore(tmp_path / "tasks.sqlite3")

    with pytest.raises(ValueError, match="'not-a-status'"):
        store.list("not-a-status")
    with pytest.raises(ValueError, match="between 1 and 200"):
        store.list(limit=201)
    with pytest.raises(ValueError, match="cannot be blank"):
        store.list(cursor="   ")


def test_task_lineage_returns_a_stable_metadata_only_revision_family(tmp_path: Path) -> None:
    store = TaskStore(tmp_path / "tasks.sqlite3")
    root = TaskRecord(request=TaskRequest(goal="Prepare a lecture on graph theory"))
    root.status = TaskStatus.REJECTED
    root.approval_note = "Add a numerical example."
    root.reviewed_by = "Dr Aslam"
    revision = TaskRecord(request=TaskRequest(goal="Prepare a lecture on graph theory"))
    revision.revision_of = root.task_id
    revision.revision_requested_by = "Dr Aslam"
    second_revision = TaskRecord(request=TaskRequest(goal="Prepare a lecture on graph theory"))
    second_revision.revision_of = revision.task_id
    for record in (root, revision, second_revision):
        store.save(record)

    lineage = store.lineage(revision.task_id)

    assert lineage["requested_task_id"] == revision.task_id
    assert lineage["root_task_id"] == root.task_id
    assert [item["task_id"] for item in lineage["items"]] == [
        root.task_id,
        revision.task_id,
        second_revision.task_id,
    ]
    assert lineage["items"][0]["reviewed_by"] == "Dr Aslam"
    assert "approval_note" not in lineage["items"][0]
    assert "deliverables" not in lineage["items"][0]


def test_task_lineage_rejects_missing_ancestor(tmp_path: Path) -> None:
    store = TaskStore(tmp_path / "tasks.sqlite3")
    orphan = TaskRecord(request=TaskRequest(goal="Prepare a lecture on graph theory"))
    orphan.revision_of = "task_missing"
    store.save(orphan)

    with pytest.raises(ValueError, match="missing ancestor"):
        store.lineage(orphan.task_id)
