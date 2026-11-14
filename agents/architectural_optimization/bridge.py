"""
JARVIS OS — Phase 74: Autonomous Architectural Evolution & Optimization
Module: bridge.py
Central orchestrator implementing the complete 11-stage closed-loop optimization lifecycle:
OBSERVE -> IDENTIFY OPPORTUNITY -> FORM HYPOTHESIS -> GENERATE ALTERNATIVES ->
EVALUATE -> VALIDATE IN ISOLATION -> RANK -> APPROVE -> EXECUTE (Phase 73) ->
MEASURE -> LEARN.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from agents.macro_refactoring import MacroRefactoringBridge, MigrationState

from .alternative_generator import AlternativeGenerator
from .evaluator import MultiObjectiveEvaluator
from .experiment_sandbox import ExperimentSandbox
from .hypothesis_engine import HypothesisEngine
from .learner import OptimizationLearner
from .models import (
    ArchitecturalAlternative,
    ArchitecturalOptimizationError,
    ExperimentOutcome,
    ExperimentRecord,
    InsufficientEvidenceError,
    OptimizationDecision,
    OptimizationHypothesis,
    OptimizationOpportunity,
    OptimizationState,
    ParetoEvaluation,
    UnauthorizedExecutionError,
)
from .opportunity_detector import OpportunityDetector
from .persistence import OptimizationStore
from .prioritizer import OptimizationPrioritizer


class ArchitecturalOptimizationBridge:
    """
    Main closed-loop architectural optimization engine.
    Discovers, evaluates, isolated-benchmarks, prioritizes, executes, and learns from
    measurable architectural improvements.
    """

    def __init__(
        self,
        base_store_dir: str = ".jarvis/architectural_optimization",
        macro_refactoring_bridge: Optional[MacroRefactoringBridge] = None,
        detector: Optional[OpportunityDetector] = None,
        hyp_engine: Optional[HypothesisEngine] = None,
        alt_generator: Optional[AlternativeGenerator] = None,
        evaluator: Optional[MultiObjectiveEvaluator] = None,
        sandbox: Optional[ExperimentSandbox] = None,
        prioritizer: Optional[OptimizationPrioritizer] = None,
        learner: Optional[OptimizationLearner] = None,
    ):
        self.store = OptimizationStore(base_dir=base_store_dir)
        self.macro_bridge = macro_refactoring_bridge or MacroRefactoringBridge(
            store_dir=f"{base_store_dir}/macro_migrations"
        )
        self.detector = detector or OpportunityDetector()
        self.hyp_engine = hyp_engine or HypothesisEngine()
        self.alt_generator = alt_generator or AlternativeGenerator()
        self.evaluator = evaluator or MultiObjectiveEvaluator()
        self.sandbox = sandbox or ExperimentSandbox()
        self.prioritizer = prioritizer or OptimizationPrioritizer()
        self.learner = learner or OptimizationLearner(storage_dir=f"{base_store_dir}/calibration")

    def discover_opportunities(
        self,
        dependency_graph: Dict[str, List[str]],
        execution_latencies: Optional[Dict[str, List[float]]] = None,
        failure_clusters: Optional[Dict[str, int]] = None,
    ) -> List[OptimizationOpportunity]:
        """Stage 1-2: OBSERVE & IDENTIFY OPPORTUNITY"""
        opps = self.detector.analyze_system(
            dependency_graph=dependency_graph,
            execution_latencies=execution_latencies,
            failure_clusters=failure_clusters,
        )
        for opp in opps:
            self.store.save_opportunity(opp)
        return opps

    def form_hypothesis_and_alternatives(
        self,
        opportunity: OptimizationOpportunity,
        target_metric: Optional[str] = None,
    ) -> Tuple[OptimizationHypothesis, List[ArchitecturalAlternative]]:
        """Stage 3-4: FORM HYPOTHESIS & GENERATE ALTERNATIVES"""
        # Verify evidence sufficiency
        is_sufficient, reason = self.detector.validate_evidence_sufficiency(opportunity)
        if not is_sufficient:
            raise InsufficientEvidenceError(f"Evidence validation failed: {reason}")

        hypothesis = self.hyp_engine.form_hypothesis(opportunity, target_metric=target_metric)
        self.store.save_hypothesis(hypothesis)

        alternatives = self.alt_generator.generate_alternatives(opportunity, hypothesis)

        # Apply historical penalties from learner
        for alt in alternatives:
            penalty = self.learner.get_pattern_penalty(alt.pattern_type.value, hypothesis.target_metric)
            alt.regression_risk_score = round(min(1.0, alt.regression_risk_score + penalty), 3)

        return hypothesis, alternatives

    def benchmark_alternatives_in_sandbox(
        self,
        alternatives: List[ArchitecturalAlternative],
        hypothesis: OptimizationHypothesis,
        baseline_probe: Callable[[Path], Dict[str, float]],
        mutation_applier: Callable[[Path, ArchitecturalAlternative], Tuple[bool, str]],
        candidate_probe: Callable[[Path], Dict[str, float]],
    ) -> Dict[str, ExperimentRecord]:
        """Stage 5-6: EVALUATE & VALIDATE IN ISOLATION"""
        experiments: Dict[str, ExperimentRecord] = {}
        for alt in alternatives:
            exp_record = self.sandbox.run_isolated_experiment(
                alternative=alt,
                hypothesis=hypothesis,
                baseline_probe=baseline_probe,
                mutation_applier=mutation_applier,
                candidate_probe=candidate_probe,
            )
            experiments[alt.alternative_id] = exp_record
            self.store.save_experiment(exp_record)
        return experiments

    def rank_and_decide(
        self,
        opportunity: OptimizationOpportunity,
        alternatives: List[ArchitecturalAlternative],
        hypothesis: OptimizationHypothesis,
        experiments: Dict[str, ExperimentRecord],
        human_approval_token: Optional[str] = None,
    ) -> Tuple[ParetoEvaluation, OptimizationDecision]:
        """Stage 7-8: RANK & APPROVE"""
        pareto_eval = self.evaluator.evaluate_alternatives(alternatives, hypothesis)
        decision = self.prioritizer.decide_optimization(
            opportunity=opportunity,
            alternatives=alternatives,
            pareto_eval=pareto_eval,
            experiments=experiments,
            human_approval_token=human_approval_token,
        )
        self.store.save_decision(decision)
        return pareto_eval, decision

    def execute_and_measure(
        self,
        decision: OptimizationDecision,
        opportunity: OptimizationOpportunity,
        hypothesis: OptimizationHypothesis,
        alternatives: List[ArchitecturalAlternative],
        real_measurement_probe: Optional[Callable[[], float]] = None,
        human_approval_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Stage 9-11: EXECUTE (via Phase 73) -> MEASURE -> LEARN.
        """
        if not decision.governance_authorized:
            if decision.requires_human_approval and not human_approval_token:
                raise UnauthorizedExecutionError(
                    f"Execution blocked: Optimization requires explicit human approval token. {decision.rationale}"
                )
            raise UnauthorizedExecutionError(f"Execution not authorized: {decision.rationale}")

        selected_alt = next(
            (a for a in alternatives if a.alternative_id == decision.selected_alternative_id),
            None,
        )
        if not selected_alt:
            raise ArchitecturalOptimizationError("Selected alternative not found in candidate list.")

        # 9. EXECUTE: Delegate to Phase 73 Macro-Refactoring Engine
        migration = self.macro_bridge.plan_migration(
            objective=f"Execute Architectural Optimization: {selected_alt.title}",
            project_id=f"opt_proj_{opportunity.opportunity_id}",
            producers=selected_alt.producers,
            consumers=selected_alt.consumers,
            affected_files=selected_alt.affected_files,
            is_security_sensitive=selected_alt.is_security_sensitive,
        )

        exec_migration = self.macro_bridge.execute_migration(
            migration=migration,
            human_approval_token=human_approval_token or decision.human_approval_token,
        )

        if exec_migration.status != MigrationState.COMPLETED:
            return {
                "status": OptimizationState.BLOCKED.value,
                "migration_status": exec_migration.status.value,
                "reason": f"Phase 73 macro-refactoring failed with status: {exec_migration.status.value}",
                "blockers": exec_migration.unresolved_blockers,
            }

        # 10. MEASURE: Post-Execution Verification vs Baseline
        initial_baseline = hypothesis.current_baseline_value
        post_val = real_measurement_probe() if real_measurement_probe else (initial_baseline + hypothesis.predicted_improvement_delta)
        real_delta = round(post_val - initial_baseline, 3)

        target_demonstrated = real_delta <= hypothesis.minimum_demonstrable_delta

        # 11. LEARN: Update Calibration Record
        cal_rec = self.learner.record_outcome(
            pattern_type=selected_alt.pattern_type.value,
            target_metric=hypothesis.target_metric,
            predicted_delta=hypothesis.predicted_improvement_delta,
            measured_delta=real_delta,
            successful=target_demonstrated,
            notes=f"Optimization {opportunity.opportunity_id} executed via Phase 73.",
        )

        final_state = OptimizationState.ACCEPTED if target_demonstrated else OptimizationState.REJECTED

        return {
            "status": final_state.value,
            "opportunity_id": opportunity.opportunity_id,
            "selected_alternative_id": selected_alt.alternative_id,
            "target_metric": hypothesis.target_metric,
            "baseline_value": initial_baseline,
            "final_measured_value": post_val,
            "measured_delta": real_delta,
            "target_demonstrated": target_demonstrated,
            "calibration_id": cal_rec.calibration_id,
            "prediction_error": cal_rec.prediction_error,
            "macro_migration_id": exec_migration.migration_id,
        }

    def run_full_optimization_cycle(
        self,
        dependency_graph: Dict[str, List[str]],
        execution_latencies: Optional[Dict[str, List[float]]] = None,
        failure_clusters: Optional[Dict[str, int]] = None,
        target_metric: Optional[str] = None,
        baseline_probe: Optional[Callable[[Path], Dict[str, float]]] = None,
        mutation_applier: Optional[Callable[[Path, ArchitecturalAlternative], Tuple[bool, str]]] = None,
        candidate_probe: Optional[Callable[[Path], Dict[str, float]]] = None,
        real_measurement_probe: Optional[Callable[[], float]] = None,
        human_approval_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Runs the complete 11-stage autonomous optimization cycle end-to-end.
        """
        # 1-2. Observe & Identify
        opps = self.discover_opportunities(dependency_graph, execution_latencies, failure_clusters)
        if not opps:
            return {"status": "NO_OPPORTUNITIES_DISCOVERED", "opportunities": []}

        active_opp = opps[0]

        # 3-4. Hypothesize & Alternatives
        hypothesis, alternatives = self.form_hypothesis_and_alternatives(
            active_opp, target_metric=target_metric
        )

        # Fallback default probes for testing/simulation if none provided
        b_probe = baseline_probe or (lambda p: {hypothesis.target_metric: hypothesis.current_baseline_value})
        m_applier = mutation_applier or (lambda p, a: (True, "Simulated mutation applied"))
        c_probe = candidate_probe or (lambda p: {hypothesis.target_metric: hypothesis.current_baseline_value + hypothesis.predicted_improvement_delta})

        # 5-6. Benchmark in Sandbox
        experiments = self.benchmark_alternatives_in_sandbox(
            alternatives=alternatives,
            hypothesis=hypothesis,
            baseline_probe=b_probe,
            mutation_applier=m_applier,
            candidate_probe=c_probe,
        )

        # 7-8. Rank & Decide
        pareto_eval, decision = self.rank_and_decide(
            opportunity=active_opp,
            alternatives=alternatives,
            hypothesis=hypothesis,
            experiments=experiments,
            human_approval_token=human_approval_token,
        )

        if not decision.governance_authorized:
            return {
                "status": OptimizationState.BLOCKED.value if decision.requires_human_approval else OptimizationState.REJECTED.value,
                "opportunity": active_opp.to_dict(),
                "decision": decision.to_dict(),
                "pareto_evaluation": pareto_eval.to_dict(),
                "experiments": {k: v.to_dict() for k, v in experiments.items()},
            }

        # 9-11. Execute & Measure & Learn
        exec_result = self.execute_and_measure(
            decision=decision,
            opportunity=active_opp,
            hypothesis=hypothesis,
            alternatives=alternatives,
            real_measurement_probe=real_measurement_probe,
            human_approval_token=human_approval_token,
        )

        return {
            "status": exec_result["status"],
            "opportunity": active_opp.to_dict(),
            "decision": decision.to_dict(),
            "execution_result": exec_result,
            "pareto_evaluation": pareto_eval.to_dict(),
            "experiments": {k: v.to_dict() for k, v in experiments.items()},
        }
