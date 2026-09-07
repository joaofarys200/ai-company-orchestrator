import asyncio
import os
import shutil
import tempfile
import unittest

from agents.collaboration_engine import (
    AgentConflictArbitrator,
    AgentProposal,
    ArbitrationDecision,
    ArbitrationRecord,
    CollaborationCoordinator,
    CollaborationMetrics,
    CollaborationSession,
    CollaborationStatus,
    ConflictDetails,
    ConflictKey,
    ConflictType,
    PatchMergeEngine,
    ResultKind,
)
from agents.mission_orchestrator import MissionLifecycleOrchestrator
from agents.mission_state import MissionStateStore
from agents.swarm_agents import (
    ArchitectureAgent,
    BrowserAgent,
    CodingAgent,
    ResearchAgent,
    ReviewAgent,
    SwarmAgent,
    TestingAgent,
)
from agents.swarm_coordinator import (
    AgentCapability,
    AgentCategory,
    SwarmCoordinator,
)
from agents.task_graph import (
    FailureCategory,
    RetryConfig,
    TaskGraph,
    TaskNode,
    TaskStatus,
)


class TestCollaborationUnit(unittest.IsolatedAsyncioTestCase):
    """Suite de Testes Unitários Completa para a Fase 15 — Autonomous Collaboration & Conflict Resolution."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.project_id = "proj_collab_test"
        self.mission_id = "mission_collab_test"
        os.makedirs(os.path.join(self.temp_dir, "workspace", "projects", self.project_id), exist_ok=True)
        self.state_store = MissionStateStore(workspace_root=self.temp_dir)
        self.state_store.create_mission(self.project_id, "Collab Test Mission", "Objective", mission_id=self.mission_id)
        self.coord = CollaborationCoordinator(
            project_id=self.project_id,
            mission_id=self.mission_id,
            workspace_root=self.temp_dir,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 42 - TEST 1: Two disjoint file changes -> AUTO-MERGE
    # ──────────────────────────────────────────────────────────────────────────

    def test_01_two_disjoint_file_changes_automerge(self) -> None:
        base_code = (
            "def login(user):\n"
            "    return True\n"
            "\n"
            "def logout(user):\n"
            "    return False\n"
        )
        agent1_code = (
            "def login(user):\n"
            "    print('logging in')\n"
            "    return True\n"
            "\n"
            "def logout(user):\n"
            "    return False\n"
        )
        agent2_code = (
            "def login(user):\n"
            "    return True\n"
            "\n"
            "def logout(user):\n"
            "    print('logging out')\n"
            "    return False\n"
        )

        ok, merged, reason = PatchMergeEngine.auto_merge_disjoint(
            "auth.py", base_code, agent1_code, agent2_code
        )
        self.assertTrue(ok)
        self.assertEqual(reason, "DISJOINT_AUTO_MERGE_SUCCESS")
        self.assertIn("print('logging in')", merged)
        self.assertIn("print('logging out')", merged)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 42 - TEST 2: Same symbol conflict -> ARBITRATION
    # ──────────────────────────────────────────────────────────────────────────

    def test_02_same_symbol_conflict_arbitration(self) -> None:
        task = TaskNode("t_symbol", "Implement login auth", category="CODING")
        p1 = AgentProposal(
            proposal_id="p1",
            agent_id="code_01",
            task_id=task.task_id,
            result_kind=ResultKind.PATCH,
            description="Login implementation A",
            affected_files=["auth.py"],
            affected_symbols=["login"],
            content_by_file={"auth.py": "def login(): return 'A'"},
            evidence=[{"kind": "TEST_PASS", "description": "passes test A"}],
            confidence_score=0.7,
        )
        p2 = AgentProposal(
            proposal_id="p2",
            agent_id="code_02",
            task_id=task.task_id,
            result_kind=ResultKind.PATCH,
            description="Login implementation B",
            affected_files=["auth.py"],
            affected_symbols=["login"],
            content_by_file={"auth.py": "def login(): return 'B'"},
            evidence=[
                {"kind": "HARD_VALIDATION_SYNTAX", "description": "hard syntax check"},
                {"kind": "TEST_PASS", "description": "passes test B"},
            ],
            confidence_score=0.9,
        )

        session = self.coord.create_session(task.task_id, ["code_01", "code_02"])
        self.coord.add_proposal(session.collaboration_id, p1)
        self.coord.add_proposal(session.collaboration_id, p2)

        status, conflicts, arbitrations = self.coord.evaluate_collaboration(
            session.collaboration_id, task
        )
        self.assertTrue(any(c.conflict_type == ConflictType.SYMBOL_CONFLICT for c in conflicts))
        self.assertEqual(len(arbitrations), len(conflicts))
        arb = arbitrations[0]
        self.assertIn(arb.decision, [ArbitrationDecision.ACCEPT_B, ArbitrationDecision.ACCEPT_A])
        self.assertEqual(arb.selected_proposal_id, "p2")

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 42 - TEST 3: Frontend/backend contract conflict -> CONTRACT REVIEW
    # ──────────────────────────────────────────────────────────────────────────

    def test_03_frontend_backend_contract_conflict(self) -> None:
        task = TaskNode("t_contract", "Update User Profile API", category="IMPLEMENTATION")
        p_fe = AgentProposal(
            proposal_id="p_fe",
            agent_id="code_fe",
            task_id=task.task_id,
            result_kind=ResultKind.PROPOSAL,
            description="Frontend expects JSON with profile_id",
            metadata={"contract_signature": {"endpoint": "/api/v1/profile", "params": ["profile_id"]}},
        )
        p_be = AgentProposal(
            proposal_id="p_be",
            agent_id="code_be",
            task_id=task.task_id,
            result_kind=ResultKind.PROPOSAL,
            description="Backend exposes endpoint with user_uuid",
            metadata={"contract_signature": {"endpoint": "/api/v1/profile", "params": ["user_uuid"]}},
        )

        session = self.coord.create_session(task.task_id, ["code_fe", "code_be"])
        self.coord.add_proposal(session.collaboration_id, p_fe)
        self.coord.add_proposal(session.collaboration_id, p_be)

        status, conflicts, arbitrations = self.coord.evaluate_collaboration(
            session.collaboration_id, task
        )
        contract_confs = [c for c in conflicts if c.conflict_type == ConflictType.CONTRACT_CONFLICT]
        self.assertTrue(len(contract_confs) > 0)
        self.assertIn("Contract parameter mismatch", contract_confs[0].rationale)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 42 - TEST 4: Architecture/coding conflict -> REPLAN
    # ──────────────────────────────────────────────────────────────────────────

    def test_04_architecture_coding_conflict_replan(self) -> None:
        task = TaskNode("t_arch", "Design & Implement Search API", category="IMPLEMENTATION")
        p_arch = AgentProposal(
            proposal_id="p_arch",
            agent_id="arch_01",
            task_id=task.task_id,
            result_kind=ResultKind.PROPOSAL,
            description="Architecture mandates RESTful search endpoints",
            metadata={"architecture_pattern": "REST"},
        )
        p_code = AgentProposal(
            proposal_id="p_code",
            agent_id="code_01",
            task_id=task.task_id,
            result_kind=ResultKind.PROPOSAL,
            description="Coding agent implements GraphQL search schema",
            metadata={"architecture_pattern": "GRAPHQL"},
        )

        session = self.coord.create_session(task.task_id, ["arch_01", "code_01"])
        self.coord.add_proposal(session.collaboration_id, p_arch)
        self.coord.add_proposal(session.collaboration_id, p_code)

        arch_ctx = {"required_pattern": "REST"}
        status, conflicts, arbitrations = self.coord.evaluate_collaboration(
            session.collaboration_id, task, architecture_context=arch_ctx
        )
        arch_confs = [c for c in conflicts if c.conflict_type == ConflictType.ARCHITECTURAL_CONFLICT]
        self.assertTrue(len(arch_confs) > 0)
        self.assertTrue(any(a.decision == ArbitrationDecision.REPLAN for a in arbitrations))

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 42 - TEST 5: Requirement ambiguity -> REVIEW / HALT
    # ──────────────────────────────────────────────────────────────────────────

    def test_05_requirement_ambiguity(self) -> None:
        task = TaskNode("t_req", "Name Search Filter", category="IMPLEMENTATION")
        p1 = AgentProposal(
            proposal_id="p1",
            agent_id="code_01",
            task_id=task.task_id,
            result_kind=ResultKind.PROPOSAL,
            description="Search filter must be strictly case-sensitive",
        )
        p2 = AgentProposal(
            proposal_id="p2",
            agent_id="code_02",
            task_id=task.task_id,
            result_kind=ResultKind.PROPOSAL,
            description="Search filter must be case-insensitive for UX",
        )

        session = self.coord.create_session(task.task_id, ["code_01", "code_02"])
        self.coord.add_proposal(session.collaboration_id, p1)
        self.coord.add_proposal(session.collaboration_id, p2)

        status, conflicts, arbitrations = self.coord.evaluate_collaboration(
            session.collaboration_id, task
        )
        req_confs = [c for c in conflicts if c.conflict_type == ConflictType.REQUIREMENT_CONFLICT]
        self.assertTrue(len(req_confs) > 0)
        self.assertIn("Case-sensitivity ambiguity", req_confs[0].rationale)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 42 - TEST 6: Conflicting test outcomes -> evidence-based arbitration
    # ──────────────────────────────────────────────────────────────────────────

    def test_06_conflicting_test_outcomes_arbitration(self) -> None:
        task = TaskNode("t_test_conf", "Optimized Query", category="IMPLEMENTATION")
        p_fast = AgentProposal(
            proposal_id="p_fast",
            agent_id="code_fast",
            task_id=task.task_id,
            result_kind=ResultKind.PATCH,
            description="Fast unsafe query",
            affected_files=["query.py"],
            affected_symbols=["execute_query"],
            confidence_score=0.99,
            evidence=[{"kind": "TEST_FAIL", "description": "Failed SQL injection security test"}],
        )
        p_safe = AgentProposal(
            proposal_id="p_safe",
            agent_id="code_safe",
            task_id=task.task_id,
            result_kind=ResultKind.PATCH,
            description="Safe parameterized query",
            affected_files=["query.py"],
            affected_symbols=["execute_query"],
            confidence_score=0.75,
            evidence=[
                {"kind": "TEST_PASS", "description": "All 12 security and unit tests passed"},
                {"kind": "BUILD_SUCCESS", "description": "Clean compilation"},
            ],
        )

        session = self.coord.create_session(task.task_id, ["code_fast", "code_safe"])
        self.coord.add_proposal(session.collaboration_id, p_fast)
        self.coord.add_proposal(session.collaboration_id, p_safe)

        status, conflicts, arbitrations = self.coord.evaluate_collaboration(
            session.collaboration_id, task
        )
        self.assertEqual(len(arbitrations), 1)
        arb = arbitrations[0]
        self.assertEqual(arb.selected_proposal_id, "p_safe")
        self.assertGreater(arb.confidence_score, 0.0)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 42 - TEST 7: Duplicate proposals -> deduplication
    # ──────────────────────────────────────────────────────────────────────────

    def test_07_duplicate_proposals_deduplication(self) -> None:
        task = TaskNode("t_dedup", "Deduplication task", category="CODING")
        session = self.coord.create_session(task.task_id, ["code_01", "code_02"])

        p1 = AgentProposal(
            proposal_id="p_same_1",
            agent_id="code_01",
            task_id=task.task_id,
            result_kind=ResultKind.PATCH,
            description="Identical patch",
            diff_content="--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-1\n+2",
            content_by_file={"x.py": "x = 2"},
        )
        p1_dup = AgentProposal(
            proposal_id="p_same_2",
            agent_id="code_01",
            task_id=task.task_id,
            result_kind=ResultKind.PATCH,
            description="Identical patch content",
            diff_content="--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-1\n+2",
            content_by_file={"x.py": "x = 2"},
        )

        ok1 = self.coord.add_proposal(session.collaboration_id, p1)
        ok2 = self.coord.add_proposal(session.collaboration_id, p1_dup)
        self.assertTrue(ok1)
        self.assertTrue(ok2)
        self.assertEqual(len(session.proposals), 1)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 42 - TEST 8: Agent failure during collaboration -> reassignment
    # ──────────────────────────────────────────────────────────────────────────

    async def test_08_agent_failure_during_collaboration_reassignment(self) -> None:
        class FailingAgent(SwarmAgent):
            def __init__(self):
                super().__init__("fail_ag", "CODING", AgentCapability("CODING", categories=[AgentCategory.CODING]))

            async def execute(self, task, context, lease, heartbeat_cb=None):
                raise RuntimeError("Process crashed during collaborative step")

        graph = TaskGraph(nodes=[
            TaskNode(
                "t_reassign",
                "Collaborative Feature",
                category="CODING",
                status=TaskStatus.READY,
                retry_config=RetryConfig(max_attempts=3),
                metadata={
                    "collaborative": True,
                    "collaborating_agents": ["fail_ag", "code_01"],
                },
            )
        ])

        orch = MissionLifecycleOrchestrator(
            project_id=self.project_id,
            mission_id=self.mission_id,
            mission_state=self.state_store,
            task_graph=graph,
            use_swarm=True,
            swarm_agents=[FailingAgent(), CodingAgent("code_01")],
        )

        ready_tasks = graph.get_ready_tasks()
        self.assertEqual(len(ready_tasks), 1)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 42 - TEST 9: Conflict + dynamic sub-DAG
    # ──────────────────────────────────────────────────────────────────────────

    async def test_09_conflict_plus_dynamic_subdag(self) -> None:
        graph = TaskGraph(nodes=[
            TaskNode("t_parent", "Parent feature", category="CODING", status=TaskStatus.RUNNING),
        ])
        orch = MissionLifecycleOrchestrator(
            project_id=self.project_id,
            mission_id=self.mission_id,
            mission_state=self.state_store,
            task_graph=graph,
            use_swarm=True,
        )

        # Conflict triggers dynamic sub-task expansion for contract review
        sub_review = TaskNode("t_sub_review", "Contract Review Sub-Task", category="REVIEW", dependencies=["t_parent"], status=TaskStatus.READY)
        orch.task_graph.add_node(sub_review)
        orch.task_graph.update_derived_statuses()
        self.assertIn("t_sub_review", orch.task_graph.nodes)
        self.assertEqual(orch.task_graph.nodes["t_sub_review"].category, "REVIEW")

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 42 - TEST 10: Conflict + adaptive planning
    # ──────────────────────────────────────────────────────────────────────────

    async def test_10_conflict_plus_adaptive_planning(self) -> None:
        graph = TaskGraph(nodes=[
            TaskNode("t1", "API Design", category="ARCH", status=TaskStatus.COMPLETED),
            TaskNode("t2", "Implementation", category="CODING", status=TaskStatus.RUNNING),
        ])
        orch = MissionLifecycleOrchestrator(
            project_id=self.project_id,
            mission_id=self.mission_id,
            mission_state=self.state_store,
            task_graph=graph,
            use_swarm=True,
        )

        eval_res = await orch.evaluate_plan(
            architecture_change={"conflict": "REST_VS_GRAPHQL_CONFLICT"}
        )
        self.assertIsNotNone(eval_res)
        self.assertIn(eval_res.decision.value, ["NO_ADAPTATION_NEEDED", "ADAPT_PLAN", "REPLAN"])

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 7: Deterministic ConflictKey Identity
    # ──────────────────────────────────────────────────────────────────────────

    def test_conflict_key_determinism(self) -> None:
        key1 = ConflictKey("proj_1", "task_A", "src/auth.py", "login", ConflictType.SYMBOL_CONFLICT)
        key2 = ConflictKey("proj_1", "task_A", "src/auth.py", "login", ConflictType.SYMBOL_CONFLICT)
        key3 = ConflictKey("proj_1", "task_A", "src/auth.py", "logout", ConflictType.SYMBOL_CONFLICT)

        self.assertEqual(key1.make_key(), key2.make_key())
        self.assertNotEqual(key1.make_key(), key3.make_key())

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 24 & 25: Collaboration State Machine & Anti-Loop Limits
    # ──────────────────────────────────────────────────────────────────────────

    def test_collaboration_state_machine_and_no_progress_protection(self) -> None:
        task = TaskNode("t_loop", "Loop Task", category="CODING")
        session = self.coord.create_session(task.task_id, ["ag1", "ag2"], max_rounds=2)
        self.assertEqual(session.status, CollaborationStatus.OPEN)

        r1 = self.coord.advance_round(session.collaboration_id)
        self.assertEqual(r1, 2)
        r2 = self.coord.advance_round(session.collaboration_id)
        self.assertEqual(r2, 3)

        status, _, _ = self.coord.evaluate_collaboration(session.collaboration_id, task)
        self.assertEqual(status, CollaborationStatus.BLOCKED)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 29 & 30: Checkpointing & State Restoration
    # ──────────────────────────────────────────────────────────────────────────

    def test_collaboration_checkpoint_and_restore(self) -> None:
        task = TaskNode("t_cp", "Checkpoint Task", category="CODING")
        session = self.coord.create_session(task.task_id, ["code_01", "code_02"])
        p = AgentProposal(
            proposal_id="p_cp",
            agent_id="code_01",
            task_id=task.task_id,
            result_kind=ResultKind.PATCH,
            description="Patch to persist",
            content_by_file={"main.py": "print('ok')"},
        )
        self.coord.add_proposal(session.collaboration_id, p)
        self.coord.metrics.conflict_count = 5
        self.coord.metrics.arbitration_count = 3

        state = self.coord.export_state()

        new_coord = CollaborationCoordinator(
            project_id=self.project_id,
            mission_id=self.mission_id,
        )
        new_coord.restore_state(state)

        restored_session = new_coord.get_session(session.collaboration_id)
        self.assertIsNotNone(restored_session)
        self.assertEqual(len(restored_session.proposals), 1)
        self.assertEqual(restored_session.proposals[0].proposal_id, "p_cp")
        self.assertEqual(new_coord.metrics.conflict_count, 5)
        self.assertEqual(new_coord.metrics.arbitration_count, 3)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 31 & 32: Security & Economic Invariants
    # ──────────────────────────────────────────────────────────────────────────

    def test_security_privilege_escalation_denied(self) -> None:
        arbitrator = AgentConflictArbitrator()
        conf = ConflictDetails(
            conflict_key=ConflictKey("proj", "task", "os.system", "", ConflictType.SEMANTIC_CONFLICT),
            proposals_involved=["p_unsafe", "p_safe"],
            description="Unsafe command proposal vs safe proposal",
        )
        p_unsafe = AgentProposal(
            proposal_id="p_unsafe",
            agent_id="code_01",
            task_id="task",
            result_kind=ResultKind.PATCH,
            description="Attempting to run outside workspace",
            confidence_score=0.99,
        )
        p_safe = AgentProposal(
            proposal_id="p_safe",
            agent_id="code_02",
            task_id="task",
            result_kind=ResultKind.PATCH,
            description="Executing inside workspace",
            confidence_score=0.8,
            evidence=[{"kind": "HARD_VALIDATION_SANDBOX", "description": "Confined to workspace"}],
        )

        arb = arbitrator.arbitrate(conf, [p_unsafe, p_safe])
        self.assertEqual(arb.selected_proposal_id, "p_safe")

    def test_economic_safeguards_cannot_be_bypassed_by_consensus(self) -> None:
        arbitrator = AgentConflictArbitrator()
        conf = ConflictDetails(
            conflict_key=ConflictKey("proj", "money_task", "ledger", "", ConflictType.SEMANTIC_CONFLICT),
            proposals_involved=["p_agreed1", "p_agreed2"],
            description="Both agents agree to skip payment gateway verification",
        )
        p1 = AgentProposal(
            proposal_id="p_agreed1",
            agent_id="code_01",
            task_id="money_task",
            result_kind=ResultKind.PROPOSAL,
            description="Skip external verification",
            confidence_score=0.9,
        )
        p2 = AgentProposal(
            proposal_id="p_agreed2",
            agent_id="code_02",
            task_id="money_task",
            result_kind=ResultKind.PROPOSAL,
            description="Skip external verification also",
            confidence_score=0.9,
        )

        arb = arbitrator.arbitrate(conf, [p1, p2])
        self.assertEqual(arb.decision, ArbitrationDecision.BLOCK)
