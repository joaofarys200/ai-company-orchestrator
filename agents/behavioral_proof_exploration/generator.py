"""
JARVIS OS — Phase 51: Behavioral Proof Coverage & Scenario Exploration
Scenario Generator: Deterministic generation from Schemas, Baselines, Traces, and Constraints.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Dict, List, Optional, Set

from agents.behavioral_proof_exploration.models import (
    BehavioralScenario,
    ExplorationBudget,
    ExplorationStrategy,
)


class ScenarioGenerator:
    """
    Deterministic Scenario Generator.
    Generates bounded test scenarios across all canonical edge-case dimensions
    without performing any real external economic operations.
    """

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed

    def generate_scenarios_for_contract(
        self,
        contract_id: str,
        consumer_id: str,
        schema: Dict[str, Any],
        baseline: Optional[Dict[str, Any]] = None,
        historical_traces: Optional[List[Dict[str, Any]]] = None,
        budget: Optional[ExplorationBudget] = None,
        polymorphic_variants: Optional[List[str]] = None,
        is_open_polymorphic: bool = False,
    ) -> List[BehavioralScenario]:
        """
        Generate bounded scenarios covering all required dimensions.
        """
        scenarios: List[BehavioralScenario] = []
        max_scenarios = budget.max_scenarios if budget else 100
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))

        # 1. Valid Canonical Input
        base_valid_input: Dict[str, Any] = {}
        for prop, pdef in properties.items():
            base_valid_input[prop] = self._generate_canonical_value(prop, pdef)
        
        # If schema has no properties but baseline exists, use baseline input shape
        if not base_valid_input and baseline and "input_shape" in baseline:
            base_valid_input = copy.deepcopy(baseline["input_shape"])
        if not base_valid_input:
            base_valid_input = {"id": "default_01", "name": "Standard Test", "amount": 10.0, "status": "active"}

        # Add 1. VALID INPUT
        scenarios.append(
            BehavioralScenario.create(
                consumer_id=consumer_id,
                contract_id=contract_id,
                input_payload=copy.deepcopy(base_valid_input),
                expected_behavior={"status_code": 200, "success": True},
                preconditions=["VALID_STATE"],
                seed=self.seed,
                coverage_target="valid_input",
                strategy=ExplorationStrategy.SCHEMA_MUTATION,
            )
        )

        # 2. MISSING REQUIRED FIELDS
        for req_field in sorted(required):
            if req_field in base_valid_input:
                missing_payload = copy.deepcopy(base_valid_input)
                del missing_payload[req_field]
                scenarios.append(
                    BehavioralScenario.create(
                        consumer_id=consumer_id,
                        contract_id=contract_id,
                        input_payload=missing_payload,
                        expected_behavior={"status_code": 400, "success": False, "error": "MISSING_REQUIRED_FIELD"},
                        mutation={"type": "missing_field", "target_field": req_field},
                        seed=self.seed + len(scenarios),
                        coverage_target=f"missing_required_{req_field}",
                        strategy=ExplorationStrategy.SCHEMA_MUTATION,
                    )
                )

        # 3. OPTIONAL FIELD OMITTED & OPTIONAL FIELD PRESENT
        optional_fields = [p for p in properties if p not in required]
        for opt_field in optional_fields:
            # Omitted
            omitted_payload = copy.deepcopy(base_valid_input)
            if opt_field in omitted_payload:
                del omitted_payload[opt_field]
                scenarios.append(
                    BehavioralScenario.create(
                        consumer_id=consumer_id,
                        contract_id=contract_id,
                        input_payload=omitted_payload,
                        expected_behavior={"status_code": 200, "success": True},
                        mutation={"type": "optional_field_omitted", "target_field": opt_field},
                        seed=self.seed + len(scenarios),
                        coverage_target=f"optional_omitted_{opt_field}",
                        strategy=ExplorationStrategy.SCHEMA_MUTATION,
                    )
                )

        # 4. BOUNDARY VALUES (numbers min/max, 0, strings empty/large, negative)
        numeric_fields = [p for p, d in properties.items() if d.get("type") in ("integer", "number")]
        if not numeric_fields and "amount" in base_valid_input:
            numeric_fields = ["amount"]

        for num_field in numeric_fields:
            for b_val in [0, -1, 999999999, 0.0001]:
                b_payload = copy.deepcopy(base_valid_input)
                b_payload[num_field] = b_val
                scenarios.append(
                    BehavioralScenario.create(
                        consumer_id=consumer_id,
                        contract_id=contract_id,
                        input_payload=b_payload,
                        expected_behavior={"status_code": 200 if b_val >= 0 else 400, "boundary_checked": True},
                        mutation={"type": "boundary_value", "field": num_field, "value": b_val},
                        seed=self.seed + len(scenarios),
                        coverage_target=f"boundary_{num_field}_{b_val}",
                        strategy=ExplorationStrategy.BOUNDARY_EXPLORATION,
                    )
                )

        # 5. EMPTY COLLECTIONS & LARGE COLLECTIONS
        array_fields = [p for p, d in properties.items() if d.get("type") == "array"]
        if not array_fields:
            # Inject simulated collection if none defined
            array_fields = ["items"]
            base_valid_input["items"] = ["item_1", "item_2"]

        for arr_field in array_fields:
            # Empty collection
            empty_payload = copy.deepcopy(base_valid_input)
            empty_payload[arr_field] = []
            scenarios.append(
                BehavioralScenario.create(
                    consumer_id=consumer_id,
                    contract_id=contract_id,
                    input_payload=empty_payload,
                    expected_behavior={"status_code": 200, "collection_empty": True},
                    mutation={"type": "empty_collection", "field": arr_field},
                    seed=self.seed + len(scenarios),
                    coverage_target=f"empty_collection_{arr_field}",
                    strategy=ExplorationStrategy.BOUNDARY_EXPLORATION,
                )
            )
            # Large collection
            large_payload = copy.deepcopy(base_valid_input)
            large_payload[arr_field] = [f"elem_{i}" for i in range(100)]
            scenarios.append(
                BehavioralScenario.create(
                    consumer_id=consumer_id,
                    contract_id=contract_id,
                    input_payload=large_payload,
                    expected_behavior={"status_code": 200, "collection_large": True},
                    mutation={"type": "large_collection", "field": arr_field, "size": 100},
                    seed=self.seed + len(scenarios),
                    coverage_target=f"large_collection_{arr_field}",
                    strategy=ExplorationStrategy.BOUNDARY_EXPLORATION,
                )
            )

        # 6. NULL VALUES & UNKNOWN VALUES
        for prop in list(properties.keys())[:3]:
            null_payload = copy.deepcopy(base_valid_input)
            null_payload[prop] = None
            scenarios.append(
                BehavioralScenario.create(
                    consumer_id=consumer_id,
                    contract_id=contract_id,
                    input_payload=null_payload,
                    expected_behavior={"status_code": 400 if prop in required else 200},
                    mutation={"type": "null_injection", "field": prop},
                    seed=self.seed + len(scenarios),
                    coverage_target=f"null_value_{prop}",
                    strategy=ExplorationStrategy.SCHEMA_MUTATION,
                )
            )

        unknown_payload = copy.deepcopy(base_valid_input)
        unknown_payload["__unexpected_extra_attribute__"] = "unknown_probe_val"
        scenarios.append(
            BehavioralScenario.create(
                consumer_id=consumer_id,
                contract_id=contract_id,
                input_payload=unknown_payload,
                expected_behavior={"status_code": 200, "unknown_field_tolerated": True},
                mutation={"type": "unknown_field_addition"},
                seed=self.seed + len(scenarios),
                coverage_target="unknown_field",
                strategy=ExplorationStrategy.SCHEMA_MUTATION,
            )
        )

        # 7. ENUM BOUNDARIES & INVALID ENUM
        for prop, pdef in properties.items():
            if "enum" in pdef and pdef["enum"]:
                valid_enums = pdef["enum"]
                for e_val in valid_enums:
                    e_payload = copy.deepcopy(base_valid_input)
                    e_payload[prop] = e_val
                    scenarios.append(
                        BehavioralScenario.create(
                            consumer_id=consumer_id,
                            contract_id=contract_id,
                            input_payload=e_payload,
                            expected_behavior={"status_code": 200, "enum_valid": True},
                            mutation={"type": "enum_valid", "field": prop, "value": e_val},
                            seed=self.seed + len(scenarios),
                            coverage_target=f"enum_{prop}_{e_val}",
                            strategy=ExplorationStrategy.SCHEMA_MUTATION,
                        )
                    )
                # Invalid enum
                inv_payload = copy.deepcopy(base_valid_input)
                inv_payload[prop] = "__INVALID_ENUM_VALUE_OUT_OF_BOUNDS__"
                scenarios.append(
                    BehavioralScenario.create(
                        consumer_id=consumer_id,
                        contract_id=contract_id,
                        input_payload=inv_payload,
                        expected_behavior={"status_code": 400, "error": "INVALID_ENUM"},
                        mutation={"type": "invalid_enum", "field": prop},
                        seed=self.seed + len(scenarios),
                        coverage_target=f"invalid_enum_{prop}",
                        strategy=ExplorationStrategy.SCHEMA_MUTATION,
                    )
                )

        # 8. POLYMORPHIC VARIANTS (Phase 47) & UNKNOWN VARIANT
        variants = polymorphic_variants or ["STANDARD_TIER", "PREMIUM_TIER"]
        for variant in variants:
            var_payload = copy.deepcopy(base_valid_input)
            var_payload["type"] = variant
            var_payload["variant"] = variant
            scenarios.append(
                BehavioralScenario.create(
                    consumer_id=consumer_id,
                    contract_id=contract_id,
                    input_payload=var_payload,
                    expected_behavior={"status_code": 200, "variant_resolved": True},
                    mutation={"type": "polymorphic_variant", "variant": variant},
                    seed=self.seed + len(scenarios),
                    coverage_target=f"variant_{variant}",
                    strategy=ExplorationStrategy.POLYMORPHIC_EXPLORATION,
                )
            )

        if is_open_polymorphic or True:
            unk_var_payload = copy.deepcopy(base_valid_input)
            unk_var_payload["type"] = "FUTURE_EXPERIMENTAL_VARIANT"
            unk_var_payload["variant"] = "FUTURE_EXPERIMENTAL_VARIANT"
            scenarios.append(
                BehavioralScenario.create(
                    consumer_id=consumer_id,
                    contract_id=contract_id,
                    input_payload=unk_var_payload,
                    expected_behavior={
                        "status_code": 200 if is_open_polymorphic else 400,
                        "fallback_used": is_open_polymorphic,
                    },
                    mutation={"type": "unknown_polymorphic_variant"},
                    seed=self.seed + len(scenarios),
                    coverage_target="unknown_variant_fallback",
                    strategy=ExplorationStrategy.POLYMORPHIC_EXPLORATION,
                )
            )

        # 9. RETRY, IDEMPOTENCY & DUPLICATE EVENT
        retry_payload = copy.deepcopy(base_valid_input)
        retry_payload["idempotency_key"] = "idem_key_retry_001"
        scenarios.append(
            BehavioralScenario.create(
                consumer_id=consumer_id,
                contract_id=contract_id,
                input_payload=retry_payload,
                expected_behavior={"status_code": 200, "idempotent": True, "side_effects_deduplicated": True},
                mutation={"type": "retry", "idempotency_key": "idem_key_retry_001"},
                seed=self.seed + len(scenarios),
                coverage_target="retry_idempotency",
                strategy=ExplorationStrategy.RETRY_EXPLORATION,
            )
        )

        dup_payload = copy.deepcopy(base_valid_input)
        dup_payload["event_id"] = "event_dup_999"
        dup_payload["is_duplicate"] = True
        scenarios.append(
            BehavioralScenario.create(
                consumer_id=consumer_id,
                contract_id=contract_id,
                input_payload=dup_payload,
                expected_behavior={"status_code": 200, "duplicate_event_handled": True},
                mutation={"type": "duplicate_event", "event_id": "event_dup_999"},
                seed=self.seed + len(scenarios),
                coverage_target="duplicate_event",
                strategy=ExplorationStrategy.RETRY_EXPLORATION,
            )
        )

        # 10. TIMEOUT & PARTIAL FAILURE
        timeout_payload = copy.deepcopy(base_valid_input)
        timeout_payload["__simulate_timeout__"] = True
        scenarios.append(
            BehavioralScenario.create(
                consumer_id=consumer_id,
                contract_id=contract_id,
                input_payload=timeout_payload,
                expected_behavior={"status_code": 504, "timeout": True, "clean_rollback": True},
                mutation={"type": "timeout"},
                seed=self.seed + len(scenarios),
                coverage_target="timeout_recovery",
                strategy=ExplorationStrategy.ERROR_PATH_EXPLORATION,
            )
        )

        partial_payload = copy.deepcopy(base_valid_input)
        partial_payload["__simulate_partial_failure__"] = True
        scenarios.append(
            BehavioralScenario.create(
                consumer_id=consumer_id,
                contract_id=contract_id,
                input_payload=partial_payload,
                expected_behavior={"status_code": 500, "partial_failure": True, "clean_rollback": True},
                mutation={"type": "partial_failure"},
                seed=self.seed + len(scenarios),
                coverage_target="partial_failure_rollback",
                strategy=ExplorationStrategy.ERROR_PATH_EXPLORATION,
            )
        )

        # 11. AUTHORIZATION FAILURE
        auth_fail_payload = copy.deepcopy(base_valid_input)
        auth_fail_payload["__simulate_auth_failure__"] = True
        scenarios.append(
            BehavioralScenario.create(
                consumer_id=consumer_id,
                contract_id=contract_id,
                input_payload=auth_fail_payload,
                expected_behavior={"status_code": 401, "error": "UNAUTHORIZED"},
                mutation={"type": "auth_failure"},
                seed=self.seed + len(scenarios),
                coverage_target="authorization_failure",
                strategy=ExplorationStrategy.ERROR_PATH_EXPLORATION,
            )
        )

        # 12. HISTORICAL TRACE REPLAY
        if historical_traces:
            for idx, trace in enumerate(historical_traces[:5]):
                t_input = trace.get("input_payload") or base_valid_input
                scenarios.append(
                    BehavioralScenario.create(
                        consumer_id=consumer_id,
                        contract_id=contract_id,
                        input_payload=copy.deepcopy(t_input),
                        expected_behavior={"status_code": trace.get("status_code", 200)},
                        mutation={"type": "trace_replay", "original_trace_id": trace.get("trace_id")},
                        seed=self.seed + len(scenarios),
                        coverage_target=f"trace_replay_{idx}",
                        strategy=ExplorationStrategy.TRACE_REPLAY,
                    )
                )

        # Bounded truncation to respect budget
        return scenarios[:max_scenarios]

    def _generate_canonical_value(self, prop_name: str, pdef: Dict[str, Any]) -> Any:
        """Generate deterministic default canonical value for a schema property."""
        ptype = pdef.get("type", "string")
        if "enum" in pdef and pdef["enum"]:
            return pdef["enum"][0]
        if ptype == "string":
            if "format" in pdef and pdef["format"] == "email":
                return f"user_{prop_name}@jarvis.internal"
            return f"sample_{prop_name}"
        if ptype == "integer":
            return pdef.get("minimum", 1)
        if ptype == "number":
            return float(pdef.get("minimum", 10.0))
        if ptype == "boolean":
            return True
        if ptype == "array":
            return ["item_alpha", "item_beta"]
        if ptype == "object":
            return {"sub_key": "sub_value"}
        return f"val_{prop_name}"
