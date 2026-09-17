"""
JARVIS OS — Phase 57: Mission Completion Evaluator & Objective Retention Guard
Evaluates the 12 non-negotiable mission completion criteria, detects False Completion,
and guards strictly against unauthorized Objective Drift.
"""

from __future__ import annotations

import time
from typing import Any

from .models import (
    AutonomousMission,
    CompletionDecision,
    CriterionStatus,
    EvidenceStatus,
    MissionEvidenceType,
    MissionHumanReviewReason,
    MissionState,
    RequirementCategory,
)


class ObjectiveDriftError(Exception):
    """Raised when an unauthorized objective drift or requirement drop is detected."""


class ObjectiveRetentionGuard:
    """Guards against silent objective drift and requirement degradation."""

    @classmethod
    def check_retention(cls, mission: AutonomousMission) -> tuple[bool, str | None]:
        # 1. Check if objective was mutated
        if mission.objective.strip() != mission.original_objective.strip():
            # Allow minor whitespace/case or flag drift
            msg = f"OBJECTIVE_DRIFT: Objetivo alterado de '{mission.original_objective}' para '{mission.objective}'"
            return False, msg

        # 2. Check if critical user requirements were dropped
        user_reqs = [r for r in mission.requirements if r.category == RequirementCategory.USER_REQUIREMENT and r.critical]
        if not user_reqs and mission.requirements:
            return False, "OBJECTIVE_DRIFT: Requisitos críticos de utilizador foram eliminados"

        return True, None


