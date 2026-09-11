"""
JARVIS OS — Phase 34: Unit & Contract Tests for Real User Mission Engine
"""

import asyncio
import os
import shutil
import unittest

from agents.autonomous_mission_engine import FaultType
from agents.real_user_mission_engine import (
    FailureTaxonomy,
    OutputQualityScore,
    RealUserCategory,
    RealUserMissionEngine,
    TimeToValueMetrics,
    UserAcceptanceDecision,
    UserAcceptanceGate,
    UserEffortMetrics,
    ValueLevel,
)


class TestPhase34RealUserMissions(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_dir = os.path.abspath("scratch/test_phase34_engine")
        shutil.rmtree(self.test_dir, ignore_errors=True)
        os.makedirs(self.test_dir, exist_ok=True)
        self.engine = RealUserMissionEngine(base_dir=self.test_dir)

    async def asyncTearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_user_acceptance_gate_logic(self):
        # Must pass all three criteria
        useful, label = UserAcceptanceGate.evaluate(True, True, True)
        self.assertTrue(useful)
        self.assertEqual(label, "USER_USEFUL")

        # Any failure results in NOT_USER_USEFUL
        useful, label = UserAcceptanceGate.evaluate(False, True, True)
        self.assertFalse(useful)
        self.assertEqual(label, "NOT_USER_USEFUL")

        useful, label = UserAcceptanceGate.evaluate(True, False, True)
        self.assertFalse(useful)
        self.assertEqual(label, "NOT_USER_USEFUL")

        useful, label = UserAcceptanceGate.evaluate(True, True, False)
        self.assertFalse(useful)
        self.assertEqual(label, "NOT_USER_USEFUL")

    def test_02_time_to_value_metrics(self):
        m = TimeToValueMetrics(
            t_start=100.0,
            t_first_output=101.5,
            t_first_validated_artifact=102.8,
            t_useful_result=103.2,
            t_end=103.5,
        )
        self.assertEqual(m.time_to_first_output_seconds, 1.5)
        self.assertEqual(m.time_to_first_validated_artifact_seconds, 2.8)
        self.assertEqual(m.time_to_useful_result_seconds, 3.2)
        self.assertEqual(m.total_mission_duration_seconds, 3.5)

    def test_03_user_effort_score(self):
        # Autonomous run (1 prompt, 0 manual interventions)
        effort = UserEffortMetrics(prompts_required=1)
        self.assertEqual(effort.effort_score, 0.0)

        # Run with 1 manual retry and 1 manual edit
        effort_manual = UserEffortMetrics(
            prompts_required=2,
            manual_approvals=1,
            manual_file_edits=1,
            manual_retries=1,
            manual_debugging_steps=0,
        )
        self.assertGreater(effort_manual.effort_score, 0.0)

    async def test_04_execution_new_small_application(self):
        res = await self.engine.execute_real_user_mission(
            mission_id="m_test_app",
            category=RealUserCategory.NEW_SMALL_APPLICATION,
            prompt="Cria uma pequena aplicação para organizar despesas pessoais.",
            run_index=1,
        )
        self.assertTrue(res.execution_success)
        self.assertTrue(res.requirement_satisfaction)
        self.assertTrue(res.validation_evidence)
        self.assertTrue(res.user_useful)
        self.assertEqual(res.user_useful_label, "USER_USEFUL")
        self.assertEqual(res.value_level, ValueLevel.A_IMMEDIATELY_USEFUL)
        self.assertTrue(res.browser_validated)
        self.assertGreater(len(res.artifacts_created), 2)
        self.assertGreater(res.time_to_value.time_to_useful_result_seconds, 0.0)

    async def test_05_autonomous_repair_on_bug(self):
        res = await self.engine.execute_real_user_mission(
            mission_id="m_test_repair",
            category=RealUserCategory.BUG_FIX,
            prompt="Encontra e corrige o problema na ordenação.",
            run_index=1,
            inject_fault=FaultType.SYNTAX_ERROR,
        )
        # Should detect fault, repair it, revalidate, and succeed
        self.assertFalse(res.first_pass_success)
        self.assertTrue(res.eventual_success)
        self.assertEqual(res.repair_count, 1)
        self.assertTrue(res.user_useful)

    async def test_06_crash_recovery(self):
        res = await self.engine.execute_real_user_mission(
            mission_id="m_test_recovery",
            category=RealUserCategory.TESTING_QUALITY,
            prompt="Melhora a cobertura de testes deste componente.",
            run_index=1,
            test_recovery=True,
        )
        self.assertTrue(res.recovery_tested)
        self.assertTrue(res.recovery_success)
        self.assertTrue(res.execution_success)


if __name__ == "__main__":
    unittest.main()
