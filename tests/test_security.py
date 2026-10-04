import json

import pytest
from fastapi import HTTPException

from axioms.api import app
from axioms.security import (
    AccessRole,
    SecurityConfigurationError,
    _named_keys,
    auth_enabled,
    auth_mode,
    configured_api_key,
    require_api_key,
    require_role,
    resolve_principal,
    resolve_role,
)

# ---------------------------------------------------------------------------
# Single-key mode (backward compat)
# ---------------------------------------------------------------------------


def test_auth_is_open_when_no_key_configured(monkeypatch) -> None:
    monkeypatch.delenv("AXIOMS_API_KEY", raising=False)
    monkeypatch.delenv("AXIOMS_API_KEYS", raising=False)
    assert configured_api_key() is None
    assert auth_enabled() is False
    # No key configured -> dependency allows the request through.
    assert require_api_key(None) is None


def test_missing_key_is_rejected_when_auth_enabled(monkeypatch) -> None:
    monkeypatch.setenv("AXIOMS_API_KEY", "s3cret")
    monkeypatch.delenv("AXIOMS_API_KEYS", raising=False)
    assert auth_enabled() is True
    with pytest.raises(HTTPException) as excinfo:
        require_api_key(None)
    assert excinfo.value.status_code == 401


def test_wrong_key_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("AXIOMS_API_KEY", "s3cret")
    monkeypatch.delenv("AXIOMS_API_KEYS", raising=False)
    with pytest.raises(HTTPException):
        require_api_key("nope")


def test_correct_key_is_accepted(monkeypatch) -> None:
    monkeypatch.setenv("AXIOMS_API_KEY", "s3cret")
    monkeypatch.delenv("AXIOMS_API_KEYS", raising=False)
    assert require_api_key("s3cret") is None


# ---------------------------------------------------------------------------
# _named_keys parsing
# ---------------------------------------------------------------------------


def test_named_keys_returns_none_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("AXIOMS_API_KEYS", raising=False)
    assert _named_keys() is None


def test_named_keys_parses_valid_json(monkeypatch) -> None:
    monkeypatch.setenv("AXIOMS_API_KEYS", json.dumps({"Dr Aslam": "key1", "Lab TA": "key2"}))
    result = _named_keys()
    assert result == {"Dr Aslam": "key1", "Lab TA": "key2"}


def test_role_bearing_named_keys_normalise_with_legacy_administrator_compatibility(monkeypatch) -> None:
    monkeypatch.setenv(
        "AXIOMS_API_KEYS",
        json.dumps(
            {
                "Dr Aslam": {"secret": "admin-key", "role": "admin"},
                "Reviewer": {"secret": "approver-key", "role": "approver"},
                "Observer": {"secret": "viewer-key", "role": "viewer"},
                "Legacy": "legacy-key",
            }
        ),
    )
    assert _named_keys() == {
        "Dr Aslam": "admin-key",
        "Reviewer": "approver-key",
        "Observer": "viewer-key",
        "Legacy": "legacy-key",
    }
    assert resolve_role("admin-key") is AccessRole.ADMIN
    assert resolve_role("approver-key") is AccessRole.APPROVER
    assert resolve_role("viewer-key") is AccessRole.VIEWER
    assert resolve_role("legacy-key") is AccessRole.ADMIN


def test_role_bearing_named_keys_reject_unsafe_role_objects(monkeypatch) -> None:
    monkeypatch.setenv(
        "AXIOMS_API_KEYS", json.dumps({"Reviewer": {"secret": "key", "role": "owner"}})
    )
    with pytest.raises(SecurityConfigurationError, match="role must be one of"):
        _named_keys()

    monkeypatch.setenv(
        "AXIOMS_API_KEYS", json.dumps({"Reviewer": {"secret": "key", "role": "viewer", "extra": 1}})
    )
    with pytest.raises(SecurityConfigurationError, match="exactly 'secret' and 'role'"):
        _named_keys()


def test_named_keys_rejects_invalid_json(monkeypatch) -> None:
    monkeypatch.setenv("AXIOMS_API_KEYS", "not-json")
    with pytest.raises(SecurityConfigurationError):
        _named_keys()


