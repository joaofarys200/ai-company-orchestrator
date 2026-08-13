import sys, os
sys.path.insert(0, os.path.abspath("."))

import unittest
from backend.security.permissions import PermissionLevel, PermissionPolicyManager, TOOL_PERMISSIONS


class TestPermissionSystem(unittest.TestCase):
    def test_permission_policy_manager_default_levels(self):
        policy = PermissionPolicyManager()
        
        # Read file should be allowed with no approval
        allowed, approval, reason = policy.can_execute_tool("read_file")
        self.assertTrue(allowed)
        self.assertFalse(approval)

        # Write file should be allowed with no approval
        allowed, approval, reason = policy.can_execute_tool("write_file")
        self.assertTrue(allowed)
        self.assertFalse(approval)

        # Shell command execution should be allowed with no approval in default dev levels
        allowed, approval, reason = policy.can_execute_tool("execute_command")
        self.assertTrue(allowed)
        self.assertFalse(approval)

    def test_high_risk_financial_action_requires_human_approval(self):
        policy = PermissionPolicyManager()

        # Financial transaction MUST require human approval
        allowed, approval, reason = policy.can_execute_tool("financial_transaction")
        self.assertTrue(allowed)
        self.assertTrue(approval)
        self.assertIn("requer aprovação humana", reason)

        # External account creation MUST require human approval
        allowed, approval, reason = policy.can_execute_tool("external_account_create")
        self.assertTrue(allowed)
        self.assertTrue(approval)
        self.assertIn("requer aprovação humana", reason)

    def test_restricted_permission_levels(self):
        # Strict read-only policy
        read_only_policy = PermissionPolicyManager(allowed_levels={PermissionLevel.READ_ONLY})

        allowed, approval, reason = read_only_policy.can_execute_tool("read_file")
        self.assertTrue(allowed)

        allowed, approval, reason = read_only_policy.can_execute_tool("write_file")
        self.assertFalse(allowed)


if __name__ == "__main__":
    unittest.main()
