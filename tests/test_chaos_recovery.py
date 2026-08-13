import sys, os, shutil
from pathlib import Path
sys.path.insert(0, os.path.abspath("."))

import unittest
from agents.mission_state import MissionStateStore, StaleVersionError
from agents.mission_recovery import MissionRecoveryWatchdog


class TestChaosRecovery(unittest.TestCase):
    def setUp(self):
        self.project_id = "chaos_test_proj"
        Path(f"workspace/projects/{self.project_id}").mkdir(parents=True, exist_ok=True)
        self.store = MissionStateStore()
        self.watchdog = MissionRecoveryWatchdog(self.store)

    def test_chaos_kill_during_execution_and_resumption(self):
        """Simulates hard kill during work package execution and tests watchdog resumption."""
        m_data = self.store.create_mission(self.project_id, "Chaos Mission", "Survive hard kills")
        m_id = m_data["mission"]["mission_id"]

        # Add 3 work packages
        wp1 = self.store.create_work_package(self.project_id, m_id, title="WP1", type="RESEARCH")
        wp1_id = wp1["work_packages"][0]["work_package_id"]

        # Set WP1 to IN_PROGRESS (simulating active execution)
        self.store.set_work_package_status(self.project_id, m_id, wp1_id, "IN_PROGRESS", 1)

        # SIMULATE HARD PROCESS KILL: Re-instantiate a fresh MissionStateStore
        fresh_store = MissionStateStore()
        fresh_watchdog = MissionRecoveryWatchdog(fresh_store)

        # Watchdog scans and heals the crashed state
        recovered = fresh_watchdog.scan_and_recover_project(self.project_id)
        self.assertGreaterEqual(len(recovered), 1)
        self.assertEqual(recovered[0]["action"], "REVERTED_TO_READY")

        # Verify WP1 is now READY to resume safely
        loaded = fresh_store.load_mission(self.project_id, m_id)
        recovered_wp = [p for p in loaded["work_packages"] if p["work_package_id"] == wp1_id][0]
        self.assertEqual(recovered_wp["status"], "READY")

    def test_chaos_kill_during_state_transition_locks(self):
        """Simulates stale version write attempts after crash."""
        m_data = self.store.create_mission(self.project_id, "Lock Chaos", "Validate lock integrity")
        m_id = m_data["mission"]["mission_id"]

        # Valid update increments version 1 -> 2
        self.store.update_mission(self.project_id, m_id, 1, {"title": "Updated V2"})

        # Stale update with version 1 is blocked
        with self.assertRaises(StaleVersionError):
            self.store.update_mission(self.project_id, m_id, 1, {"title": "Stale Write"})


if __name__ == "__main__":
    unittest.main()
