import sys, os, shutil
from pathlib import Path
sys.path.insert(0, os.path.abspath("."))

import unittest
from agents.mission_state import MissionStateStore
from agents.mission_recovery import MissionRecoveryWatchdog


class TestMissionRecovery(unittest.TestCase):
    def setUp(self):
        self.project_id = "test_recovery_proj"
        Path(f"workspace/projects/{self.project_id}").mkdir(parents=True, exist_ok=True)
        self.store = MissionStateStore()
        self.watchdog = MissionRecoveryWatchdog(self.store)
        
        # Create a clean mission with an IN_PROGRESS work package
        mission_data = self.store.create_mission(
            project_id=self.project_id,
            title="Missao de Teste Crash",
            objective="Testar recuperacao apos falha",
        )
        self.mission_id = mission_data["mission"]["mission_id"]
        
        # Add a work package and set to IN_PROGRESS
        wp_data = self.store.create_work_package(
            project_id=self.project_id,
            mission_id=self.mission_id,
            title="Pacote Interrompido",
            type="CODING",
        )
        self.wp_id = wp_data["work_packages"][0]["work_package_id"]
        
        # Transition to IN_PROGRESS
        self.store.set_work_package_status(
            self.project_id, self.mission_id, self.wp_id, "IN_PROGRESS", 1
        )

    def test_watchdog_recovers_in_progress_work_package(self):
        """Proves that watchdog detects orphan IN_PROGRESS and reverts it cleanly to READY."""
        actions = self.watchdog.scan_and_recover_project(self.project_id)
        self.assertGreaterEqual(len(actions), 1)
        
        # Check that the created package is now READY
        data = self.store.load_mission(self.project_id, self.mission_id)
        reverted_wp = [p for p in data["work_packages"] if p["work_package_id"] == self.wp_id][0]
        self.assertEqual(reverted_wp["status"], "READY")

    def test_watchdog_idempotency(self):
        """Proves that running the watchdog 5 times in a row produces no spurious updates."""
        # First run recovers all orphan packages
        actions_first = self.watchdog.scan_and_recover_project(self.project_id)
        self.assertGreaterEqual(len(actions_first), 1)
        
        # Second to fifth runs should find 0 IN_PROGRESS packages
        for _ in range(4):
            actions = self.watchdog.scan_and_recover_project(self.project_id)
            self.assertEqual(len(actions), 0)


if __name__ == "__main__":
    unittest.main()
