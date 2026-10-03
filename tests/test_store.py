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
