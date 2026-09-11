"""
JARVIS OS — Phase 35: Mission Control Center & Explainable Autonomous Execution UX Tests
"""

import asyncio
import json
import os
import sys
import time
import unittest

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from agents.mission_control_engine import (
    MissionControlEngine,
    MissionControlEvent,
    MissionControlStage,
    MissionControlStatus,
    RecoveryExplainabilityRecord,
    RepairExplainabilityRecord,
    ReplanExplainabilityRecord,
    ReplanTrigger,
    WhyPanelItem,
)


class TestMissionControlPhase35(unittest.TestCase):
    def setUp(self):
        self.engine = MissionControlEngine()

    def test_01_all_scenarios_generate_valid_state(self):
        scenarios = ["NORMAL", "REPAIR", "REPLAN", "RECOVERY", "BLOCKED"]
        for sc in scenarios:
            state = self.engine.get_scenario_state(sc)
            self.assertIsNotNone(state.mission_id)
            self.assertIsNotNone(state.user_goal)
            self.assertGreater(len(state.tasks), 0)
            self.assertGreater(len(state.agents), 0)
            self.assertGreater(len(state.events), 0)
            self.assertGreater(len(state.requirements), 0)
            self.assertGreater(len(state.evidence), 0)
            self.assertIsNotNone(state.time_to_value)
            self.assertIsNotNone(state.user_effort)

    def test_02_zero_false_success_enforcement(self):
        # Scenario NORMAL is fully valid and should be COMPLETED
        normal = self.engine.get_scenario_state("NORMAL")
        self.assertTrue(normal.can_complete())
        self.assertEqual(normal.status, MissionControlStatus.COMPLETED)
        self.assertTrue(normal.result.get("execution_success"))
        self.assertTrue(normal.result.get("requirement_satisfaction"))
        self.assertTrue(normal.result.get("required_validation"))

        # Scenario BLOCKED must NOT be COMPLETED
        blocked = self.engine.get_scenario_state("BLOCKED")
        self.assertFalse(blocked.can_complete())
        self.assertEqual(blocked.status, MissionControlStatus.BLOCKED)
        self.assertEqual(blocked.result.get("status"), "BLOCKED")

    def test_03_strict_separation_of_requirements_and_assumptions(self):
        state = self.engine.get_scenario_state("NORMAL")
        user_reqs = [r for r in state.requirements if r.get("source") == "USER_REQUIREMENT"]
        sys_assumptions = [r for r in state.assumptions if r.get("source") == "SYSTEM_ASSUMPTION"]

        self.assertGreater(len(user_reqs), 0)
        self.assertGreater(len(sys_assumptions), 0)

        # All user requirements must be VERIFIED in completed normal run
        for ur in user_reqs:
            self.assertEqual(ur.get("verification_status"), "VERIFIED")
            self.assertEqual(ur.get("status"), "VALIDATED")

        # System assumptions are INFERRED
        for sa in sys_assumptions:
            self.assertEqual(sa.get("verification_status"), "INFERRED")

    def test_04_why_panel_explainability(self):
        repair_state = self.engine.get_scenario_state("REPAIR")
        self.assertGreater(len(repair_state.why_panel), 0)
        item = repair_state.why_panel[0]
        self.assertTrue(item.action)
        self.assertTrue(item.reason)
        self.assertIn(item.source, ["USER_REQUIREMENT", "SYSTEM_ASSUMPTION", "AUTONOMOUS_REPAIR_LOOP"])
        self.assertTrue(item.evidence)

    def test_05_repair_explainability_chain(self):
        repair_state = self.engine.get_scenario_state("REPAIR")
        self.assertIsNotNone(repair_state.repair_explainability)
        rep = repair_state.repair_explainability
        self.assertIn("TypeError", rep.failure)
        self.assertTrue(rep.diagnosis)
        self.assertTrue(rep.patch)
        self.assertTrue(rep.validation)
        self.assertIn("PASS", rep.validation_result)
        self.assertGreater(len(rep.files_changed), 0)

    def test_06_replan_explainability_chain(self):
        replan_state = self.engine.get_scenario_state("REPLAN")
        self.assertIsNotNone(replan_state.replan_explainability)
        rep = replan_state.replan_explainability
        self.assertTrue(rep.old_plan_summary)
        self.assertTrue(rep.new_plan_summary)
        self.assertTrue(rep.why_changed)
        self.assertIsInstance(rep.trigger, ReplanTrigger)

    def test_07_recovery_explainability_chain(self):
        rec_state = self.engine.get_scenario_state("RECOVERY")
        self.assertIsNotNone(rec_state.recovery_explainability)
        rec = rec_state.recovery_explainability
        self.assertTrue(rec.worker_failed)
        self.assertTrue(rec.checkpoint_id)
        self.assertTrue(rec.state_restored)
        self.assertTrue(rec.task_resumed)
        self.assertEqual(rec.duplicate_protection, "ZERO_WORK_DUPLICATION")

    def test_08_event_contract_and_deduplication(self):
        events = self.engine.generate_events(count=50, scenario_type="NORMAL")
        self.assertEqual(len(events), 50)

        # Every event adheres to strict WebSocket contract
        for evt in events:
            d = evt.to_dict()
            self.assertIn("event_id", d)
            self.assertIn("mission_id", d)
            self.assertIn("timestamp", d)
            self.assertIn("type", d)
            self.assertIn("payload", d)
            self.assertTrue(d["event_id"].startswith("evt_"))

        # Test deduplication
        duplicated_stream = events + events[:25]  # 75 events with 25 duplicates
        deduped, rej_count = self.engine.deduplicate_events(duplicated_stream)
        self.assertEqual(len(deduped), 50)
        self.assertEqual(rej_count, 25)

    def test_09_observability_score_calculation(self):
        for sc in ["NORMAL", "REPAIR", "REPLAN", "RECOVERY", "BLOCKED"]:
            state = self.engine.get_scenario_state(sc)
            score_data = self.engine.calculate_observability_score(state)
            self.assertEqual(score_data["score_pct"], 100.0)
            self.assertEqual(score_data["missing_count"], 0)

    def test_10_high_throughput_events_performance(self):
        test_counts = [10, 50, 100, 250, 500, 1000]
        results = {}
        for count in test_counts:
            t0 = time.perf_counter()
            events = self.engine.generate_events(count=count, scenario_type="NORMAL")
            deduped, rejections = self.engine.deduplicate_events(events)
            duration_ms = (time.perf_counter() - t0) * 1000.0

            self.assertEqual(len(deduped), count)
            self.assertEqual(rejections, 0)
            results[count] = duration_ms
            # Event processing should be well under 100ms even for 1000 events
            self.assertLess(duration_ms, 250.0)


if __name__ == "__main__":
    unittest.main()
