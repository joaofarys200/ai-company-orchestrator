"""
JARVIS OS — Phase 39 Test Suite: Prediction vs Actual Outcome Comparison

Tests:
1. Exact match produces Precision = 1.0, Recall = 1.0, and CORRECT classification.
2. Overprediction (false alarms) correctly calculates lower precision and classification OVERPREDICTED.
3. Underprediction (missed changes) calculates lower recall and classification UNDERPREDICTED.
4. Correctly isolates matched, missed (false negatives), and unexpected (false positives) items.
"""

import time
import pytest
from intelligence.predictive_impact.comparison import PredictionComparator
from intelligence.predictive_impact.models import (
    OutcomeClassification,
    PredictiveImpactReport,
)


@pytest.fixture
def mock_report():
    return PredictiveImpactReport(
        prediction_id="pred_test_cmp",
        mission_id="m_test",
        source_intent_version=1,
        proposed_intent_version=2,
        generated_at=time.time(),
        predicted_scope="CROSS_FILE",
        predicted_risk="MEDIUM",
        predicted_files=[
            {"file_path": "backend/api.py", "classification": "DIRECT"},
            {"file_path": "frontend/src/App.tsx", "classification": "INDIRECT"},
        ],
        predicted_tasks=[
            {"predicted_task_id": "pt_1", "action": "ADD_TASK", "source_requirement": "REQ_SEARCH"},
        ],
        predicted_evidence_impact=[
            {"evidence_id": "ev_01", "predicted_status": "REQUIRES_REVALIDATION"},
        ],
    )


def test_perfect_prediction_match(mock_report):
    outcome = PredictionComparator.compare(
        report=mock_report,
        actual_intent_version=2,
        actual_plan_version=2,
        actual_files_changed=["backend/api.py", "frontend/src/App.tsx"],
        actual_tasks_added=["REQ_SEARCH"],
        actual_tasks_modified=[],
        actual_tasks_removed=[],
        actual_evidence_invalidated=["ev_01"],
        actual_agents_used=["coder"],
        actual_browser_validation=True,
        actual_scope="CROSS_FILE",
    )

    assert outcome.classification == OutcomeClassification.CORRECT.value
    assert outcome.file_precision == 1.0
    assert outcome.file_recall == 1.0
    assert outcome.task_precision == 1.0
    assert outcome.task_recall == 1.0
    assert len(outcome.matched_files) == 2
    assert len(outcome.missed_files) == 0
    assert len(outcome.unexpected_files) == 0


def test_overprediction_deviation(mock_report):
    """Predicted 2 files, but only 1 was actually changed."""
    outcome = PredictionComparator.compare(
        report=mock_report,
        actual_intent_version=2,
        actual_plan_version=2,
        actual_files_changed=["backend/api.py"],  # App.tsx was not touched
        actual_tasks_added=["REQ_SEARCH"],
        actual_tasks_modified=[],
        actual_tasks_removed=[],
        actual_evidence_invalidated=["ev_01"],
        actual_agents_used=["coder"],
        actual_browser_validation=False,
        actual_scope="LOCAL",
    )

    assert outcome.file_precision == 0.5  # 1 matched / 2 predicted
    assert outcome.file_recall == 1.0     # 1 matched / 1 actual
    assert "frontend/src/app.tsx" in [f.lower() for f in outcome.missed_files]
    assert len(outcome.unexpected_files) == 0
    assert outcome.classification in (OutcomeClassification.OVERPREDICTED.value, OutcomeClassification.PARTIALLY_CORRECT.value)


def test_underprediction_deviation(mock_report):
    """Predicted 2 files, but 4 files were actually modified (unexpected changes)."""
    outcome = PredictionComparator.compare(
        report=mock_report,
        actual_intent_version=2,
        actual_plan_version=2,
        actual_files_changed=[
            "backend/api.py",
            "frontend/src/App.tsx",
            "backend/database.py",  # unexpected
            "backend/config.py",    # unexpected
        ],
        actual_tasks_added=["REQ_SEARCH"],
        actual_tasks_modified=[],
        actual_tasks_removed=[],
        actual_evidence_invalidated=["ev_01"],
        actual_agents_used=["coder"],
        actual_browser_validation=True,
        actual_scope="CROSS_MODULE",
    )

    assert outcome.file_precision == 1.0   # 2 matched / 2 predicted
    assert outcome.file_recall == 0.5      # 2 matched / 4 actual
    assert len(outcome.unexpected_files) == 2
    assert outcome.classification in (OutcomeClassification.UNDERPREDICTED.value, OutcomeClassification.PARTIALLY_CORRECT.value)
    assert any(d["type"] == "UNEXPECTED_FILE" for d in outcome.deviations)
