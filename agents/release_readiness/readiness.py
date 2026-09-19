"""
Release Candidate Readiness Lifecycle Module
Phase 70 — Autonomous Release Readiness & Production Governance

Orchestrates candidate lifecycles and enforces strict finite-state-machine rules.
Crucial invariant: Transitions directly from CREATED to RELEASED are strictly forbidden.
"""

from __future__ import annotations
import uuid
import time
from typing import Dict, Any, Optional
from .models import ReleaseCandidate, ReleaseCandidateState
from .provenance import ReleaseProvenanceTracker


class ReleaseCandidateLifecycleManager:
    """Manages state transitions and lifecycle validation for release candidates."""

    LEGAL_TRANSITIONS = {
        ReleaseCandidateState.CREATED: {
            ReleaseCandidateState.ANALYZING,
            ReleaseCandidateState.BLOCKED,
            ReleaseCandidateState.NOT_READY
        },
        ReleaseCandidateState.ANALYZING: {
            ReleaseCandidateState.VALIDATING,
            ReleaseCandidateState.BLOCKED,
            ReleaseCandidateState.NOT_READY
        },
        ReleaseCandidateState.VALIDATING: {
            ReleaseCandidateState.READY,
            ReleaseCandidateState.READY_WITH_RISK,
            ReleaseCandidateState.HUMAN_REVIEW,
            ReleaseCandidateState.BLOCKED,
            ReleaseCandidateState.NOT_READY,
            ReleaseCandidateState.REJECTED
        },
        ReleaseCandidateState.READY: {
            ReleaseCandidateState.RELEASED,
            ReleaseCandidateState.BLOCKED,
            ReleaseCandidateState.NOT_READY
        },
        ReleaseCandidateState.READY_WITH_RISK: {
            ReleaseCandidateState.RELEASED,
            ReleaseCandidateState.BLOCKED,
            ReleaseCandidateState.NOT_READY
        },
        ReleaseCandidateState.HUMAN_REVIEW: {
            ReleaseCandidateState.READY,
            ReleaseCandidateState.READY_WITH_RISK,
            ReleaseCandidateState.BLOCKED,
            ReleaseCandidateState.NOT_READY,
            ReleaseCandidateState.REJECTED
        },
        ReleaseCandidateState.RELEASED: {
            ReleaseCandidateState.ROLLED_BACK
        },
        ReleaseCandidateState.BLOCKED: {
            ReleaseCandidateState.ANALYZING,  # Re-evaluation allowed
            ReleaseCandidateState.REJECTED
        },
        ReleaseCandidateState.NOT_READY: {
            ReleaseCandidateState.ANALYZING
        },
        ReleaseCandidateState.REJECTED: set(),
        ReleaseCandidateState.ROLLED_BACK: set()
    }

    @classmethod
    def create_candidate(
        cls,
        mission_id: str,
        commit_sha: str,
        workspace_snapshot: str,
        artifact_hashes: Optional[Dict[str, str]] = None,
        version: str = "1.0.0",
        environment: str = "production",
        release_id: Optional[str] = None
    ) -> ReleaseCandidate:
        """Creates a new candidate initialized in CREATED state with provenance record."""
        r_id = release_id or f"rc-{uuid.uuid4().hex[:12]}"
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        hashes = artifact_hashes or {}

        candidate = ReleaseCandidate(
            release_id=r_id,
            mission_id=mission_id,
            commit_sha=commit_sha,
            workspace_snapshot=workspace_snapshot,
            artifact_hashes=hashes,
            version=version,
            environment=environment,
            created_at=now,
            state=ReleaseCandidateState.CREATED
        )

        provenance = ReleaseProvenanceTracker.create_provenance_record(
            entity_id=candidate.release_id,
            entity_type="ReleaseCandidate",
            content=candidate.to_dict()
        )
        candidate.provenance = provenance
        return candidate

    @classmethod
    def transition_state(
        cls,
        candidate: ReleaseCandidate,
        target_state: ReleaseCandidateState,
        reason: str = ""
    ) -> ReleaseCandidate:
        """
        Transitions candidate to target state.
        Raises ValueError if transition violates the finite-state machine.
        """
        current_state = candidate.state
        if isinstance(current_state, str):
            current_state = ReleaseCandidateState(current_state)
        if isinstance(target_state, str):
            target_state = ReleaseCandidateState(target_state)

        # Explicit check for the prohibited invariant CREATED -> RELEASED
        if current_state == ReleaseCandidateState.CREATED and target_state == ReleaseCandidateState.RELEASED:
            raise ValueError("Illegal transition: CREATED -> RELEASED is strictly forbidden")

        allowed_targets = cls.LEGAL_TRANSITIONS.get(current_state, set())
        if target_state not in allowed_targets:
            raise ValueError(
                f"Illegal state transition from {current_state.value} to {target_state.value} "
                f"(Allowed: {[s.value for s in allowed_targets]})"
            )

        candidate.state = target_state
        # Update provenance trail
        candidate.provenance = ReleaseProvenanceTracker.create_provenance_record(
            entity_id=candidate.release_id,
            entity_type="ReleaseCandidate",
            content=candidate.to_dict(),
            parent_hash=candidate.provenance.get("provenance_hash", "")
        )
        return candidate
