"""
JARVIS OS — Phase 63: Cross-Project Engineering Learning & Verification Transfer
Module: policy.py
Policy profiles and rule configurations governing cross-project transfer boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from .models import TransferPolicyName


@dataclass
class PolicyProfile:
    name: TransferPolicyName
    min_retrieval_score: float
    min_transfer_confidence: float
    max_transfers_per_cycle: int
    require_human_review_on_adapter: bool
    allow_cross_language_hypotheses: bool
    max_validation_timeout_ms: int
    reject_on_any_harm_history: bool


class PolicyRegistry:
    """Manages policy configurations and retrieval."""

    PROFILES: Dict[TransferPolicyName, PolicyProfile] = {
        TransferPolicyName.CONSERVATIVE: PolicyProfile(
            name=TransferPolicyName.CONSERVATIVE,
            min_retrieval_score=0.60,
            min_transfer_confidence=0.80,
            max_transfers_per_cycle=2,
            require_human_review_on_adapter=True,
            allow_cross_language_hypotheses=False,
            max_validation_timeout_ms=5000,
            reject_on_any_harm_history=True,
        ),
        TransferPolicyName.STANDARD: PolicyProfile(
            name=TransferPolicyName.STANDARD,
            min_retrieval_score=0.35,
            min_transfer_confidence=0.55,
            max_transfers_per_cycle=5,
            require_human_review_on_adapter=False,
            allow_cross_language_hypotheses=True,
            max_validation_timeout_ms=10000,
            reject_on_any_harm_history=False,
        ),
        TransferPolicyName.STRICT: PolicyProfile(
            name=TransferPolicyName.STRICT,
            min_retrieval_score=0.50,
            min_transfer_confidence=0.75,
            max_transfers_per_cycle=3,
            require_human_review_on_adapter=True,
            allow_cross_language_hypotheses=True,
            max_validation_timeout_ms=8000,
            reject_on_any_harm_history=True,
        ),
        TransferPolicyName.AGGRESSIVE: PolicyProfile(
            name=TransferPolicyName.AGGRESSIVE,
            min_retrieval_score=0.20,
            min_transfer_confidence=0.40,
            max_transfers_per_cycle=10,
            require_human_review_on_adapter=False,
            allow_cross_language_hypotheses=True,
            max_validation_timeout_ms=20000,
            reject_on_any_harm_history=False,
        ),
        TransferPolicyName.SECURITY_FIRST: PolicyProfile(
            name=TransferPolicyName.SECURITY_FIRST,
            min_retrieval_score=0.65,
            min_transfer_confidence=0.85,
            max_transfers_per_cycle=1,
            require_human_review_on_adapter=True,
            allow_cross_language_hypotheses=False,
            max_validation_timeout_ms=5000,
            reject_on_any_harm_history=True,
        ),
        TransferPolicyName.ECONOMIC: PolicyProfile(
            name=TransferPolicyName.ECONOMIC,
            min_retrieval_score=0.45,
            min_transfer_confidence=0.65,
            max_transfers_per_cycle=2,
            require_human_review_on_adapter=False,
            allow_cross_language_hypotheses=True,
            max_validation_timeout_ms=2000,
            reject_on_any_harm_history=True,
        ),
    }

    @classmethod
    def get_policy(cls, name: TransferPolicyName | str) -> PolicyProfile:
        if isinstance(name, str):
            try:
                name = TransferPolicyName(name.upper())
            except ValueError:
                name = TransferPolicyName.STANDARD
        return cls.PROFILES.get(name, cls.PROFILES[TransferPolicyName.STANDARD])
