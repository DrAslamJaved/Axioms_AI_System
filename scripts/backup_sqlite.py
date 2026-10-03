"""Create a new local SQLite backup or verify it through a disposable restore drill."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from axioms.backup import create_sqlite_backup, verify_sqlite_restore


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create", help="Create one new backup and verify its disposable restore.")
    create.add_argument("--source", type=Path, required=True, help="Existing SQLite database file.")
    create.add_argument("--destination", type=Path, required=True, help="New backup file; it must not exist.")
    verify = subparsers.add_parser("verify-restore", help="Verify a backup without restoring it over live data.")
    verify.add_argument("--backup", type=Path, required=True, help="Existing SQLite backup file.")
    args = parser.parse_args()
    try:
        report = (
            create_sqlite_backup(args.source, args.destination)
            if args.command == "create"
            else verify_sqlite_restore(args.backup)
        )
    except (FileNotFoundError, FileExistsError, ValueError, sqlite3.Error) as error:
        print(f"FAIL: {error}")
        return 1
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
