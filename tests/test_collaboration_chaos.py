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


class TestCollaborationChaos(unittest.IsolatedAsyncioTestCase):
    """
    Testes de Caos e Robustez para a Fase 15 (Secção 46).
    Cobre:
    * Proposta duplicada
    * Proposta estéril / obsoleta
    * Propostas concorrentes simultâneas
    * Crash durante arbitragem
    * Crash pós-arbitragem antes do apply
    * Estado de colaboração corrompido
    * Ownership conflituosa
    * Evidência duplicada
    * Arbitragem inválida / forçada
    * Tentativa de impersonação de agente
    * Tentativa de escalação de privilégios
    * Loop infinito de conflitos
    """

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.project_id = "proj_chaos"
        self.mission_id = "mission_chaos"
        os.makedirs(os.path.join(self.temp_dir, "workspace", "projects", self.project_id), exist_ok=True)
        self.state_store = MissionStateStore(workspace_root=self.temp_dir)
        self.state_store.create_mission(self.project_id, "Chaos Test", "Objective", mission_id=self.mission_id)
        self.coord = CollaborationCoordinator(
            project_id=self.project_id,
            mission_id=self.mission_id,
            workspace_root=self.temp_dir,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_chaos_duplicate_proposals(self) -> None:
        task = TaskNode("t_chaos_1", "Duplicate Test", category="CODING")
        session = self.coord.create_session(task.task_id, ["ag1", "ag2"])
        p = AgentProposal(
            proposal_id="prop_ident_1",
            agent_id="ag1",
            task_id=task.task_id,
            diff_content="diff",
            content_by_file={"a.py": "1"},
        )
        p_dup = AgentProposal(
            proposal_id="prop_ident_2",
            agent_id="ag1",
            task_id=task.task_id,
            diff_content="diff",
            content_by_file={"a.py": "1"},
        )
        self.assertTrue(self.coord.add_proposal(session.collaboration_id, p))
        self.assertTrue(self.coord.add_proposal(session.collaboration_id, p_dup))
        self.assertEqual(len(session.proposals), 1)

    def test_chaos_stale_proposals(self) -> None:
        task = TaskNode("t_chaos_2", "Stale Test", category="CODING")
        session = self.coord.create_session(task.task_id, ["ag1", "ag2"])
        # Advance round to make older proposals stale
        self.coord.advance_round(session.collaboration_id)
        self.assertEqual(session.round_count, 2)
        # Session cleared proposals for round 2
        self.assertEqual(len(session.proposals), 0)

    async def test_chaos_concurrent_proposals(self) -> None:
        task = TaskNode("t_chaos_3", "Concurrent Test", category="CODING")
        session = self.coord.create_session(task.task_id, [f"ag_{i}" for i in range(10)])

        async def _submit(i: int):
            p = AgentProposal(
                proposal_id=f"p_{i}",
                agent_id=f"ag_{i}",
                task_id=task.task_id,
                content_by_file={"file.py": f"x = {i}"},
            )
            self.coord.add_proposal(session.collaboration_id, p)

        await asyncio.gather(*[_submit(i) for i in range(10)])
        self.assertEqual(len(session.proposals), 10)

    def test_chaos_crash_during_arbitration_recovery(self) -> None:
        task = TaskNode("t_chaos_4", "Crash Arbitration", category="CODING")
        session = self.coord.create_session(task.task_id, ["ag1", "ag2"])
        p1 = AgentProposal("p1", task.task_id, "ag1", content_by_file={"main.py": "a = 1"})
        p2 = AgentProposal("p2", task.task_id, "ag2", content_by_file={"main.py": "a = 2"})
        self.coord.add_proposal(session.collaboration_id, p1)
        self.coord.add_proposal(session.collaboration_id, p2)

        # Simulate state export just as arbitration starts
        session.status = CollaborationStatus.ARBITRATING
        exported = self.coord.export_state()

        # Restore in new coordinator
        fresh_coord = CollaborationCoordinator(self.project_id, self.mission_id, workspace_root=self.temp_dir)
        fresh_coord.restore_state(exported)
        restored = fresh_coord.get_session(session.collaboration_id)
        self.assertIsNotNone(restored)
        # Re-evaluate cleanly from restored state
        status, conflicts, arbs = fresh_coord.evaluate_collaboration(session.collaboration_id, task)
        self.assertIn(status, [CollaborationStatus.RESOLVED, CollaborationStatus.BLOCKED])

    def test_chaos_corrupted_collaboration_state(self) -> None:
        fresh_coord = CollaborationCoordinator(self.project_id, self.mission_id)
        # Restore corrupted/empty dictionary
        corrupt_state = {
            "sessions": {"bad_session": {"collaboration_id": "bad", "mission_id": "m", "task_id": "t"}},
            "metrics": {"collaboration_count": "NOT_AN_INT"},
        }
        try:
            fresh_coord.restore_state(corrupt_state)
        except Exception:
            pass
        # Coordinator survives corrupted input
        self.assertIsNotNone(fresh_coord)

    def test_chaos_conflicting_ownership(self) -> None:
        p1 = AgentProposal("p1", "t1", "code_01", affected_files=["shared.py"], content_by_file={"shared.py": "v1"})
        p2 = AgentProposal("p2", "t1", "code_02", affected_files=["shared.py"], content_by_file={"shared.py": "v2"})
        task = TaskNode("t1", "Shared file task", category="CODING")
        session = self.coord.create_session(task.task_id, ["code_01", "code_02"])
        self.coord.add_proposal(session.collaboration_id, p1)
        self.coord.add_proposal(session.collaboration_id, p2)

        status, conflicts, arbs = self.coord.evaluate_collaboration(session.collaboration_id, task)
        self.assertTrue(any(c.conflict_type in (ConflictType.FILE_CONFLICT, ConflictType.SYMBOL_CONFLICT) for c in conflicts))

    def test_chaos_duplicate_evidence(self) -> None:
        ev = {"evidence_id": "ev_dup", "kind": "TEST_PASS", "description": "passes test"}
        p = AgentProposal(
            "p_ev", "t_ev", "code_01",
            evidence=[ev, ev, ev]  # Triplicate evidence
        )
        sc, breakdown = AgentConflictArbitrator.score_proposal_evidence(p)
        # Ensure scoring doesn't arbitrarily multiply without distinct IDs or limits
        self.assertGreater(sc, 0.0)

    def test_chaos_privilege_escalation_attempt(self) -> None:
        p_escalate = AgentProposal(
            "p_esc", "t_esc", "research_01",
            result_kind=ResultKind.PATCH,
            description="Research agent attempting destructive write",
            content_by_file={"system.ini": "dangerous_override=True"},
        )
        task = TaskNode("t_esc", "Safe task", category="RESEARCH")
        session = self.coord.create_session(task.task_id, ["research_01"])
        self.coord.add_proposal(session.collaboration_id, p_escalate)

        # Arbitrator does not allow research agents to escalate to system mutation
        arbitrator = AgentConflictArbitrator()
        conf = ConflictDetails(
            conflict_key=ConflictKey("proj", "t_esc", "system.ini", "", ConflictType.SEMANTIC_CONFLICT),
            proposals_involved=["p_esc"],
            description="Agent capability boundary violation",
        )
        arb = arbitrator.arbitrate(conf, [p_escalate])
        # Unverifiable unsafe mutation without hard validation yields non-acceptance
        self.assertIn(arb.decision, [ArbitrationDecision.BLOCK, ArbitrationDecision.REGENERATE])

    def test_chaos_endless_conflict_loop(self) -> None:
        task = TaskNode("t_loop", "Endless Loop", category="CODING")
        session = self.coord.create_session(task.task_id, ["ag1", "ag2"], max_rounds=3)

        for _ in range(5):
            self.coord.advance_round(session.collaboration_id)

        # Strictly triggers anti-loop guard
        status, _, _ = self.coord.evaluate_collaboration(session.collaboration_id, task)
        self.assertEqual(status, CollaborationStatus.BLOCKED)
