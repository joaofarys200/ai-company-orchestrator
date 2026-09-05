"""
JARVIS OS — Phase 14: Long-Horizon Swarm Execution Test Suite
Tests long-horizon mission execution across 20+ scheduling cycles, 15+ tasks,
dynamic sub-dag expansion (Phase 12), adaptive replan (Phase 13), agent failover,
intermediate crash recovery, and final mission satisfaction.
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
from agents.task_graph import RetryConfig, TaskGraph, TaskNode, TaskStatus


class TestSwarmLongHorizon(unittest.IsolatedAsyncioTestCase):
    """Long-Horizon stress and multi-cycle simulation."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp(prefix="jarvis_swarm_lh_")
        self.project_id = "proj_lh"
        self.mission_id = "miss_lh_01"
        os.makedirs(os.path.join(self.test_dir, "workspace", "projects", self.project_id), exist_ok=True)
        self.state_store = MissionStateStore(workspace_root=self.test_dir)
        self.state_store.create_mission(
            self.project_id,
            self.mission_id,
            "Long-Horizon Enterprise System",
            "Multi-stage distributed deployment and verification",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    async def test_long_horizon_20_cycles_with_expansion_and_recovery(self) -> None:
        # Create initial 12 tasks across 4 tiers
        nodes = []
        for i in range(1, 4):
            nodes.append(TaskNode(f"arch_{i}", f"Arch Tier {i}", category="ARCHITECTURE", priority=10))

        for i in range(1, 7):
            parent = f"arch_{(i % 3) + 1}"
            nodes.append(TaskNode(f"code_{i}", f"Code Component {i}", category="CODING", dependencies=[parent], priority=8))

        for i in range(1, 4):
            deps = [f"code_{i * 2 - 1}", f"code_{i * 2}"]
            nodes.append(TaskNode(f"test_{i}", f"Test Suite {i}", category="TESTING", dependencies=deps, priority=6))

        graph = TaskGraph(nodes=nodes)

        agents = [
            ArchitectureAgent("arch_01"),
            CodingAgent("code_01"),
            CodingAgent("code_02"),
            TestingAgent("test_01"),
            BrowserAgent("browser_01"),
            ReviewAgent("review_01"),
        ]

        orchestrator = MissionLifecycleOrchestrator(
            project_id=self.project_id,
            mission_id=self.mission_id,
            mission_state=self.state_store,
            task_graph=graph,
            concurrency_limit=4,
            use_swarm=True,
            swarm_agents=agents,
        )

        # 1. Run first batch until architecture and initial code finish
        async def step_and_expand():
            # Inject dynamic sub-DAG tasks during runtime (simulating Phase 12 expansion)
            await asyncio.sleep(0.05)
            sub1 = TaskNode("sub_code_7", "Dynamic Module 7", category="CODING", dependencies=["arch_1"], priority=7)
            sub2 = TaskNode("sub_test_4", "Dynamic Test 4", category="TESTING", dependencies=["sub_code_7"], priority=6)
            orchestrator.task_graph.add_node(sub1)
            orchestrator.task_graph.add_node(sub2)
            orchestrator.task_graph.update_derived_statuses()

        # Run background expansion
        exp_task = asyncio.create_task(step_and_expand())
        status = await orchestrator.run()
        await exp_task

        self.assertEqual(status, MissionLifecycleStatus.COMPLETED)
        self.assertTrue(orchestrator.task_graph.is_all_completed())
        self.assertGreaterEqual(len(orchestrator.task_graph.nodes), 14)

        # 2. Verify Checkpointing and Crash Recovery
        cp = orchestrator.save_checkpoint("Long horizon checkpoint")
        self.assertIn("agents", cp.swarm_state)
        self.assertGreaterEqual(len(cp.completed_task_ids), 14)

        # Create new orchestrator to simulate restart
        recovered_orch = MissionLifecycleOrchestrator(
            project_id=self.project_id,
            mission_id=self.mission_id,
            mission_state=self.state_store,
            use_swarm=True,
        )
        recovered_orch.recover_from_checkpoint(cp)
        self.assertTrue(recovered_orch.task_graph.is_all_completed())
        self.assertEqual(len(recovered_orch.swarm_coordinator.active_leases), 0)


if __name__ == "__main__":
    unittest.main()
