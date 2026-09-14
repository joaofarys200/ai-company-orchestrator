"""
JARVIS OS — Phase 43: Memory Transfer & False Transfer Detection Tests
"""

import pytest
from agents.experience_memory.models import (
    ExperienceApplicabilityRating,
    ExperienceRecord,
    ExperienceReuseOutcome,
    ExperienceSignature,
    MemoryBenefitCategory,
    MemoryInfluenceType,
    NoveltyLevel,
)
from agents.experience_memory.applicability import ExperienceApplicabilityValidator
from agents.experience_memory.generalization import MemoryHarmDetector


def test_cross_mission_reuse_outcome_structure():
    """Verify ExperienceReuseOutcome records full lineage from source to target mission."""
    outcome = ExperienceReuseOutcome(
        reuse_id="reuse_p43_01",
        source_mission_id="m_auth_jwt_service",
        source_experience_id="exp_jwt_refresh_01",
        target_mission_id="m_payment_gateway_api",
        novelty_level=NoveltyLevel.RELATED,
        relevance_score=0.94,
        applicability_rating=ExperienceApplicabilityRating.RELEVANT.value,
        influence_type=MemoryInfluenceType.PLANNING_HINT.value,
        outcome_summary="Applied refresh token handling pattern safely.",
        benefit_category=MemoryBenefitCategory.BENEFICIAL,
        is_false_transfer=False,
    )
    
    assert outcome.source_mission_id == "m_auth_jwt_service"
    assert outcome.target_mission_id == "m_payment_gateway_api"
    assert outcome.is_false_transfer is False
    assert outcome.benefit_category == MemoryBenefitCategory.BENEFICIAL


def test_false_memory_transfer_flagging():
    """A false transfer occurs when incompatible/stale/harmful memory influenced a decision."""
    exp = ExperienceRecord(
        experience_id="exp_react_hook_01",
        mission_id="m_react_spa",
        cycle_id="c_01",
        intent_signature=ExperienceSignature(intent_category="FRONTEND"),
        mission_context={},
        decision="REPAIR",
        policy_version="43.0.0",
        observation={},
        outcome="failure",
        root_cause="INCOMPATIBLE_STACK",
        severity="HIGH",
        prediction={},
        actual_result={},
        adaptation={},
        confidence=0.88,
        applicability="INAPPLICABLE",
    )
    
    # Evaluate harm when decision correctness degraded
    outcome = MemoryHarmDetector.evaluate_harm(
        experience=exp,
        target_mission_id="m_django_templates",
        novelty_level=NoveltyLevel.NOVEL,
        influence_type=MemoryInfluenceType.REPAIR_HINT,
        baseline_success=True,
        actual_success=False,
        baseline_repairs=1,
        actual_repairs=3,
        baseline_replans=0,
        actual_replans=1,
        resolution_seconds_delta=15.0,
        decision_correctness_degraded=True,
    )
    
    assert outcome.is_false_transfer is True
    assert outcome.benefit_category == MemoryBenefitCategory.HARMFUL
    assert outcome.root_cause_if_harmful == "MEMORY_INDUCED_DECISION_ERROR"
    assert outcome.corrective_action == "MARK_MISLEADING"


def test_matched_vs_mismatched_rejection():
    """ExperienceApplicabilityValidator must accept matched memory and reject mismatched technology/intent."""
    current_arch = {
        "intent_category": "AUTH_OAUTH2",
        "technology": ["fastapi", "python"],
        "architecture": "modular_service",
        "policy_version": "43.0.0",
        "security_clearance": "standard",
    }
    
    # 1. Highly relevant experience
    relevant_exp = ExperienceRecord(
        experience_id="exp_oauth_01",
        mission_id="m_auth_01",
        cycle_id="c_01",
        intent_signature=ExperienceSignature(
            intent_category="SECURITY",
            technology=("fastapi", "python"),
        ),
        mission_context={"architecture": "modular_service"},
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
    
    rating_rel, inf_rel, reasons_rel, note_rel = ExperienceApplicabilityValidator.validate(
        experience=relevant_exp,
        current_mission_state={},
        current_architecture=current_arch,
        current_policy_version="43.0.0",
    )
    assert rating_rel in (ExperienceApplicabilityRating.RELEVANT, ExperienceApplicabilityRating.POSSIBLY_RELEVANT)
    
    # 2. Technology mismatched experience (Django vs FastAPI)
    mismatched_tech_exp = ExperienceRecord(
        experience_id="exp_django_01",
        mission_id="m_django_01",
        cycle_id="c_01",
        intent_signature=ExperienceSignature(
            intent_category="SECURITY",
            technology=("django", "jinja2"),
        ),
        mission_context={"architecture": "monolith"},
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
    
    rating_tech, inf_tech, reasons_tech, note_tech = ExperienceApplicabilityValidator.validate(
        experience=mismatched_tech_exp,
        current_mission_state={},
        current_architecture=current_arch,
        current_policy_version="43.0.0",
    )
    assert rating_tech in (ExperienceApplicabilityRating.INAPPLICABLE, ExperienceApplicabilityRating.STALE)
