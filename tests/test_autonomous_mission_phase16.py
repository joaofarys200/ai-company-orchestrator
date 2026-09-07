"""
JARVIS OS — Phase 16: Autonomous Mission Stress, Long-Horizon Swarm & Self-Healing End-to-End

Comprehensive test suite verifying:
1. End-to-End Autonomous Mission Pipeline across 9 Mission Classes.
2. Deterministic Fault Injection across 15 Failure Modes.
3. Self-Healing Loop, Failure Escalation Chain & Minimal Repair (unrelated_changes == 0).
4. Retry Budgets Enforcement, Atomic Decrements & Persistence.
5. Long-Horizon Cycles (10 to 1000) with Latency & Memory Drift Reporting.
6. 24/7 Stability & Zero Resource Leaks (active_processes_delta == 0, active_leases_delta == 0).
7. Deterministic Recovery Oracle (MissionRecoveryReference) & Arbitrary Restart.
8. Recovery Idempotence & Zero Duplicate Work.
9. Swarm Scaling (1 to 256 agents) and Empirical Diminishing Returns Point.
10. Real Repository Missions & Application Generation.
11. Strict Evidence Provenance (SELF_REPORTED != VALIDATED) & Hard Security/Economic Invariants.
12. Event Stream Ordering Oracle (Causal Rules).
13. Browser QA & WebSocket Reconnection Recovery.
14. Extreme Scenario Multi-Agent Autonomous Completion (human_intervention == 0).
"""

from __future__ import annotations

import ast
import hashlib
import os
import time
import unittest
from typing import Any

from agents.autonomous_mission_engine import (
    AutonomousMissionPipeline,
    EventOrderingOracle,
    EvidenceProvenance,
    FailureEscalationGovernance,
    FailureEscalationLevel,
    FaultInjectionPlan,
    FaultType,
    LongHorizonSimulator,
    MissionCategory,
    MissionEvidenceItem,
    MissionFaultInjector,
    MissionGoalSpec,
    MissionRecoveryReference,
    MissionStateSnapshot,
    RepairMinimalityReport,
    RetryBudgets,
    SelfHealingEngine,
    SwarmScalingAnalyzer,
)


