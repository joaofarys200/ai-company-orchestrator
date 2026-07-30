from __future__ import annotations

from threading import Lock

from backend.model_harness.harness import ModelHarness
from backend.model_harness.provider import ProviderRegistry
from backend.model_harness.providers.anthropic import (
    AnthropicMessagesProvider,
)
from backend.model_harness.providers.gemini import GeminiOpenAIProvider
from backend.model_harness.providers.ollama import OllamaChatProvider
from backend.model_harness.telemetry import ModelTelemetry


_DEFAULT_HARNESS: ModelHarness | None = None
_DEFAULT_HARNESS_LOCK = Lock()


def create_runtime_model_harness(
    *,
    ollama_provider: OllamaChatProvider | None = None,
    gemini_provider: GeminiOpenAIProvider | None = None,
    anthropic_provider: AnthropicMessagesProvider | None = None,
    telemetry: ModelTelemetry | None = None,
) -> ModelHarness:
    providers = [
        ollama_provider or OllamaChatProvider(),
        gemini_provider or GeminiOpenAIProvider(),
        anthropic_provider or AnthropicMessagesProvider(),
    ]
    return ModelHarness(
        ProviderRegistry(providers),
        telemetry=telemetry,
    )


def get_runtime_model_harness() -> ModelHarness:
    global _DEFAULT_HARNESS
    if _DEFAULT_HARNESS is None:
        with _DEFAULT_HARNESS_LOCK:
            if _DEFAULT_HARNESS is None:
                _DEFAULT_HARNESS = create_runtime_model_harness()
    return _DEFAULT_HARNESS


def get_model_harness() -> ModelHarness:
    """Return the shared production model runtime."""
    return get_runtime_model_harness()


__all__ = [
    "create_runtime_model_harness",
    "get_model_harness",
    "get_runtime_model_harness",
]
