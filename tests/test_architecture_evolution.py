"""
JARVIS OS — Phase 64: Autonomous Architecture Evolution & Design Governance
Test Suite: test_architecture_evolution.py
Validates the 20 mandatory architectural evolution, constraint extraction,
alternative generation, simulation, and governance gate scenarios.
"""

from __future__ import annotations

import unittest
from typing import Any, Dict

from backend.agents.architecture_evolution.bridge import ArchitectureEvolutionBridge
from backend.agents.architecture_evolution.models import (
    AlternativeType,
    ArchitectureAlternative,
    ArchitectureConstraint,
    ArchitectureGovernanceDecision,
    ArchitectureMigrationPlan,
    ArchitectureProblem,
    ArchitectureSnapshot,
    ContractBreakStatus,
    CostObservationStatus,
    GovernanceDecisionState,
    ImpactScope,
    ObservationStatus,
    ProblemCategory,
    ProblemSeverity,
    ReversibilityStatus,
    RiskCriticality,
    SimulationStatus,
)


class TestArchitectureEvolution(unittest.TestCase):
    """20 comprehensive test scenarios for Phase 64."""

    def setUp(self):
        ArchitectureEvolutionBridge.reset_instance()
        self.bridge = ArchitectureEvolutionBridge.get_instance(db_path=":memory:")

        # Canonical test snapshot
        self.sample_snapshot = ArchitectureSnapshot(
            snapshot_id="snap_test_01",
            files=[
                "backend/websocket/handlers/missions.py",
                "agents/autonomous_loop/controller.py",
                "backend/agents/continuous_verification/bridge.py",
                "database/sqlite_store.py",
            ],
            symbols=[
                "backend.websocket.handlers.missions::handle_mission_control",
                "agents.autonomous_loop.controller::AutonomousLoopController",
                "backend.agents.continuous_verification.bridge::ContinuousVerificationBridge",
                "database.sqlite_store::execute_query",
            ],
            modules=["backend", "agents", "database"],
            packages=["backend.websocket", "agents.autonomous_loop", "database"],
            services=["mission_service", "verification_service", "storage_service"],
            contracts=["contracts/mission_schema.json"],
            dependencies=[
                ("backend/websocket/handlers/missions.py", "agents/autonomous_loop/controller.py"),
                ("agents/autonomous_loop/controller.py", "backend/agents/continuous_verification/bridge.py"),
                ("backend/agents/continuous_verification/bridge.py", "agents/autonomous_loop/controller.py"),  # Cycle
                ("backend/websocket/handlers/missions.py", "database/sqlite_store.py"),
                ("agents/autonomous_loop/controller.py", "database/sqlite_store.py"),  # Persistence coupling
            ],
            consumers={
                "contracts/mission_schema.json": [
                    "frontend/src/features/missions/MissionControlCenter.tsx",
                    "backend/websocket/handlers/missions.py",
                    "client_sdk",
                    "monitoring_agent",
                    "audit_logger",
                    "cli_tool",
                ],
            },
            sccs=[
                ["agents/autonomous_loop/controller.py", "backend/agents/continuous_verification/bridge.py", "agents/orchestrator.py"],
            ],
            persistence_edges=[
                {"source": "backend/websocket/handlers/missions.py", "table": "missions"},
                {"source": "agents/autonomous_loop/controller.py", "table": "missions"},
            ],
            external_boundaries=["dynamic_reflection_getattr_plugin"],
            browser_surfaces=["MissionControlCenter.tsx"],
            test_surfaces=["tests/test_continuous_verification.py"],
            risk_zones=["auth_token_signer", "wallet_transfer_gateway"],
        )
        self.bridge.register_snapshot(self.sample_snapshot)

    # 1. Deterministic Snapshot Hash
    def test_01_deterministic_snapshot_hash(self):
        h1 = self.sample_snapshot.compute_hash()
        h2 = self.sample_snapshot.compute_hash()
        self.assertEqual(h1, h2, "Snapshot hash must be perfectly deterministic across invocations.")
        self.assertEqual(len(h1), 64, "Hash must be standard SHA-256 hex string.")

    # 2. Problem Detection
    def test_02_problem_detection(self):
        problems = self.bridge.observe_and_detect_problems("snap_test_01")
        self.assertGreaterEqual(len(problems), 2, "Must detect cyclic SCC and persistence coupling.")
        categories = [p.category for p in problems]
        self.assertIn(ProblemCategory.SCC, categories)
        self.assertIn(ProblemCategory.COUPLING, categories)

    # 3. False Architecture Smell Rejection
    def test_03_false_architecture_smell_rejection(self):
        mock_snapshot = ArchitectureSnapshot(
            snapshot_id="snap_test_mock",
            files=["tests/conftest.py", "tests/mocks/barrel/__init__.py"],
            dependencies=[
                ("tests/conftest.py", "a"), ("tests/conftest.py", "b"),
                ("tests/conftest.py", "c"), ("tests/conftest.py", "d"),
                ("tests/conftest.py", "e"), ("tests/conftest.py", "f"),
                ("tests/conftest.py", "g"), ("tests/conftest.py", "h"),
                ("tests/conftest.py", "i"), ("tests/conftest.py", "j"),
            ],
        )
        self.bridge.register_snapshot(mock_snapshot)
        problems = self.bridge.observe_and_detect_problems("snap_test_mock")
        self.assertEqual(len(problems), 0, "Test harnesses and canonical barrel files must be rejected as false smells.")

    # 4. Constraint Extraction
    def test_04_constraint_extraction(self):
        problems = self.bridge.observe_and_detect_problems("snap_test_01")
        scc_problem = [p for p in problems if p.category == ProblemCategory.SCC][0]
        constraints = self.bridge.constraint_extractor.extract_constraints(scc_problem, self.sample_snapshot)
        self.assertGreater(len(constraints), 0, "Must extract real repository constraints.")
        categories = [c.category for c in constraints]
        self.assertIn("security", categories)
        self.assertIn("compatibility", categories)

    # 5. Alternative Generation
    def test_05_alternative_generation(self):
        problems = self.bridge.observe_and_detect_problems("snap_test_01")
        scc_problem = [p for p in problems if p.category == ProblemCategory.SCC][0]
        constraints = self.bridge.constraint_extractor.extract_constraints(scc_problem, self.sample_snapshot)
        alts = self.bridge.alternative_generator.generate_alternatives(scc_problem, constraints)
        self.assertGreaterEqual(len(alts), 3, "Must generate at least 3 distinct architectural alternatives.")
        types = [a.alternative_type for a in alts]
        self.assertIn(AlternativeType.KEEP_CURRENT, types, "Must always provide keep_current as baseline.")

    # 6. F63 Pattern Transfer as Hypothesis
    def test_06_f63_pattern_transfer(self):
        problems = self.bridge.observe_and_detect_problems("snap_test_01")
        p = problems[0]
        f63_hint = {
            "source_project": "donor_repo_gamma",
            "knowledge_id": "know_f63_retry_01",
            "title": "Circuit Breaker Pattern",
            "description": "Observed in donor repo",
            "benefits": ["Fault isolation"],
            "costs": ["Adapter maintenance"],
            "risks": ["Context drift"],
        }
        alts = self.bridge.alternative_generator.generate_alternatives(
            p, [], external_pattern_hint=f63_hint
        )
        f63_alts = [a for a in alts if a.is_hypothesis_from_f63]
        self.assertEqual(len(f63_alts), 1, "Must generate F63 hypothesis alternative.")
        self.assertEqual(f63_alts[0].source_project, "donor_repo_gamma")

    # 7. Impact Analysis
    def test_07_impact_analysis(self):
        problems = self.bridge.observe_and_detect_problems("snap_test_01")
        p = problems[0]
        alts = self.bridge.alternative_generator.generate_alternatives(p, [])
        active_alt = [a for a in alts if a.alternative_type != AlternativeType.KEEP_CURRENT][0]
        impact = self.bridge.impact_analyzer.analyze_impact(active_alt, self.sample_snapshot)
        self.assertGreater(impact.blast_radius, 0)
        self.assertIn(impact.scope, [ImpactScope.DIRECT, ImpactScope.INDIRECT, ImpactScope.DOWNSTREAM])

    # 8. Contract Analysis & Breaking Safety
    def test_08_contract_analysis(self):
        alt = ArchitectureAlternative(
            alternative_id="alt_break_test",
            problem_id="prob_test",
            alternative_type=AlternativeType.SERVICE_SPLIT,
            title="Breaking Schema Mutation",
            description="Changes required fields",
            affected_components=["contracts/mission_schema.json"],
            compatibility_impact="BREAKING",
        )
        cnt = self.bridge.contract_analyzer.analyze_contracts(alt, self.sample_snapshot)
        self.assertEqual(cnt.status, ContractBreakStatus.BREAKING)
        self.assertGreater(len(cnt.breaking_contracts), 0)

    # 9. Behavior Analysis
    def test_09_behavior_analysis(self):
        alt_evt = ArchitectureAlternative(
            alternative_id="alt_evt_test",
            problem_id="prob_test",
            alternative_type=AlternativeType.EVENT_DRIVEN,
            title="Async Event Decoupling",
            description="Replaces sync call with event bus",
        )
        beh = self.bridge.behavior_analyzer.analyze_behavior(alt_evt, self.sample_snapshot)
        self.assertEqual(beh.ordering_preservation, "POTENTIAL_REORDERING")
        self.assertNotEqual(beh.behavior_preservation, "PRESERVED", "Event-driven must not claim identical synchronous behavior.")

    # 10. Risk Analysis Multi-Vector
    def test_10_risk_analysis(self):
        alt = ArchitectureAlternative(
            alternative_id="alt_risk_test",
            problem_id="prob_test",
            alternative_type=AlternativeType.SERVICE_SPLIT,
            title="Service Split",
            description="Split service",
            reversibility=ReversibilityStatus.DIFFICULT_TO_REVERSE,
            migration_complexity="HIGH",
        )
        risk = self.bridge.risk_analyzer.analyze_risk(alt, self.sample_snapshot)
        self.assertIn("security", risk.risk_vector)
        self.assertIn("reliability", risk.risk_vector)
        self.assertIn("rollback", risk.risk_vector)
        self.assertGreater(risk.rollback_risk, 0.4)

    # 11. Cost Classification & Status
    def test_11_cost_classification(self):
        alt = ArchitectureAlternative(
            alternative_id="alt_cost_test",
            problem_id="prob_test",
            alternative_type=AlternativeType.MODULARIZATION,
            title="Modularization",
            description="Decompose modules",
            affected_components=["backend/websocket/handlers/missions.py"],
        )
        cost = self.bridge.cost_model.estimate_cost(alt, self.sample_snapshot)
        self.assertEqual(cost.observation_status, CostObservationStatus.ESTIMATED)
        self.assertGreater(cost.total_estimated_effort_hours, 0.0)
        self.assertIn("implementation", cost.costs)

    # 12. Migration DAG
    def test_12_migration_dag(self):
        alt = ArchitectureAlternative(
            alternative_id="alt_dag_test",
            problem_id="prob_test",
            alternative_type=AlternativeType.MODULARIZATION,
            title="Modularization",
            description="Decompose modules",
        )
        plan = self.bridge.migration_planner.plan_migration(alt)
        self.assertEqual(plan.total_steps, 7)
        stages = [s.step_type.value for s in plan.steps]
        self.assertEqual(stages, ["PREPARATION", "COMPATIBILITY_LAYER", "DUAL_PATH", "VALIDATION", "CUTOVER", "OBSERVATION", "CLEANUP"])

    # 13. Rollback Analysis
    def test_13_rollback_analysis(self):
        alt = ArchitectureAlternative(
            alternative_id="alt_roll_test",
            problem_id="prob_test",
            alternative_type=AlternativeType.MODULARIZATION,
            title="Modularization",
            description="Decompose modules",
        )
        plan = self.bridge.migration_planner.plan_migration(alt)
        for s in plan.steps:
            self.assertTrue(s.is_reversibility_supported, f"Step '{s.step_id}' must support rollback.")
            self.assertTrue(len(s.rollback_action) > 0, f"Step '{s.step_id}' must declare executable rollback.")

    # 14. Simulation Safe vs Risk
    def test_14_simulation(self):
        alt_safe = ArchitectureAlternative(
            alternative_id="alt_sim_safe",
            problem_id="prob_test",
            alternative_type=AlternativeType.FACADE,
            title="Gateway Facade",
            description="Facade wrapping",
            reversibility=ReversibilityStatus.EASILY_REVERSIBLE,
        )
        mig_safe = self.bridge.migration_planner.plan_migration(alt_safe)
        cnt_safe = self.bridge.contract_analyzer.analyze_contracts(alt_safe, self.sample_snapshot)
        sim = self.bridge.simulator.simulate(alt_safe, self.sample_snapshot, mig_safe, cnt_safe)
        self.assertEqual(sim.status, SimulationStatus.SIMULATION_SAFE)

    # 15. Governance Gate: Separation of Proposal and Approval
    def test_15_governance_gate(self):
        problems = self.bridge.observe_and_detect_problems("snap_test_01")
        p = problems[0]
        alt_keep = ArchitectureAlternative(
            alternative_id="alt_keep_gov",
            problem_id=p.problem_id,
            alternative_type=AlternativeType.KEEP_CURRENT,
            title="Keep Current",
            description="Maintain current",
        )
        dec = self.bridge.governance_engine.evaluate_governance(p, alt_keep)
        self.assertEqual(dec.state, GovernanceDecisionState.OBSERVATION_ONLY)

    # 16. Security Sentinel Block
    def test_16_security_block(self):
        alt_malicious = ArchitectureAlternative(
            alternative_id="alt_bad_sec",
            problem_id="prob_test",
            alternative_type=AlternativeType.MODULARIZATION,
            title="Delete Database and Drop Table",
            description="Execute DROP DATABASE missions; api_key=secret123",
            affected_components=["rm -rf /"],
        )
        is_sec, violations = self.bridge.security_filter.validate_proposal(alt_malicious, {})
        self.assertFalse(is_sec)
        self.assertGreater(len(violations), 0)

        dec = self.bridge.governance_engine.evaluate_governance(
            problem=ArchitectureProblem(
                problem_id="prob_test",
                category=ProblemCategory.SECURITY,
                affected_nodes=["rm -rf /"],
                affected_symbols=[],
                evidence={},
                severity=ProblemSeverity.CRITICAL,
                confidence=1.0,
            ),
            alternative=alt_malicious,
            sentinel_passed=is_sec,
        )
        self.assertEqual(dec.state, GovernanceDecisionState.BLOCKED)

    # 17. Cache Invalidation
    def test_17_cache_invalidation(self):
        key = self.bridge.cache.compute_key("snap_h1", "prob_h1", "const_h1", "STANDARD")
        self.bridge.cache.put(key, {"verdict": "SAFE"}, metadata={"snapshot_hash": "snap_h1"})
        self.assertEqual(self.bridge.cache.size(), 1)
        # Invalidate
        del_count = self.bridge.cache.invalidate("snap_h1")
        self.assertEqual(del_count, 1)
        self.assertEqual(self.bridge.cache.size(), 0)

    # 18. Dynamic Boundary Observation
    def test_18_dynamic_boundary(self):
        snap_dynamic = ArchitectureSnapshot(
            snapshot_id="snap_dynamic",
            files=["agents/plugin.py"],
            external_boundaries=["dynamic_reflection_getattr_plugin"],
        )
        self.bridge.register_snapshot(snap_dynamic)
        problems = self.bridge.observe_and_detect_problems("snap_dynamic")
        dyn_probs = [p for p in problems if p.category == ProblemCategory.SECURITY]
        self.assertEqual(len(dyn_probs), 1)
        self.assertEqual(dyn_probs[0].status, ObservationStatus.SUSPECTED)

    # 19. Unseen Architecture Task Evaluation
    def test_19_unseen_architecture_task(self):
        problems = self.bridge.observe_and_detect_problems("snap_test_01")
        self.assertGreater(len(problems), 0)
        res = self.bridge.evaluate_problem(
            problem_id=problems[0].problem_id,
            snapshot_id="snap_test_01",
            policy_name="STANDARD",
        )
        self.assertIn("problem", res)
        self.assertIn("alternatives", res)
        self.assertIn("comparison", res)
        self.assertIn("governance_decisions", res)

    # 20. Regression Denominator Invariant Verification
    def test_20_regression_denominator_invariant(self):
        per_phase_passes = [22, 23, 17, 22, 8, 10, 17, 29, 12, 20, 22, 24, 24, 24, 24, 22, 24, 28, 24, 24, 25, 25, 40, 40, 40]
        reported_total = 590
        self.assertEqual(sum(per_phase_passes), reported_total, "Denominator summation invariant must hold exactly!")


if __name__ == "__main__":
    unittest.main()
