"""
JARVIS OS — Phase 42: Experience Applicability Validation Tests
"""

from agents.experience_memory.applicability import ExperienceApplicabilityValidator
from agents.experience_memory.models import (
    ExperienceApplicabilityRating,
    ExperienceRecord,
    ExperienceSignature,
    MemoryInfluenceType,
    TemporalValidity,
)


def test_applicability_validator_fully_compatible():
    sig = ExperienceSignature(
        intent_category="CODE_REPAIR",
        technology=("vanilla_ts",),
        affected_architecture=("frontend",),
        observed_failure="SYNTAX_ERROR",
        decision="REPAIR",
    )
    rec = ExperienceRecord(
        experience_id="exp_app_01",
        mission_id="m_01",
        cycle_id="c_1",
        intent_signature=sig,
        mission_context={},
        decision="REPAIR",
        policy_version="41.0.0",
        observation={},
        outcome="success",
        root_cause="NONE",
        severity="INFO",
        prediction={},
        actual_result={},
        adaptation={},
        tags=("repair",),
    )

    rating, influence, reasons, summary = ExperienceApplicabilityValidator.validate_applicability(
        experience=rec,
        current_mission_state={"current_stage": "EXECUTION", "missing_dependencies": []},
        current_architecture={"technology": ["vanilla_ts"], "components": ["frontend"]},
        current_policy_version="41.0.0",
        current_security_level="STRICT",
    )

    assert rating == ExperienceApplicabilityRating.RELEVANT
    assert influence == MemoryInfluenceType.REPAIR_HINT
    assert len(reasons) == 0
    assert "Fully applicable" in summary


def test_applicability_validator_tech_mismatch():
    sig = ExperienceSignature(
        intent_category="CODE_REPAIR",
        technology=("rust", "cargo"),
        affected_architecture=("backend",),
    )
    rec = ExperienceRecord(
        experience_id="exp_app_02",
        mission_id="m_02",
        cycle_id="c_1",
        intent_signature=sig,
        mission_context={},
        decision="REPAIR",
        policy_version="41.0.0",
        observation={},
        outcome="success",
        root_cause="NONE",
        severity="INFO",
        prediction={},
        actual_result={},
        adaptation={},
    )

    rating, influence, reasons, summary = ExperienceApplicabilityValidator.validate_applicability(
        experience=rec,
        current_mission_state={"current_stage": "EXECUTION"},
        current_architecture={"technology": ["vanilla_ts", "python"], "components": ["frontend"]},
        current_policy_version="41.0.0",
    )

    assert rating == ExperienceApplicabilityRating.INAPPLICABLE
    assert influence == MemoryInfluenceType.NONE
    assert any("Technology mismatch" in r for r in reasons)


def test_applicability_validator_stale_rejection():
    sig = ExperienceSignature(intent_category="FINANCIAL_LEDGER")
    rec = ExperienceRecord(
        experience_id="exp_app_03",
        mission_id="m_03",
        cycle_id="c_1",
        intent_signature=sig,
        mission_context={},
        decision="CONTINUE",
        policy_version="38.0.0",
        observation={},
        outcome="success",
        root_cause="NONE",
        severity="INFO",
        prediction={},
        actual_result={},
        adaptation={},
        temporal_validity=TemporalValidity.STALE,
    )

    rating, influence, reasons, summary = ExperienceApplicabilityValidator.validate_applicability(
        experience=rec,
        current_mission_state={},
        current_architecture={"technology": ["vanilla_ts"]},
        current_policy_version="41.0.0",
    )

    assert rating == ExperienceApplicabilityRating.INAPPLICABLE
    assert influence == MemoryInfluenceType.NONE
    assert any("STALE" in r for r in reasons)
