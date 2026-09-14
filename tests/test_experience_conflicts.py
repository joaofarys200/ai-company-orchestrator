"""
JARVIS OS — Phase 42: Conflicting Experience Detection Tests
"""

from agents.experience_memory.conflict import ConflictResolver
from agents.experience_memory.models import (
    ExperienceApplicabilityRating,
    ExperienceRecord,
    ExperienceSignature,
    MemoryInfluenceType,
    RelevantExperience,
)


def test_conflict_resolver_detects_contradiction():
    sig1 = ExperienceSignature(
        intent_category="CODE_REPAIR",
        observed_failure="MISSING_DEPENDENCY",
        decision="REPAIR",
        technology=("python",),
    )
    rec1 = ExperienceRecord(
        experience_id="exp_conf_01",
        mission_id="m_01",
        cycle_id="c_1",
        intent_signature=sig1,
        mission_context={},
        decision="REPAIR",
        policy_version="40.1.0",
        observation={},
        outcome="repaired",
        root_cause="NONE",
        severity="MEDIUM",
        prediction={},
        actual_result={},
        adaptation={},
        evidence_refs=("EVD_01",),
        confidence=0.85,
    )

    sig2 = ExperienceSignature(
        intent_category="CODE_REPAIR",
        observed_failure="MISSING_DEPENDENCY",
        decision="REPLAN",
        technology=("python",),
    )
    rec2 = ExperienceRecord(
        experience_id="exp_conf_02",
        mission_id="m_02",
        cycle_id="c_1",
        intent_signature=sig2,
        mission_context={},
        decision="REPLAN",
        policy_version="41.0.0",
        observation={},
        outcome="replanned",
        root_cause="NONE",
        severity="HIGH",
        prediction={},
        actual_result={},
        adaptation={},
        evidence_refs=("EVD_02", "EVD_03"),
        confidence=0.92,
    )

    rel1 = RelevantExperience(
        experience=rec1,
        relevance_score=0.85,
        applicability=ExperienceApplicabilityRating.RELEVANT,
        why_relevant="same failure",
        influence_type=MemoryInfluenceType.REPAIR_HINT,
    )
    rel2 = RelevantExperience(
        experience=rec2,
        relevance_score=0.88,
        applicability=ExperienceApplicabilityRating.RELEVANT,
        why_relevant="same failure",
        influence_type=MemoryInfluenceType.PLANNING_HINT,
    )

    conflicts = ConflictResolver.detect_conflicts([rel1, rel2])
    assert len(conflicts) == 1
    c = conflicts[0]
    assert c.primary_experience_id == "exp_conf_01"
    assert c.conflicting_experience_id == "exp_conf_02"
    assert "recommends REPAIR" in c.divergence_summary
    assert "recommends REPLAN" in c.divergence_summary
    assert c.policy_version_delta == "40.1.0 vs 41.0.0"
