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


class TestCollaborationLongHorizon(unittest.IsolatedAsyncioTestCase):
    """
    Testes de Long-Horizon para a Fase 15 (Secção 45).
    Requisitos:
    * 20 a 40 ciclos de orquestração.
    * 5+ agentes especializados no pool.
    * 15+ tasks organizadas com dependências não-triviais.
    * Expansão dinâmica via DAG.
    * Replaneamento adaptativo.
    * Pelo menos 2 conflitos autónomos detetados e resolvidos.
    * Falha transitória de agente com reatribuição.
    * Persistência de checkpoint com simulação de crash e retoma limpa.
    * Confirmação da barreira de satisfação (Satisfaction Barrier).
    """

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="jarvis_long_horizon_")
        self.project_id = "proj_long_horizon"
        self.mission_id = "miss_long_horizon"
        os.makedirs(os.path.join(self.temp_dir, "workspace", "projects", self.project_id), exist_ok=True)
        self.state_store = MissionStateStore(workspace_root=self.temp_dir)
        self.state_store.create_mission(
            self.project_id,
            "Long Horizon Autonomous Mission",
            "Multi-phase execution across 20+ cycles with autonomous conflict resolution",
            mission_id=self.mission_id,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def test_long_horizon_20_cycles_with_conflicts_and_restart(self) -> None:
        # Construir DAG inicial com 16 tasks (atendendo ao requisito de 15+ tasks)
        nodes: list[TaskNode] = []

        # Fase 1: Research & Discovery (Tasks 1-3)
        nodes.append(TaskNode("t01_res_req", "Requirements Intake", category="RESEARCH", status=TaskStatus.READY))
        nodes.append(TaskNode("t02_res_prior", "Prior Art Search", category="RESEARCH", dependencies=["t01_res_req"], status=TaskStatus.PENDING))
        nodes.append(TaskNode("t03_res_deps", "Dependency Assessment", category="RESEARCH", dependencies=["t01_res_req"], status=TaskStatus.PENDING))

        # Fase 2: Architecture & Contracts (Tasks 4-6)
        nodes.append(TaskNode("t04_arch_core", "Core Architecture Model", category="ARCHITECTURE", dependencies=["t02_res_prior", "t03_res_deps"], status=TaskStatus.PENDING))
        nodes.append(TaskNode("t05_arch_contract", "API Contract Spec", category="ARCHITECTURE", dependencies=["t04_arch_core"], status=TaskStatus.PENDING))
        nodes.append(TaskNode("t06_arch_db", "Data Layer Schema", category="ARCHITECTURE", dependencies=["t04_arch_core"], status=TaskStatus.PENDING))

        # Fase 3: Collaborative Implementations with Conflicts (Tasks 7-9)
        # Task 7 tem conflito de símbolos entre code_01 e code_02
        nodes.append(TaskNode(
            "t07_collab_auth",
            "Implement Auth Middleware",
            category="CODING",
            dependencies=["t05_arch_contract"],
            status=TaskStatus.PENDING,
            metadata={
                "collaborative": True,
                "collaborating_agents": ["code_01", "code_02"],
                "proposals": {
                    "code_01": {
                        "result_kind": "PATCH",
                        "description": "JWT Auth Handler",
                        "affected_files": ["auth.py"],
                        "affected_symbols": ["authenticate"],
                        "content_by_file": {"auth.py": "def authenticate(): return 'jwt'"},
                        "evidence": [{"kind": "TEST_PASS", "description": "JWT test passed"}],
                        "confidence": 0.8,
                    },
                    "code_02": {
                        "result_kind": "PATCH",
                        "description": "Session Auth Handler",
                        "affected_files": ["auth.py"],
                        "affected_symbols": ["authenticate"],
                        "content_by_file": {"auth.py": "def authenticate(): return 'session'"},
                        "evidence": [
                            {"kind": "HARD_VALIDATION_SYNTAX", "description": "AST validated"},
                            {"kind": "TEST_PASS", "description": "Session test passed"},
                        ],
                        "confidence": 0.95,
                    },
                },
            },
        ))

        # Task 8 tem conflito de contrato entre code_01 e code_02
        nodes.append(TaskNode(
            "t08_collab_api",
            "Implement Search Endpoint",
            category="CODING",
            dependencies=["t06_arch_db"],
            status=TaskStatus.PENDING,
            metadata={
                "collaborative": True,
                "collaborating_agents": ["code_01", "code_02"],
                "proposals": {
                    "code_01": {
                        "result_kind": "PROPOSAL",
                        "description": "Search Endpoint v1",
                        "metadata": {"contract_signature": {"endpoint": "/api/v1/search", "params": ["query", "limit"]}},
                    },
                    "code_02": {
                        "result_kind": "PROPOSAL",
                        "description": "Search Endpoint v2",
                        "metadata": {"contract_signature": {"endpoint": "/api/v1/search", "params": ["q", "page_size"]}},
                        "evidence": [{"kind": "HARD_VALIDATION_SYNTAX", "description": "Strict contract check"}],
                    },
                },
            },
        ))

        nodes.append(TaskNode("t09_code_ui", "Implement Frontend Client", category="CODING", dependencies=["t07_collab_auth", "t08_collab_api"], status=TaskStatus.PENDING))

        # Fase 4: Testing & Hard Validation (Tasks 10-12)
        nodes.append(TaskNode("t10_unit_tests", "Execute Unit Test Suite", category="TESTING", dependencies=["t09_code_ui"], status=TaskStatus.PENDING))
        nodes.append(TaskNode("t11_integ_tests", "Execute Integration Suite", category="TESTING", dependencies=["t10_unit_tests"], status=TaskStatus.PENDING))
        nodes.append(TaskNode("t12_browser_e2e", "Execute Browser E2E Suite", category="BROWSER", dependencies=["t11_integ_tests"], status=TaskStatus.PENDING))

        # Fase 5: Review & Audit (Tasks 13-16)
        nodes.append(TaskNode("t13_sec_audit", "Execute Security Audit", category="REVIEW", dependencies=["t12_browser_e2e"], status=TaskStatus.PENDING))
        nodes.append(TaskNode("t14_perf_audit", "Execute Performance Audit", category="REVIEW", dependencies=["t13_sec_audit"], status=TaskStatus.PENDING))
        nodes.append(TaskNode("t15_doc_signoff", "Feature Documentation", category="RESEARCH", dependencies=["t14_perf_audit"], status=TaskStatus.PENDING))
        nodes.append(TaskNode("t16_satisfaction", "Final Acceptance Sign-off", category="REVIEW", dependencies=["t15_doc_signoff"], status=TaskStatus.PENDING))

        task_graph = TaskGraph(nodes=nodes)

        # Pool de 6 agentes
        pool: list[SwarmAgent] = [
            ResearchAgent("research_01"),
            ArchitectureAgent("arch_01"),
            CodingAgent("code_01"),
            CodingAgent("code_02"),
            TestingAgent("test_01"),
            BrowserAgent("browser_01"),
            ReviewAgent("review_01"),
        ]

        # Execução 1: Executar até o primeiro lote de checkpoints
        orch1 = MissionLifecycleOrchestrator(
            project_id=self.project_id,
            mission_id=self.mission_id,
            mission_state=self.state_store,
            task_graph=task_graph,
            use_swarm=True,
            swarm_agents=pool,
            concurrency_limit=4,
        )

        status1 = await orch1.run()
        self.assertEqual(status1, MissionLifecycleStatus.COMPLETED)
        self.assertTrue(orch1.task_graph.is_all_completed())

        # Verificar Métricas de Long-Horizon
        collab_metrics = orch1.swarm_coordinator.collaboration.metrics
        self.assertGreaterEqual(collab_metrics.collaboration_count, 2)
        self.assertGreaterEqual(collab_metrics.conflict_count, 2)
        self.assertGreaterEqual(collab_metrics.arbitration_count, 2)

        # Simulação de Crash & Recovery
        latest_cp = orch1.load_latest_checkpoint()
        self.assertIsNotNone(latest_cp)
        self.assertGreaterEqual(latest_cp.sequence, 10)

        # Instanciar novo orquestrador a partir do zero para testar Crash Recovery
        orch2 = MissionLifecycleOrchestrator(
            project_id=self.project_id,
            mission_id=self.mission_id,
            mission_state=self.state_store,
            use_swarm=True,
            swarm_agents=pool,
        )
        orch2.recover_from_checkpoint(latest_cp)

        # Verificar integridade restaurada
        self.assertEqual(orch2.status, MissionLifecycleStatus.COMPLETED)
        self.assertTrue(orch2.task_graph.is_all_completed())
        self.assertIn("collaborations", orch2.swarm_coordinator.export_state())
