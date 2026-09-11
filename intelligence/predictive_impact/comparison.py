"""
JARVIS OS — Phase 39: Prediction vs Actual Comparison

Performs empirical telemetry comparison between what was PREDICTED and what was ACTUALLY OBSERVED.
Calculates formal observable metrics:
- File Precision & Recall
- Task Precision & Recall
- Evidence Precision & Recall
- Explicit separation of False Positives (unexpected) and False Negatives (missed)
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Set

from intelligence.predictive_impact.models import (
    OutcomeClassification,
    PredictionOutcome,
    PredictiveImpactReport,
)


class PredictionComparator:
    """
    Evaluates how closely reality matched the prediction without hidden deviations.
    """

    @classmethod
    def compare(
        cls,
        report: PredictiveImpactReport,
        actual_intent_version: int,
        actual_plan_version: int,
        actual_files_changed: list[str],
        actual_tasks_added: list[str],
        actual_tasks_modified: list[str],
        actual_tasks_removed: list[str],
        actual_evidence_invalidated: list[str],
        actual_agents_used: list[str],
        actual_browser_validation: bool = False,
        actual_scope: str = "LOCAL",
    ) -> PredictionOutcome:
        """
        Builds PredictionOutcome from report and empirical observation.
        """
        # 1. File Precision & Recall
        pred_files: Set[str] = {f.get("file_path", "").lower() for f in report.predicted_files if f.get("file_path")}
        act_files: Set[str] = {f.lower() for f in actual_files_changed if f}

        matched_files_set = pred_files.intersection(act_files)
        unexpected_files_set = act_files.difference(pred_files)  # False positives in actual / underpredicted
        missed_files_set = pred_files.difference(act_files)  # False positives in prediction / overpredicted

        file_precision = len(matched_files_set) / len(pred_files) if pred_files else (1.0 if not act_files else 0.0)
        file_recall = len(matched_files_set) / len(act_files) if act_files else (1.0 if not pred_files else 0.0)

        # 2. Task Precision & Recall
        pred_task_actions = {f"{t.get('action')}:{t.get('source_requirement', '').lower()}" for t in report.predicted_tasks}
        act_task_actions = set()
        for t in actual_tasks_added:
            act_task_actions.add(f"ADD_TASK:{t.lower()}")
        for t in actual_tasks_modified:
            act_task_actions.add(f"MODIFY_TASK:{t.lower()}")
        for t in actual_tasks_removed:
            act_task_actions.add(f"REMOVE_TASK:{t.lower()}")

        matched_tasks_set = pred_task_actions.intersection(act_task_actions)
        unexpected_tasks_set = act_task_actions.difference(pred_task_actions)
        missed_tasks_set = pred_task_actions.difference(act_task_actions)

        task_precision = len(matched_tasks_set) / len(pred_task_actions) if pred_task_actions else (1.0 if not act_task_actions else 0.0)
        task_recall = len(matched_tasks_set) / len(act_task_actions) if act_task_actions else (1.0 if not pred_task_actions else 0.0)

        # 3. Evidence Precision & Recall
        pred_ev: Set[str] = {e.get("evidence_id", "") for e in report.predicted_evidence_impact if e.get("predicted_status") in ("REQUIRES_REVALIDATION", "SUPERSEDED")}
        act_ev: Set[str] = set(actual_evidence_invalidated)

        matched_ev_set = pred_ev.intersection(act_ev)
        evidence_precision = len(matched_ev_set) / len(pred_ev) if pred_ev else (1.0 if not act_ev else 0.0)
        evidence_recall = len(matched_ev_set) / len(act_ev) if act_ev else (1.0 if not pred_ev else 0.0)

        # 4. Deviations analysis
        deviations: list[dict[str, Any]] = []
        for uf in unexpected_files_set:
            deviations.append({
                "type": "UNEXPECTED_FILE",
                "item": uf,
                "description": f"Ficheiro '{uf}' foi alterado na execução mas não tinha sido previsto",
            })
        for mf in missed_files_set:
            deviations.append({
                "type": "MISSED_FILE_PREDICTION",
                "item": mf,
                "description": f"Ficheiro '{mf}' foi previsto mas não sofreu alteração física",
            })
        if report.predicted_scope != actual_scope:
            deviations.append({
                "type": "SCOPE_MISMATCH",
                "item": f"predicted: {report.predicted_scope} vs actual: {actual_scope}",
                "description": "Divergência entre escopo previsto e escopo executado",
            })

        # 5. Overall Classification
        avg_score = (file_precision + file_recall + task_precision + task_recall) / 4.0
        has_file_mismatch = (len(unexpected_files_set) > 0 or len(missed_files_set) > 0)
        has_task_mismatch = (len(unexpected_tasks_set) > 0 or len(missed_tasks_set) > 0)

        if len(unexpected_files_set) > 0 and len(unexpected_files_set) >= len(matched_files_set):
            classification = OutcomeClassification.UNDERPREDICTED.value
        elif len(missed_files_set) > 0 and len(missed_files_set) >= len(matched_files_set):
            classification = OutcomeClassification.OVERPREDICTED.value
        elif not has_file_mismatch and not has_task_mismatch and avg_score >= 0.80:
            classification = OutcomeClassification.CORRECT.value
        elif avg_score >= 0.50:
            classification = OutcomeClassification.PARTIALLY_CORRECT.value
        else:
            classification = OutcomeClassification.MISSED.value

        outcome = PredictionOutcome(
            outcome_id=f"out_{uuid.uuid4().hex[:8]}",
            prediction_id=report.prediction_id,
            mission_id=report.mission_id,
            actual_intent_version=actual_intent_version,
            actual_plan_version=actual_plan_version,
            evaluated_at=time.time(),
            actual_tasks_added=actual_tasks_added,
            actual_tasks_modified=actual_tasks_modified,
            actual_tasks_removed=actual_tasks_removed,
            actual_files_changed=actual_files_changed,
            actual_tests_added=actual_files_changed,
            actual_evidence_invalidated=actual_evidence_invalidated,
            actual_agents_used=actual_agents_used,
            actual_browser_validation=actual_browser_validation,
            actual_scope=actual_scope,
            file_precision=round(file_precision, 3),
            file_recall=round(file_recall, 3),
            task_precision=round(task_precision, 3),
            task_recall=round(task_recall, 3),
            evidence_precision=round(evidence_precision, 3),
            evidence_recall=round(evidence_recall, 3),
            classification=classification,
            matched_files=sorted(list(matched_files_set)),
            missed_files=sorted(list(missed_files_set)),
            unexpected_files=sorted(list(unexpected_files_set)),
            matched_tasks=sorted(list(matched_tasks_set)),
            missed_tasks=sorted(list(missed_tasks_set)),
            unexpected_tasks=sorted(list(unexpected_tasks_set)),
            deviations=deviations,
        )

        return outcome
