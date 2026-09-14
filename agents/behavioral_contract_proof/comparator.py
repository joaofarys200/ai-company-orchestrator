"""
JARVIS OS — Phase 50: Behavioral Contract Preservation & Migration Proof
Behavioral Comparator & Equivalence Level Evaluator.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Set, Tuple

from agents.behavioral_contract_proof.models import BehaviorBaseline, EquivalenceLevel, RuntimeTrace
from agents.behavioral_contract_proof.normalizer import RuntimeTraceNormalizer


class ComparisonResult:
    """Encapsulates the outcome of a behavioral comparison."""

    def __init__(
        self,
        equivalence_level: EquivalenceLevel,
        differences: List[str],
        baseline_shape: Dict[str, Any],
        observed_shape: Dict[str, Any],
    ) -> None:
        self.equivalence_level = equivalence_level
        self.differences = differences
        self.baseline_shape = baseline_shape
        self.observed_shape = observed_shape

    @property
    def is_compatible(self) -> bool:
        return self.equivalence_level in (
            EquivalenceLevel.EXACT_EQUIVALENCE,
            EquivalenceLevel.SEMANTIC_EQUIVALENCE,
            EquivalenceLevel.ALLOWED_CHANGE,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "equivalence_level": self.equivalence_level.value,
            "is_compatible": self.is_compatible,
            "differences": self.differences,
            "baseline_shape": self.baseline_shape,
            "observed_shape": self.observed_shape,
        }


class BehaviorComparator:
    """
    Compares normalized baseline against observed post-change execution trace.
    """

    @classmethod
    def compare(cls, baseline: BehaviorBaseline, observed_trace: RuntimeTrace) -> ComparisonResult:
        """
        Executes full comparative analysis across status, payload shapes, events,
        side effects, economic effects, and auth states.
        """
        differences: List[str] = []

        # 1. Status Code Comparison
        if baseline.status_code != observed_trace.status_code:
            differences.append(
                f"Status code mismatch: expected {baseline.status_code}, observed {observed_trace.status_code}"
            )

        # 2. Output Payload Shape Comparison (Normalized)
        norm_baseline_out = RuntimeTraceNormalizer.normalize_payload(baseline.output_shape)
        norm_observed_out = RuntimeTraceNormalizer.normalize_payload(observed_trace.output_payload)

        payload_diffs = cls._compare_payload_shapes(norm_baseline_out, norm_observed_out, path="response")
        differences.extend(payload_diffs)

        # 3. Events Comparison
        event_diffs = cls._compare_events(baseline.events, observed_trace.events)
        differences.extend(event_diffs)

        # 4. Economic Effects Comparison
        econ_diffs = cls._compare_economic_effects(baseline.economic_effects, observed_trace.economic_effects)
        differences.extend(econ_diffs)

        # 5. Authorization State Comparison
        auth_diffs = cls._compare_auth_state(baseline.authorization_state, observed_trace.authorization_state)
        differences.extend(auth_diffs)

        # 6. Side Effects Ordering and Content
        side_diffs = cls._compare_side_effects(baseline.side_effects, observed_trace.side_effects)
        differences.extend(side_diffs)

        # Determine Equivalence Level
        if not differences:
            return ComparisonResult(
                equivalence_level=EquivalenceLevel.EXACT_EQUIVALENCE,
                differences=[],
                baseline_shape=norm_baseline_out,
                observed_shape=norm_observed_out,
            )

        # Check for Breaking Changes vs Allowed Changes
        is_breaking = False
        for diff in differences:
            # Status code changes, removals, scalar-to-object, and economic/auth changes are breaking
            if any(
                tag in diff
                for tag in (
                    "Status code mismatch",
                    "Missing required field",
                    "Type changed from",
                    "Scalar-to-object change",
                    "Economic effect altered",
                    "Currency mismatch",
                    "Amount mismatch",
                    "Authorization requirement changed",
                    "Event removed or renamed",
                )
            ):
                is_breaking = True
                break

        if is_breaking:
            level = EquivalenceLevel.BREAKING_CHANGE
        else:
            # Check if all differences are benign additions
            if all("Added optional field" in d or "Additional non-conflicting event" in d for d in differences):
                level = EquivalenceLevel.ALLOWED_CHANGE
            else:
                level = EquivalenceLevel.SEMANTIC_EQUIVALENCE

        return ComparisonResult(
            equivalence_level=level,
            differences=differences,
            baseline_shape=norm_baseline_out,
            observed_shape=norm_observed_out,
        )

    @classmethod
    def _compare_payload_shapes(cls, expected: Any, observed: Any, path: str = "") -> List[str]:
        diffs = []

        if isinstance(expected, dict) and isinstance(observed, dict):
            # Check for missing expected keys
            for k, exp_val in expected.items():
                curr_path = f"{path}.{k}" if path else k
                if k not in observed:
                    diffs.append(f"Missing required field at '{curr_path}'")
                else:
                    obs_val = observed[k]
                    # Check scalar-to-object
                    if not isinstance(exp_val, dict) and isinstance(obs_val, dict):
                        diffs.append(
                            f"Scalar-to-object change at '{curr_path}': expected scalar {type(exp_val).__name__}, observed object"
                        )
                    # Check object-to-scalar
                    elif isinstance(exp_val, dict) and not isinstance(obs_val, dict):
                        diffs.append(
                            f"Object-to-scalar change at '{curr_path}': expected object, observed {type(obs_val).__name__}"
                        )
                    # Check primitive type change
                    elif type(exp_val) != type(obs_val) and exp_val is not None and obs_val is not None:
                        diffs.append(
                            f"Type changed from {type(exp_val).__name__} to {type(obs_val).__name__} at '{curr_path}'"
                        )
                    else:
                        diffs.extend(cls._compare_payload_shapes(exp_val, obs_val, curr_path))

            # Check for added keys
            for k in observed:
                if k not in expected:
                    curr_path = f"{path}.{k}" if path else k
                    diffs.append(f"Added optional field '{curr_path}'")

        elif isinstance(expected, list) and isinstance(observed, list):
            if len(expected) != len(observed):
                diffs.append(f"Array length changed at '{path}': expected {len(expected)}, observed {len(observed)}")
            else:
                for idx, (exp_item, obs_item) in enumerate(zip(expected, observed)):
                    diffs.extend(cls._compare_payload_shapes(exp_item, obs_item, f"{path}[{idx}]"))

        elif expected != observed:
            # Value mismatch
            diffs.append(f"Value mismatch at '{path}': expected '{expected}', observed '{observed}'")

        return diffs

    @classmethod
    def _compare_events(cls, expected_events: List[Dict[str, Any]], observed_events: List[Dict[str, Any]]) -> List[str]:
        diffs = []
        exp_topics = [e.get("topic") or e.get("name") or e.get("event") for e in expected_events]
        obs_topics = [e.get("topic") or e.get("name") or e.get("event") for e in observed_events]

        for topic in exp_topics:
            if topic and topic not in obs_topics:
                diffs.append(f"Event removed or renamed: expected event '{topic}' was not emitted")

        for topic in obs_topics:
            if topic and topic not in exp_topics:
                diffs.append(f"Additional non-conflicting event emitted: '{topic}'")

        return diffs

    @classmethod
    def _compare_economic_effects(
        cls, expected_econ: List[Dict[str, Any]], observed_econ: List[Dict[str, Any]]
    ) -> List[str]:
        diffs = []
        if len(expected_econ) != len(observed_econ):
            diffs.append(
                f"Economic effect altered: count changed from {len(expected_econ)} to {len(observed_econ)}"
            )
            return diffs

        for idx, (exp, obs) in enumerate(zip(expected_econ, observed_econ)):
            if exp.get("currency") != obs.get("currency"):
                diffs.append(
                    f"Currency mismatch at economic effect [{idx}]: expected '{exp.get('currency')}', observed '{obs.get('currency')}'"
                )
            if exp.get("amount") != obs.get("amount"):
                diffs.append(
                    f"Amount mismatch at economic effect [{idx}]: expected '{exp.get('amount')}', observed '{obs.get('amount')}'"
                )
            if exp.get("ledger_action") != obs.get("ledger_action"):
                diffs.append(
                    f"Economic effect altered: ledger_action expected '{exp.get('ledger_action')}', observed '{obs.get('ledger_action')}'"
                )

        return diffs

    @classmethod
    def _compare_auth_state(cls, expected_auth: Dict[str, Any], observed_auth: Dict[str, Any]) -> List[str]:
        diffs = []
        exp_req = expected_auth.get("requires_auth", False)
        obs_req = observed_auth.get("requires_auth", False)

        if exp_req and not obs_req:
            diffs.append("Authorization requirement changed: Authentication was removed (Auth Downgrade)")
        elif not exp_req and obs_req:
            diffs.append("Authorization requirement changed: Route now requires authentication")

        exp_roles = set(expected_auth.get("roles", []))
        obs_roles = set(observed_auth.get("roles", []))
        if exp_roles != obs_roles:
            diffs.append(f"Authorization requirement changed: roles changed from {exp_roles} to {obs_roles}")

        return diffs

    @classmethod
    def _compare_side_effects(cls, expected_se: List[Dict[str, Any]], observed_se: List[Dict[str, Any]]) -> List[str]:
        diffs = []
        if len(expected_se) != len(observed_se):
            diffs.append(f"Side effects count mismatch: expected {len(expected_se)}, observed {len(observed_se)}")
            return diffs

        for idx, (exp, obs) in enumerate(zip(expected_se, observed_se)):
            if exp.get("type") != obs.get("type"):
                diffs.append(
                    f"Side effect ordering/type mismatch at [{idx}]: expected '{exp.get('type')}', observed '{obs.get('type')}'"
                )
        return diffs
