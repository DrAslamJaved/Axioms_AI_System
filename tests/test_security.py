import json

import pytest
from fastapi import HTTPException

from axioms.security import _named_keys, auth_enabled, auth_mode, configured_api_key, require_api_key, resolve_principal


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


def test_named_keys_returns_none_on_invalid_json(monkeypatch) -> None:
    monkeypatch.setenv("AXIOMS_API_KEYS", "not-json")
    assert _named_keys() is None


def test_named_keys_returns_none_on_empty_object(monkeypatch) -> None:
    monkeypatch.setenv("AXIOMS_API_KEYS", "{}")
    assert _named_keys() is None


def test_named_keys_returns_none_on_non_object(monkeypatch) -> None:
    monkeypatch.setenv("AXIOMS_API_KEYS", '["a", "b"]')
    assert _named_keys() is None


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
