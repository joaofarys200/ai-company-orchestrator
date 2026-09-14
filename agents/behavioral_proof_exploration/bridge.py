"""
JARVIS OS — Phase 51: Behavioral Proof Coverage & Scenario Exploration
Behavioral Proof Exploration Bridge: High-Level Orchestrator for Bounded Exploration.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from agents.behavioral_contract_proof.models import (
    BehaviorBaseline,
    Counterexample,
    ExecutionGateDecision,
    ProofResult,
    RuntimeTrace,
)
from agents.behavioral_proof_exploration.budget import ExplorationBudgetController
from agents.behavioral_proof_exploration.comparator import ExplorationComparator
from agents.behavioral_proof_exploration.counterexample import (
    ExplorationCounterexampleManager,
)
from agents.behavioral_proof_exploration.coverage import BehavioralCoverageEngine
from agents.behavioral_proof_exploration.executor import ScenarioExecutor
from agents.behavioral_proof_exploration.generator import ScenarioGenerator
from agents.behavioral_proof_exploration.index import ExplorationIndex
from agents.behavioral_proof_exploration.invariants import ExplorationInvariantEngine
from agents.behavioral_proof_exploration.metrics import ExplorationTelemetry
from agents.behavioral_proof_exploration.models import (
    BehavioralCoverage,
    BehavioralScenario,
    BoundedExplorationProof,
    CoverageThresholdPolicy,
    ExplorationBudget,
    ExplorationStrategy,
    ProofScope,
    ScenarioExecutionResult,
    ShrunkCounterexample,
    compute_deterministic_id,
)
from agents.behavioral_proof_exploration.mutator import ScenarioMutator
from agents.behavioral_proof_exploration.scheduler import ScenarioScheduler
from agents.behavioral_proof_exploration.security import ExplorationSecuritySentinel
from agents.behavioral_proof_exploration.shrinker import CounterexampleShrinker
from agents.behavioral_proof_exploration.trace import ExplorationTraceAdapter
from agents.behavioral_proof_exploration.validator import ExplorationValidator


class BehavioralProofExplorationBridge:
    """
    Central Orchestrator for Phase 51:
    Implements the 17-stage workflow:
    CONTRACT CHANGE -> STATIC IMPACT -> BEHAVIOR BASELINE -> SCENARIO GENERATION ->
    SCENARIO EXECUTION -> TRACE NORMALIZATION -> BEHAVIOR COMPARISON -> INVARIANT CHECK ->
    COUNTEREXAMPLE SEARCH -> COVERAGE EVALUATION -> PROOF DECISION -> MISSION GATE ->
    EXECUTION -> POST-CHANGE EXPLORATION -> FINAL PROOF -> FINISH GATE.
    """

    def __init__(
        self,
        telemetry: Optional[ExplorationTelemetry] = None,
        index: Optional[ExplorationIndex] = None,
    ) -> None:
        self.telemetry = telemetry or ExplorationTelemetry()
        self.index = index or ExplorationIndex()
        self.generator = ScenarioGenerator()
        self.mutator = ScenarioMutator()
        self.executor = ScenarioExecutor()
        self.scheduler = ScenarioScheduler(self.executor)
        self.trace_adapter = ExplorationTraceAdapter()
        self.comparator = ExplorationComparator()
        self.invariant_engine = ExplorationInvariantEngine()
        self.counterexample_manager = ExplorationCounterexampleManager()
        self.shrinker = CounterexampleShrinker()
        self.coverage_engine = BehavioralCoverageEngine()
        self.validator = ExplorationValidator()
        self.security_sentinel = ExplorationSecuritySentinel()

    def run_exploration_proof(
        self,
        migration_id: str,
        contract_id: str,
        before_version: str,
        after_version: str,
        schema: Dict[str, Any],
        known_consumers: List[str],
        baseline: Optional[BehaviorBaseline] = None,
        historical_traces: Optional[List[Dict[str, Any]]] = None,
        budget: Optional[ExplorationBudget] = None,
        coverage_policy: CoverageThresholdPolicy = CoverageThresholdPolicy.STANDARD,
        seed: int = 42,
        is_economic: bool = False,
        polymorphic_variants: Optional[List[str]] = None,
        is_open_polymorphic: bool = False,
        dynamic_consumer_uncertainties: Optional[List[str]] = None,
        before_handler: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        after_handler: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
    ) -> BoundedExplorationProof:
        """
        Execute bounded behavioral exploration and synthesize the cryptographic proof certificate.
        """
        effective_budget = budget or ExplorationBudget()
        scope_id = compute_deterministic_id({
            "migration_id": migration_id,
            "contract_id": contract_id,
            "budget": effective_budget.to_dict(),
            "policy": coverage_policy.value,
            "seed": seed,
        }, prefix="scp_")

        scope = ProofScope(
            scope_id=scope_id,
            contract_id=contract_id,
            before_version=before_version,
            after_version=after_version,
            budget=effective_budget,
            strategies=[
                ExplorationStrategy.SCHEMA_MUTATION,
                ExplorationStrategy.BOUNDARY_EXPLORATION,
                ExplorationStrategy.POLYMORPHIC_EXPLORATION,
                ExplorationStrategy.ERROR_PATH_EXPLORATION,
                ExplorationStrategy.RETRY_EXPLORATION,
            ],
            seed=seed,
            environment="sandbox",
            max_interleavings=effective_budget.max_concurrency_variants,
            coverage_threshold_policy=coverage_policy,
            provenance={"mission_id": migration_id, "seed": seed},
        )
        self.index.register_scope(scope)

        # 1. SCENARIO GENERATION
        self.telemetry.emit_event("scenario_generation_started", migration_id=migration_id, contract_id=contract_id, seed=seed)
        scenarios: List[BehavioralScenario] = []
        for consumer in (known_consumers or ["default_consumer"]):
            scenarios.extend(
                self.generator.generate_scenarios_for_contract(
                    contract_id=contract_id,
                    consumer_id=consumer,
                    schema=schema,
                    baseline=baseline.to_dict() if baseline else None,
                    historical_traces=historical_traces,
                    budget=effective_budget,
                    polymorphic_variants=polymorphic_variants,
                    is_open_polymorphic=is_open_polymorphic,
                )
            )

        # Security Inspection on all generated scenarios
        for scen in scenarios:
            self.security_sentinel.inspect_scenario(scen)
            self.index.register_scenario(scen)

        self.telemetry.emit_event(
            "scenario_generated",
            migration_id=migration_id,
            contract_id=contract_id,
            seed=seed,
            details={"scenarios_count": len(scenarios)},
        )

        # 2. SCENARIO EXECUTION & SCHEDULING (Bounded)
        self.telemetry.emit_event("scenario_started", migration_id=migration_id, contract_id=contract_id)
        exec_results, unexplored_interleavings = self.scheduler.run_bounded_exploration(
            scope=scope,
            scenarios=scenarios,
            before_handler=before_handler,
            after_handler=after_handler,
        )

        # 3. COMPARISON, INVARIANTS, & COUNTEREXAMPLE SEARCH
        counterexamples: List[Counterexample] = []
        shrunk_counterexamples: List[ShrunkCounterexample] = []
        all_invariants_violated = set()

        for idx, res in enumerate(exec_results):
            scen = scenarios[idx] if idx < len(scenarios) else scenarios[0]
            if res.is_divergent or res.invariants_violated:
                all_invariants_violated.update(res.invariants_violated)
                diff_desc = res.divergence_reason or "Behavioral divergence between before and after"

                # Create raw counterexample
                cx = self.counterexample_manager.create_counterexample(
                    scenario=scen,
                    before_trace=res.before_trace,
                    after_trace=res.after_trace,
                    difference=diff_desc,
                    scope_id=scope_id,
                )
                counterexamples.append(cx)
                self.telemetry.emit_event(
                    "counterexample_found",
                    migration_id=migration_id,
                    scenario_id=scen.scenario_id,
                    contract_id=contract_id,
                    details={"diff": diff_desc},
                )

                # Shrink counterexample (Delta Debugging)
                def make_checker(target_scen: BehavioralScenario):
                    def checker(payload: Dict[str, Any]) -> bool:
                        test_scen = BehavioralScenario.create(
                            consumer_id=target_scen.consumer_id,
                            contract_id=target_scen.contract_id,
                            input_payload=payload,
                            expected_behavior=target_scen.expected_behavior,
                            seed=target_scen.seed,
                            strategy=target_scen.strategy,
                        )
                        test_res = self.executor.execute(
                            test_scen,
                            before_handler=before_handler,
                            after_handler=after_handler,
                        )
                        return test_res.is_divergent or len(test_res.invariants_violated) > 0
                    return checker

                shrunk = self.shrinker.shrink(
                    scenario=scen,
                    divergence_checker=make_checker(scen),
                    proof_scope_id=scope_id,
                    difference=diff_desc,
                    trace_id=res.after_trace.trace_id if res.after_trace else "tr_shrunk",
                )
                # Verify shrunk counterexample security
                self.security_sentinel.inspect_tampered_counterexample(shrunk.minimal_input, shrunk.original_input)
                self.counterexample_manager.register_shrunk_counterexample(shrunk)
                self.index.register_shrunk_counterexample(shrunk)
                shrunk_counterexamples.append(shrunk)

                self.telemetry.emit_event(
                    "counterexample_shrunk",
                    migration_id=migration_id,
                    scenario_id=scen.scenario_id,
                    details={
                        "original_fields": shrunk.original_field_count,
                        "minimal_fields": shrunk.minimal_field_count,
                        "shrink_steps": shrunk.shrink_steps,
                    },
                )

        # 4. COVERAGE EVALUATION
        coverage = self.coverage_engine.evaluate_coverage(
            scope_id=scope_id,
            scenarios=scenarios,
            execution_results=exec_results,
            schema=schema,
            known_consumers=known_consumers,
            known_variants=polymorphic_variants,
            policy=coverage_policy,
            is_economic_operation=is_economic,
        )
        # Security Sentinel inspection against coverage spoofing
        self.security_sentinel.inspect_coverage(coverage, scenarios)
        self.index.register_coverage(coverage)

        self.telemetry.emit_event(
            "coverage_updated",
            migration_id=migration_id,
            contract_id=contract_id,
            coverage=coverage.to_dict(),
            details={"threshold_met": coverage.threshold_met},
        )

        # 5. PROOF DECISION & MISSION GATE
        proof_result, gate_decision, decision_reasons = self.validator.evaluate_proof_result(
            scope=scope,
            coverage=coverage,
            counterexamples=counterexamples,
            invariants_violated=list(all_invariants_violated),
            consumer_uncertainties=dynamic_consumer_uncertainties,
            is_economic_operation=is_economic,
        )

        proof_id = compute_deterministic_id({
            "migration_id": migration_id,
            "scope_id": scope_id,
            "result": proof_result.value,
            "gate": gate_decision.value,
        }, prefix="prf_")

        proof = BoundedExplorationProof(
            proof_id=proof_id,
            migration_id=migration_id,
            scope=scope,
            coverage=coverage,
            result=proof_result,
            counterexamples=counterexamples,
            shrunk_counterexamples=shrunk_counterexamples,
            invariants_checked=scope.invariants,
            invariants_preserved=len(all_invariants_violated) == 0,
            unexplored_interleavings=unexplored_interleavings,
            consumer_uncertainties=dynamic_consumer_uncertainties or [],
            confidence=1.0 if proof_result == ProofResult.PROVEN_COMPATIBLE_WITHIN_SCOPE else 0.85,
            gate_decision=gate_decision,
            provenance={"reasons": decision_reasons, "mission_id": migration_id},
            timestamp=100.0,
        )
        proof.proof_hash = proof.compute_hash()
        self.index.register_proof(proof)

        evt_name = "proof_cleared" if gate_decision == ExecutionGateDecision.GATE_CLEARED else "proof_blocked"
        self.telemetry.emit_event(
            evt_name,
            mission_id=migration_id,
            contract_id=contract_id,
            decision=gate_decision.value,
            details={"result": proof_result.value, "reasons": decision_reasons},
        )

        return proof
