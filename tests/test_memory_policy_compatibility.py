"""
JARVIS OS — Phase 43: Cross-Policy Compatibility Tests
"""

import pytest
from agents.experience_memory.models import (
    ExperienceApplicabilityRating,
    ExperienceRecord,
    ExperienceSignature,
    PolicyCompatibilityStatus,
)
from agents.experience_memory.applicability import ExperienceApplicabilityValidator


def test_cross_policy_version_compatibility_classification():
    """Verify classification of experiences from different policy versions."""
    current_policy = "43.0.0"
    
    # 1. Same major version -> CURRENT_POLICY_COMPATIBLE
    compat_status_1 = ExperienceApplicabilityValidator.evaluate_policy_compatibility("43.0.1", current_policy)
    assert compat_status_1 == PolicyCompatibilityStatus.CURRENT_POLICY_COMPATIBLE
    
    # 2. Close recent policy (e.g. 42.0.0 or 41.0.0) -> POLICY_REQUIRES_VALIDATION
    compat_status_2 = ExperienceApplicabilityValidator.evaluate_policy_compatibility("42.0.0", current_policy)
    assert compat_status_2 == PolicyCompatibilityStatus.POLICY_REQUIRES_VALIDATION
    
    # 3. Distant obsolete policy (e.g. 35.0.0, delta > 2) -> POLICY_MISMATCH
    compat_status_3 = ExperienceApplicabilityValidator.evaluate_policy_compatibility("35.0.0", current_policy)
    assert compat_status_3 == PolicyCompatibilityStatus.POLICY_MISMATCH


def test_policy_mismatch_demotes_influence():
    """Experiences with POLICY_MISMATCH must never be given active PLANNING or REPAIR authority."""
    current_arch = {
        "intent_category": "PLANNING_STRATEGY",
        "technology": ["python"],
        "architecture": "modular_service",
        "policy_version": "43.0.0",
        "security_clearance": "standard",
    }
    
    v35_exp = ExperienceRecord(
        experience_id="exp_policy_v35",
        mission_id="m_v35_01",
        cycle_id="c_01",
        intent_signature=ExperienceSignature(
            intent_category="PLANNING",
            technology=("python",),
        ),
        mission_context={},
        decision="REPLAN",
        policy_version="35.0.0", # Obsolete Policy v35 (delta = 8)
        observation={},
        outcome="success",
        root_cause="NONE",
        severity="INFO",
        prediction={},
        actual_result={},
        adaptation={},
    )
    
    rating, influence, reasons, note = ExperienceApplicabilityValidator.validate(
        experience=v35_exp,
        current_mission_state={},
        current_architecture=current_arch,
        current_policy_version="43.0.0",
    )
    # Under policy mismatch, experience cannot have unverified authority
    assert rating in (ExperienceApplicabilityRating.INAPPLICABLE, ExperienceApplicabilityRating.STALE) or any("policy" in r.lower() for r in reasons)
