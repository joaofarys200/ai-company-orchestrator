"""
JARVIS OS — Phase 77: Autonomous Evidence Verification & Engineering Claims Governance
Module: persistence.py
Durable atomic storage, crash recovery, and verification audit ledger.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from .models import (
    EngineeringClaim,
    EvidenceArtifact,
    VerificationResult,
    VerificationStatus,
)
from .registry import EvidenceClaimsRegistry


class EvidenceGovernanceStore:
    """
    Atomic filesystem store for claims, evidence artifacts, and verification ledgers.
    Supports crash recovery and state reconciliation across restarts.
    """

    def __init__(self, base_dir: str = ".jarvis/evidence_governance"):
        self.base_dir = Path(base_dir)
        self.artifacts_dir = self.base_dir / "artifacts"
        self.claims_file = self.base_dir / "claims.json"
        self.audit_ledger_file = self.base_dir / "audit_ledger.json"

        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def save_claim(self, claim: EngineeringClaim) -> None:
        """Atomically persist a single claim."""
        claims = self.load_all_claims()
        claims[claim.claim_id] = claim.to_dict()

        temp_path = self.base_dir / "claims.tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(claims, f, indent=2)
        os.replace(temp_path, self.claims_file)

    def save_artifact(self, artifact: EvidenceArtifact) -> Path:
        """Atomically persist an evidence artifact."""
        target_path = self.artifacts_dir / f"{artifact.artifact_id}.json"
        temp_path = self.artifacts_dir / f"{artifact.artifact_id}.tmp"

        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(artifact.to_dict(), f, indent=2)
        os.replace(temp_path, target_path)
        return target_path

    def load_all_claims(self) -> Dict[str, Dict]:
        """Load raw claim dictionaries from disk."""
        if not self.claims_file.exists():
            return {}
        try:
            with open(self.claims_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def record_audit_entry(self, entry: Dict) -> None:
        """Append an entry to the audit ledger."""
        ledger = []
        if self.audit_ledger_file.exists():
            try:
                with open(self.audit_ledger_file, "r", encoding="utf-8") as f:
                    ledger = json.load(f)
            except Exception:
                ledger = []
        ledger.append(entry)

        temp_path = self.base_dir / "audit_ledger.tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(ledger, f, indent=2)
        os.replace(temp_path, self.audit_ledger_file)

    def reconcile_and_recover(self, registry: EvidenceClaimsRegistry) -> int:
        """
        Loads all persisted artifacts and claims on startup, reconciling any incomplete states.
        Returns the count of recovered claims.
        """
        # 1. Load artifacts
        for f in self.artifacts_dir.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                    art = EvidenceArtifact.from_dict(data)
                    registry.register_artifact(art)
            except Exception:
                continue

        # 2. Load claims
        raw_claims = self.load_all_claims()
        recovered_count = 0
        for c_dict in raw_claims.values():
            try:
                claim = EngineeringClaim.from_dict(c_dict)
                registry.register_claim(claim)
                recovered_count += 1
            except Exception:
                continue

        return recovered_count
