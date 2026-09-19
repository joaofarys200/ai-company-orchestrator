"""
JARVIS OS — Phase 69: Autonomous Quality Debt Remediation
Root cause analysis engine. Identifies true structural/behavioral causes rather than correlation.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Tuple

from .debt import IngestedDebtItem
from .models import DebtRootCause, RootCauseCategory


class DebtRootCauseEngine:
    """
    Performs root cause analysis on validated technical debt.
    Categorizes the causal origin and routes UNKNOWN causes to human review or boundary analysis.
    """

    def analyze(self, debt_item: IngestedDebtItem) -> DebtRootCause:
        cause_id = f"rc_{uuid.uuid4().hex[:8]}"
        category_str = debt_item.category.upper()
        evidence = debt_item.evidence
        surface = debt_item.affected_surface

        # Determine category and explanation from evidence
        if "ARCHITECT" in category_str or "CYCLIC" in category_str or "SCC" in category_str:
            return DebtRootCause(
                cause_id=cause_id,
                debt_id=debt_item.debt_id,
                category=RootCauseCategory.ARCHITECTURAL_CAUSE,
                description=f"Architectural coupling / circular dependency identified in surface: {surface}",
                evidence=[{"kind": "dependency_graph", "surface": surface, "details": evidence}],
                confidence=min(debt_item.confidence, 0.92),
                affected_surface=surface,
            )

        elif "SECURITY" in category_str or "SENTINEL" in category_str or "VULN" in category_str:
            return DebtRootCause(
                cause_id=cause_id,
                debt_id=debt_item.debt_id,
                category=RootCauseCategory.SECURITY_CAUSE,
                description=f"Security constraint or policy violation detected in surface: {surface}",
                evidence=[{"kind": "security_audit", "surface": surface, "details": evidence}],
                confidence=min(debt_item.confidence, 0.98),
                affected_surface=surface,
            )

        elif "CONTRACT" in category_str or "INTERFACE" in category_str or "SCHEMA" in category_str:
            return DebtRootCause(
                cause_id=cause_id,
                debt_id=debt_item.debt_id,
                category=RootCauseCategory.CONTRACT_CAUSE,
                description=f"API contract drift or signature incompatibility in surface: {surface}",
                evidence=[{"kind": "contract_diff", "surface": surface, "details": evidence}],
                confidence=min(debt_item.confidence, 0.90),
                affected_surface=surface,
            )

        elif "BEHAVIOR" in category_str or "INVARIANT" in category_str or "DRIFT" in category_str:
            return DebtRootCause(
                cause_id=cause_id,
                debt_id=debt_item.debt_id,
                category=RootCauseCategory.BEHAVIOR_CAUSE,
                description=f"State machine transition invariant violation in surface: {surface}",
                evidence=[{"kind": "invariant_trace", "surface": surface, "details": evidence}],
                confidence=min(debt_item.confidence, 0.88),
                affected_surface=surface,
            )

        elif "TEST" in category_str or "COVERAGE" in category_str or "FLAKY" in category_str:
            return DebtRootCause(
                cause_id=cause_id,
                debt_id=debt_item.debt_id,
                category=RootCauseCategory.TEST_CAUSE,
                description=f"Test debt, coverage gap, or flaky test behavior in surface: {surface}",
                evidence=[{"kind": "test_suite_trace", "surface": surface, "details": evidence}],
                confidence=min(debt_item.confidence, 0.89),
                affected_surface=surface,
            )

        elif "PERF" in category_str or "LATENCY" in category_str or "MEMORY" in category_str or "N+1" in category_str:
            return DebtRootCause(
                cause_id=cause_id,
                debt_id=debt_item.debt_id,
                category=RootCauseCategory.PERFORMANCE_CAUSE,
                description=f"Performance bottleneck or unindexed resource access in surface: {surface}",
                evidence=[{"kind": "profiler_samples", "surface": surface, "details": evidence}],
                confidence=min(debt_item.confidence, 0.87),
                affected_surface=surface,
            )

        elif "RELIAB" in category_str or "CRASH" in category_str or "RETRY" in category_str:
            return DebtRootCause(
                cause_id=cause_id,
                debt_id=debt_item.debt_id,
                category=RootCauseCategory.RELIABILITY_CAUSE,
                description=f"Reliability failure or unhandled exception risk in surface: {surface}",
                evidence=[{"kind": "error_log_trace", "surface": surface, "details": evidence}],
                confidence=min(debt_item.confidence, 0.86),
                affected_surface=surface,
            )

        elif "CODE" in category_str or "COMPLEX" in category_str or "DUPLICAT" in category_str:
            return DebtRootCause(
                cause_id=cause_id,
                debt_id=debt_item.debt_id,
                category=RootCauseCategory.CODE_CAUSE,
                description=f"Code complexity hotspot or code duplication in surface: {surface}",
                evidence=[{"kind": "ast_metric", "surface": surface, "details": evidence}],
                confidence=min(debt_item.confidence, 0.85),
                affected_surface=surface,
            )

        elif "PROCESS" in category_str or "DOC" in category_str:
            return DebtRootCause(
                cause_id=cause_id,
                debt_id=debt_item.debt_id,
                category=RootCauseCategory.PROCESS_CAUSE,
                description=f"Engineering process or documentation debt in surface: {surface}",
                evidence=[{"kind": "audit_log", "surface": surface, "details": evidence}],
                confidence=min(debt_item.confidence, 0.80),
                affected_surface=surface,
            )

        else:
            # UNKNOWN_CAUSE -> must route to human review or boundary analysis
            return DebtRootCause(
                cause_id=cause_id,
                debt_id=debt_item.debt_id,
                category=RootCauseCategory.UNKNOWN_CAUSE,
                description=f"Causal origin cannot be reliably isolated for category '{category_str}'. Routed to BOUNDARY_ANALYSIS and HUMAN_REVIEW.",
                evidence=[{"kind": "unresolved_correlation", "surface": surface, "details": evidence}],
                confidence=0.30,
                affected_surface=surface,
            )
