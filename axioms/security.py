"""Authentication and principal resolution for mutating endpoints.

The Foundation MVP's central promise -- "human approval precedes any external
action" -- was not actually enforced: every endpoint was open, so anyone who
could reach the port could approve tasks. This module closes that gap.

Two modes are supported:

* **Named keys** (``AXIOMS_API_KEYS``): a JSON object mapping principal names to
  secrets, e.g. ``{"Dr Aslam": "key1", "Lab TA": "key2"}``. The principal is
  derived from the authenticated key, so ``approved_by`` is unforgeable.
* **Single key** (``AXIOMS_API_KEY``): backward-compatible single secret with no
  identity binding. ``approved_by`` still comes from the request body -- honest
  but not authenticated.

When neither is set the app runs in open development mode, reported truthfully
by ``GET /health``.
"""

from __future__ import annotations

import hmac
import json
import os

from fastapi import Header, HTTPException


def _named_keys() -> dict[str, str] | None:
    """Parse ``AXIOMS_API_KEYS`` (JSON object: principal → secret)."""
    raw = os.getenv("AXIOMS_API_KEYS", "").strip()
    if not raw:
        return None
    try:
        mapping = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(mapping, dict) or not mapping:
        return None
    return {str(k): str(v) for k, v in mapping.items() if k and v}


def configured_api_key() -> str | None:
    """Return the single legacy key, or ``None``."""
    key = os.getenv("AXIOMS_API_KEY", "").strip()
    return key or None


def auth_enabled() -> bool:
    return _named_keys() is not None or configured_api_key() is not None


def auth_mode() -> str:
    """Return ``'named'``, ``'single'``, or ``'open-dev'``."""
    if _named_keys():
        return "named"
    if configured_api_key():
        return "single"
    return "open-dev"


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """FastAPI dependency. Enforces the API key when one is configured."""

    named = _named_keys()
    if named:
        if not x_api_key:
            raise HTTPException(status_code=401, detail="Missing or invalid API key.")
        for _principal, secret in named.items():
            if hmac.compare_digest(x_api_key, secret):
                return
        raise HTTPException(status_code=401, detail="Missing or invalid API key.")

    expected = configured_api_key()
    if expected is None:
        return
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Missing or invalid API key.")


def resolve_principal(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> str | None:
    """Return the authenticated principal name, or ``None`` in single-key/open mode.

    In named-key mode, the principal is derived from whichever key matched.
    This is the identity recorded for approvals -- it cannot be self-asserted.
    """

    named = _named_keys()
    if not named or not x_api_key:
        return None
    for principal, secret in named.items():
        if hmac.compare_digest(x_api_key, secret):
            return principal
    return None
