import sys, os
sys.path.insert(0, os.path.abspath("."))

import unittest
from backend.tools.computer_use import ComputerUseEngine
from backend.security.permissions import PermissionPolicyManager, PermissionLevel


class TestComputerUse(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = ComputerUseEngine()

    async def test_take_screenshot_creates_sha256_artifact(self):
        result = self.engine.take_screenshot("http://localhost:8080", "test_shot.png")
        self.assertEqual(result["status"], "CAPTURED")
        self.assertTrue(os.path.exists(result["path"]))
        self.assertEqual(len(result["sha256"]), 64)

    async def test_run_command_sandboxed(self):
        result = self.engine.run_command("python -c \"print('HELLO_FROM_JARVIS')\"")
        self.assertEqual(result["status"], "COMPLETED")
        self.assertIn("HELLO_FROM_JARVIS", result["stdout"])

    async def test_permission_denial_blocks_unauthorized_command(self):
        # Policy with read-only permission (no CODE_EXECUTION)
        policy = PermissionPolicyManager(allowed_levels={PermissionLevel.READ_ONLY})
        restricted_engine = ComputerUseEngine(policy=policy)
        
        with self.assertRaises(PermissionError):
            restricted_engine.run_command("dir")


if __name__ == "__main__":
    unittest.main()
