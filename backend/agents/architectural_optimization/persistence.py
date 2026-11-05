"""
JARVIS OS — Phase 74: Autonomous Architectural Evolution & Optimization
Module: persistence.py
JSON-backed persistence for optimization opportunities, hypotheses, experiments, and decisions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import (
    ArchitecturalAlternative,
    ArchitecturalMetricSnapshot,
    ExperimentOutcome,
    ExperimentRecord,
    OpportunityCategory,
    OptimizationDecision,
    OptimizationHypothesis,
    OptimizationOpportunity,
    OptimizationState,
    StructuralPatternType,
)


class OptimizationStore:
    """
    Persists and retrieves Phase 74 artifacts to and from durable JSON files.
    """

    def __init__(self, base_dir: str = ".jarvis/architectural_optimization"):
        self.base_dir = Path(base_dir)
        self.opps_dir = self.base_dir / "opportunities"
        self.hyps_dir = self.base_dir / "hypotheses"
        self.exps_dir = self.base_dir / "experiments"
        self.decs_dir = self.base_dir / "decisions"
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        self.opps_dir.mkdir(parents=True, exist_ok=True)
        self.hyps_dir.mkdir(parents=True, exist_ok=True)
        self.exps_dir.mkdir(parents=True, exist_ok=True)
        self.decs_dir.mkdir(parents=True, exist_ok=True)

    def save_opportunity(self, opportunity: OptimizationOpportunity) -> str:
        file_path = self.opps_dir / f"{opportunity.opportunity_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(opportunity.to_dict(), f, indent=2)
        return str(file_path)

    def load_opportunity(self, opportunity_id: str) -> Optional[OptimizationOpportunity]:
        file_path = self.opps_dir / f"{opportunity_id}.json"
        if not file_path.exists():
            return None
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        baseline = {}
        for k, v in data.get("baseline_metrics", {}).items():
            baseline[k] = ArchitecturalMetricSnapshot(
                metric_name=v["metric_name"],
                value=v["value"],
                sample_count=v.get("sample_count", 1),
                std_dev=v.get("std_dev", 0.0),
                unit=v.get("unit", ""),
                timestamp=v.get("timestamp", 0.0),
            )

        return OptimizationOpportunity(
            opportunity_id=data["opportunity_id"],
            title=data["title"],
            category=OpportunityCategory(data["category"]),
            affected_components=data.get("affected_components", []),
            supporting_evidence=data.get("supporting_evidence", []),
            baseline_metrics=baseline,
            severity_score=data.get("severity_score", 0.5),
            confidence_score=data.get("confidence_score", 0.8),
            discovered_at=data.get("discovered_at", 0.0),
            metadata=data.get("metadata", {}),
        )

    def save_hypothesis(self, hypothesis: OptimizationHypothesis) -> str:
        file_path = self.hyps_dir / f"{hypothesis.hypothesis_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(hypothesis.to_dict(), f, indent=2)
        return str(file_path)

    def save_experiment(self, experiment: ExperimentRecord) -> str:
        file_path = self.exps_dir / f"{experiment.experiment_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(experiment.to_dict(), f, indent=2)
        return str(file_path)

    def save_decision(self, decision: OptimizationDecision) -> str:
        file_path = self.decs_dir / f"{decision.decision_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(decision.to_dict(), f, indent=2)
        return str(file_path)
