"""
JARVIS OS — Phase 63: Cross-Project Engineering Learning & Verification Transfer
Module: patterns.py
Standardized schema templates and factories for the 10 engineering knowledge categories.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from .models import KnowledgeCategory


class PatternLibrary:
    """Provides validated pattern blueprints across all 10 knowledge categories."""

    @staticmethod
    def create_architecture_pattern(
        name: str,
        style: str,
        components: List[str],
        data_flow: str,
        boundaries: List[str],
    ) -> Dict[str, Any]:
        return {
            "name": name,
            "architecture_style": style,
            "components": components,
            "data_flow": data_flow,
            "boundaries": boundaries,
            "category": KnowledgeCategory.ARCHITECTURE_PATTERN.value,
        }

    @staticmethod
    def create_test_pattern(
        name: str,
        test_type: str,
        target_invariant: str,
        setup_strategy: str,
        assertion_strategy: str,
        mock_requirements: List[str],
    ) -> Dict[str, Any]:
        return {
            "name": name,
            "test_type": test_type,
            "target_invariant": target_invariant,
            "setup_strategy": setup_strategy,
            "assertion_strategy": assertion_strategy,
            "mock_requirements": mock_requirements,
            "category": KnowledgeCategory.TEST_PATTERN.value,
        }

    @staticmethod
    def create_repair_pattern(
        name: str,
        failure_signature: str,
        transformation_strategy: str,
        safety_checks: List[str],
    ) -> Dict[str, Any]:
        return {
            "name": name,
            "failure_signature": failure_signature,
            "transformation_strategy": transformation_strategy,
            "safety_checks": safety_checks,
            "category": KnowledgeCategory.REPAIR_PATTERN.value,
        }

    @staticmethod
    def create_failure_pattern(
        name: str,
        symptom: str,
        root_cause_class: str,
        detection_rule: str,
    ) -> Dict[str, Any]:
        return {
            "name": name,
            "symptom": symptom,
            "root_cause_class": root_cause_class,
            "detection_rule": detection_rule,
            "category": KnowledgeCategory.FAILURE_PATTERN.value,
        }

    @staticmethod
    def create_contract_pattern(
        name: str,
        protocol: str,
        schema_format: str,
        compatibility_rule: str,
        drift_mitigation: str,
    ) -> Dict[str, Any]:
        return {
            "name": name,
            "protocol": protocol,
            "schema_format": schema_format,
            "compatibility_rule": compatibility_rule,
            "drift_mitigation": drift_mitigation,
            "category": KnowledgeCategory.CONTRACT_PATTERN.value,
        }

    @staticmethod
    def create_behavior_pattern(
        name: str,
        state_machine: str,
        transition_invariants: List[str],
        timeout_budget_ms: int,
    ) -> Dict[str, Any]:
        return {
            "name": name,
            "state_machine": state_machine,
            "transition_invariants": transition_invariants,
            "timeout_budget_ms": timeout_budget_ms,
            "category": KnowledgeCategory.BEHAVIOR_PATTERN.value,
        }

    @staticmethod
    def create_risk_pattern(
        name: str,
        risk_class: str,
        impact_severity: str,
        mitigation_strategy: str,
    ) -> Dict[str, Any]:
        return {
            "name": name,
            "risk_class": risk_class,
            "impact_severity": impact_severity,
            "mitigation_strategy": mitigation_strategy,
            "category": KnowledgeCategory.RISK_PATTERN.value,
        }

    @staticmethod
    def create_performance_pattern(
        name: str,
        bottleneck_type: str,
        caching_strategy: str,
        concurrency_limit: int,
    ) -> Dict[str, Any]:
        return {
            "name": name,
            "bottleneck_type": bottleneck_type,
            "caching_strategy": caching_strategy,
            "concurrency_limit": concurrency_limit,
            "category": KnowledgeCategory.PERFORMANCE_PATTERN.value,
        }

    @staticmethod
    def create_browser_pattern(
        name: str,
        interaction_type: str,
        selector_strategy: str,
        wait_condition: str,
    ) -> Dict[str, Any]:
        return {
            "name": name,
            "interaction_type": interaction_type,
            "selector_strategy": selector_strategy,
            "wait_condition": wait_condition,
            "category": KnowledgeCategory.BROWSER_PATTERN.value,
        }

    @staticmethod
    def create_recovery_pattern(
        name: str,
        anomaly_type: str,
        checkpoint_policy: str,
        rollback_action: str,
    ) -> Dict[str, Any]:
        return {
            "name": name,
            "anomaly_type": anomaly_type,
            "checkpoint_policy": checkpoint_policy,
            "rollback_action": rollback_action,
            "category": KnowledgeCategory.RECOVERY_PATTERN.value,
        }
