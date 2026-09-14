"""
JARVIS OS — Phase 50: Behavioral Contract Preservation & Migration Proof
8-Stage Structural Behavioral Model for Contract Invocations.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from agents.behavioral_contract_proof.models import (
    BehavioralInvariantType,
    BehavioralModel,
    BehavioralStage,
    BehavioralStageExecution,
)


CANONICAL_STAGE_ORDER: List[BehavioralStage] = [
    BehavioralStage.REQUEST,
    BehavioralStage.AUTH,
    BehavioralStage.VALIDATION,
    BehavioralStage.BUSINESS_LOGIC,
    BehavioralStage.RESPONSE,
    BehavioralStage.EVENT,
    BehavioralStage.SIDE_EFFECT,
    BehavioralStage.ECONOMIC_EFFECT,
]


class BehavioralModelEngine:
    """
    Constructs, validates, and evaluates structural behavioral models.
    """

    @classmethod
    def create_default_model(
        cls,
        contract_id: str,
        version: str,
        is_economic: bool = False,
        custom_invariants: Optional[List[BehavioralInvariantType]] = None,
    ) -> BehavioralModel:
        """Constructs a standard 8-stage behavioral model."""
        stages = list(CANONICAL_STAGE_ORDER)
        if not is_economic:
            # Omit economic effect if not an economic route
            stages = [s for s in stages if s != BehavioralStage.ECONOMIC_EFFECT]

        invariants = custom_invariants or [
            BehavioralInvariantType.AUTHORIZATION_PRESERVED,
            BehavioralInvariantType.REQUIRED_FIELDS_PRESERVED,
            BehavioralInvariantType.ERROR_SEMANTICS_PRESERVED,
            BehavioralInvariantType.EVENT_SEMANTICS_PRESERVED,
            BehavioralInvariantType.SIDE_EFFECT_ORDER_PRESERVED,
            BehavioralInvariantType.CONSUMER_EXPECTATION_PRESERVED,
        ]
        if is_economic:
            invariants.append(BehavioralInvariantType.ECONOMIC_VALUE_PRESERVED)

        return BehavioralModel(
            model_id=f"bm_{contract_id}_{version}",
            contract_id=contract_id,
            version=version,
            stages=stages,
            preconditions=[
                "request_envelope_valid",
                "auth_header_present",
                "schema_contract_satisfied",
            ],
            postconditions=[
                "response_shape_conforms_to_spec",
                "events_emitted_in_registry",
                "side_effects_recorded_with_idempotency",
            ],
            invariants=invariants,
        )

    @classmethod
    def validate_stage_sequence(cls, executions: List[BehavioralStageExecution]) -> Tuple[bool, Optional[str]]:
        """
        Validates whether stage executions respect the expected canonical order.
        """
        if not executions:
            return True, None

        current_index = -1
        for exec_stage in executions:
            try:
                stage_idx = CANONICAL_STAGE_ORDER.index(exec_stage.stage)
            except ValueError:
                return False, f"Unknown stage '{exec_stage.stage}' in execution flow"

            if stage_idx < current_index:
                prev_stage = CANONICAL_STAGE_ORDER[current_index].value
                curr_stage = exec_stage.stage.value
                return False, f"Stage sequence violation: '{curr_stage}' executed after '{prev_stage}'"
            current_index = stage_idx

        return True, None
