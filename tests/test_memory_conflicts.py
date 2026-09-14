"""
JARVIS OS — Phase 43: Experience Conflict Resolution & Non-Recency Tests
"""

import pytest
from agents.experience_memory.models import (
    ExperienceApplicabilityRating,
    ExperienceRecord,
    ExperienceSignature,
    MemoryInfluenceType,
    RelevantExperience,
)
from agents.experience_memory.conflict import ConflictResolver


def test_recency_is_not_sole_authority():
    """An older experience with strong evidence and higher confidence prevails over a newer flawed one."""
    # Exp A: Older (created_at 100), higher evidence count & confidence
    exp_a = ExperienceRecord(
        experience_id="exp_proven_repair",
        mission_id="m_01",
        cycle_id="c_01",
        intent_signature=ExperienceSignature(
            intent_category="CODE_REPAIR",
            observed_failure="SYNTAX_ERROR",
            decision="REPAIR",
        ),
        mission_context={"architecture": "modular"},
        decision="REPAIR",
        policy_version="43.0.0",
        observation={},
        outcome="success",
        root_cause="NONE",
        severity="INFO",
        prediction={},
        actual_result={"tests_passed": True},
        adaptation={},
        evidence_refs=("EVD_01", "EVD_02", "EVD_03"),
        confidence=0.98,
        created_at=100.0, # Older
        applicability="RELEVANT",
    )
    
    # Exp B: Newer (created_at 500), but fewer evidence refs
    exp_b = ExperienceRecord(
        experience_id="exp_flawed_replan",
        mission_id="m_02",
        cycle_id="c_01",
        intent_signature=ExperienceSignature(
            intent_category="CODE_REPAIR",
            observed_failure="SYNTAX_ERROR",
            decision="REPLAN",
        ),
        mission_context={"architecture": "modular"},
        decision="REPLAN",
        policy_version="43.0.0",
        observation={},
        outcome="failure",
        root_cause="BAD_DECISION",
        severity="HIGH",
        prediction={},
        actual_result={"tests_passed": False},
        adaptation={},
        evidence_refs=(),
        confidence=0.60,
        created_at=500.0, # Newer!
        applicability="RELEVANT",
    )
    
    rel_a = RelevantExperience(
        experience=exp_a,
        relevance_score=0.95,
        applicability=ExperienceApplicabilityRating.RELEVANT,
        why_relevant="same error",
        influence_type=MemoryInfluenceType.REPAIR_HINT,
    )
    rel_b = RelevantExperience(
        experience=exp_b,
        relevance_score=0.90,
        applicability=ExperienceApplicabilityRating.RELEVANT,
        why_relevant="same error",
        influence_type=MemoryInfluenceType.PLANNING_HINT,
    )
    
    conflicts = ConflictResolver.detect_conflicts([rel_a, rel_b])
    assert len(conflicts) == 1
    
    winner_id, influence = ConflictResolver.resolve_conflict(conflicts[0], exp_a, exp_b)
    # The older proven experience with evidence must win over mere recency
    assert winner_id == "exp_proven_repair"
    assert influence == MemoryInfluenceType.DIAGNOSTIC


def test_ambiguous_conflict_demoted_to_context_only():
    """When two contradictory experiences have equivalent evidence, result is CONFLICT_UNRESOLVED and CONTEXT_ONLY."""
    # Experience A: repair succeeds in context
    exp_a = ExperienceRecord(
        experience_id="exp_ambig_a",
        mission_id="m_a",
        cycle_id="c_01",
        intent_signature=ExperienceSignature(
            intent_category="DEPENDENCY",
            observed_failure="IMPORT_ERROR",
            decision="REPAIR",
        ),
        mission_context={},
        decision="REPAIR",
        policy_version="43.0.0",
        observation={},
        outcome="success",
        root_cause="NONE",
        severity="INFO",
        prediction={},
        actual_result={},
        adaptation={},
        evidence_refs=("EVD_A",),
        confidence=0.80,
        created_at=200.0,
        applicability="RELEVANT",
    )
    
    # Experience B: replan succeeds in context
    exp_b = ExperienceRecord(
        experience_id="exp_ambig_b",
        mission_id="m_b",
        cycle_id="c_01",
        intent_signature=ExperienceSignature(
            intent_category="DEPENDENCY",
            observed_failure="IMPORT_ERROR",
            decision="REPLAN",
        ),
        mission_context={},
        decision="REPLAN",
        policy_version="43.0.0",
        observation={},
        outcome="success",
        root_cause="NONE",
        severity="INFO",
        prediction={},
        actual_result={},
        adaptation={},
        evidence_refs=("EVD_B",),
        confidence=0.80,
        created_at=205.0, # Sightly newer
        applicability="RELEVANT",
    )
    
    rel_a = RelevantExperience(
        experience=exp_a,
        relevance_score=0.85,
        applicability=ExperienceApplicabilityRating.RELEVANT,
        why_relevant="same error",
        influence_type=MemoryInfluenceType.REPAIR_HINT,
    )
    rel_b = RelevantExperience(
        experience=exp_b,
        relevance_score=0.85,
        applicability=ExperienceApplicabilityRating.RELEVANT,
        why_relevant="same error",
        influence_type=MemoryInfluenceType.PLANNING_HINT,
    )
    
    conflicts = ConflictResolver.detect_conflicts([rel_a, rel_b])
    assert len(conflicts) == 1
    
    status, influence = ConflictResolver.resolve_conflict(conflicts[0], exp_a, exp_b)
    assert status == "CONFLICT_UNRESOLVED"
    assert influence == MemoryInfluenceType.CONTEXT_ONLY
