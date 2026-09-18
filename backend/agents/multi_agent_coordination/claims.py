"""
JARVIS OS — Phase 66: Multi-Agent Engineering Coordination & Conflict Arbitration
Module: claims.py
Manages multi-granularity resource claims, compatibility verification, leases, and expiration.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set, Tuple

from .models import ClaimType, ResourceClaim, ResourceGranularity


class ClaimManager:
    """Acquires, releases, and validates compatibility of resource claims."""

    def __init__(self, default_ttl_seconds: float = 300.0):
        self.default_ttl = default_ttl_seconds
        self.active_claims: Dict[str, ResourceClaim] = {}  # claim_id -> claim

    def is_compatible(self, claim_a: ResourceClaim, claim_b: ResourceClaim) -> bool:
        """Check if two resource claims are mutually compatible."""
        if claim_a.resource_id != claim_b.resource_id:
            return True
        if claim_a.claim_type == ClaimType.READ and claim_b.claim_type == ClaimType.READ:
            return True
        if claim_a.claim_type == ClaimType.SHARED and claim_b.claim_type == ClaimType.SHARED:
            return True
        return False

    def acquire_claim(
        self,
        *args,
        **kwargs,
    ) -> Tuple[bool, Optional[ResourceClaim], str]:
        """Request and grant a claim if compatible with existing active claims."""
        self.purge_expired_claims()
        if len(args) == 1 and isinstance(args[0], ResourceClaim):
            claim = args[0]
            self.active_claims[claim.claim_id] = claim
            return True, claim, f"CLAIM_GRANTED: {claim.claim_id}"

        agent_id = args[0] if len(args) > 0 else kwargs.get("agent_id", "")
        intent_id = args[1] if len(args) > 1 else kwargs.get("intent_id", "")
        resource_id = args[2] if len(args) > 2 else kwargs.get("resource_id", "")
        resource_type = args[3] if len(args) > 3 else kwargs.get("resource_type", ResourceGranularity.FILE)
        claim_type = args[4] if len(args) > 4 else kwargs.get("claim_type", ClaimType.READ)
        ttl_seconds = args[5] if len(args) > 5 else kwargs.get("ttl_seconds")

        norm_res = resource_id.replace("\\", "/").strip()
        # Check compatibility with active claims on the same resource
        conflict_msg = self.check_compatibility(norm_res, claim_type, agent_id)
        if conflict_msg:
            return False, None, f"CLAIM_DENIED: {conflict_msg}"

        claim_id = f"claim_{agent_id}_{int(time.time() * 1000) % 1000000}"
        claim = ResourceClaim(
            claim_id=claim_id,
            agent_id=agent_id,
            intent_id=intent_id,
            resource_id=norm_res,
            resource_type=resource_type,
            claim_type=claim_type,
            ttl_seconds=ttl_seconds or self.default_ttl,
        )
        self.active_claims[claim_id] = claim
        return True, claim, f"CLAIM_GRANTED: {claim_id} on {norm_res} as {claim_type.value}"

    def check_compatibility(self, resource_id: str, requested_type: ClaimType, requesting_agent: str) -> Optional[str]:
        """Verify compatibility against active claims for a resource."""
        for c in self.active_claims.values():
            if not c.is_active or c.is_expired():
                continue
            if c.resource_id == resource_id:
                # Same agent can re-claim/upgrade
                if c.agent_id == requesting_agent:
                    continue

                # Conflict rules
                if requested_type == ClaimType.READ and c.claim_type == ClaimType.READ:
                    continue
                if requested_type in {ClaimType.WRITE, ClaimType.EXCLUSIVE, ClaimType.STRUCTURAL} or \
                   c.claim_type in {ClaimType.WRITE, ClaimType.EXCLUSIVE, ClaimType.STRUCTURAL}:
                    return f"Incompatible claim {requested_type.value} conflicts with active {c.claim_type.value} held by {c.agent_id}"

        return None

    def release_claim(self, claim_id: str) -> bool:
        claim = self.active_claims.get(claim_id)
        if claim:
            claim.is_active = False
            del self.active_claims[claim_id]
            return True
        return False

    def release_intent_claims(self, intent_id: str) -> List[str]:
        """Release all claims associated with a finished/aborted intent."""
        released = []
        to_delete = []
        for cid, claim in self.active_claims.items():
            if claim.intent_id == intent_id:
                claim.is_active = False
                released.append(cid)
                to_delete.append(cid)
        for cid in to_delete:
            del self.active_claims[cid]
        return released

    def purge_expired_claims(self) -> List[str]:
        """Automatically expire stale claims preventing permanent orphan locks."""
        expired = []
        now = time.time()
        to_delete = []
        for cid, claim in self.active_claims.items():
            if claim.is_expired(now):
                claim.is_active = False
                expired.append(cid)
                to_delete.append(cid)
        for cid in to_delete:
            del self.active_claims[cid]
        return expired

    def get_claims_for_resource(self, resource_id: str) -> List[ResourceClaim]:
        norm_res = resource_id.replace("\\", "/").strip()
        return [c for c in self.active_claims.values() if c.resource_id == norm_res and c.is_active and not c.is_expired()]
