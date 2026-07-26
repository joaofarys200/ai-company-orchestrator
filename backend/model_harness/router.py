from __future__ import annotations

from backend.model_harness.contracts import ModelRequest, ModelRoute
from backend.model_harness.errors import ModelRoutingError
from backend.model_harness.profiles import TaskProfile
from backend.model_harness.provider import ProviderRegistry


class ModelRouter:
    """Deterministic routing infrastructure without task-specific heuristics."""

    def __init__(self, providers: ProviderRegistry):
        self.providers = providers

    def route(
        self,
        request: ModelRequest,
        profile: TaskProfile,
    ) -> ModelRoute:
        requested = tuple(
            item.strip().lower()
            for item in request.model_preferences.providers
            if item.strip()
        )
        preferred = tuple(
            item.strip().lower()
            for item in profile.preferred_providers
            if item.strip()
        )
        if requested:
            candidates = requested
            strict = True
        elif preferred:
            candidates = preferred + tuple(
                item
                for item in self.providers.names()
                if item not in preferred
            )
            strict = False
        else:
            candidates = self.providers.names()
            strict = False
        provider_name = next(
            (
                candidate
                for candidate in candidates
                if self.providers.has(candidate)
            ),
            None,
        )
        if provider_name is None:
            qualifier = "pedido" if strict else "registado"
            raise ModelRoutingError(
                f"Nenhum provider {qualifier} esta disponivel."
            )
        provider = self.providers.get(provider_name)
        model = next(
            (
                item.strip()
                for item in request.model_preferences.models
                if item.strip()
            ),
            "",
        )
        if not model:
            model = next(
                (
                    item.strip()
                    for item in profile.preferred_models
                    if item.strip()
                ),
                provider.default_model,
            )
        constraints = request.execution_constraints
        return ModelRoute(
            provider=provider_name,
            model=model,
            mode=request.model_preferences.mode or "chat",
            streaming=(
                profile.streaming
                if constraints.streaming is None
                else constraints.streaming
            ),
            thinking=(
                profile.thinking
                if constraints.thinking is None
                else constraints.thinking
            ),
        )
