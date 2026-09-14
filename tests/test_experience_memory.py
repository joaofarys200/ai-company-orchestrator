"""
JARVIS OS — Phase 42: Experience Memory Storage & Immutability Tests
"""

import pytest
import time

from agents.experience_memory.models import (
    ExperienceCorrection,
    ExperienceRecord,
    ExperienceSignature,
    ExperienceSourceType,
    HumanCurationAction,
    TemporalValidity,
)
from agents.experience_memory.storage import ExperienceStorage


def test_experience_storage_insertion_and_hash():
    storage = ExperienceStorage()
    sig = ExperienceSignature(
        intent_category="FINANCIAL_LEDGER",
        requirement_types=("USER_REQUIREMENT",),
        technology=("vanilla_ts", "local_storage"),
    )
    rec = ExperienceRecord(
        experience_id="exp_01",
        mission_id="m_01",
        cycle_id="c_01",
        intent_signature=sig,
        mission_context={"app": "despesas"},
        decision="CONTINUE",
        policy_version="41.0.0",
        observation={"status": "clean"},
        outcome="success",
        root_cause="NONE",
        severity="INFO",
        prediction={},
        actual_result={},
        adaptation={},
        tags=("financial", "vanilla_ts"),
    )

    stored = storage.add_experience(rec)
    assert stored.experience_id == "exp_01"
    assert stored.source_hash != ""
    assert storage.get_experience("exp_01") is not None


def test_experience_immutability_rejection():
    storage = ExperienceStorage()
    sig = ExperienceSignature(intent_category="FINANCIAL_LEDGER")
    rec = ExperienceRecord(
        experience_id="exp_02",
        mission_id="m_02",
        cycle_id="c_01",
        intent_signature=sig,
        mission_context={},
        decision="CONTINUE",
        policy_version="41.0.0",
        observation={},
        outcome="success",
        root_cause="NONE",
        severity="INFO",
        prediction={},
        actual_result={},
        adaptation={},
    )
    storage.add_experience(rec)

    # Attempting to overwrite directly must be rejected
    with pytest.raises(ValueError, match="immutable"):
        storage.add_experience(rec)


def test_experience_correction_linkage():
    storage = ExperienceStorage()
    sig = ExperienceSignature(intent_category="CODE_REPAIR")
    rec = ExperienceRecord(
        experience_id="exp_03",
        mission_id="m_03",
        cycle_id="c_01",
        intent_signature=sig,
        mission_context={},
        decision="REPAIR",
        policy_version="41.0.0",
        observation={},
        outcome="partial",
        root_cause="OBSERVATION_GAP",
        severity="MEDIUM",
        prediction={},
        actual_result={},
        adaptation={},
    )
    storage.add_experience(rec)

    correction = ExperienceCorrection(
        correction_id="corr_01",
        original_experience_id="exp_03",
        corrected_fields={"root_cause": "STALE_STATE"},
        reason="Análise posterior revelou estado desatualizado no step 8",
        curator_id="senior_operator",
    )
    storage.add_correction(correction)
    assert len(storage._corrections) == 1
    assert storage._corrections[0].correction_id == "corr_01"


def test_experience_human_curation_and_pin():
    storage = ExperienceStorage()
    sig = ExperienceSignature(intent_category="OSCILLATION_DEFENSE")
    rec = ExperienceRecord(
        experience_id="exp_04",
        mission_id="m_04",
        cycle_id="c_01",
        intent_signature=sig,
        mission_context={},
        decision="REQUEST_HUMAN",
        policy_version="41.0.0",
        observation={},
        outcome="loop_prevented",
        root_cause="NONE",
        severity="HIGH",
        prediction={},
        actual_result={},
        adaptation={},
    )
    storage.add_experience(rec)

    curated = storage.curate_experience(
        experience_id="exp_04",
        action=HumanCurationAction.PIN_EXPERIENCE,
        curator_id="operator_1",
        notes="Experiência exemplar de defesa contra oscilação",
    )
    assert curated.curation_status == "PIN_EXPERIENCE"
    assert storage.get_experience("exp_04").curation_status == "PIN_EXPERIENCE"


def test_experience_archival_under_pressure():
    storage = ExperienceStorage()
    sig = ExperienceSignature(intent_category="GENERIC")
    now = time.time()

    for i in range(15):
        rec = ExperienceRecord(
            experience_id=f"exp_arch_{i:02d}",
            mission_id="m_arch",
            cycle_id=f"c_{i}",
            intent_signature=sig,
            mission_context={},
            decision="CONTINUE",
            policy_version="40.1.0",
            observation={},
            outcome="ok",
            root_cause="NONE",
            severity="INFO",
            prediction={},
            actual_result={},
            adaptation={},
            created_at=now + i,
            temporal_validity=TemporalValidity.STALE if i < 3 else TemporalValidity.CURRENT,
        )
        storage.add_experience(rec)

    assert len(storage.list_active_experiences()) == 15
    # Archive with budget of 10 active records
    archived_count = storage.archive_under_pressure(max_active=10)
    assert archived_count == 5
    assert len(storage.list_active_experiences()) == 10
    assert len(storage.list_all_experiences()) == 15
