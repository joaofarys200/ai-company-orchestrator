import os


def get_orchestrator_mode() -> str:
    return os.getenv("ORCHESTRATOR_MODE", "local").lower()


def get_default_ollama_model() -> str:
    return os.getenv("OLLAMA_MODEL", "qwen3.5:9b")


__all__ = [
    "get_default_ollama_model",
    "get_orchestrator_mode",
]