def test_named_keys_rejects_empty_object(monkeypatch) -> None:
    monkeypatch.setenv("AXIOMS_API_KEYS", "{}")
    with pytest.raises(SecurityConfigurationError):
        _named_keys()


def test_named_keys_rejects_non_object(monkeypatch) -> None:
    monkeypatch.setenv("AXIOMS_API_KEYS", '["a", "b"]')
    with pytest.raises(SecurityConfigurationError):
        _named_keys()


# ---------------------------------------------------------------------------
# auth_mode()
# ---------------------------------------------------------------------------


def test_auth_mode_open_dev(monkeypatch) -> None:
    monkeypatch.delenv("AXIOMS_API_KEY", raising=False)
    monkeypatch.delenv("AXIOMS_API_KEYS", raising=False)
    assert auth_mode() == "open-dev"


def test_auth_mode_single(monkeypatch) -> None:
    monkeypatch.setenv("AXIOMS_API_KEY", "s3cret")
    monkeypatch.delenv("AXIOMS_API_KEYS", raising=False)
    assert auth_mode() == "single"


def test_auth_mode_named(monkeypatch) -> None:
    monkeypatch.setenv("AXIOMS_API_KEYS", json.dumps({"Dr Aslam": "key1"}))
    monkeypatch.delenv("AXIOMS_API_KEY", raising=False)
    assert auth_mode() == "named"


def test_auth_mode_named_takes_priority(monkeypatch) -> None:
    """When both AXIOMS_API_KEYS and AXIOMS_API_KEY are set, named wins."""
    monkeypatch.setenv("AXIOMS_API_KEYS", json.dumps({"Dr Aslam": "key1"}))
    monkeypatch.setenv("AXIOMS_API_KEY", "legacy-key")
    assert auth_mode() == "named"


# ---------------------------------------------------------------------------
# resolve_principal()
# ---------------------------------------------------------------------------


def test_resolve_principal_returns_none_without_named_keys(monkeypatch) -> None:
    monkeypatch.delenv("AXIOMS_API_KEYS", raising=False)
    assert resolve_principal("any-key") is None


def test_resolve_principal_returns_none_with_no_key(monkeypatch) -> None:
    monkeypatch.setenv("AXIOMS_API_KEYS", json.dumps({"Dr Aslam": "key1"}))
    assert resolve_principal(None) is None


def test_resolve_principal_returns_matching_principal(monkeypatch) -> None:
    monkeypatch.setenv("AXIOMS_API_KEYS", json.dumps({"Dr Aslam": "key1", "Lab TA": "key2"}))
    assert resolve_principal("key1") == "Dr Aslam"
    assert resolve_principal("key2") == "Lab TA"


def test_resolve_principal_returns_none_for_unknown_key(monkeypatch) -> None:
    monkeypatch.setenv("AXIOMS_API_KEYS", json.dumps({"Dr Aslam": "key1"}))
    assert resolve_principal("wrong") is None


# ---------------------------------------------------------------------------
# Named-key auth flow in require_api_key()
# ---------------------------------------------------------------------------


def test_named_key_missing_header_is_401(monkeypatch) -> None:
    monkeypatch.setenv("AXIOMS_API_KEYS", json.dumps({"Dr Aslam": "key1"}))
    monkeypatch.delenv("AXIOMS_API_KEY", raising=False)
    with pytest.raises(HTTPException) as excinfo:
        require_api_key(None)
    assert excinfo.value.status_code == 401


def test_named_key_wrong_key_is_401(monkeypatch) -> None:
    monkeypatch.setenv("AXIOMS_API_KEYS", json.dumps({"Dr Aslam": "key1"}))
    monkeypatch.delenv("AXIOMS_API_KEY", raising=False)
    with pytest.raises(HTTPException) as excinfo:
        require_api_key("wrong-key")
    assert excinfo.value.status_code == 401


def test_named_key_correct_key_is_accepted(monkeypatch) -> None:
    monkeypatch.setenv("AXIOMS_API_KEYS", json.dumps({"Dr Aslam": "key1", "Lab TA": "key2"}))
    monkeypatch.delenv("AXIOMS_API_KEY", raising=False)
    assert require_api_key("key1") is None
    assert require_api_key("key2") is None


