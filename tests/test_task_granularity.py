"""
JARVIS OS — Phase 39.2 Test Suite: Task Granularity Normalization & Cardinality

Tests:
1. Multiple files associated with a single task (N files -> 1 task).
2. Single file associated with multiple distinct tasks (1 file -> N tasks: e.g. Coding + Testing).
3. Non-file validation task (validation policy driven).
4. Non-file architecture task (semantic architectural impact).
5. Granularity normalization does not artificially inflate scores.
"""

from intelligence.predictive_impact.models import (
    PredictedFile,
    TaskCategory,
    TaskDerivationType,
)
from intelligence.predictive_impact.task_derivation import TaskDerivationEngine
from intelligence.predictive_impact.task_validator import TaskImpactConsistencyValidator


def test_multiple_files_single_task():
    """Case E: Multiple files affected by one implementation task."""
    files = [
        PredictedFile(file_path="frontend/src/App.tsx", classification="DIRECT", reason="Header"),
        PredictedFile(file_path="frontend/src/index.css", classification="INDIRECT", reason="CSS"),
        PredictedFile(file_path="frontend/src/components/Header.tsx", classification="DIRECT", reason="Nav"),
    ]

    tasks = TaskDerivationEngine.derive_tasks(
        operation="ADD_REQUIREMENT",
        target_name="REQ_HEADER_REDESIGN",
        directive_text="Redesenhar cabeçalho da aplicação",
        predicted_files=files,
        predicted_symbols=[],
        current_tasks=[],
        requirements=[],
        constraints=[],
        scope="LOCAL",
    )

    impl_task = tasks[0]
    assert len(impl_task.predicted_files) == 3
    assert set(impl_task.predicted_files) == {"frontend/src/App.tsx", "frontend/src/index.css", "frontend/src/components/Header.tsx"}

    # Consistency validator confirms valid structure
    report = TaskImpactConsistencyValidator.validate(tasks, files)
    assert report["is_valid"] is True


def test_single_file_multiple_tasks():
    """Case F: Single file touched by multiple tasks (Coding task + Validation task)."""
    files = [
        PredictedFile(file_path="backend/security/auth.py", classification="DIRECT", reason="Auth core"),
    ]

    tasks = TaskDerivationEngine.derive_tasks(
        operation="ADD_REQUIREMENT",
        target_name="REQ_AUTH",
        directive_text="Implementar autenticação",
        predicted_files=files,
        predicted_symbols=[],
        current_tasks=[],
        requirements=[],
        constraints=[],
    )

    assert len(tasks) == 2
    coding_task, testing_task = tasks[0], tasks[1]

    assert "backend/security/auth.py" in coding_task.predicted_files
    assert "backend/security/auth.py" in testing_task.predicted_files
    assert coding_task.category == TaskCategory.CODING.value
    assert testing_task.category == TaskCategory.TESTING.value


def test_validation_task_without_direct_code_file():
    """Case G: Validation task derived from policy without artificial file constraint."""
    tasks = TaskDerivationEngine.derive_tasks(
        operation="ADD_REQUIREMENT",
        target_name="REQ_PERF_AUDIT",
        directive_text="Auditar latência e métricas de desempenho",
        predicted_files=[],
        predicted_symbols=[],
        current_tasks=[],
        requirements=[],
        constraints=[],
    )

    test_task = tasks[1]
    assert test_task.category == TaskCategory.TESTING.value
    assert test_task.derivation_type == TaskDerivationType.VALIDATION_DRIVEN.value
    assert test_task.causal_trace is not None
    assert "validation_policy" in test_task.causal_trace


def test_architecture_task_without_direct_file():
    """Case H: Architecture task derived from requirement without explicit source file."""
    tasks = TaskDerivationEngine.derive_tasks(
        operation="REVISE_APPROACH",
        target_name="REQ_ARCH_REVISE",
        directive_text="Revisar arquitetura para desacoplamento assíncrono",
        predicted_files=[],
        predicted_symbols=[],
        current_tasks=[],
        requirements=[],
        constraints=[],
        scope="ARCHITECTURAL",
    )

    arch_task = tasks[0]
    assert arch_task.category == TaskCategory.ARCHITECTURE.value
    assert arch_task.derivation_type == TaskDerivationType.ARCHITECTURE_DRIVEN.value
    assert arch_task.predicted_owner == "architect"
    assert arch_task.causal_trace["requirement"] == "REQ_ARCH_REVISE"
