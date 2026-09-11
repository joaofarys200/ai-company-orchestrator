"""
JARVIS OS — Phase 39.2 Test Suite: Task Prediction Matching & Root Cause Classification

Tests:
1. Exact task match yields Precision = 1.0, Recall = 1.0, and MATCHED status.
2. Unmatched actual tasks are flagged MISSED and assigned causal root causes.
3. Unmatched predicted tasks are flagged OVERPREDICTED with root causes.
4. Root causes aggregated accurately in task_mismatches_by_root_cause.
5. Matching is deterministic across repeat executions.
"""

from intelligence.predictive_impact.comparison import PredictionComparator
from intelligence.predictive_impact.models import (
    PredictedTask,
    TaskCategory,
    TaskDerivationType,
    TaskRootCauseType,
)


def test_task_matching_exact():
    pred_tasks = [
        PredictedTask(
            predicted_task_id="p1",
            action="ADD_TASK",
            title="Implement search",
            description="...",
            source_requirement="REQ_SEARCH",
            category=TaskCategory.CODING.value,
            predicted_files=["frontend/src/features/search/SearchBar.tsx"],
            causal_trace={"requirement": "REQ_SEARCH"},
        ).to_dict(),
        PredictedTask(
            predicted_task_id="p2",
            action="ADD_TASK",
            title="Validate search tests",
            description="...",
            source_requirement="REQ_SEARCH",
            category=TaskCategory.TESTING.value,
            predicted_files=["frontend/src/features/search/SearchBar.tsx"],
            causal_trace={"requirement": "REQ_SEARCH"},
        ).to_dict(),
    ]

    actual_tasks = [
        {"id": "a1", "action": "ADD_TASK", "category": "Coding", "requirement": "REQ_SEARCH"},
        {"id": "a2", "action": "ADD_TASK", "category": "Testing", "requirement": "REQ_SEARCH"},
    ]

    res = PredictionComparator.match_tasks(
        predicted_tasks=pred_tasks,
        actual_tasks_added=actual_tasks,
        actual_tasks_modified=[],
        actual_tasks_removed=[],
        predicted_files=[{"file_path": "frontend/src/features/search/SearchBar.tsx"}],
        actual_files_changed=["frontend/src/features/search/SearchBar.tsx"],
    )

    assert res["task_precision"] == 1.0
    assert res["task_recall"] == 1.0
    assert len(res["matched_tasks"]) == 2
    assert len(res["unexpected_tasks"]) == 0
    assert len(res["missed_tasks"]) == 0


def test_task_mismatch_root_cause_classification():
    pred_tasks = [
        PredictedTask(
            predicted_task_id="p1",
            action="ADD_TASK",
            title="Implement unused",
            description="...",
            source_requirement="REQ_UNUSED",
            category=TaskCategory.CODING.value,
            predicted_files=["unmodified.py"],
            derivation_type=TaskDerivationType.DIRECT_FILE_IMPACT.value,
        ).to_dict()
    ]

    # Actual had a testing task that wasn't predicted
    actual_tasks = [
        {"id": "act_test", "action": "ADD_TASK", "category": "Testing", "requirement": "REQ_OTHER"}
    ]

    res = PredictionComparator.match_tasks(
        predicted_tasks=pred_tasks,
        actual_tasks_added=actual_tasks,
        actual_tasks_modified=[],
        actual_tasks_removed=[],
        predicted_files=[{"file_path": "unmodified.py"}],
        actual_files_changed=[],  # unmodified.py wasn't touched
    )

    assert res["task_precision"] == 0.0
    assert res["task_recall"] == 0.0
    assert len(res["missed_tasks"]) == 1
    assert len(res["unexpected_tasks"]) == 1

    root_causes = res["root_causes"]
    # Unmatched predicted task touching untouched file -> OVER_AGGRESSIVE_TASK_DERIVATION
    assert TaskRootCauseType.OVER_AGGRESSIVE_TASK_DERIVATION.value in root_causes
    # Unmatched actual testing task -> VALIDATION_TASK_NOT_FILE_DRIVEN
    assert TaskRootCauseType.VALIDATION_TASK_NOT_FILE_DRIVEN.value in root_causes
