"""
JARVIS OS — Phase 14: Multi-Agent Swarm Integration Test Suite
Tests end-to-end distributed execution: 10 tasks, parallel branches, handoff,
transient failure with sticky retry & reassignment, and mission evidence satisfaction.
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
    ReviewAgent,
    TestingAgent,
)
from agents.task_graph import RetryConfig, TaskGraph, TaskNode, TaskStatus


class TestSwarmIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration scenarios for multi-agent swarm."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp(prefix="jarvis_swarm_integ_")
        self.project_id = "proj_integ"
        self.mission_id = "miss_integ_01"
        os.makedirs(os.path.join(self.test_dir, "workspace", "projects", self.project_id), exist_ok=True)
        self.state_store = MissionStateStore(workspace_root=self.test_dir)
        self.state_store.create_mission(
            self.project_id,
            self.mission_id,
            "Multi-Agent E2E Feature Mission",
            "Build secure authentication feature with full swarm pipeline",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    async def test_full_swarm_pipeline_with_handoff_and_retry(self) -> None:
        """
        10 Tasks DAG:
        Phase 1: Architecture Spec (arch_01)
        Phase 2 (Parallel):
          - Backend Models (code_01)
          - Frontend Scaffold (code_02)
        Phase 3 (Parallel):
          - Backend API Endpoints (code_01) [Flakes once, retries, succeeds]
          - Frontend UI Components (code_02)
        Phase 4: Unit & Integration Tests (test_01)
        Phase 5: Browser QA (browser_01)
        Phase 6: Multi-Axis Code Review (review_01)
        Phase 7: Build & Package (code_01)
        Phase 8: Acceptance Verification & Evidence Confirmation (review_01)
        """

        nodes = [
            # T1: Architecture
            TaskNode("t1_arch", "Architecture Spec", category="ARCHITECTURE", priority=10),

            # T2 & T3 (Parallel models & scaffold)
            TaskNode("t2_models", "Backend Models", category="CODING", dependencies=["t1_arch"], priority=8, metadata={"path_scope": ["backend/models.py"]}),
            TaskNode("t3_scaffold", "Frontend Scaffold", category="CODING", dependencies=["t1_arch"], priority=8, metadata={"path_scope": ["frontend/src/"]}),

            # T4 & T5 (Parallel API & UI)
            TaskNode("t4_api", "Backend API Endpoints", category="CODING", dependencies=["t2_models"], priority=7, retry_config=RetryConfig(max_attempts=3), metadata={"path_scope": ["backend/routes.py"]}),
            TaskNode("t5_ui", "Frontend UI Components", category="CODING", dependencies=["t3_scaffold"], priority=7, metadata={"path_scope": ["frontend/src/components/"]}),

            # T6: Testing
            TaskNode("t6_tests", "Test Suite", category="TESTING", dependencies=["t4_api", "t5_ui"], priority=6),

            # T7: Browser
            TaskNode("t7_browser", "Browser E2E Verification", category="BROWSER", dependencies=["t6_tests"], priority=5),

            # T8: Review
            TaskNode("t8_review", "Multi-Axis Review", category="REVIEW", dependencies=["t7_browser"], priority=4),

            # T9: Build
            TaskNode("t9_build", "Build & Package", category="CODING", dependencies=["t8_review"], priority=3),

            # T10: Signoff
            TaskNode("t10_signoff", "Acceptance Signoff", category="REVIEW", dependencies=["t9_build"], priority=2),
        ]

        graph = TaskGraph(nodes=nodes)

        # Create custom pool with flaking behavior on t4_api
        class FlakyCodingAgent(CodingAgent):
            def __init__(self, agent_id: str):
                super().__init__(agent_id)
                self.has_flaked = False

            async def execute(self, task, context, lease, heartbeat_cb=None):
                if task.task_id == "t4_api" and not self.has_flaked:
                    self.has_flaked = True
                    raise RuntimeError("Transient connection reset while generating routes")
                return await super().execute(task, context, lease, heartbeat_cb)

        swarm_agents = [
            ArchitectureAgent("arch_01"),
            FlakyCodingAgent("code_01"),
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
            swarm_agents=swarm_agents,
        )

        final_status = await orchestrator.run()

        # 1. Verify complete success
        self.assertEqual(final_status, MissionLifecycleStatus.COMPLETED)
        self.assertTrue(orchestrator.task_graph.is_all_completed())

        # 2. Verify all 10 tasks completed
        for node in graph.nodes.values():
            self.assertEqual(node.status, TaskStatus.COMPLETED, f"Task {node.task_id} did not complete")
            self.assertTrue(len(node.output_data) > 0, f"Task {node.task_id} has no output data")

        # 3. Verify retry occurred on flaky task
        t4_node = graph.get_node("t4_api")
        self.assertGreaterEqual(t4_node.attempt_count, 2)

        # 4. Verify cross-agent handoff occurred
        t6_node = graph.get_node("t6_tests")
        self.assertIn("t6_tests", orchestrator._task_outputs)

        # 5. Verify evidence was collected
        self.assertGreater(len(orchestrator._evidence_collected), 5)

        # 6. Verify coordinator metrics
        metrics = orchestrator.swarm_coordinator.metrics
        self.assertGreaterEqual(metrics.total_completed_tasks, 10)


if __name__ == "__main__":
    unittest.main()
