"""
JARVIS OS — Phase 55: Transactional Multi-Repair Orchestration & Convergence
Transaction Risk Aggregator.
Aggregates risk across blast radius, affected contracts, consumers, security, and economic dimensions.
Enforces the invariant that transaction risk >= max(internal repair risk).
"""

from __future__ import annotations

from typing import Any, Dict, List, Set

from agents.multi_repair_orchestration.models import (
    FailureCluster,
    TransactionRisk,
)


class TransactionRiskAggregator:
    """
    Computes aggregated multi-dimensional risk for a transaction and its failure cluster.
    """

    def aggregate_risk(
        self,
        cluster: FailureCluster,
        repairs: List[Any],
        economic_keywords: List[str] | None = None,
        security_keywords: List[str] | None = None,
    ) -> TransactionRisk:
        economic_keywords = economic_keywords or ["payment", "amount", "price", "stripe", "refund", "billing", "wallet"]
        security_keywords = security_keywords or ["token", "auth", "permission", "password", "jwt", "session", "role"]

        affected_files: Set[str] = set(cluster.shared_files)
        affected_contracts: Set[str] = set(cluster.shared_contracts)
        affected_consumers: Set[str] = set(cluster.shared_consumers)

        max_repair_risk = 0.0
        has_economic = False
        has_security = False

        for rep in repairs:
            # Check individual candidate risk if available
            r_risk = float(getattr(rep, "risk", 0.2))
            if r_risk > max_repair_risk:
                max_repair_risk = r_risk

            # Inspect diffs and strategies
            strategy = str(getattr(rep, "strategy_name", "")).lower()
            diffs = getattr(rep, "diffs", [])
            for diff in diffs:
                fpath = str(getattr(diff, "file_path", "")).lower()
                affected_files.add(fpath)
                patch_str = str(getattr(diff, "added_lines", [])).lower()

                if any(kw in fpath or kw in patch_str for kw in economic_keywords):
                    has_economic = True
                if any(kw in fpath or kw in patch_str for kw in security_keywords):
                    has_security = True

            if any(kw in strategy for kw in economic_keywords):
                has_economic = True
            if any(kw in strategy for kw in security_keywords):
                has_security = True

        blast_radius = len(affected_files) + len(affected_contracts) + len(affected_consumers)

        # Baseline risk calculation
        base_score = 0.20 * min(5, blast_radius) / 5.0
        if has_economic:
            base_score += 0.35
        if has_security:
            base_score += 0.30

        # Invariant: Aggregated risk cannot be less than the max repair risk
        aggregated_risk_score = max(max_repair_risk, min(1.0, base_score))

        return TransactionRisk(
            blast_radius=blast_radius,
            files_count=len(affected_files),
            contracts_count=len(affected_contracts),
            consumers_count=len(affected_consumers),
            has_economic=has_economic,
            has_security=has_security,
            max_repair_risk=round(max_repair_risk, 3),
            aggregated_risk_score=round(aggregated_risk_score, 3),
        )
