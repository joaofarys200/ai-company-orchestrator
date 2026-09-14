"""
JARVIS OS — Phase 40: Autonomous Engineering Loop & Closed-Loop Mission Adaptation
Observable Telemetry Collector & Evidence Verification.

Strict Rule:
"Agent says it worked" is NOT evidence.
All observations must be backed by verifiable execution artifacts, exit codes,
test results, AST diagnostics, browser QA outputs, or physical filesystem touches.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import os
import time
from typing import Any, Dict, List, Optional


@dataclass
class ObservedTaskResult:
    task_id: str
    owner_agent: str
    status: str  # COMPLETED, FAILED, RUNNING, PENDING
    exit_code: int
    files_touched: list[str] = field(default_factory=list)
    artifacts_created: list[str] = field(default_factory=list)
    error_message: Optional[str] = None
    execution_duration_seconds: float = 0.0


@dataclass
class ObservedValidationResult:
    validation_type: str  # TEST, BUILD, LINT, AST, BROWSER
    target: str
    passed: bool
    summary: str
    evidence_id: Optional[str] = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class LoopObservation:
    observation_id: str
    cycle_id: str
    mission_id: str
    timestamp: float = field(default_factory=time.time)
    task_results: list[ObservedTaskResult] = field(default_factory=list)
    validations: list[ObservedValidationResult] = field(default_factory=list)
    files_changed: list[str] = field(default_factory=list)
    active_failures: list[dict[str, Any]] = field(default_factory=list)
    evidence_ids_collected: list[str] = field(default_factory=list)
    all_tasks_completed: bool = False
    all_validations_passed: bool = True
    build_clean: bool = True
    tests_clean: bool = True
    ast_clean: bool = True
    browser_clean: bool = True
    has_unrepairable_failure: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["task_results"] = [asdict(t) for t in self.task_results]
        d["validations"] = [asdict(v) for v in self.validations]
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LoopObservation:
        data_copy = dict(data)
        if "task_results" in data_copy:
            data_copy["task_results"] = [
                ObservedTaskResult(**t) if isinstance(t, dict) else t
                for t in data_copy["task_results"]
            ]
        if "validations" in data_copy:
            data_copy["validations"] = [
                ObservedValidationResult(**v) if isinstance(v, dict) else v
                for v in data_copy["validations"]
            ]
        return cls(**{k: v for k, v in data_copy.items() if k in cls.__dataclass_fields__})


class AutonomousLoopObserver:
    """
    Collects observable facts from tasks, tests, build, AST diagnostics, and browser assertions.
    """

    @classmethod
    def observe(
        cls,
        mission_id: str,
        cycle_id: str,
        task_executions: list[dict[str, Any]],
        validation_reports: Optional[list[dict[str, Any]]] = None,
        workspace_root: Optional[str] = None,
    ) -> LoopObservation:
        obs_id = f"obs_{cycle_id}_{int(time.time() * 1000) % 100000}"
        tasks: list[ObservedTaskResult] = []
        validations: list[ObservedValidationResult] = []
        files_touched_set: set[str] = set()
        evidence_ids: list[str] = []
        failures: list[dict[str, Any]] = []

        all_tasks_completed = True
        all_validations_passed = True
        build_clean = True
        tests_clean = True
        ast_clean = True
        browser_clean = True
        has_unrepairable = False

        for t in task_executions:
            status = str(t.get("status", "PENDING")).upper()
            exit_code = int(t.get("exit_code", 0 if status == "COMPLETED" else 1))
            files = t.get("files_touched", []) or []
            artifacts = t.get("artifacts_created", []) or []
            err = t.get("error_message")

            for f in files:
                files_touched_set.add(f)
            for a in artifacts:
                files_touched_set.add(a)

            if status != "COMPLETED":
                all_tasks_completed = False

            if exit_code != 0 or status == "FAILED":
                is_repairable = bool(t.get("is_repairable", False))
                if not is_repairable:
                    # check if error looks like syntax or null pointer (repairable AST)
                    err_lower = (err or "").lower()
                    if any(w in err_lower for w in ("syntax", "indentation", "null", "none", "cannot read property", "undefined", "typeerror", "attributeerror")):
                        is_repairable = True
                    else:
                        has_unrepairable = True

                failures.append({
                    "task_id": t.get("task_id", ""),
                    "error": err or "Task failed with non-zero exit code",
                    "exit_code": exit_code,
                    "is_repairable": is_repairable,
                    "target_file": files[0] if files else "",
                    "timestamp": time.time(),
                })

            tasks.append(
                ObservedTaskResult(
                    task_id=str(t.get("task_id", "")),
                    owner_agent=str(t.get("owner_agent", "swarm_worker")),
                    status=status,
                    exit_code=exit_code,
                    files_touched=files,
                    artifacts_created=artifacts,
                    error_message=err,
                    execution_duration_seconds=float(t.get("execution_duration_seconds", 0.0)),
                )
            )

        for v in (validation_reports or []):
            v_type = str(v.get("validation_type", "TEST")).upper()
            target = str(v.get("target", ""))
            passed = bool(v.get("passed", True))
            summary = str(v.get("summary", ""))
            ev_id = v.get("evidence_id")
            details = v.get("details", {})

            if ev_id:
                evidence_ids.append(ev_id)

            if not passed:
                all_validations_passed = False
                if v_type == "BUILD":
                    build_clean = False
                elif v_type == "TEST":
                    tests_clean = False
                elif v_type == "AST":
                    ast_clean = False
                elif v_type == "BROWSER":
                    browser_clean = False

                failures.append({
                    "validation_type": v_type,
                    "target": target,
                    "error": summary,
                    "is_repairable": bool(v.get("is_repairable", True if v_type in ("AST", "BUILD", "TEST") else False)),
                    "timestamp": time.time(),
                })

            validations.append(
                ObservedValidationResult(
                    validation_type=v_type,
                    target=target,
                    passed=passed,
                    summary=summary,
                    evidence_id=ev_id,
                    details=details,
                )
            )

        return LoopObservation(
            observation_id=obs_id,
            cycle_id=cycle_id,
            mission_id=mission_id,
            task_results=tasks,
            validations=validations,
            files_changed=sorted(list(files_touched_set)),
            active_failures=failures,
            evidence_ids_collected=evidence_ids,
            all_tasks_completed=all_tasks_completed and (len(tasks) > 0),
            all_validations_passed=all_validations_passed,
            build_clean=build_clean,
            tests_clean=tests_clean,
            ast_clean=ast_clean,
            browser_clean=browser_clean,
            has_unrepairable_failure=has_unrepairable,
        )
