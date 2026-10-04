import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from axioms.llm import (
    AnthropicProvider,
    DisabledProvider,
    FakeProvider,
    LLMConfigurationError,
    LLMDisabledError,
    LLMMessage,
    OpenAIProvider,
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
    assert result.input_tokens == 0
    assert result.output_tokens == 0


def test_anthropic_provider_preserves_provider_reported_token_counts(tmp_path: Path, monkeypatch) -> None:
    response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="Complete")],
        stop_reason="end_turn",
        usage=SimpleNamespace(input_tokens=21, output_tokens=13),
    )

    class FakeAnthropic:
        def __init__(self, *, api_key: str) -> None:
            self.messages = SimpleNamespace(create=lambda **_kwargs: response)

    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(Anthropic=FakeAnthropic))
    monkeypatch.setenv("AXIOMS_DATABASE_URL", f"sqlite:///{tmp_path / 'usage.sqlite3'}")
    result = AnthropicProvider("test-key").complete([LLMMessage("user", "hello")])
    assert (result.input_tokens, result.output_tokens) == (21, 13)


def test_openai_provider_preserves_provider_reported_token_counts(tmp_path: Path, monkeypatch) -> None:
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Complete"), finish_reason="stop")],
        usage=SimpleNamespace(prompt_tokens=34, completion_tokens=8),
    )

    class FakeOpenAI:
        def __init__(self, *, api_key: str) -> None:
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **_kwargs: response))

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    monkeypatch.setenv("AXIOMS_DATABASE_URL", f"sqlite:///{tmp_path / 'usage.sqlite3'}")
    result = OpenAIProvider("test-key").complete([LLMMessage("user", "hello")])
    assert (result.input_tokens, result.output_tokens) == (34, 8)


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