def test_role_dependency_rejects_viewer_but_admits_approver_and_admin(monkeypatch) -> None:
    monkeypatch.setenv(
        "AXIOMS_API_KEYS",
        json.dumps(
            {
                "Approver": {"secret": "approve", "role": "approver"},
                "Viewer": {"secret": "view", "role": "viewer"},
                "Admin": {"secret": "admin", "role": "admin"},
            }
        ),
    )
    dependency = require_role(AccessRole.APPROVER)
    with pytest.raises(HTTPException) as excinfo:
        dependency("view")
    assert excinfo.value.status_code == 403
    assert dependency("approve") is None
    assert dependency("admin") is None


def test_content_bearing_personal_memory_read_routes_require_an_approver(monkeypatch) -> None:
    monkeypatch.setenv(
        "AXIOMS_API_KEYS",
        json.dumps(
            {
                "Reviewer": {"secret": "approve", "role": "approver"},
                "Observer": {"secret": "view", "role": "viewer"},
            }
        ),
    )
    paths = [
        "/personal-kb/entries",
        "/episodic-memory/search",
        "/episodic-memory/{memory_id}/audit",
    ]
    for path in paths:
        route = next(route for route in app.routes if getattr(route, "path", None) == path)
        dependency = route.dependant.dependencies[0].call
        with pytest.raises(HTTPException) as excinfo:
            dependency("view")
        assert excinfo.value.status_code == 403
        assert dependency("approve") is None


def test_reference_document_metadata_route_requires_an_approver(monkeypatch) -> None:
    monkeypatch.setenv(
        "AXIOMS_API_KEYS",
        json.dumps(
            {
                "Reviewer": {"secret": "approve", "role": "approver"},
                "Observer": {"secret": "view", "role": "viewer"},
            }
        ),
    )
    route = next(route for route in app.routes if getattr(route, "path", None) == "/documents/{document_id}")
    dependency = route.dependant.dependencies[0].call

    with pytest.raises(HTTPException) as excinfo:
        dependency("view")
    assert excinfo.value.status_code == 403
    assert dependency("approve") is None


def test_individual_dispatch_job_route_requires_an_approver(monkeypatch) -> None:
    monkeypatch.setenv(
        "AXIOMS_API_KEYS",
        json.dumps(
            {
                "Reviewer": {"secret": "approve", "role": "approver"},
                "Observer": {"secret": "view", "role": "viewer"},
            }
        ),
    )
    route = next(route for route in app.routes if getattr(route, "path", None) == "/dispatch/jobs/{job_id}")
    dependency = route.dependant.dependencies[0].call

    with pytest.raises(HTTPException) as excinfo:
        dependency("view")
    assert excinfo.value.status_code == 403
    assert dependency("approve") is None


def test_dispatch_and_local_execution_routes_require_an_approver(monkeypatch) -> None:
    monkeypatch.setenv(
        "AXIOMS_API_KEYS",
        json.dumps(
            {
                "Reviewer": {"secret": "approve", "role": "approver"},
                "Observer": {"secret": "view", "role": "viewer"},
            }
        ),
    )
    paths = [
        "/tasks/{task_id}/dispatch",
        "/dispatch/jobs/claim",
        "/dispatch/jobs/{job_id}/finish",
        "/dispatch/jobs/{job_id}/renew",
        "/dispatch/run-one",
        "/tasks/{task_id}/execute",
    ]
    for path in paths:
        route = next(route for route in app.routes if getattr(route, "path", None) == path)
        dependency = route.dependant.dependencies[0].call
        with pytest.raises(HTTPException) as excinfo:
            dependency("view")
        assert excinfo.value.status_code == 403
        assert dependency("approve") is None


def test_external_research_discovery_routes_require_an_approver(monkeypatch) -> None:
    monkeypatch.setenv(
        "AXIOMS_API_KEYS",
        json.dumps(
            {
                "Reviewer": {"secret": "approve", "role": "approver"},
                "Observer": {"secret": "view", "role": "viewer"},
            }
        ),
    )
    paths = [
        "/research/discover",
        "/research/discover/arxiv",
        "/research/discover/semantic-scholar",
    ]
    for path in paths:
        route = next(route for route in app.routes if getattr(route, "path", None) == path)
        dependency = route.dependant.dependencies[0].call
        with pytest.raises(HTTPException) as excinfo:
            dependency("view")
        assert excinfo.value.status_code == 403
        assert dependency("approve") is None


