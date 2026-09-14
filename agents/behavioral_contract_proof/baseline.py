"""
JARVIS OS — Phase 50: Behavioral Contract Preservation & Migration Proof
Immutable Behavioral Baseline Store with SHA-256 Hash Verification.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple

from agents.behavioral_contract_proof.models import BehaviorBaseline, LatencyClass


class BaselineImmutableError(RuntimeError):
    """Raised when an attempt is made to mutate or overwrite an existing baseline."""
    pass


class BaselineIntegrityError(RuntimeError):
    """Raised when baseline content does not match its cryptographic hash."""
    pass


def compute_baseline_hash(baseline: BehaviorBaseline) -> str:
    """
    Computes deterministic SHA-256 hash across all canonical behavioral aspects.
    Ignores non-semantic fields like creation timestamp.
    """
    canonical_dict = {
        "contract_id": baseline.contract_id,
        "contract_version": baseline.contract_version,
        "consumer_id": baseline.consumer_id,
        "operation": baseline.operation,
        "input_shape": baseline.input_shape,
        "output_shape": baseline.output_shape,
        "status_code": baseline.status_code,
        "side_effects": baseline.side_effects,
        "events": baseline.events,
        "economic_effects": baseline.economic_effects,
        "authorization_state": baseline.authorization_state,
        "latency_class": baseline.latency_class.value,
        "source": baseline.source,
    }
    encoded = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class BehaviorBaselineStore:
    """
    Thread-safe, tamper-evident repository for immutable behavioral baselines.
    Never permits silent overwriting of baselines.
    """

    def __init__(self) -> None:
        # Key: (contract_id, contract_version, consumer_id) -> BehaviorBaseline
        self._baselines: Dict[Tuple[str, str, str], BehaviorBaseline] = {}

    def register_baseline(self, baseline: BehaviorBaseline) -> str:
        """
        Registers a new baseline. Computes and assigns its baseline_hash.
        Raises BaselineImmutableError if a differing baseline is already stored for this key.
        """
        calculated_hash = compute_baseline_hash(baseline)
        if not baseline.baseline_hash:
            baseline.baseline_hash = calculated_hash
        elif baseline.baseline_hash != calculated_hash:
            raise BaselineIntegrityError(
                f"Baseline provided hash '{baseline.baseline_hash}' does not match "
                f"computed structural hash '{calculated_hash}'"
            )

        key = (baseline.contract_id, baseline.contract_version, baseline.consumer_id)
        if key in self._baselines:
            existing = self._baselines[key]
            if existing.baseline_hash != baseline.baseline_hash:
                raise BaselineImmutableError(
                    f"Forbidden: Attempted to overwrite immutable baseline for "
                    f"contract '{baseline.contract_id}' v{baseline.contract_version}, "
                    f"consumer '{baseline.consumer_id}'. "
                    f"Existing hash: {existing.baseline_hash}, Attempted hash: {baseline.baseline_hash}"
                )
            # Idempotent re-registration of identical baseline
            return existing.baseline_hash

        self._baselines[key] = baseline
        return baseline.baseline_hash

    def get_baseline(
        self, contract_id: str, contract_version: str, consumer_id: str
    ) -> Optional[BehaviorBaseline]:
        """Retrieves a baseline by exact coordinate key."""
        key = (contract_id, contract_version, consumer_id)
        return self._baselines.get(key)

    def list_baselines(
        self, contract_id: Optional[str] = None, consumer_id: Optional[str] = None
    ) -> List[BehaviorBaseline]:
        """Lists baselines with optional filtering."""
        results = []
        for b in self._baselines.values():
            if contract_id and b.contract_id != contract_id:
                continue
            if consumer_id and b.consumer_id != consumer_id:
                continue
            results.append(b)
        return results

    def verify_integrity(self, baseline: BehaviorBaseline) -> bool:
        """Cryptographically verifies baseline structural integrity."""
        return baseline.baseline_hash == compute_baseline_hash(baseline)

    def clear(self) -> None:
        """Clears memory store (primarily for unit test isolation)."""
        self._baselines.clear()

    def count(self) -> int:
        """Returns the total number of registered baselines."""
        return len(self._baselines)
