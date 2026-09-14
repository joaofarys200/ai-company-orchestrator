"""
JARVIS OS — Phase 50: Behavioral Contract Preservation & Migration Proof
Behavioral Invariants Evaluation Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from agents.behavioral_contract_proof.models import (
    BehaviorBaseline,
    BehavioralInvariantType,
    RuntimeTrace,
)


@dataclass
class InvariantEvaluationResult:
    """Outcome of evaluating a single behavioral invariant."""
    invariant: BehavioralInvariantType
    satisfied: bool
    violation_reason: Optional[str] = None
    details: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "invariant": self.invariant.value,
            "satisfied": self.satisfied,
            "violation_reason": self.violation_reason,
            "details": self.details or {},
        }


class BehavioralInvariantEngine:
    """
    Evaluates formal behavioral invariants between baseline and observed trace.
    """

    @classmethod
    def evaluate_invariants(
        cls,
        baseline: BehaviorBaseline,
        observed: RuntimeTrace,
        invariants_to_check: Optional[List[BehavioralInvariantType]] = None,
        is_closed_exhaustive: bool = False,
    ) -> List[InvariantEvaluationResult]:
        """Runs all specified invariant checks."""
        targets = invariants_to_check or list(BehavioralInvariantType)
        results = []

        for inv in targets:
            if inv == BehavioralInvariantType.AUTHORIZATION_PRESERVED:
                results.append(cls._check_authorization_preserved(baseline, observed))
            elif inv == BehavioralInvariantType.ECONOMIC_VALUE_PRESERVED:
                results.append(cls._check_economic_value_preserved(baseline, observed))
            elif inv == BehavioralInvariantType.EVENT_SEMANTICS_PRESERVED:
                results.append(cls._check_event_semantics_preserved(baseline, observed))
            elif inv == BehavioralInvariantType.REQUIRED_FIELDS_PRESERVED:
                results.append(cls._check_required_fields_preserved(baseline, observed))
            elif inv == BehavioralInvariantType.ERROR_SEMANTICS_PRESERVED:
                results.append(cls._check_error_semantics_preserved(baseline, observed))
            elif inv == BehavioralInvariantType.SIDE_EFFECT_ORDER_PRESERVED:
                results.append(cls._check_side_effect_order_preserved(baseline, observed))
            elif inv == BehavioralInvariantType.CONSUMER_EXPECTATION_PRESERVED:
                results.append(cls._check_consumer_expectation_preserved(baseline, observed, is_closed_exhaustive))

        return results

    @classmethod
    def _check_authorization_preserved(cls, b: BehaviorBaseline, o: RuntimeTrace) -> InvariantEvaluationResult:
        b_auth = b.authorization_state or {}
        o_auth = o.authorization_state or {}

        # Check downgrade: was required, now isn't
        if b_auth.get("requires_auth", False) and not o_auth.get("requires_auth", False):
            return InvariantEvaluationResult(
                invariant=BehavioralInvariantType.AUTHORIZATION_PRESERVED,
                satisfied=False,
                violation_reason="Authorization requirement downgraded from required to public",
            )

        b_roles = set(b_auth.get("roles", []))
        o_roles = set(o_auth.get("roles", []))
        if b_roles != o_roles:
            return InvariantEvaluationResult(
                invariant=BehavioralInvariantType.AUTHORIZATION_PRESERVED,
                satisfied=False,
                violation_reason=f"Role mismatch: baseline requires {b_roles}, observed {o_roles}",
            )

        return InvariantEvaluationResult(
            invariant=BehavioralInvariantType.AUTHORIZATION_PRESERVED,
            satisfied=True,
        )

    @classmethod
    def _check_economic_value_preserved(cls, b: BehaviorBaseline, o: RuntimeTrace) -> InvariantEvaluationResult:
        b_econ = b.economic_effects or []
        o_econ = o.economic_effects or []

        if len(b_econ) != len(o_econ):
            return InvariantEvaluationResult(
                invariant=BehavioralInvariantType.ECONOMIC_VALUE_PRESERVED,
                satisfied=False,
                violation_reason=f"Economic effect count changed: baseline {len(b_econ)}, observed {len(o_econ)}",
            )

        for idx, (b_item, o_item) in enumerate(zip(b_econ, o_econ)):
            if b_item.get("amount") != o_item.get("amount"):
                return InvariantEvaluationResult(
                    invariant=BehavioralInvariantType.ECONOMIC_VALUE_PRESERVED,
                    satisfied=False,
                    violation_reason=(
                        f"Monetary amount delta at item [{idx}]: baseline {b_item.get('amount')}, "
                        f"observed {o_item.get('amount')}"
                    ),
                )
            if b_item.get("currency") != o_item.get("currency"):
                return InvariantEvaluationResult(
                    invariant=BehavioralInvariantType.ECONOMIC_VALUE_PRESERVED,
                    satisfied=False,
                    violation_reason=(
                        f"Currency divergence at item [{idx}]: baseline {b_item.get('currency')}, "
                        f"observed {o_item.get('currency')}"
                    ),
                )

        return InvariantEvaluationResult(
            invariant=BehavioralInvariantType.ECONOMIC_VALUE_PRESERVED,
            satisfied=True,
        )

    @classmethod
    def _check_event_semantics_preserved(cls, b: BehaviorBaseline, o: RuntimeTrace) -> InvariantEvaluationResult:
        b_events = {e.get("topic") or e.get("name") for e in b.events if e.get("topic") or e.get("name")}
        o_events = {e.get("topic") or e.get("name") for e in o.events if e.get("topic") or e.get("name")}

        missing_events = b_events - o_events
        if missing_events:
            return InvariantEvaluationResult(
                invariant=BehavioralInvariantType.EVENT_SEMANTICS_PRESERVED,
                satisfied=False,
                violation_reason=f"Baseline events missing in observed execution: {missing_events}",
            )

        return InvariantEvaluationResult(
            invariant=BehavioralInvariantType.EVENT_SEMANTICS_PRESERVED,
            satisfied=True,
        )

    @classmethod
    def _check_required_fields_preserved(cls, b: BehaviorBaseline, o: RuntimeTrace) -> InvariantEvaluationResult:
        missing_fields = []

        def check_keys(b_dict: Any, o_dict: Any, prefix: str = ""):
            if isinstance(b_dict, dict) and isinstance(o_dict, dict):
                for k, v in b_dict.items():
                    path = f"{prefix}.{k}" if prefix else k
                    if k not in o_dict:
                        missing_fields.append(path)
                    else:
                        check_keys(v, o_dict[k], path)

        check_keys(b.output_shape, o.output_payload)

        if missing_fields:
            return InvariantEvaluationResult(
                invariant=BehavioralInvariantType.REQUIRED_FIELDS_PRESERVED,
                satisfied=False,
                violation_reason=f"Required output fields missing: {missing_fields}",
            )

        return InvariantEvaluationResult(
            invariant=BehavioralInvariantType.REQUIRED_FIELDS_PRESERVED,
            satisfied=True,
        )

    @classmethod
    def _check_error_semantics_preserved(cls, b: BehaviorBaseline, o: RuntimeTrace) -> InvariantEvaluationResult:
        # If baseline is error (4xx/5xx), observed should also be error with compatible status
        b_is_err = b.status_code >= 400
        o_is_err = o.status_code >= 400

        if b_is_err != o_is_err:
            return InvariantEvaluationResult(
                invariant=BehavioralInvariantType.ERROR_SEMANTICS_PRESERVED,
                satisfied=False,
                violation_reason=(
                    f"Error status mismatch: baseline status {b.status_code} (is_err={b_is_err}), "
                    f"observed status {o.status_code} (is_err={o_is_err})"
                ),
            )

        return InvariantEvaluationResult(
            invariant=BehavioralInvariantType.ERROR_SEMANTICS_PRESERVED,
            satisfied=True,
        )

    @classmethod
    def _check_side_effect_order_preserved(cls, b: BehaviorBaseline, o: RuntimeTrace) -> InvariantEvaluationResult:
        b_types = [se.get("type") for se in b.side_effects if se.get("type")]
        o_types = [se.get("type") for se in o.side_effects if se.get("type")]

        if b_types != o_types:
            return InvariantEvaluationResult(
                invariant=BehavioralInvariantType.SIDE_EFFECT_ORDER_PRESERVED,
                satisfied=False,
                violation_reason=f"Side effect execution sequence divergence: baseline {b_types}, observed {o_types}",
            )

        return InvariantEvaluationResult(
            invariant=BehavioralInvariantType.SIDE_EFFECT_ORDER_PRESERVED,
            satisfied=True,
        )

    @classmethod
    def _check_consumer_expectation_preserved(
        cls, b: BehaviorBaseline, o: RuntimeTrace, is_closed_exhaustive: bool
    ) -> InvariantEvaluationResult:
        if is_closed_exhaustive:
            # Closed-world: Any additional unexpected keys or events violate closed consumer expectations
            b_keys = set(b.output_shape.keys()) if isinstance(b.output_shape, dict) else set()
            o_keys = set(o.output_payload.keys()) if isinstance(o.output_payload, dict) else set()
            unexpected_keys = o_keys - b_keys
            if unexpected_keys:
                return InvariantEvaluationResult(
                    invariant=BehavioralInvariantType.CONSUMER_EXPECTATION_PRESERVED,
                    satisfied=False,
                    violation_reason=(
                        f"Closed-exhaustive consumer expectation violated: unexpected added keys {unexpected_keys}"
                    ),
                )

        return InvariantEvaluationResult(
            invariant=BehavioralInvariantType.CONSUMER_EXPECTATION_PRESERVED,
            satisfied=True,
        )
