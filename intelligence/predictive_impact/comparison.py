"""
JARVIS OS — Phase 39.2: Prediction vs Actual Telemetry & Task Reconciliation Comparison

Performs empirical telemetry comparison between what was PREDICTED and what was ACTUALLY OBSERVED.
Calculates formal observable metrics:
- File Precision & Recall
- Task Precision & Recall
- Evidence Precision & Recall
- Explicit separation of False Positives (unexpected) and False Negatives (missed)
- Multi-dimensional Task Matching (Action, Category, Requirement, Target Files, Symbols)
- Causal Match Traceability (MATCHED, MISSED, OVERPREDICTED)
- Deterministic Root-Cause Classification for Task Deviations
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional, Set

from intelligence.predictive_impact.models import (
    OutcomeClassification,
    PredictionOutcome,
    PredictiveImpactReport,
    TaskCategory,
    TaskRootCauseType,
)


class PredictionComparator:
    """
    Evaluates how closely reality matched the prediction without hidden deviations.
    Reconciles impact-to-task relationships and classifies deviations into root causes.
    """

    @classmethod
    def match_tasks(
        cls,
        predicted_tasks: list[dict[str, Any]],
        actual_tasks_added: list[Any],
        actual_tasks_modified: list[Any],
        actual_tasks_removed: list[Any],
        predicted_files: list[dict[str, Any]],
        actual_files_changed: list[str],
    ) -> dict[str, Any]:
        """
        Multi-dimensional matching of predicted tasks against actual observations.
        Considers:
        - Action (ADD_TASK, MODIFY_TASK, REMOVE_TASK)
        - Semantic Category (Coding, Testing, Architecture, Browser, Review)
        - Source Requirement
        - Impacted Files & Symbols
        - Granularity Normalization
        """
        # Normalize actual tasks into structured records
        norm_actual: list[dict[str, Any]] = []

        def add_actual(items: list[Any], default_action: str):
            for it in items:
                if isinstance(it, dict):
                    norm_actual.append({
                        "id": it.get("id", it.get("task_id", f"act_{uuid.uuid4().hex[:6]}")),
                        "action": it.get("action", default_action),
                        "category": it.get("category", TaskCategory.CODING.value),
                        "requirement": it.get("source_requirement", it.get("requirement", "")).lower(),
                        "title": it.get("title", ""),
                        "files": [f.lower() for f in it.get("files", [])],
                        "raw": it,
                    })
                elif isinstance(it, str):
                    # Could be "REQ_SEARCH", "ADD_TASK:req_search", "ptask_impl_1", etc.
                    s = it.strip()
                    s_lower = s.lower()
                    act = default_action
                    req = s_lower
                    cat = TaskCategory.CODING.value

                    if ":" in s:
                        parts = s.split(":", 1)
                        if parts[0].upper() in ("ADD_TASK", "MODIFY_TASK", "REMOVE_TASK"):
                            act = parts[0].upper()
                            req = parts[1].lower()

                    if "test" in s_lower or "valid" in s_lower:
                        cat = TaskCategory.TESTING.value
                    elif "arch" in s_lower or "esquema" in s_lower:
                        cat = TaskCategory.ARCHITECTURE.value

                    norm_actual.append({
                        "id": s,
                        "action": act,
                        "category": cat,
                        "requirement": req,
                        "title": s,
                        "files": [],
                        "raw": it,
                    })

        add_actual(actual_tasks_added, "ADD_TASK")
        add_actual(actual_tasks_modified, "MODIFY_TASK")
        add_actual(actual_tasks_removed, "REMOVE_TASK")

        # Normalize predicted tasks
        norm_predicted: list[dict[str, Any]] = []
        for pt in predicted_tasks:
            ptid = pt.get("predicted_task_id", "")
            action = pt.get("action", "ADD_TASK")
            req = (pt.get("source_requirement") or "").lower()
            cat = pt.get("category", TaskCategory.CODING.value)
            files = [f.lower() for f in pt.get("predicted_files", [])]
            symbols = pt.get("impacted_symbols", [])
            causal_trace = pt.get("causal_trace", {})

            norm_predicted.append({
                "id": ptid,
                "action": action,
                "requirement": req,
                "category": cat,
                "title": pt.get("title", ""),
                "files": files,
                "symbols": symbols,
                "causal_trace": causal_trace,
                "derivation_type": pt.get("derivation_type", ""),
                "raw": pt,
            })

        matched_pred_ids: Set[str] = set()
        matched_act_ids: Set[str] = set()
        causal_matches: list[dict[str, Any]] = []
        root_causes: dict[str, int] = {}

        def record_root_cause(cause: str):
            root_causes[cause] = root_causes.get(cause, 0) + 1

        # Matching Strategy 1: Exact task ID or Action + Requirement + Category Match
        for p in norm_predicted:
            p_id = p["id"]
            p_act = p["action"]
            p_req = p["requirement"]
            p_cat = p["category"]

            best_act = None
            for a in norm_actual:
                if a["id"] in matched_act_ids:
                    continue

                # ID match
                if p_id.lower() == a["id"].lower():
                    best_act = a
                    break

                # Action + Requirement match
                act_req_match = (
                    p_req
                    and (p_req == a["requirement"] or p_req in a["requirement"] or a["requirement"] in p_req)
                )

                if act_req_match and p_act == a["action"]:
                    # If category also matches or actual has generic category
                    if p_cat == a["category"] or not a["files"]:
                        best_act = a
                        break

            # Fallback matching: Requirement match even if single actual task represents requirement
            if not best_act:
                for a in norm_actual:
                    if a["id"] in matched_act_ids:
                        continue
                    if p_req and (p_req == a["requirement"] or p_req in a["requirement"] or a["requirement"] in p_req):
                        best_act = a
                        break

            if best_act:
                matched_pred_ids.add(p_id)
                matched_act_ids.add(best_act["id"])
                causal_matches.append({
                    "predicted_task_id": p_id,
                    "actual_task_id": best_act["id"],
                    "match_status": "MATCHED",
                    "category": p_cat,
                    "source_requirement": p_req,
                    "derivation_type": p["derivation_type"],
                    "causal_trace": p["causal_trace"],
                })

        # Identify Missed Predicted Tasks (Overprediction / False Positives in Prediction)
        missed_pred_tasks: list[str] = []
        for p in norm_predicted:
            if p["id"] not in matched_pred_ids:
                missed_pred_tasks.append(p["id"])
                # Classify root cause for why predicted task wasn't observed
                if p["files"] and not any(f in [af.lower() for af in actual_files_changed] for f in p["files"]):
                    rc = TaskRootCauseType.OVER_AGGRESSIVE_TASK_DERIVATION.value
                elif p["derivation_type"] == "VALIDATION_DRIVEN":
                    rc = TaskRootCauseType.VALIDATION_TASK_NOT_FILE_DRIVEN.value
                else:
                    rc = TaskRootCauseType.EXPECTED_UNCERTAINTY.value

                record_root_cause(rc)
                causal_matches.append({
                    "predicted_task_id": p["id"],
                    "actual_task_id": None,
                    "match_status": "OVERPREDICTED",
                    "category": p["category"],
                    "source_requirement": p["requirement"],
                    "derivation_type": p["derivation_type"],
                    "root_cause": rc,
                    "causal_trace": p["causal_trace"],
                })

        # Identify Unexpected Actual Tasks (False Negatives in Prediction)
        unexpected_act_tasks: list[str] = []
        for a in norm_actual:
            if a["id"] not in matched_act_ids:
                unexpected_act_tasks.append(a["id"])
                # Classify root cause
                if a["category"] == TaskCategory.TESTING.value:
                    rc = TaskRootCauseType.VALIDATION_TASK_NOT_FILE_DRIVEN.value
                elif a["category"] == TaskCategory.ARCHITECTURE.value:
                    rc = TaskRootCauseType.SEMANTIC_TASK_NOT_FILE_DRIVEN.value
                elif any(f in [pf.get("file_path", "").lower() for pf in predicted_files] for f in a["files"]):
                    rc = TaskRootCauseType.MISSING_FILE_TO_TASK_MAPPING.value
                else:
                    rc = TaskRootCauseType.PLANNING_CONTRACT_GAP.value

                record_root_cause(rc)
                causal_matches.append({
                    "predicted_task_id": None,
                    "actual_task_id": a["id"],
                    "match_status": "MISSED",
                    "category": a["category"],
                    "source_requirement": a["requirement"],
                    "derivation_type": None,
                    "root_cause": rc,
                    "causal_trace": None,
                })

        # Backward compatibility format
        matched_tasks_list = sorted(list(matched_pred_ids))
        unexpected_tasks_list = sorted(unexpected_act_tasks)
        missed_tasks_list = sorted(missed_pred_tasks)

        # Precision & Recall calculation
        total_pred = len(norm_predicted)
        total_act = len(norm_actual)
        tp = len(matched_pred_ids)

        task_precision = tp / total_pred if total_pred > 0 else (1.0 if not total_act else 0.0)
        task_recall = tp / total_act if total_act > 0 else (1.0 if not total_pred else 0.0)

        return {
            "task_precision": round(task_precision, 3),
            "task_recall": round(task_recall, 3),
            "matched_tasks": matched_tasks_list,
            "unexpected_tasks": unexpected_tasks_list,
            "missed_tasks": missed_tasks_list,
            "causal_matches": causal_matches,
            "root_causes": root_causes,
        }

    @classmethod
    def compare(
        cls,
        report: PredictiveImpactReport,
        actual_intent_version: int,
        actual_plan_version: int,
        actual_files_changed: list[str],
        actual_tasks_added: list[Any],
        actual_tasks_modified: list[Any],
        actual_tasks_removed: list[Any],
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
        unexpected_files_set = act_files.difference(pred_files)  # Underpredicted files
        missed_files_set = pred_files.difference(act_files)  # Overpredicted files

        file_precision = len(matched_files_set) / len(pred_files) if pred_files else (1.0 if not act_files else 0.0)
        file_recall = len(matched_files_set) / len(act_files) if act_files else (1.0 if not pred_files else 0.0)

        # 2. Reconciled Task Precision & Recall
        task_match_res = cls.match_tasks(
            predicted_tasks=report.predicted_tasks,
            actual_tasks_added=actual_tasks_added,
            actual_tasks_modified=actual_tasks_modified,
            actual_tasks_removed=actual_tasks_removed,
            predicted_files=report.predicted_files,
            actual_files_changed=actual_files_changed,
        )

        task_precision = task_match_res["task_precision"]
        task_recall = task_match_res["task_recall"]
        matched_tasks_list = task_match_res["matched_tasks"]
        unexpected_tasks_list = task_match_res["unexpected_tasks"]
        missed_tasks_list = task_match_res["missed_tasks"]

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
        for ut in unexpected_tasks_list:
            deviations.append({
                "type": "UNEXPECTED_TASK",
                "item": ut,
                "description": f"Tarefa '{ut}' executada sem correspondente previsto",
            })
        for mt in missed_tasks_list:
            deviations.append({
                "type": "MISSED_TASK",
                "item": mt,
                "description": f"Tarefa '{mt}' prevista não foi executada no plano",
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
        has_task_mismatch = (len(unexpected_tasks_list) > 0 or len(missed_tasks_list) > 0)

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
            actual_tasks_added=[str(t) for t in actual_tasks_added],
            actual_tasks_modified=[str(t) for t in actual_tasks_modified],
            actual_tasks_removed=[str(t) for t in actual_tasks_removed],
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
            matched_tasks=matched_tasks_list,
            missed_tasks=missed_tasks_list,
            unexpected_tasks=unexpected_tasks_list,
            deviations=deviations,
            task_mismatches_by_root_cause=task_match_res["root_causes"],
            task_causal_matches=task_match_res["causal_matches"],
        )

        return outcome
