from __future__ import annotations

import os

from backend.model_harness.contracts import ModelRequest, ModelRoute
from backend.model_harness.errors import ModelRoutingError
from backend.model_harness.profiles import TaskProfile
from backend.model_harness.provider import ProviderRegistry


# Task profiles that benefit strongly from a cloud-grade model
_COMPLEX_PROFILES = frozenset({"TOOL_SELECTION", "MISSION_PLANNING"})


class ModelRouter:
    """Deterministic routing infrastructure without task-specific heuristics.

    When the env-var ``GEMINI_FOR_COMPLEX=true`` is set, requests whose
    task_profile is in _COMPLEX_PROFILES are automatically routed to the
    ``gemini`` provider (if registered), falling back to the normal selection
    order when Gemini is unavailable.
    """

    def __init__(self, providers: ProviderRegistry):
        self.providers = providers

    @property
    def _gemini_for_complex(self) -> bool:
        v = (
            os.getenv("GEMINI_FOR_COMPLEX")
            or os.getenv("CLOUD_FOR_COMPLEX")
            or ""
        )
        return v.strip().lower() in ("true", "1", "yes")

    def route(
        self,
        request: ModelRequest,
        profile: TaskProfile,
    ) -> ModelRoute:
        # --- Dual-model override: route complex tasks to Gemini when enabled ---
        if (
            self._gemini_for_complex
            and profile.name in _COMPLEX_PROFILES
            and not request.model_preferences.providers  # no explicit override
            and self.providers.has("gemini")
        ):
            provider = self.providers.get("gemini")
            return ModelRoute(
                provider="gemini",
                model=provider.default_model,
                mode=request.model_preferences.mode or "chat",
                streaming=profile.streaming,
                thinking=profile.thinking,
            )

        # --- Standard routing ---
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
        
        # Respect global ORCHESTRATOR_MODE preference from environment
        orchestrator_mode = (os.getenv("ORCHESTRATOR_MODE") or "").strip().lower()
        if orchestrator_mode in ("gemini", "cloud") and self.providers.has("gemini") and not requested:
            preferred = ("gemini",) + tuple(p for p in preferred if p != "gemini")

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
