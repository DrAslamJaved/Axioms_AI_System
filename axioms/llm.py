"""LLM provider seam for the Axioms AI System.

This is the single integration point the Foundation MVP was missing. Every
generative step in the system asks :func:`get_provider` for a provider and then
calls :meth:`LLMProvider.complete`. Nothing else in the codebase imports an LLM
SDK directly, so a new backend is added here and nowhere else.

Design rules that keep the human-governance guarantees intact:

* The default provider is :class:`DisabledProvider`. With no configuration the
  system behaves exactly as the deterministic MVP did: any code path that would
  call a model instead raises :class:`LLMDisabledError`, and callers are
  expected to degrade gracefully rather than fabricate output.
* Real providers (:class:`AnthropicProvider`, :class:`OpenAIProvider`) lazily
  import their SDKs, so the package installs and its tests run without those
  optional dependencies present.
* :class:`FakeProvider` is a deterministic, offline provider used by the test
  suite and by anyone who wants to exercise the agent loop without a key.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

# A sensible, documented default. Model identifiers change over time; the exact
# string is expected to be supplied through AXIOMS_LLM_MODEL in deployment and
# verified against the provider's current model list.
DEFAULT_ANTHROPIC_MODEL = "claude-3-5-sonnet-latest"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


class LLMDisabledError(RuntimeError):
    """Raised when a generative step is attempted while no provider is enabled."""


class LLMConfigurationError(RuntimeError):
    """Raised when a provider is selected but its configuration is incomplete."""


@dataclass(frozen=True, slots=True)
class LLMMessage:
    """One chat message. ``role`` is ``system``, ``user`` or ``assistant``."""

    role: str
    content: str


@dataclass(frozen=True, slots=True)
class LLMResult:
    """The provider-agnostic result of a completion."""

    text: str
    provider: str
    model: str
    stop_reason: str | None = None


@runtime_checkable
class LLMProvider(Protocol):
    """Minimal contract every backend implements."""

    name: str

    def complete(
        self,
        messages: Sequence[LLMMessage],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> LLMResult: ...


class DisabledProvider:
    """The safe default: never generates, always fails loudly."""

    name = "disabled"

    def complete(
        self,
        messages: Sequence[LLMMessage],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> LLMResult:
        raise LLMDisabledError(
            "The LLM provider is disabled. Set AXIOMS_LLM_PROVIDER to 'anthropic' "
            "or 'openai' and supply the matching API key to enable generation."
        )


class FakeProvider:
    """Deterministic offline provider for tests and local dry runs.

    ``responder`` receives the full message list and returns the assistant text,
    which makes it easy to assert exactly what the agent sent to the model.
    """

    name = "fake"

    def __init__(self, responder: Callable[[Sequence[LLMMessage]], str], *, model: str = "fake-1") -> None:
        self._responder = responder
        self._model = model

    def complete(
        self,
        messages: Sequence[LLMMessage],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> LLMResult:
        return LLMResult(text=self._responder(messages), provider=self.name, model=self._model, stop_reason="stop")


def _split_system(messages: Sequence[LLMMessage]) -> tuple[str | None, list[LLMMessage]]:
    system = next((m.content for m in messages if m.role == "system"), None)
    conversation = [m for m in messages if m.role != "system"]
    return system, conversation


class AnthropicProvider:
    """Anthropic Messages API backend. The SDK is imported lazily."""

    name = "anthropic"

    def __init__(self, api_key: str, *, model: str = DEFAULT_ANTHROPIC_MODEL) -> None:
        if not api_key:
            raise LLMConfigurationError("ANTHROPIC_API_KEY is required for the anthropic provider.")
        self._api_key = api_key
        self._model = model

    def complete(
        self,
        messages: Sequence[LLMMessage],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> LLMResult:
        try:
            import anthropic
        except ImportError as error:  # pragma: no cover - exercised only with the extra installed
            raise LLMConfigurationError(
                "The 'anthropic' package is not installed. Install with: pip install '.[agentic]'."
            ) from error
        client = anthropic.Anthropic(api_key=self._api_key)
        system, conversation = _split_system(messages)
        response = client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system or "You are a careful, evidence-bound research assistant.",
            messages=[{"role": m.role, "content": m.content} for m in conversation],
        )
        text = "".join(block.text for block in response.content if getattr(block, "type", None) == "text")
        return LLMResult(text=text, provider=self.name, model=self._model, stop_reason=response.stop_reason)


class OpenAIProvider:
    """OpenAI Chat Completions backend. The SDK is imported lazily."""

    name = "openai"

    def __init__(self, api_key: str, *, model: str = DEFAULT_OPENAI_MODEL) -> None:
        if not api_key:
            raise LLMConfigurationError("OPENAI_API_KEY is required for the openai provider.")
        self._api_key = api_key
        self._model = model

    def complete(
        self,
        messages: Sequence[LLMMessage],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> LLMResult:
        try:
            from openai import OpenAI
        except ImportError as error:  # pragma: no cover - exercised only with the extra installed
            raise LLMConfigurationError(
                "The 'openai' package is not installed. Install with: pip install '.[agentic]'."
            ) from error
        client = OpenAI(api_key=self._api_key)
        response = client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": m.role, "content": m.content} for m in messages],
        )
        choice = response.choices[0]
        return LLMResult(
            text=choice.message.content or "",
            provider=self.name,
            model=self._model,
            stop_reason=choice.finish_reason,
        )


def get_provider(env: Mapping[str, str] | None = None) -> LLMProvider:
    """Resolve the configured provider from the environment.

    Reads ``AXIOMS_LLM_PROVIDER`` (``disabled`` by default) and, for real
    backends, the matching API key and optional ``AXIOMS_LLM_MODEL`` override.
    """

    env = env if env is not None else os.environ
    name = env.get("AXIOMS_LLM_PROVIDER", "disabled").strip().casefold()
    model_override = env.get("AXIOMS_LLM_MODEL", "").strip() or None
    if name in {"", "disabled", "none", "off"}:
        return DisabledProvider()
    if name == "anthropic":
        return AnthropicProvider(
            env.get("ANTHROPIC_API_KEY", ""),
            model=model_override or DEFAULT_ANTHROPIC_MODEL,
        )
    if name == "openai":
        return OpenAIProvider(
            env.get("OPENAI_API_KEY", ""),
            model=model_override or DEFAULT_OPENAI_MODEL,
        )
    raise ValueError(f"Unknown AXIOMS_LLM_PROVIDER: {name!r}. Use 'disabled', 'anthropic', or 'openai'.")
