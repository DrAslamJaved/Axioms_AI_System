"""End-to-end HTTP tests via Starlette's TestClient.

Unlike the handler-level tests, these exercise routing, request validation at
the HTTP boundary, authentication, and the real streamed DOCX response.
"""

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


def test_task_carries_risk_tier_and_policy_reason() -> None:
    created = client.post("/tasks", json={"goal": "Email a course announcement to the mailing list"})
    body = created.json()
    assert body["risk_tier"] == "elevated"
    assert "External" in body["policy_reason"]
