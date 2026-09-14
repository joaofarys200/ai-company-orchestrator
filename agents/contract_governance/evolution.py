"""
JARVIS OS — Phase 46: Versioned Contract Evolution & Rollback Manager
Manages immutable contract baselines, version progression (v1 -> v2),
human approval gating, and deterministic rollback preserving history.
"""

from __future__ import annotations

import copy
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from agents.contract_governance.models import (
    ContractBaseline,
    ContractDriftReport,
    DriftClassification,
    DriftResolution,
    DriftResolutionAction,
    ProposedContractVersion,
)
from agents.contract_governance.security import ContractGovernanceSecurity


class ContractEvolutionManager:
    """Oversees version progression, approval gates, and rollback for immutable contract baselines."""

    def __init__(self) -> None:
        self._active_baselines: Dict[str, ContractBaseline] = {}
        self._version_history: Dict[str, List[ContractBaseline]] = {}
        self._proposals: Dict[str, ProposedContractVersion] = {}
        self._resolutions: List[DriftResolution] = []

    def register_baseline(self, baseline: ContractBaseline) -> None:
        """Registers a baseline as the active verified contract and appends to history."""
        # Validate integrity
        if not ContractGovernanceSecurity.verify_baseline_integrity(baseline):
            raise ValueError(f"Integrity check failed: schema_hash does not match baseline content for '{baseline.contract_id}'")

        self._active_baselines[baseline.contract_id] = baseline
        if baseline.contract_id not in self._version_history:
            self._version_history[baseline.contract_id] = []
        
        # Avoid duplicate version in history
        existing_versions = [b.version for b in self._version_history[baseline.contract_id]]
        if baseline.version not in existing_versions:
            self._version_history[baseline.contract_id].append(baseline)

    def get_active_baseline(self, contract_id: str) -> Optional[ContractBaseline]:
        return self._active_baselines.get(contract_id)

    def list_active_baselines(self) -> List[ContractBaseline]:
        return list(self._active_baselines.values())

    def get_version_history(self, contract_id: str) -> List[ContractBaseline]:
        return list(self._version_history.get(contract_id, []))

    def propose_version_evolution(
        self,
        drift_report: ContractDriftReport,
        new_version_tag: str,
        migration_impact: str = "",
        updated_response_schema: Optional[Dict[str, Any]] = None,
        updated_request_schema: Optional[Dict[str, Any]] = None,
    ) -> ProposedContractVersion:
        """Constructs a ProposedContractVersion v2 from confirmed drift on v1."""
        active_baseline = self.get_active_baseline(drift_report.contract_id)
        if not active_baseline:
            raise ValueError(f"No active baseline found for contract '{drift_report.contract_id}'")

        proposal_id = f"prop_v2_{uuid.uuid4().hex[:8]}"

        # Synthesize proposed new schemas based on changes if not explicitly provided
        new_resp = copy.deepcopy(updated_response_schema if updated_response_schema is not None else active_baseline.response_schema)
        new_req = copy.deepcopy(updated_request_schema if updated_request_schema is not None else active_baseline.request_schema)

        # Compute new deterministic hash
        new_hash = ContractBaseline.compute_schema_hash(
            request_schema=new_req,
            response_schema=new_resp,
            error_contract=active_baseline.error_contract,
        )

        proposed_baseline = ContractBaseline(
            contract_id=active_baseline.contract_id,
            version=new_version_tag,
            schema_hash=new_hash,
            route=active_baseline.route,
            method=active_baseline.method,
            request_schema=new_req,
            response_schema=new_resp,
            error_contract=active_baseline.error_contract,
            provenance={
                "derived_from_proposal": proposal_id,
                "parent_version": active_baseline.version,
                "evidence_refs": drift_report.evidence_refs,
            },
            validated_at=time.time(),
            validated_by="pending_approval",
            semantic_graph_version=active_baseline.semantic_graph_version + 1,
            policy_version=active_baseline.policy_version,
            parent_version=active_baseline.version,
            metadata={
                "evolution_reason": drift_report.notes or "Evolved from runtime drift",
                "drift_classification": drift_report.classification.value,
            },
        )

        is_breaking = drift_report.classification == DriftClassification.BREAKING

        proposal = ProposedContractVersion(
            proposal_id=proposal_id,
            contract_id=active_baseline.contract_id,
            parent_version=active_baseline.version,
            new_version=new_version_tag,
            proposed_baseline=proposed_baseline,
            diff_report=drift_report,
            evidence_refs=drift_report.evidence_refs,
            affected_consumers=drift_report.affected_consumers,
            migration_impact=migration_impact or f"Evolution from {active_baseline.version} to {new_version_tag}",
            approval_required=is_breaking or bool(drift_report.changes),
            status="PENDING_APPROVAL",
        )

        self._proposals[proposal_id] = proposal
        return proposal

    def review_proposal(
        self,
        proposal_id: str,
        action: str,
        operator_id: str = "human_operator",
        notes: str = "",
    ) -> Dict[str, Any]:
        """Applies human approval gate to proposed version evolution."""
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return {"success": False, "error": f"Proposal '{proposal_id}' not found"}

        is_breaking = proposal.diff_report.classification == DriftClassification.BREAKING

        # Security check
        if not ContractGovernanceSecurity.validate_operator_authorization(operator_id, is_breaking=is_breaking):
            return {
                "success": False,
                "error": f"Operator '{operator_id}' is unauthorized to approve contract evolution",
            }

        action_upper = action.upper()
        if action_upper in ("APPROVE", "ACCEPT"):
            proposal.status = "APPROVED"
            proposal.approved_by = operator_id
            proposal.approval_notes = notes

            # Activate the new baseline
            active_candidate = proposal.proposed_baseline
            activated_baseline = ContractBaseline(
                contract_id=active_candidate.contract_id,
                version=active_candidate.version,
                schema_hash=active_candidate.schema_hash,
                route=active_candidate.route,
                method=active_candidate.method,
                request_schema=active_candidate.request_schema,
                response_schema=active_candidate.response_schema,
                error_contract=active_candidate.error_contract,
                provenance=active_candidate.provenance,
                validated_at=time.time(),
                validated_by=operator_id,
                semantic_graph_version=active_candidate.semantic_graph_version,
                policy_version=active_candidate.policy_version,
                parent_version=active_candidate.parent_version,
                metadata=active_candidate.metadata,
            )

            self.register_baseline(activated_baseline)

            # Record resolution
            resolution = DriftResolution(
                resolution_id=f"res_{uuid.uuid4().hex[:8]}",
                drift_id=proposal.diff_report.drift_id,
                contract_id=proposal.contract_id,
                action=DriftResolutionAction.CREATE_NEW_VERSION,
                contract_version_before=proposal.parent_version,
                contract_version_after=proposal.new_version,
                tasks=[f"task_migrate_{c.consumer_id}" for c in proposal.affected_consumers],
                evidence=proposal.evidence_refs,
                approved_by=operator_id,
                outcome=f"Successfully evolved contract to {proposal.new_version}",
            )
            self._resolutions.append(resolution)

            return {
                "success": True,
                "status": "APPROVED",
                "active_version": proposal.new_version,
                "resolution": resolution.to_dict(),
            }

        elif action_upper in ("REJECT", "BLOCK"):
            proposal.status = "REJECTED"
            proposal.approved_by = operator_id
            proposal.approval_notes = notes

            resolution = DriftResolution(
                resolution_id=f"res_{uuid.uuid4().hex[:8]}",
                drift_id=proposal.diff_report.drift_id,
                contract_id=proposal.contract_id,
                action=DriftResolutionAction.BLOCK,
                contract_version_before=proposal.parent_version,
                contract_version_after=proposal.parent_version,
                evidence=proposal.evidence_refs,
                approved_by=operator_id,
                outcome=f"Rejected proposal {proposal.new_version}: {notes}",
            )
            self._resolutions.append(resolution)

            return {
                "success": True,
                "status": "REJECTED",
                "active_version": proposal.parent_version,
                "resolution": resolution.to_dict(),
            }

        return {"success": False, "error": f"Unknown review action '{action}'"}

    def rollback(
        self,
        contract_id: str,
        target_version: str,
        operator_id: str = "human_operator",
        notes: str = "",
    ) -> Dict[str, Any]:
        """Rolls back the active baseline to a previous target version without deleting newer history."""
        active = self.get_active_baseline(contract_id)
        if not active:
            return {"success": False, "error": f"Contract '{contract_id}' not found"}

        history = self.get_version_history(contract_id)
        target_baseline = next((b for b in history if b.version == target_version), None)
        if not target_baseline:
            return {
                "success": False,
                "error": f"Target rollback version '{target_version}' not found in history of '{contract_id}'",
            }

        # Authorization check
        if not ContractGovernanceSecurity.validate_operator_authorization(operator_id, is_breaking=True):
            return {"success": False, "error": f"Operator '{operator_id}' unauthorized for rollback"}

        version_before = active.version
        # Switch active baseline
        self._active_baselines[contract_id] = target_baseline

        # Create formal audit resolution record
        resolution = DriftResolution(
            resolution_id=f"res_rb_{uuid.uuid4().hex[:8]}",
            drift_id=f"rb_{uuid.uuid4().hex[:6]}",
            contract_id=contract_id,
            action=DriftResolutionAction.ROLLBACK,
            contract_version_before=version_before,
            contract_version_after=target_version,
            tasks=[f"revert_consumers_to_{target_version}"],
            evidence=[f"rollback_authorized_by_{operator_id}"],
            approved_by=operator_id,
            outcome=f"Rolled back from {version_before} to {target_version}. Reason: {notes or 'Operator requested rollback'}",
        )
        self._resolutions.append(resolution)

        return {
            "success": True,
            "status": "ROLLED_BACK",
            "active_version": target_version,
            "previous_version": version_before,
            "resolution": resolution.to_dict(),
        }

    def list_proposals(self) -> List[ProposedContractVersion]:
        return list(self._proposals.values())

    def list_resolutions(self) -> List[DriftResolution]:
        return list(self._resolutions)
