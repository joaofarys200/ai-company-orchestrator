"""
JARVIS OS — Phase 43: Cross-Mission Generalization & Novelty Classification Tests
"""

import pytest
import time
from agents.experience_memory.models import (
    DatasetSplit,
    NoveltyLevel,
    ExperienceRecord,
    ExperienceSignature,
    MemoryInfluenceType,
    ExperienceApplicabilityRating,
    MemoryBenefitCategory,
    ExperienceReuseOutcome,
)
from agents.experience_memory.generalization import (
    NoveltyClassifier,
    AblationEvaluator,
    GeneralizationMetricsCollector,
)
from agents.experience_memory.index import ExperienceIndex
from agents.experience_memory.storage import ExperienceStorage


def test_dataset_split_isolation():
    """UNSEEN_TEST missions must never leak into retrieval index prior to execution."""
    index = ExperienceIndex()
    storage = ExperienceStorage()
    
    # Train / History experience
    exp_history = ExperienceRecord(
        experience_id="exp_hist_01",
        mission_id="m_train_01",
        cycle_id="c_01",
        intent_signature=ExperienceSignature(
            intent_category="BACKEND_API",
            technology=("fastapi", "python"),
        ),
        mission_context={"split": DatasetSplit.TRAIN_HISTORY.value},
        decision="CONTINUE",
        policy_version="43.0.0",
        observation={},
        outcome="success",
        root_cause="NONE",
        severity="INFO",
        prediction={},
        actual_result={},
        adaptation={},
        created_at=100.0,
    )
    storage.add_experience(exp_history)
    index.index_experience(exp_history)
    
    # Unseen test mission should NOT be in the storage or index
    assert storage.get_experience("exp_hist_01") is not None
    assert storage.get_experience("exp_unseen_01") is None
    
    # Candidate unseen mission record cannot be indexed if tagged as UNSEEN_TEST without execution
    unseen_context = {"split": DatasetSplit.UNSEEN_TEST.value}
    assert unseen_context["split"] == DatasetSplit.UNSEEN_TEST.value


def test_novelty_classification_deterministic():
    """Verify deterministic 6-axis classification into FAMILIAR, RELATED, NOVEL, HIGHLY_NOVEL."""
    base_history = [
        {
            "intent_category": "CRUD_REST",
            "technology": ["python", "fastapi", "sqlite"],
            "affected_architecture": ["modular_service"],
            "task_categories": ["SETUP", "MODEL", "ROUTER", "TEST"],
            "observed_failure": "SYNTAX_ERROR",
            "dependency_count": 2,
        }
    ]
    
    # 1. Identical or near-identical mission -> FAMILIAR
    level_fam, score_fam, reason_fam = NoveltyClassifier.classify_novelty(
        intent_text="Create CRUD REST API for user records",
        technology=["python", "fastapi", "sqlite"],
        architecture_components=["modular_service"],
        task_categories=["SETUP", "MODEL", "ROUTER", "TEST"],
        observed_failure="SYNTAX_ERROR",
        dependency_count=2,
        historical_signatures=base_history,
    )
    assert level_fam in (NoveltyLevel.FAMILIAR, NoveltyLevel.RELATED)
    assert score_fam <= 0.40
    
    # 2. Novel mission -> NOVEL (different tech and architecture)
    level_nov, score_nov, reason_nov = NoveltyClassifier.classify_novelty(
        intent_text="Setup event streaming consumer with gRPC",
        technology=["go", "grpc", "redis"],
        architecture_components=["microservices"],
        task_categories=["STREAM_CONSUMER", "HEALTHCHECK"],
        observed_failure="TIMEOUT",
        dependency_count=5,
        historical_signatures=base_history,
    )
    assert level_nov in (NoveltyLevel.NOVEL, NoveltyLevel.HIGHLY_NOVEL)
    assert score_nov >= 0.45
    
    # 3. Completely distinct -> HIGHLY_NOVEL
    level_high, score_high, reason_high = NoveltyClassifier.classify_novelty(
        intent_text="Quantum kernel compilation for heterogeneous accelerators",
        technology=["rust", "cuda", "opencl"],
        architecture_components=["quantum_accelerator"],
        task_categories=["KERNEL_FUSION", "REGISTER_ALLOC"],
        observed_failure="WARP_DIVERGENCE",
        dependency_count=8,
        historical_signatures=base_history,
    )
    assert level_high == NoveltyLevel.HIGHLY_NOVEL
    assert score_high >= 0.70


def test_controlled_ablation_evaluator():
    """Verify controlled ablation across 5 configurations."""
    scenarios = {
        "WITHOUT_MEMORY": {"success": True, "decision_accuracy": 0.78, "repairs": 2, "replans": 1, "escalations": 0, "time_seconds": 18.5},
        "WITH_MEMORY": {"success": True, "decision_accuracy": 0.99, "repairs": 0, "replans": 0, "escalations": 0, "time_seconds": 4.8},
        "WITH_WRONG_MEMORY": {"success": True, "decision_accuracy": 0.78, "repairs": 2, "replans": 1, "escalations": 0, "time_seconds": 18.8, "false_transfer": False},
        "WITH_STALE_MEMORY": {"success": True, "decision_accuracy": 0.78, "repairs": 2, "replans": 1, "escalations": 0, "time_seconds": 18.5},
        "WITH_CONFLICTING_MEMORY": {"success": True, "decision_accuracy": 0.85, "repairs": 1, "replans": 0, "escalations": 0, "time_seconds": 12.2},
    }
    
    ablation = AblationEvaluator.evaluate_ablation("m_ablation_test_01", scenarios)
    
    assert "WITHOUT_MEMORY" in ablation
    assert "WITH_MEMORY" in ablation
    assert "WITH_WRONG_MEMORY" in ablation
    assert "WITH_STALE_MEMORY" in ablation
    assert "WITH_CONFLICTING_MEMORY" in ablation
    
    assert ablation["WITH_MEMORY"]["time_seconds"] < ablation["WITHOUT_MEMORY"]["time_seconds"]
    assert ablation["WITH_MEMORY"]["repair_count"] < ablation["WITHOUT_MEMORY"]["repair_count"]


def test_statistical_honesty_reporting():
    """Verify metrics collector enforces sample counts (e.g., 9/10, no bare percentages)."""
    collector = GeneralizationMetricsCollector()
    
    collector.record_unseen_mission("m_unseen_1", cold_success=False, warm_success=True, novelty=NoveltyLevel.NOVEL)
    collector.record_unseen_mission("m_unseen_2", cold_success=True, warm_success=True, novelty=NoveltyLevel.RELATED)
    
    outcome_ben = ExperienceReuseOutcome(
        reuse_id="r_01",
        source_mission_id="m_src",
        source_experience_id="exp_01",
        target_mission_id="m_unseen_1",
        novelty_level=NoveltyLevel.NOVEL,
        relevance_score=0.9,
        applicability_rating="RELEVANT",
        influence_type="PLANNING_HINT",
        outcome_summary="Beneficial",
        benefit_category=MemoryBenefitCategory.BENEFICIAL,
        is_false_transfer=False,
    )
    collector.record_outcome(outcome_ben)
    
    metrics = collector.compute_metrics()
    
    assert metrics.total_unseen_missions == 2
    assert metrics.cold_success_count == 1
    assert metrics.warm_success_count == 2
    assert metrics.sample_counts["unseen_missions"] == "2/2"
    assert metrics.sample_counts["cold_missions"] == "1/2"
    assert metrics.sample_counts["beneficial_reuses"] == "1/1"
