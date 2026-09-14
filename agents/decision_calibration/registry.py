"""
JARVIS OS — Phase 41: Autonomous Decision Calibration & Failure Intelligence
Decision Policy Registry: Versioning, Immutability, Governance & Atomic Rollback.

Principles:
- Policy versions are strictly immutable once created.
- Exactly one ACTIVE policy version is in effect at any time.
- Security Sentinel and Mission Gate bypass operations are permanently blocked.
- Atomic, audited rollback preserves parent-child lineage without deleting history.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from agents.autonomous_loop.models import LoopDecisionType
from agents.autonomous_loop.policy import AutonomousDecisionPolicy, PolicyRuleDefinition
from agents.decision_calibration.models import (
    PROHIBITED_POLICY_OPERATIONS,
    PolicyChangeProposal,
    PolicyChangeType,
    PolicyStatus,
)


@dataclass
class RegisteredPolicyVersion:
    policy_id: str
    version: str
    rules: list[dict[str, Any]]
    status: PolicyStatus
    parent_version: Optional[str]
    changelog: str
    created_at: float = field(default_factory=time.time)
    approval_metadata: dict[str, Any] = field(default_factory=dict)
    version_hash: str = ""

    def __post_init__(self):
        if not self.version_hash:
            content = f"{self.policy_id}:{self.version}:{self.parent_version}:{json.dumps(self.rules, sort_keys=True)}"
            self.version_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


class DecisionPolicyRegistry:
    """
    Central registry for versioned autonomous decision policies.
    Enforces immutability, prohibited operation guards, and atomic rollback.
    """

    def __init__(self):
        self._versions: dict[str, RegisteredPolicyVersion] = {}
        self._active_version_id: str = ""
        self._shadow_version_id: Optional[str] = None
        self._init_baseline_policy()

    def _init_baseline_policy(self):
        # Baseline Phase 40 policy
        baseline_rules = [
            {
                "rule_id": r.rule_id,
                "priority": r.priority,
                "condition_name": r.condition_name,
                "allowed_decision": r.allowed_decision.value,
                "description": r.description,
                "consequence": r.consequence,
            }
            for r in AutonomousDecisionPolicy.RULES_TABLE
        ]
        baseline = RegisteredPolicyVersion(
            policy_id="pol_v40_baseline",
            version="40.1.0",
            rules=baseline_rules,
            status=PolicyStatus.ACTIVE,
            parent_version=None,
            changelog="Phase 40 baseline deterministic decision policy (14 rules).",
            approval_metadata={"approved_by": "SYSTEM_BOOTSTRAP", "reason": "Phase 40 verified baseline"},
        )
        self._versions[baseline.version] = baseline
        self._active_version_id = baseline.version

    @property
    def active_version(self) -> str:
        return self._active_version_id

    @property
    def shadow_version(self) -> Optional[str]:
        return self._shadow_version_id

    def get_policy(self, version: str) -> Optional[RegisteredPolicyVersion]:
        return self._versions.get(version)

    def list_policies(self) -> list[dict[str, Any]]:
        return [p.to_dict() for p in sorted(self._versions.values(), key=lambda x: x.created_at)]

    def create_proposal_version(
        self,
        proposal: PolicyChangeProposal,
        modified_rules: list[dict[str, Any]],
        creator: str = "PolicyProposalEngine",
    ) -> RegisteredPolicyVersion:
        """
        Creates an immutable PROPOSED policy version linked to parent active version.
        Validates prohibited operations.
        """
        # 1. Prohibited operations check
        is_valid, reason = proposal.validate_prohibited_operations()
        if not is_valid:
            raise ValueError(f"Cannot register prohibited policy proposal: {reason}")

        # Ensure no rule modifies or deletes security / mission gate invariant
        for rule in modified_rules:
            r_id = rule.get("rule_id", "")
            if "SECURITY" in r_id and rule.get("allowed_decision") != LoopDecisionType.BLOCK.value:
                raise ValueError("SECURITY_BLOCK rule cannot be modified to a non-BLOCK decision.")

        # 2. Construct registered version
        new_version = RegisteredPolicyVersion(
            policy_id=f"pol_{proposal.proposed_policy_version.replace('.', '_')}",
            version=proposal.proposed_policy_version,
            rules=modified_rules,
            status=PolicyStatus.PROPOSED,
            parent_version=self._active_version_id,
            changelog=f"Proposal {proposal.proposal_id}: {proposal.expected_benefit}",
            approval_metadata={"creator": creator, "proposal_id": proposal.proposal_id},
        )
        self._versions[new_version.version] = new_version
        return new_version

    def set_shadow_version(self, version: str):
        if version not in self._versions:
            raise ValueError(f"Policy version {version} not found.")
        self._shadow_version_id = version
        if self._versions[version].status == PolicyStatus.PROPOSED:
            self._versions[version].status = PolicyStatus.SHADOW

    def clear_shadow_version(self):
        if self._shadow_version_id and self._shadow_version_id in self._versions:
            if self._versions[self._shadow_version_id].status == PolicyStatus.SHADOW:
                self._versions[self._shadow_version_id].status = PolicyStatus.PROPOSED
        self._shadow_version_id = None

    def approve_and_activate(
        self,
        version: str,
        approver: str,
        approval_notes: str = "",
    ) -> RegisteredPolicyVersion:
        """
        Activates a proposed or shadow policy version following explicit human review.
        Supersedes the currently active version.
        """
        if version not in self._versions:
            raise ValueError(f"Policy version {version} not found.")
        target = self._versions[version]

        if target.status in [PolicyStatus.REJECTED, PolicyStatus.ROLLED_BACK]:
            raise ValueError(f"Cannot activate policy {version} with status {target.status.value}")

        # Supersede current active
        if self._active_version_id and self._active_version_id in self._versions:
            current = self._versions[self._active_version_id]
            current.status = PolicyStatus.SUPERSEDED

        target.status = PolicyStatus.ACTIVE
        target.approval_metadata.update({
            "approved_by": approver,
            "approved_at": time.time(),
            "notes": approval_notes,
        })
        self._active_version_id = version
        if self._shadow_version_id == version:
            self._shadow_version_id = None
        return target

    def reject_proposal(self, version: str, rejector: str, reason: str) -> RegisteredPolicyVersion:
        if version not in self._versions:
            raise ValueError(f"Policy version {version} not found.")
        target = self._versions[version]
        target.status = PolicyStatus.REJECTED
        target.approval_metadata.update({
            "rejected_by": rejector,
            "rejected_at": time.time(),
            "rejection_reason": reason,
        })
        if self._shadow_version_id == version:
            self._shadow_version_id = None
        return target

    def rollback(self, target_version: Optional[str] = None, operator: str = "human_operator") -> RegisteredPolicyVersion:
        """
        Atomic rollback to target_version or parent_version.
        Marks currently active version as ROLLED_BACK.
        """
        current = self._versions[self._active_version_id]
        fallback_version = target_version or current.parent_version
        if not fallback_version:
            raise ValueError(f"No parent version exists to rollback from {current.version}.")
        if fallback_version not in self._versions:
            raise ValueError(f"Target rollback version {fallback_version} not found in registry.")

        parent = self._versions[fallback_version]
        current.status = PolicyStatus.ROLLED_BACK
        current.approval_metadata["rolled_back_by"] = operator
        current.approval_metadata["rolled_back_at"] = time.time()

        parent.status = PolicyStatus.ACTIVE
        self._active_version_id = fallback_version
        return parent
