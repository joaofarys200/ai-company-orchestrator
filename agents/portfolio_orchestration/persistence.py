"""
JARVIS OS — Phase 75: Autonomous Engineering Strategy & Portfolio Orchestration
Module: persistence.py
Durable storage, state reconciliation, and crash recovery for portfolio orchestration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .models import (
    EngineeringInitiative,
    ExecutionSchedule,
    ExecutionScheduleItem,
    InitiativeState,
    MilestoneCheckpoint,
    PortfolioMetrics,
    PortfolioRoadmap,
    ReplanningEvent,
    ReplanningTriggerType,
)


class PortfolioStore:
    """
    Persists and recovers portfolio state, roadmaps, initiatives, and replanning logs.
    Reconciles in-flight initiatives with authoritative subsystems upon recovery.
    """

    def __init__(self, base_dir: str = ".jarvis/portfolio_orchestration"):
        self.base_dir = Path(base_dir)
        self.roadmaps_dir = self.base_dir / "roadmaps"
        self.initiatives_file = self.base_dir / "initiatives.json"
        self.replanning_file = self.base_dir / "replanning_events.json"
        self.metrics_file = self.base_dir / "metrics.json"

        self.roadmaps_dir.mkdir(parents=True, exist_ok=True)

    def save_roadmap(self, roadmap: PortfolioRoadmap) -> Path:
        """Persist a versioned roadmap."""
        from backend.atomic_io import atomic_write_json

        filepath = self.roadmaps_dir / f"{roadmap.roadmap_id}_{roadmap.version}.json"
        atomic_write_json(filepath, roadmap.to_dict(), indent=2)
        return filepath

    def load_roadmap(self, roadmap_id: str, version: Optional[str] = None) -> Optional[PortfolioRoadmap]:
        """Load a persisted roadmap by ID and optional version."""
        pattern = f"{roadmap_id}_*.json" if not version else f"{roadmap_id}_{version}.json"
        matches = list(self.roadmaps_dir.glob(pattern))
        if not matches:
            return None
        # Pick latest by modification time
        latest = sorted(matches, key=lambda p: p.stat().st_mtime, reverse=True)[0]
        with open(latest, "r", encoding="utf-8") as f:
            data = json.load(f)

        sched_data = data.get("schedule", {})
        schedule = ExecutionSchedule(
            schedule_id=sched_data.get("schedule_id", ""),
            portfolio_id=sched_data.get("portfolio_id", ""),
            items=[ExecutionScheduleItem(**it) for it in sched_data.get("items", [])],
            total_waves=sched_data.get("total_waves", 0),
            critical_path=sched_data.get("critical_path", []),
        )

        milestones = [
            MilestoneCheckpoint(**m) for m in data.get("milestones", [])
        ]

        return PortfolioRoadmap(
            roadmap_id=data["roadmap_id"],
            version=data["version"],
            portfolio_id=data["portfolio_id"],
            selected_initiatives=data.get("selected_initiatives", []),
            rejected_initiatives=data.get("rejected_initiatives", []),
            schedule=schedule,
            milestones=milestones,
            created_at=data.get("created_at", 0.0),
            status=data.get("status", "ACTIVE"),
            rationale=data.get("rationale", ""),
        )

    def save_initiatives(self, initiatives: Dict[str, EngineeringInitiative]) -> Path:
        """Persist normalized initiatives."""
        from backend.atomic_io import atomic_write_json

        payload = {init_id: init.to_dict() for init_id, init in initiatives.items()}
        atomic_write_json(self.initiatives_file, payload, indent=2)
        return self.initiatives_file

    def load_initiatives(self) -> Dict[str, EngineeringInitiative]:
        """Load persisted initiatives."""
        if not self.initiatives_file.exists():
            return {}
        with open(self.initiatives_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {init_id: EngineeringInitiative.from_dict(d) for init_id, d in data.items()}

    def record_replanning_event(self, event: ReplanningEvent) -> None:
        """Append a replanning event to the history log."""
        events = []
        if self.replanning_file.exists():
            try:
                with open(self.replanning_file, "r", encoding="utf-8") as f:
                    events = json.load(f)
            except Exception:
                events = []
        from backend.atomic_io import atomic_write_json

        events.append(event.to_dict())
        atomic_write_json(self.replanning_file, events, indent=2)

    def reconcile_and_recover(
        self,
        authoritative_checker: Optional[Callable[[str], InitiativeState]] = None,
    ) -> Dict[str, EngineeringInitiative]:
        """
        Recover persisted initiatives and reconcile any in-flight / EXECUTING initiatives
        against authoritative subsystem status.
        Never resume an initiative solely because it was persisted as EXECUTING.
        """
        initiatives = self.load_initiatives()
        for init_id, init in initiatives.items():
            if init.state == InitiativeState.EXECUTING:
                if authoritative_checker:
                    actual_state = authoritative_checker(init_id)
                    init.state = actual_state
                else:
                    # In absence of authoritative confirmation, reset to PROPOSED/FAILED to avoid ghost execution
                    init.state = InitiativeState.FAILED
                    init.error_message = "INTERRUPTED_EXECUTION: Unconfirmed in-flight state during crash recovery."
        self.save_initiatives(initiatives)
        return initiatives
