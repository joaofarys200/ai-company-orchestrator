"""
JARVIS OS — Phase 43: Architecture Drift & Compatibility Tests
"""

import pytest
from agents.experience_memory.models import (
    ExperienceApplicabilityRating,
    ExperienceRecord,
    ExperienceSignature,
)
from agents.experience_memory.applicability import ExperienceApplicabilityValidator


def test_architecture_drift_monolith_to_microservices():
    """Experiences created under monolith architecture must not be naively applied to microservices."""
    current_arch = {
        "intent_category": "TRANSACTION_SERVICE",
        "technology": ["python", "fastapi"],
        "architecture": "microservices",
        "policy_version": "43.0.0",
        "security_clearance": "standard",
    }
    
    monolith_exp = ExperienceRecord(
        experience_id="exp_monolith_db_tx",
        mission_id="m_monolith_01",
        cycle_id="c_01",
        intent_signature=ExperienceSignature(
            intent_category="BACKEND",
            technology=("python", "fastapi"),
        ),
        mission_context={"architecture": "monolith", "db_shared": True},
        decision="CONTINUE",
        policy_version="43.0.0",
        observation={},
        outcome="success",
        root_cause="NONE",
        severity="INFO",
        prediction={},
        actual_result={},
        adaptation={},
    )
    
    rating, influence, reasons, note = ExperienceApplicabilityValidator.validate(
        experience=monolith_exp,
        current_mission_state={},
        current_architecture=current_arch,
        current_policy_version="43.0.0",
    )
    assert rating in (ExperienceApplicabilityRating.INAPPLICABLE, ExperienceApplicabilityRating.STALE)
    combined = " ".join(reasons) + " " + note
    assert "architecture" in combined.lower() or "monolith" in combined.lower() or "microservices" in combined.lower()


def test_react_architecture_evolution_drift():
    """React Class Component / Legacy architecture experiences marked STALE in Modern React Hooks."""
    current_arch = {
        "intent_category": "FRONTEND_STATE",
        "technology": ["react", "typescript"],
        "architecture": "react_functional_hooks",
        "policy_version": "43.0.0",
        "security_clearance": "standard",
    }
    
    legacy_react_exp = ExperienceRecord(
        experience_id="exp_react_class_01",
        mission_id="m_legacy_react",
        cycle_id="c_01",
        intent_signature=ExperienceSignature(
            intent_category="BROWSER",
            technology=("react", "typescript"),
        ),
        mission_context={"architecture": "react_class_components_v16"},
        decision="CONTINUE",
        policy_version="38.0.0",
        observation={},
        outcome="success",
        root_cause="NONE",
        severity="INFO",
        prediction={},
        actual_result={},
        adaptation={},
    )
    
    rating, influence, reasons, note = ExperienceApplicabilityValidator.validate(
        experience=legacy_react_exp,
        current_mission_state={},
        current_architecture=current_arch,
        current_policy_version="43.0.0",
    )
    assert rating in (ExperienceApplicabilityRating.STALE, ExperienceApplicabilityRating.INAPPLICABLE)
