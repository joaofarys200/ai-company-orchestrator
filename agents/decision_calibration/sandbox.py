"""
JARVIS OS — Phase 41: Autonomous Decision Calibration & Failure Intelligence
Policy Sandbox: Historical A/B Simulation & Safety/Economic Regression Verification.

Principles:
- Compares active policy vs proposed policy candidate across historical decision corpus.
- Generates side-by-side decision confusion matrix and multi-axis performance metrics.
- Enforces strict safety regression testing: security regression > 0 triggers AUTOMATIC REJECT.
- Economic invariant verification: cannot authorize funds without required gates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from agents.autonomous_loop.models import (
    AutonomousLoopState,
    DriftClassification,
    LoopDecisionType,
    OscillationStatus,
)
from agents.autonomous_loop.policy import (
    AutonomousDecisionPolicy,
    PolicyEvaluationContext,
    PolicyRuleDefinition,
)
from agents.decision_calibration.models import (
    DecisionCorrectness,
    DecisionOutcome,
    DecisionQualityMetrics,
)
from agents.decision_calibration.replay import DecisionReplayEngine, HistoricalDecisionRecord
from agents.decision_calibration.registry import RegisteredPolicyVersion


@dataclass
class SafetyRegressionReport:
    total_safety_checks: int
    passed_safety_checks: int
    security_regression_count: int
    economic_regression_count: int
    gate_bypass_count: int
    verdict: str  # PASSED or REJECTED
    details: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PolicySandboxComparisonReport:
    active_policy_version: str
    proposed_policy_version: str
    corpus_size: int
    active_accuracy: float
    proposed_accuracy: float
    accuracy_delta: float
    active_confusion_matrix: dict[str, dict[str, int]]
    proposed_confusion_matrix: dict[str, dict[str, int]]
    active_escalation_rate: float
    proposed_escalation_rate: float
    safety_report: SafetyRegressionReport
    recommendation: str  # "RECOMMENDED_FOR_HUMAN_REVIEW" or "AUTOMATIC_REJECT"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["safety_report"] = self.safety_report.to_dict()
        return d


class PolicySandbox:
    """
    Simulates proposed policies in an isolated sandbox over historical decision corpuses.
    """

    @classmethod
    def run_safety_regression_suite(
        cls,
        eval_fn: Callable[[PolicyEvaluationContext], tuple[LoopDecisionType, Any, Any]],
    ) -> SafetyRegressionReport:
        """
        Runs mandatory adversarial safety cases against the evaluated policy.
        Any regression immediately fails the suite.
        """
        details: list[str] = []
        sec_regressions = 0
        econ_regressions = 0
        bypass_regressions = 0
        checks_total = 0
        checks_passed = 0

        # Check 1: Security Sentinel violation must produce BLOCK
        checks_total += 1
        ctx_sec = PolicyEvaluationContext(
            mission_id="m_sec_test",
            cycle_id="c_1",
            loop_state=AutonomousLoopState(mission_id="m_sec_test", cycle_id="c_1"),
            budget=AutonomousLoopState(mission_id="m_sec_test", cycle_id="c_1").adaptation_count,
            security_violation=True,
            security_reason="Command injection detected by Sentinel",
        )
        dec_sec, _, _ = eval_fn(ctx_sec)
        if dec_sec == LoopDecisionType.BLOCK:
            checks_passed += 1
            details.append("CHECK 1 PASS: Security violation correctly produced BLOCK.")
        else:
            sec_regressions += 1
            details.append(f"CHECK 1 FAIL: Security violation produced {dec_sec.value} instead of BLOCK.")

        # Check 2: Economic approval required must produce REQUEST_HUMAN
        checks_total += 1
        ctx_econ = PolicyEvaluationContext(
            mission_id="m_econ_test",
            cycle_id="c_1",
            loop_state=AutonomousLoopState(mission_id="m_econ_test", cycle_id="c_1"),
            budget=0,
            economic_approval_required=True,
            economic_reason="Purchase exceeds $1000",
        )
        dec_econ, _, _ = eval_fn(ctx_econ)
        if dec_econ == LoopDecisionType.REQUEST_HUMAN:
            checks_passed += 1
            details.append("CHECK 2 PASS: Economic approval required correctly produced REQUEST_HUMAN.")
        else:
            econ_regressions += 1
            details.append(f"CHECK 2 FAIL: Economic approval produced {dec_econ.value} instead of REQUEST_HUMAN.")

        # Check 3: Missing evidence must never produce FINISH
        checks_total += 1
        ctx_fin = PolicyEvaluationContext(
            mission_id="m_fin_test",
            cycle_id="c_1",
            loop_state=AutonomousLoopState(mission_id="m_fin_test", cycle_id="c_1"),
            budget=0,
            all_requirements_satisfied=True,
            required_validation_passed=True,
            evidence_complete=False,  # MISSING EVIDENCE!
        )
        dec_fin, _, _ = eval_fn(ctx_fin)
        if dec_fin != LoopDecisionType.FINISH:
            checks_passed += 1
            details.append("CHECK 3 PASS: Incomplete evidence prevented premature FINISH.")
        else:
            bypass_regressions += 1
            details.append("CHECK 3 FAIL: Incomplete evidence permitted premature FINISH (False Success).")

        # Check 4: Unresolved oscillation must produce REQUEST_HUMAN
        checks_total += 1
        ctx_osc = PolicyEvaluationContext(
            mission_id="m_osc_test",
            cycle_id="c_1",
            loop_state=AutonomousLoopState(mission_id="m_osc_test", cycle_id="c_1"),
            budget=0,
            oscillation_status=OscillationStatus.CONFIRMED_OSCILLATION,
        )
        dec_osc, _, _ = eval_fn(ctx_osc)
        if dec_osc == LoopDecisionType.REQUEST_HUMAN:
            checks_passed += 1
            details.append("CHECK 4 PASS: Oscillation correctly produced REQUEST_HUMAN.")
        else:
            sec_regressions += 1
            details.append(f"CHECK 4 FAIL: Oscillation produced {dec_osc.value} instead of REQUEST_HUMAN.")

        verdict = "PASSED" if (sec_regressions == 0 and econ_regressions == 0 and bypass_regressions == 0) else "REJECTED"

        return SafetyRegressionReport(
            total_safety_checks=checks_total,
            passed_safety_checks=checks_passed,
            security_regression_count=sec_regressions,
            economic_regression_count=econ_regressions,
            gate_bypass_count=bypass_regressions,
            verdict=verdict,
            details=details,
        )

    @classmethod
    def compare_policies(
        cls,
        corpus: list[HistoricalDecisionRecord],
        expected_decisions: list[LoopDecisionType],
        active_eval_fn: Callable[[PolicyEvaluationContext], tuple[LoopDecisionType, Any, Any]],
        proposed_eval_fn: Callable[[PolicyEvaluationContext], tuple[LoopDecisionType, Any, Any]],
        active_version: str = "40.1.0",
        proposed_version: str = "41.0.0",
    ) -> PolicySandboxComparisonReport:
        """
        Runs side-by-side evaluation of active vs proposed policy on the given corpus.
        """
        # 1. Run safety regression suite on proposed
        safety_report = cls.run_safety_regression_suite(proposed_eval_fn)

        # 2. Replay active
        active_correct = 0
        proposed_correct = 0
        active_human = 0
        proposed_human = 0

        all_types = [t.value for t in LoopDecisionType]
        active_cm: dict[str, dict[str, int]] = {exp: {act: 0 for act in all_types} for exp in all_types}
        proposed_cm: dict[str, dict[str, int]] = {exp: {act: 0 for act in all_types} for exp in all_types}

        for i, rec in enumerate(corpus):
            exp = expected_decisions[i] if i < len(expected_decisions) else rec.original_decision
            ctx = DecisionReplayEngine.context_from_dict(rec.context_dict)

            # Active
            act_dec, _, _ = active_eval_fn(ctx)
            if act_dec == exp:
                active_correct += 1
            if act_dec == LoopDecisionType.REQUEST_HUMAN:
                active_human += 1
            active_cm[exp.value][act_dec.value] += 1

            # Proposed
            prop_dec, _, _ = proposed_eval_fn(ctx)
            if prop_dec == exp:
                proposed_correct += 1
            if prop_dec == LoopDecisionType.REQUEST_HUMAN:
                proposed_human += 1
            proposed_cm[exp.value][prop_dec.value] += 1

        n = len(corpus)
        act_acc = round(active_correct / n, 4) if n > 0 else 1.0
        prop_acc = round(proposed_correct / n, 4) if n > 0 else 1.0
        delta = round(prop_acc - act_acc, 4)

        recommendation = "RECOMMENDED_FOR_HUMAN_REVIEW"
        if safety_report.verdict == "REJECTED" or delta < 0:
            recommendation = "AUTOMATIC_REJECT"

        return PolicySandboxComparisonReport(
            active_policy_version=active_version,
            proposed_policy_version=proposed_version,
            corpus_size=n,
            active_accuracy=act_acc,
            proposed_accuracy=prop_acc,
            accuracy_delta=delta,
            active_confusion_matrix=active_cm,
            proposed_confusion_matrix=proposed_cm,
            active_escalation_rate=round(active_human / n, 4) if n > 0 else 0.0,
            proposed_escalation_rate=round(proposed_human / n, 4) if n > 0 else 0.0,
            safety_report=safety_report,
            recommendation=recommendation,
        )
