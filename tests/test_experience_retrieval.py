"""
JARVIS OS — Phase 42: Experience Retrieval Tests
"""

import time

from agents.experience_memory.index import ExperienceIndex
from agents.experience_memory.models import (
    ExperienceRecord,
    ExperienceSignature,
    ExperienceSourceType,
)
from agents.experience_memory.retrieval import ExperienceRetriever
from agents.experience_memory.storage import ExperienceStorage


def test_experience_retrieval_ranking_and_explanation():
    storage = ExperienceStorage()
    index = ExperienceIndex()
    now = time.time()

    # Experience 1: Despesas Financial Ledger
    sig1 = ExperienceSignature(
        intent_category="FINANCIAL_LEDGER",
        technology=("vanilla_ts", "local_storage"),
        observed_failure="NONE",
        decision="CONTINUE",
    )
    rec1 = ExperienceRecord(
        experience_id="exp_ret_01",
        mission_id="m_despesas",
        cycle_id="c_1",
        intent_signature=sig1,
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
        tags=("financial", "vanilla_ts"),
        created_at=now - 50,
    )
    storage.add_experience(rec1)
    index.index_experience(rec1)

    # Experience 2: Authentication JWT
    sig2 = ExperienceSignature(
        intent_category="AUTHENTICATION_AND_AUTH",
        technology=("python", "fastapi", "jwt"),
        observed_failure="NONE",
        decision="CONTINUE",
    )
    rec2 = ExperienceRecord(
        experience_id="exp_ret_02",
        mission_id="m_auth",
        cycle_id="c_1",
        intent_signature=sig2,
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
        tags=("auth", "security"),
        created_at=now - 40,
    )
    storage.add_experience(rec2)
    index.index_experience(rec2)

    retriever = ExperienceRetriever(storage=storage, index=index)

    # Query matching Experience 1
    results = retriever.retrieve(
        current_intent="Registo de despesas e totais financeiros com localStorage",
        current_observation={"failure_class": "NONE"},
        current_mission_state={"user_goal": "App de despesas"},
        architecture_context={"technology": ["vanilla_ts", "local_storage"]},
        current_mission_timestamp=now,
    )

    assert len(results) >= 1
    top = results[0]
    assert top.experience.experience_id == "exp_ret_01"
    assert top.relevance_score > 0.6
    assert "same requirement category" in top.why_relevant
    assert "matching technology stack" in top.why_relevant
