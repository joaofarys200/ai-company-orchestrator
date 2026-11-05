"""
JARVIS OS — Phase 75: Autonomous Engineering Strategy & Portfolio Orchestration
Deterministic Test Suite covering all 25 required scenarios from Section 10.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path
import pytest

from backend.agents.portfolio_orchestration import (
    CapacityScheduler,
    ConflictDiagnostic,
    ConflictType,
    ConstraintViolationError,
    DependencyCycleError,
    DependencyGraphEngine,
    DependencyRelation,
    DependencyType,
    EngineeringInitiative,
    EvidenceProvenance,
    ExecutionSchedule,
    ExecutionScheduleItem,
    InfeasiblePortfolioError,
    InitiativeState,
    InitiativeType,
    MilestoneCheckpoint,
    PortfolioBacklog,
    PortfolioMetricsTracker,
    PortfolioOrchestrationBridge,
    PortfolioReplanningEngine,
    PortfolioRoadmap,
    PortfolioStore,
    RedundancyDefinition,
    ReplanningEvent,
    ReplanningLoopError,
    ReplanningTriggerType,
    SynergyDefinition,
    UnauthorizedInitiativeError,
)


class TestPortfolioOrchestrationEngine:

    @pytest.fixture(autouse=True)
    def setup_temp_env(self):
        self.temp_dir = tempfile.mkdtemp(prefix="jarvis_phase75_test_")
        self.bridge = PortfolioOrchestrationBridge(store_dir=self.temp_dir)
        yield
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Scenario 1: Creating a portfolio from existing supported engineering initiatives
    # -------------------------------------------------------------------------
    def test_01_create_portfolio_from_supported_initiatives(self):
        backlog = self.bridge.backlog
        init1 = backlog.ingest_from_architectural_optimization(
            opp_id="opt_cache_decouple",
            title="Decouple Cache Client",
            affected_files=["backend/cache.py", "backend/router.py"],
            predicted_benefit=80.0,
            cost=20.0,
        )
        init2 = backlog.ingest_from_macro_refactoring(
            migration_id="refactor_event_bus",
            title="Extract Event Bus",
            affected_components=["backend/events.py"],
            estimated_steps=4,
            expected_benefit=100.0,
        )
        init3 = backlog.ingest_from_quality_debt(
            debt_id="debt_complexity_storage",
            title="Refactor Storage God Object",
            affected_files=["backend/storage.py"],
            severity_score=8.5,
            remediation_cost=15.0,
        )

        eval_res, roadmap = self.bridge.create_and_evaluate_portfolio(
            portfolio_id="port_initial",
            max_budget=100.0,
            max_effort=20.0,
        )

        assert eval_res.is_feasible is True
        assert len(eval_res.selected_initiatives) == 3
        assert set(roadmap.selected_initiatives) == {"opt_cache_decouple", "refactor_event_bus", "debt_complexity_storage"}
        assert roadmap.version == "v1.0.0"
        assert roadmap.schedule.total_waves >= 1

    # -------------------------------------------------------------------------
    # Scenario 2: Identifying hard prerequisites
    # -------------------------------------------------------------------------
    def test_02_identifying_hard_prerequisites(self):
        backlog = self.bridge.backlog
        # init_b requires init_a
        init_a = backlog.ingest_from_macro_refactoring(
            migration_id="init_a",
            title="Foundational Interface Extraction",
            affected_components=["backend/base.py"],
            estimated_steps=2,
            expected_benefit=40.0,
        )
        init_b = backlog.ingest_from_architectural_optimization(
            opp_id="init_b",
            title="Consumer Adapter Optimization",
            affected_files=["backend/adapter.py"],
            predicted_benefit=90.0,
            cost=20.0,
            prerequisites=["init_a"],
        )

        eval_res, roadmap = self.bridge.create_and_evaluate_portfolio(
            portfolio_id="port_prereq",
            max_budget=100.0,
            max_effort=20.0,
        )

        assert eval_res.is_feasible is True
        assert "init_a" in roadmap.selected_initiatives
        assert "init_b" in roadmap.selected_initiatives

        # init_a must be in an earlier wave than init_b
        wave_a = next(it.wave_index for it in roadmap.schedule.items if it.initiative_id == "init_a")
        wave_b = next(it.wave_index for it in roadmap.schedule.items if it.initiative_id == "init_b")
        assert wave_a < wave_b, "Prerequisite init_a must precede dependent init_b in execution schedule"

    # -------------------------------------------------------------------------
    # Scenario 3: Detecting dependency cycles
    # -------------------------------------------------------------------------
    def test_03_detecting_dependency_cycles(self):
        backlog = self.bridge.backlog
        # Create circular prerequisites: X -> Y -> Z -> X
        init_x = EngineeringInitiative(
            id="init_x",
            title="Initiative X",
            initiative_type=InitiativeType.MACRO_REFACTORING,
            prerequisites=["init_z"],
        )
        init_y = EngineeringInitiative(
            id="init_y",
            title="Initiative Y",
            initiative_type=InitiativeType.ARCHITECTURAL_OPTIMIZATION,
            prerequisites=["init_x"],
        )
        init_z = EngineeringInitiative(
            id="init_z",
            title="Initiative Z",
            initiative_type=InitiativeType.TECHNICAL_DEBT_REMEDIATION,
            prerequisites=["init_y"],
        )
        backlog.add_initiative(init_x)
        backlog.add_initiative(init_y)
        backlog.add_initiative(init_z)

        with pytest.raises(DependencyCycleError) as exc_info:
            self.bridge.create_and_evaluate_portfolio(
                portfolio_id="port_cycle",
                max_budget=100.0,
                max_effort=20.0,
            )
        assert len(exc_info.value.cycle_path) >= 2
        assert "init_x" in exc_info.value.cycle_path

    # -------------------------------------------------------------------------
    # Scenario 4: Detecting conflicting component modifications
    # -------------------------------------------------------------------------
    def test_04_detecting_conflicting_component_modifications(self):
        graph = DependencyGraphEngine()
        init1 = EngineeringInitiative(
            id="init1",
            title="Modify Storage Layer",
            initiative_type=InitiativeType.MACRO_REFACTORING,
            affected_components=["backend/storage.py", "backend/models.py"],
        )
        init2 = EngineeringInitiative(
            id="init2",
            title="Optimize Storage Latency",
            initiative_type=InitiativeType.ARCHITECTURAL_OPTIMIZATION,
            affected_components=["backend/storage.py", "backend/driver.py"],
        )
        graph.add_initiative(init1)
        graph.add_initiative(init2)

        conflicts = graph.detect_conflicts({"init1", "init2"})
        overlap_conflicts = [c for c in conflicts if c.conflict_type == ConflictType.OVERLAPPING_COMPONENTS]
        assert len(overlap_conflicts) == 1
        assert "backend/storage.py" in overlap_conflicts[0].description
        assert overlap_conflicts[0].resolvable is True

    # -------------------------------------------------------------------------
    # Scenario 5: Allowing demonstrably independent initiatives to run concurrently
    # -------------------------------------------------------------------------
    def test_05_independent_initiatives_run_concurrently(self):
        graph = DependencyGraphEngine()
        init_frontend = EngineeringInitiative(
            id="init_fe",
            title="Frontend UI Clean",
            initiative_type=InitiativeType.TECHNICAL_DEBT_REMEDIATION,
            affected_components=["frontend/src/App.tsx"],
        )
        init_backend = EngineeringInitiative(
            id="init_be",
            title="Backend Logger Decouple",
            initiative_type=InitiativeType.ARCHITECTURAL_OPTIMIZATION,
            affected_components=["backend/logging.py"],
        )
        graph.add_initiative(init_frontend)
        graph.add_initiative(init_backend)

        assert graph.are_concurrent_safe("init_fe", "init_be") is True

        scheduler = CapacityScheduler(graph_engine=graph, max_concurrency=2)
        schedule = scheduler.build_schedule(
            portfolio_id="port_conc",
            selected_ids=["init_fe", "init_be"],
            initiatives={"init_fe": init_frontend, "init_be": init_backend},
        )
        assert schedule.total_waves == 1
        waves = {it.wave_index for it in schedule.items}
        assert len(waves) == 1, "Independent initiatives must be scheduled in the same parallel wave"

    # -------------------------------------------------------------------------
    # Scenario 6: Detecting duplicate objectives
    # -------------------------------------------------------------------------
    def test_06_detecting_duplicate_objectives(self):
        backlog = PortfolioBacklog()
        init1 = EngineeringInitiative(
            id="debt_101",
            title="Clean Up Database Connection Leak",
            initiative_type=InitiativeType.TECHNICAL_DEBT_REMEDIATION,
            affected_components=["backend/db.py"],
        )
        init2 = EngineeringInitiative(
            id="opt_202",
            title="clean up database connection leak",  # Semantically duplicate
            initiative_type=InitiativeType.TECHNICAL_DEBT_REMEDIATION,
            affected_components=["backend/db.py"],
        )

        ok1, msg1 = backlog.add_initiative(init1)
        assert ok1 is True

        ok2, msg2 = backlog.add_initiative(init2)
        assert ok2 is False
        assert "DUPLICATE_OBJECTIVE" in msg2

    # -------------------------------------------------------------------------
    # Scenario 7: Accounting for prerequisite value when prioritizing candidates
    # -------------------------------------------------------------------------
    def test_07_accounting_for_prerequisite_value_in_prioritization(self):
        # Enabler has moderate benefit (30) but unlocks High-Value Target (200)
        enabler = EngineeringInitiative(
            id="enabler",
            title="Core Modular Framework",
            initiative_type=InitiativeType.MACRO_REFACTORING,
            budget_cost=20.0,
            effort_units=2.0,
            expected_benefit=30.0,
            confidence=1.0,
        )
        high_value = EngineeringInitiative(
            id="high_value",
            title="Distributed Transaction Service",
            initiative_type=InitiativeType.ARCHITECTURAL_OPTIMIZATION,
            budget_cost=30.0,
            effort_units=3.0,
            expected_benefit=200.0,
            confidence=1.0,
            prerequisites=["enabler"],
        )
        standalone = EngineeringInitiative(
            id="standalone",
            title="Isolated Utility Patch",
            initiative_type=InitiativeType.TECHNICAL_DEBT_REMEDIATION,
            budget_cost=20.0,
            effort_units=2.0,
            expected_benefit=45.0,  # higher than enabler alone, but does not unlock anything
            confidence=1.0,
        )

        backlog = self.bridge.backlog
        backlog.add_initiative(enabler)
        backlog.add_initiative(high_value)
        backlog.add_initiative(standalone)

        # Budget of 55 allows either (enabler + high_value) [cost 50] or (standalone + enabler) [cost 40]
        eval_res, roadmap = self.bridge.create_and_evaluate_portfolio(
            portfolio_id="port_prereq_val",
            max_budget=55.0,
            max_effort=10.0,
        )

        assert eval_res.is_feasible is True
        assert "enabler" in eval_res.selected_initiatives
        assert "high_value" in eval_res.selected_initiatives
        assert "standalone" in eval_res.rejected_initiatives

    # -------------------------------------------------------------------------
    # Scenario 8: Selecting a feasible portfolio under a strict budget
    # -------------------------------------------------------------------------
    def test_08_selecting_feasible_portfolio_under_strict_budget(self):
        backlog = self.bridge.backlog
        init_cheap = EngineeringInitiative(
            id="cheap",
            title="Cheap Refactor",
            initiative_type=InitiativeType.TECHNICAL_DEBT_REMEDIATION,
            budget_cost=20.0,
            effort_units=1.0,
            expected_benefit=50.0,
        )
        init_expensive = EngineeringInitiative(
            id="expensive",
            title="Expensive Rewrite",
            initiative_type=InitiativeType.MACRO_REFACTORING,
            budget_cost=100.0,
            effort_units=10.0,
            expected_benefit=120.0,
        )
        backlog.add_initiative(init_cheap)
        backlog.add_initiative(init_expensive)

        eval_res, roadmap = self.bridge.create_and_evaluate_portfolio(
            portfolio_id="port_budget",
            max_budget=30.0,
            max_effort=5.0,
        )

        assert eval_res.is_feasible is True
        assert eval_res.selected_initiatives == ["cheap"]
        assert eval_res.rejected_initiatives == ["expensive"]
        assert eval_res.total_cost <= 30.0

    # -------------------------------------------------------------------------
    # Scenario 9: Reporting infeasibility when no safe portfolio exists
    # -------------------------------------------------------------------------
    def test_09_reporting_infeasibility_when_no_safe_portfolio(self):
        backlog = self.bridge.backlog
        # All initiatives exceed budget or have impossible constraints
        init1 = EngineeringInitiative(
            id="huge_1",
            title="Huge Job 1",
            initiative_type=InitiativeType.MACRO_REFACTORING,
            budget_cost=500.0,
            effort_units=50.0,
            expected_benefit=100.0,
        )
        backlog.add_initiative(init1)

        eval_res, roadmap = self.bridge.create_and_evaluate_portfolio(
            portfolio_id="port_infeasible",
            max_budget=50.0,
            max_effort=5.0,
        )

        assert eval_res.is_feasible is False
        assert len(eval_res.infeasibility_reasons) > 0
        assert roadmap.status == "INFEASIBLE"
        assert len(roadmap.selected_initiatives) == 0

    # -------------------------------------------------------------------------
    # Scenario 10: Enforcing hard security and approval constraints
    # -------------------------------------------------------------------------
    def test_10_enforcing_hard_security_and_approval_constraints(self):
        backlog = self.bridge.backlog
        unauthorized_init = EngineeringInitiative(
            id="auth_boundary",
            title="Kernel Security Protocol Mod",
            initiative_type=InitiativeType.MACRO_REFACTORING,
            budget_cost=20.0,
            effort_units=2.0,
            expected_benefit=200.0,
            requires_approval=True,
            approval_token=None,  # Missing human authorization token
        )
        backlog.add_initiative(unauthorized_init)

        eval_res, roadmap = self.bridge.create_and_evaluate_portfolio(
            portfolio_id="port_auth",
            max_budget=100.0,
            max_effort=10.0,
        )

        # High score does not bypass required approval
        assert "auth_boundary" in eval_res.rejected_initiatives

        # If forced into roadmap, authorization step must halt
        roadmap.selected_initiatives = ["auth_boundary"]
        with pytest.raises(UnauthorizedInitiativeError):
            self.bridge.authorize_roadmap(roadmap)
        assert roadmap.status == "AWAITING_APPROVAL"

    # -------------------------------------------------------------------------
    # Scenario 11: Producing deterministic decisions for identical inputs
    # -------------------------------------------------------------------------
    def test_11_deterministic_decisions_for_identical_inputs(self):
        backlog = self.bridge.backlog
        for idx in range(6):
            backlog.add_initiative(
                EngineeringInitiative(
                    id=f"init_{idx}",
                    title=f"Task {idx}",
                    initiative_type=InitiativeType.ARCHITECTURAL_OPTIMIZATION,
                    budget_cost=15.0 + (idx % 3) * 5.0,
                    effort_units=1.5,
                    expected_benefit=40.0 + idx * 10.0,
                )
            )

        res1, road1 = self.bridge.create_and_evaluate_portfolio("det_1", 50.0, 10.0)
        res2, road2 = self.bridge.create_and_evaluate_portfolio("det_2", 50.0, 10.0)

        assert res1.selected_initiatives == res2.selected_initiatives
        assert res1.net_utility == res2.net_utility
        assert [it.initiative_id for it in road1.schedule.items] == [it.initiative_id for it in road2.schedule.items]

    # -------------------------------------------------------------------------
    # Scenario 12: Handling uncertainty in expected benefits
    # -------------------------------------------------------------------------
    def test_12_handling_uncertainty_in_expected_benefits(self):
        # Cand A: High speculative benefit (150) but low confidence (0.2) -> expected = 30
        # Cand B: Moderate benefit (70) with high confidence (0.95) -> expected = 66.5
        cand_a = EngineeringInitiative(
            id="speculative",
            title="Speculative AI Optim",
            initiative_type=InitiativeType.ARCHITECTURAL_OPTIMIZATION,
            budget_cost=20.0,
            effort_units=2.0,
            expected_benefit=150.0,
            confidence=0.2,
        )
        cand_b = EngineeringInitiative(
            id="grounded",
            title="Empirically Proven Cache",
            initiative_type=InitiativeType.ARCHITECTURAL_OPTIMIZATION,
            budget_cost=20.0,
            effort_units=2.0,
            expected_benefit=70.0,
            confidence=0.95,
        )
        backlog = self.bridge.backlog
        backlog.add_initiative(cand_a)
        backlog.add_initiative(cand_b)

        eval_res, _ = self.bridge.create_and_evaluate_portfolio("port_uncert", 25.0, 5.0)
        assert eval_res.selected_initiatives == ["grounded"], "Grounded candidate with higher expected utility must be chosen"

    # -------------------------------------------------------------------------
    # Scenario 13: Avoiding double-counting of overlapping benefits
    # -------------------------------------------------------------------------
    def test_13_avoiding_double_counting_overlapping_benefits(self):
        # Two initiatives that both target the same problem on the same file
        init1 = EngineeringInitiative(
            id="overlap_1",
            title="Fix DB Latency Part A",
            initiative_type=InitiativeType.ARCHITECTURAL_OPTIMIZATION,
            affected_components=["backend/db.py"],
            budget_cost=15.0,
            effort_units=1.5,
            expected_benefit=100.0,
            confidence=1.0,
        )
        init2 = EngineeringInitiative(
            id="overlap_2",
            title="Fix DB Latency Part B",
            initiative_type=InitiativeType.ARCHITECTURAL_OPTIMIZATION,
            affected_components=["backend/db.py"],
            budget_cost=15.0,
            effort_units=1.5,
            expected_benefit=100.0,
            confidence=1.0,
        )
        independent = EngineeringInitiative(
            id="indep_service",
            title="Fix Auth Service",
            initiative_type=InitiativeType.TECHNICAL_DEBT_REMEDIATION,
            affected_components=["backend/auth.py"],
            budget_cost=15.0,
            effort_units=1.5,
            expected_benefit=95.0,
            confidence=1.0,
        )

        backlog = self.bridge.backlog
        backlog.add_initiative(init1)
        backlog.add_initiative(init2)
        backlog.add_initiative(independent)

        # Budget of 35 allows 2 tasks. Because overlap_1 and overlap_2 have redundancy penalty,
        # (overlap_1 + independent) is superior to (overlap_1 + overlap_2).
        eval_res, _ = self.bridge.create_and_evaluate_portfolio("port_dedup", 35.0, 5.0)
        assert "indep_service" in eval_res.selected_initiatives
        assert len(eval_res.selected_initiatives) == 2

    # -------------------------------------------------------------------------
    # Scenario 14: Scheduling tasks using existing agent and resource interfaces
    # -------------------------------------------------------------------------
    def test_14_scheduling_tasks_using_resource_interfaces(self):
        scheduler = CapacityScheduler(max_concurrency=2)
        inits = {
            f"task_{i}": EngineeringInitiative(
                id=f"task_{i}",
                title=f"Task {i}",
                initiative_type=InitiativeType.TECHNICAL_DEBT_REMEDIATION,
                affected_components=[f"comp_{i}.py"],
                effort_units=2.0,
            ) for i in range(4)
        }
        schedule = scheduler.build_schedule("port_sched", list(inits.keys()), inits)

        assert schedule.total_waves == 2
        wave0 = [it for it in schedule.items if it.wave_index == 0]
        wave1 = [it for it in schedule.items if it.wave_index == 1]
        assert len(wave0) == 2
        assert len(wave1) == 2
        assert {it.assigned_agent for it in wave0} == {"agent-1", "agent-2"}

    # -------------------------------------------------------------------------
    # Scenario 15: Preventing unauthorized concurrent execution (claim conflicts)
    # -------------------------------------------------------------------------
    def test_15_preventing_unauthorized_concurrent_execution(self):
        graph = DependencyGraphEngine()
        init_a = EngineeringInitiative(
            id="mod_a",
            title="Modify Storage Engine",
            initiative_type=InitiativeType.MACRO_REFACTORING,
            affected_components=["backend/storage.py"],
            effort_units=1.0,
        )
        init_b = EngineeringInitiative(
            id="mod_b",
            title="Storage Connection Pool Refactor",
            initiative_type=InitiativeType.ARCHITECTURAL_OPTIMIZATION,
            affected_components=["backend/storage.py"],  # Common resource
            effort_units=1.0,
        )
        graph.add_initiative(init_a)
        graph.add_initiative(init_b)

        scheduler = CapacityScheduler(graph_engine=graph, max_concurrency=2)
        schedule = scheduler.build_schedule(
            "port_claim", ["mod_a", "mod_b"], {"mod_a": init_a, "mod_b": init_b}
        )

        # mod_a and mod_b touch backend/storage.py, so they cannot be in the same wave
        wave_a = next(it.wave_index for it in schedule.items if it.initiative_id == "mod_a")
        wave_b = next(it.wave_index for it in schedule.items if it.initiative_id == "mod_b")
        assert wave_a != wave_b, "Conflicting component modifications must be placed in separate waves"

    # -------------------------------------------------------------------------
    # Scenario 16: Replanning after an initiative fails
    # -------------------------------------------------------------------------
    def test_16_replanning_after_initiative_fails(self):
        replanner = self.bridge.replanner
        inits = {
            "step_1": EngineeringInitiative(id="step_1", title="Step 1", initiative_type=InitiativeType.MACRO_REFACTORING, budget_cost=10.0),
            "step_2": EngineeringInitiative(id="step_2", title="Step 2", initiative_type=InitiativeType.ARCHITECTURAL_OPTIMIZATION, budget_cost=10.0),
            "step_3": EngineeringInitiative(id="step_3", title="Step 3", initiative_type=InitiativeType.TECHNICAL_DEBT_REMEDIATION, budget_cost=10.0),
        }
        current_roadmap = PortfolioRoadmap(
            roadmap_id="rdm_fail",
            version="v1.0.0",
            portfolio_id="port_fail",
            selected_initiatives=["step_1", "step_2", "step_3"],
            rejected_initiatives=[],
            schedule=ExecutionSchedule("sched_f", "port_fail", []),
        )

        new_roadmap, event = replanner.replan_on_failure(
            current_roadmap=current_roadmap,
            failed_initiative_id="step_2",
            initiatives=inits,
            total_budget=50.0,
            total_effort=10.0,
            error_reason="Unit tests failed after patch application",
        )

        assert new_roadmap.version == "v1.1.0"
        assert event.trigger_type == ReplanningTriggerType.INITIATIVE_FAILURE
        assert event.failed_initiative_id == "step_2"
        assert inits["step_2"].state == InitiativeState.FAILED

    # -------------------------------------------------------------------------
    # Scenario 17: Preserving completed work during replanning
    # -------------------------------------------------------------------------
    def test_17_preserving_completed_work_during_replanning(self):
        replanner = self.bridge.replanner
        inits = {
            "step_1": EngineeringInitiative(
                id="step_1", title="Step 1", initiative_type=InitiativeType.MACRO_REFACTORING,
                state=InitiativeState.COMPLETED, actual_benefit=85.0, actual_cost=10.0
            ),
            "step_2": EngineeringInitiative(
                id="step_2", title="Step 2", initiative_type=InitiativeType.ARCHITECTURAL_OPTIMIZATION,
                state=InitiativeState.EXECUTING, budget_cost=10.0
            ),
            "step_3": EngineeringInitiative(
                id="step_3", title="Step 3", initiative_type=InitiativeType.TECHNICAL_DEBT_REMEDIATION,
                state=InitiativeState.PROPOSED, budget_cost=10.0
            ),
        }
        current_roadmap = PortfolioRoadmap(
            roadmap_id="rdm_pres",
            version="v1.0.0",
            portfolio_id="port_pres",
            selected_initiatives=["step_1", "step_2", "step_3"],
            rejected_initiatives=[],
            schedule=ExecutionSchedule("sched_p", "port_pres", []),
        )

        new_roadmap, event = replanner.replan_on_failure(
            current_roadmap=current_roadmap,
            failed_initiative_id="step_2",
            initiatives=inits,
            total_budget=50.0,
            total_effort=10.0,
        )

        assert "step_1" in event.preserved_initiatives
        assert "step_1" in new_roadmap.selected_initiatives
        assert inits["step_1"].state == InitiativeState.COMPLETED
        assert inits["step_1"].actual_benefit == 85.0

    # -------------------------------------------------------------------------
    # Scenario 18: Invalidating stale downstream evidence
    # -------------------------------------------------------------------------
    def test_18_invalidating_stale_downstream_evidence(self):
        replanner = self.bridge.replanner
        graph = replanner.graph_engine

        init_up = EngineeringInitiative(
            id="init_up", title="Upstream Refactor",
            initiative_type=InitiativeType.MACRO_REFACTORING,
            affected_components=["backend/core.py"],
        )
        init_down = EngineeringInitiative(
            id="init_down", title="Downstream Optimization",
            initiative_type=InitiativeType.ARCHITECTURAL_OPTIMIZATION,
            affected_components=["backend/client.py"],
            prerequisites=["init_up"],
            evidence=EvidenceProvenance(source_phase="Phase 74", is_valid=True),
        )
        graph.add_initiative(init_up)
        graph.add_initiative(init_down)

        inits = {"init_up": init_up, "init_down": init_down}
        roadmap = PortfolioRoadmap(
            roadmap_id="rdm_ev", version="v1.0.0", portfolio_id="p",
            selected_initiatives=["init_up", "init_down"], rejected_initiatives=[],
            schedule=ExecutionSchedule("s", "p", []),
        )

        new_roadmap, event = replanner.replan_on_failure(
            current_roadmap=roadmap,
            failed_initiative_id="init_up",
            initiatives=inits,
            total_budget=50.0,
            total_effort=10.0,
        )

        assert inits["init_down"].evidence.is_valid is False
        assert inits["init_down"].state == InitiativeState.DEFERRED

    # -------------------------------------------------------------------------
    # Scenario 19: Recovering safely from interrupted orchestration
    # -------------------------------------------------------------------------
    def test_19_recovering_safely_from_interrupted_orchestration(self):
        store = PortfolioStore(base_dir=self.temp_dir)
        inits = {
            "init_c": EngineeringInitiative(id="init_c", title="Completed", initiative_type=InitiativeType.TECHNICAL_DEBT_REMEDIATION, state=InitiativeState.COMPLETED),
            "init_hang": EngineeringInitiative(id="init_hang", title="Hanging in-flight", initiative_type=InitiativeType.MACRO_REFACTORING, state=InitiativeState.EXECUTING),
        }
        store.save_initiatives(inits)

        # Crash recovery without authoritative confirmation
        recovered = store.reconcile_and_recover(authoritative_checker=None)
        assert recovered["init_c"].state == InitiativeState.COMPLETED
        # Must not resume simply because it was persisted as EXECUTING
        assert recovered["init_hang"].state == InitiativeState.FAILED
        assert "INTERRUPTED_EXECUTION" in recovered["init_hang"].error_message

    # -------------------------------------------------------------------------
    # Scenario 20: Reconciling planned, executing, and actually completed initiatives
    # -------------------------------------------------------------------------
    def test_20_reconciling_planned_executing_and_completed(self):
        store = PortfolioStore(base_dir=self.temp_dir)
        inits = {
            "init_done": EngineeringInitiative(id="init_done", title="Done", initiative_type=InitiativeType.MACRO_REFACTORING, state=InitiativeState.EXECUTING),
        }
        store.save_initiatives(inits)

        # Authoritative checker confirms it actually completed in Phase 73
        checker = lambda i_id: InitiativeState.COMPLETED if i_id == "init_done" else InitiativeState.FAILED
        recovered = store.reconcile_and_recover(authoritative_checker=checker)
        assert recovered["init_done"].state == InitiativeState.COMPLETED

    # -------------------------------------------------------------------------
    # Scenario 21: Measuring portfolio-level outcomes against a valid baseline
    # -------------------------------------------------------------------------
    def test_21_measuring_portfolio_level_outcomes(self):
        tracker = PortfolioMetricsTracker()
        inits = {
            "task_1": EngineeringInitiative(
                id="task_1", title="Task 1", initiative_type=InitiativeType.MACRO_REFACTORING,
                state=InitiativeState.COMPLETED, expected_benefit=50.0, confidence=1.0,
                actual_benefit=52.0, actual_cost=10.0, actual_duration=30.0
            ),
            "task_2": EngineeringInitiative(
                id="task_2", title="Task 2", initiative_type=InitiativeType.ARCHITECTURAL_OPTIMIZATION,
                state=InitiativeState.COMPLETED, expected_benefit=80.0, confidence=1.0,
                actual_benefit=85.0, actual_cost=20.0, actual_duration=45.0
            ),
        }

        metrics = tracker.compute_portfolio_metrics(
            portfolio_id="port_metrics",
            initiatives=inits,
            allocated_budget=50.0,
            estimated_duration=80.0,
        )

        assert metrics.completed_initiatives == 2
        assert metrics.failed_initiatives == 0
        assert metrics.realized_benefit == 137.0
        assert metrics.budget_consumed == 30.0
        assert metrics.roi_ratio > 4.0
        assert metrics.verification_pass_rate == 1.0

    # -------------------------------------------------------------------------
    # Scenario 22: Avoiding duplicate execution after restart
    # -------------------------------------------------------------------------
    def test_22_avoiding_duplicate_execution_after_restart(self):
        backlog = self.bridge.backlog
        init = EngineeringInitiative(
            id="done_already",
            title="Already Executed Task",
            initiative_type=InitiativeType.MACRO_REFACTORING,
            state=InitiativeState.COMPLETED,
            budget_cost=20.0,
            effort_units=2.0,
        )
        backlog.add_initiative(init)

        # Scheduler must not schedule already COMPLETED initiatives
        scheduler = CapacityScheduler()
        schedule = scheduler.build_schedule("p", [], {"done_already": init})
        assert len(schedule.items) == 0

    # -------------------------------------------------------------------------
    # Scenario 23: Handling a new initiative that changes the critical path
    # -------------------------------------------------------------------------
    def test_23_new_initiative_changes_critical_path(self):
        graph = DependencyGraphEngine()
        init_a = EngineeringInitiative(id="a", title="A", initiative_type=InitiativeType.MACRO_REFACTORING, effort_units=2.0)
        init_b = EngineeringInitiative(id="b", title="B", initiative_type=InitiativeType.MACRO_REFACTORING, effort_units=3.0, prerequisites=["a"])
        init_c = EngineeringInitiative(id="c", title="C (Short Path)", initiative_type=InitiativeType.TECHNICAL_DEBT_REMEDIATION, effort_units=1.0)
        graph.add_initiative(init_a)
        graph.add_initiative(init_b)
        graph.add_initiative(init_c)

        scheduler = CapacityScheduler(graph_engine=graph)
        sched1 = scheduler.build_schedule("p1", ["a", "b", "c"], {"a": init_a, "b": init_b, "c": init_c})
        assert sched1.critical_path == ["a", "b"]

        # Now add new initiative d that depends on b and takes 10 effort units
        init_d = EngineeringInitiative(id="d", title="D (Heavy)", initiative_type=InitiativeType.ARCHITECTURAL_OPTIMIZATION, effort_units=10.0, prerequisites=["b"])
        graph.add_initiative(init_d)
        sched2 = scheduler.build_schedule("p2", ["a", "b", "c", "d"], {"a": init_a, "b": init_b, "c": init_c, "d": init_d})
        assert sched2.critical_path == ["a", "b", "d"]

    # -------------------------------------------------------------------------
    # Scenario 24: Preventing infinite replanning loops
    # -------------------------------------------------------------------------
    def test_24_preventing_infinite_replanning_loops(self):
        replanner = PortfolioReplanningEngine(max_replan_attempts=2)
        inits = {
            "failing_task": EngineeringInitiative(id="failing_task", title="Always Fails", initiative_type=InitiativeType.MACRO_REFACTORING)
        }
        roadmap = PortfolioRoadmap("rdm_loop", "v1.0.0", "p", ["failing_task"], [], ExecutionSchedule("s", "p", []))

        # Replan 1
        roadmap, _ = replanner.replan_on_failure(roadmap, "failing_task", inits, 100.0, 10.0)
        # Replan 2
        roadmap, _ = replanner.replan_on_failure(roadmap, "failing_task", inits, 100.0, 10.0)

        # Replan 3 exceeds max_replan_attempts (2) -> must raise ReplanningLoopError
        with pytest.raises(ReplanningLoopError):
            replanner.replan_on_failure(roadmap, "failing_task", inits, 100.0, 10.0)

    # -------------------------------------------------------------------------
    # Scenario 25: Preserving release-governance boundaries
    # -------------------------------------------------------------------------
    def test_25_preserving_release_governance_boundaries(self):
        backlog = self.bridge.backlog
        release_gate_init = EngineeringInitiative(
            id="prod_release_candidate",
            title="Core Payment Pipeline Migration",
            initiative_type=InitiativeType.MACRO_REFACTORING,
            requires_approval=True,
            approval_token=None,  # No token
            budget_cost=10.0,
            effort_units=1.0,
            expected_benefit=300.0,
        )
        backlog.add_initiative(release_gate_init)

        eval_res, roadmap = self.bridge.create_and_evaluate_portfolio(
            portfolio_id="port_release_gov",
            max_budget=50.0,
            max_effort=10.0,
        )

        assert "prod_release_candidate" in eval_res.rejected_initiatives

        # When authorized token is supplied, candidate is accepted
        release_gate_init.approval_token = "TOKEN_RELEASE_APPROVED_SEC_2026"
        eval_res_ok, roadmap_ok = self.bridge.create_and_evaluate_portfolio(
            portfolio_id="port_release_gov_ok",
            max_budget=50.0,
            max_effort=10.0,
        )
        assert "prod_release_candidate" in eval_res_ok.selected_initiatives
        assert self.bridge.authorize_roadmap(roadmap_ok) is True
        assert roadmap_ok.status == "AUTHORIZED"
