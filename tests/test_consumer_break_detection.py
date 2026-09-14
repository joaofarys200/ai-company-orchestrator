"""
Tests for Phase 48 Consumer Break Detection:
- Tracing direct, indirect, test, and browser consumers
- Closed-enum matching detection (switch without default)
- Open matching with default branch
"""

import pytest
from agents.contract_change_management.consumers import ContractConsumerTracer
from agents.contract_change_management.models import (
    ConsumerCategory,
    ConsumerPatternMatching,
)


def test_detect_closed_exhaustive_switch():
    code_closed = """
    function handleEvent(event: AuditEvent) {
        switch (event.type) {
            case 'user.created':
                return createUser(event);
            case 'user.updated':
                return updateUser(event);
        }
    }
    """
    pattern = ContractConsumerTracer.detect_pattern_matching(code_closed)
    assert pattern == ConsumerPatternMatching.CLOSED_EXHAUSTIVE


def test_detect_open_with_default_fallback():
    code_open = """
    function handleEvent(event: AuditEvent) {
        switch (event.type) {
            case 'user.created':
                return createUser(event);
            default:
                logger.warn('Unknown event type', event.type);
                return null;
        }
    }
    """
    pattern = ContractConsumerTracer.detect_pattern_matching(code_open)
    assert pattern == ConsumerPatternMatching.OPEN_WITH_FALLBACK


def test_trace_known_consumers_for_route():
    traces = ContractConsumerTracer.trace_consumers(
        contract_id="contract_events_v1",
        route="/api/v1/events",
    )
    assert len(traces) >= 4

    categories = {c.category for c in traces}
    assert ConsumerCategory.DIRECT in categories
    assert ConsumerCategory.TEST in categories
    assert ConsumerCategory.BROWSER_SCENARIO in categories

    # Verify crm-sync-worker has CLOSED_EXHAUSTIVE
    crm_worker = next((c for c in traces if c.consumer_id == "crm-sync-worker"), None)
    assert crm_worker is not None
    assert crm_worker.pattern_matching == ConsumerPatternMatching.CLOSED_EXHAUSTIVE
    assert "Exhaustive" in crm_worker.impact_reason
    assert len(crm_worker.required_action) > 0
