"""
JARVIS OS — Phase 50: Behavioral Contract Preservation & Migration Proof
Concrete Counterexample Generator for Incompatible Migrations.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from agents.behavioral_contract_proof.models import BehaviorBaseline, Counterexample, RuntimeTrace


class CounterexampleGenerator:
    """
    Generates actionable, verifiable counterexamples demonstrating why a contract
    migration is behaviorally incompatible.
    """

    @classmethod
    def generate(
        cls,
        baseline: BehaviorBaseline,
        observed: RuntimeTrace,
        difference_summary: str,
        specific_evidence: Optional[Dict[str, Any]] = None,
    ) -> Counterexample:
        """Constructs a deterministic counterexample record."""
        cid = f"cex_{baseline.consumer_id}_{baseline.contract_id}_{int(time.time() * 1000)}"

        expected_behavior = {
            "status_code": baseline.status_code,
            "output_shape": baseline.output_shape,
            "events": baseline.events,
            "economic_effects": baseline.economic_effects,
            "authorization_state": baseline.authorization_state,
        }

        observed_behavior = {
            "status_code": observed.status_code,
            "output_payload": observed.output_payload,
            "events": observed.events,
            "economic_effects": observed.economic_effects,
            "authorization_state": observed.authorization_state,
        }

        evidence = specific_evidence or {
            "baseline_hash": baseline.baseline_hash,
            "observed_trace_hash": observed.trace_hash,
            "contract_version_before": baseline.contract_version,
            "observed_operation": observed.operation,
        }

        return Counterexample(
            counterexample_id=cid,
            input_payload=observed.input_payload,
            expected_behavior=expected_behavior,
            observed_behavior=observed_behavior,
            difference=difference_summary,
            consumer_id=baseline.consumer_id,
            contract_id=baseline.contract_id,
            trace_id=observed.trace_id,
            evidence=evidence,
            timestamp=time.time(),
        )
