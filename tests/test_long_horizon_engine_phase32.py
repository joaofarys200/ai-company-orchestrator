"""
JARVIS OS — Phase 32: Unit & Integration Test Suite
Tests Long-Horizon Autonomous Engine, Task Transitions, State Consistency, and Recovery
"""

import asyncio
import os
import shutil
import tempfile
import unittest

from agents.long_horizon_mission_engine import (
    ContextDriftEvaluator,
    LongHorizonComplexityLevel,
    LongHorizonExecutionResult,
    LongHorizonMissionEngine,
    LongHorizonMissionSpec,
    StateConsistencyMonitor,
    TaskTransitionRecord,
    TaskTransitionType,
    build_phase32_mission_corpus,
)
from agents.mission_orchestrator import Checkpoint
from agents.task_graph import TaskGraph, TaskNode, TaskStatus


class TestLongHorizonEnginePhase32(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="jarvis_p32_test_")
        self.engine = LongHorizonMissionEngine(base_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_corpus_specification_integrity(self):
        corpus = build_phase32_mission_corpus()
        self.assertEqual(len(corpus), 10)

        categories = [m.category for m in corpus]
        self.assertEqual(categories.count("SOFTWARE_PROJECT"), 3)
        self.assertEqual(categories.count("FULL_STACK_APPLICATION"), 2)
        self.assertEqual(categories.count("LARGE_FEATURE_SET"), 2)
        self.assertEqual(categories.count("REFACTOR_MIGRATION"), 2)
        self.assertEqual(categories.count("COMPLEX_BUG_FEATURE_TEST"), 1)

        # All 5 complexity levels must be present
        levels = {m.target_complexity_level for m in corpus}
        self.assertIn(LongHorizonComplexityLevel.LEVEL_1, levels)
        self.assertIn(LongHorizonComplexityLevel.LEVEL_2, levels)
        self.assertIn(LongHorizonComplexityLevel.LEVEL_3, levels)
        self.assertIn(LongHorizonComplexityLevel.LEVEL_4, levels)
        self.assertIn(LongHorizonComplexityLevel.LEVEL_5, levels)

    def test_02_task_transition_formal_types(self):
        all_types = list(TaskTransitionType)
        self.assertEqual(len(all_types), 9)
        expected = {
            "TASK_CREATION",
            "TASK_START",
            "TASK_COMPLETION",
            "TASK_RETRY",
            "TASK_REPAIR",
            "TASK_REPLAN",
            "TASK_REASSIGNMENT",
            "TASK_ROLLBACK",
            "TASK_RECOVERY",
        }
        self.assertEqual({t.value for t in all_types}, expected)

    def test_03_state_consistency_monitor_acyclic_and_clean(self):
        graph = TaskGraph()
        n1 = TaskNode(task_id="t1", title="Task 1", status=TaskStatus.COMPLETED)
        n2 = TaskNode(task_id="t2", title="Task 2", dependencies=["t1"], status=TaskStatus.COMPLETED)
        graph.add_node(n1)
        graph.add_node(n2)

        report = StateConsistencyMonitor.inspect(
            graph=graph,
            executed_task_ids=["t1", "t2"],
            checkpoints=[],
        )
        self.assertTrue(report.is_consistent)
        self.assertEqual(len(report.lost_tasks), 0)
        self.assertEqual(len(report.duplicate_tasks), 0)
        self.assertFalse(report.corrupted_graph)

    def test_04_state_consistency_monitor_detects_duplicate_and_lost(self):
        graph = TaskGraph()
        n1 = TaskNode(task_id="t1", title="Task 1", status=TaskStatus.COMPLETED)
        n2 = TaskNode(task_id="t2", title="Task 2", status=TaskStatus.COMPLETED)
        graph.add_node(n1)
        graph.add_node(n2)

        # t1 executed twice, t2 never recorded as executed
        report = StateConsistencyMonitor.inspect(
            graph=graph,
            executed_task_ids=["t1", "t1"],
            checkpoints=[],
        )
        self.assertFalse(report.is_consistent)
        self.assertIn("t1", report.duplicate_tasks)
        self.assertIn("t2", report.lost_tasks)

    def test_05_context_drift_evaluator(self):
        initial_reqs = ["Req A", "Req B", "Req C"]
        final_reqs = ["Req A", "Req B", "Req C"]
        drift_report = ContextDriftEvaluator.evaluate(
            initial_goal="Build app",
            initial_requirements=initial_reqs,
            final_requirements=final_reqs,
            current_plan_titles=["Task 1", "Task 2"],
            final_state="COMPLETED",
            unrelated_changes=0,
        )
        self.assertEqual(drift_report.requirements_retention_rate, 1.0)
        self.assertEqual(drift_report.mission_drift_score, 0.0)
        self.assertEqual(drift_report.unrelated_changes_count, 0)

    async def test_06_long_horizon_execution_level_1(self):
        corpus = build_phase32_mission_corpus()
        spec = corpus[0]  # MISSION_LH_01 (LEVEL_1)
        res = await self.engine.execute_long_horizon_mission(
            spec=spec,
            session_id=1,
            target_transitions=16,
            inject_sequential_faults=True,
            simulate_interruptions=True,
        )
        self.assertIsInstance(res, LongHorizonExecutionResult)
        self.assertGreaterEqual(res.total_task_transitions, 16)
        self.assertTrue(res.eventual_success)
        self.assertTrue(res.requirement_satisfaction)
        self.assertEqual(res.human_intervention_count, 0)
        self.assertFalse(res.false_success)
        self.assertGreaterEqual(res.repair_count, 1)
        self.assertGreaterEqual(res.recovery_count, 1)
        self.assertTrue(res.state_consistency.is_consistent)
        self.assertEqual(res.mission_drift_score, 0.0)

    async def test_07_multiple_sequential_repairs_and_recovery(self):
        corpus = build_phase32_mission_corpus()
        spec = corpus[1]  # MISSION_LH_02 (2 faults, 2 recoveries)
        res = await self.engine.execute_long_horizon_mission(
            spec=spec,
            session_id=1,
            target_transitions=32,
            inject_sequential_faults=True,
            simulate_interruptions=True,
        )
        self.assertGreaterEqual(res.total_task_transitions, 30)
        self.assertEqual(res.repair_count, res.repair_success_count)
        self.assertEqual(res.recovery_count, res.recovery_success_count)
        self.assertTrue(res.eventual_success)
        self.assertEqual(res.human_intervention_count, 0)


if __name__ == "__main__":
    unittest.main()
