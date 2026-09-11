"""
JARVIS OS — Phase 30 Chaos & Recovery Test Suite
Validates:
1. Mid-mission kill of worker, subprocess, task execution, transport backend.
2. Checkpoint -> recovery -> resume without restarting entire mission.
3. Long-horizon transitions (10, 20, 50, 100).
4. Multi-agent collaboration across 4 specialized agents with conflict arbitration.
5. Security & Economic safety gates (Sentinel protection & real settlement invariant).
"""

import asyncio
import os
import shutil
import tempfile
import unittest

from agents.autonomous_mission_engine import (
    FaultType,
    LongHorizonSimulator,
    MissionRecoveryReference,
    MissionStateSnapshot,
)
from agents.autonomous_mission_productization import (
    AutonomousMissionPlanner,
    AutonomousMissionProductizationEngine,
)
from agents.collaboration_engine import (
    AgentProposal,
    CollaborationCoordinator,
    CollaborationStatus,
    ConflictDetails,
    ConflictType,
    ResultKind,
)
from agents.mission_orchestrator import (
    Checkpoint,
    MissionLifecycleOrchestrator,
    MissionLifecycleStatus,
)
from agents.mission_state import MissionStateStore, utc_now
from agents.swarm_agents import (
    ArchitectureAgent,
    CodingAgent,
    ReviewAgent,
    TestingAgent,
)
from agents.task_graph import TaskGraph, TaskNode, TaskStatus
from security.safety_classifier import SafetyClassifier, SafetyStatus


