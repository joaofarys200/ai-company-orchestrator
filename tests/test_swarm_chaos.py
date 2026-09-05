"""
JARVIS OS — Phase 14: Chaos & Adversarial Swarm Test Suite
Tests resilience under hostile conditions: duplicate results, stale leases,
heartbeat timeouts, file contention, quota exhaustion, and permission boundaries.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import unittest

from agents.mission_orchestrator import MissionLifecycleOrchestrator, MissionLifecycleStatus
from agents.mission_state import MissionStateStore
from agents.swarm_agents import (
    ArchitectureAgent,
    BrowserAgent,
    CodingAgent,
    ResearchAgent,
    ReviewAgent,
    TestingAgent,
)
from agents.swarm_coordinator import (
    AgentCapability,
    AgentCategory,
    AgentHealthStatus,
    AgentInstance,
    AgentResult,
    FileOwnershipRegistry,
    HierarchicalQuotaManager,
    LeaseManager,
    ResultStatus,
    ResultValidator,
    SwarmCoordinator,
    TaskLease,
)
from agents.task_graph import FailureCategory, RetryConfig, TaskGraph, TaskNode, TaskStatus


class TestSwarmChaos(unittest.IsolatedAsyncioTestCase):
    """Adversarial and chaos stress testing of swarm runtime invariants."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp(prefix="jarvis_swarm_chaos_")
        self.project_id = "proj_chaos"
        self.mission_id = "miss_chaos_01"
        os.makedirs(os.path.join(self.test_dir, "workspace", "projects", self.project_id), exist_ok=True)
        self.state_store = MissionStateStore(workspace_root=self.test_dir)
        self.state_store.create_mission(
            self.project_id,
            self.mission_id,
            "Chaos Swarm Mission",
            "Adversarial and boundary stress validation",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # 1. Duplicate result submission
    def test_chaos_duplicate_result_idempotency(self) -> None:
        validator = ResultValidator()
        res = AgentResult(
            task_id="t_dup",
            attempt_id=1,
            agent_id="code_01",
            result_id="res_fixed_token",
            output={"diff": "added patch"},
        )
        ok1, msg1 = validator.validate_and_record(res)
        self.assertTrue(ok1)
        self.assertEqual(msg1, "VALID")

        # Re-submitting identical token must not process twice
        ok2, msg2 = validator.validate_and_record(res)
        self.assertTrue(ok2)
        self.assertIn("DUPLICATE_IGNORED", msg2)

    # 2. Stale lease submission rejected
    def test_chaos_stale_lease_rejection(self) -> None:
        lm = LeaseManager()
        t0 = 1000.0
        lease = lm.acquire_lease("t_stale", "agent_slow", attempt_id=1, ttl_seconds=5.0, now=t0)
        # Advance time past TTL
        expired = lm.reap_expired_leases(now=t0 + 10.0)
        self.assertEqual(len(expired), 1)

        # Agent tries to renew expired lease
        renewed = lm.renew_lease(lease.lease_id, "agent_slow", now=t0 + 11.0)
        self.assertFalse(renewed)
        self.assertIsNone(lm.get_active_lease_for_task("t_stale", now=t0 + 11.0))

    # 3. Heartbeat loss & failover
    async def test_chaos_heartbeat_loss_and_reassignment(self) -> None:
        graph = TaskGraph(nodes=[
            TaskNode("t_hb", "Heartbeat Task", category="CODING", status=TaskStatus.READY, retry_config=RetryConfig(max_attempts=3)),
        ])
        coordinator = SwarmCoordinator(
            project_id=self.project_id,
            mission_id=self.mission_id,
            mission_state=self.state_store,
            task_graph=graph,
        )

        agent_dying = AgentInstance("code_dying", "CODING", AgentCapability("CODING"), heartbeat_timeout_seconds=2.0)
        agent_healthy = AgentInstance("code_healthy", "CODING", AgentCapability("CODING"), heartbeat_timeout_seconds=10.0)
        coordinator.register_agent(agent_dying)
        coordinator.register_agent(agent_healthy)

        # Lease to dying agent
        node = graph.get_node("t_hb")
        lease = coordinator.acquire_task_lease(node, agent_dying)
        node.status = TaskStatus.RUNNING

        # Simulate heartbeat timeout: 5s later without heartbeat
        now = lease.acquired_at + 5.0
        interrupted = coordinator.reconcile_leases_and_failures(now=now)

        self.assertIn("t_hb", interrupted)
        self.assertEqual(node.status, TaskStatus.INTERRUPTED)
        self.assertEqual(agent_dying.status, AgentHealthStatus.UNHEALTHY)

        # Re-queue task and let healthy agent pick it up
        node.status = TaskStatus.READY
        selection = coordinator.select_agent_for_task(node)
        self.assertIsNotNone(selection)
        self.assertEqual(selection.agent_id, "code_healthy")

    # 4. File collision prevention
    def test_chaos_file_collision_prevention(self) -> None:
        registry = FileOwnershipRegistry()
        ok1, _ = registry.acquire_paths("t1", "code_01", ["backend/services/auth.py", "backend/routes/"])
        self.assertTrue(ok1)

        # Task 2 attempts to write to routes subfile
        ok2, err2 = registry.acquire_paths("t2", "code_02", ["backend/routes/auth_routes.py"])
        self.assertFalse(ok2)
        self.assertIn("CONFLICT_DETECTED", err2)

        # Task 3 attempts to claim parent folder
        ok3, err3 = registry.acquire_paths("t3", "code_03", ["backend/"])
        self.assertFalse(ok3)
        self.assertIn("CONFLICT_DETECTED", err3)

    # 5. Quota exhaustion and backpressure
    def test_chaos_quota_exhaustion(self) -> None:
        quotas = HierarchicalQuotaManager(global_max_concurrency=2, category_limits={"CODING": 2})
        c1 = AgentInstance("c1", "CODING", AgentCapability("CODING", concurrency_limit=1))
        c2 = AgentInstance("c2", "CODING", AgentCapability("CODING", concurrency_limit=1))
        c3 = AgentInstance("c3", "CODING", AgentCapability("CODING", concurrency_limit=1))

        t1 = TaskNode("t1", "T1", category="CODING")
        t2 = TaskNode("t2", "T2", category="CODING")
        t3 = TaskNode("t3", "T3", category="CODING")

        self.assertTrue(quotas.can_dispatch(c1, t1)[0])
        quotas.allocate("t1", "c1", "CODING")
        c1.current_tasks.add("t1")

        self.assertTrue(quotas.can_dispatch(c2, t2)[0])
        quotas.allocate("t2", "c2", "CODING")
        c2.current_tasks.add("t2")

        # Third task rejected by global and category quota
        can3, reason3 = quotas.can_dispatch(c3, t3)
        self.assertFalse(can3)
        self.assertIn("Global concurrency limit reached", reason3)

        # Release task 1 -> third task now permitted
        quotas.release("t1")
        c1.current_tasks.discard("t1")
        can3_after, _ = quotas.can_dispatch(c3, t3)
        self.assertTrue(can3_after)


if __name__ == "__main__":
    unittest.main()