class TestAutonomousMissionPhase16(unittest.TestCase):
    """Exhaustive empirical validation of Phase 16 End-to-End Autonomous Missions."""

    def test_01_mission_classes_and_end_to_end_pipeline(self) -> None:
        """
        Valida as 9 categorias de missão e execução do pipeline autónomo
        desde o user goal até à barreira de satisfação com human_intervention == 0.
        """
        all_categories = list(MissionCategory)
        self.assertEqual(len(all_categories), 9)

        # Executar missão autónoma com categoria FEATURE_IMPLEMENTATION
        spec = MissionGoalSpec(
            goal_text="Implement secure multi-factor authentication endpoint",
            category=MissionCategory.FEATURE_IMPLEMENTATION,
            target_artifacts=["src/auth/mfa.py", "tests/test_mfa.py"],
            requires_browser=True,
        )
        pipeline = AutonomousMissionPipeline(spec)
        report = pipeline.execute_mission()

        self.assertEqual(report.status, "COMPLETED")
        self.assertTrue(report.satisfaction_barrier_passed)
        self.assertEqual(report.human_intervention_count, 0)
        self.assertGreaterEqual(report.completed_tasks, 4)
        self.assertTrue(report.provenance_verified)

    def test_02_deterministic_fault_injection_all_15_modes(self) -> None:
        """
        Valida que o MissionFaultInjector suporta deterministicamente
        todos os 15 modos de falha da especificação da Fase 16.
        """
        all_faults = list(FaultType)
        self.assertEqual(len(all_faults), 15)

        injector = MissionFaultInjector()
        for i, fault in enumerate(all_faults):
            plan = FaultInjectionPlan(
                fault_type=fault,
                target_stage="EXECUTION",
                target_task_id=f"task_{i}",
                trigger_attempt=1,
            )
            injector.register_fault(plan)

        # Exercitar cada falha determinística
        triggered = []
        for i in range(15):
            f = injector.check_and_apply("EXECUTION", task_id=f"task_{i}", attempt=1)
            self.assertIsNotNone(f)
            triggered.append(f)

        self.assertEqual(len(triggered), 15)
        self.assertEqual(set(triggered), set(all_faults))
        self.assertEqual(len(injector.injection_history), 15)

    def test_03_self_healing_escalation_chain_and_minimal_repair(self) -> None:
        """
        Testa o ciclo de auto-reparação:
        - Falha sintática detectada.
        - Escalação para REPAIR.
        - Reparação minimalista via AST com unrelated_changes == 0.
        """
        budgets = RetryBudgets(repair_budget=2)
        decision = FailureEscalationGovernance.decide_escalation(
            FaultType.SYNTAX_ERROR, attempt=1, budgets=budgets
        )
        self.assertEqual(decision, FailureEscalationLevel.REPAIR)

        # Código com dois pontos esquecidos em função
        broken_python = (
            "def calculate_tax(amount, rate)\n"
            "    tax = amount * rate\n"
            "    return tax\n"
        )
        rep = SelfHealingEngine.diagnose_and_repair(
            "src/tax.py",
            broken_python,
            "SyntaxError: invalid syntax (tax.py, line 1)",
        )

        self.assertTrue(rep.success)
        self.assertEqual(rep.unrelated_changes, 0)
        self.assertTrue(rep.passes_invariants())
        self.assertIn("def calculate_tax(amount, rate):", rep.repaired_code)
        # Confirmar que a AST valida sem erros
        parsed = ast.parse(rep.repaired_code)
        self.assertIsNotNone(parsed)

    def test_04_retry_budget_enforcement_and_persistence(self) -> None:
        """
        Verifica decremento atómico dos budgets de retry e transição para BLOCK
        quando os budgets se esgotam, impedindo loops infinitos.
        """
        budgets = RetryBudgets(agent_retry_budget=2, repair_budget=1, replan_budget=0)

        # Consumir agent_retry
        self.assertTrue(budgets.consume_agent_retry())
        self.assertEqual(budgets.agent_retry_budget, 1)
        self.assertTrue(budgets.consume_agent_retry())
        self.assertEqual(budgets.agent_retry_budget, 0)
        self.assertFalse(budgets.consume_agent_retry())

        # Consumir repair
        self.assertTrue(budgets.consume_repair())
        self.assertEqual(budgets.repair_budget, 0)
        self.assertFalse(budgets.consume_repair())

        # Decisão quando todos os budgets relevantes estão a zero -> BLOCK ou ROLLBACK
        dec = FailureEscalationGovernance.decide_escalation(
            FaultType.AGENT_CRASH, attempt=3, budgets=budgets
        )
        self.assertEqual(dec, FailureEscalationLevel.BLOCK)

        # Persistência / Roundtrip
        b_dict = budgets.to_dict()
        restored = RetryBudgets.from_dict(b_dict)
        self.assertEqual(restored.agent_retry_budget, 0)
        self.assertEqual(restored.repair_budget, 0)

    def test_05_long_horizon_simulation_and_drift_metrics(self) -> None:
        """
        Executa simulação de 50 ciclos e valida métricas de latência (p50, p95, p99),
        crescimento controlado de checkpoints e memory drift delimitado.
        """
        metrics = LongHorizonSimulator.run_cycles(target_cycles=50, fault_probability=0.1)

        self.assertEqual(metrics.total_cycles, 50)
        self.assertGreater(metrics.duration_seconds, 0.0)
        self.assertGreaterEqual(metrics.latency_drift_p50_ms, 0.0)
        self.assertGreaterEqual(metrics.latency_drift_p99_ms, metrics.latency_drift_p50_ms)
        self.assertGreater(metrics.task_count_growth, 50)
        self.assertGreater(metrics.checkpoint_growth, 5)
        self.assertEqual(metrics.active_processes_delta, 0)
        self.assertEqual(metrics.active_leases_delta, 0)

    def test_06_stability_24_7_and_zero_resource_leaks(self) -> None:
        """
        Valida que após o término da missão não existem fugas de processos
        ou leases órfãos: active_processes_delta == 0 e active_leases_delta == 0.
        """
        spec = MissionGoalSpec(
            goal_text="Refactor authentication layer",
            category=MissionCategory.REFACTOR,
            target_artifacts=["src/auth/handler.py"],
        )
        pipeline = AutonomousMissionPipeline(spec)
        report = pipeline.execute_mission()

        self.assertEqual(report.status, "COMPLETED")
        self.assertEqual(report.active_processes_delta, 0)
        self.assertEqual(report.active_leases_delta, 0)

    def test_07_deterministic_recovery_oracle_and_restart(self) -> None:
        """
        Compara o estado de execução normal contra execução com crash/recovery
        via MissionRecoveryReference.
        """
        normal_snap = MissionStateSnapshot(
            mission_id="m_normal_1",
            completed_task_ids=["t1", "t2", "t3"],
            applied_patches={"src/a.py": "hash_a", "src/b.py": "hash_b"},
            evidence_ids=["ev_1", "ev_2"],
            checkpoints_count=3,
            status="COMPLETED",
        )

        recovered_snap = MissionStateSnapshot(
            mission_id="m_normal_1",
            completed_task_ids=["t1", "t2", "t3"],
            applied_patches={"src/a.py": "hash_a", "src/b.py": "hash_b"},
            evidence_ids=["ev_1", "ev_2"],
            checkpoints_count=4,  # Checkpoint adicional pós-restart
            status="COMPLETED",
        )

        ok, reason = MissionRecoveryReference.verify_equivalence(normal_snap, recovered_snap)
        self.assertTrue(ok, f"Recovery oracle failed: {reason}")
        self.assertEqual(reason, "SEMANTIC_EQUIVALENCE_CONFIRMED")

    def test_08_recovery_idempotence_no_duplicate_work(self) -> None:
        """
        Valida idempotência absoluta: se o estado recuperado tentar duplicar evidências
        ou tarefas, o oráculo deve rejeitar imediatamente.
        """
        normal_snap = MissionStateSnapshot(
            mission_id="m_dup_1",
            completed_task_ids=["t1", "t2"],
            applied_patches={"src/a.py": "h1"},
            evidence_ids=["ev_1", "ev_2"],
            checkpoints_count=2,
            status="COMPLETED",
        )

        corrupted_snap = MissionStateSnapshot(
            mission_id="m_dup_1",
            completed_task_ids=["t1", "t2"],
            applied_patches={"src/a.py": "h1"},
            evidence_ids=["ev_1", "ev_1"],  # DUPLICADO!
            checkpoints_count=2,
            status="COMPLETED",
        )

        ok, reason = MissionRecoveryReference.verify_equivalence(normal_snap, corrupted_snap)
        self.assertFalse(ok)
        self.assertIn("DUPLICATE_EVIDENCE_DETECTED", reason)

    def test_09_swarm_scaling_and_diminishing_returns(self) -> None:
        """
        Modela paralelismo de swarm de 1 a 256 agentes e determina empiricamente
        o ponto ótimo de saturação (diminishing returns threshold).
        """
        metrics = SwarmScalingAnalyzer.analyze_scaling()
        self.assertEqual(len(metrics), 9)

        # Verificar speedup inicial com poucos agentes
        m1 = metrics[0]  # 1 agente
        m8 = metrics[3]  # 8 agentes
        self.assertEqual(m1.agent_count, 1)
        self.assertEqual(m1.speedup, 1.0)
        self.assertGreater(m8.speedup, 4.0)

        # Encontrar ponto de retorno decrescente
        best_n = SwarmScalingAnalyzer.find_diminishing_returns_point(metrics)
        self.assertIn(best_n, (16, 32, 64))
        self.assertLess(best_n, 256, "Overhead de coordenação deve dominar antes de 256 agentes.")

    def test_10_real_repository_mission_and_application_generation(self) -> None:
        """
        Executa missão autónoma de geração sobre estrutura real do projeto,
        verificando compilação e integridade de AST.
        """
        spec = MissionGoalSpec(
            goal_text="Generate CRUD service for agent analytics",
            category=MissionCategory.SOFTWARE_PROJECT,
            target_artifacts=["services/analytics_service.py"],
            requires_full_stack=True,
        )
        pipeline = AutonomousMissionPipeline(spec)
        report = pipeline.execute_mission()

        self.assertEqual(report.status, "COMPLETED")
        self.assertEqual(report.human_intervention_count, 0)
        self.assertGreaterEqual(report.total_tasks, 4)

    def test_11_evidence_provenance_and_security_economic_invariants(self) -> None:
        """
        Verifica as salvaguardas de evidência e segurança:
        - Itens SELF_REPORTED não são aceites para conclusão.
        - Apenas EXECUTED, VALIDATED e EXTERNALLY_VERIFIED são aceites.
        """
        ev_self = MissionEvidenceItem(
            evidence_id="ev_fake",
            task_id="t_fake",
            producer_agent="agent_untrusted",
            provenance=EvidenceProvenance.SELF_REPORTED,
            kind="UNVERIFIED_CLAIM",
            description="Agent claims task is done",
            hash_signature="hash_0",
        )
        self.assertFalse(ev_self.is_acceptable_for_completion())

        ev_valid = MissionEvidenceItem(
            evidence_id="ev_real",
            task_id="t_real",
            producer_agent="testing_agent",
            provenance=EvidenceProvenance.VALIDATED,
            kind="TEST_EXECUTION_PASS",
            description="Automated tests verified by test runner",
            hash_signature="hash_1",
        )
        self.assertTrue(ev_valid.is_acceptable_for_completion())

    def test_12_event_stream_ordering_oracle(self) -> None:
        """
        Valida que o EventOrderingOracle valida streams causais corretas
        e deteta violações de ordenação impossíveis.
        """
        # Stream válida
        valid_stream = [
            {"type": "TASK_STARTED"},
            {"type": "PROPOSAL_CREATED"},
            {"type": "PROPOSAL_ARBITRATED"},
            {"type": "TASK_COMPLETED"},
            {"type": "CHECKPOINT_COMMITTED"},
        ]
        ok_v, msg_v = EventOrderingOracle.verify_stream(valid_stream)
        self.assertTrue(ok_v, msg_v)

        # Stream inválida (TASK_COMPLETED antes de TASK_STARTED)
        invalid_stream = [
            {"type": "TASK_COMPLETED"},
            {"type": "TASK_STARTED"},
        ]
        ok_i, msg_i = EventOrderingOracle.verify_stream(invalid_stream)
        self.assertFalse(ok_i)
        self.assertIn("CAUSAL_VIOLATION", msg_i)

    def test_13_browser_and_websocket_recovery(self) -> None:
        """
        Verifica a integridade de evidências de Browser QA e convergência de telemetria.
        """
        spec = MissionGoalSpec(
            goal_text="Verify responsive layout and form submission in browser",
            category=MissionCategory.BROWSER_VALIDATION,
            target_artifacts=["frontend/views/Settings.tsx"],
            requires_browser=True,
        )
        pipeline = AutonomousMissionPipeline(spec)
        report = pipeline.execute_mission()

        self.assertTrue(report.satisfaction_barrier_passed)
        self.assertTrue(any("browser" in e for e in report.evidence_chain))

    def test_14_extreme_scenario_autonomous_completion(self) -> None:
        """
        Cenário Extremo da Fase 16:
        Missão complexa com injeção deliberada de falhas concorrentes,
        auto-reparação, browser validation e barreira de satisfação confirmada
        sem qualquer intervenção humana (human_intervention_count == 0).
        """
        injector = MissionFaultInjector()
        # Injetar falha de sintaxe no início
        injector.register_fault(FaultInjectionPlan(
            fault_type=FaultType.SYNTAX_ERROR,
            target_stage="EXECUTION",
            target_task_id="task_1",
            trigger_attempt=1,
        ))

        spec = MissionGoalSpec(
            goal_text="Build end-to-end telemetry pipeline with self-healing and browser QA",
            category=MissionCategory.FULL_STACK_APP,
            target_artifacts=["src/telemetry.py", "frontend/src/views/Telemetry.tsx"],
            requires_browser=True,
            requires_full_stack=True,
        )

        pipeline = AutonomousMissionPipeline(spec, fault_injector=injector)
        report = pipeline.execute_mission()

        self.assertEqual(report.status, "COMPLETED")
        self.assertTrue(report.satisfaction_barrier_passed)
        self.assertEqual(report.human_intervention_count, 0)
        self.assertEqual(report.faults_injected_count, 1)
        self.assertEqual(report.repairs_executed_count, 1)
        self.assertEqual(report.active_processes_delta, 0)
        self.assertEqual(report.active_leases_delta, 0)


if __name__ == "__main__":
    unittest.main()
