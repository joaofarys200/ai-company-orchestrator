"""
JARVIS OS — Phase 57: Validator Registry
Pluggable registry for domain-specific and system-level mission validators.
"""

from __future__ import annotations

from typing import Any, Callable

ValidationFunc = Callable[[dict[str, Any]], dict[str, Any]]


class ValidatorRegistry:
    """Registry maintaining available validators across different verification dimensions."""

    _validators: dict[str, ValidationFunc] = {}

    @classmethod
    def register(cls, name: str, func: ValidationFunc) -> None:
        cls._validators[name] = func

    @classmethod
    def get(cls, name: str) -> ValidationFunc | None:
        return cls._validators.get(name)

    @classmethod
    def list_validators(cls) -> list[str]:
        return list(cls._validators.keys())
