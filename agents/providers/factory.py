import os

from agents.providers.gemini import GeminiProvider
from agents.providers.ollama import OllamaProvider


def get_llm_provider(mode: str | None = None):
    selected_mode = (mode or os.getenv("ORCHESTRATOR_MODE", "local")).lower()
    providers = {
        "gemini": GeminiProvider(),
        "local": OllamaProvider(),
        "ollama": OllamaProvider(),
    }
    provider = providers.get(selected_mode, OllamaProvider())
    if provider.has_credentials():
        return provider
    return OllamaProvider()


def build_crewai_llm(llm_cls, mode: str | None = None, temperature: float | None = None):
    resolved_temperature = (
        float(os.getenv("CREWAI_TEMPERATURE", "0.2"))
        if temperature is None
        else temperature
    )
    provider = get_llm_provider(mode)
    return provider.build_crewai_llm(llm_cls, resolved_temperature)
