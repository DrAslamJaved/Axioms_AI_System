import pytest
from fastapi import HTTPException

from axioms.security import auth_enabled, configured_api_key, require_api_key


def test_auth_is_open_when_no_key_configured(monkeypatch) -> None:
    monkeypatch.delenv("AXIOMS_API_KEY", raising=False)
    assert configured_api_key() is None
    assert auth_enabled() is False
    # No key configured -> dependency allows the request through.
    assert require_api_key(None) is None


def test_missing_key_is_rejected_when_auth_enabled(monkeypatch) -> None:
    monkeypatch.setenv("AXIOMS_API_KEY", "s3cret")
    assert auth_enabled() is True
    with pytest.raises(HTTPException) as excinfo:
        require_api_key(None)
    assert excinfo.value.status_code == 401


def test_wrong_key_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("AXIOMS_API_KEY", "s3cret")
    with pytest.raises(HTTPException):
        require_api_key("nope")


def test_correct_key_is_accepted(monkeypatch) -> None:
    monkeypatch.setenv("AXIOMS_API_KEY", "s3cret")
    assert require_api_key("s3cret") is None