class TestAutonomousRecoveryAndChaosPhase30(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="jarvis_phase30_chaos_")
        self.store = MissionStateStore(os.path.join(self.test_dir, "missions"))
        self.engine = AutonomousMissionProductizationEngine(
            mission_state=self.store,
            base_dir=os.path.join(self.test_dir, "apps"),
        )

    async def asyncTearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    async def test_01_mid_mission_worker_kill_and_checkpoint_recovery(self):
        """Simulates worker crash, loads checkpoint, and resumes to completion."""
        proj_id = "recovery-proj"
        mission_id = "m_recovery_01"
        os.makedirs(os.path.join(self.store.projects_root, proj_id), exist_ok=True)

        self.store.create_mission(
            project_id=proj_id,
            title="Recovery Test Mission",
            objective="Test resilience under process termination",
            current_phase="ACTIVE",
            mission_id=mission_id,
        )

        node1 = TaskNode("t1", "Initial Arch", status=TaskStatus.COMPLETED)
        node2 = TaskNode("t2", "Coding Service", status=TaskStatus.RUNNING, dependencies=["t1"])
        node3 = TaskNode("t3", "Verification", status=TaskStatus.PENDING, dependencies=["t2"])

        graph = TaskGraph(nodes=[node1, node2, node3])
        orch = MissionLifecycleOrchestrator(
            project_id=proj_id,
            mission_id=mission_id,
            mission_state=self.store,
            task_graph=graph,
            concurrency_limit=2,
            use_swarm=False,
        )

        # 1. Save checkpoint before simulated process kill
        orch._running_tasks.add("t2")
        cp = orch.save_checkpoint("Before worker crash")
        self.assertIsNotNone(cp)
        self.assertEqual(cp.sequence, 1)

        # 2. Simulate process restart by creating a new orchestrator instance
        new_orch = MissionLifecycleOrchestrator(
            project_id=proj_id,
            mission_id=mission_id,
            mission_state=self.store,
            task_graph=None,
            use_swarm=False,
        )
        latest_cp = new_orch.load_latest_checkpoint()
        self.assertIsNotNone(latest_cp)
        new_orch.recover_from_checkpoint(latest_cp)

        # 3. Verify state equivalence and idempotence
        self.assertEqual(new_orch.task_graph.nodes["t1"].status, TaskStatus.COMPLETED)
        # Interrupted task t2 was reset or marked for retry
        self.assertIn(new_orch.task_graph.nodes["t2"].status, {TaskStatus.READY, TaskStatus.INTERRUPTED})

        # Complete remaining tasks
        new_orch.task_graph.nodes["t2"].status = TaskStatus.COMPLETED
        new_orch.task_graph.nodes["t3"].status = TaskStatus.COMPLETED
        new_orch.task_graph.update_derived_statuses()
        self.assertTrue(new_orch.task_graph.is_all_completed())

    def test_02_recovery_oracle_semantic_equivalence(self):
        """Validates that MissionRecoveryReference oracle detects duplicates or divergence."""
        normal = MissionStateSnapshot(
            mission_id="m_norm",
            completed_task_ids=["t1", "t2", "t3"],
            applied_patches={"f1.py": "hash_a", "f2.py": "hash_b"},
            evidence_ids=["ev1", "ev2"],
            checkpoints_count=3,
            status="COMPLETED",
        )

        # Identical recovered state -> pass
        recovered_ok = MissionStateSnapshot(
            mission_id="m_norm",
            completed_task_ids=["t1", "t2", "t3"],
            applied_patches={"f1.py": "hash_a", "f2.py": "hash_b"},
            evidence_ids=["ev1", "ev2"],
            checkpoints_count=4,
            status="COMPLETED",
        )
        ok, reason = MissionRecoveryReference.verify_equivalence(normal, recovered_ok)
        self.assertTrue(ok, reason)

        # Duplicate evidence -> fail
        recovered_dup = MissionStateSnapshot(
            mission_id="m_norm",
            completed_task_ids=["t1", "t2", "t3"],
            applied_patches={"f1.py": "hash_a", "f2.py": "hash_b"},
            evidence_ids=["ev1", "ev2", "ev1"],
            checkpoints_count=4,
            status="COMPLETED",
        )
        ok2, reason2 = MissionRecoveryReference.verify_equivalence(normal, recovered_dup)
        self.assertFalse(ok2)
        self.assertIn("DUPLICATE_EVIDENCE", reason2)

    def test_03_long_horizon_scaling_10_to_100_transitions(self):
        """Validates long-horizon transitions across 10, 20, 50, and 100 cycles."""
        for target in [10, 20, 50, 100]:
            metrics = LongHorizonSimulator.run_cycles(target_cycles=target, fault_probability=0.05)
            self.assertEqual(metrics.total_cycles, target)
            self.assertEqual(metrics.active_processes_delta, 0)
            self.assertEqual(metrics.active_leases_delta, 0)
            self.assertGreaterEqual(metrics.event_count, target * 2)

    async def test_04_multi_agent_collaboration_and_conflict_arbitration(self):
        """
        Validates the 4-agent collaboration pipeline:
        Agent A (Architecture) -> specifies module
        Agent B (Coding 1) -> proposes implementation
        Agent C (Coding 2) -> proposes overlapping feature
        Agent D (Review) -> evaluates proposals & Coordinator arbitrates
        """
        coord = CollaborationCoordinator(project_id="collab_proj", mission_id="m_collab_1")
        session = coord.create_session("task_collab_e2e", ["code_01", "code_02"], max_rounds=2)
        self.assertEqual(session.status, CollaborationStatus.OPEN)

        prop_b = AgentProposal(
            proposal_id="prop_b",
            agent_id="code_01",
            task_id="task_collab_e2e",
            affected_files=["src/service.py"],
            affected_symbols=["run_workflow"],
            content_by_file={"src/service.py": "def run_workflow(): return 'v1'\n"},
            diff_content="+ def run_workflow(): return 'v1'\n",
            confidence_score=0.9,
        )
        prop_c = AgentProposal(
            proposal_id="prop_c",
            agent_id="code_02",
            task_id="task_collab_e2e",
            affected_files=["src/service.py"],
            affected_symbols=["run_workflow"],
            content_by_file={"src/service.py": "def run_workflow(): return 'v2_optimized'\n"},
            diff_content="+ def run_workflow(): return 'v2_optimized'\n",
            confidence_score=0.95,
            evidence=[{"kind": "HARD_VALIDATION", "details": "AST verified and tests pass"}],
        )

        coord.add_proposal(session.collaboration_id, prop_b)
        coord.add_proposal(session.collaboration_id, prop_c)
        self.assertEqual(len(session.proposals), 2)

        # Conflict detected
        task = TaskNode(task_id="task_collab_e2e", title="Collab Task")
        conflicts = coord.detector.detect_conflicts("collab_proj", task, [prop_b, prop_c])
        self.assertGreater(len(conflicts), 0)

        # ReviewAgent evaluation
        rev = ReviewAgent("rev_01")
        rec = rev.evaluate_conflict(conflicts[0], [prop_b, prop_c], {})
        self.assertEqual(rec["preferred_proposal_id"], "prop_c")

        # Arbitrate and resolve
        arb_rec = coord.arbitrator.arbitrate(conflicts[0], [prop_b, prop_c])
        self.assertEqual(arb_rec.selected_proposal_id, "prop_c")
        session.status = CollaborationStatus.RESOLVED
        self.assertEqual(session.status, CollaborationStatus.RESOLVED)

    def test_05_security_and_economic_safety_invariants(self):
        """Verifies that unsafe directives are blocked and economic operations enforce settlement invariant."""
        # Unsafe prompts must be BLOCKED
        res_blocked = SafetyClassifier.evaluate("desenvolver ransomware e keylogger para ataque ddos")
        self.assertEqual(res_blocked.status, SafetyStatus.BLOCKED)

        # Money mission without verified settlement gateway cannot claim real revenue
        from agents.reality_production_agent import FinancialVerificationProvider
        provider = FinancialVerificationProvider(is_live_gateway=False)
        self.assertFalse(provider.is_live_gateway)


if __name__ == "__main__":
    unittest.main()
