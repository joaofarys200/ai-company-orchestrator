"""
JARVIS OS — Phase 43: Temporal Leakage Protection Tests
"""

import pytest
import time
from agents.experience_memory.models import (
    ExperienceRecord,
    ExperienceSignature,
    TemporalValidity,
)
from agents.experience_memory.index import ExperienceIndex


def test_temporal_leakage_backward_blocking():
    """TEMPORAL_LEAKAGE_TEST: Mission starting at T can only see experiences with timestamp < T."""
    index = ExperienceIndex()
    
    t_start = 1000.0
    
    # 1. Past experience (valid)
    past_exp = ExperienceRecord(
        experience_id="exp_past_01",
        mission_id="m_past_01",
        cycle_id="c_01",
        intent_signature=ExperienceSignature(
            intent_category="BACKEND",
            technology=("python",),
        ),
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
        created_at=900.0, # < 1000.0
    )
    index.index_experience(past_exp)
    
    # 2. Future experience (leaked/future timestamp)
    future_exp = ExperienceRecord(
        experience_id="exp_future_01",
        mission_id="m_future_01",
        cycle_id="c_01",
        intent_signature=ExperienceSignature(
            intent_category="BACKEND",
            technology=("python",),
        ),
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
        created_at=1100.0, # > 1000.0 (FUTURE!)
    )
    index.index_experience(future_exp)
    
    # Query candidate IDs with max_timestamp=t_start (1000.0)
    candidate_ids = index.query_candidates(
        intent_category="BACKEND",
        technology=["python"],
        max_timestamp=t_start,
    )
    
    assert "exp_past_01" in candidate_ids
    assert "exp_future_01" not in candidate_ids, "TEMPORAL LEAKAGE DETECTED: Future experience leaked backwards!"


def test_temporal_validity_strict_enforcement():
    """Ensure that temporal checks reject future evidence, outcomes, and benchmark records."""
    t_mission = 500.0
    
    # An experience timestamped exactly or after mission start is rejected
    exp_concurrent = ExperienceRecord(
        experience_id="exp_concurrent_01",
        mission_id="m_other",
        cycle_id="c_01",
        intent_signature=ExperienceSignature(intent_category="CRUD"),
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
        created_at=500.1, # Future by 0.1s
    )
    
    index = ExperienceIndex()
    index.index_experience(exp_concurrent)
    
    results = index.query_candidates(intent_category="CRUD", max_timestamp=t_mission)
    assert len(results) == 0, "Concurrent or future experience leaked into mission context!"
