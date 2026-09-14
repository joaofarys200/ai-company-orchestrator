"""
JARVIS OS — Phase 51: Behavioral Proof Coverage & Scenario Exploration
Counterexample Shrinker: Delta-debugging input minimization for reproducible divergences.
"""

from __future__ import annotations

import copy
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from agents.behavioral_proof_exploration.models import (
    BehavioralScenario,
    ShrunkCounterexample,
    compute_deterministic_id,
)


class CounterexampleShrinker:
    """
    Delta-Debugging Counterexample Shrinker.
    Given a failing scenario input (e.g., 20 fields), systematically minimizes the payload
    down to the smallest subset of fields (e.g., 2 fields) that reproduces the divergence.
    """

    def shrink(
        self,
        scenario: BehavioralScenario,
        divergence_checker: Callable[[Dict[str, Any]], bool],
        proof_scope_id: str,
        difference: str,
        trace_id: str,
    ) -> ShrunkCounterexample:
        """
        Execute iterative delta debugging on scenario input fields.
        """
        original_input = copy.deepcopy(scenario.input)
        keys = list(original_input.keys())
        original_field_count = len(keys)

        # Baseline check: ensure original payload actually reproduces divergence
        if not divergence_checker(original_input):
            # If not reproducing, return as-is
            return ShrunkCounterexample(
                counterexample_id=f"shrunk_{scenario.scenario_id}",
                scenario_id=scenario.scenario_id,
                consumer_id=scenario.consumer_id,
                contract_id=scenario.contract_id,
                original_input=original_input,
                minimal_input=copy.deepcopy(original_input),
                difference=difference,
                original_field_count=original_field_count,
                minimal_field_count=original_field_count,
                shrink_steps=0,
                trace_id=trace_id,
                proof_scope_id=proof_scope_id,
                reproducible_seed=scenario.seed,
            )

        current_payload = copy.deepcopy(original_input)
        shrink_steps = 0
        changed = True

        # Iterative 1-minimal reduction
        while changed and len(current_payload) > 1:
            changed = False
            current_keys = list(current_payload.keys())

            for k in current_keys:
                candidate = copy.deepcopy(current_payload)
                del candidate[k]
                shrink_steps += 1

                # If removing field k STILL reproduces the divergence, keep it removed!
                if divergence_checker(candidate):
                    current_payload = candidate
                    changed = True
                    break

        shrunk_id = compute_deterministic_id({
            "scenario_id": scenario.scenario_id,
            "minimal_input": current_payload,
            "scope_id": proof_scope_id,
        }, prefix="shrunk_")

        return ShrunkCounterexample(
            counterexample_id=shrunk_id,
            scenario_id=scenario.scenario_id,
            consumer_id=scenario.consumer_id,
            contract_id=scenario.contract_id,
            original_input=original_input,
            minimal_input=current_payload,
            difference=difference,
            original_field_count=original_field_count,
            minimal_field_count=len(current_payload),
            shrink_steps=shrink_steps,
            trace_id=trace_id,
            proof_scope_id=proof_scope_id,
            reproducible_seed=scenario.seed,
            timestamp=100.0,  # deterministic timestamp
        )
