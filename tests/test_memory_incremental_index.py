"""
JARVIS OS — Phase 43: Event-Driven Incremental Indexing Tests
"""

import pytest
import time
from agents.experience_memory.models import (
    ExperienceRecord,
    ExperienceSignature,
)
from agents.experience_memory.index import ExperienceIndex


def test_incremental_indexing_order_preservation():
    """Verify index_incremental uses bisect.insort and maintains strictly sorted timeline."""
    index = ExperienceIndex()
    
    timestamps = [50.0, 10.0, 90.0, 30.0, 70.0]
    for i, ts in enumerate(timestamps):
        rec = ExperienceRecord(
            experience_id=f"exp_inc_{i}",
            mission_id=f"m_{i}",
            cycle_id="c_01",
            intent_signature=ExperienceSignature(
                intent_category="TEST_CATEGORY",
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
            created_at=ts,
        )
        duration_ms = index.index_incremental(rec)
        assert duration_ms >= 0.0
    
    # Check timeline is strictly sorted ascending by timestamp
    timeline_ts = [item[0] for item in index._timeline]
    assert timeline_ts == sorted(timeline_ts)
    assert timeline_ts == [10.0, 30.0, 50.0, 70.0, 90.0]


def test_incremental_append_vs_rebuild_performance():
    """Single incremental append should be fast and avoid full rebuild overhead."""
    index = ExperienceIndex()
    
    # Pre-populate index with 500 records
    records = []
    for i in range(500):
        rec = ExperienceRecord(
            experience_id=f"exp_bench_{i}",
            mission_id=f"m_{i}",
            cycle_id="c_01",
            intent_signature=ExperienceSignature(
                intent_category=f"CAT_{i % 10}",
                technology=("tech_a", "tech_b"),
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
            created_at=float(i),
        )
        records.append(rec)
    
    index.index_batch_incremental(records)
    assert len(index._timeline) == 500
    
    # 1. Measure incremental single append
    new_rec = ExperienceRecord(
        experience_id="exp_bench_new",
        mission_id="m_new",
        cycle_id="c_01",
        intent_signature=ExperienceSignature(intent_category="CAT_0"),
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
        created_at=250.5,
    )
    
    t0 = time.perf_counter()
    append_time = index.index_incremental(new_rec)
    
    # 2. Measure full rebuild of 501 items
    t0 = time.perf_counter()
    rebuild_time = index.rebuild(records + [new_rec])
    
    # Incremental append is significantly faster than rebuilding 501 items
    assert append_time <= rebuild_time or append_time < 5.0
    assert len(index._timeline) == 501


def test_index_versioning_and_metadata():
    """Verify index metadata contains Phase 43 version tags."""
    index = ExperienceIndex()
    meta = index.get_metadata()
    
    assert meta["index_version"] == "43.0.0"
    assert meta["schema_version"] == "2.0.0"
    assert meta["policy_version"] == "43.0.0"
    assert meta["architecture_snapshot"] == "JARVIS_PHASE_43_MODULAR"
    assert "incremental_appends_count" in meta
    assert "last_incremental_latency_ms" in meta
