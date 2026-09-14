"""
JARVIS OS — Phase 51: Behavioral Proof Coverage & Scenario Exploration
Trace normalization and adapter integrating with Phase 50 RuntimeTraceNormalizer.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from agents.behavioral_contract_proof.models import RuntimeTrace
from agents.behavioral_contract_proof.normalizer import RuntimeTraceNormalizer
from agents.behavioral_proof_exploration.models import BehavioralScenario


class ExplorationTraceAdapter:
    """
    Adapter converting and normalizing scenario execution outputs into
    deterministic Phase 50 RuntimeTrace structures.
    """

    def __init__(self) -> None:
        self.normalizer = RuntimeTraceNormalizer()

    def normalize_trace(self, trace: RuntimeTrace) -> RuntimeTrace:
        """Apply Phase 50 deterministic normalization to an execution trace."""
        normalized_dict = self.normalizer.normalize_trace(trace.to_dict())
        trace.input_payload = normalized_dict.get("input_payload", trace.input_payload)
        trace.output_payload = normalized_dict.get("output_payload", trace.output_payload)
        trace.side_effects = normalized_dict.get("side_effects", trace.side_effects)
        trace.events = normalized_dict.get("events", trace.events)
        trace.economic_effects = normalized_dict.get("economic_effects", trace.economic_effects)
        trace.authorization_state = normalized_dict.get("authorization_state", trace.authorization_state)
        return trace

    def scenario_to_trace(
        self,
        scenario: BehavioralScenario,
        status_code: int,
        output_payload: Dict[str, Any],
        side_effects: Optional[List[Dict[str, Any]]] = None,
        economic_effects: Optional[List[Dict[str, Any]]] = None,
        auth_state: Optional[Dict[str, Any]] = None,
    ) -> RuntimeTrace:
        """Create a normalized RuntimeTrace from a BehavioralScenario."""
        raw_trace = RuntimeTrace(
            trace_id=f"tr_{scenario.scenario_id}",
            source="scenario_exploration",
            timestamp=100.0,
            mission_id="msn_phase51_exploration",
            consumer_id=scenario.consumer_id,
            contract_id=scenario.contract_id,
            operation="explore",
            input_payload=copy.deepcopy(scenario.input),
            output_payload=copy.deepcopy(output_payload),
            status_code=status_code,
            side_effects=copy.deepcopy(side_effects or []),
            economic_effects=copy.deepcopy(economic_effects or []),
            authorization_state=copy.deepcopy(auth_state or {}),
            environment=scenario.environment,
            build_hash="build_hash_deterministic",
        )
        return self.normalize_trace(raw_trace)
