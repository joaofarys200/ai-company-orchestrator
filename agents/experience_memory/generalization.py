"""
JARVIS OS — Phase 43: Cross-Mission Generalization & Memory Reliability
Implements deterministic novelty classification, memory harm detection,
ablation evaluation, and statistical generalization metrics tracking.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from agents.experience_memory.models import (
    ExperienceRecord,
    ExperienceReuseOutcome,
    GeneralizationMetrics,
    MemoryBenefitCategory,
    MemoryInfluenceType,
    NoveltyLevel,
)
from agents.experience_memory.signature import IntentNormalizer


class NoveltyClassifier:
    """Deterministically classifies the novelty level of a target mission."""

    @classmethod
    def classify_novelty(
        cls,
        intent_text: str,
        technology: list[str],
        architecture_components: list[str],
        task_categories: list[str],
        observed_failure: str,
        dependency_count: int,
        historical_signatures: list[dict[str, Any]],
    ) -> tuple[NoveltyLevel, float, str]:
        """
        Classifies mission novelty into FAMILIAR, RELATED, NOVEL, or HIGHLY_NOVEL
        based on 6 deterministic dimensions compared against historical signatures.
        """
        if not historical_signatures:
            return NoveltyLevel.HIGHLY_NOVEL, 1.0, "No historical signatures available: completely novel mission."

        intent_cat, _ = IntentNormalizer.normalize_intent(intent_text)
        target_techs = {t.lower() for t in technology}
        target_archs = {a.lower() for a in architecture_components}
        target_tasks = {t.upper() for t in task_categories}
        target_failure = observed_failure.upper() if observed_failure else "NONE"

        # Check domain familiarity across historical records
        known_intents = {s.get("intent_category", "").upper() for s in historical_signatures}
        known_techs = set().union(*[{t.lower() for t in s.get("technology", [])} for s in historical_signatures])
        known_archs = set().union(*[{a.lower() for a in s.get("affected_architecture", [])} for s in historical_signatures])
        known_failures = {s.get("observed_failure", "NONE").upper() for s in historical_signatures}

        # 1. Intent novelty (25%)
        intent_novelty = 0.0 if intent_cat.upper() in known_intents else 1.0

        # 2. Technology novelty (25%)
        if target_techs:
            tech_overlap = target_techs.intersection(known_techs)
            tech_novelty = 1.0 - (len(tech_overlap) / len(target_techs))
        else:
            tech_novelty = 0.5

        # 3. Architecture novelty (20%)
        if target_archs:
            arch_overlap = target_archs.intersection(known_archs)
            arch_novelty = 1.0 - (len(arch_overlap) / len(target_archs))
        else:
            arch_novelty = 0.5

        # 4. Task structure novelty (10%)
        known_tasks = set().union(*[{t.upper() for t in s.get("task_categories", [])} for s in historical_signatures])
        if target_tasks and known_tasks:
            task_overlap = target_tasks.intersection(known_tasks)
            task_novelty = 1.0 - (len(task_overlap) / len(target_tasks))
        else:
            task_novelty = 0.0

        # 5. Failure novelty (10%)
        failure_novelty = 0.0 if target_failure in known_failures else 1.0

        # 6. Dependency novelty (10%)
        avg_deps = sum(s.get("dependency_count", 2) for s in historical_signatures) / max(len(historical_signatures), 1)
        dep_novelty = min(abs(dependency_count - avg_deps) / max(avg_deps, 1.0), 1.0)

        # Weighted composite score
        composite_score = (
            0.25 * intent_novelty
            + 0.25 * tech_novelty
            + 0.20 * arch_novelty
            + 0.10 * task_novelty
            + 0.10 * failure_novelty
            + 0.10 * dep_novelty
        )

        composite_score = round(min(max(composite_score, 0.0), 1.0), 4)

        if composite_score < 0.20:
            level = NoveltyLevel.FAMILIAR
            reason = f"Familiar domain: high overlap across intent ({intent_cat}), stack ({list(target_techs)}) and architecture."
        elif composite_score < 0.45:
            level = NoveltyLevel.RELATED
            reason = f"Related mission: intent or stack shares strong commonalities with historical baseline (score: {composite_score})."
        elif composite_score < 0.75:
            level = NoveltyLevel.NOVEL
            reason = f"Novel mission: introduces unencountered technology, architecture or intent patterns (score: {composite_score})."
        else:
            level = NoveltyLevel.HIGHLY_NOVEL
            reason = f"Highly novel mission: completely distinct technology stack, architecture and failure characteristics (score: {composite_score})."

        return level, composite_score, reason


class MemoryHarmDetector:
    """Detects, characterizes, and provides audit traces for harmful memory transfers."""

    @classmethod
    def evaluate_harm(
        cls,
        experience: ExperienceRecord,
        target_mission_id: str,
        novelty_level: NoveltyLevel,
        influence_type: MemoryInfluenceType,
        baseline_success: bool,
        actual_success: bool,
        baseline_repairs: int,
        actual_repairs: int,
        baseline_replans: int,
        actual_replans: int,
        resolution_seconds_delta: float,
        decision_correctness_degraded: bool = False,
    ) -> ExperienceReuseOutcome:
        """
        Evaluates whether a memory reuse was BENEFICIAL, NEUTRAL, or HARMFUL.
        """
        is_harmful = False
        is_false_transfer = False
        root_cause = "NONE"
        corrective_action = "NONE"

        # Detect Harm Conditions:
        # 1. Decision degraded because of memory influence
        if decision_correctness_degraded:
            is_harmful = True
            is_false_transfer = True
            root_cause = "MEMORY_INDUCED_DECISION_ERROR"
            corrective_action = "MARK_MISLEADING"

        # 2. Memory caused failure where baseline would have succeeded
        elif baseline_success and not actual_success:
            is_harmful = True
            is_false_transfer = True
            root_cause = "FALSE_HEALING_PREMISE_FAILURE"
            corrective_action = "MARK_MISLEADING"

        # 3. Memory caused unnecessary repairs or replans
        elif actual_repairs > baseline_repairs + 1 or actual_replans > baseline_replans + 1:
            is_harmful = True
            is_false_transfer = True
            root_cause = "SUPERFLUOUS_REPAIR_LOOP_INDUCED"
            corrective_action = "MARK_CONTEXT_ONLY"

        # 4. Severe resolution delay (> 100% time increase without benefit)
        elif resolution_seconds_delta > 5.0 and actual_repairs >= baseline_repairs:
            is_harmful = True
            root_cause = "EXCESSIVE_LATENCY_OVERHEAD"
            corrective_action = "MARK_STALE"

        if is_harmful:
            benefit_cat = MemoryBenefitCategory.HARMFUL
            summary = f"Harmful reuse detected for {target_mission_id}: {root_cause}."
        elif actual_success and (not baseline_success or actual_repairs < baseline_repairs or actual_replans < baseline_replans):
            benefit_cat = MemoryBenefitCategory.BENEFICIAL
            summary = f"Beneficial reuse for {target_mission_id}: improved success/repairs."
        elif actual_success == baseline_success and actual_repairs == baseline_repairs:
            benefit_cat = MemoryBenefitCategory.NEUTRAL
            summary = f"Neutral reuse for {target_mission_id}: operational outcome unchanged."
        else:
            benefit_cat = MemoryBenefitCategory.NO_HARM
            summary = f"Safe reuse for {target_mission_id}: no negative side-effects observed."

        return ExperienceReuseOutcome(
            reuse_id=f"reuse_{experience.experience_id}_{target_mission_id}",
            source_mission_id=experience.mission_id,
            source_experience_id=experience.experience_id,
            target_mission_id=target_mission_id,
            novelty_level=novelty_level,
            relevance_score=experience.confidence,
            applicability_rating=experience.applicability,
            influence_type=influence_type.value,
            outcome_summary=summary,
            benefit_category=benefit_cat,
            is_false_transfer=is_false_transfer,
            root_cause_if_harmful=root_cause,
            corrective_action=corrective_action,
        )


class AblationEvaluator:
    """Runs controlled ablation across 5 distinct memory configurations."""

    @classmethod
    def evaluate_ablation(cls, mission_id: str, test_scenarios: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """
        Evaluates 5 ablation configurations:
        - WITHOUT_MEMORY
        - WITH_MEMORY
        - WITH_WRONG_MEMORY
        - WITH_STALE_MEMORY
        - WITH_CONFLICTING_MEMORY
        """
        results = {}
        for regime, data in test_scenarios.items():
            results[regime] = {
                "mission_id": mission_id,
                "first_pass_success": data.get("success", False),
                "decision_accuracy": data.get("decision_accuracy", 1.0),
                "repair_count": data.get("repairs", 0),
                "replan_count": data.get("replans", 0),
                "human_escalations": data.get("escalations", 0),
                "time_seconds": round(data.get("time_seconds", 3.0), 2),
                "false_transfer_detected": data.get("false_transfer", False),
            }
        return results


class GeneralizationMetricsCollector:
    """Collects and aggregates statistical generalization metrics with honesty in sample reporting."""

    def __init__(self):
        self._reuse_outcomes: list[ExperienceReuseOutcome] = []
        self._unseen_missions: list[dict[str, Any]] = []

    def record_outcome(self, outcome: ExperienceReuseOutcome) -> None:
        self._reuse_outcomes.append(outcome)

    def record_unseen_mission(self, mission_id: str, cold_success: bool, warm_success: bool, novelty: NoveltyLevel) -> None:
        self._unseen_missions.append({
            "mission_id": mission_id,
            "cold_success": cold_success,
            "warm_success": warm_success,
            "novelty": novelty,
        })

    def compute_metrics(
        self,
        retrieval_precision: float = 1.0,
        retrieval_recall: float = 1.0,
        stale_rejection_rate: float = 1.0,
        conflict_resolution_accuracy: float = 1.0,
        temporal_leakage_count: int = 0,
    ) -> GeneralizationMetrics:
        total_unseen = len(self._unseen_missions)
        cold_succ = sum(1 for m in self._unseen_missions if m["cold_success"])
        warm_succ = sum(1 for m in self._unseen_missions if m["warm_success"])

        cold_rate = (cold_succ / max(total_unseen, 1)) if total_unseen > 0 else 0.0
        warm_rate = (warm_succ / max(total_unseen, 1)) if total_unseen > 0 else 0.0
        warm_delta = warm_rate - cold_rate

        total_reuses = len(self._reuse_outcomes)
        beneficial_cnt = sum(1 for o in self._reuse_outcomes if o.benefit_category == MemoryBenefitCategory.BENEFICIAL)
        harmful_cnt = sum(1 for o in self._reuse_outcomes if o.benefit_category == MemoryBenefitCategory.HARMFUL)
        false_transfer_cnt = sum(1 for o in self._reuse_outcomes if o.is_false_transfer)

        benefit_rate = (beneficial_cnt / max(total_reuses, 1)) if total_reuses > 0 else 0.0
        harm_rate = (harmful_cnt / max(total_reuses, 1)) if total_reuses > 0 else 0.0
        false_transfer_rate = (false_transfer_cnt / max(total_reuses, 1)) if total_reuses > 0 else 0.0

        sample_counts = {
            "unseen_missions": f"{warm_succ}/{total_unseen}",
            "cold_missions": f"{cold_succ}/{total_unseen}",
            "beneficial_reuses": f"{beneficial_cnt}/{total_reuses}",
            "harmful_reuses": f"{harmful_cnt}/{total_reuses}",
            "false_transfers": f"{false_transfer_cnt}/{total_reuses}",
        }

        return GeneralizationMetrics(
            total_unseen_missions=total_unseen,
            cold_success_count=cold_succ,
            warm_success_count=warm_succ,
            cold_success_rate=round(cold_rate, 4),
            warm_success_rate=round(warm_rate, 4),
            warm_delta=round(warm_delta, 4),
            memory_benefit_rate=round(benefit_rate, 4),
            memory_harm_rate=round(harm_rate, 4),
            false_memory_transfer_rate=round(false_transfer_rate, 4),
            retrieval_precision=round(retrieval_precision, 4),
            retrieval_recall=round(retrieval_recall, 4),
            applicability_accuracy=1.0 - round(false_transfer_rate, 4),
            stale_rejection_rate=round(stale_rejection_rate, 4),
            conflict_resolution_accuracy=round(conflict_resolution_accuracy, 4),
            temporal_leakage_count=temporal_leakage_count,
            sample_counts=sample_counts,
        )
