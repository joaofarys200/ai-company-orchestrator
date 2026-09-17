"""
JARVIS OS — Phase 57: Mission Evidence Collector & Integrity Verifier
Collects multi-dimensional evidence across build, test, contract, browser, security,
calculates SHA-256 hashes and verifies evidence set integrity.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from .models import (
    AutonomousMission,
    EvidenceStatus,
    MissionEvidence,
    MissionEvidenceSet,
    MissionEvidenceType,
)


class EvidenceCollector:
    """Collects and audits immutable SHA-256 evidence for autonomous missions."""

    @classmethod
    def record_build_evidence(
        cls,
        mission: AutonomousMission,
        success: bool,
        output_files: list[str],
        diagnostics: dict[str, Any] | None = None,
    ) -> MissionEvidence:
        ev = MissionEvidence.create(
            evidence_type=MissionEvidenceType.BUILD,
            source="project_builder_tsc_pycompile",
            mission_id=mission.mission_id,
            status=EvidenceStatus.VALID if success else EvidenceStatus.INVALID,
            payload={
                "success": success,
                "output_files": output_files,
                "diagnostics": diagnostics or {},
            },
        )
        mission.evidence_set.add_evidence(ev)
        return ev

    @classmethod
    def record_test_evidence(
        cls,
        mission: AutonomousMission,
        passed_count: int,
        failed_count: int,
        test_suite_name: str,
        duration_ms: float = 120.0,
    ) -> MissionEvidence:
        is_success = failed_count == 0 and passed_count > 0
        ev = MissionEvidence.create(
            evidence_type=MissionEvidenceType.TEST,
            source=f"pytest_runner:{test_suite_name}",
            mission_id=mission.mission_id,
            status=EvidenceStatus.VALID if is_success else EvidenceStatus.INVALID,
            payload={
                "test_suite": test_suite_name,
                "passed": passed_count,
                "failed": failed_count,
                "duration_ms": duration_ms,
                "all_passed": is_success,
            },
        )
        mission.evidence_set.add_evidence(ev)
        return ev

    @classmethod
    def record_contract_evidence(
        cls,
        mission: AutonomousMission,
        schema_name: str,
        is_valid: bool,
        breaking_changes: list[str] | None = None,
    ) -> MissionEvidence:
        ev = MissionEvidence.create(
            evidence_type=MissionEvidenceType.CONTRACT,
            source=f"contract_governance:{schema_name}",
            mission_id=mission.mission_id,
            status=EvidenceStatus.VALID if is_valid else EvidenceStatus.INVALID,
            payload={
                "schema_name": schema_name,
                "valid": is_valid,
                "breaking_changes": breaking_changes or [],
            },
        )
        mission.evidence_set.add_evidence(ev)
        return ev

    @classmethod
    def record_browser_evidence(
        cls,
        mission: AutonomousMission,
        url: str,
        screenshot_path: str,
        console_errors: int = 0,
        network_failures: int = 0,
    ) -> MissionEvidence:
        is_valid = console_errors == 0 and network_failures == 0
        ev = MissionEvidence.create(
            evidence_type=MissionEvidenceType.BROWSER,
            source="playwright_edge_official",
            mission_id=mission.mission_id,
            status=EvidenceStatus.VALID if is_valid else EvidenceStatus.INVALID,
            payload={
                "target_url": url,
                "screenshot_path": screenshot_path,
                "console_errors": console_errors,
                "network_failures": network_failures,
            },
        )
        mission.evidence_set.add_evidence(ev)
        return ev

    @classmethod
    def record_security_evidence(
        cls,
        mission: AutonomousMission,
        passed_sentinel_audit: bool,
        quarantine_actions: list[str] | None = None,
        safety_score: float = 1.0,
    ) -> MissionEvidence:
        ev = MissionEvidence.create(
            evidence_type=MissionEvidenceType.SECURITY,
            source="security_sentinel_watchdog",
            mission_id=mission.mission_id,
            status=EvidenceStatus.VALID if passed_sentinel_audit else EvidenceStatus.INVALID,
            payload={
                "passed_audit": passed_sentinel_audit,
                "quarantine_actions": quarantine_actions or [],
                "safety_score": safety_score,
            },
        )
        mission.evidence_set.add_evidence(ev)
        return ev

    @classmethod
    def record_convergence_evidence(
        cls,
        mission: AutonomousMission,
        state: str,
        lyapunov_v: float,
        cycle_detected: bool,
        stall_detected: bool,
        divergence_detected: bool,
    ) -> MissionEvidence:
        is_converged = state in ("CONVERGED", "COMMITTED", "STABLE") and not (cycle_detected or divergence_detected)
        ev = MissionEvidence.create(
            evidence_type=MissionEvidenceType.CONVERGENCE,
            source="repair_convergence_governance_phase56",
            mission_id=mission.mission_id,
            status=EvidenceStatus.VALID if is_converged else EvidenceStatus.INVALID,
            payload={
                "convergence_state": state,
                "lyapunov_v": lyapunov_v,
                "cycle_detected": cycle_detected,
                "stall_detected": stall_detected,
                "divergence_detected": divergence_detected,
            },
        )
        mission.evidence_set.add_evidence(ev)
        return ev

    @classmethod
    def record_repair_evidence(
        cls,
        mission: AutonomousMission,
        repair_id: str,
        patch_summary: str,
        success: bool,
    ) -> MissionEvidence:
        ev = MissionEvidence.create(
            evidence_type=MissionEvidenceType.REPAIR,
            source="verified_repair_synthesis_phase54",
            mission_id=mission.mission_id,
            status=EvidenceStatus.VALID if success else EvidenceStatus.INVALID,
            payload={
                "repair_id": repair_id,
                "patch_summary": patch_summary,
                "success": success,
            },
        )
        mission.evidence_set.add_evidence(ev)
        return ev
