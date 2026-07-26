from agents.executors.base import (
    ExecutorDescriptor,
    WorkPackageExecutionContext,
    WorkPackageExecutionResult,
    WorkPackageExecutor,
)
from agents.executors.coding import CodingWorkPackageExecutor
from agents.executors.project_build import ProjectBuildWorkPackageExecutor
from agents.executors.registry import (
    DuplicateExecutorKindError,
    ExecutorNotFoundError,
    ExecutorRegistry,
    ExecutorRegistryError,
    InvalidExecutorKindError,
)


def create_default_executor_registry() -> ExecutorRegistry:
    registry = ExecutorRegistry()
    registry.register(
        CodingWorkPackageExecutor(),
        ExecutorDescriptor(
            kind="CODING",
            executor_name="CodingSession",
            supported=True,
            requires_apply_approval=True,
            autonomous_allowed=True,
            risk_level="MEDIUM",
            description=(
                "Prepara uma CodingSession; qualquer aplicacao exige "
                "confirmacao explicita."
            ),
        ),
    )
    registry.register(
        ProjectBuildWorkPackageExecutor(),
        ExecutorDescriptor(
            kind="PROJECT_BUILD",
            executor_name="ProjectBuilder",
            supported=True,
            requires_apply_approval=False,
            autonomous_allowed=False,
            risk_level="HIGH",
            description=(
                "Executa o ProjectBuilder controlado; autonomia permanece "
                "desativada nesta fase."
            ),
        ),
    )
    for kind, description in (
        ("RESEARCH", "Executor de investigacao ainda nao implementado."),
        ("DOCUMENT", "Executor documental ainda nao implementado."),
        ("EXPERIMENT", "Executor de experiencias ainda nao implementado."),
        ("REVIEW", "Executor de revisao ainda nao implementado."),
        ("GENERIC", "Executor generico deliberadamente indisponivel."),
    ):
        registry.register(
            None,
            ExecutorDescriptor(
                kind=kind,
                executor_name=None,
                supported=False,
                requires_apply_approval=False,
                autonomous_allowed=False,
                risk_level="HIGH",
                description=description,
            ),
        )
    return registry


__all__ = [
    "CodingWorkPackageExecutor",
    "DuplicateExecutorKindError",
    "ExecutorDescriptor",
    "ExecutorNotFoundError",
    "ExecutorRegistry",
    "ExecutorRegistryError",
    "InvalidExecutorKindError",
    "ProjectBuildWorkPackageExecutor",
    "WorkPackageExecutionContext",
    "WorkPackageExecutionResult",
    "WorkPackageExecutor",
    "create_default_executor_registry",
]
