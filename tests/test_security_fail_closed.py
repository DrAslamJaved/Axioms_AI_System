import pytest
from fastapi import HTTPException

from axioms.security import auth_enabled, auth_mode, require_api_key, resolve_principal


def test_invalid_named_key_configuration_fails_closed(monkeypatch) -> None:
    monkeypatch.setenv("AXIOMS_API_KEYS", "not-json")
    monkeypatch.delenv("AXIOMS_API_KEY", raising=False)

    assert auth_mode() == "misconfigured"
    assert auth_enabled() is True

    with pytest.raises(HTTPException) as authentication_error:
        require_api_key("any-key")
    assert authentication_error.value.status_code == 503

    with pytest.raises(HTTPException) as principal_error:
        resolve_principal("any-key")
    assert principal_error.value.status_code == 503


@pytest.mark.parametrize("configuration", ["{}", "[]"])
def test_empty_or_non_object_named_key_configuration_fails_closed(monkeypatch, configuration: str) -> None:
    monkeypatch.setenv("AXIOMS_API_KEYS", configuration)

    with pytest.raises(HTTPException) as error:
        require_api_key("any-key")
    assert error.value.status_code == 503
