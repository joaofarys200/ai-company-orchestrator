"""
JARVIS OS — Phase 74: Autonomous Architectural Evolution & Optimization
Deterministic Test Suite covering all 20 required scenarios from Section 9.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path
import pytest

from backend.agents.architectural_optimization import (
    AlternativeGenerator,
    ArchitecturalAlternative,
    ArchitecturalMetricSnapshot,
    ArchitecturalOptimizationBridge,
    ExperimentContaminationError,
    ExperimentOutcome,
    ExperimentRecord,
    ExperimentSandbox,
    HypothesisEngine,
    InsufficientEvidenceError,
    MultiObjectiveEvaluator,
    OpportunityCategory,
    OpportunityDetector,
    OptimizationDecision,
    OptimizationHypothesis,
    OptimizationLearner,
    OptimizationOpportunity,
    OptimizationPrioritizer,
    OptimizationState,
    OptimizationStore,
    StructuralPatternType,
    UnauthorizedExecutionError,
)
from backend.agents.macro_refactoring import MacroRefactoringBridge, MigrationState


class TestArchitecturalOptimizationEngine:

    @pytest.fixture(autouse=True)
    def setup_temp_env(self):
        self.temp_dir = tempfile.mkdtemp(prefix="jarvis_phase74_test_")
        self.bridge = ArchitecturalOptimizationBridge(base_store_dir=self.temp_dir)
        yield
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Scenario 1: Discovering a genuine architectural optimization opportunity
    # -------------------------------------------------------------------------
    def test_01_discovering_genuine_architectural_opportunity(self):
        dep_graph = {
            "core.router": [f"service_{i}" for i in range(10)],  # fan-in = 10
            "util.helpers": ["core.router"],
        }
        latencies = {
            "core.router": [110.0, 130.0, 125.0, 115.0],
        }
        opps = self.bridge.discover_opportunities(dep_graph, latencies)
        assert len(opps) >= 1
        opp = opps[0]
        assert opp.category == OpportunityCategory.DEPENDENCY_CONCENTRATION
        assert "core.router" in opp.affected_components
        assert "coupling_ratio" in opp.baseline_metrics
        assert opp.confidence_score >= 0.8
        assert len(opp.supporting_evidence) >= 2

    # -------------------------------------------------------------------------
    # Scenario 2: Rejecting an opportunity unsupported by sufficient evidence
    # -------------------------------------------------------------------------
    def test_02_rejecting_opportunity_unsupported_by_sufficient_evidence(self):
        detector = OpportunityDetector(min_sample_count=5, min_confidence=0.7)
        flimsy_opp = OptimizationOpportunity(
            opportunity_id="opp_flimsy",
            title="Unsubstantiated opportunity",
            category=OpportunityCategory.EXCESSIVE_COUPLING,
            affected_components=["module_a"],
            supporting_evidence=["Single anecdotal observation"],
            baseline_metrics={
                "latency_ms": ArchitecturalMetricSnapshot(
                    metric_name="latency_ms", value=150.0, sample_count=1
                )
            },
            confidence_score=0.4,  # below 0.7
        )
        is_ok, reason = detector.validate_evidence_sufficiency(flimsy_opp)
        assert not is_ok
        assert "confidence" in reason.lower()

        # Attempting hypothesis formation must raise InsufficientEvidenceError
        with pytest.raises(InsufficientEvidenceError):
            self.bridge.form_hypothesis_and_alternatives(flimsy_opp)

    # -------------------------------------------------------------------------
    # Scenario 3: Generating alternatives for a supported optimization hypothesis
    # -------------------------------------------------------------------------
    def test_03_generating_alternatives_for_supported_hypothesis(self):
        opp = OptimizationOpportunity(
            opportunity_id="opp_valid",
            title="Coupling bottleneck",
            category=OpportunityCategory.DEPENDENCY_CONCENTRATION,
            affected_components=["core.dispatch", "worker.a", "worker.b"],
            supporting_evidence=["Fan-in: 8", "Samples: 10"],
            baseline_metrics={
                "execution_latency_ms": ArchitecturalMetricSnapshot(
                    metric_name="execution_latency_ms", value=80.0, sample_count=10
                )
            },
            confidence_score=0.85,
        )
        hyp, alts = self.bridge.form_hypothesis_and_alternatives(opp)
        assert hyp.status == OptimizationState.HYPOTHESIZED
        assert hyp.target_metric == "execution_latency_ms"
        assert len(alts) >= 3

        pattern_types = {alt.pattern_type for alt in alts}
        assert StructuralPatternType.INTERFACE_INVERSION in pattern_types
        assert StructuralPatternType.FACADE_SHIM in pattern_types
        assert StructuralPatternType.EVENT_DRIVEN_DECOUPLING in pattern_types

    # -------------------------------------------------------------------------
    # Scenario 4: Deterministic ranking for identical inputs
    # -------------------------------------------------------------------------
    def test_04_deterministic_ranking_for_identical_inputs(self):
        hyp = OptimizationHypothesis(
            hypothesis_id="hyp_det",
            opportunity_id="opp_det",
            target_metric="latency_ms",
            current_baseline_value=100.0,
            predicted_improvement_delta=-25.0,
            minimum_demonstrable_delta=-5.0,
            falsification_conditions=[],
        )
        alt_gen = AlternativeGenerator()
        opp = OptimizationOpportunity(
            opportunity_id="opp_det",
            title="Deterministic test",
            category=OpportunityCategory.DEPENDENCY_CONCENTRATION,
            affected_components=["service.a", "client.b"],
            supporting_evidence=[],
            baseline_metrics={},
        )
        alts = alt_gen.generate_alternatives(opp, hyp)
        evaluator = MultiObjectiveEvaluator()

        res1 = evaluator.evaluate_alternatives(alts, hyp)
        res2 = evaluator.evaluate_alternatives(alts, hyp)

        assert res1.ranked_alternatives == res2.ranked_alternatives
        assert res1.pareto_frontier == res2.pareto_frontier

    # -------------------------------------------------------------------------
    # Scenario 5: Preserving trade-offs between competing objectives
    # -------------------------------------------------------------------------
    def test_05_preserving_trade_offs_between_competing_objectives(self):
        hyp = OptimizationHypothesis(
            hypothesis_id="hyp_tradeoff",
            opportunity_id="opp_tradeoff",
            target_metric="latency_ms",
            current_baseline_value=100.0,
            predicted_improvement_delta=-30.0,
            minimum_demonstrable_delta=-5.0,
            falsification_conditions=[],
        )
        # Alt A: High improvement (-40ms), High Cost (50)
        alt_a = ArchitecturalAlternative(
            alternative_id="alt_high_gain_high_cost",
            pattern_type=StructuralPatternType.EVENT_DRIVEN_DECOUPLING,
            title="High Gain High Cost",
            description="",
            producers=["p"],
            consumers=["c"],
            affected_files=["p", "c"],
            predicted_metric_deltas={"latency_ms": -40.0},
            estimated_implementation_cost=50.0,
            regression_risk_score=0.2,
        )
        # Alt B: Modest improvement (-15ms), Very Low Cost (10)
        alt_b = ArchitecturalAlternative(
            alternative_id="alt_low_gain_low_cost",
            pattern_type=StructuralPatternType.FACADE_SHIM,
            title="Low Gain Low Cost",
            description="",
            producers=["p"],
            consumers=["c"],
            affected_files=["p"],
            predicted_metric_deltas={"latency_ms": -15.0},
            estimated_implementation_cost=10.0,
            regression_risk_score=0.05,
        )

        evaluator = MultiObjectiveEvaluator()
        pareto_res = evaluator.evaluate_alternatives([alt_a, alt_b], hyp)

        # Neither dominates the other; both must be in the Pareto frontier
        assert "alt_high_gain_high_cost" in pareto_res.pareto_frontier
        assert "alt_low_gain_low_cost" in pareto_res.pareto_frontier

    # -------------------------------------------------------------------------
    # Scenario 6: Enforcing hard security and compatibility constraints
    # -------------------------------------------------------------------------
    def test_06_enforcing_hard_security_and_compatibility_constraints(self):
        hyp = OptimizationHypothesis(
            hypothesis_id="hyp_hard",
            opportunity_id="opp_hard",
            target_metric="latency_ms",
            current_baseline_value=100.0,
            predicted_improvement_delta=-20.0,
            minimum_demonstrable_delta=-5.0,
            falsification_conditions=[],
        )
        # Irreversible candidate
        alt_irreversible = ArchitecturalAlternative(
            alternative_id="alt_irreversible",
            pattern_type=StructuralPatternType.DIRECT_SIMPLIFICATION,
            title="Irreversible DB schema purge",
            description="",
            producers=["p"],
            consumers=["c"],
            affected_files=["p"],
            predicted_metric_deltas={"latency_ms": -50.0},
            reversibility=False,  # VIOLATES HARD CONSTRAINT
        )
        # High-risk candidate exceeding ceiling
        alt_excessive_risk = ArchitecturalAlternative(
            alternative_id="alt_risky",
            pattern_type=StructuralPatternType.EVENT_DRIVEN_DECOUPLING,
            title="Uncontrolled concurrency",
            description="",
            producers=["p"],
            consumers=["c"],
            affected_files=["p"],
            predicted_metric_deltas={"latency_ms": -50.0},
            regression_risk_score=0.9,  # VIOLATES HARD CONSTRAINT
        )

        evaluator = MultiObjectiveEvaluator(max_acceptable_risk=0.5)
        res = evaluator.evaluate_alternatives([alt_irreversible, alt_excessive_risk], hyp)

        assert "alt_irreversible" in res.hard_constraint_rejections
        assert "alt_risky" in res.hard_constraint_rejections
        assert len(res.ranked_alternatives) == 0

    # -------------------------------------------------------------------------
    # Scenario 7: Detecting stale or invalidated architectural evidence
    # -------------------------------------------------------------------------
    def test_07_detecting_stale_or_invalidated_architectural_evidence(self):
        detector = OpportunityDetector(min_sample_count=3)
        stale_opp = OptimizationOpportunity(
            opportunity_id="opp_stale",
            title="Stale evidence test",
            category=OpportunityCategory.DEPENDENCY_CONCENTRATION,
            affected_components=["comp_x"],
            supporting_evidence=["Old logs from 2 weeks ago"],
            baseline_metrics={
                "latency_ms": ArchitecturalMetricSnapshot(
                    metric_name="latency_ms",
                    value=90.0,
                    sample_count=1,  # below minimum 3
                    timestamp=time.time() - 10000.0,
                )
            },
            confidence_score=0.5,
        )
        is_ok, reason = detector.validate_evidence_sufficiency(stale_opp)
        assert not is_ok
        assert "samples" in reason.lower() or "confidence" in reason.lower()

    # -------------------------------------------------------------------------
    # Scenario 8: Handling missing or unavailable telemetry
    # -------------------------------------------------------------------------
    def test_08_handling_missing_or_unavailable_telemetry(self):
        dep_graph = {"module.a": ["b", "c", "d", "e", "f", "g", "h", "i"]}
        # No latency telemetry, no failure clusters
        opps = self.bridge.discover_opportunities(
            dependency_graph=dep_graph,
            execution_latencies=None,
            failure_clusters=None,
        )
        assert len(opps) >= 1
        opp = opps[0]
        # Should record default nominal latency without crashing
        assert "execution_latency_ms" in opp.baseline_metrics
        assert opp.baseline_metrics["execution_latency_ms"].value == 50.0

    # -------------------------------------------------------------------------
    # Scenario 9: Detecting an optimization that does not improve its target metric
    # -------------------------------------------------------------------------
    def test_09_detecting_optimization_that_does_not_improve_target_metric(self):
        hyp = OptimizationHypothesis(
            hypothesis_id="hyp_no_impr",
            opportunity_id="opp_1",
            target_metric="latency_ms",
            current_baseline_value=100.0,
            predicted_improvement_delta=-20.0,
            minimum_demonstrable_delta=-5.0,  # Requires at least -5ms delta
            falsification_conditions=[],
        )
        alt = ArchitecturalAlternative(
            alternative_id="alt_ineffective",
            pattern_type=StructuralPatternType.FACADE_SHIM,
            title="Ineffective Shim",
            description="",
            producers=["p"],
            consumers=["c"],
            affected_files=["p"],
            predicted_metric_deltas={"latency_ms": -20.0},
        )
        sandbox = ExperimentSandbox()

        # Ineffective candidate probe produces exactly baseline (0 delta)
        exp = sandbox.run_isolated_experiment(
            alternative=alt,
            hypothesis=hyp,
            baseline_probe=lambda p: {"latency_ms": 100.0},
            mutation_applier=lambda p, a: (True, "Applied"),
            candidate_probe=lambda p: {"latency_ms": 99.0},  # delta = -1.0 (fails -5.0 threshold)
        )
        assert exp.outcome == ExperimentOutcome.NO_MEASURABLE_IMPROVEMENT
        assert "failed to meet minimum threshold" in exp.summary

    # -------------------------------------------------------------------------
    # Scenario 10: Detecting a regression in a secondary metric
    # -------------------------------------------------------------------------
    def test_10_detecting_regression_in_secondary_metric(self):
        hyp = OptimizationHypothesis(
            hypothesis_id="hyp_reg",
            opportunity_id="opp_1",
            target_metric="latency_ms",
            current_baseline_value=100.0,
            predicted_improvement_delta=-30.0,
            minimum_demonstrable_delta=-10.0,
            falsification_conditions=[],
        )
        alt = ArchitecturalAlternative(
            alternative_id="alt_regressive",
            pattern_type=StructuralPatternType.EVENT_DRIVEN_DECOUPLING,
            title="Regressive Decoupling",
            description="",
            producers=["p"],
            consumers=["c"],
            affected_files=["p"],
            predicted_metric_deltas={"latency_ms": -30.0},
        )
        sandbox = ExperimentSandbox()

        # Target latency improves by -35ms, BUT error_rate regresses by +0.08 (>0.01 limit)
        exp = sandbox.run_isolated_experiment(
            alternative=alt,
            hypothesis=hyp,
            baseline_probe=lambda p: {"latency_ms": 100.0, "error_rate": 0.0},
            mutation_applier=lambda p, a: (True, "Applied"),
            candidate_probe=lambda p: {"latency_ms": 65.0, "error_rate": 0.08},
            regression_thresholds={"error_rate": 0.01},
        )
        assert exp.outcome == ExperimentOutcome.REGRESSION_DETECTED
        assert len(exp.secondary_regressions_detected) > 0

    # -------------------------------------------------------------------------
    # Scenario 11: Comparing equivalent baselines and candidate measurements
    # -------------------------------------------------------------------------
    def test_11_comparing_equivalent_baselines_and_candidate_measurements(self):
        hyp = OptimizationHypothesis(
            hypothesis_id="hyp_probe",
            opportunity_id="opp_probe",
            target_metric="latency_ms",
            current_baseline_value=120.0,
            predicted_improvement_delta=-30.0,
            minimum_demonstrable_delta=-5.0,
            falsification_conditions=[],
        )
        alt = ArchitecturalAlternative(
            alternative_id="alt_p",
            pattern_type=StructuralPatternType.INTERFACE_INVERSION,
            title="Inversion",
            description="",
            producers=["p"],
            consumers=["c"],
            affected_files=["p"],
            predicted_metric_deltas={"latency_ms": -30.0},
        )
        sandbox = ExperimentSandbox()
        exp = sandbox.run_isolated_experiment(
            alternative=alt,
            hypothesis=hyp,
            baseline_probe=lambda p: {"latency_ms": 120.0, "memory_mb": 40.0},
            mutation_applier=lambda p, a: (True, "Applied"),
            candidate_probe=lambda p: {"latency_ms": 85.0, "memory_mb": 42.0},
        )
        assert exp.measured_deltas["latency_ms"] == -35.0
        assert exp.measured_deltas["memory_mb"] == 2.0
        assert exp.outcome == ExperimentOutcome.IMPROVEMENT_CONFIRMED

    # -------------------------------------------------------------------------
    # Scenario 12: Preventing contaminated or non-isolated experiments
    # -------------------------------------------------------------------------
    def test_12_preventing_contaminated_or_non_isolated_experiments(self):
        hyp = OptimizationHypothesis(
            hypothesis_id="hyp_contam",
            opportunity_id="opp_contam",
            target_metric="latency_ms",
            current_baseline_value=100.0,
            predicted_improvement_delta=-20.0,
            minimum_demonstrable_delta=-5.0,
            falsification_conditions=[],
        )
        alt = ArchitecturalAlternative(
            alternative_id="alt_c",
            pattern_type=StructuralPatternType.FACADE_SHIM,
            title="",
            description="",
            producers=[],
            consumers=[],
            affected_files=[],
            predicted_metric_deltas={},
        )
        # Sandbox pointing directly to temp_dir as both workspace and sandbox
        sandbox = ExperimentSandbox(main_workspace_path=self.temp_dir)
        # Force sandbox to simulate running inside main workspace
        orig_mkdtemp = tempfile.mkdtemp
        tempfile.mkdtemp = lambda prefix: self.temp_dir
        try:
            with pytest.raises(ExperimentContaminationError):
                sandbox.run_isolated_experiment(
                    alternative=alt,
                    hypothesis=hyp,
                    baseline_probe=lambda p: {},
                    mutation_applier=lambda p, a: (True, ""),
                    candidate_probe=lambda p: {},
                )
        finally:
            tempfile.mkdtemp = orig_mkdtemp

    # -------------------------------------------------------------------------
    # Scenario 13: Handling failed experiments without corrupting working tree
    # -------------------------------------------------------------------------
    def test_13_handling_failed_experiments_without_corrupting_working_tree(self):
        hyp = OptimizationHypothesis(
            hypothesis_id="hyp_fail",
            opportunity_id="opp_fail",
            target_metric="latency_ms",
            current_baseline_value=100.0,
            predicted_improvement_delta=-20.0,
            minimum_demonstrable_delta=-5.0,
            falsification_conditions=[],
        )
        alt = ArchitecturalAlternative(
            alternative_id="alt_fail",
            pattern_type=StructuralPatternType.DIRECT_SIMPLIFICATION,
            title="Broken mutation",
            description="",
            producers=["p"],
            consumers=["c"],
            affected_files=["p"],
            predicted_metric_deltas={},
        )
        sandbox = ExperimentSandbox()

        def broken_mutation(worktree: Path, a: ArchitecturalAlternative):
            # Write a scratch file in sandbox then fail
            (worktree / "scratch.tmp").write_text("bad code", encoding="utf-8")
            return False, "Syntax error compiling generated code"

        exp = sandbox.run_isolated_experiment(
            alternative=alt,
            hypothesis=hyp,
            baseline_probe=lambda p: {"latency_ms": 100.0},
            mutation_applier=broken_mutation,
            candidate_probe=lambda p: {"latency_ms": 100.0},
        )
        assert exp.outcome == ExperimentOutcome.INCONCLUSIVE
        assert "Syntax error" in exp.summary
        # Verify the scratch file was not left behind in the main workspace
        assert not os.path.exists("scratch.tmp")

    # -------------------------------------------------------------------------
    # Scenario 14: Reusing Phase 73 for a cross-component change
    # -------------------------------------------------------------------------
    def test_14_reusing_phase_73_for_cross_component_change(self):
        opp = OptimizationOpportunity(
            opportunity_id="opp_p73",
            title="Phase 73 cross-component integration",
            category=OpportunityCategory.DEPENDENCY_CONCENTRATION,
            affected_components=["core.orchestrator", "worker.task_a", "worker.task_b"],
            supporting_evidence=["Fan-in: 8", "Samples: 5"],
            baseline_metrics={
                "latency_ms": ArchitecturalMetricSnapshot(
                    metric_name="latency_ms", value=120.0, sample_count=5
                )
            },
        )
        hyp = OptimizationHypothesis(
            hypothesis_id="hyp_p73",
            opportunity_id=opp.opportunity_id,
            target_metric="latency_ms",
            current_baseline_value=120.0,
            predicted_improvement_delta=-30.0,
            minimum_demonstrable_delta=-5.0,
            falsification_conditions=[],
        )
        alt = ArchitecturalAlternative(
            alternative_id="alt_p73_winner",
            pattern_type=StructuralPatternType.FACADE_SHIM,
            title="Phase 73 Facade Shim",
            description="Decomposed refactoring",
            producers=["core/orchestrator.py"],
            consumers=["worker/task_a.py", "worker/task_b.py"],
            affected_files=["core/orchestrator.py", "worker/task_a.py"],
            predicted_metric_deltas={"latency_ms": -30.0},
        )
        decision = OptimizationDecision(
            decision_id="dec_p73",
            opportunity_id=opp.opportunity_id,
            selected_alternative_id=alt.alternative_id,
            governance_authorized=True,
            requires_human_approval=False,
            rationale="Approved",
        )

        res = self.bridge.execute_and_measure(
            decision=decision,
            opportunity=opp,
            hypothesis=hyp,
            alternatives=[alt],
            real_measurement_probe=lambda: 85.0,  # real delta = -35.0 (better than -5.0)
        )
        assert res["status"] == OptimizationState.ACCEPTED.value
        assert res["target_demonstrated"] is True
        assert res["macro_migration_id"].startswith("mig_")

    # -------------------------------------------------------------------------
    # Scenario 15: Respecting human approval requirements
    # -------------------------------------------------------------------------
    def test_15_respecting_human_approval_requirements(self):
        opp = OptimizationOpportunity(
            opportunity_id="opp_sec",
            title="Security sensitive component refactor",
            category=OpportunityCategory.EXCESSIVE_COUPLING,
            affected_components=["backend.auth.tokens"],
            supporting_evidence=["Samples: 5"],
            baseline_metrics={
                "latency_ms": ArchitecturalMetricSnapshot(
                    metric_name="latency_ms", value=100.0, sample_count=5
                )
            },
        )
        hyp = OptimizationHypothesis(
            hypothesis_id="hyp_sec",
            opportunity_id=opp.opportunity_id,
            target_metric="latency_ms",
            current_baseline_value=100.0,
            predicted_improvement_delta=-20.0,
            minimum_demonstrable_delta=-5.0,
            falsification_conditions=[],
        )
        alt_sec = ArchitecturalAlternative(
            alternative_id="alt_auth_mod",
            pattern_type=StructuralPatternType.INTERFACE_INVERSION,
            title="Auth Module Inversion",
            description="",
            producers=["backend/auth/tokens.py"],
            consumers=["backend/api/auth.py"],
            affected_files=["backend/auth/tokens.py"],
            predicted_metric_deltas={"latency_ms": -20.0},
            is_security_sensitive=True,
        )
        prioritizer = OptimizationPrioritizer()
        pareto_eval = MultiObjectiveEvaluator().evaluate_alternatives([alt_sec], hyp)
        confirmed_exp = {
            alt_sec.alternative_id: ExperimentRecord(
                experiment_id="exp_1",
                hypothesis_id=hyp.hypothesis_id,
                alternative_id=alt_sec.alternative_id,
                worktree_path="/tmp",
                baseline_measurements={"latency_ms": 100.0},
                candidate_measurements={"latency_ms": 75.0},
                measured_deltas={"latency_ms": -25.0},
                outcome=ExperimentOutcome.IMPROVEMENT_CONFIRMED,
                summary="Passed",
            )
        }

        # 1. Without token: stops at boundary
        dec_unauth = prioritizer.decide_optimization(
            opp, [alt_sec], pareto_eval, confirmed_exp, human_approval_token=None
        )
        assert not dec_unauth.governance_authorized
        assert dec_unauth.requires_human_approval is True

        # 2. With token: authorized
        dec_auth = prioritizer.decide_optimization(
            opp, [alt_sec], pareto_eval, confirmed_exp, human_approval_token="HUMAN_TOKEN_PHASE74"
        )
        assert dec_auth.governance_authorized is True

    # -------------------------------------------------------------------------
    # Scenario 16: Preventing unauthorized execution or release promotion
    # -------------------------------------------------------------------------
    def test_16_preventing_unauthorized_execution_or_release_promotion(self):
        opp = OptimizationOpportunity(
            opportunity_id="opp_unauth",
            title="Unauthorized execution test",
            category=OpportunityCategory.COORDINATION_BOTTLENECK,
            affected_components=["core.p"],
            supporting_evidence=[],
            baseline_metrics={},
        )
        hyp = OptimizationHypothesis(
            hypothesis_id="hyp_u",
            opportunity_id=opp.opportunity_id,
            target_metric="latency_ms",
            current_baseline_value=100.0,
            predicted_improvement_delta=-20.0,
            minimum_demonstrable_delta=-5.0,
            falsification_conditions=[],
        )
        alt = ArchitecturalAlternative(
            alternative_id="alt_u",
            pattern_type=StructuralPatternType.FACADE_SHIM,
            title="",
            description="",
            producers=["p"],
            consumers=["c"],
            affected_files=["p"],
            predicted_metric_deltas={},
        )
        unauthorized_dec = OptimizationDecision(
            decision_id="dec_unauth",
            opportunity_id=opp.opportunity_id,
            selected_alternative_id=alt.alternative_id,
            governance_authorized=False,  # NOT AUTHORIZED
            requires_human_approval=True,
            rationale="Approval missing",
        )

        with pytest.raises(UnauthorizedExecutionError) as exc_info:
            self.bridge.execute_and_measure(unauthorized_dec, opp, hyp, [alt])
        assert "Execution blocked" in str(exc_info.value)

    # -------------------------------------------------------------------------
    # Scenario 17: Recovering safely from interrupted experiments
    # -------------------------------------------------------------------------
    def test_17_recovering_safely_from_interrupted_experiments(self):
        hyp = OptimizationHypothesis(
            hypothesis_id="hyp_crash",
            opportunity_id="opp_crash",
            target_metric="latency_ms",
            current_baseline_value=100.0,
            predicted_improvement_delta=-20.0,
            minimum_demonstrable_delta=-5.0,
            falsification_conditions=[],
        )
        alt = ArchitecturalAlternative(
            alternative_id="alt_crash",
            pattern_type=StructuralPatternType.FACADE_SHIM,
            title="Crash candidate",
            description="",
            producers=["p"],
            consumers=["c"],
            affected_files=["p"],
            predicted_metric_deltas={},
        )
        sandbox = ExperimentSandbox()

        def crashing_probe(path: Path):
            raise RuntimeError("Simulated process interruption during benchmark")

        try:
            sandbox.run_isolated_experiment(
                alternative=alt,
                hypothesis=hyp,
                baseline_probe=crashing_probe,
                mutation_applier=lambda p, a: (True, ""),
                candidate_probe=lambda p: {},
            )
        except RuntimeError:
            pass

        # Verify no orphan worktree remained behind in temp directory
        orphan_dirs = list(Path(tempfile.gettempdir()).glob("jarvis_opt_sandbox_*"))
        # Any orphan dir should be clean or empty
        assert len(orphan_dirs) == 0 or all(not os.listdir(d) for d in orphan_dirs)

    # -------------------------------------------------------------------------
    # Scenario 18: Persisting full evidence and decision provenance
    # -------------------------------------------------------------------------
    def test_18_persisting_full_evidence_and_decision_provenance(self):
        opp = OptimizationOpportunity(
            opportunity_id="opp_persist",
            title="Persistence verification",
            category=OpportunityCategory.DEPENDENCY_CONCENTRATION,
            affected_components=["mod.a", "mod.b"],
            supporting_evidence=["Trace evidence"],
            baseline_metrics={
                "latency_ms": ArchitecturalMetricSnapshot(
                    metric_name="latency_ms", value=75.0, sample_count=5
                )
            },
        )
        store = self.bridge.store
        opp_path = store.save_opportunity(opp)
        assert os.path.exists(opp_path)

        loaded_opp = store.load_opportunity("opp_persist")
        assert loaded_opp is not None
        assert loaded_opp.opportunity_id == "opp_persist"
        assert loaded_opp.baseline_metrics["latency_ms"].value == 75.0

    # -------------------------------------------------------------------------
    # Scenario 19: Learning from a previously unsuccessful optimization
    # -------------------------------------------------------------------------
    def test_19_learning_from_previously_unsuccessful_optimization(self):
        learner = OptimizationLearner(storage_dir=os.path.join(self.temp_dir, "calibration"))
        # Record 2 historical failures for EVENT_DRIVEN_DECOUPLING on latency_ms
        learner.record_outcome(
            pattern_type=StructuralPatternType.EVENT_DRIVEN_DECOUPLING.value,
            target_metric="latency_ms",
            predicted_delta=-40.0,
            measured_delta=+15.0,  # Regressed
            successful=False,
            notes="Message broker introduced excessive serialization overhead",
        )
        learner.record_outcome(
            pattern_type=StructuralPatternType.EVENT_DRIVEN_DECOUPLING.value,
            target_metric="latency_ms",
            predicted_delta=-30.0,
            measured_delta=+5.0,  # Regressed
            successful=False,
            notes="Second attempt failed to reduce latency",
        )

        assert learner.is_assumption_previously_refuted(
            StructuralPatternType.EVENT_DRIVEN_DECOUPLING.value, "latency_ms"
        )
        penalty = learner.get_pattern_penalty(
            StructuralPatternType.EVENT_DRIVEN_DECOUPLING.value, "latency_ms"
        )
        assert penalty > 0.0  # Applies risk penalty to prevent repeating invalid assumption

    # -------------------------------------------------------------------------
    # Scenario 20: Handling an unseen architectural topology without hardcoded assumptions
    # -------------------------------------------------------------------------
    def test_20_handling_unseen_architectural_topology(self):
        """
        Unseen complex cyclic multi-cluster graph with 12 nodes:
        Cluster A (nodes 1-4) connected to Cluster B (nodes 5-8) through bridge 4->5,
        with backward feedback loop 8->1.
        """
        complex_graph = {
            "node_1": ["node_2", "node_3"],
            "node_2": ["node_3", "node_4"],
            "node_3": ["node_4"],
            "node_4": ["node_5"],  # Inter-cluster bridge
            "node_5": ["node_6", "node_7"],
            "node_6": ["node_7", "node_8"],
            "node_7": ["node_8"],
            "node_8": ["node_1"],  # Cyclic feedback
            "node_9": ["node_5", "node_6", "node_7", "node_8", "node_1"],  # Hub
        }
        latencies = {
            "node_9": [150.0, 160.0, 140.0, 155.0],
            "node_4": [90.0, 95.0, 85.0],
        }

        # Run full optimization cycle
        cycle_res = self.bridge.run_full_optimization_cycle(
            dependency_graph=complex_graph,
            execution_latencies=latencies,
            target_metric="execution_latency_ms",
            baseline_probe=lambda p: {"coupling_ratio": 0.5, "execution_latency_ms": 150.0},
            mutation_applier=lambda p, a: (True, "Applied interface inversion"),
            candidate_probe=lambda p: {"coupling_ratio": 0.3, "execution_latency_ms": 110.0},
            real_measurement_probe=lambda: 110.0,
        )
        assert cycle_res["status"] == OptimizationState.ACCEPTED.value
        assert cycle_res["execution_result"]["target_demonstrated"] is True
        assert len(cycle_res["experiments"]) >= 2
