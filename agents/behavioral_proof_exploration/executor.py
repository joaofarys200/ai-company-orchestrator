"""
JARVIS OS — Phase 51: Behavioral Proof Coverage & Scenario Exploration
Scenario Executor: Deterministic sandbox execution and trace generation.
"""

from __future__ import annotations

import copy
import time
from typing import Any, Callable, Dict, List, Optional

from agents.behavioral_contract_proof.models import (
    BehavioralInvariantType,
    BehavioralStage,
    BehavioralStageExecution,
    LatencyClass,
    RuntimeTrace,
)
from agents.behavioral_contract_proof.trace import compute_trace_hash
from agents.behavioral_proof_exploration.models import (
    BehavioralScenario,
    ScenarioExecutionResult,
)


class ScenarioExecutor:
    """
    Deterministic Sandbox Executor.
    Executes a BehavioralScenario against target simulated endpoints (before & after).
    Computes runtime traces, evaluates status codes, side effects, and detects divergences.
    """

    def __init__(self, environment: str = "sandbox") -> None:
        self.environment = environment

    def execute(
        self,
        scenario: BehavioralScenario,
        before_handler: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        after_handler: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
    ) -> ScenarioExecutionResult:
        """
        Execute a single scenario across before and after handlers.
        """
        start_time = time.perf_counter()

        # Execute Before Handler
        before_trace = self._invoke_handler(
            scenario=scenario,
            handler=before_handler,
            version_label="before",
        )

        # Execute After Handler
        after_trace = self._invoke_handler(
            scenario=scenario,
            handler=after_handler,
            version_label="after",
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        # Check divergence
        is_divergent = False
        divergence_reason: Optional[str] = None
        invariants_violated: List[BehavioralInvariantType] = []

        if before_trace and after_trace:
            # Status code mismatch
            if before_trace.status_code != after_trace.status_code:
                is_divergent = True
                divergence_reason = (
                    f"Status code mismatch: before={before_trace.status_code}, after={after_trace.status_code}"
                )
                invariants_violated.append(BehavioralInvariantType.ERROR_SEMANTICS_PRESERVED)

            # Output mismatch
            elif before_trace.output_payload != after_trace.output_payload:
                is_divergent = True
                divergence_reason = f"Output payload divergence between before and after versions"

            # Economic effect check
            if before_trace.economic_effects != after_trace.economic_effects:
                is_divergent = True
                divergence_reason = "Economic effects mismatch between before and after versions"
                invariants_violated.append(BehavioralInvariantType.ECONOMIC_VALUE_PRESERVED)

            # Side effects order
            if len(before_trace.side_effects) != len(after_trace.side_effects):
                is_divergent = True
                divergence_reason = "Side effects count/order divergence"
                invariants_violated.append(BehavioralInvariantType.SIDE_EFFECT_ORDER_PRESERVED)

        return ScenarioExecutionResult(
            scenario_id=scenario.scenario_id,
            success=not is_divergent,
            before_trace=before_trace,
            after_trace=after_trace,
            is_divergent=is_divergent,
            divergence_reason=divergence_reason,
            invariants_violated=invariants_violated,
            latency_ms=elapsed_ms,
            side_effects_before=before_trace.side_effects if before_trace else [],
            side_effects_after=after_trace.side_effects if after_trace else [],
            metadata={"seed": scenario.seed, "strategy": scenario.strategy.value},
        )

    def _invoke_handler(
        self,
        scenario: BehavioralScenario,
        handler: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]],
        version_label: str,
    ) -> RuntimeTrace:
        """Invoke custom handler or generate simulated response trace."""
        p_input = scenario.input
        t_id = f"trace_{scenario.scenario_id}_{version_label}"

        # Default handler simulation if none provided
        if handler:
            raw_out = handler(p_input)
            status_code = raw_out.get("status_code", 200)
            output_payload = raw_out.get("output", {"success": status_code < 400})
            side_effects = raw_out.get("side_effects", [{"action": "audit_log", "target": "operation"}])
            economic_effects = raw_out.get("economic_effects", [])
            auth_state = raw_out.get("authorization_state", {"role": "caller", "valid": True})
        else:
            # Deterministic standard simulation based on scenario properties
            if p_input.get("__simulate_timeout__"):
                status_code = 504
                output_payload = {"error": "GATEWAY_TIMEOUT", "success": False}
                side_effects = [{"action": "timeout_logged"}]
                economic_effects = []
                auth_state = {"authenticated": True}
            elif p_input.get("__simulate_auth_failure__"):
                status_code = 401
                output_payload = {"error": "UNAUTHORIZED", "success": False}
                side_effects = []
                economic_effects = []
                auth_state = {"authenticated": False}
            elif p_input.get("__simulate_partial_failure__"):
                status_code = 500
                output_payload = {"error": "INTERNAL_SERVER_ERROR", "success": False}
                side_effects = [{"action": "rollback_triggered"}]
                economic_effects = []
                auth_state = {"authenticated": True}
            elif any(k in scenario.mutation.get("type", "") for k in ("missing_field", "invalid_enum") if scenario.mutation):
                status_code = 400
                output_payload = {"error": "BAD_REQUEST", "details": scenario.mutation}
                side_effects = []
                economic_effects = []
                auth_state = {"authenticated": True}
            else:
                status_code = 200
                output_payload = {
                    "id": p_input.get("id", "res_01"),
                    "status": "processed",
                    "echo": {k: v for k, v in p_input.items() if not k.startswith("__")},
                }
                side_effects = [{"action": "write_record", "record_id": p_input.get("id", "res_01")}]
                economic_effects = [{"amount": p_input.get("amount", 0.0), "currency": p_input.get("currency", "USD")}] if "amount" in p_input else []
                auth_state = {"authenticated": True, "scope": "standard"}

        stages = [
            BehavioralStageExecution(stage=BehavioralStage.REQUEST, started_at=100.0, duration_ms=1.0, success=True),
            BehavioralStageExecution(stage=BehavioralStage.AUTH, started_at=101.0, duration_ms=1.0, success=status_code != 401),
            BehavioralStageExecution(stage=BehavioralStage.VALIDATION, started_at=102.0, duration_ms=1.0, success=status_code != 400),
            BehavioralStageExecution(stage=BehavioralStage.BUSINESS_LOGIC, started_at=103.0, duration_ms=2.0, success=status_code < 500),
            BehavioralStageExecution(stage=BehavioralStage.RESPONSE, started_at=105.0, duration_ms=1.0, success=True),
        ]

        trace = RuntimeTrace(
            trace_id=t_id,
            source="behavioral_exploration",
            timestamp=100.0,  # deterministic timestamp
            mission_id="msn_exploration_phase51",
            consumer_id=scenario.consumer_id,
            contract_id=scenario.contract_id,
            operation="explore_operation",
            input_payload=p_input,
            output_payload=output_payload,
            status_code=status_code,
            stages=stages,
            side_effects=side_effects,
            events=[{"event_name": "ScenarioExecuted", "scenario_id": scenario.scenario_id}],
            economic_effects=economic_effects,
            authorization_state=auth_state,
            environment=self.environment,
            build_hash="build_hash_fixed_deterministic",
        )
        trace.trace_hash = compute_trace_hash(trace)
        return trace
