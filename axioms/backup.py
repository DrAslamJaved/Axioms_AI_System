"""Explicit, local SQLite backup and restore-verification helpers.

These helpers never restore over a live database. A verification drill copies a
backup into a temporary database, checks integrity there, and then discards the
temporary copy.
"""

from __future__ import annotations

import sqlite3
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

REQUIRED_AXIOMS_TABLES = ("tasks",)


@dataclass(frozen=True, slots=True)
class BackupVerification:
    backup_path: str
    verified_at: str
    integrity_check: str
    tables: tuple[str, ...]
    required_tables: tuple[str, ...]
    restore_verified: bool

    def to_dict(self) -> dict:
        return asdict(self)


def create_sqlite_backup(source: Path, destination: Path) -> BackupVerification:
    """Create one new local backup, refusing to overwrite an existing destination."""
    source = _database_file(source)
    destination = destination.expanduser().resolve()
    if destination.exists():
        raise FileExistsError(f"Backup destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with _readonly_connection(source) as source_connection, sqlite3.connect(destination) as destination_connection:
        source_connection.backup(destination_connection)
    return verify_sqlite_restore(destination)


def verify_sqlite_restore(backup: Path) -> BackupVerification:
    """Verify a backup via a disposable restore drill; never changes the backup or live database."""
    backup = _database_file(backup)
    with tempfile.TemporaryDirectory(prefix="axioms-restore-verify-") as temporary_directory:
        restored = Path(temporary_directory) / "restored.sqlite3"
        with _readonly_connection(backup) as backup_connection, sqlite3.connect(restored) as restored_connection:
            backup_connection.backup(restored_connection)
        with _readonly_connection(restored) as restored_connection:
            integrity_check = restored_connection.execute("PRAGMA integrity_check").fetchone()[0]
            tables = tuple(
                row[0]
                for row in restored_connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
                ).fetchall()
            )
    missing_tables = sorted(set(REQUIRED_AXIOMS_TABLES).difference(tables))
    if integrity_check != "ok":
        raise ValueError(f"Backup integrity check failed: {integrity_check}")
    if missing_tables:
        raise ValueError("Backup is not an Axioms task database; missing table(s): " + ", ".join(missing_tables))
    return BackupVerification(
        backup_path=str(backup),
        verified_at=datetime.now(UTC).isoformat(),
        integrity_check=integrity_check,
        tables=tables,
        required_tables=REQUIRED_AXIOMS_TABLES,
        restore_verified=True,
    )


def _database_file(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"SQLite database file was not found: {resolved}")
    return resolved


def _readonly_connection(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
