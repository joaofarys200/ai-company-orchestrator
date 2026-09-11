"""
JARVIS OS — Phase 39.2 Test Suite: Task Impact Consistency Validator

Tests:
1. Consistent prediction returns verdict CONSISTENT and is_valid = True.
2. Invariant 1: FILE_DRIVEN task without files flags ERROR.
3. Invariant 5: Duplicate task IDs flags ERROR.
4. Invariant 6: Unresolved dependency flags ERROR.
5. Invariant 7: Cyclic task dependency graph flags ERROR and INCONSISTENT.
6. Invariant 9: Unmapped category flags ERROR.
"""

from intelligence.predictive_impact.models import (
    ConsistencyVerdict,
    PredictedFile,
    PredictedTask,
    TaskCategory,
    TaskDerivationType,
)
from intelligence.predictive_impact.task_validator import TaskImpactConsistencyValidator


def test_valid_consistency():
    files = [PredictedFile(file_path="src/App.tsx", classification="DIRECT", reason="UI")]
    tasks = [
        PredictedTask(
            predicted_task_id="t1",
            action="ADD_TASK",
            title="Impl",
            description="Impl desc",
            source_requirement="REQ_1",
            predicted_files=["src/App.tsx"],
            category=TaskCategory.CODING.value,
            derivation_type=TaskDerivationType.DIRECT_FILE_IMPACT.value,
        ),
        PredictedTask(
            predicted_task_id="t2",
            action="ADD_TASK",
            title="Test",
            description="Test desc",
            source_requirement="REQ_1",
            dependencies=["t1"],
            predicted_files=["src/App.tsx"],
            category=TaskCategory.TESTING.value,
            derivation_type=TaskDerivationType.VALIDATION_DRIVEN.value,
        ),
    ]

    report = TaskImpactConsistencyValidator.validate(tasks, files)
    assert report["is_valid"] is True
    assert report["verdict"] == ConsistencyVerdict.CONSISTENT.value
    assert report["checks_passed"] == 9


def test_file_driven_task_missing_files():
    files = [PredictedFile(file_path="src/App.tsx", classification="DIRECT", reason="UI")]
    tasks = [
        PredictedTask(
            predicted_task_id="t1",
            action="ADD_TASK",
            title="Impl",
            description="Impl desc",
            source_requirement="REQ_1",
            predicted_files=[],  # Empty files for DIRECT_FILE_IMPACT
            category=TaskCategory.CODING.value,
            derivation_type=TaskDerivationType.DIRECT_FILE_IMPACT.value,
        ),
    ]

    report = TaskImpactConsistencyValidator.validate(tasks, files)
    assert report["is_valid"] is False
    assert report["verdict"] == ConsistencyVerdict.INCONSISTENT.value
    assert any(i["invariant"] == 1 for i in report["issues"])


def test_duplicate_task_ids():
    tasks = [
        PredictedTask(
            predicted_task_id="dup_id",
            action="ADD_TASK",
            title="Impl 1",
            description="Desc",
            source_requirement="REQ_1",
            predicted_files=["a.py"],
        ),
        PredictedTask(
            predicted_task_id="dup_id",
            action="ADD_TASK",
            title="Impl 2",
            description="Desc",
            source_requirement="REQ_2",
            predicted_files=["b.py"],
        ),
    ]

    report = TaskImpactConsistencyValidator.validate(tasks, [])
    assert report["is_valid"] is False
    assert any(i["invariant"] == 5 for i in report["issues"])


def test_unresolved_dependency():
    tasks = [
        PredictedTask(
            predicted_task_id="t1",
            action="ADD_TASK",
            title="Impl",
            description="Desc",
            source_requirement="REQ_1",
            dependencies=["non_existent_task"],
            predicted_files=["a.py"],
        ),
    ]

    report = TaskImpactConsistencyValidator.validate(tasks, [])
    assert report["is_valid"] is False
    assert any(i["invariant"] == 6 for i in report["issues"])


def test_cycle_detection():
    tasks = [
        PredictedTask(
            predicted_task_id="t1",
            action="ADD_TASK",
            title="Task 1",
            description="Desc",
            source_requirement="REQ_1",
            dependencies=["t2"],
            predicted_files=["a.py"],
        ),
        PredictedTask(
            predicted_task_id="t2",
            action="ADD_TASK",
            title="Task 2",
            description="Desc",
            source_requirement="REQ_1",
            dependencies=["t1"],
            predicted_files=["a.py"],
        ),
    ]

    report = TaskImpactConsistencyValidator.validate(tasks, [])
    assert report["is_valid"] is False
    assert any(i["invariant"] == 7 for i in report["issues"])


def test_invalid_category():
    tasks = [
        PredictedTask(
            predicted_task_id="t1",
            action="ADD_TASK",
            title="Task 1",
            description="Desc",
            source_requirement="REQ_1",
            category="INVALID_ARBITRARY_CATEGORY",
            predicted_files=["a.py"],
        ),
    ]

    report = TaskImpactConsistencyValidator.validate(tasks, [])
    assert report["is_valid"] is False
    assert any(i["invariant"] == 9 for i in report["issues"])