class MissionCompletionEvaluator:
    """Evaluates mission completion across 12 rigorous criteria."""

    CRITERIA_KEYS = [
        "objective_satisfied",
        "acceptance_criteria_satisfied",
        "required_artifacts_present",
        "build_valid",
        "relevant_tests_valid",
        "contracts_valid",
        "behavior_valid",
        "security_valid",
        "browser_valid_when_required",
        "no_blocking_failures",
        "convergence_valid",
        "evidence_complete",
    ]

    @classmethod
    def evaluate(cls, mission: AutonomousMission) -> tuple[CompletionDecision, dict[str, Any]]:
        # 1. Run Objective Retention Guard
        retention_ok, retention_err = ObjectiveRetentionGuard.check_retention(mission)
        if not retention_ok:
            return (
                CompletionDecision.HUMAN_REVIEW_REQUIRED,
                {
                    "verdict": "OBJECTIVE_DRIFT_DETECTED",
                    "reason": retention_err,
                    "details": {"retention_ok": False},
                },
            )

        # 2. Evaluate all 12 criteria
        ev_set = mission.evidence_set
        domain = mission.provenance.get("domain", "general_engineering")
        is_ui = domain in ("frontend", "fullstack", "browser_task")

        # Criterion 1: Objective satisfied
        objective_satisfied = bool(mission.objective and mission.state != MissionState.FAILED)

        # Criterion 2: Acceptance criteria satisfied
        crit_results = []
        acceptance_criteria_satisfied = True
        for c in mission.acceptance_criteria:
            if c.required and c.status != CriterionStatus.SATISFIED:
                acceptance_criteria_satisfied = False
            crit_results.append(c.to_dict())

        # Criterion 3: Required artifacts present
        has_artifact = ev_set.has_valid(MissionEvidenceType.ARTIFACT) or len(ev_set.evidences) > 0
        required_artifacts_present = has_artifact

        # Criterion 4: Build valid
        build_valid = ev_set.has_valid(MissionEvidenceType.BUILD)

        # Criterion 5: Relevant tests valid
        relevant_tests_valid = ev_set.has_valid(MissionEvidenceType.TEST)

        # Criterion 6: Contracts valid (if applicable)
        has_contract_ev = ev_set.has_valid(MissionEvidenceType.CONTRACT)
        contracts_valid = True
        if domain in ("backend", "contract_change", "fullstack"):
            contracts_valid = has_contract_ev

        # Criterion 7: Behavior valid
        behavior_valid = ev_set.has_valid(MissionEvidenceType.BEHAVIOR) or relevant_tests_valid

        # Criterion 8: Security valid (Mandatory Sovereign Gate)
        has_security_fail = any(
            e.type == MissionEvidenceType.SECURITY and e.status == EvidenceStatus.INVALID
            for e in ev_set.evidences
        )
        security_valid = ev_set.has_valid(MissionEvidenceType.SECURITY) and not has_security_fail

        # Criterion 9: Browser valid when required
        browser_valid_when_required = True
        if is_ui:
            browser_valid_when_required = ev_set.has_valid(MissionEvidenceType.BROWSER)

        # Criterion 10: No blocking failures
        blocking_failures = [f for f in mission.failures if f.get("blocking", False) and not f.get("resolved", False)]
        no_blocking_failures = len(blocking_failures) == 0

        # Criterion 11: Convergence valid
        convergence_info = mission.convergence or {}
        convergence_state = convergence_info.get("state", "CONVERGED")
        convergence_valid = convergence_state in ("CONVERGED", "STABLE", "COMMITTED") and not convergence_info.get("cycle_detected", False)

        # Criterion 12: Evidence complete
        evidence_complete = len(ev_set.evidences) >= 3 and ev_set.compute_aggregate_hash() != ""

        status_map = {
            "objective_satisfied": objective_satisfied,
            "acceptance_criteria_satisfied": acceptance_criteria_satisfied,
            "required_artifacts_present": required_artifacts_present,
            "build_valid": build_valid,
            "relevant_tests_valid": relevant_tests_valid,
            "contracts_valid": contracts_valid,
            "behavior_valid": behavior_valid,
            "security_valid": security_valid,
            "browser_valid_when_required": browser_valid_when_required,
            "no_blocking_failures": no_blocking_failures,
            "convergence_valid": convergence_valid,
            "evidence_complete": evidence_complete,
        }

        # 3. False Completion Prevention Rules:
        # Rule A: Build and tests pass, but Security Fails
        if build_valid and relevant_tests_valid and not security_valid:
            return (
                CompletionDecision.MISSION_BLOCKED,
                {
                    "verdict": "FALSE_COMPLETION_PREVENTED_SECURITY_VIOLATION",
                    "criteria_status": status_map,
                    "reason": "Build e testes passaram, mas ocorreu violação mandatória de segurança",
                },
            )

        # Rule B: Build and tests pass, but Contract Fails
        if build_valid and relevant_tests_valid and not contracts_valid:
            return (
                CompletionDecision.MISSION_FAILED,
                {
                    "verdict": "FALSE_COMPLETION_PREVENTED_CONTRACT_DRIFT",
                    "criteria_status": status_map,
                    "reason": "Build e testes passaram, mas contratos da API/Schema falharam",
                },
            )

        # Rule C: Build and tests pass, but Browser Validation Fails for UI mission
        if build_valid and relevant_tests_valid and is_ui and not browser_valid_when_required:
            return (
                CompletionDecision.MISSION_BLOCKED,
                {
                    "verdict": "FALSE_COMPLETION_PREVENTED_BROWSER_FAILURE",
                    "criteria_status": status_map,
                    "reason": "Build e testes passaram, mas validação visual no browser falhou ou está ausente",
                },
            )

        # Rule D: Build and tests pass, but acceptance criteria are unsatisfied
        if build_valid and relevant_tests_valid and not acceptance_criteria_satisfied:
            return (
                CompletionDecision.MISSION_FAILED,
                {
                    "verdict": "FALSE_COMPLETION_PREVENTED_MISSING_CRITERIA",
                    "criteria_status": status_map,
                    "reason": "Testes unitários passaram, mas critérios de aceitação observáveis não foram satisfeitos",
                },
            )

        # Rule E: Insufficient Evidence
        if not evidence_complete:
            return (
                CompletionDecision.MISSION_INSUFFICIENT_EVIDENCE,
                {
                    "verdict": "INSUFFICIENT_EVIDENCE",
                    "criteria_status": status_map,
                    "reason": "Evidências insuficientes para comprovar a conclusão da missão",
                },
            )

        # Rule F: Blocking failures present
        if not no_blocking_failures:
            return (
                CompletionDecision.MISSION_BLOCKED,
                {
                    "verdict": "BLOCKING_FAILURES_PRESENT",
                    "criteria_status": status_map,
                    "blocking_failures": blocking_failures,
                    "reason": f"Restam {len(blocking_failures)} falhas bloqueantes não resolvidas",
                },
            )

        # Rule G: Non-convergence or cycling
        if not convergence_valid:
            return (
                CompletionDecision.MISSION_FAILED,
                {
                    "verdict": "NON_CONVERGENCE_TERMINATION",
                    "criteria_status": status_map,
                    "reason": "Ciclo de reparações não convergiu ou entrou em oscilação",
                },
            )

        # 4. Success check: All 12 criteria must be True
        all_passed = all(status_map.values())
        if all_passed:
            return (
                CompletionDecision.MISSION_PROVEN_COMPLETE,
                {
                    "verdict": "ALL_CRITERIA_SATISFIED",
                    "criteria_status": status_map,
                    "reason": "Todos os 12 critérios formais de conclusão foram comprovados com sucesso",
                },
            )

        # Default fallback: Insufficient Evidence
        return (
            CompletionDecision.MISSION_INSUFFICIENT_EVIDENCE,
            {
                "verdict": "PARTIAL_CRITERIA_SATISFIED",
                "criteria_status": status_map,
                "failed_criteria": [k for k, v in status_map.items() if not v],
            },
        )
