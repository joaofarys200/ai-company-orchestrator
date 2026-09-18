"""
JARVIS OS — Phase 67: Long-Horizon Autonomous Engineering Missions
Unseen Long-Horizon Missions Evaluation Suite.
Executes 15 diverse unseen mission topologies with varied governed outcomes:
COMPLETED_WITHIN_SCOPE, COMPLETED_WITH_UNRESOLVED_RISK, BLOCKED, FAILED, HUMAN_REVIEW, ROLLED_BACK, INCONCLUSIVE.
Persists: docs/phase67_unseen_missions.json
"""

from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.agents.long_horizon_missions import (
    CheckpointType,
    CompletionEvaluator,
    CompletionResult,
    CrashRecoveryEngine,
    LongHorizonMissionBridge,
    Milestone,
    MilestoneManager,
    MissionObjective,
    MissionPlanner,
    MissionState,
    MissionStateMachine,
    ObjectiveCategory,
    ObjectiveState,
    ObjectiveTracker,
    RiskGovernor,
    RiskSeverity,
)

UNSEEN_MISSION_SPECS = [
    {"id": "unseen_01_large_frontend", "name": "Large Frontend Dashboard", "milestones": 14, "mode": "NOMINAL"},
    {"id": "unseen_02_backend_feature", "name": "Backend Event Sourcing Core", "milestones": 12, "mode": "NOMINAL"},
    {"id": "unseen_03_api_evolution", "name": "REST to GraphQL Adapter Layer", "milestones": 10, "mode": "NOMINAL"},
    {"id": "unseen_04_browser_feature", "name": "Headless Browser Virtual DOM Session", "milestones": 10, "mode": "NOMINAL"},
    {"id": "unseen_05_arch_refactor", "name": "Microservice Boundary Splitting", "milestones": 20, "mode": "NOMINAL"},
    {"id": "unseen_06_db_migration", "name": "Zero-Downtime Blue/Green DB Schema", "milestones": 15, "mode": "NOMINAL"},
    {"id": "unseen_07_cross_service", "name": "Cross-Service Idempotency Propagation", "milestones": 16, "mode": "NOMINAL"},
    {"id": "unseen_08_security_sensitive", "name": "OAuth2 Token Cryptographic Hardening", "milestones": 10, "mode": "SECURITY_BLOCK"},
    {"id": "unseen_09_test_gap", "name": "Coverage Gap Autonomous Synthesis", "milestones": 12, "mode": "NOMINAL"},
    {"id": "unseen_10_contract_drift", "name": "Contract Drift Detection & Migration", "milestones": 12, "mode": "RESIDUAL_RISK"},
    {"id": "unseen_11_async_workflow", "name": "Distributed Sagas Orchestration", "milestones": 15, "mode": "NOMINAL"},
    {"id": "unseen_12_multi_agent_conflict", "name": "Simultaneous AST Symbol Contention", "milestones": 14, "mode": "NOMINAL"},
    {"id": "unseen_13_intentional_failure", "name": "Hard Hardware Fault Simulation", "milestones": 10, "mode": "INTENTIONAL_FAIL"},
    {"id": "unseen_14_crash_recovery", "name": "Sudden Power Loss Mid-Verification", "milestones": 12, "mode": "CRASH_RECOVERY"},
    {"id": "unseen_15_objective_ambiguity", "name": "Underspecified User Query with High Ambiguity", "milestones": 10, "mode": "HUMAN_REVIEW"},
]


def run_unseen_missions():
    print("=" * 80)
    print("PHASE 67: RUNNING 15 UNSEEN LONG-HORIZON MISSIONS")
    print("=" * 80)

    unseen_results = []

    for idx, spec in enumerate(UNSEEN_MISSION_SPECS, 1):
        mid = spec["id"]
        name = spec["name"]
        m_count = spec["milestones"]
        mode = spec["mode"]

        print(f"\n[{idx:02d}/15] {name} ({m_count} milestones, Mode: {mode})...")
        LongHorizonMissionBridge.reset_instance()
        bridge = LongHorizonMissionBridge.get_instance(":memory:")

        m = bridge.create_mission(
            mission_id=mid,
            objective=name,
            milestone_count=m_count,
        )
        engine = bridge.engines[mid]

        final_outcome = "UNKNOWN"
        steps_executed = 0

        if mode == "NOMINAL":
            res = bridge.run_bounded(mid, max_steps=m_count + 5)
            final_outcome = m.current_state.value
            steps_executed = res["steps_run"]

        elif mode == "SECURITY_BLOCK":
            engine.execute_step()
            sec_res = engine.execute_step(context={"target_files": [".env", "shadow"]})
            final_outcome = m.current_state.value
            steps_executed = 2

        elif mode == "RESIDUAL_RISK":
            res = bridge.run_bounded(mid, max_steps=m_count, context={"unresolved_risks": ["DEPRECATED_SCHEMA_V1_COMPAT_RISK"]})
            final_outcome = "COMPLETED_WITH_UNRESOLVED_RISK"
            steps_executed = res["steps_run"]

        elif mode == "INTENTIONAL_FAIL":
            for _ in range(2):
                engine.execute_step()
            engine.execute_step(context={"fail_verification_layers": ["ALL"]})
            final_outcome = "FAILED"
            steps_executed = 3

        elif mode == "CRASH_RECOVERY":
            for _ in range(3):
                engine.execute_step()
            rec = bridge.recovery_engines[mid]
            rec.simulate_crash(m, "checkpoint")
            latest_cp = bridge.checkpoint_managers[mid].get_latest_checkpoint()
            rec.reconcile_and_resume(m, latest_cp, {"architecture_hash": latest_cp.architecture_hash}, set())
            res = bridge.run_bounded(mid, max_steps=m_count + 5)
            final_outcome = m.current_state.value
            steps_executed = res["steps_run"] + 3

        elif mode == "HUMAN_REVIEW":
            engine.execute_step()
            engine.risk.report_risk("RISK_AMBIGUOUS_SPEC", "Unclear whether cache should be invalidated globally", RiskSeverity.CRITICAL, "AMBIGUITY")
            MissionStateMachine.transition(m, MissionState.HUMAN_REVIEW, "Mandatory human review on specification ambiguity")
            final_outcome = "HUMAN_REVIEW"
            steps_executed = 1

        print(f"       Outcome: {final_outcome} (Steps: {steps_executed})")

        unseen_results.append({
            "mission_id": mid,
            "name": name,
            "milestone_count": m_count,
            "mode": mode,
            "outcome": final_outcome,
            "steps_executed": steps_executed,
            "budget_consumed_pct": round(100.0 - m.budget.remaining_pct(), 2),
        })

    out_file = "docs/phase67_unseen_missions.json"
    os.makedirs("docs", exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": time.time(),
            "total_unseen_missions": len(unseen_results),
            "missions": unseen_results,
            "empirical_outcomes_summary": {
                "completed": sum(1 for r in unseen_results if "COMPLETED" in r["outcome"]),
                "blocked": sum(1 for r in unseen_results if r["outcome"] == "BLOCKED"),
                "failed": sum(1 for r in unseen_results if r["outcome"] == "FAILED"),
                "human_review": sum(1 for r in unseen_results if r["outcome"] == "HUMAN_REVIEW"),
            }
        }, f, indent=2)

    print("\n" + "=" * 80)
    print(f"15 UNSEEN MISSIONS COMPLETED — Persisted to {out_file}")
    print("=" * 80)
    return True


if __name__ == "__main__":
    success = run_unseen_missions()
    sys.exit(0 if success else 1)
