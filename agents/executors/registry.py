from __future__ import annotations

import re
from collections.abc import Iterable

from agents.executors.base import (
    EXECUTOR_RISK_LEVELS,
    ExecutorDescriptor,
    WorkPackageExecutor,
)


EXECUTOR_KIND_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


class ExecutorRegistryError(ValueError):
    pass


class InvalidExecutorKindError(ExecutorRegistryError):
    pass


class DuplicateExecutorKindError(ExecutorRegistryError):
    pass


class ExecutorNotFoundError(ExecutorRegistryError):
    pass


class ExecutorRegistry:
    def __init__(
        self,
        entries: Iterable[
            tuple[WorkPackageExecutor | None, ExecutorDescriptor]
        ] | None = None,
    ):
        self._executors: dict[str, WorkPackageExecutor] = {}
        self._descriptors: dict[str, ExecutorDescriptor] = {}
        for executor, descriptor in entries or ():
            self.register(executor, descriptor)

    def register(
        self,
        executor: WorkPackageExecutor | None,
        descriptor: ExecutorDescriptor,
    ) -> None:
        kind = self._validate_descriptor(executor, descriptor)
        if kind in self._descriptors:
            raise DuplicateExecutorKindError(
                f"Executor kind ja registado: {kind}."
            )
        self._descriptors[kind] = descriptor
        if executor is not None:
            self._executors[kind] = executor

    def get(self, kind: str) -> WorkPackageExecutor:
        normalized = self._normalize_kind(kind)
        descriptor = self._descriptors.get(normalized)
        executor = self._executors.get(normalized)
        if descriptor is None or not descriptor.supported or executor is None:
            raise ExecutorNotFoundError(
                f"Executor indisponivel para {normalized}."
            )
        return executor

    def descriptor(self, kind: str) -> ExecutorDescriptor:
        normalized = self._normalize_kind(kind)
        descriptor = self._descriptors.get(normalized)
        if descriptor is None:
            raise ExecutorNotFoundError(
                f"Executor desconhecido: {normalized}."
            )
        return descriptor

    def is_supported(self, kind: str) -> bool:
        try:
            descriptor = self.descriptor(kind)
        except ExecutorRegistryError:
            return False
        normalized = self._normalize_kind(kind)
        return descriptor.supported and normalized in self._executors

    def describe(self) -> dict[str, dict]:
        return {
            kind: descriptor.to_public_dict()
            for kind, descriptor in self._descriptors.items()
        }

    def available_for_autonomy(self) -> list[ExecutorDescriptor]:
        return [
            descriptor
            for kind, descriptor in self._descriptors.items()
            if descriptor.supported
            and descriptor.autonomous_allowed
            and kind in self._executors
        ]

    @classmethod
    def _validate_descriptor(
        cls,
        executor: WorkPackageExecutor | None,
        descriptor: ExecutorDescriptor,
    ) -> str:
        if not isinstance(descriptor, ExecutorDescriptor):
            raise ExecutorRegistryError(
                "descriptor deve ser ExecutorDescriptor."
            )
        kind = cls._normalize_kind(descriptor.kind)
        if descriptor.kind != kind:
            raise InvalidExecutorKindError(
                "ExecutorDescriptor.kind deve estar normalizado em maiusculas."
            )
        risk_level = str(descriptor.risk_level or "").strip().upper()
        if risk_level not in EXECUTOR_RISK_LEVELS:
            raise ExecutorRegistryError(
                f"risk_level invalido: {descriptor.risk_level}."
            )
        if descriptor.risk_level != risk_level:
            raise ExecutorRegistryError(
                "risk_level deve estar normalizado em maiusculas."
            )
        if descriptor.supported and executor is None:
            raise ExecutorRegistryError(
                f"Executor suportado sem implementacao: {kind}."
            )
        if not descriptor.supported and executor is not None:
            raise ExecutorRegistryError(
                f"Executor nao suportado nao pode ter implementacao ativa: {kind}."
            )
        if descriptor.autonomous_allowed and not descriptor.supported:
            raise ExecutorRegistryError(
                f"Autonomia exige executor suportado: {kind}."
            )
        if descriptor.supported and not str(
            descriptor.executor_name or ""
        ).strip():
            raise ExecutorRegistryError(
                f"Executor suportado sem executor_name: {kind}."
            )
        if executor is not None:
            executor_kind = cls._normalize_kind(
                getattr(executor, "kind", "")
            )
            if executor_kind != kind:
                raise ExecutorRegistryError(
                    "Executor e descriptor declaram kinds diferentes."
                )
            execute = getattr(executor, "execute", None)
            if not callable(execute):
                raise ExecutorRegistryError(
                    f"Executor {kind} nao implementa execute()."
                )
        return kind

    @staticmethod
    def _normalize_kind(kind: str) -> str:
        normalized = str(kind or "").strip().upper()
        if not EXECUTOR_KIND_PATTERN.fullmatch(normalized):
            raise InvalidExecutorKindError(
                f"Executor kind invalido: {normalized or '<vazio>'}."
            )
        return normalized
