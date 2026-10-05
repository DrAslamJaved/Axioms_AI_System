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

When neither is set the app runs in open development mode unless
``AXIOMS_REQUIRE_AUTH=true`` is explicitly configured. In that strict posture,
protected operations fail closed until an API key is supplied. Deployment
posture is available only through the authenticated readiness report, not the
public liveness probe.
"""

from __future__ import annotations

import hmac
import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from fastapi import Header, HTTPException

from axioms.audit_log import log_event


class SecurityConfigurationError(ValueError):
    """Raised when AXIOMS_API_KEYS is present but unsafe or invalid."""


class AccessRole(StrEnum):
    """Minimum authority for a named API key."""

    VIEWER = "viewer"
    APPROVER = "approver"
    ADMIN = "admin"


_ROLE_RANK = {AccessRole.VIEWER: 0, AccessRole.APPROVER: 1, AccessRole.ADMIN: 2}
_EXTERNAL_LLM_PROVIDERS = frozenset({"anthropic", "openai"})


@dataclass(frozen=True, slots=True)
class NamedCredential:
    secret: str
    role: AccessRole


def _named_credentials() -> dict[str, NamedCredential] | None:
    """Parse legacy and role-bearing ``AXIOMS_API_KEYS`` formats fail-closed.

    Legacy ``{"Principal": "secret"}`` entries remain administrator-equivalent
    for compatibility. New entries must explicitly provide ``secret`` and
    ``role``, for example ``{"Principal": {"secret": "...", "role": "approver"}}``.
    """
    raw = os.getenv("AXIOMS_API_KEYS", "").strip()
    if not raw:
        return None
    try:
        mapping = json.loads(raw)
    except json.JSONDecodeError as error:
        raise SecurityConfigurationError("AXIOMS_API_KEYS must contain valid JSON.") from error
    if not isinstance(mapping, dict) or not mapping:
        raise SecurityConfigurationError("AXIOMS_API_KEYS must be a non-empty JSON object.")

    normalised: dict[str, NamedCredential] = {}
    for principal, value in mapping.items():
        if not isinstance(principal, str) or not principal.strip():
            raise SecurityConfigurationError("AXIOMS_API_KEYS principals must be non-empty strings.")
        if isinstance(value, str):
            credential = NamedCredential(secret=value, role=AccessRole.ADMIN)
        elif isinstance(value, dict):
            if set(value) != {"secret", "role"}:
                raise SecurityConfigurationError(
                    "Role-bearing AXIOMS_API_KEYS entries require exactly 'secret' and 'role'."
                )
            secret, role = value["secret"], value["role"]
            if not isinstance(secret, str) or not secret.strip() or not isinstance(role, str):
                raise SecurityConfigurationError(
                    "Role-bearing AXIOMS_API_KEYS entries require non-empty string secret and role."
                )
            try:
                credential = NamedCredential(secret=secret, role=AccessRole(role.strip().casefold()))
            except ValueError as error:
                valid = ", ".join(role.value for role in AccessRole)
                raise SecurityConfigurationError(
                    f"AXIOMS_API_KEYS role must be one of: {valid}."
                ) from error
        else:
            raise SecurityConfigurationError(
                "AXIOMS_API_KEYS values must be legacy secrets or role-bearing objects."
            )
        if not credential.secret.strip():
            raise SecurityConfigurationError("AXIOMS_API_KEYS secrets must be non-empty strings.")
        normalised[principal.strip()] = credential
    if len(normalised) != len(mapping):
        raise SecurityConfigurationError("AXIOMS_API_KEYS contains duplicate principal names.")
    if len({credential.secret for credential in normalised.values()}) != len(normalised):
        raise SecurityConfigurationError("AXIOMS_API_KEYS must not reuse a secret across principals.")
    return normalised


def _named_keys() -> dict[str, str] | None:
    """Return the legacy principal → secret view used by existing integrations."""
    credentials = _named_credentials()
    return {principal: item.secret for principal, item in credentials.items()} if credentials else None


def _named_keys_or_service_error() -> dict[str, str] | None:
    """Return named keys or fail protected operations closed with HTTP 503."""
    try:
        return _named_keys()
    except SecurityConfigurationError as error:
        raise HTTPException(
            status_code=503,
            detail="Authentication is misconfigured; protected operations are unavailable.",
        ) from error


def _named_credentials_or_service_error() -> dict[str, NamedCredential] | None:
    """Return role-bearing named credentials or fail protected operations closed with HTTP 503."""
    try:
        return _named_credentials()
    except SecurityConfigurationError as error:
        raise HTTPException(
            status_code=503,
            detail="Authentication is misconfigured; protected operations are unavailable.",
        ) from error


def configured_api_key() -> str | None:
    """Return the single legacy key, or ``None``."""
    key = os.getenv("AXIOMS_API_KEY", "").strip()
    return key or None


def auth_required() -> bool:
    """Return whether a deployment must fail closed without configured credentials."""
    return os.getenv("AXIOMS_REQUIRE_AUTH", "false").strip().casefold() in {"1", "true", "yes"}


def auth_enabled() -> bool:
    try:
        return auth_required() or _named_keys() is not None or configured_api_key() is not None
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
    if auth_required():
        return "required-unconfigured"
    return "open-dev"


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """FastAPI dependency. Enforces the API key when one is configured."""

    named = _named_keys_or_service_error()
    if named:
        if not x_api_key:
            raise HTTPException(status_code=401, detail="Missing or invalid API key.")
        for secret in named.values():
            if hmac.compare_digest(x_api_key, secret):
                return
        raise HTTPException(status_code=401, detail="Missing or invalid API key.")

    expected = configured_api_key()
    if expected is None:
        if auth_required():
            raise HTTPException(
                status_code=503,
                detail="Authentication is required but no API key is configured; protected operations are unavailable.",
            )
        return
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Missing or invalid API key.")


def resolve_principal(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> str | None:
    """Return the authenticated principal name, or ``None`` in single-key/open mode.

    In named-key mode, the principal is derived from whichever key matched.
    This is the identity recorded for approvals -- it cannot be self-asserted.
    """

    named = _named_credentials_or_service_error()
    if not named or not x_api_key:
        return None
    for principal, credential in named.items():
        if hmac.compare_digest(x_api_key, credential.secret):
            return principal
    return None


def resolve_role(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> AccessRole | None:
    """Return the named-key role, or ``None`` for legacy single-key/open-development modes."""
    named = _named_credentials_or_service_error()
    if not named or not x_api_key:
        return None
    for credential in named.values():
        if hmac.compare_digest(x_api_key, credential.secret):
            return credential.role
    return None


def ensure_role(role: AccessRole | None, required: AccessRole) -> None:
    """Reject an authenticated named principal below the required authority.

    ``None`` is deliberately compatible with open-development and legacy
    single-key modes; production named-key deployments receive the separation.
    """
    if role is not None and _ROLE_RANK[role] < _ROLE_RANK[required]:
        raise HTTPException(status_code=403, detail=f"This operation requires the {required.value} role.")


def require_role(required: AccessRole) -> Callable[[str | None], None]:
    """Create a FastAPI dependency for a minimum named-key role."""

    def dependency(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
        named = _named_credentials_or_service_error()
        if named:
            if not x_api_key:
                raise HTTPException(status_code=401, detail="Missing or invalid API key.")
            for credential in named.values():
                if hmac.compare_digest(x_api_key, credential.secret):
                    ensure_role(credential.role, required)
                    return
            raise HTTPException(status_code=401, detail="Missing or invalid API key.")
        require_api_key(x_api_key)

    return dependency


def require_external_provider_consent(
    x_axioms_allow_external_provider: str | None = Header(
        default=None, alias="X-Axioms-Allow-External-Provider"
    ),
) -> None:
    """Require an explicit request signal before a configured external LLM is used.

    The disabled provider and local deterministic fallbacks remain available
    without this header. A configured Anthropic or OpenAI provider is external,
    so the authorized human caller must opt in for each request.
    """
    provider = os.getenv("AXIOMS_LLM_PROVIDER", "disabled").strip().casefold()
    consented = (x_axioms_allow_external_provider or "").strip().casefold() in {"1", "true", "yes"}
    if provider in _EXTERNAL_LLM_PROVIDERS and not consented:
        log_event("external_provider_consent_missing", provider=provider)
        raise HTTPException(
            status_code=428,
            detail="External LLM use requires X-Axioms-Allow-External-Provider: true for this request.",
        )
    if provider in _EXTERNAL_LLM_PROVIDERS:
        log_event("external_provider_consent_accepted", provider=provider)
