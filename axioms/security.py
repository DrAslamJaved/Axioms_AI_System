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


class SecurityConfigurationError(ValueError):
    """Raised when AXIOMS_API_KEYS is present but unsafe or invalid."""


def _named_keys() -> dict[str, str] | None:
    """Parse ``AXIOMS_API_KEYS`` (JSON object: principal → secret)."""
    raw = os.getenv("AXIOMS_API_KEYS", "").strip()
    if not raw:
        return None
    try:
        mapping = json.loads(raw)
    except json.JSONDecodeError as error:
        raise SecurityConfigurationError("AXIOMS_API_KEYS must contain valid JSON.") from error
    if not isinstance(mapping, dict) or not mapping:
        raise SecurityConfigurationError("AXIOMS_API_KEYS must be a non-empty JSON object.")
    if any(
        not isinstance(principal, str)
        or not principal.strip()
        or not isinstance(secret, str)
        or not secret.strip()
        for principal, secret in mapping.items()
    ):
        raise SecurityConfigurationError(
            "AXIOMS_API_KEYS principals and secrets must be non-empty strings."
        )
    normalised = {principal.strip(): secret for principal, secret in mapping.items()}
    if len(normalised) != len(mapping):
        raise SecurityConfigurationError("AXIOMS_API_KEYS contains duplicate principal names.")
    if len(set(normalised.values())) != len(normalised):
        raise SecurityConfigurationError("AXIOMS_API_KEYS must not reuse a secret across principals.")
    return normalised


def _named_keys_or_service_error() -> dict[str, str] | None:
    """Return named keys or fail protected operations closed with HTTP 503."""
    try:
        return _named_keys()
    except SecurityConfigurationError as error:
        raise HTTPException(
            status_code=503,
            detail="Authentication is misconfigured; protected operations are unavailable.",
        ) from error


def configured_api_key() -> str | None:
    """Return the single legacy key, or ``None``."""
    key = os.getenv("AXIOMS_API_KEY", "").strip()
    return key or None


def auth_enabled() -> bool:
    try:
        return _named_keys() is not None or configured_api_key() is not None
    except SecurityConfigurationError:
        # A broken configured authentication system must never be reported as open.
        return True


def auth_mode() -> str:
    """Return ``'named'``, ``'single'``, or ``'open-dev'``."""
    try:
        named = _named_keys()
    except SecurityConfigurationError:
        return "misconfigured"
    if named:
        return "named"
    if configured_api_key():
        return "single"
    return "open-dev"


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """FastAPI dependency. Enforces the API key when one is configured."""

    named = _named_keys_or_service_error()
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

    named = _named_keys_or_service_error()
    if not named or not x_api_key:
        return None
    for principal, secret in named.items():
        if hmac.compare_digest(x_api_key, secret):
            return principal
    return None
