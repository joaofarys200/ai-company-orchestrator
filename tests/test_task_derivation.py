"""
JARVIS OS — Phase 39.2 Test Suite: Task Derivation Engine

Tests:
1. File-driven task derivation for ADD_REQUIREMENT produces implementation and validation tasks.
2. Architecture-driven derivation produces architecture category and owner.
3. MODIFY_REQUIREMENT produces adaptation and regression re-validation tasks.
4. REMOVE_REQUIREMENT produces deprecation/removal and evidence cleanup tasks.
5. Causal traces are attached with requirement, files, symbols, and rationale.
6. FILES x TASKS correlation matrix classifies DIRECT, INDIRECT, VALIDATION relationships.
"""

import pytest
from intelligence.predictive_impact.models import (
    ConfidenceClass,
    PredictedFile,
    PredictedSymbol,
    TaskCategory,
    TaskDerivationType,
    TaskFileRelationType,
)
from intelligence.predictive_impact.task_derivation import TaskDerivationEngine


@pytest.fixture
def sample_files():
    return [
        PredictedFile(file_path="frontend/src/App.tsx", classification="DIRECT", reason="Target component"),
        PredictedFile(file_path="frontend/src/index.css", classification="INDIRECT", reason="Stylesheet import"),
    ]


@pytest.fixture
def sample_symbols():
    return [
        PredictedSymbol(name="App", file_path="frontend/src/App.tsx", symbol_type="function", change_nature="MODIFY", reason="Directive target"),
    ]


def test_add_requirement_task_derivation(sample_files, sample_symbols):
    tasks = TaskDerivationEngine.derive_tasks(
        operation="ADD_REQUIREMENT",
        target_name="REQ_SEARCH_BAR",
        directive_text="Adicionar barra de busca reactiva no frontend",
        predicted_files=sample_files,
        predicted_symbols=sample_symbols,
        current_tasks=[],
        requirements=[],
        constraints=[],
        scope="LOCAL",
    )

    assert len(tasks) == 2
    impl_task, test_task = tasks[0], tasks[1]

    # Task 1: Implementation
    assert impl_task.action == "ADD_TASK"
    assert impl_task.category == TaskCategory.CODING.value
    assert impl_task.derivation_type == TaskDerivationType.DIRECT_FILE_IMPACT.value
    assert impl_task.confidence_class == ConfidenceClass.DETERMINISTIC.value
    assert "frontend/src/App.tsx" in impl_task.predicted_files
    assert impl_task.causal_trace is not None
    assert impl_task.causal_trace["requirement"] == "REQ_SEARCH_BAR"

    # Task 2: Testing / Validation
    assert test_task.action == "ADD_TASK"
    assert test_task.category == TaskCategory.TESTING.value
    assert test_task.derivation_type == TaskDerivationType.VALIDATION_DRIVEN.value
    assert test_task.dependencies == [impl_task.predicted_task_id]


def test_architecture_derivation():
    tasks = TaskDerivationEngine.derive_tasks(
        operation="ADD_REQUIREMENT",
        target_name="REQ_EVENT_BUS",
        directive_text="Implementar arquitetura de swarm orientada a eventos",
        predicted_files=[PredictedFile(file_path="agents/domain_logic.py", classification="DIRECT", reason="Core agent logic")],
        predicted_symbols=[],
        current_tasks=[],
        requirements=[],
        constraints=[],
        scope="ARCHITECTURAL",
    )

    assert len(tasks) == 2
    arch_task = tasks[0]
    assert arch_task.category == TaskCategory.ARCHITECTURE.value
    assert arch_task.derivation_type == TaskDerivationType.ARCHITECTURE_DRIVEN.value
    assert arch_task.predicted_owner == "architect"


def test_modify_requirement_derivation(sample_files):
    tasks = TaskDerivationEngine.derive_tasks(
        operation="MODIFY_REQUIREMENT",
        target_name="REQ_STYLE_3",
        directive_text="Atualizar tipografia para Outfit",
        predicted_files=sample_files,
        predicted_symbols=[],
        current_tasks=[],
        requirements=[],
        constraints=[],
        scope="LOCAL",
    )

    assert len(tasks) == 2
    adapt_task, reval_task = tasks[0], tasks[1]
    assert adapt_task.action == "MODIFY_TASK"
    assert adapt_task.derivation_type == TaskDerivationType.DIRECT_FILE_IMPACT.value
    assert reval_task.action == "ADD_TASK"
    assert reval_task.category == TaskCategory.TESTING.value
    assert reval_task.derivation_type == TaskDerivationType.VALIDATION_DRIVEN.value


def test_remove_requirement_derivation():
    tasks = TaskDerivationEngine.derive_tasks(
        operation="REMOVE_REQUIREMENT",
        target_name="REQ_EXPORT_1",
        directive_text="Remover exportação CSV do painel",
        predicted_files=[PredictedFile(file_path="frontend/src/features/export/ExportPanel.tsx", classification="DIRECT", reason="Obsolete export")],
        predicted_symbols=[],
        current_tasks=[{"id": "TSK_01", "title": "Base setup"}],
        requirements=[],
        constraints=[],
        scope="CROSS_MODULE",
    )

    assert len(tasks) == 2
    depr_task, clean_task = tasks[0], tasks[1]
    assert depr_task.action == "REMOVE_TASK"
    assert clean_task.category == TaskCategory.TESTING.value
    assert clean_task.derivation_type == TaskDerivationType.VALIDATION_DRIVEN.value


def test_task_file_matrix_generation(sample_files):
    tasks = TaskDerivationEngine.derive_tasks(
        operation="ADD_REQUIREMENT",
        target_name="REQ_PROFILE",
        directive_text="Perfil de utilizador",
        predicted_files=sample_files,
        predicted_symbols=[],
        current_tasks=[],
        requirements=[],
        constraints=[],
    )

    matrix = TaskDerivationEngine.build_task_file_matrix(tasks, sample_files)
    assert "relationships" in matrix
    assert matrix["total_relationships"] > 0

    direct_rels = [r for r in matrix["relationships"] if r["relation_type"] == TaskFileRelationType.DIRECT.value]
    val_rels = [r for r in matrix["relationships"] if r["relation_type"] == TaskFileRelationType.VALIDATION.value]

    assert len(direct_rels) >= 1
    assert len(val_rels) >= 1
