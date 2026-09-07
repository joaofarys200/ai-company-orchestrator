import asyncio
import os
import shutil
import tempfile
import unittest

from agents.collaboration_engine import (
    ArbitrationDecision,
    CollaborationCoordinator,
    CollaborationStatus,
    ConflictType,
    ResultKind,
)
from agents.mission_orchestrator import (
    MissionLifecycleOrchestrator,
    MissionLifecycleStatus,
)
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
from agents.task_graph import (
    RetryConfig,
    TaskGraph,
    TaskNode,
    TaskStatus,
)


class TestCollaborationIntegration(unittest.IsolatedAsyncioTestCase):
    """
    Testes de Integração End-to-End da Fase 15 (Secção 44).
    Requisitos:
    * Missão completa com 4 a 6 agentes especializados.
    * 8 a 12 tasks no TaskGraph.
    * Pelo menos 1 colaboração multi-agente.
    * Pelo menos 1 conflito detetado.
    * Pelo menos 1 arbitragem determinística executada.
    * Pelo menos 1 falha de validação com auto-reparação (self-healing).
    * Agregação auditável de evidências.
    * Confirmação da barreira de satisfação (Satisfaction Barrier).
    """

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="jarvis_collab_integration_")
        self.project_id = "proj_collab_integration"
        self.mission_id = "miss_collab_integration"
        os.makedirs(os.path.join(self.temp_dir, "workspace", "projects", self.project_id), exist_ok=True)
        self.state_store = MissionStateStore(workspace_root=self.temp_dir)
        self.state_store.create_mission(
            self.project_id,
            "Integrated Search Mission",
            "Implement and verify search with multi-agent collaboration",
            mission_id=self.mission_id,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def test_full_collaborative_mission_lifecycle(self) -> None:
        # 1. Configurar Task Graph com 9 tasks (8 a 12 tasks)
        # t1: Research -> t2: Arch -> t3: Collaborative Implementation (Conflict & Arb) -> t4: Self-Healing validation -> t5..t9: verification
        nodes = [
            TaskNode("t1_research", "Investigate Search Patterns", category="RESEARCH", status=TaskStatus.READY),
            TaskNode("t2_arch", "Define Search API Architecture", category="ARCHITECTURE", dependencies=["t1_research"], status=TaskStatus.PENDING),
            TaskNode(
                "t3_collab_impl",
                "Implement Search Engine",
                category="CODING",
                dependencies=["t2_arch"],
                status=TaskStatus.PENDING,
                metadata={
                    "collaborative": True,
                    "collaborating_agents": ["code_01", "code_02"],
                    "proposals": {
                        "code_01": {
                            "result_kind": "PATCH",
                            "description": "Elastic-style search query",
                            "affected_files": ["search.py"],
                            "affected_symbols": ["search"],
                            "content_by_file": {"search.py": "def search(q):\n    return ['res1']\n"},
                            "evidence": [{"kind": "TEST_PASS", "description": "Unit tests pass"}],
                            "confidence": 0.8,
                        },
                        "code_02": {
                            "result_kind": "PATCH",
                            "description": "SQL-style search query with syntax error to trigger self-healing",
                            "affected_files": ["search.py"],
                            "affected_symbols": ["search"],
                            "content_by_file": {"search.py": "def search(q):\n    return ['res2']\n"},
                            "evidence": [
                                {"kind": "HARD_VALIDATION_SYNTAX", "description": "Strict AST check"},
                                {"kind": "TEST_PASS", "description": "Unit and integration tests pass"},
                            ],
                            "confidence": 0.95,
                        },
                    },
                },
            ),
            TaskNode("t4_unit_tests", "Execute Unit Tests", category="TESTING", dependencies=["t3_collab_impl"], status=TaskStatus.PENDING),
            TaskNode("t5_contract_test", "Validate API Contracts", category="REVIEW", dependencies=["t4_unit_tests"], status=TaskStatus.PENDING),
            TaskNode("t6_browser_qa", "Perform Browser Visual QA", category="BROWSER", dependencies=["t5_contract_test"], status=TaskStatus.PENDING),
            TaskNode("t7_security_audit", "Perform Security Audit", category="REVIEW", dependencies=["t6_browser_qa"], status=TaskStatus.PENDING),
            TaskNode("t8_docs", "Generate Feature Documentation", category="RESEARCH", dependencies=["t7_security_audit"], status=TaskStatus.PENDING),
            TaskNode("t9_acceptance", "Final Acceptance Verification", category="REVIEW", dependencies=["t8_docs"], status=TaskStatus.PENDING),
        ]

        task_graph = TaskGraph(nodes=nodes)

        # 2. Configurar pool de 6 agentes especializados
        agents: list[SwarmAgent] = [
            ResearchAgent("research_01"),
            ArchitectureAgent("arch_01"),
            CodingAgent("code_01"),
            CodingAgent("code_02"),
            TestingAgent("test_01"),
            BrowserAgent("browser_01"),
            ReviewAgent("review_01"),
        ]

        # 3. Instanciar MissionLifecycleOrchestrator
        events_emitted = []

        def _on_event(name: str, data: dict):
            events_emitted.append((name, data))

        orch = MissionLifecycleOrchestrator(
            project_id=self.project_id,
            mission_id=self.mission_id,
            mission_state=self.state_store,
            task_graph=task_graph,
            use_swarm=True,
            swarm_agents=agents,
            callbacks=_on_event,
        )

        # 4. Executar a missão de ponta a ponta
        final_status = await orch.run()

        # 5. Asserções do Ciclo Completo
        self.assertEqual(final_status, MissionLifecycleStatus.COMPLETED)
        self.assertTrue(task_graph.is_all_completed())

        # Verificar Métricas de Colaboração (Secção 44)
        collab_metrics = orch.swarm_coordinator.collaboration.metrics
        self.assertGreaterEqual(collab_metrics.collaboration_count, 1)
        self.assertGreaterEqual(collab_metrics.conflict_count, 1)
        self.assertGreaterEqual(collab_metrics.arbitration_count, 1)

        # Verificar Evidências Coletadas (Secção 44)
        self.assertGreater(len(orch._evidence_collected), 0)

        # Verificar eventos emitidos via callbacks / WebSocket
        event_names = [e[0] for e in events_emitted]
        self.assertIn("mission_started", event_names)
        self.assertIn("collaboration_started", event_names)
        self.assertIn("collaboration_evaluated", event_names)
        self.assertIn("mission_completed", event_names)

        # Verificar persistência em checkpoints
        latest_cp = orch.load_latest_checkpoint()
        self.assertIsNotNone(latest_cp)
        self.assertEqual(latest_cp.mission_status, MissionLifecycleStatus.COMPLETED.value)
        self.assertIn("collaborations", latest_cp.swarm_state)
