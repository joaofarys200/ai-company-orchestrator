"""
Tests for Phase 48 Polymorphic Contract Changes (Integration with Phase 47):
- Variant addition in discriminated union
- Closed-enum consumer impact evaluation
- Variant removal breaking check
- Discriminator change breaking check
"""

import pytest
from agents.contract_change_management.analyzer import ContractChangeAnalyzer
from agents.contract_change_management.models import (
    ContractChangeType,
    ContractRiskLevel,
)


def test_polymorphic_variant_addition_with_closed_consumer():
    task = {
        "id": "tsk_add_event_variant",
        "title": "Add user.archived variant to events audit contract",
        "description": "Add new polymorphic variant user.archived to audit schema",
    }
    # This route has crm-sync-worker with CLOSED_EXHAUSTIVE
    pred = ContractChangeAnalyzer.analyze_task_change(
        task=task,
        predicted_files=["backend/api/events.py"],
    )

    # Because crm-sync-worker has CLOSED_EXHAUSTIVE switch without default,
    # the analyzer must promote POTENTIALLY_BREAKING to BREAKING
    assert pred.breaking_risk == ContractRiskLevel.BREAKING
    assert pred.migration_required is True
    assert pred.approval_required is True
    assert any(d.change_type == ContractChangeType.ADD_VARIANT for d in pred.predicted_diffs)

    crm_consumer = next((c for c in pred.affected_consumers if c.consumer_id == "crm-sync-worker"), None)
    assert crm_consumer is not None
    assert crm_consumer.pattern_matching.value == "CLOSED_EXHAUSTIVE"


def test_polymorphic_variant_removal():
    task = {
        "id": "tsk_remove_event_variant",
        "title": "Remove user.deleted variant from events contract",
        "description": "Remove variant user.deleted from event union",
    }
    pred = ContractChangeAnalyzer.analyze_task_change(
        task=task,
        predicted_files=["backend/api/events.py"],
    )

    assert pred.breaking_risk == ContractRiskLevel.BREAKING
    assert any(d.change_type == ContractChangeType.REMOVE_VARIANT for d in pred.predicted_diffs)
