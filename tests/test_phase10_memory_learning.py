"""
PyTest Test Suite for Phase 10: Memory & Pedagogical Learning Engine
"""

import asyncio
import pytest
from agents.controlled_real_world_value_agent import (
    LearningEngine,
    StudentState
)


def test_learning_engine_10_stage_pedagogical_pipeline():
    async def _run():
        engine = LearningEngine()
        res = await engine.execute_pedagogical_cycle(
            topic="Distributed Epoch Fencing",
            source_content="Epoch fencing prevents split-brain zombie writes via monotonic counters.",
            provenance="JARVIS_INTERNAL"
        )
        assert res["pipeline_stages_completed"] == 10
        assert res["quiz_score"] == 100.0
        assert res["transfer_solved"] is True
        assert res["student_mastery"] > 0.5
        assert res["next_review_timestamp"] > 0

    asyncio.run(_run())


def test_student_state_spaced_review_calculation():
    st = StudentState(
        topic="SQLite WAL Concurrency",
        mastery=0.5,
        weaknesses=[],
        attempts=0,
        last_review=0.0,
        next_review=0.0,
        source_provenance="JARVIS_INTERNAL"
    )
    # 1. High score increases mastery and schedules future spaced review
    st.update_spaced_review(1.0)
    assert st.attempts == 1
    assert st.mastery == 0.75
    assert st.next_review > st.last_review

    # 2. Low score reduces mastery and sets immediate review (1 day)
    st.update_spaced_review(0.4)
    assert st.attempts == 2
    assert st.mastery == 0.55
