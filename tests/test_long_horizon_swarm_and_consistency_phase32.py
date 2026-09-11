"""
JARVIS OS — Phase 32: Swarm Coordination, High-Horizon Transitions, & Consistency Tests
Verifies multi-level progressive scaling, cycle prevention, transport fallback, and swarm health.
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


class TestLongHorizonSwarmAndConsistencyPhase32(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="jarvis_p32_swarm_")
        self.engine = LongHorizonMissionEngine(base_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    async def test_01_level_3_scaling_and_subdag_expansion(self):
        corpus = build_phase32_mission_corpus()
        spec = [m for m in corpus if m.target_complexity_level == LongHorizonComplexityLevel.LEVEL_3][0]
        res = await self.engine.execute_long_horizon_mission(
            spec=spec,
            session_id=1,
            target_transitions=65,
            inject_sequential_faults=True,
            simulate_interruptions=True,
        )
        self.assertGreaterEqual(res.total_task_transitions, 60)
        self.assertTrue(res.eventual_success)
        self.assertTrue(res.state_consistency.is_consistent)
        self.assertEqual(res.state_consistency.lost_tasks, [])
        self.assertEqual(res.state_consistency.duplicate_tasks, [])
        self.assertFalse(res.state_consistency.corrupted_graph)
        self.assertEqual(res.requirement_retention_rate, 1.0)
        self.assertEqual(res.mission_drift_score, 0.0)

    async def test_02_level_4_scaling_with_transport_fallback(self):
        corpus = build_phase32_mission_corpus()
        spec = [m for m in corpus if m.target_complexity_level == LongHorizonComplexityLevel.LEVEL_4 and m.has_transport_fallback_test][0]
        res = await self.engine.execute_long_horizon_mission(
            spec=spec,
            session_id=1,
            target_transitions=130,
            inject_sequential_faults=True,
            simulate_interruptions=True,
            simulate_transport_fallback=True,
        )
        self.assertGreaterEqual(res.total_task_transitions, 120)
        self.assertTrue(res.eventual_success)
        self.assertGreaterEqual(res.repair_count, 3)
        self.assertEqual(res.repair_count, res.repair_success_count)
        self.assertGreaterEqual(res.recovery_count, 2)
        self.assertEqual(res.recovery_count, res.recovery_success_count)
        # Check that transport reassignment transition was recorded
        reassignments = res.transitions_by_type.get(TaskTransitionType.TASK_REASSIGNMENT.value, 0)
        self.assertGreaterEqual(reassignments, 1)

    async def test_03_level_5_high_horizon_stress(self):
        corpus = build_phase32_mission_corpus()
        spec = [m for m in corpus if m.target_complexity_level == LongHorizonComplexityLevel.LEVEL_5][0]
        res = await self.engine.execute_long_horizon_mission(
            spec=spec,
            session_id=1,
            target_transitions=220,
            inject_sequential_faults=True,
            simulate_interruptions=True,
            simulate_transport_fallback=True,
        )
        self.assertGreaterEqual(res.total_task_transitions, 200)
        self.assertTrue(res.eventual_success)
        self.assertEqual(res.human_intervention_count, 0)
        self.assertFalse(res.false_success)
        self.assertTrue(res.state_consistency.is_consistent)
        # Verify first real limit observed at >= 200 transitions
        self.assertEqual(res.first_real_limit_observed, "STATE_SERIALIZATION_LATENCY_GROWTH")
        self.assertEqual(res.first_real_failure_observed, "NONE")

    def test_04_state_consistency_cycle_detection(self):
        graph = TaskGraph()
        n1 = TaskNode(task_id="t1", title="Task 1", dependencies=["t2"], status=TaskStatus.COMPLETED)
        n2 = TaskNode(task_id="t2", title="Task 2", dependencies=["t1"], status=TaskStatus.COMPLETED)
        graph.add_node(n1)
        graph.add_node(n2)

        report = StateConsistencyMonitor.inspect(
            graph=graph,
            executed_task_ids=["t1", "t2"],
            checkpoints=[],
        )
        self.assertFalse(report.is_consistent)
        self.assertTrue(report.corrupted_graph)

    def test_05_state_consistency_checkpoint_sequence_validation(self):
        graph = TaskGraph()
        n1 = TaskNode(task_id="t1", title="Task 1", status=TaskStatus.COMPLETED)
        graph.add_node(n1)

        # Non-monotonic checkpoint sequence (e.g. 1 then 1)
        cp1 = Checkpoint(checkpoint_id="c1", sequence=1, mission_id="m1", project_id="p1", mission_status="A",
                         task_graph_data={}, completed_task_ids=[], pending_task_ids=[], running_task_ids=[],
                         failed_task_ids=[], blocked_task_ids=[], evidence_refs=[], outputs={}, created_at="",
                         description="", graph_version=1)
        cp2 = Checkpoint(checkpoint_id="c2", sequence=1, mission_id="m1", project_id="p1", mission_status="A",
                         task_graph_data={}, completed_task_ids=[], pending_task_ids=[], running_task_ids=[],
                         failed_task_ids=[], blocked_task_ids=[], evidence_refs=[], outputs={}, created_at="",
                         description="", graph_version=1)

        report = StateConsistencyMonitor.inspect(
            graph=graph,
            executed_task_ids=["t1"],
            checkpoints=[cp1, cp2],
        )
        self.assertFalse(report.is_consistent)
        self.assertTrue(any("c2" in ic for ic in report.invalid_checkpoints))


if __name__ == "__main__":
    unittest.main()
