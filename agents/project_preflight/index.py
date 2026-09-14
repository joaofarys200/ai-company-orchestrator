"""
JARVIS OS — Phase 53: Universal Project Preflight & Runtime Failure Auto-Recovery
Project Preflight Index: Central repository for runtime profiles, preflight results,
diagnostics, repair plans, and the recovery ledger.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from agents.project_preflight.models import (
    PreflightResult,
    ProjectRuntimeProfile,
    RecoveryRun,
    RepairPlan,
    RuntimeDiagnostic,
)


class ProjectPreflightIndex:
    """
    In-memory and ledger repository for all Phase 53 preflight and recovery data.
    """

    def __init__(self) -> None:
        self.profiles: Dict[str, ProjectRuntimeProfile] = {}
        self.preflights: Dict[str, PreflightResult] = {}
        self.diagnostics: Dict[str, RuntimeDiagnostic] = {}
        self.repairs: Dict[str, RepairPlan] = {}
        self.recoveries: List[RecoveryRun] = []

    def register_profile(self, profile: ProjectRuntimeProfile) -> None:
        self.profiles[profile.project_id] = profile

    def get_profile(self, project_id: str) -> Optional[ProjectRuntimeProfile]:
        return self.profiles.get(project_id)

    def register_preflight(self, result: PreflightResult) -> None:
        self.preflights[result.preflight_id] = result

    def get_preflight(self, preflight_id: str) -> Optional[PreflightResult]:
        return self.preflights.get(preflight_id)

    def register_diagnostic(self, diagnostic: RuntimeDiagnostic) -> None:
        self.diagnostics[diagnostic.diagnostic_id] = diagnostic

    def get_diagnostic(self, diagnostic_id: str) -> Optional[RuntimeDiagnostic]:
        return self.diagnostics.get(diagnostic_id)

    def register_repair_plan(self, repair: RepairPlan) -> None:
        self.repairs[repair.repair_id] = repair

    def get_repair_plan(self, repair_id: str) -> Optional[RepairPlan]:
        return self.repairs.get(repair_id)

    def record_recovery_run(self, run: RecoveryRun) -> None:
        self.recoveries.append(run)

    def get_recovery_runs(self, project_id: Optional[str] = None) -> List[RecoveryRun]:
        if not project_id:
            return list(self.recoveries)
        return [r for r in self.recoveries if r.project_id == project_id]
