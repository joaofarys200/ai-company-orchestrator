"""
JARVIS OS — Phase 43: Memory Harm & Misleading Experience Investigation Tests
"""

import pytest
from agents.experience_memory.models import (
    ExperienceApplicabilityRating,
    ExperienceRecord,
    ExperienceReuseOutcome,
    ExperienceSignature,
    HumanCurationAction,
    MemoryBenefitCategory,
    MemoryInfluenceType,
    NoveltyLevel,
)
from agents.experience_memory.generalization import MemoryHarmDetector
from agents.experience_memory.storage import ExperienceStorage


def test_memory_harm_categorization_and_investigation():
    """Verify classification of reuse into BENEFICIAL, NEUTRAL, HARMFUL with root cause."""
    exp = ExperienceRecord(
        experience_id="exp_01",
        mission_id="m_src_01",
        cycle_id="c_01",
        intent_signature=ExperienceSignature(intent_category="BACKEND"),
        mission_context={},
        decision="CONTINUE",
        policy_version="43.0.0",
        observation={},
        outcome="success",
        root_cause="NONE",
        severity="INFO",
        prediction={},
        actual_result={},
        adaptation={},
        confidence=0.92,
        applicability="RELEVANT",
    )
    
    # Case 1: Beneficial
    outcome_ben = MemoryHarmDetector.evaluate_harm(
        experience=exp,
        target_mission_id="m_tgt_01",
        novelty_level=NoveltyLevel.FAMILIAR,
        influence_type=MemoryInfluenceType.PLANNING_HINT,
        baseline_success=False,
        actual_success=True,
        baseline_repairs=2,
        actual_repairs=0,
        baseline_replans=1,
        actual_replans=0,
        resolution_seconds_delta=-5.0,
    )
    assert outcome_ben.benefit_category == MemoryBenefitCategory.BENEFICIAL
    assert outcome_ben.is_false_transfer is False
    
    # Case 2: Harmful (caused unnecessary repair and delayed execution)
    outcome_harm = MemoryHarmDetector.evaluate_harm(
        experience=exp,
        target_mission_id="m_tgt_orm",
        novelty_level=NoveltyLevel.NOVEL,
        influence_type=MemoryInfluenceType.REPAIR_HINT,
        baseline_success=True,
        actual_success=False,
        baseline_repairs=0,
        actual_repairs=3,
        baseline_replans=0,
        actual_replans=2,
        resolution_seconds_delta=22.0,
        decision_correctness_degraded=True,
    )
    assert outcome_harm.benefit_category == MemoryBenefitCategory.HARMFUL
    assert outcome_harm.is_false_transfer is True
    assert outcome_harm.corrective_action == "MARK_MISLEADING"


def test_history_immutability_on_harmful_experience():
    """Harmful experiences must never be deleted from historical ledger; they must be curated."""
    storage = ExperienceStorage()
    
    rec = ExperienceRecord(
        experience_id="exp_harm_record_01",
        mission_id="m_harm_01",
        cycle_id="c_01",
        intent_signature=ExperienceSignature(intent_category="MIGRATION"),
        mission_context={},
        decision="REPAIR",
        policy_version="43.0.0",
        observation={},
        outcome="failure",
        root_cause="BAD_HINT",
        severity="HIGH",
        prediction={},
        actual_result={},
        adaptation={},
    )
    storage.add_experience(rec)
    
    # Verify curation marks record as MISLEADING without deleting the original record
    updated = storage.curate_experience("exp_harm_record_01", HumanCurationAction.MARK_MISLEADING, "Operator: misleading repair pattern")
    assert updated.curation_status == HumanCurationAction.MARK_MISLEADING.value
    
    # The record remains in storage, maintaining full audit trail
    stored = storage.get_experience("exp_harm_record_01")
    assert stored is not None
    assert stored.curation_status == HumanCurationAction.MARK_MISLEADING.value
