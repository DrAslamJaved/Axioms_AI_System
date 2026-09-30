"""Lightweight authentication for mutating endpoints.

The Foundation MVP's central promise -- "human approval precedes any external
action" -- was not actually enforced: every endpoint was open, so anyone who
could reach the port could approve tasks. This module closes that gap with an
API-key check appropriate to the current stage, and it records *who* approved.

Posture:

* Set ``AXIOMS_API_KEY`` to require a matching ``X-API-Key`` header on every
  state-changing request. Reads (health, agent list, readiness, task fetch)
  stay open.
* If ``AXIOMS_API_KEY`` is unset the app runs in open development mode. That is
  reported truthfully by ``GET /health`` so it can never be mistaken for a
  secured deployment. Production must set the key (and, as a next step, map keys
  to real user identities).
"""

from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException


def configured_api_key() -> str | None:
    key = os.getenv("AXIOMS_API_KEY", "").strip()
    return key or None


def auth_enabled() -> bool:
    return configured_api_key() is not None


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """FastAPI dependency. Enforces the API key when one is configured."""

    expected = configured_api_key()
    if expected is None:
        return
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Missing or invalid API key.")
