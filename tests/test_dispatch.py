from pathlib import Path

import pytest

from axioms.dispatch import DispatchStateError, DispatchStatus, DurableDispatchStore


def _store(tmp_path: Path) -> DurableDispatchStore:
    return DurableDispatchStore(tmp_path / "dispatch.sqlite3")


def test_dispatch_is_idempotent_and_records_claim_success(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = store.enqueue("task_001", idempotency_key="dispatch-task-001")
    repeated = store.enqueue("task_001", idempotency_key="dispatch-task-001")
    assert repeated.job_id == first.job_id
    claimed = store.claim_next("local-worker")
    assert claimed is not None
    assert claimed.status is DispatchStatus.CLAIMED
    assert claimed.attempts == 1
    completed = store.finish(claimed.job_id, worker_id="local-worker", succeeded=True)
    assert completed.status is DispatchStatus.SUCCEEDED
    assert store.claim_next("another-worker") is None


def test_dispatch_retries_within_fixed_budget_then_dead_letters(tmp_path: Path) -> None:
    store = _store(tmp_path)
    job = store.enqueue("task_002", idempotency_key="dispatch-task-002", max_attempts=2)
    first = store.claim_next("worker-a")
    assert first is not None
    retry = store.finish(first.job_id, worker_id="worker-a", succeeded=False, error="temporary failure")
    assert retry.status is DispatchStatus.QUEUED
    assert retry.last_error == "temporary failure"
    second = store.claim_next("worker-b")
    assert second is not None and second.attempts == 2
    dead = store.finish(second.job_id, worker_id="worker-b", succeeded=False, error="still failing")
    assert dead.status is DispatchStatus.DEAD_LETTER
    assert dead.last_error == "still failing"
    assert store.get(job.job_id) == dead


def test_dispatch_rejects_cross_task_idempotency_and_wrong_worker_completion(tmp_path: Path) -> None:
    store = _store(tmp_path)
    job = store.enqueue("task_003", idempotency_key="dispatch-task-003")
    with pytest.raises(DispatchStateError, match="different task"):
        store.enqueue("task_004", idempotency_key="dispatch-task-003")
    claimed = store.claim_next("worker-a")
    assert claimed is not None
    with pytest.raises(DispatchStateError, match="different worker"):
        store.finish(job.job_id, worker_id="worker-b", succeeded=True)
