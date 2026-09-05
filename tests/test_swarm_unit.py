"""
JARVIS OS — Phase 14: Comprehensive Unit Test Suite (A-Z)
Tests all 26 core architectural facets of the Swarm Coordinator and Multi-Agent Runtime.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import time
import unittest

from agents.mission_orchestrator import MissionLifecycleOrchestrator, MissionLifecycleStatus
from agents.mission_state import MissionStateStore, utc_now
from agents.swarm_agents import (
    ArchitectureAgent,
    BrowserAgent,
    CodingAgent,
    CrossAgentHandoffManager,
    ResearchAgent,
    ReviewAgent,
    SwarmAgent,
    TestingAgent,
    create_default_swarm_pool,
)
from agents.swarm_coordinator import (
    AgentCapability,
    AgentCategory,
    AgentHealthStatus,
    AgentInstance,
    AgentRegistry,
    AgentResult,
    AgentSelector,
    FileOwnershipRegistry,
    HierarchicalQuotaManager,
    LeaseManager,
    ResourceClass,
    ResultStatus,
    ResultValidator,
    SwarmCoordinator,
    TaskLease,
    TaskScheduler,
)
from agents.task_graph import FailureCategory, FailureInfo, RetryConfig, TaskGraph, TaskNode, TaskStatus


class TestSwarmUnitAtoZ(unittest.IsolatedAsyncioTestCase):
    """Unit Tests A through Z covering every aspect of Phase 14 Swarm Coordinator."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp(prefix="jarvis_swarm_unit_")
        self.project_id = "proj_swarm_test"
        self.mission_id = "miss_swarm_test"
        os.makedirs(os.path.join(self.test_dir, "workspace", "projects", self.project_id), exist_ok=True)
        self.state_store = MissionStateStore(workspace_root=self.test_dir)
        self.state_store.create_mission(self.project_id, self.mission_id, "Swarm Test Mission", "Objective")

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # A: Agent Registry
    def test_a_agent_registry(self) -> None:
        coordinator = SwarmCoordinator(
            project_id=self.project_id,
            mission_id=self.mission_id,
            mission_state=self.state_store,
            task_graph=TaskGraph(),
        )
        agent = AgentInstance(
            agent_id="test_agent_1",
            agent_type="CODING",
            capability=AgentCapability(agent_type="CODING", categories=[AgentCategory.CODING]),
        )
        coordinator.register_agent(agent)
        self.assertIsNotNone(coordinator.registry.get("test_agent_1"))
        self.assertEqual(len(coordinator.registry.list_agents()), 1)
        coordinator.registry.unregister("test_agent_1")
        self.assertIsNone(coordinator.registry.get("test_agent_1"))

    # B: Capability Matching
    def test_b_capability_matching(self) -> None:
        cap_coding = AgentCapability(agent_type="CODING", categories=[AgentCategory.CODING])
        cap_general = AgentCapability(agent_type="GENERAL", categories=[AgentCategory.GENERAL])

        task_code = TaskNode(task_id="t1", title="Code", category="CODING")
        task_research = TaskNode(task_id="t2", title="Research", category="RESEARCH")

        self.assertTrue(cap_coding.matches_task(task_code))
        self.assertFalse(cap_coding.matches_task(task_research))
        self.assertTrue(cap_general.matches_task(task_research))

    # C: Deterministic Agent Selection
    def test_c_deterministic_agent_selection(self) -> None:
        coordinator = SwarmCoordinator(
            project_id=self.project_id,
            mission_id=self.mission_id,
            mission_state=self.state_store,
            task_graph=TaskGraph(),
        )
        # 2 coding agents: agent_b is completely idle, agent_a is already running a task
        agent_a = AgentInstance(
            agent_id="agent_a",
            agent_type="CODING",
            capability=AgentCapability(agent_type="CODING", categories=[AgentCategory.CODING]),
            current_tasks={"other_task"},
        )
        agent_b = AgentInstance(
            agent_id="agent_b",
            agent_type="CODING",
            capability=AgentCapability(agent_type="CODING", categories=[AgentCategory.CODING]),
        )
        coordinator.register_agent(agent_a)
        coordinator.register_agent(agent_b)

        task = TaskNode(task_id="t_code", title="Implement", category="CODING", priority=5)
        selection = coordinator.select_agent_for_task(task)
        self.assertIsNotNone(selection)
        # agent_b should win due to being completely idle (+30 bonus vs -20 load penalty)
        self.assertEqual(selection.agent_id, "agent_b")

    # D: Lease Acquisition
    def test_d_lease_acquisition(self) -> None:
        lm = LeaseManager()
        lease = lm.acquire_lease("t1", "agent_1", attempt_id=1, ttl_seconds=10.0)
        self.assertEqual(lease.task_id, "t1")
        self.assertEqual(lease.agent_id, "agent_1")
        self.assertTrue(lease.is_valid())
        self.assertIsNotNone(lm.get_active_lease_for_task("t1"))

    # E: Lease Conflict
    def test_e_lease_conflict(self) -> None:
        lm = LeaseManager()
        lm.acquire_lease("t1", "agent_1", attempt_id=1, ttl_seconds=10.0)
        with self.assertRaises(ValueError):
            # Second agent cannot acquire active lease
            lm.acquire_lease("t1", "agent_2", attempt_id=1, ttl_seconds=10.0)

    # F: Lease Expiration
    def test_f_lease_expiration(self) -> None:
        lm = LeaseManager()
        t0 = 1000.0
        lease = lm.acquire_lease("t1", "agent_1", attempt_id=1, ttl_seconds=5.0, now=t0)
        self.assertTrue(lease.is_valid(now=t0 + 2.0))
        self.assertFalse(lease.is_valid(now=t0 + 6.0))

        expired = lm.reap_expired_leases(now=t0 + 6.0)
        self.assertEqual(len(expired), 1)
        self.assertEqual(expired[0].task_id, "t1")
        self.assertIsNone(lm.get_active_lease_for_task("t1", now=t0 + 6.0))

    # G: Heartbeat Renewal
    def test_g_heartbeat(self) -> None:
        lm = LeaseManager()
        t0 = 1000.0
        lease = lm.acquire_lease("t1", "agent_1", attempt_id=1, ttl_seconds=5.0, now=t0)
        renewed = lm.renew_lease(lease.lease_id, "agent_1", now=t0 + 3.0)
        self.assertTrue(renewed)
        self.assertTrue(lease.is_valid(now=t0 + 7.0))

    # H: Agent Health & Failure Detection
    def test_h_agent_health(self) -> None:
        reg = AgentRegistry()
        t0 = 1000.0
        agent = AgentInstance(
            agent_id="ag_1",
            agent_type="CODING",
            capability=AgentCapability(agent_type="CODING"),
            last_heartbeat=t0,
            heartbeat_timeout_seconds=5.0,
        )
        reg.register(agent)
        self.assertEqual(agent.check_health(now=t0 + 2.0), AgentHealthStatus.IDLE)
        # Heartbeat missed after 6s -> UNHEALTHY
        unhealthy = reg.check_all_health(now=t0 + 6.0)
        self.assertIn("ag_1", unhealthy)
        self.assertEqual(agent.status, AgentHealthStatus.UNHEALTHY)
        self.assertFalse(agent.is_available)

    # I: Dispatch Flow
    def test_i_dispatch(self) -> None:
        graph = TaskGraph(nodes=[
            TaskNode(task_id="t1", title="Task 1", category="CODING", status=TaskStatus.READY),
        ])
        coordinator = SwarmCoordinator(
            project_id=self.project_id,
            mission_id=self.mission_id,
            mission_state=self.state_store,
            task_graph=graph,
        )
        agent = AgentInstance("code_01", "CODING", AgentCapability("CODING", categories=[AgentCategory.CODING]))
        coordinator.register_agent(agent)

        task = graph.get_node("t1")
        selection = coordinator.select_agent_for_task(task)
        self.assertIsNotNone(selection)
        lease = coordinator.acquire_task_lease(task, agent)
        self.assertIn("t1", coordinator.active_leases)
        self.assertIn("t1", agent.current_tasks)

    # J: Hierarchical Quotas (Global & Category)
    def test_j_quotas(self) -> None:
        qm = HierarchicalQuotaManager(
            global_max_concurrency=2,
            category_limits={"CODING": 1},
        )
        agent_1 = AgentInstance("c1", "CODING", AgentCapability("CODING", concurrency_limit=2))
        agent_2 = AgentInstance("c2", "CODING", AgentCapability("CODING", concurrency_limit=2))
        t1 = TaskNode(task_id="t1", title="T1", category="CODING")
        t2 = TaskNode(task_id="t2", title="T2", category="CODING")

        can_run, _ = qm.can_dispatch(agent_1, t1)
        self.assertTrue(can_run)
        qm.allocate("t1", "c1", "CODING")

        # Category quota for CODING is 1 -> t2 must be blocked
        can_run2, reason2 = qm.can_dispatch(agent_2, t2)
        self.assertFalse(can_run2)
        self.assertIn("Category quota", reason2)

    # K: Concurrency Limit Per Agent
    def test_k_concurrency(self) -> None:
        qm = HierarchicalQuotaManager(global_max_concurrency=8, category_limits={"CODING": 5})
        agent = AgentInstance("c1", "CODING", AgentCapability("CODING", concurrency_limit=1))
        t1 = TaskNode("t1", "T1", category="CODING")
        t2 = TaskNode("t2", "T2", category="CODING")

        can_run, _ = qm.can_dispatch(agent, t1)
        self.assertTrue(can_run)
        agent.current_tasks.add("t1")
        qm.allocate("t1", "c1", "CODING")

        can_run2, reason2 = qm.can_dispatch(agent, t2)
        self.assertFalse(can_run2)
        self.assertIn("max concurrency", reason2)

    # L: Priority Scheduling
    def test_l_priority(self) -> None:
        scheduler = TaskScheduler()
        t_low = TaskNode(task_id="t_low", title="Low", priority=1)
        t_high = TaskNode(task_id="t_high", title="High", priority=10)
        ordered = scheduler.order_ready_tasks([t_low, t_high], now=1000.0)
        self.assertEqual(ordered[0].task_id, "t_high")

    # M: Fairness & Priority Aging
    def test_m_fairness_and_aging(self) -> None:
        scheduler = TaskScheduler()
        t0 = 1000.0
        t_old = TaskNode(task_id="t_old", title="Old Task", priority=1)
        t_new = TaskNode(task_id="t_new", title="New Task", priority=5)

        # t_old was ready at t0
        scheduler.record_ready("t_old", now=t0)

        # 30 seconds later, t_old has gained aging bonus (+50.0 effective priority)
        ordered = scheduler.order_ready_tasks([t_old, t_new], now=t0 + 30.0)
        self.assertEqual(ordered[0].task_id, "t_old")

    # N: Result Validation Contract
    def test_n_result_validation(self) -> None:
        validator = ResultValidator()
        bad_result = AgentResult(task_id="", attempt_id=1, agent_id="c1")
        ok, msg = validator.validate_and_record(bad_result)
        self.assertFalse(ok)

        good_result = AgentResult(task_id="t1", attempt_id=1, agent_id="c1", output={"diff": "ok"})
        ok2, msg2 = validator.validate_and_record(good_result)
        self.assertTrue(ok2)
        self.assertEqual(msg2, "VALID")

    # O: Duplicate Result Idempotency
    def test_o_duplicate_result(self) -> None:
        validator = ResultValidator()
        res = AgentResult(task_id="t1", attempt_id=1, agent_id="c1", result_id="fixed_id")
        ok, _ = validator.validate_and_record(res)
        self.assertTrue(ok)

        # Resubmitting same (task_id, attempt_id, result_id)
        ok2, msg2 = validator.validate_and_record(res)
        self.assertTrue(ok2)
        self.assertIn("DUPLICATE_IGNORED", msg2)

    # P: Reassignment on Failure
    async def test_p_reassignment(self) -> None:
        graph = TaskGraph(nodes=[
            TaskNode(task_id="t1", title="Task 1", category="CODING", status=TaskStatus.RUNNING),
        ])
        coordinator = SwarmCoordinator(
            project_id=self.project_id,
            mission_id=self.mission_id,
            mission_state=self.state_store,
            task_graph=graph,
        )
        agent_1 = AgentInstance("c1", "CODING", AgentCapability("CODING"))
        agent_2 = AgentInstance("c2", "CODING", AgentCapability("CODING"))
        coordinator.register_agent(agent_1)
        coordinator.register_agent(agent_2)

        # Agent 1 fails
        fail_result = AgentResult(
            task_id="t1",
            attempt_id=1,
            agent_id="c1",
            status=ResultStatus.FAILURE,
            failure={"error": "SyntaxError"},
        )
        await coordinator.handle_agent_result(fail_result)
        self.assertEqual(len(coordinator.task_attempts["t1"]), 1)
        self.assertEqual(coordinator.task_attempts["t1"][0]["agent_id"], "c1")
        self.assertEqual(graph.nodes["t1"].status, TaskStatus.FAILED)

    # Q: Cross-Agent Handoff
    def test_q_cross_agent_handoff(self) -> None:
        t1 = TaskNode("t1", "Arch", category="ARCHITECTURE", output_data={"spec": "Interface V1"}, evidence_refs=["ev_1"])
        t2 = TaskNode("t2", "Code", category="CODING", dependencies=["t1"])
        all_tasks = {"t1": t1, "t2": t2}
        outputs = {"t1": {"spec": "Interface V1"}}

        ctx = CrossAgentHandoffManager.build_task_context(t2, all_tasks, outputs)
        self.assertIn("t1", ctx["handoff_inputs"])
        self.assertEqual(ctx["handoff_inputs"]["t1"]["output"]["spec"], "Interface V1")
        self.assertIn("ev_1", ctx["relevant_evidence"])

    # R: File Ownership Acquisition & Release
    def test_r_file_ownership(self) -> None:
        registry = FileOwnershipRegistry()
        ok, err = registry.acquire_paths("t1", "c1", ["src/models/user.py"])
        self.assertTrue(ok)
        self.assertIsNone(err)

        registry.release_paths("t1")
        ok2, err2 = registry.acquire_paths("t2", "c2", ["src/models/user.py"])
        self.assertTrue(ok2)

    # S: Conflict Detection
    def test_s_conflict_detection(self) -> None:
        registry = FileOwnershipRegistry()
        registry.acquire_paths("t1", "c1", ["src/models/"])
        # t2 attempts to modify a file inside the same directory tree
        ok, err = registry.acquire_paths("t2", "c2", ["src/models/user.py"])
        self.assertFalse(ok)
        self.assertIn("CONFLICT_DETECTED", err)

    # T: Cancellation
    async def test_t_cancellation(self) -> None:
        graph = TaskGraph(nodes=[
            TaskNode("t1", "T1", category="CODING", status=TaskStatus.READY),
            TaskNode("t2", "T2", category="CODING", dependencies=["t1"]),
        ])
        orch = MissionLifecycleOrchestrator(
            project_id=self.project_id,
            mission_id=self.mission_id,
            mission_state=self.state_store,
            task_graph=graph,
            use_swarm=True,
        )
        await orch.cancel()
        self.assertTrue(orch._cancelled)
        self.assertEqual(orch.status, MissionLifecycleStatus.CANCELLED)

    # U: Pause & Resume
    async def test_u_pause_resume(self) -> None:
        graph = TaskGraph(nodes=[
            TaskNode("t1", "T1", category="CODING", status=TaskStatus.READY),
        ])
        orch = MissionLifecycleOrchestrator(
            project_id=self.project_id,
            mission_id=self.mission_id,
            mission_state=self.state_store,
            task_graph=graph,
            use_swarm=True,
        )
        await orch.pause()
        self.assertTrue(orch._paused)
        self.assertEqual(orch.status, MissionLifecycleStatus.PAUSED)
        await orch.resume()
        self.assertFalse(orch._paused)
        self.assertEqual(orch.status, MissionLifecycleStatus.ACTIVE)

    # V: Checkpoint & Restart Reconciliation
    def test_v_checkpoint_restart(self) -> None:
        graph = TaskGraph(nodes=[
            TaskNode("t1", "T1", category="CODING", status=TaskStatus.COMPLETED),
            TaskNode("t2", "T2", category="TESTING", status=TaskStatus.READY),
        ])
        orch = MissionLifecycleOrchestrator(
            project_id=self.project_id,
            mission_id=self.mission_id,
            mission_state=self.state_store,
            task_graph=graph,
            use_swarm=True,
        )
        cp = orch.save_checkpoint("Test CP")
        self.assertIn("agents", cp.swarm_state)

        # Recover in new orchestrator
        new_orch = MissionLifecycleOrchestrator(
            project_id=self.project_id,
            mission_id=self.mission_id,
            mission_state=self.state_store,
            use_swarm=True,
        )
        new_orch.recover_from_checkpoint(cp)
        self.assertEqual(new_orch.task_graph.nodes["t1"].status, TaskStatus.COMPLETED)
        self.assertEqual(len(new_orch.swarm_coordinator.active_leases), 0)

    # W: Agent Crash Simulation
    async def test_w_agent_crash(self) -> None:
        class CrashingAgent(SwarmAgent):
            def __init__(self):
                super().__init__("crash_01", "CODING", AgentCapability("CODING", categories=[AgentCategory.CODING]))

            async def execute(self, task, context, lease, heartbeat_cb=None):
                raise RuntimeError("Uncaught process crash in sandbox")

        graph = TaskGraph(nodes=[
            TaskNode("t1", "Task 1", category="CODING", status=TaskStatus.READY, retry_config=RetryConfig(max_attempts=2)),
        ])
        orch = MissionLifecycleOrchestrator(
            project_id=self.project_id,
            mission_id=self.mission_id,
            mission_state=self.state_store,
            task_graph=graph,
            use_swarm=True,
            swarm_agents=[CrashingAgent()],
        )
        node = graph.get_node("t1")
        agent = orch.swarm_agents["crash_01"]
        lease = orch.swarm_coordinator.acquire_task_lease(node, agent.instance)
        await orch._execute_swarm_task_guarded(node, agent, lease)

        # After crash, retry config allows retry -> reset to READY
        self.assertEqual(node.status, TaskStatus.READY)
        self.assertEqual(node.attempt_count, 1)

    # X: Dynamic Sub-DAG Integration
    async def test_x_dynamic_subdag_integration(self) -> None:
        graph = TaskGraph(nodes=[
            TaskNode("t_parent", "Parent Task", category="CODING", status=TaskStatus.COMPLETED),
        ])
        orch = MissionLifecycleOrchestrator(
            project_id=self.project_id,
            mission_id=self.mission_id,
            mission_state=self.state_store,
            task_graph=graph,
            use_swarm=True,
        )
        # Dynamically inject subtasks
        sub1 = TaskNode("sub_1", "Subtask 1", category="TESTING", dependencies=["t_parent"], status=TaskStatus.READY)
        orch.task_graph.add_node(sub1)
        orch.task_graph.update_derived_statuses()

        ready = orch.task_graph.get_ready_tasks()
        self.assertIn("sub_1", [n.task_id for n in ready])
        selection = orch.swarm_coordinator.select_agent_for_task(sub1)
        self.assertIsNotNone(selection)
        self.assertEqual(selection.agent_type, "TESTING")

    # Y: Adaptive Planning Integration
    async def test_y_adaptive_planning_integration(self) -> None:
        graph = TaskGraph(nodes=[
            TaskNode("t1", "Completed Task", category="CODING", status=TaskStatus.COMPLETED),
            TaskNode("t2", "Running Task", category="CODING", status=TaskStatus.RUNNING),
            TaskNode("t3", "Pending Task", category="TESTING", status=TaskStatus.PENDING),
        ])
        orch = MissionLifecycleOrchestrator(
            project_id=self.project_id,
            mission_id=self.mission_id,
            mission_state=self.state_store,
            task_graph=graph,
            use_swarm=True,
        )
        # Evaluation respects running and completed tasks
        eval_res = await orch.evaluate_plan()
        self.assertIsNotNone(eval_res)
        self.assertEqual(graph.nodes["t1"].status, TaskStatus.COMPLETED)
        self.assertEqual(graph.nodes["t2"].status, TaskStatus.RUNNING)

    # Z: Safety Boundaries & Least Privilege
    async def test_z_safety_boundaries(self) -> None:
        research_agent = ResearchAgent("res_01")
        # Research agent cannot execute destructive commands
        task_malicious = TaskNode("t_bad", "Destructive Action", category="RESEARCH", metadata={"requested_tools": ["execute_command"]})
        lease = TaskLease("l_1", "t_bad", "res_01", attempt_id=1)
        res = await research_agent.execute(task_malicious, {}, lease)
        self.assertEqual(res.status, ResultStatus.FAILURE)
        self.assertIn("SECURITY_VIOLATION", res.failure.get("reason", ""))

        browser_agent = BrowserAgent("browser_01")
        # Browser agent cannot modify economic state
        task_money = TaskNode("t_money", "Transfer Money", category="BROWSER", metadata={"modifies_economic_state": True})
        lease_money = TaskLease("l_2", "t_money", "browser_01", attempt_id=1)
        res_money = await browser_agent.execute(task_money, {}, lease_money)
        self.assertEqual(res_money.status, ResultStatus.FAILURE)
        self.assertIn("SECURITY_VIOLATION", res_money.failure.get("reason", ""))


if __name__ == "__main__":
    unittest.main()
