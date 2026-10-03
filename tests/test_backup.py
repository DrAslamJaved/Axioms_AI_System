import json
import subprocess
import sys
from pathlib import Path

import pytest

from axioms.backup import create_sqlite_backup, verify_sqlite_restore
from axioms.models import TaskRecord, TaskRequest
from axioms.store import TaskStore


def _task_database(tmp_path: Path) -> Path:
    database = tmp_path / "axioms.sqlite3"
    store = TaskStore(database)
    store.save(TaskRecord(request=TaskRequest(goal="Prepare a lecture on spectral graph theory")))
    return database


def test_create_backup_refuses_overwrite_and_verifies_a_disposable_restore(tmp_path: Path) -> None:
    source = _task_database(tmp_path)
    destination = tmp_path / "backups" / "axioms.sqlite3"

    report = create_sqlite_backup(source, destination)

    assert destination.is_file()
    assert report.integrity_check == "ok"
    assert report.restore_verified
    assert "tasks" in report.tables
    with pytest.raises(FileExistsError, match="already exists"):
        create_sqlite_backup(source, destination)


def test_verify_restore_never_changes_the_backup_file(tmp_path: Path) -> None:
    source = _task_database(tmp_path)
    destination = tmp_path / "backup.sqlite3"
    create_sqlite_backup(source, destination)
    original = destination.read_bytes()

    report = verify_sqlite_restore(destination)

    assert report.restore_verified
    assert destination.read_bytes() == original


def test_verify_restore_rejects_missing_or_non_axioms_database(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="not found"):
        verify_sqlite_restore(tmp_path / "missing.sqlite3")
    unrelated = tmp_path / "unrelated.sqlite3"
    unrelated.touch()
    with pytest.raises(ValueError, match="not an Axioms task database"):
        verify_sqlite_restore(unrelated)


def test_backup_cli_creates_and_verifies_a_new_backup(tmp_path: Path) -> None:
    source = _task_database(tmp_path)
    destination = tmp_path / "cli-backup.sqlite3"
    repository = Path(__file__).parents[1]

    result = subprocess.run(
        [
            sys.executable,
            "scripts/backup_sqlite.py",
            "create",
            "--source",
            str(source),
            "--destination",
            str(destination),
        ],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["restore_verified"]
