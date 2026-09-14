"""
JARVIS OS — Phase 42: Cross-Mission Experience Reuse & Quality Benchmark Tests
"""

from agents.experience_memory.metrics import ExperienceMetricsCollector
from agents.experience_memory.models import ExperienceReuseRecord


def test_experience_metrics_reuse_tracking():
    collector = ExperienceMetricsCollector()

    collector.record_reuse(
        ExperienceReuseRecord(
            reuse_id="re_01",
            source_experience_id="exp_01",
            target_mission_id="m_target_1",
            target_cycle_id="c_1",
            what_was_reused="localStorage persistence pattern",
            how_adapted="Applied directly to expenses DAG",
            experience_prediction="First pass success",
            actual_outcome="Verified in browser QA",
            successful_reuse=True,
        )
    )
    collector.record_reuse(
        ExperienceReuseRecord(
            reuse_id="re_02",
            source_experience_id="exp_02",
            target_mission_id="m_target_2",
            target_cycle_id="c_1",
            what_was_reused="AST syntax repair rule",
            how_adapted="Applied surgical patch",
            experience_prediction="Clean build",
            actual_outcome="Compilation error resolved",
            successful_reuse=True,
        )
    )

    metrics = collector.compute_quality_metrics(
        total_retrievals=2,
        relevant_retrieved=2,
        ground_truth_relevant=2,
    )

    assert metrics.reuse_count == 2
    assert metrics.successful_reuse_count == 2
    assert metrics.failed_reuse_count == 0
    assert metrics.applicability_accuracy == 1.0
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0


def test_cold_vs_warm_benchmark_comparison():
    collector = ExperienceMetricsCollector()

    # Record Cold Mission
    collector.record_mission_benchmark(
        mission_profile="COLD_DESPESAS",
        is_warm=False,
        metrics={
            "first_pass_success_rate": 0.70,
            "repair_count": 3,
            "replan_count": 1,
            "decision_accuracy": 0.96,
            "human_escalation_count": 1,
            "resolution_seconds": 20.0,
        },
    )

    # Record Warm Mission
    collector.record_mission_benchmark(
        mission_profile="WARM_DESPESAS",
        is_warm=True,
        metrics={
            "first_pass_success_rate": 0.95,
            "repair_count": 0,
            "replan_count": 0,
            "decision_accuracy": 1.0,
            "human_escalation_count": 0,
            "resolution_seconds": 5.0,
        },
    )

    comparison = collector.compare_cold_vs_warm()
    assert comparison["cold_missions_count"] == 1
    assert comparison["warm_missions_count"] == 1
    assert comparison["warm"]["first_pass_success_rate"] > comparison["cold"]["first_pass_success_rate"]
    assert comparison["warm"]["avg_repairs"] < comparison["cold"]["avg_repairs"]
    assert comparison["delta"]["first_pass_success_rate_delta"] == 0.25