def test_durable_knowledge_write_routes_require_an_approver(monkeypatch) -> None:
    monkeypatch.setenv(
        "AXIOMS_API_KEYS",
        json.dumps(
            {
                "Reviewer": {"secret": "approve", "role": "approver"},
                "Observer": {"secret": "view", "role": "viewer"},
            }
        ),
    )
    paths = [
        "/feedback",
        "/personal-kb/proposals",
        "/tasks/{task_id}/memory-proposal",
    ]
    for path in paths:
        route = next(route for route in app.routes if getattr(route, "path", None) == path)
        dependency = route.dependant.dependencies[0].call
        with pytest.raises(HTTPException) as excinfo:
            dependency("view")
        assert excinfo.value.status_code == 403
        assert dependency("approve") is None


def test_optional_llm_generation_routes_require_an_approver(monkeypatch) -> None:
    monkeypatch.setenv(
        "AXIOMS_API_KEYS",
        json.dumps(
            {
                "Reviewer": {"secret": "approve", "role": "approver"},
                "Observer": {"secret": "view", "role": "viewer"},
            }
        ),
    )
    paths = [
        "/lecture-plans",
        "/lecture-plans/docx",
        "/writing-drafts",
        "/writing-drafts/docx",
        "/research-briefs/agentic",
        "/assessment-blueprints",
        "/assessment-blueprints/agentic",
        "/assessment-blueprints/student-docx",
        "/assessment-blueprints/instructor-docx",
        "/content-packages",
        "/content-packages/agentic",
        "/content-packages/docx",
        "/social-media-packages",
        "/social-media-packages/agentic",
        "/social-media-packages/docx",
        "/portfolio-packages",
        "/portfolio-packages/agentic",
        "/portfolio-packages/docx",
        "/autoeval-reports",
        "/autoeval-reports/docx",
    ]
    for path in paths:
        route = next(route for route in app.routes if getattr(route, "path", None) == path)
        dependency = route.dependant.dependencies[0].call
        with pytest.raises(HTTPException) as excinfo:
            dependency("view")
        assert excinfo.value.status_code == 403
        assert dependency("approve") is None


def test_remaining_service_operation_routes_require_an_approver(monkeypatch) -> None:
    monkeypatch.setenv(
        "AXIOMS_API_KEYS",
        json.dumps(
            {
                "Reviewer": {"secret": "approve", "role": "approver"},
                "Observer": {"secret": "view", "role": "viewer"},
            }
        ),
    )
    paths = [
        "/similarity/screen",
        "/tasks",
        "/research-briefs",
        "/research-briefs/docx",
        "/research-briefs/bibtex",
        "/tasks/{task_id}/cross-agent-autoeval",
    ]
    for path in paths:
        route = next(route for route in app.routes if getattr(route, "path", None) == path)
        dependency = route.dependant.dependencies[0].call
        with pytest.raises(HTTPException) as excinfo:
            dependency("view")
        assert excinfo.value.status_code == 403
        assert dependency("approve") is None


def test_detailed_readiness_route_requires_an_approver(monkeypatch) -> None:
    monkeypatch.setenv(
        "AXIOMS_API_KEYS",
        json.dumps(
            {
                "Reviewer": {"secret": "approve", "role": "approver"},
                "Observer": {"secret": "view", "role": "viewer"},
            }
        ),
    )
    route = next(route for route in app.routes if getattr(route, "path", None) == "/system/readiness")
    dependency = route.dependant.dependencies[0].call
    with pytest.raises(HTTPException) as excinfo:
        dependency("view")
    assert excinfo.value.status_code == 403
    assert dependency("approve") is None


def test_specialist_registry_requires_an_authenticated_key(monkeypatch) -> None:
    monkeypatch.setenv(
        "AXIOMS_API_KEYS",
        json.dumps({"Observer": {"secret": "view", "role": "viewer"}}),
    )
    route = next(route for route in app.routes if getattr(route, "path", None) == "/agents")
    dependency = route.dependant.dependencies[0].call
    with pytest.raises(HTTPException) as excinfo:
        dependency(None)
    assert excinfo.value.status_code == 401
    assert dependency("view") is None
