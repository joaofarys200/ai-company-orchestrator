"""
JARVIS OS — Phase 51: Behavioral Proof Coverage & Scenario Exploration
Counterexample Generator and Catalog for Behavioral Proof Exploration.
"""

from __future__ import annotations

import copy
import time
from typing import Any, Dict, List, Optional

from agents.behavioral_contract_proof.models import Counterexample, RuntimeTrace
from agents.behavioral_proof_exploration.models import (
    BehavioralScenario,
    ShrunkCounterexample,
    compute_deterministic_id,
)


class ExplorationCounterexampleManager:
    """
    Catalog and generator of reproducible counterexamples detected during exploration.
    """

    def __init__(self) -> None:
        self._counterexamples: Dict[str, Counterexample] = {}
        self._shrunk_counterexamples: Dict[str, ShrunkCounterexample] = {}

    def create_counterexample(
        self,
        scenario: BehavioralScenario,
        before_trace: RuntimeTrace,
        after_trace: RuntimeTrace,
        difference: str,
        scope_id: str,
    ) -> Counterexample:
        """Create a reproducible counterexample from a diverging scenario execution."""
        c_id = compute_deterministic_id({
            "scenario_id": scenario.scenario_id,
            "diff": difference,
            "before_hash": before_trace.trace_hash,
            "after_hash": after_trace.trace_hash,
        }, prefix="cx_")

        cx = Counterexample(
            counterexample_id=c_id,
            input_payload=copy.deepcopy(scenario.input),
            expected_behavior=before_trace.output_payload,
            observed_behavior=after_trace.output_payload,
            difference=difference,
            consumer_id=scenario.consumer_id,
            contract_id=scenario.contract_id,
            trace_id=after_trace.trace_id,
            evidence={
                "scope_id": scope_id,
                "seed": scenario.seed,
                "before_status": before_trace.status_code,
                "after_status": after_trace.status_code,
                "environment": scenario.environment,
            },
            timestamp=100.0,  # deterministic timestamp
        )
        self._counterexamples[c_id] = cx
        return cx

    def register_shrunk_counterexample(self, shrunk: ShrunkCounterexample) -> ShrunkCounterexample:
        """Register a minimized/shrunk counterexample."""
        self._shrunk_counterexamples[shrunk.counterexample_id] = shrunk
        return shrunk

    def get_counterexample(self, cx_id: str) -> Optional[Counterexample]:
        return self._counterexamples.get(cx_id)

    def get_shrunk_counterexample(self, cx_id: str) -> Optional[ShrunkCounterexample]:
        return self._shrunk_counterexamples.get(cx_id)

    def list_all(self) -> List[Counterexample]:
        return list(self._counterexamples.values())

    def list_all_shrunk(self) -> List[ShrunkCounterexample]:
        return list(self._shrunk_counterexamples.values())
