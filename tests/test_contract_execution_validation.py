"""
Tests for Phase 48 ContractRuntimeVerifier:
- Runtime verification: PREDICTED vs ACTUAL contract
- Consumer compatibility validation
- Test suite and browser QA pass enforcement
- Evidence completeness check
"""

import pytest
from agents.contract_change_management.verification import ContractRuntimeVerifier


def test_verify_runtime_execution_all_pass():
    result = ContractRuntimeVerifier.verify_runtime_execution(
        contract_id="contract_users_v1",
        predicted_version="2.0.0",
        actual_observed_schema={"id": "string", "avatar": {"url": "string"}},
        actual_observed_version="2.0.0",
        consumer_check_results={
            "frontend-user-card": True,
            "test-user-api": True,
            "browser-user-profile-qa": True,
        },
        test_results_passed=True,
        browser_qa_passed=True,
        evidence_present=True,
    )

    assert result.passed is True
    assert result.matches_predicted is True
    assert result.consumer_compatibility_verified is True
    assert len(result.failure_reasons) == 0


def test_verify_runtime_execution_version_mismatch():
    result = ContractRuntimeVerifier.verify_runtime_execution(
        contract_id="contract_users_v1",
        predicted_version="2.0.0",
        actual_observed_schema={"id": "string"},
        actual_observed_version="1.0.0",  # mismatch!
        consumer_check_results={"frontend-user-card": True},
        test_results_passed=True,
        browser_qa_passed=True,
        evidence_present=True,
    )

    assert result.passed is False
    assert result.matches_predicted is False
    assert any("Version mismatch" in r for r in result.failure_reasons)


def test_verify_runtime_execution_consumer_breakage():
    result = ContractRuntimeVerifier.verify_runtime_execution(
        contract_id="contract_users_v1",
        predicted_version="2.0.0",
        actual_observed_schema={"id": "string"},
        actual_observed_version="2.0.0",
        consumer_check_results={
            "frontend-user-card": False,  # Failed!
            "test-user-api": True,
        },
        test_results_passed=True,
        browser_qa_passed=True,
        evidence_present=True,
    )

    assert result.passed is False
    assert result.consumer_compatibility_verified is False
    assert any("Consumer compatibility failure" in r for r in result.failure_reasons)
