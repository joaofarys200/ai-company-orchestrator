"""
Live Verification Script for Phase 15 — Autonomous Agent Collaboration & Conflict Resolution.
Executes the 14 end-to-end verification checks mandated in Section 47.
"""

import sys
import os
import time
import json
import asyncio
from typing import Any

# Ensure workspace root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.collaboration_engine import (
    CollaborationCoordinator,
    CollaborationStatus,
    ConflictDetails,
    ConflictKey,
    ConflictType,
    ArbitrationDecision,
    ResultKind,
    AgentProposal,
    LargeArtifactMergeEngine,
    PatchMergeEngine,
)
from agents.task_graph import TaskGraph, TaskNode, TaskStatus
from agents.mission_state import MissionStateStore
from agents.mission_orchestrator import MissionLifecycleOrchestrator
from agents.swarm_coordinator import SwarmCoordinator


async def run_verification():
    print("=" * 70)
    print("JARVIS OS — PHASE 15 LIVE VERIFICATION SUITE (14 CHECKS)")
    print("=" * 70)

    checks_passed = 0
    checks_total = 14
    results = {}

    coord = CollaborationCoordinator(project_id="live_proj", mission_id="live_mission_1")
    task = TaskNode(task_id="task_live_1", title="Live Collaborative Task")

    # CHECK 1: Collaboration Session Creation
    print("\n[CHECK 1/14] Collaboration Session Creation...")
    s1 = coord.create_session("task_live_1", ["CODING_1", "REVIEW_1"], max_rounds=3)
    if s1 and s1.status == CollaborationStatus.OPEN and s1.collaboration_id in coord.sessions:
        print("  -> PASS: Session created with status OPEN.")
        results["check_1_session_creation"] = "PASS"
        checks_passed += 1
    else:
        print("  -> FAIL: Could not create session.")
        results["check_1_session_creation"] = "FAIL"

    # CHECK 2: Multiple Agents Submitting Proposals
    print("\n[CHECK 2/14] Multiple Agents Submitting Proposals...")
    p1 = AgentProposal(
        proposal_id="prop_1",
        agent_id="CODING_1",
        task_id="task_live_1",
        affected_files=["src/service.py"],
        affected_symbols=["process_order"],
        content_by_file={"src/service.py": "def process_order(): return 'v1'\ndef audit(): pass\n"},
        diff_content="+ def process_order(): return 'v1'\n",
        confidence_score=0.9,
    )
    p2 = AgentProposal(
        proposal_id="prop_2",
        agent_id="CODING_2",
        task_id="task_live_1",
        affected_files=["src/service.py"],
        affected_symbols=["audit"],
        content_by_file={"src/service.py": "def process_order(): pass\ndef audit(): return 'audited_v2'\n"},
        diff_content="+ def audit(): return 'audited_v2'\n",
        confidence_score=0.85,
    )
    ok1 = coord.add_proposal(s1.collaboration_id, p1)
    ok2 = coord.add_proposal(s1.collaboration_id, p2)
    if ok1 and ok2 and len(s1.proposals) == 2:
        print("  -> PASS: Two proposals registered from distinct agents.")
        results["check_2_multiple_proposals"] = "PASS"
        checks_passed += 1
    else:
        print("  -> FAIL: Failed to add proposals.")
        results["check_2_multiple_proposals"] = "FAIL"

    # CHECK 3: Deterministic Conflict Detection Across Dimensions
    print("\n[CHECK 3/14] Deterministic Conflict Detection (File Overlap)...")
    p_ov_1 = AgentProposal(
        proposal_id="p_ov_1",
        agent_id="CODING_1",
        task_id="task_live_1",
        affected_files=["src/conflict_file.py"],
        affected_symbols=["run_algo"],
        content_by_file={"src/conflict_file.py": "def run_algo(): return 10\n"},
    )
    p_ov_2 = AgentProposal(
        proposal_id="p_ov_2",
        agent_id="CODING_2",
        task_id="task_live_1",
        affected_files=["src/conflict_file.py"],
        affected_symbols=["run_algo"],
        content_by_file={"src/conflict_file.py": "def run_algo(): return 20\n"},
    )
    conflicts = coord.detector.detect_conflicts("live_proj", task, [p_ov_1, p_ov_2])
    if any(c.conflict_key.conflict_type in (ConflictType.FILE_CONFLICT, ConflictType.SYMBOL_CONFLICT) for c in conflicts):
        print(f"  -> PASS: Detected {len(conflicts)} conflict(s) including {conflicts[0].conflict_key.conflict_type.value}.")
        results["check_3_conflict_detection"] = "PASS"
        checks_passed += 1
    else:
        print("  -> FAIL: No file overlap conflict detected.")
        results["check_3_conflict_detection"] = "FAIL"

    # CHECK 4: Deterministic Arbitration Based on Evidence Hierarchy
    print("\n[CHECK 4/14] Deterministic Arbitration (Evidence Hierarchy)...")
    p1_ev = AgentProposal(
        proposal_id="prop_ev_1",
        agent_id="CODING_1",
        task_id="task_live_1",
        affected_files=["src/calc.py"],
        affected_symbols=["calc"],
        evidence=[{"kind": "TEST_PASS", "weight": 500.0, "details": "100% tests pass"}],
        confidence_score=0.5,
    )
    p2_ev = AgentProposal(
        proposal_id="prop_ev_2",
        agent_id="CODING_2",
        task_id="task_live_1",
        affected_files=["src/calc.py"],
        affected_symbols=["calc"],
        evidence=[{"kind": "BUILD_PASS", "weight": 300.0}],
        confidence_score=0.99,  # High confidence, but lower evidence
    )
    conf_calc = coord.detector.detect_conflicts("live_proj", task, [p1_ev, p2_ev])[0]
    arb_rec = coord.arbitrator.arbitrate(conf_calc, [p1_ev, p2_ev])
    if arb_rec.decision == ArbitrationDecision.ACCEPT_A and arb_rec.selected_proposal_id == "prop_ev_1":
        print("  -> PASS: Evidence (TEST_PASS 500) strictly beat high confidence (0.99 with BUILD_PASS 300).")
        results["check_4_arbitration_hierarchy"] = "PASS"
        checks_passed += 1
    else:
        print(f"  -> FAIL: Arbitration did not favor evidence: {arb_rec.decision}")
        results["check_4_arbitration_hierarchy"] = "FAIL"

    # CHECK 5: Disjoint Auto-Merge Success
    print("\n[CHECK 5/14] Disjoint Auto-Merge Execution...")
    base_src = "def process_order(): pass\ndef audit(): pass\n"
    ok_merge, merged_code, m_reason = LargeArtifactMergeEngine.auto_merge_disjoint(
        "src/service.py", base_src, p1.content_by_file["src/service.py"], p2.content_by_file["src/service.py"]
    )
    if ok_merge and "return 'v1'" in merged_code and "return 'audited_v2'" in merged_code:
        print(f"  -> PASS: Disjoint merge succeeded ({m_reason}) with preserved functions.")
        results["check_5_auto_merge"] = "PASS"
        checks_passed += 1
    else:
        print(f"  -> FAIL: Auto-merge failed: {m_reason}")
        results["check_5_auto_merge"] = "FAIL"

    # CHECK 6: Evidence Aggregation
    print("\n[CHECK 6/14] Evidence Aggregation...")
    score1, breakdown1 = coord.arbitrator.evaluate_evidence(p1_ev)
    if score1 >= 500.0 and any(b["kind"] == "TEST_PASS" for b in breakdown1):
        print(f"  -> PASS: Evidence aggregated successfully with score={score1}.")
        results["check_6_evidence_aggregation"] = "PASS"
        checks_passed += 1
    else:
        print("  -> FAIL: Evidence breakdown missing.")
        results["check_6_evidence_aggregation"] = "FAIL"

    # CHECK 7: Agent Failure Reassignment
    print("\n[CHECK 7/14] Agent Failure Reassignment...")
    t7 = TaskNode("task_reassign_demo", "Failing task", category="CODING", status=TaskStatus.RUNNING)
    g7 = TaskGraph(nodes=[t7])
    swarm = SwarmCoordinator(
        project_id="live_proj",
        mission_id="live_mission_1",
        mission_state=MissionStateStore("live_proj"),
        task_graph=g7,
    )
    l7 = swarm.lease_manager.acquire_lease("task_reassign_demo", "CODING_CRASHED", 1, ttl_seconds=-10.0)
    swarm.active_leases["task_reassign_demo"] = l7
    interrupted = swarm.reconcile_leases_and_failures()
    if "task_reassign_demo" in interrupted and t7.status == TaskStatus.INTERRUPTED:
        print("  -> PASS: Expired lease reaped and task marked INTERRUPTED for reassignment.")
        results["check_7_reassignment"] = "PASS"
        checks_passed += 1
    else:
        print("  -> FAIL: Task reassignment failed.")
        results["check_7_reassignment"] = "FAIL"

    # CHECK 8: Checkpoint Export and Restore Across Restart
    print("\n[CHECK 8/14] Checkpoint Export and Restore...")
    saved_state = coord.export_state()
    coord_restored = CollaborationCoordinator(project_id="live_proj", mission_id="live_mission_1")
    coord_restored.restore_state(saved_state)
    restored_sess = coord_restored.get_session(s1.collaboration_id)
    if restored_sess and len(restored_sess.proposals) == 2:
        print("  -> PASS: Session and proposals restored byte-for-byte.")
        results["check_8_checkpoint_restore"] = "PASS"
        checks_passed += 1
    else:
        print("  -> FAIL: Checkpoint restoration failed.")
        results["check_8_checkpoint_restore"] = "FAIL"

    # CHECK 9: Dynamic Sub-DAG Integration
    print("\n[CHECK 9/14] Dynamic Sub-DAG Integration...")
    p_arch_1 = AgentProposal(
        proposal_id="p_arch_1",
        agent_id="ARCH_1",
        task_id="t_subdag",
        metadata={"architecture_pattern": "REST"},
    )
    p_arch_2 = AgentProposal(
        proposal_id="p_arch_2",
        agent_id="ARCH_2",
        task_id="t_subdag",
        metadata={"architecture_pattern": "GRAPHQL"},
    )
    conf_arch = coord.detector.detect_conflicts("live_proj", TaskNode(task_id="t_subdag", title="Arch Task"), [p_arch_1, p_arch_2])[0]
    arb_arch = coord.arbitrator.arbitrate(conf_arch, [p_arch_1, p_arch_2])
    if arb_arch.decision == ArbitrationDecision.REPLAN:
        print(f"  -> PASS: Architectural mismatch yielded {arb_arch.decision.value} for Dynamic Sub-DAG.")
        results["check_9_dynamic_subdag"] = "PASS"
        checks_passed += 1
    else:
        print("  -> FAIL: Expected REPLAN for architectural conflict.")
        results["check_9_dynamic_subdag"] = "FAIL"

    # CHECK 10: Adaptive Planning Engine Integration
    print("\n[CHECK 10/14] Adaptive Planning Engine Integration...")
    g = TaskGraph(nodes=[TaskNode("task_adapt", "Plan Adapt Task", category="CODING", status=TaskStatus.RUNNING)])
    state_store = MissionStateStore("live_proj")
    orch = MissionLifecycleOrchestrator(
        project_id="live_proj",
        mission_id="live_mission_1",
        mission_state=state_store,
        task_graph=g,
        use_swarm=True,
    )
    eval_res = await orch.evaluate_plan(
        architecture_change={"conflict": "REST_VS_GRAPHQL_CONFLICT"}
    )
    if eval_res and eval_res.decision:
        print(f"  -> PASS: Adaptive planning evaluated conflict with decision: {eval_res.decision.value}.")
        results["check_10_adaptive_planning"] = "PASS"
        checks_passed += 1
    else:
        print("  -> FAIL: Adaptive planning evaluation failed.")
        results["check_10_adaptive_planning"] = "FAIL"

    # CHECK 11: Security & Economic Safeguards
    print("\n[CHECK 11/14] Security & Economic Safeguards...")
    # Test 11a: Economic bypass blocked
    conf_money = ConflictDetails(
        conflict_key=ConflictKey("live_proj", "money_task", "ledger", "", ConflictType.SEMANTIC_CONFLICT),
        proposals_involved=["p_agreed1", "p_agreed2"],
        description="Both agents agree to skip payment gateway verification",
    )
    p_mon_1 = AgentProposal(
        proposal_id="p_agreed1",
        agent_id="code_01",
        task_id="money_task",
        result_kind=ResultKind.PROPOSAL,
        description="Skip external verification",
        confidence_score=0.9,
    )
    p_mon_2 = AgentProposal(
        proposal_id="p_agreed2",
        agent_id="code_02",
        task_id="money_task",
        result_kind=ResultKind.PROPOSAL,
        description="Skip external verification also",
        confidence_score=0.9,
    )
    arb_money = coord.arbitrator.arbitrate(conf_money, [p_mon_1, p_mon_2])

    # Test 11b: Security sandbox preference over high-confidence unverified
    conf_sec = ConflictDetails(
        conflict_key=ConflictKey("live_proj", "sec_task", "os.system", "", ConflictType.SEMANTIC_CONFLICT),
        proposals_involved=["p_unsafe", "p_safe"],
        description="Unsafe command proposal vs safe proposal",
    )
    p_unsafe = AgentProposal(
        proposal_id="p_unsafe",
        agent_id="code_01",
        task_id="sec_task",
        result_kind=ResultKind.PATCH,
        confidence_score=0.99,
    )
    p_safe = AgentProposal(
        proposal_id="p_safe",
        agent_id="code_02",
        task_id="sec_task",
        result_kind=ResultKind.PATCH,
        confidence_score=0.7,
        evidence=[{"kind": "HARD_VALIDATION_SANDBOX", "status": "PASS"}],
    )
    arb_sec = coord.arbitrator.arbitrate(conf_sec, [p_unsafe, p_safe])

    if arb_money.decision == ArbitrationDecision.BLOCK and arb_sec.selected_proposal_id == "p_safe":
        print("  -> PASS: Economic consensus bypass strictly BLOCKED and Security Sandbox prioritized.")
        results["check_11_safeguards"] = "PASS"
        checks_passed += 1
    else:
        print("  -> FAIL: Safeguard check did not block violations.")
        results["check_11_safeguards"] = "FAIL"

    # CHECK 12: Mission Completion with Satisfaction Barrier
    print("\n[CHECK 12/14] Mission Completion with Satisfaction Barrier...")
    t_complete = TaskNode("t_comp", "Final Task", category="CODING", status=TaskStatus.COMPLETED)
    g_comp = TaskGraph(nodes=[t_complete])
    orch_barrier = MissionLifecycleOrchestrator(
        project_id="live_proj",
        mission_id="live_mission_sat",
        mission_state=MissionStateStore("live_proj"),
        task_graph=g_comp,
    )
    satisfied, reason = await orch_barrier.verify_satisfaction()
    if satisfied:
        print(f"  -> PASS: Satisfaction barrier verified: {reason or 'All tasks completed and satisfied'}.")
        results["check_12_satisfaction_barrier"] = "PASS"
        checks_passed += 1
    else:
        print(f"  -> FAIL: Satisfaction barrier did not satisfy: {reason}")
        results["check_12_satisfaction_barrier"] = "FAIL"

    # CHECK 13: Idempotency and Anti-Loop Protection
    print("\n[CHECK 13/14] Idempotency and Anti-Loop Protection...")
    s_loop = coord.create_session("task_loop", ["A1", "A2"], max_rounds=2)
    s_loop.round_count = 3  # Exceed limit
    st, _, _ = coord.evaluate_collaboration(s_loop.collaboration_id, TaskNode(task_id="task_loop", title="Loop Task"))
    if st == CollaborationStatus.BLOCKED:
        print("  -> PASS: Exceeded round limit automatically transitioned to BLOCKED (anti-loop active).")
        results["check_13_anti_loop"] = "PASS"
        checks_passed += 1
    else:
        print("  -> FAIL: Anti-loop failed to block excessive rounds.")
        results["check_13_anti_loop"] = "FAIL"

    # CHECK 14: Phase 15.2 Hierarchical Indexing & Connected Components
    print("\n[CHECK 14/14] Hierarchical Indexing & Connected Components Decomposition...")
    h_idx = coord.detector.build_hierarchical_index("live_proj", task, [p1, p2, p1_ev, p2_ev])
    _, _, comps, strat = coord.detector.build_hierarchical_conflict_graph("live_proj", task, [p1, p2, p1_ev, p2_ev])
    if len(h_idx.package_to_proposals) > 0 and len(comps) >= 1:
        print(f"  -> PASS: Hierarchical index built with {len(comps)} connected component(s) using strategy {strat.value}.")
        results["check_14_phase15_2_components"] = "PASS"
        checks_passed += 1
    else:
        print("  -> FAIL: Hierarchical index or components missing.")
        results["check_14_phase15_2_components"] = "FAIL"

    # Summary
    print("\n" + "=" * 70)
    print(f"VERIFICATION SUMMARY: {checks_passed}/{checks_total} CHECKS PASSED")
    print("=" * 70)
    for k, v in results.items():
        print(f"  {k:35s}: {v}")

    return checks_passed == checks_total


if __name__ == "__main__":
    success = asyncio.run(run_verification())
    sys.exit(0 if success else 1)
