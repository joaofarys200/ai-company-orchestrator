"""
JARVIS OS — Phase 57: Security Sentinel Sovereignty & Anti-Adversarial Defenses
Enforces upper-authority Sentinel sovereignty against mission poisoning, objective injection,
criteria tampering, evidence spoofing, memory poisoning, and dangerous command execution.
"""

from __future__ import annotations

import re
from typing import Any

from .failure import FailureCategory, FailureManager, FailureSeverity
from .models import AutonomousMission, MissionEvidence, MissionState


class SecurityAuditError(Exception):
    """Raised when a severe security violation or adversarial attack is detected."""


class MissionSecuritySentinel:
    """Watchdog auditing mission payloads, intent, criteria, and evidence for adversarial manipulation."""

    ADVERSARIAL_PATTERNS = [
        r"ignore (all )?previous instructions",
        r"bypass (security|sentinel|gate)",
        r"rm\s+-rf",
        r"drop\s+database",
        r"delete\s+from\s+users",
        r"curl\s+.*\.(onion|sh|exe)",
        r"chmod\s+777",
        r"cat\s+.*\.env",
        r"steal\s+token",
        r"disable\s+(sentinel|sandbox|firewall)",
    ]

    @classmethod
    def audit_intent(cls, raw_intent: str) -> tuple[bool, str | None]:
        lower = raw_intent.lower()
        for pattern in cls.ADVERSARIAL_PATTERNS:
            if re.search(pattern, lower):
                return False, f"ADVERSARIAL_ATTACK_DETECTED: Padrão destrutivo ou injeção detectada ('{pattern}')"
        return True, None

    @classmethod
    def audit_mission_security(cls, mission: AutonomousMission) -> tuple[bool, str | None]:
        # 1. Audit objective
        is_safe, reason = cls.audit_intent(mission.objective)
        if not is_safe:
            cls._flag_security_block(mission, reason or "Injeção no objetivo da missão")
            return False, reason

        # 2. Audit acceptance criteria against criteria poisoning
        for crit in mission.acceptance_criteria:
            is_c_safe, c_reason = cls.audit_intent(crit.description)
            if not is_c_safe:
                cls._flag_security_block(mission, f"Envenenamento de critério de aceitação: {c_reason}")
                return False, c_reason

        # 3. Audit evidence integrity against spoofing
        for ev in mission.evidence_set.evidences:
            if not ev.hash or len(ev.hash) != 64:
                cls._flag_security_block(mission, f"Hash SHA-256 inválido na evidência {ev.evidence_id}")
                return False, "Evidência corrompida ou falsificada (spoofing)"

        return True, None

    @classmethod
    def _flag_security_block(cls, mission: AutonomousMission, description: str) -> None:
        FailureManager.record_failure(
            mission=mission,
            description=description,
            category=FailureCategory.SECURITY,
            severity=FailureSeverity.BLOCKING,
        )
        mission.state = MissionState.BLOCKED
