from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Tuple

from .models import CondensationDAG, StronglyConnectedComponent


class SCCSecuritySentinel:
    """Guards against graph poisoning, illegal cycle injection, and state tampering in SCC graphs."""

    FINANCIAL_SYMBOLS = ["payment", "billing", "wallet", "ledger", "invoice", "refund"]

    def __init__(self) -> None:
        self.violations: List[Dict[str, Any]] = []

    def validate_scc_integrity(self, scc: StronglyConnectedComponent) -> Tuple[bool, str]:
        """Validates that SCC state hash matches its internal structure and contents."""
        hash_input = f"{scc.scc_id}:{sorted(scc.nodes)}:{len(scc.edges_internal)}:{scc.density}"
        expected = hashlib.sha256(hash_input.encode()).hexdigest()[:16]

        if scc.state_hash != expected:
            self._record_violation("SCC_STATE_TAMPERING", f"Hash mismatch on {scc.scc_id}")
            return False, "SCC state hash mismatch"

        # Check for financial symbols masquerading in cycles
        for n in scc.nodes:
            if any(kw in n.lower() for kw in self.FINANCIAL_SYMBOLS):
                if scc.size > 50:
                    self._record_violation(
                        "SUSPICIOUS_DENSE_FINANCIAL_CYCLE",
                        f"Financial node {n} trapped in large cyclic component of size {scc.size}"
                    )

        return True, "SCC integrity verified"

    def validate_dag_acyclicity(self, dag: CondensationDAG) -> Tuple[bool, str]:
        """Ensures the Condensation DAG is strictly acyclic."""
        if not dag.is_acyclic:
            self._record_violation("DAG_CYCLE_DETECTED", f"Condensation DAG {dag.dag_id} contains illegal cycles")
            return False, "Condensation DAG is not acyclic"
        return True, "Condensation DAG is strictly acyclic"

    def _record_violation(self, v_type: str, details: str) -> None:
        self.violations.append({"type": v_type, "details": details})

    def get_violations(self) -> List[Dict[str, Any]]:
        return list(self.violations)
