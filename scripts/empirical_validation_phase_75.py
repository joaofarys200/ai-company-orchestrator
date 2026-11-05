"""
JARVIS OS — Phase 75: Autonomous Engineering Strategy & Portfolio Orchestration
Empirical Portfolio Validation Script
Demonstrates end-to-end:
1. Baseline portfolio with heterogeneous initiatives.
2. Explicit budget and approval constraints.
3. Dependency & conflict analysis (prerequisites, component overlaps, mutual exclusions).
4. Combinatorial portfolio evaluation with synergy bonuses vs independent ranking baseline.
5. Justified execution sequence (waves, critical path).
6. Delegated execution through simulated existing engines.
7. Dynamic replan triggered by injected failure.
8. Preservation of completed work.
9. State reconciliation and auditability.
10. Machine-readable evidence written to docs/phase75_empirical_validation_evidence.json.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from typing import Dict, List, Tuple

from backend.agents.portfolio_orchestration import (
    CapacityScheduler,
    ConflictType,
    DependencyGraphEngine,
    EngineeringInitiative,
    EvidenceProvenance,
    InitiativeState,
    InitiativeType,
    PortfolioBacklog,
    PortfolioMetricsTracker,
    PortfolioOrchestrationBridge,
    PortfolioStore,
    RedundancyDefinition,
    ReplanningTriggerType,
    SynergyDefinition,
)


def run_empirical_validation() -> Dict:
    print("=" * 80)
    print("JARVIS OS — Phase 75 Empirical Portfolio Validation")
    print("=" * 80)

    temp_dir = tempfile.mkdtemp(prefix="jarvis_phase75_empirical_")
    store = PortfolioStore(base_dir=temp_dir)
    backlog = PortfolioBacklog()
    graph = DependencyGraphEngine()

    # 1. Define Heterogeneous Candidate Initiatives
    initiatives = [
        # Initiative 1: Foundation (Macro-Refactoring)
        EngineeringInitiative(
            id="INIT-01-CORE-REFACTOR",
            title="Modular Core Interface Extraction",
            initiative_type=InitiativeType.MACRO_REFACTORING,
            description="Extract decoupled interfaces from monolithic core router.",
            affected_components=["backend/router.py", "backend/interfaces.py"],
            effort_units=2.0,
            budget_cost=25.0,
            expected_benefit=40.0,
            confidence=0.95,
            evidence=EvidenceProvenance(source_phase="Phase 73", confidence=0.95),
        ),
        # Initiative 2: Architectural Optimization (Unlocked by Initiative 1)
        EngineeringInitiative(
            id="INIT-02-ASYNC-PIPELINE",
            title="Non-Blocking Dispatch Pipeline",
            initiative_type=InitiativeType.ARCHITECTURAL_OPTIMIZATION,
            description="Replace synchronous worker loop with non-blocking event streaming.",
            affected_components=["backend/pipeline.py", "backend/events.py"],
            effort_units=3.0,
            budget_cost=35.0,
            expected_benefit=130.0,
            confidence=0.90,
            prerequisites=["INIT-01-CORE-REFACTOR"],
            evidence=EvidenceProvenance(source_phase="Phase 74", confidence=0.90),
        ),
        # Initiative 3: Technical Debt Remediation (Overlaps with Initiative 1 on backend/router.py)
        EngineeringInitiative(
            id="INIT-03-DEBT-ROUTER-CLEANUP",
            title="Router Legacy Exception Handling Clean",
            initiative_type=InitiativeType.TECHNICAL_DEBT_REMEDIATION,
            description="Remove deprecated error handling shims.",
            affected_components=["backend/router.py"],
            effort_units=1.0,
            budget_cost=15.0,
            expected_benefit=35.0,
            confidence=0.95,
            evidence=EvidenceProvenance(source_phase="Phase 68/69", confidence=0.95),
        ),
        # Initiative 4: Reliability Hardening (Synergistic with Initiative 2)
        EngineeringInitiative(
            id="INIT-04-TELEMETRY-CIRCUIT-BREAKER",
            title="Adaptive Circuit Breaker & Telemetry",
            initiative_type=InitiativeType.RELIABILITY_IMPROVEMENT,
            description="Add anomaly detection and auto-throttling to dispatch pipeline.",
            affected_components=["backend/circuit_breaker.py", "backend/telemetry.py"],
            effort_units=2.0,
            budget_cost=20.0,
            expected_benefit=60.0,
            confidence=0.88,
            evidence=EvidenceProvenance(source_phase="Phase 72", confidence=0.88),
        ),
        # Initiative 5: High-Risk Unapproved Production Change (Exceeds Security Boundary)
        EngineeringInitiative(
            id="INIT-05-KERNEL-BYPASS-UNAUTH",
            title="Kernel Direct Bypass Driver",
            initiative_type=InitiativeType.ARCHITECTURAL_OPTIMIZATION,
            description="Bypass OS security checks for maximum throughput.",
            affected_components=["backend/kernel_driver.sys"],
            effort_units=4.0,
            budget_cost=40.0,
            expected_benefit=180.0,
            confidence=0.50,
            requires_approval=True,
            approval_token=None,  # Not approved!
            evidence=EvidenceProvenance(source_phase="Phase 74", confidence=0.50),
        ),
        # Initiative 6: Low-Value Redundant Utility Patch
        EngineeringInitiative(
            id="INIT-06-REDUNDANT-ROUTER-SHIM",
            title="Router Shim Optimization",
            initiative_type=InitiativeType.TECHNICAL_DEBT_REMEDIATION,
            description="Micro-tune router shim before removal.",
            affected_components=["backend/router.py"],
            effort_units=1.5,
            budget_cost=20.0,
            expected_benefit=25.0,
            confidence=0.70,
            mutual_exclusions=["INIT-01-CORE-REFACTOR"],  # Mutually exclusive with modular refactor!
        ),
    ]

    for init in initiatives:
        backlog.add_initiative(init)
        graph.add_initiative(init)

    # 2. Synergies & Redundancies Definition
    synergies = [
        SynergyDefinition(
            initiative_ids={"INIT-02-ASYNC-PIPELINE", "INIT-04-TELEMETRY-CIRCUIT-BREAKER"},
            bonus_benefit=45.0,
            description="Combining async streaming with adaptive circuit breaker eliminates backpressure faults.",
        )
    ]
    redundancies = [
        RedundancyDefinition(
            initiative_ids={"INIT-01-CORE-REFACTOR", "INIT-03-DEBT-ROUTER-CLEANUP"},
            penalty_benefit=15.0,
            description="Core refactor already restructures router exception boundaries.",
        )
    ]

    # Global Execution Constraints
    MAX_BUDGET = 90.0
    MAX_EFFORT = 8.0

    print(f"\n[STAGE 1] Ingested {len(initiatives)} candidates into unified backlog.")
    print(f"[STAGE 2] Global Constraints: Max Budget = ${MAX_BUDGET:.1f}, Max Effort = {MAX_EFFORT:.1f} units")

    # 3. Dependency & Conflict Analysis
    conflicts = graph.detect_conflicts({i.id for i in initiatives})
    print(f"\n[STAGE 3] Detected {len(conflicts)} conflict/dependency relationships:")
    for c in conflicts:
        print(f"  - [{c.conflict_type.value}] {c.description}")

    # 4. Compare Portfolio Optimization vs Baseline Independent Ranking Strategy
    # Baseline strategy: Rank by Benefit/Cost ratio greedily without synergy/prerequisite awareness
    independent_ranking = sorted(
        initiatives,
        key=lambda x: -(x.expected_benefit * x.confidence / max(1.0, x.budget_cost))
    )
    baseline_selected: List[str] = []
    baseline_cost = 0.0
    baseline_benefit = 0.0
    for cand in independent_ranking:
        if cand.requires_approval and not cand.approval_token:
            continue  # cannot take unauthorized
        if baseline_cost + cand.budget_cost <= MAX_BUDGET:
            baseline_selected.append(cand.id)
            baseline_cost += cand.budget_cost
            baseline_benefit += cand.expected_benefit * cand.confidence

    print("\n[BASELINE COMPARISON] Independent Candidate Ranking Strategy:")
    print(f"  Selected: {baseline_selected}")
    print(f"  Cost: ${baseline_cost:.1f} | Raw Expected Benefit: {baseline_benefit:.1f}")

    # Strategic Portfolio Optimization
    bridge = PortfolioOrchestrationBridge(
        store_dir=temp_dir,
        backlog=backlog,
        graph_engine=graph,
    )
    bridge.evaluator.synergies = synergies
    bridge.evaluator.redundancies = redundancies

    eval_result, roadmap = bridge.create_and_evaluate_portfolio(
        portfolio_id="PORTFOLIO-VALIDATION-F75",
        max_budget=MAX_BUDGET,
        max_effort=MAX_EFFORT,
    )

    print("\n[PORTFOLIO ORCHESTRATION] Combinatorial Portfolio Selection:")
    print(f"  Selected: {eval_result.selected_initiatives}")
    print(f"  Rejected: {eval_result.rejected_initiatives}")
    print(f"  Total Cost: ${eval_result.total_cost:.1f} / ${MAX_BUDGET:.1f}")
    print(f"  Total Effort: {eval_result.total_effort:.1f} / {MAX_EFFORT:.1f}")
    print(f"  Total Benefit (with Synergies): {eval_result.total_benefit:.1f}")
    print(f"  Synergy Bonus: +{eval_result.synergy_bonus:.1f}")
    print(f"  Net Strategic Utility: {eval_result.net_utility:.1f}")
    print(f"  Delta over Independent Baseline: +{eval_result.total_benefit - baseline_benefit:.1f} benefit")

    # Authorize roadmap
    assert bridge.authorize_roadmap(roadmap) is True
    print(f"\n[STAGE 4] Roadmap {roadmap.version} successfully authorized under governance gates.")

    # 5. Roadmap Schedule Inspection
    print(f"\n[STAGE 5] Wave-by-Wave Execution Schedule ({roadmap.schedule.total_waves} waves):")
    for wave_idx in range(roadmap.schedule.total_waves):
        items = [it for it in roadmap.schedule.items if it.wave_index == wave_idx]
        print(f"  Wave {wave_idx + 1}:")
        for it in items:
            print(f"    * {it.initiative_id} assigned to {it.assigned_agent} (Resources: {it.claimed_resources})")

    # 6. Execute Wave 1
    print("\n[STAGE 6] Executing Wave 1...")
    passed_w1, comp_w1, fail_w1 = bridge.execute_wave(roadmap, 0)
    print(f"  Wave 1 Outcome: Passed = {passed_w1}, Completed = {comp_w1}, Failed = {fail_w1}")
    assert passed_w1 is True
    assert len(comp_w1) > 0

    # 7. Inject Failure in Wave 2 to demonstrate Dynamic Replanning & Work Preservation
    print("\n[STAGE 7] Injecting Simulated Verification Failure in Wave 2...")
    # Custom executor that fails INIT-02-ASYNC-PIPELINE due to integration test failure
    def failing_executor(init: EngineeringInitiative) -> Tuple[bool, float, float, str]:
        if init.id == "INIT-02-ASYNC-PIPELINE":
            return False, 0.0, 15.0, "Integration verification failure: memory leak in stream buffer"
        return True, init.expected_benefit * init.confidence, init.budget_cost, "Verified and accepted"

    bridge.custom_executor = failing_executor
    passed_w2, comp_w2, fail_w2 = bridge.execute_wave(roadmap, 1)
    print(f"  Wave 2 Outcome: Passed = {passed_w2}, Failed = {fail_w2}")
    assert passed_w2 is False
    assert "INIT-02-ASYNC-PIPELINE" in fail_w2

    # 8. Trigger Governed Dynamic Replanning
    print("\n[STAGE 8] Triggering Dynamic Portfolio Replanning...")
    init_map = {init.id: init for init in backlog.list_initiatives()}
    new_roadmap, replan_event = bridge.replanner.replan_on_failure(
        current_roadmap=roadmap,
        failed_initiative_id="INIT-02-ASYNC-PIPELINE",
        initiatives=init_map,
        total_budget=MAX_BUDGET,
        total_effort=MAX_EFFORT,
        error_reason="Integration verification failure: memory leak in stream buffer",
    )
    bridge.store.record_replanning_event(replan_event)
    bridge.store.save_roadmap(new_roadmap)

    print(f"  Replanned to Version: {new_roadmap.version}")
    print(f"  Preserved Completed Initiatives: {replan_event.preserved_initiatives}")
    print(f"  Newly Selected for Revised Roadmap: {new_roadmap.selected_initiatives}")
    print(f"  Rationale: {new_roadmap.rationale}")

    # Verify completed work preserved
    assert set(comp_w1).issubset(set(replan_event.preserved_initiatives))
    for c_id in comp_w1:
        assert init_map[c_id].state == InitiativeState.COMPLETED

    # 9. Execute Revised Roadmap with restored healthy executor
    print("\n[STAGE 9] Executing Remaining Waves in Revised Roadmap...")
    bridge.custom_executor = None  # restore standard executor
    final_roadmap, metrics = bridge.execute_entire_roadmap(
        roadmap=new_roadmap,
        max_budget=MAX_BUDGET,
        max_effort=MAX_EFFORT,
        auto_replan=False,
    )

    # 10. Audit State Recovery
    print("\n[STAGE 10] Testing Persistence Recovery & State Reconciliation...")
    recovered_inits = bridge.store.reconcile_and_recover()
    assert len(recovered_inits) > 0
    print(f"  Successfully recovered and reconciled {len(recovered_inits)} initiatives from store.")

    # 11. Compile Machine-Readable Evidence
    evidence_payload = {
        "validation_id": "empirical_validation_phase_75",
        "timestamp": time.time(),
        "status": "VALIDATION_PASSED",
        "portfolio_id": roadmap.portfolio_id,
        "initial_roadmap_version": "v1.0.0",
        "final_roadmap_version": final_roadmap.version,
        "constraints": {
            "max_budget_usd": MAX_BUDGET,
            "max_effort_units": MAX_EFFORT,
        },
        "candidates_evaluated": len(initiatives),
        "conflicts_detected": len(conflicts),
        "conflict_types_observed": [c.conflict_type.value for c in conflicts],
        "baseline_independent_strategy": {
            "selected": baseline_selected,
            "cost": baseline_cost,
            "benefit": baseline_benefit,
        },
        "portfolio_strategy": {
            "initial_selected": eval_result.selected_initiatives,
            "initial_rejected": eval_result.rejected_initiatives,
            "initial_cost": eval_result.total_cost,
            "initial_benefit": eval_result.total_benefit,
            "synergy_bonus": eval_result.synergy_bonus,
            "net_utility": eval_result.net_utility,
        },
        "replanning_event": {
            "failed_initiative": replan_event.failed_initiative_id,
            "trigger": replan_event.trigger_type.value,
            "preserved_initiatives": replan_event.preserved_initiatives,
            "affected_downstream": replan_event.affected_initiatives,
            "new_roadmap_version": replan_event.new_version,
            "reason": replan_event.reason,
        },
        "final_metrics": metrics.to_dict(),
    }

    out_evidence_path = Path("docs/phase75_empirical_validation_evidence.json")
    with open(out_evidence_path, "w", encoding="utf-8") as f:
        json.dump(evidence_payload, f, indent=2)

    print("\n" + "=" * 80)
    print(f"[SUCCESS] Empirical validation completed. Evidence recorded at: {out_evidence_path}")
    print(f"Final Metrics Summary: {metrics.net_improvement_summary}")
    print("=" * 80)

    # Clean up temp fixture
    shutil.rmtree(temp_dir, ignore_errors=True)
    return evidence_payload


if __name__ == "__main__":
    run_empirical_validation()
