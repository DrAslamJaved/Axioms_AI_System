import pytest

from axioms.llm import (
    DisabledProvider,
    FakeProvider,
    LLMConfigurationError,
    LLMDisabledError,
    LLMMessage,
    get_provider,
)


def test_disabled_provider_refuses_to_generate() -> None:
    provider = DisabledProvider()
    with pytest.raises(LLMDisabledError):
        provider.complete([LLMMessage("user", "hello")])


def test_fake_provider_returns_responder_output() -> None:
    provider = FakeProvider(lambda messages: f"echo:{messages[-1].content}")
    result = provider.complete([LLMMessage("user", "ping")])
    assert result.text == "echo:ping"
    assert result.provider == "fake"


def test_get_provider_defaults_to_disabled() -> None:
    assert isinstance(get_provider({}), DisabledProvider)
    assert isinstance(get_provider({"AXIOMS_LLM_PROVIDER": "disabled"}), DisabledProvider)


def test_get_provider_rejects_unknown_backend() -> None:
    with pytest.raises(ValueError, match="Unknown"):
        get_provider({"AXIOMS_LLM_PROVIDER": "mystery"})


def test_get_provider_anthropic_without_key_is_a_configuration_error() -> None:
    with pytest.raises(LLMConfigurationError):
        get_provider({"AXIOMS_LLM_PROVIDER": "anthropic"})


def test_get_provider_openai_without_key_is_a_configuration_error() -> None:
    with pytest.raises(LLMConfigurationError):
        get_provider({"AXIOMS_LLM_PROVIDER": "openai"})
