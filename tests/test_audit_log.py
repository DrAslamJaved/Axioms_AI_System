from __future__ import annotations

import json
import logging

from axioms.audit_log import (
    LOGGER,
    bind_request_id,
    current_request_id,
    log_event,
    reset_request_id,
    select_request_id,
)


def test_select_request_id_reuses_only_bounded_safe_values() -> None:
    assert select_request_id("study-run_2026") == "study-run_2026"
    assert len(select_request_id("too short")) == 32
    assert len(select_request_id("contains spaces")) == 32
    assert len(select_request_id("x" * 129)) == 32


def test_audit_event_is_json_correlated_and_drops_unapproved_fields(caplog) -> None:
    caplog.set_level(logging.INFO, logger=LOGGER.name)
    token = bind_request_id("review-run_2026")
    try:
        payload = log_event(
            "task_approval_recorded",
            task_id="task_123",
            status="approved",
            risk_tier="high",
            raw_goal="sensitive request text",
            document_text="private document body",
        )
    finally:
        reset_request_id(token)

    assert current_request_id() is None
    assert payload["request_id"] == "review-run_2026"
    assert payload["task_id"] == "task_123"
    assert "raw_goal" not in payload
    rendered = json.loads(caplog.records[-1].message)
    assert rendered == payload
    assert "document_text" not in rendered
