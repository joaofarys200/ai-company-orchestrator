"""
JARVIS OS — Phase 14: Real-World Software Engineering Swarm Trial
Simulates complete feature implementation:
Architecture -> Coding -> Testing -> Browser QA -> Security Review.
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
from agents.task_graph import TaskGraph, TaskNode, TaskStatus


class TestSwarmRealWorld(unittest.IsolatedAsyncioTestCase):
    """Real-world software engineering trial executed by distributed multi-agent swarm."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp(prefix="jarvis_swarm_rw_")
        self.project_id = "realworld_feature_app"
        self.mission_id = "mission_user_profile_security"
        self.proj_root = os.path.join(self.test_dir, "workspace", "projects", self.project_id)
        os.makedirs(self.proj_root, exist_ok=True)
        self.state_store = MissionStateStore(workspace_root=self.test_dir)
        self.state_store.create_mission(
            self.project_id,
            self.mission_id,
            "User Profile & Security Feature",
            "Implement secure profile data and authentication auditing",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    async def test_full_software_engineering_lifecycle(self) -> None:
        nodes = [
            # 1. Architecture
            TaskNode(
                task_id="rw_01_arch",
                title="Design User Profile & Hash Schema",
                category="ARCHITECTURE",
                priority=10,
                metadata={"path_scope": ["docs/specs/user_profile.md"]},
            ),

            # 2. Parallel Coding: Database Model & Password Hasher
            TaskNode(
                task_id="rw_02_model",
                title="Implement User Model with Pydantic",
                category="CODING",
                dependencies=["rw_01_arch"],
                priority=8,
                metadata={"path_scope": ["src/models/user.py"]},
            ),
            TaskNode(
                task_id="rw_03_hasher",
                title="Implement Argon2 Password Hasher",
                category="CODING",
                dependencies=["rw_01_arch"],
                priority=8,
                metadata={"path_scope": ["src/security/hasher.py"]},
            ),

            # 3. Parallel Coding: API Service
            TaskNode(
                task_id="rw_04_service",
                title="Implement User Profile Service",
                category="CODING",
                dependencies=["rw_02_model", "rw_03_hasher"],
                priority=7,
                metadata={"path_scope": ["src/services/user_service.py"]},
            ),

            # 4. Automated Testing
            TaskNode(
                task_id="rw_05_tests",
                title="Run Unit Tests & Regression Matrix",
                category="TESTING",
                dependencies=["rw_04_service"],
                priority=6,
            ),

            # 5. Browser UI QA
            TaskNode(
                task_id="rw_06_browser",
                title="Run Browser E2E Profile View QA",
                category="BROWSER",
                dependencies=["rw_05_tests"],
                priority=5,
            ),

            # 6. Security Review & Acceptance
            TaskNode(
                task_id="rw_07_review",
                title="Security Multi-Axis Review & Signoff",
                category="REVIEW",
                dependencies=["rw_06_browser"],
                priority=4,
            ),
        ]

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

        status = await orchestrator.run()

        # Assertions
        self.assertEqual(status, MissionLifecycleStatus.COMPLETED)
        self.assertTrue(orchestrator.task_graph.is_all_completed())

        # Check evidence was collected across all disciplines
        evidence_kinds = set()
        for ev_id in orchestrator._evidence_collected:
            if "arch" in ev_id:
                evidence_kinds.add("ARCHITECTURE")
            if "code" in ev_id:
                evidence_kinds.add("CODING")
            if "test" in ev_id:
                evidence_kinds.add("TESTING")
            if "browser" in ev_id:
                evidence_kinds.add("BROWSER")
            if "rev" in ev_id:
                evidence_kinds.add("REVIEW")

        self.assertIn("ARCHITECTURE", evidence_kinds)
        self.assertIn("CODING", evidence_kinds)
        self.assertIn("TESTING", evidence_kinds)
        self.assertIn("BROWSER", evidence_kinds)
        self.assertIn("REVIEW", evidence_kinds)


if __name__ == "__main__":
    unittest.main()
