"""
JARVIS OS — Phase 61: Autonomous Test Synthesis & Coverage-Guided Validation
Module: requirements.py
Extracts formal test requirements from changes, symbol impact, contracts,
behavioral invariants, security/economic policies, and historical failures.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Set

from .models import (
    CoverageGapType,
    TestRequirement,
    TestRequirementSource,
)


class TestRequirementExtractor:
    """
    Translates repository changes and cross-phase signals into structured TestRequirements.
    """

    def __init__(self) -> None:
        self._requirements: Dict[str, TestRequirement] = {}

    def extract_from_change(
        self,
        symbol_id: str,
        file_id: str,
        impact_result: Optional[Dict[str, Any]] = None,
        contracts: Optional[List[Dict[str, Any]]] = None,
        behavioral_invariants: Optional[List[str]] = None,
        acceptance_criteria: Optional[List[str]] = None,
        economic_policies: Optional[List[str]] = None,
        security_policies: Optional[List[str]] = None,
        counterexamples: Optional[List[Dict[str, Any]]] = None,
        risk_score: float = 0.5,
    ) -> List[TestRequirement]:
        """Extract all candidate test requirements for a symbol change."""
        reqs: List[TestRequirement] = []

        # 1. Primary symbol impact requirement
        req_id = self._generate_id("SYM", symbol_id, "primary")
        sym_req = TestRequirement(
            requirement_id=req_id,
            source=TestRequirementSource.SYMBOL_IMPACT,
            symbol_id=symbol_id,
            file_id=file_id,
            risk=risk_score,
            coverage_gap=CoverageGapType.UNTESTED_SYMBOL,
            invariant=f"Symbol '{symbol_id}' executes correctly within expected specification",
            scenario_type="unit",
            priority=1.0 * (1.0 + risk_score),
            provenance="symbol_fine_grained_impact",
        )
        reqs.append(sym_req)

        # 2. Downstream consumer requirements from F60 impact
        if impact_result and "downstream_consumers" in impact_result:
            for consumer in impact_result.get("downstream_consumers", []):
                c_id = self._generate_id("CON", symbol_id, consumer)
                reqs.append(
                    TestRequirement(
                        requirement_id=c_id,
                        source=TestRequirementSource.SYMBOL_IMPACT,
                        symbol_id=symbol_id,
                        file_id=file_id,
                        consumer_id=consumer,
                        risk=max(0.3, risk_score * 0.8),
                        coverage_gap=CoverageGapType.UNTESTED_CONSUMER,
                        invariant=f"Consumer '{consumer}' preserves contract compatibility with '{symbol_id}'",
                        scenario_type="integration",
                        priority=0.8 * (1.0 + risk_score),
                        provenance="consumer_impact",
                    )
                )

        # 3. Contract requirements (F44 - F49)
        if contracts:
            for c in contracts:
                cid = c.get("contract_id", "contract_unknown")
                c_req_id = self._generate_id("CTR", symbol_id, cid)
                is_polymorphic = c.get("is_polymorphic", False)
                reqs.append(
                    TestRequirement(
                        requirement_id=c_req_id,
                        source=TestRequirementSource.CONTRACT,
                        symbol_id=symbol_id,
                        file_id=file_id,
                        contract_id=cid,
                        risk=0.8 if is_polymorphic else 0.6,
                        coverage_gap=CoverageGapType.UNTESTED_CONTRACT_VARIANT,
                        invariant=f"Contract '{cid}' adheres to polymorphic schema and required field constraints",
                        scenario_type="contract",
                        priority=1.2 if is_polymorphic else 0.9,
                        provenance="polymorphic_contract_governance",
                    )
                )

        # 4. Behavioral invariants (F50)
        if behavioral_invariants:
            for idx, inv in enumerate(behavioral_invariants):
                b_id = self._generate_id("BEH", symbol_id, str(idx))
                reqs.append(
                    TestRequirement(
                        requirement_id=b_id,
                        source=TestRequirementSource.BEHAVIORAL_INVARIANT,
                        symbol_id=symbol_id,
                        file_id=file_id,
                        risk=0.75,
                        coverage_gap=CoverageGapType.UNTESTED_INVARIANT,
                        invariant=inv,
                        scenario_type="behavioral",
                        priority=1.1,
                        provenance="behavioral_contract_proof",
                    )
                )

        # 5. User acceptance criteria
        if acceptance_criteria:
            for idx, crit in enumerate(acceptance_criteria):
                u_id = self._generate_id("UAC", symbol_id, str(idx))
                reqs.append(
                    TestRequirement(
                        requirement_id=u_id,
                        source=TestRequirementSource.USER_ACCEPTANCE_CRITERION,
                        symbol_id=symbol_id,
                        file_id=file_id,
                        risk=0.9,
                        invariant=crit,
                        scenario_type="acceptance",
                        priority=1.5,
                        provenance="user_intent",
                    )
                )

        # 6. Economic Policies
        if economic_policies:
            for idx, pol in enumerate(economic_policies):
                e_id = self._generate_id("ECO", symbol_id, str(idx))
                reqs.append(
                    TestRequirement(
                        requirement_id=e_id,
                        source=TestRequirementSource.ECONOMIC_POLICY,
                        symbol_id=symbol_id,
                        file_id=file_id,
                        risk=1.0,  # Highest risk
                        coverage_gap=CoverageGapType.UNTESTED_INVARIANT,
                        invariant=pol,
                        scenario_type="economic_sandbox",
                        priority=2.0,  # Top priority
                        provenance="economic_governance",
                    )
                )

        # 7. Security Policies
        if security_policies:
            for idx, sec in enumerate(security_policies):
                s_id = self._generate_id("SEC", symbol_id, str(idx))
                reqs.append(
                    TestRequirement(
                        requirement_id=s_id,
                        source=TestRequirementSource.SECURITY_POLICY,
                        symbol_id=symbol_id,
                        file_id=file_id,
                        risk=1.0,
                        coverage_gap=CoverageGapType.UNTESTED_ERROR_PATH,
                        invariant=sec,
                        scenario_type="security_isolation",
                        priority=2.0,
                        provenance="security_sentinel",
                    )
                )

        # 8. Counterexamples (from failed proofs or historical regressions)
        if counterexamples:
            for cx in counterexamples:
                cx_id = cx.get("counterexample_id", "cx_unknown")
                c_id = self._generate_id("CTX", symbol_id, cx_id)
                reqs.append(
                    TestRequirement(
                        requirement_id=c_id,
                        source=TestRequirementSource.COUNTEREXAMPLE,
                        symbol_id=symbol_id,
                        file_id=file_id,
                        risk=0.95,
                        coverage_gap=CoverageGapType.UNTESTED_REPAIR_PATH,
                        invariant=f"Counterexample '{cx_id}' is permanently prevented from recurring",
                        scenario_type="regression",
                        priority=1.8,
                        provenance="behavioral_proof_counterexample",
                    )
                )

        for r in reqs:
            self._requirements[r.requirement_id] = r

        return reqs

    def get_requirement(self, requirement_id: str) -> Optional[TestRequirement]:
        return self._requirements.get(requirement_id)

    def list_requirements(self) -> List[TestRequirement]:
        return list(self._requirements.values())

    def _generate_id(self, prefix: str, symbol: str, differentiator: str) -> str:
        payload = f"{prefix}:{symbol}:{differentiator}"
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
        return f"REQ_{prefix}_{digest}"
