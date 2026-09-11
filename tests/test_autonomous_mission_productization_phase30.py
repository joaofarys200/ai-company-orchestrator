"""
JARVIS OS — Phase 30 Unit Test Suite
Autonomous Mission Productization & Full End-to-End Execution
"""

import asyncio
import os
import shutil
import sqlite3
import tempfile
import unittest

from agents.autonomous_mission_productization import (
    AutonomyScorecard,
    AutonomousMissionPlanner,
    AutonomousMissionProductizationEngine,
    LimitBoundaries,
    LimitClass,
    MissionProductizationCategory,
    RealArtifactSynthesizer,
)
from agents.autonomous_mission_engine import (
    EvidenceProvenance,
    FailureEscalationGovernance,
    FailureEscalationLevel,
    FaultType,
    MissionEvidenceItem,
    RetryBudgets,
    SelfHealingEngine,
)
from agents.mission_state import MissionStateStore
from backend.services.chat_mission_bridge import ChatMissionBridge
from backend.websocket.gateway import ConnectionManager
from database import init_db


class RecordingConnectionManager(ConnectionManager):
    def __init__(self):
        super().__init__()
        self.sent_messages = []

    async def broadcast(self, message: dict) -> None:
        self.sent_messages.append(message)


class TestAutonomousMissionProductizationPhase30(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="jarvis_phase30_test_")
        self.store = MissionStateStore(os.path.join(self.test_dir, "missions"))
        self.engine = AutonomousMissionProductizationEngine(
            mission_state=self.store,
            base_dir=os.path.join(self.test_dir, "apps"),
        )

    async def asyncTearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_minimalist_category_inference_all_10_categories(self):
        """Validates that minimalist natural language prompts map to all 10 canonical categories."""
        test_prompts = {
            "Cria uma interface web simples de visualização com dashboard": MissionProductizationCategory.SIMPLE_FRONTEND,
            "Cria frontend e backend para processamento de ficheiros": MissionProductizationCategory.FRONTEND_BACKEND,
            "Cria uma aplicação de despesas com pesquisa e filtros": MissionProductizationCategory.CRUD_APPLICATION,
            "Encontra e corrige um bug no cálculo de impostos": MissionProductizationCategory.BUG_REPAIR,
            "Adiciona autenticação com tokens seguros": MissionProductizationCategory.FEATURE_IMPLEMENTATION,
            "Desenvolve um full stack app de mensagens em tempo real": MissionProductizationCategory.FULL_STACK_APP,
            "Executa test repair para corrigir suite de regressão": MissionProductizationCategory.TEST_REPAIR,
            "Corrige uma falha de build no módulo principal": MissionProductizationCategory.BUILD_REPAIR,
            "Valida a aplicação no browser e verifica o DOM": MissionProductizationCategory.BROWSER_VALIDATION,
            "Refatora a camada de dados em múltiplos passos": MissionProductizationCategory.MULTI_STEP_REFACTOR,
        }

        self.assertEqual(len(test_prompts), 10)
        for prompt, expected_cat in test_prompts.items():
            cat = AutonomousMissionPlanner.infer_category(prompt)
            self.assertEqual(cat, expected_cat, f"Prompt '{prompt}' should infer {expected_cat}")

    def test_02_autonomous_dag_and_artifact_generation(self):
        """Validates autonomous DAG generation, topological order, and artifact inference."""
        prompt = "Cria uma aplicação web simples de tarefas com pesquisa e filtros."
        plan = AutonomousMissionPlanner.generate_plan(prompt, base_dir=self.test_dir)

        self.assertEqual(plan.category, MissionProductizationCategory.CRUD_APPLICATION)
        self.assertTrue(plan.requires_browser)
        self.assertGreaterEqual(len(plan.tasks), 5)
        self.assertIn("index.html", plan.target_artifacts[0])

        # Test real artifact synthesis
        app_dir = os.path.join(self.test_dir, plan.project_slug)
        created = RealArtifactSynthesizer.synthesize_todo_app(app_dir)
        self.assertIn(os.path.join(app_dir, "index.html"), created)
        self.assertIn(os.path.join(app_dir, "backend_service.py"), created)
        self.assertTrue(os.path.isfile(os.path.join(app_dir, "index.html")))
        self.assertTrue(os.path.isfile(os.path.join(app_dir, "backend_service.py")))

    def test_03_autonomous_repair_minimality(self):
        """Validates AST-driven self-healing with zero unrelated changes."""
        broken_code = "def calculate_total(a, b)\n    return a + b\n"
        rep = SelfHealingEngine.diagnose_and_repair(
            "calc.py", broken_code, "SyntaxError: expected ':'"
        )
        self.assertTrue(rep.success)
        self.assertEqual(rep.unrelated_changes, 0)
        self.assertIn("def calculate_total(a, b):", rep.repaired_code)

    def test_04_failure_escalation_chain(self):
        """Validates finite escalation: RETRY -> REPAIR -> REPLAN -> REASSIGN -> ROLLBACK -> BLOCK."""
        budgets = RetryBudgets()

        # Syntax error -> REPAIR
        d1 = FailureEscalationGovernance.decide_escalation(FaultType.SYNTAX_ERROR, 1, budgets)
        self.assertEqual(d1, FailureEscalationLevel.REPAIR)

        # Consume repair budget
        budgets.repair_budget = 0
        d2 = FailureEscalationGovernance.decide_escalation(FaultType.SYNTAX_ERROR, 2, budgets)
        self.assertEqual(d2, FailureEscalationLevel.REPLAN)

        # Consume replan budget
        budgets.replan_budget = 0
        d3 = FailureEscalationGovernance.decide_escalation(FaultType.SYNTAX_ERROR, 3, budgets)
        self.assertEqual(d3, FailureEscalationLevel.ROLLBACK)

    def test_05_evidence_provenance_and_satisfaction(self):
        """Validates that self-reported results are rejected and validated evidence is accepted."""
        ev_self = MissionEvidenceItem(
            evidence_id="ev_01",
            task_id="t_01",
            producer_agent="agent_1",
            provenance=EvidenceProvenance.SELF_REPORTED,
            kind="LOG",
            description="Self reported success",
            hash_signature="hash1",
        )
        self.assertFalse(ev_self.is_acceptable_for_completion())

        ev_val = MissionEvidenceItem(
            evidence_id="ev_02",
            task_id="t_02",
            producer_agent="test_agent",
            provenance=EvidenceProvenance.VALIDATED,
            kind="TEST_PASS",
            description="Pytest passed with 0 errors",
            hash_signature="hash2",
        )
        self.assertTrue(ev_val.is_acceptable_for_completion())

    async def test_06_e2e_autonomous_minimalist_mission_execution(self):
        """Executes full autonomous mission from minimalist prompt."""
        prompt = "Cria uma aplicação web simples de tarefas com pesquisa e filtros."
        result = await self.engine.execute_minimalist_goal(prompt)

        self.assertTrue(result.execution_success)
        self.assertTrue(result.requirement_satisfaction)
        self.assertEqual(result.human_intervention_count, 0)
        self.assertEqual(result.final_status, "COMPLETED")
        self.assertTrue(result.first_pass_success)
        self.assertGreaterEqual(result.evidence_count, 5)

    async def test_07_autonomous_mission_with_fault_injection_and_repair(self):
        """Validates controlled fault injection, self-healing, and eventual autonomous success."""
        prompt = "Encontra e corrige um bug introduzido deliberadamente."
        result = await self.engine.execute_minimalist_goal(
            prompt, inject_fault=FaultType.SYNTAX_ERROR
        )

        self.assertTrue(result.execution_success)
        self.assertTrue(result.requirement_satisfaction)
        self.assertEqual(result.human_intervention_count, 0)
        self.assertFalse(result.first_pass_success)
        self.assertTrue(result.eventual_success)
        self.assertGreaterEqual(result.repair_count, 1)

    async def test_08_chat_bridge_delegation_to_autonomous_engine(self):
        """Validates that ChatMissionBridge routes through autonomous productization engine."""
        test_db = os.path.join(self.test_dir, "chat_test.db")
        os.environ["DATABASE_URL"] = test_db
        init_db()

        conn_mgr = RecordingConnectionManager()
        bridge = ChatMissionBridge(
            mission_state=self.store,
            autonomous_engine=self.engine,
            connections=conn_mgr,
        )

        res = await bridge.handle_directive(
            prompt="Cria uma aplicação web simples de tarefas com pesquisa e filtros.",
            session_id=1,
            project_id="auto-todo-app",
            correlation_id="phase30_corr_01",
        )

        self.assertEqual(res["status"], "COMPLETED")
        self.assertIn("m_phase30_corr_01", res["mission_id"])

        # Check that mission is completed in MissionStateStore
        m = self.store.load_mission("auto-todo-app", res["mission_id"])
        self.assertEqual(m["mission"]["status"], "COMPLETED")

    def test_09_autonomy_scorecard_and_limit_classifications(self):
        """Validates the autonomy scorecard calculation and limit boundary definitions."""
        card = AutonomyScorecard(
            total_missions=10,
            successful_missions=10,
            mission_success_rate=1.0,
            first_pass_success_rate=0.8,
            eventual_success_rate=1.0,
            repair_success_rate=1.0,
            replan_success_rate=1.0,
            human_intervention_rate=0.0,
            requirement_satisfaction_rate=1.0,
            browser_validation_rate=1.0,
            regression_rate=0.0,
            total_human_interventions=0,
            total_repairs=2,
            total_replans=0,
        )

        d = card.to_dict()
        self.assertEqual(d["mission_success_rate"], 1.0)
        self.assertEqual(d["total_human_interventions"], 0)

        limits = LimitBoundaries()
        self.assertIn("Chromium", limits.browser_limit)
        self.assertIn("cryptocurrency", limits.first_real_failure)
        self.assertIn("closed-source", limits.first_unresolved_autonomous_failure)


if __name__ == "__main__":
    unittest.main()
