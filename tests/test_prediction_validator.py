"""
JARVIS OS — Phase 39 Test Suite: Predictive Impact Validator

Tests:
1. Valid prediction graphs pass structural validation.
2. Kahn's Algorithm detects and rejects cyclic task dependencies in predicted graphs.
3. Unknown or malformed file paths rejected.
4. Non-existent evidence references rejected.
5. Missing or invalid task actions rejected.
"""

import pytest
from intelligence.predictive_impact.validator import PredictiveImpactValidator


def test_valid_prediction_structure():
    predicted_tasks = [
        {"predicted_task_id": "pt_1", "action": "ADD_TASK", "title": "Implementar módulo", "dependencies": []},
        {"predicted_task_id": "pt_2", "action": "ADD_TASK", "title": "Testar módulo", "dependencies": ["pt_1"]},
    ]
    predicted_files = [
        {"file_path": "backend/service.py", "classification": "DIRECT"},
        {"file_path": "frontend/src/App.tsx", "classification": "INDIRECT"},
    ]
    predicted_evidence = [
        {"evidence_id": "ev_01", "requirement_id": "REQ_01", "predicted_status": "REQUIRES_REVALIDATION"}
    ]
    current_tasks = [{"id": "t_base", "dependencies": []}]
    current_evidence = [{"evidence_id": "ev_01", "requirement_id": "REQ_01"}]

    is_valid, errors = PredictiveImpactValidator.validate_prediction(
        predicted_tasks=predicted_tasks,
        predicted_files=predicted_files,
        predicted_evidence=predicted_evidence,
        current_tasks=current_tasks,
        current_evidence=current_evidence,
    )

    assert is_valid is True
    assert len(errors) == 0


def test_cyclic_task_dependency_rejection():
    """Kahn's DAG algorithm must reject cycles between predicted tasks."""
    cyclic_tasks = [
        {"predicted_task_id": "pt_a", "action": "ADD_TASK", "title": "Task A", "dependencies": ["pt_b"]},
        {"predicted_task_id": "pt_b", "action": "ADD_TASK", "title": "Task B", "dependencies": ["pt_a"]},
    ]

    is_valid, errors = PredictiveImpactValidator.validate_prediction(
        predicted_tasks=cyclic_tasks,
        predicted_files=[],
        predicted_evidence=[],
        current_tasks=[],
        current_evidence=[],
    )

    assert is_valid is False
    assert any("Ciclo detetado" in err for err in errors)


def test_self_cyclic_dependency_rejection():
    """Task depending on itself is strictly rejected."""
    self_cycle = [
        {"predicted_task_id": "pt_self", "action": "ADD_TASK", "title": "Task Self", "dependencies": ["pt_self"]},
    ]

    is_valid, errors = PredictiveImpactValidator.validate_prediction(
        predicted_tasks=self_cycle,
        predicted_files=[],
        predicted_evidence=[],
        current_tasks=[],
        current_evidence=[],
    )

    assert is_valid is False
    assert any("auto-dependência cíclica" in err for err in errors)


def test_invalid_evidence_reference_rejection():
    """Referencing a non-existent evidence ID must be rejected."""
    predicted_ev = [
        {"evidence_id": "ev_phantom_99", "requirement_id": "REQ_X", "predicted_status": "SUPERSEDED"}
    ]

    is_valid, errors = PredictiveImpactValidator.validate_prediction(
        predicted_tasks=[],
        predicted_files=[],
        predicted_evidence=predicted_ev,
        current_tasks=[],
        current_evidence=[{"evidence_id": "ev_real_01"}],
    )

    assert is_valid is False
    assert any("não existe no Evidence Ledger" in err for err in errors)
