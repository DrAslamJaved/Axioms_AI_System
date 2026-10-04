"""Minimal structured local audit logging with request correlation and strict field allowlisting."""

from __future__ import annotations

import json
import logging
import re
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from uuid import uuid4

_REQUEST_ID = ContextVar[str | None]("axioms_request_id", default=None)
_REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{8,128}\Z")
_ALLOWED_FIELDS = {
    "task_id",
    "document_id",
    "status",
    "status_code",
    "risk_tier",
    "decision",
    "override_blocking",
    "method",
    "path",
    "duration_ms",
    "principal",
    "provider",
}
LOGGER = logging.getLogger("axioms.audit")


def select_request_id(supplied: str | None) -> str:
    """Accept only a bounded safe caller correlation ID; otherwise create a new one."""
    candidate = (supplied or "").strip()
    return candidate if _REQUEST_ID_PATTERN.fullmatch(candidate) else uuid4().hex


def bind_request_id(request_id: str) -> Token:
    """Bind a request ID for the current async task and return its reset token."""
    return _REQUEST_ID.set(request_id)


def current_request_id() -> str | None:
    return _REQUEST_ID.get()


def reset_request_id(token: Token) -> None:
    _REQUEST_ID.reset(token)


def log_event(event: str, **fields: object) -> dict[str, object]:
    """Emit one JSON audit line without request bodies, document text, or arbitrary caller fields."""
    payload: dict[str, object] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event": event,
        "request_id": current_request_id(),
    }
    payload.update({key: value for key, value in fields.items() if key in _ALLOWED_FIELDS})
    LOGGER.info(json.dumps(payload, sort_keys=True, default=str))
    return payload
