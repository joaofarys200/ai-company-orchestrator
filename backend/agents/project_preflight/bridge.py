"""
JARVIS OS — Phase 53: Universal Project Preflight & Runtime Failure Auto-Recovery
Project Preflight Bridge: Unified master orchestrator connecting Preflight, Runtime Diagnostics,
Safe Repair Planning, Policy Authorization, Healthcheck Probing, and Reversible Auto-Recovery.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from agents.project_preflight.cache import DeterministicFailureCache
from agents.project_preflight.config import ConfigValidator
from agents.project_preflight.dependencies import DependencyValidator
from agents.project_preflight.detector import ProjectProfileDetector
from agents.project_preflight.diagnostics import RuntimeDiagnosticEngine
from agents.project_preflight.entrypoint import EntrypointValidator
from agents.project_preflight.healthcheck import HealthcheckEngine
from agents.project_preflight.index import ProjectPreflightIndex
from agents.project_preflight.javascript import JavaScriptPreflightAnalyzer
from agents.project_preflight.metrics import PreflightTelemetry
from agents.project_preflight.models import (
    FailureFingerprint,
    IssueSeverity,
    LanguageType,
    PreflightGateDecision,
    PreflightIssue,
    PreflightPolicy,
    PreflightResult,
    ProjectRuntimeProfile,
    RecoveryRun,
    RepairCategory,
    RepairConfidence,
    RepairPlan,
    RuntimeDiagnostic,
    StartupHealthResult,
    compute_deterministic_hash,
)
from agents.project_preflight.policy import PreflightPolicyEngine
from agents.project_preflight.python import PythonPreflightAnalyzer
from agents.project_preflight.repair import SafeRepairPlanner
from agents.project_preflight.security import PreflightSecuritySentinel
from agents.project_preflight.typescript import TypeScriptPreflightAnalyzer
from agents.project_preflight.validator import PreflightProofValidator


class ProjectPreflightBridge:
    """
    Master coordinator for project preflight and runtime auto-recovery boundary.
    """

    def __init__(self) -> None:
        self.detector = ProjectProfileDetector()
        self.js_analyzer = JavaScriptPreflightAnalyzer()
        self.ts_analyzer = TypeScriptPreflightAnalyzer()
        self.py_analyzer = PythonPreflightAnalyzer()
        self.dependency_validator = DependencyValidator()
        self.entrypoint_validator = EntrypointValidator()
        self.config_validator = ConfigValidator()
        self.healthcheck_engine = HealthcheckEngine()
        self.diagnostic_engine = RuntimeDiagnosticEngine()
        self.repair_planner = SafeRepairPlanner()
        self.policy_engine = PreflightPolicyEngine()
        self.security_sentinel = PreflightSecuritySentinel()
        self.telemetry = PreflightTelemetry()
        self.cache = DeterministicFailureCache()
        self.validator = PreflightProofValidator()
        self.index = ProjectPreflightIndex()

    def _compute_workspace_hash(self, root_dir: str) -> str:
        """Computes a lightweight hash of project file names and mtimes for read-only invariant."""
        try:
            items = []
            for root, dirs, files in os.walk(root_dir):
                dirs[:] = [d for d in dirs if d not in ("node_modules", ".git", "venv", "__pycache__", ".venv")]
                for f in sorted(files):
                    p = os.path.join(root, f)
                    try:
                        st = os.stat(p)
                        items.append(f"{os.path.relpath(p, root_dir)}:{st.st_mtime_ns}:{st.st_size}")
                    except OSError:
                        pass
            return hashlib.sha256(";".join(items).encode("utf-8")).hexdigest()[:16]
        except Exception:
            return "hash_unavailable"

    def run_preflight(
        self,
        root_dir: str,
        project_id: Optional[str] = None,
        policy: PreflightPolicy = PreflightPolicy.STANDARD,
    ) -> PreflightResult:
        """
        Executes read-only preflight analysis.
        Enforces state_before_hash == state_after_hash.
        """
        t0 = time.perf_counter()
        root = os.path.realpath(os.path.abspath(root_dir))
        p_id = project_id or os.path.basename(root)

        state_before = self._compute_workspace_hash(root)
        self.telemetry.emit_event("preflight_started", project_id=p_id)

        # 1. Detect profile
        profile = self.detector.detect_profile(root, p_id)
        self.index.register_profile(profile)

        issues: List[PreflightIssue] = []

        # 2. Dependency validation
        issues.extend(self.dependency_validator.validate_dependencies(root, profile))

        # 3. Entrypoint validation
        issues.extend(self.entrypoint_validator.validate_entrypoint(root, profile))

        # 4. Config & Port validation
        issues.extend(self.config_validator.validate_config(root, profile))

        # 5. Language specific AST / syntax checks
        if profile.entrypoint:
            entry_full = os.path.join(root, profile.entrypoint)
            if profile.language == LanguageType.JAVASCRIPT:
                issues.extend(self.js_analyzer.analyze_file(entry_full, profile))
            elif profile.language == LanguageType.TYPESCRIPT:
                issues.extend(self.ts_analyzer.analyze(root, profile))
            elif profile.language == LanguageType.PYTHON:
                issues.extend(self.py_analyzer.analyze_file(entry_full, profile))

        # Read-only verification
        state_after = self._compute_workspace_hash(root)
        can_proceed = not any(i.severity == IssueSeverity.BLOCKER for i in issues)

        preflight_id = compute_deterministic_hash(
            {"p": p_id, "issues": len(issues), "can": can_proceed}, prefix="pre_"
        )
        duration_ms = (time.perf_counter() - t0) * 1000.0

        result = PreflightResult(
            preflight_id=preflight_id,
            project_id=p_id,
            policy=policy,
            can_proceed=can_proceed,
            issues=issues,
            state_hash_before=state_before,
            state_hash_after=state_after,
            duration_ms=duration_ms,
        )

        self.index.register_preflight(result)
        evt_name = "preflight_completed" if can_proceed else "preflight_blocked"
        self.telemetry.emit_event(
            evt_name,
            project_id=p_id,
            provenance={"duration_ms": duration_ms, "issues_count": len(issues)},
        )
        return result

    def diagnose_failure(
        self, logs: List[str] | str, root_dir: str, project_id: str
    ) -> Optional[RuntimeDiagnostic]:
        """Maps logs to a structured diagnostic and records it in index."""
        diagnostic = self.diagnostic_engine.diagnose_crash(logs, root_dir)
        if diagnostic:
            self.index.register_diagnostic(diagnostic)
            self.telemetry.emit_event(
                "diagnostic_created",
                project_id=project_id,
                diagnostic_id=diagnostic.diagnostic_id,
                confidence=str(diagnostic.confidence),
                provenance={"error_class": diagnostic.error_class.value, "symbol": diagnostic.symbol},
            )
        return diagnostic

    def plan_and_apply_recovery(
        self,
        diagnostic: RuntimeDiagnostic,
        root_dir: str,
        project_id: str,
        policy: PreflightPolicy = PreflightPolicy.STANDARD,
        attempt_number: int = 1,
        is_economic: bool = False,
        is_security_critical: bool = False,
    ) -> RecoveryRun:
        """
        Executes the recovery loop:
        DIAGNOSE -> PLAN -> GATE -> REPAIR -> VERIFY (or ROLLBACK)
        """
        t0 = time.perf_counter()
        profile = self.index.get_profile(project_id) or self.detector.detect_profile(root_dir, project_id)

        # 1. Plan Repair
        repair_plan = self.repair_planner.plan_repair(diagnostic, root_dir, profile)
        recovery_id = compute_deterministic_hash(
            {"p": project_id, "diag": diagnostic.diagnostic_id, "att": attempt_number},
            prefix="rec_",
        )

        if not repair_plan:
            run = RecoveryRun(
                recovery_id=recovery_id,
                project_id=project_id,
                attempt_number=attempt_number,
                diagnostic=diagnostic,
                repair_plan=RepairPlan(
                    repair_id="rep_none",
                    diagnostic_id=diagnostic.diagnostic_id,
                    category=RepairCategory.IMPORT_MISSING,
                    confidence=RepairConfidence.LOW_CONFIDENCE,
                    reason="Não foi possível derivar um plano de reparação determinístico.",
                ),
                gate_decision=PreflightGateDecision.EXECUTION_BLOCKED,
                was_applied=False,
                was_successful=False,
                duration_ms=(time.perf_counter() - t0) * 1000.0,
            )
            self.index.record_recovery_run(run)
            return run

        self.index.register_repair_plan(repair_plan)

        # 2. Security Sentinel Sovereign Inspection
        self.security_sentinel.inspect_repair_plan(
            repair_plan, is_economic=is_economic, is_security_critical=is_security_critical
        )

        # 3. Policy Gate Evaluation
        gate_decision, gate_reason = self.policy_engine.evaluate_repair_gate(
            repair_plan=repair_plan, policy=policy, attempt_number=attempt_number
        )

        was_applied = False
        was_successful = False
        rolled_back = False
        rollback_reason = None

        if gate_decision == PreflightGateDecision.GATE_CLEARED:
            # Apply repair atomically
            applied = self.repair_planner.apply_repair(repair_plan, root_dir)
            if applied:
                was_applied = True
                self.telemetry.emit_event(
                    "repair_applied",
                    project_id=project_id,
                    repair_id=repair_plan.repair_id,
                    confidence=repair_plan.confidence.value,
                )

                # Post-repair preflight verification
                post_preflight = self.run_preflight(root_dir, project_id, policy)
                if post_preflight.can_proceed:
                    was_successful = True
                    # Record in Experience Memory / Cache
                    fp = FailureFingerprint(
                        runtime=profile.runtime.value,
                        error_class=diagnostic.error_class.value,
                        file_name=os.path.basename(diagnostic.file_path or ""),
                        line=diagnostic.line,
                        symbol=diagnostic.symbol,
                        normalized_message=diagnostic.message,
                    )
                    self.cache.record_repair_outcome(fp, repair_plan, success=True)
                else:
                    # Rollback
                    self.repair_planner.rollback_repair(repair_plan, root_dir)
                    rolled_back = True
                    rollback_reason = f"Preflight pós-reparação falhou: {post_preflight.issues[0].message if post_preflight.issues else 'Erros pendentes'}"
                    self.telemetry.emit_event(
                        "repair_rolled_back",
                        project_id=project_id,
                        repair_id=repair_plan.repair_id,
                        provenance={"reason": rollback_reason},
                    )

        duration_ms = (time.perf_counter() - t0) * 1000.0
        run = RecoveryRun(
            recovery_id=recovery_id,
            project_id=project_id,
            attempt_number=attempt_number,
            diagnostic=diagnostic,
            repair_plan=repair_plan,
            gate_decision=gate_decision,
            was_applied=was_applied,
            was_successful=was_successful,
            rolled_back=rolled_back,
            rollback_reason=rollback_reason,
            duration_ms=duration_ms,
        )
        self.index.record_recovery_run(run)
        return run

    def probe_health(
        self,
        port: int,
        path: str = "/",
        process: Optional[Any] = None,
        timeout_seconds: float = 4.0,
    ) -> StartupHealthResult:
        """Performs healthcheck probe on the project socket."""
        return self.healthcheck_engine.probe_health(
            port=port, path=path, process=process, timeout_seconds=timeout_seconds
        )
