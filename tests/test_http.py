"""End-to-end HTTP tests via Starlette's TestClient.

Unlike the handler-level tests, these exercise routing, request validation at
the HTTP boundary, authentication, and the real streamed DOCX response.
"""

import json

from fastapi.testclient import TestClient

from axioms.api import app

client = TestClient(app)


def _lecture_body(outcomes: int = 2) -> dict:
    return {
        "topic": "Spectral Graph Theory",
        "course_level": "Graduate",
        "duration_minutes": 75,
        "audience": "MS Mathematics",
        "learning_outcomes": [f"Outcome {i}" for i in range(outcomes)],
    }


def test_health_reports_posture_and_needs_no_auth() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["auth"] == "open-dev"
    assert body["llm_provider"] == "disabled"
    assert body["approval_mode"] == "strict"


def test_lecture_plan_validation_rejects_too_few_outcomes() -> None:
    response = client.post("/lecture-plans", json=_lecture_body(outcomes=1))
    assert response.status_code == 422


def test_lecture_plan_happy_path_sums_to_duration() -> None:
    response = client.post("/lecture-plans", json=_lecture_body())
    assert response.status_code == 200
    assert sum(section["minutes"] for section in response.json()["sections"]) == 75


def test_lecture_docx_streams_a_real_word_file() -> None:
    response = client.post("/lecture-plans/docx", json=_lecture_body())
    assert response.status_code == 200
    assert response.content[:2] == b"PK"


def test_mutating_endpoint_requires_api_key_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("AXIOMS_API_KEY", "s3cret")
    unauth = client.post("/tasks", json={"goal": "Prepare a lecture on spectral graph theory"})
    assert unauth.status_code == 401
    authed = client.post(
        "/tasks",
        json={"goal": "Prepare a lecture on spectral graph theory"},
        headers={"X-API-Key": "s3cret"},
    )
    assert authed.status_code == 200


def test_approval_requires_a_named_approver() -> None:
    created = client.post("/tasks", json={"goal": "Prepare a lecture on spectral graph theory"})
    task_id = created.json()["task_id"]

    missing = client.post(f"/tasks/{task_id}/approval", json={"decision": "approve"})
    assert missing.status_code == 422

    approved = client.post(
        f"/tasks/{task_id}/approval",
        json={"decision": "approve", "approved_by": "Dr Aslam", "note": "Reviewed"},
    )
    assert approved.status_code == 200
    assert approved.json()["approved_by"] == "Dr Aslam"


def test_task_lifecycle_requires_approval_then_final_review() -> None:
    created = client.post("/tasks", json={"goal": "Prepare a lecture on spectral graph theory"})
    task_id = created.json()["task_id"]

    blocked = client.post(f"/tasks/{task_id}/execute")
    assert blocked.status_code == 409

    authorised = client.post(
        f"/tasks/{task_id}/approval",
        json={"decision": "approve", "approved_by": "Dr Aslam", "note": "Proceed locally"},
    )
    assert authorised.json()["status"] == "approved"

    executed = client.post(f"/tasks/{task_id}/execute")
    assert executed.status_code == 200
    assert executed.json()["status"] == "awaiting_review"
    assert executed.json()["deliverables"]
    assert any(step["kind"] == "agent_dispatched" for step in executed.json()["agent_trace"])

    completed = client.post(
        f"/tasks/{task_id}/approval",
        json={"decision": "approve", "approved_by": "Dr Aslam", "note": "Final review"},
    )
    assert completed.json()["status"] == "completed"


def test_task_carries_risk_tier_and_policy_reason() -> None:
    created = client.post("/tasks", json={"goal": "Email a course announcement to the mailing list"})
    body = created.json()
    assert body["risk_tier"] == "elevated"
    assert "External" in body["policy_reason"]


# ---------------------------------------------------------------------------
# Blocking enforcement for HIGH-risk tasks
# ---------------------------------------------------------------------------


def test_high_risk_task_blocks_approval_without_override() -> None:
    """A HIGH-risk task (containing sensitive keywords) returns 409 unless
    the caller explicitly acknowledges the data-governance issue."""
    created = client.post("/tasks", json={"goal": "Export student grades for the registrar"})
    body = created.json()
    assert body["risk_tier"] == "high"

    task_id = body["task_id"]
    blocked = client.post(
        f"/tasks/{task_id}/approval",
        json={"decision": "approve", "approved_by": "Dr Aslam", "note": "Reviewed"},
    )
    assert blocked.status_code == 409
    assert "HIGH risk" in blocked.json()["detail"]


def test_high_risk_task_approved_with_override() -> None:
    """With override_blocking=true the caller explicitly acknowledges
    the data-governance issue and approval proceeds."""
    created = client.post("/tasks", json={"goal": "Export student grades for the registrar"})
    task_id = created.json()["task_id"]

    approved = client.post(
        f"/tasks/{task_id}/approval",
        json={
            "decision": "approve",
            "approved_by": "Dr Aslam",
            "note": "Data governance reviewed",
            "override_blocking": True,
        },
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_by"] == "Dr Aslam"


# ---------------------------------------------------------------------------
# Named-key principal resolution at the HTTP level
# ---------------------------------------------------------------------------


def test_named_key_principal_overrides_body_approver(monkeypatch) -> None:
    """In named-key mode the approver identity comes from the authenticated
    key, not the request body, so it cannot be self-asserted."""
    monkeypatch.setenv("AXIOMS_API_KEYS", json.dumps({"Dr Aslam": "key1"}))
    monkeypatch.delenv("AXIOMS_API_KEY", raising=False)

    created = client.post(
        "/tasks",
        json={"goal": "Prepare a lecture on spectral graph theory"},
        headers={"X-API-Key": "key1"},
    )
    task_id = created.json()["task_id"]

    # The body says "Imposter" but the key resolves to "Dr Aslam"
    approved = client.post(
        f"/tasks/{task_id}/approval",
        json={"decision": "approve", "approved_by": "Imposter", "note": "Reviewed"},
        headers={"X-API-Key": "key1"},
    )
    assert approved.status_code == 200
    assert approved.json()["approved_by"] == "Dr Aslam"


def test_health_reports_named_auth_mode(monkeypatch) -> None:
    monkeypatch.setenv("AXIOMS_API_KEYS", json.dumps({"Dr Aslam": "key1"}))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["auth"] == "named"


# ---------------------------------------------------------------------------
# LLM misconfiguration → 503
# ---------------------------------------------------------------------------


def test_agentic_endpoint_returns_503_on_llm_misconfiguration(monkeypatch) -> None:
    """When the LLM provider is selected but missing its API key,
    the agentic endpoint returns 503, not 500."""
    monkeypatch.setenv("AXIOMS_LLM_PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    payload = {
        "research_question": "What are recent advances in graph neural networks?",
        "scope": "Survey of GNN architectures published since 2020",
        "sources": [
            {
                "source_id": "s1",
                "title": "Semi-Supervised Classification with Graph Convolutional Networks",
                "authors": ["Thomas Kipf", "Max Welling"],
                "year": 2017,
                "publication_kind": "journal_article",
                "doi": "10.48550/arXiv.1609.02907",
                "peer_reviewed": True,
                "supported_claim": "GCNs achieve state-of-the-art on citation networks.",
            }
        ],
    }
    response = client.post("/research-briefs/agentic", json=payload)
    assert response.status_code == 503
    assert "misconfigured" in response.json()["detail"]
