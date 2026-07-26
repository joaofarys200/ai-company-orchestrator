from __future__ import annotations

import inspect
import re
from collections.abc import Awaitable, Callable, Iterable
from typing import Protocol, runtime_checkable

from backend.model_harness.contracts import (
    ModelRequest,
    ModelRoute,
    ProviderResult,
)
from backend.model_harness.errors import (
    DuplicateProviderError,
    ProviderRegistryError,
    ProviderUnavailableError,
)


PROVIDER_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


@runtime_checkable
class ModelProvider(Protocol):
    name: str
    default_model: str

    async def generate(
        self,
        request: ModelRequest,
        route: ModelRoute,
        progress,
    ) -> ProviderResult:
        ...


ProviderCallback = Callable[
    [ModelRequest, ModelRoute, object],
    ProviderResult | str | Awaitable[ProviderResult | str],
]


class CallableModelProvider:
    def __init__(
        self,
        name: str,
        default_model: str,
        callback: ProviderCallback,
    ):
        self.name = ProviderRegistry.normalize_name(name)
        self.default_model = str(default_model or "").strip()
        if not self.default_model:
            raise ProviderRegistryError("default_model e obrigatorio.")
        if not callable(callback):
            raise ProviderRegistryError("Provider callback invalido.")
        self._callback = callback

    async def generate(
        self,
        request: ModelRequest,
        route: ModelRoute,
        progress,
    ) -> ProviderResult:
        result = self._callback(request, route, progress)
        if inspect.isawaitable(result):
            result = await result
        if isinstance(result, ProviderResult):
            return result
        if isinstance(result, str):
            return ProviderResult(raw_text=result)
        raise ProviderRegistryError(
            "Provider devolveu um resultado sem contrato."
        )


class ProviderRegistry:
    def __init__(self, providers: Iterable[ModelProvider] | None = None):
        self._providers: dict[str, ModelProvider] = {}
        for provider in providers or ():
            self.register(provider)

    def register(self, provider: ModelProvider) -> None:
        if not isinstance(provider, ModelProvider):
            raise ProviderRegistryError(
                "Provider deve implementar o contrato ModelProvider."
            )
        name = self.normalize_name(provider.name)
        if provider.name != name:
            raise ProviderRegistryError(
                "Provider.name deve estar normalizado em minusculas."
            )
        if name in self._providers:
            raise DuplicateProviderError(
                f"Provider ja registado: {name}."
            )
        if not str(provider.default_model or "").strip():
            raise ProviderRegistryError(
                f"Provider {name} sem default_model."
            )
        self._providers[name] = provider

    def get(self, name: str) -> ModelProvider:
        normalized = self.normalize_name(name)
        try:
            return self._providers[normalized]
        except KeyError as exc:
            raise ProviderUnavailableError(
                f"Provider indisponivel: {normalized}."
            ) from exc

    def has(self, name: str) -> bool:
        try:
            return self.normalize_name(name) in self._providers
        except ProviderRegistryError:
            return False

    def names(self) -> tuple[str, ...]:
        return tuple(self._providers)

    @staticmethod
    def normalize_name(name: str) -> str:
        normalized = str(name or "").strip().lower()
        if not PROVIDER_NAME_PATTERN.fullmatch(normalized):
            raise ProviderRegistryError(
                f"Nome de provider invalido: {normalized or '<vazio>'}."
            )
        return normalized
