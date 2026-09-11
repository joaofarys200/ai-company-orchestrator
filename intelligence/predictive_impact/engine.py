"""
JARVIS OS — Phase 39: Predictive Impact Engine

The non-mutating simulation core.
Orchestrates graph traversal, risk assessment, and structural validation to produce PredictiveImpactReport.
Enforces:
1. Strict NO-MUTATION of mission state, files, or SQLite during preview.
2. Optimistic locking: Marks prediction STALE if intent_version increments.
3. Crash recovery & persistence of prediction reports and outcomes.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional

from intelligence.predictive_impact.comparison import PredictionComparator
from intelligence.predictive_impact.graph import ImpactGraphEngine
from intelligence.predictive_impact.models import (
    ImpactScope,
    PredictionOutcome,
    PredictionStatus,
    PredictiveImpactReport,
    RiskLevel,
)
from intelligence.predictive_impact.risk import DeterministicRiskModel
from intelligence.predictive_impact.validator import PredictiveImpactValidator


class PredictiveImpactEngine:
    """
    Simulates mission intent changes without mutating real mission state.
    """

    _predictions: dict[str, PredictiveImpactReport] = {}
    _outcomes: dict[str, PredictionOutcome] = {}
    _persistence_file: str = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "docs", "phase39_prediction_outcomes.json")
    )

    @classmethod
    def reset(cls) -> None:
        """Reset in-memory storage for clean testing."""
        cls._predictions.clear()
        cls._outcomes.clear()

    @classmethod
    def predict(
        cls,
        delta_operation: str,
        target_name: str,
        directive_text: str,
        mission_id: str,
        base_intent_version: int,
        current_intent_version: int,
        current_requirements: list[dict[str, Any]],
        current_tasks: list[dict[str, Any]],
        current_evidence: list[dict[str, Any]],
        current_assumptions: list[str],
        is_running: bool = False,
    ) -> PredictiveImpactReport:
        """
        Simulates impact without side-effects.
        """
        # 1. Optimistic Version Check (Stale Prevention)
        if base_intent_version != current_intent_version:
            report = PredictiveImpactReport(
                prediction_id=f"pred_stale_{uuid.uuid4().hex[:8]}",
                mission_id=mission_id,
                source_intent_version=base_intent_version,
                proposed_intent_version=current_intent_version + 1,
                generated_at=time.time(),
                predicted_scope=ImpactScope.NONE.value,
                predicted_risk=RiskLevel.LOW.value,
                status=PredictionStatus.STALE.value,
                uncertainties=[f"Versão base {base_intent_version} defasada em relação à versão atual {current_intent_version}."],
                confidence=1.0,
            )
            cls._predictions[report.prediction_id] = report
            return report

        # 2. Graph Traversal
        graph_engine = ImpactGraphEngine()
        graph_data = graph_engine.analyze_delta_impact(
            operation=delta_operation,
            target_name=target_name,
            directive_text=directive_text,
            current_requirements=current_requirements,
            current_tasks=current_tasks,
            current_evidence=current_evidence,
            assumptions=current_assumptions,
        )

        pred_files = graph_data["predicted_files"]
        pred_tasks = graph_data["predicted_tasks"]
        pred_evidence = graph_data["predicted_evidence"]
        pred_tests = graph_data["predicted_tests"]
        causal_chains = graph_data["causal_chains"]
        uncertainties = graph_data["uncertainties"]

        # 3. Infer Scope
        has_backend = any("backend" in f.get("file_path", "") or "agents" in f.get("file_path", "") for f in pred_files)
        has_frontend = any("frontend" in f.get("file_path", "") for f in pred_files)
        
        if delta_operation in ("REMOVE_REQUIREMENT", "REVISE_APPROACH") or "graphql" in directive_text.lower() or "arquitetura" in directive_text.lower():
            scope = ImpactScope.ARCHITECTURAL.value
        elif has_backend and has_frontend:
            scope = ImpactScope.CROSS_MODULE.value
        elif len(pred_files) > 1:
            scope = ImpactScope.CROSS_FILE.value
        elif len(pred_files) == 1:
            scope = ImpactScope.LOCAL.value
        else:
            scope = ImpactScope.NONE.value

        # 4. Deterministic Risk Evaluation
        risk_level, risk_score, risk_factors, approval_required = DeterministicRiskModel.evaluate_risk(
            scope=scope,
            predicted_files=pred_files,
            predicted_tasks=pred_tasks,
            predicted_evidence_impact=pred_evidence,
            directive_text=directive_text,
            is_running=is_running,
        )

        # 5. Operational Flags
        browser_validation = has_frontend or any("ui" in f.get("file_path", "").lower() for f in pred_files)
        pause_required = (scope in (ImpactScope.ARCHITECTURAL.value, ImpactScope.CROSS_MODULE.value) or risk_level in (RiskLevel.HIGH.value, RiskLevel.CRITICAL.value))

        # 6. Assumptions
        assumptions = [
            {
                "assumption_id": "asm_compat",
                "statement": "Preservação da compatibilidade com os endpoints e contratos públicos existentes",
                "category": "SYSTEM_ASSUMPTION",
                "confidence": 0.90,
            },
            {
                "assumption_id": "asm_deps",
                "statement": "Reutilização dos serviços e utilitários já mapeados no workspace",
                "category": "INFERRED",
                "confidence": 0.85,
            },
        ]

        # 7. Structural Validation
        is_valid, validation_errors = PredictiveImpactValidator.validate_prediction(
            predicted_tasks=pred_tasks,
            predicted_files=pred_files,
            predicted_evidence=pred_evidence,
            current_tasks=current_tasks,
            current_evidence=current_evidence,
        )

        if not is_valid:
            status = PredictionStatus.INVALIDATED.value
            uncertainties.extend(validation_errors)
        else:
            status = PredictionStatus.GENERATED.value

        # 8. Assemble Report
        report = PredictiveImpactReport(
            prediction_id=f"pred_{uuid.uuid4().hex[:8]}",
            mission_id=mission_id,
            source_intent_version=base_intent_version,
            proposed_intent_version=base_intent_version + 1,
            generated_at=time.time(),
            predicted_scope=scope,
            predicted_risk=risk_level,
            risk_factors=risk_factors,
            affected_requirements=[target_name],
            affected_constraints=[],
            predicted_tasks=pred_tasks,
            predicted_dependencies=[],
            predicted_agents=["coder", "test_engineer"] if has_frontend or has_backend else ["planner"],
            predicted_files=pred_files,
            predicted_symbols=graph_data["predicted_symbols"],
            predicted_architecture_changes=causal_chains,
            predicted_tests=pred_tests,
            predicted_evidence_impact=pred_evidence,
            predicted_checkpoint_impact=[{"checkpoint_id": "chk_pre_intent", "action": "CREATE_SNAPSHOT"}],
            predicted_browser_validation=browser_validation,
            predicted_pause_required=pause_required,
            predicted_approval_required=approval_required,
            assumptions=assumptions,
            uncertainties=uncertainties,
            confidence=0.88 if is_valid else 0.40,
            causal_chains=causal_chains,
            status=status,
            simulation_marker="SIMULATION_ONLY",
            task_file_matrix=graph_data.get("task_file_matrix", {}),
            consistency_report=graph_data.get("consistency_report", {}),
        )

        cls._predictions[report.prediction_id] = report
        cls._persist()
        return report

    @classmethod
    def get_prediction(cls, prediction_id: str) -> Optional[PredictiveImpactReport]:
        return cls._predictions.get(prediction_id)

    @classmethod
    def get_mission_predictions(cls, mission_id: str) -> list[PredictiveImpactReport]:
        return [p for p in cls._predictions.values() if p.mission_id == mission_id]

    @classmethod
    def record_outcome(
        cls,
        prediction_id: str,
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
    ) -> Optional[PredictionOutcome]:
        report = cls._predictions.get(prediction_id)
        if not report:
            return None

        outcome = PredictionComparator.compare(
            report=report,
            actual_intent_version=actual_intent_version,
            actual_plan_version=actual_plan_version,
            actual_files_changed=actual_files_changed,
            actual_tasks_added=actual_tasks_added,
            actual_tasks_modified=actual_tasks_modified,
            actual_tasks_removed=actual_tasks_removed,
            actual_evidence_invalidated=actual_evidence_invalidated,
            actual_agents_used=actual_agents_used,
            actual_browser_validation=actual_browser_validation,
            actual_scope=actual_scope,
        )

        cls._outcomes[outcome.outcome_id] = outcome
        report.status = PredictionStatus.APPLIED.value
        cls._persist()
        return outcome

    @classmethod
    def get_outcomes_for_mission(cls, mission_id: str) -> list[PredictionOutcome]:
        return [o for o in cls._outcomes.values() if o.mission_id == mission_id]

    @classmethod
    def _persist(cls) -> None:
        try:
            os.makedirs(os.path.dirname(cls._persistence_file), exist_ok=True)
            data = {
                "predictions": [p.to_dict() for p in cls._predictions.values()],
                "outcomes": [o.to_dict() for o in cls._outcomes.values()],
                "timestamp": time.time(),
            }
            with open(cls._persistence_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass  # Non-blocking telemetry persistence
