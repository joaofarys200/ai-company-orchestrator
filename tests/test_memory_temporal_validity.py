"""
JARVIS OS — Phase 42: Memory Temporal Validity & Anti-Leakage Tests
"""

import time

from agents.experience_memory.index import ExperienceIndex
from agents.experience_memory.models import (
    ExperienceRecord,
    ExperienceSignature,
    TemporalValidity,
)
from agents.experience_memory.retrieval import ExperienceRetriever
from agents.experience_memory.storage import ExperienceStorage


def test_anti_leakage_guarantee():
    storage = ExperienceStorage()
    index = ExperienceIndex()

    current_mission_time = 1000.0  # Simulated current time

    # Past experience (T=900)
    sig_past = ExperienceSignature(intent_category="FINANCIAL_LEDGER")
    rec_past = ExperienceRecord(
        experience_id="exp_past",
        mission_id="m_past",
        cycle_id="c_1",
        intent_signature=sig_past,
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
        created_at=900.0,
    )
    storage.add_experience(rec_past)
    index.index_experience(rec_past)

    # Future experience relative to current mission (T=1100)
    sig_future = ExperienceSignature(intent_category="FINANCIAL_LEDGER")
    rec_future = ExperienceRecord(
        experience_id="exp_future",
        mission_id="m_future",
        cycle_id="c_1",
        intent_signature=sig_future,
        mission_context={},
        decision="CONTINUE",
        policy_version="41.0.0",
        observation={},
        outcome="future_success_with_leaked_evidence",
        root_cause="NONE",
        severity="INFO",
        prediction={},
        actual_result={},
        adaptation={},
        created_at=1100.0,
    )
    storage.add_experience(rec_future)
    index.index_experience(rec_future)

    retriever = ExperienceRetriever(storage=storage, index=index)

    # Query executing at T=1000.0
    results = retriever.retrieve(
        current_intent="Registo de despesas financeiras",
        current_observation={},
        current_mission_state={},
        architecture_context={"technology": ["vanilla_ts"]},
        current_mission_timestamp=current_mission_time,
    )

    retrieved_ids = [r.experience.experience_id for r in results]
    assert "exp_past" in retrieved_ids
    assert "exp_future" not in retrieved_ids  # Future evidence is STRICTLY forbidden from leaking backwards!


def test_stale_classification_penalization():
    storage = ExperienceStorage()
    index = ExperienceIndex()
    now = time.time()

    sig = ExperienceSignature(intent_category="CODE_REPAIR")
    rec_stale = ExperienceRecord(
        experience_id="exp_stale",
        mission_id="m_old",
        cycle_id="c_1",
        intent_signature=sig,
        mission_context={},
        decision="REPAIR",
        policy_version="37.0.0",
        observation={},
        outcome="success",
        root_cause="NONE",
        severity="INFO",
        prediction={},
        actual_result={},
        adaptation={},
        temporal_validity=TemporalValidity.STALE,
        created_at=now - 200,
    )
    storage.add_experience(rec_stale)
    index.index_experience(rec_stale)

    retriever = ExperienceRetriever(storage=storage, index=index)
    results = retriever.retrieve(
        current_intent="Reparar sintaxe de código",
        current_observation={},
        current_mission_state={},
        architecture_context={"technology": ["vanilla_ts"]},
        current_mission_timestamp=now,
    )

    if results:
        assert results[0].applicability.value == "STALE"
        assert "STALE" in results[0].why_relevant
