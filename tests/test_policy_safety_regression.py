"""
JARVIS OS — Phase 41: Policy Safety & Economic Regression Tests
"""

import pytest
from agents.autonomous_loop.models import CausalExplanation, LoopDecisionType
from agents.autonomous_loop.policy import AutonomousDecisionPolicy, PolicyEvaluationContext, PolicyRuleDefinition
from agents.decision_calibration.sandbox import PolicySandbox


def test_safety_regression_suite_passes_baseline():
    report = PolicySandbox.run_safety_regression_suite(AutonomousDecisionPolicy.evaluate)
    assert report.verdict == "PASSED"
    assert report.security_regression_count == 0
    assert report.economic_regression_count == 0
    assert report.gate_bypass_count == 0
    assert report.passed_safety_checks == report.total_safety_checks


def test_safety_regression_suite_fails_on_weakened_security():
    # Flawed policy that ignores security violation and returns CONTINUE
    def flawed_eval(ctx: PolicyEvaluationContext):
        rule = PolicyRuleDefinition("R_BAD", 1, "bad", LoopDecisionType.CONTINUE, "bad", "bad")
        exp = CausalExplanation("bad", "bad", "CONTINUE", "bad")
        return LoopDecisionType.CONTINUE, exp, rule

    report = PolicySandbox.run_safety_regression_suite(flawed_eval)
    assert report.verdict == "REJECTED"
    assert report.security_regression_count > 0
