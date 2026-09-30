"""Shared test setup.

Runs before any test module (and therefore before ``axioms.api`` is imported,
which instantiates the store at import time). It points the database at a
throwaway temp file and clears the optional-behaviour environment variables so
each test starts from the deterministic default posture.
"""

import os
import tempfile
from pathlib import Path

_TMP_DB = Path(tempfile.gettempdir()) / "axioms_test_db" / "axioms.sqlite3"
_TMP_DB.parent.mkdir(parents=True, exist_ok=True)
os.environ["AXIOMS_DATABASE_URL"] = f"sqlite:///{_TMP_DB}"

for _var in ("AXIOMS_API_KEY", "AXIOMS_LLM_PROVIDER", "AXIOMS_APPROVAL_MODE", "AXIOMS_LLM_MODEL"):
    os.environ.pop(_var, None)
