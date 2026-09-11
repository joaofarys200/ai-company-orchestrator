"""
JARVIS OS — Phase 39.2: Plan-to-Impact Consistency Validator

Enforces the 9 structural invariants between Impacted Files and Predicted Tasks:
1. Every FILE_DRIVEN task references at least one impacted file
2. Every executable impacted file is covered by at least one task
3. Non-file tasks specify explicit semantic sources (requirement, architecture, validation)
4. No task points to ungrounded or empty file paths
5. No duplicate predicted task IDs
6. Dependencies resolve to existing or predicted tasks
7. Predicted task dependency graph is strictly acyclic (DAG)
8. Task source is traceable (causal traceability)
9. Task category matches standard Mission Planner taxonomy

Verdicts:
- CONSISTENT
- INCONSISTENT
- PARTIALLY_TRACEABLE
"""

from __future__ import annotations

from typing import Any, Dict, List, Set

from intelligence.predictive_impact.models import (
    ConsistencyVerdict,
    PredictedFile,
    PredictedTask,
    TaskCategory,
    TaskDerivationType,
)


class TaskImpactConsistencyValidator:
    """
    Validates plan-to-impact structural integrity and causal consistency.
    """

    ALLOWED_CATEGORIES = {cat.value for cat in TaskCategory}

    @classmethod
    def validate(
        cls,
        predicted_tasks: list[PredictedTask] | list[dict[str, Any]],
        predicted_files: list[PredictedFile] | list[dict[str, Any]],
        current_tasks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        issues: list[dict[str, Any]] = []
        checks_passed = 0
        checks_total = 9

        # Normalize tasks
        tasks: list[dict[str, Any]] = []
        for t in predicted_tasks:
            if isinstance(t, PredictedTask):
                tasks.append(t.to_dict())
            elif isinstance(t, dict):
                tasks.append(t)

        # Normalize files
        files: list[str] = []
        for f in predicted_files:
            if isinstance(f, PredictedFile):
                files.append(f.file_path)
            elif isinstance(f, dict):
                files.append(f.get("file_path", ""))
        file_set = {fp for fp in files if fp}

        current_task_ids = {ct.get("id") for ct in (current_tasks or []) if ct.get("id")}
        pred_task_ids = {t.get("predicted_task_id") for t in tasks if t.get("predicted_task_id")}
        all_valid_task_ids = current_task_ids.union(pred_task_ids)

        # -------------------------------------------------------------
        # Invariant 1: File-driven tasks must possess at least 1 file
        # -------------------------------------------------------------
        inv1_failed = False
        for t in tasks:
            dtype = t.get("derivation_type", "")
            pfiles = t.get("predicted_files", [])
            if dtype in (TaskDerivationType.DIRECT_FILE_IMPACT.value, TaskDerivationType.DOWNSTREAM_FILE_IMPACT.value):
                if not pfiles:
                    issues.append({
                        "invariant": 1,
                        "severity": "ERROR",
                        "task_id": t.get("predicted_task_id"),
                        "message": f"Task {t.get('predicted_task_id')} is {dtype} but has no predicted_files",
                    })
                    inv1_failed = True
        if not inv1_failed:
            checks_passed += 1

        # -------------------------------------------------------------
        # Invariant 2: Impacted files must be mapped to at least 1 task
        # -------------------------------------------------------------
        all_task_files: Set[str] = set()
        for t in tasks:
            all_task_files.update(t.get("predicted_files", []))

        uncovered_files = file_set.difference(all_task_files)
        if uncovered_files:
            issues.append({
                "invariant": 2,
                "severity": "WARNING",
                "files": list(uncovered_files),
                "message": f"{len(uncovered_files)} impacted file(s) are not referenced by any predicted task",
            })
        else:
            checks_passed += 1

        # -------------------------------------------------------------
        # Invariant 3: Tasks without files must have explicit semantic source
        # -------------------------------------------------------------
        inv3_failed = False
        for t in tasks:
            pfiles = t.get("predicted_files", [])
            if not pfiles:
                has_semantic_source = bool(
                    t.get("source_requirement")
                    or t.get("source_requirements")
                    or t.get("source_constraints")
                    or t.get("derived_from")
                    or t.get("reason")
                )
                if not has_semantic_source:
                    issues.append({
                        "invariant": 3,
                        "severity": "ERROR",
                        "task_id": t.get("predicted_task_id"),
                        "message": f"Task {t.get('predicted_task_id')} has no files and no semantic source",
                    })
                    inv3_failed = True
        if not inv3_failed:
            checks_passed += 1

        # -------------------------------------------------------------
        # Invariant 4: No task points to non-existent or blank file paths
        # -------------------------------------------------------------
        inv4_failed = False
        for t in tasks:
            for fp in t.get("predicted_files", []):
                if not fp or not isinstance(fp, str) or not fp.strip():
                    issues.append({
                        "invariant": 4,
                        "severity": "ERROR",
                        "task_id": t.get("predicted_task_id"),
                        "message": "Task references an empty or invalid file path string",
                    })
                    inv4_failed = True
        if not inv4_failed:
            checks_passed += 1

        # -------------------------------------------------------------
        # Invariant 5: No duplicate predicted task IDs
        # -------------------------------------------------------------
        seen_ids: Set[str] = set()
        inv5_failed = False
        for t in tasks:
            tid = t.get("predicted_task_id", "")
            if tid in seen_ids:
                issues.append({
                    "invariant": 5,
                    "severity": "ERROR",
                    "task_id": tid,
                    "message": f"Duplicate predicted_task_id: {tid}",
                })
                inv5_failed = True
            seen_ids.add(tid)
        if not inv5_failed:
            checks_passed += 1

        # -------------------------------------------------------------
        # Invariant 6: Valid dependencies (must exist in current or predicted)
        # -------------------------------------------------------------
        inv6_failed = False
        for t in tasks:
            for dep in t.get("dependencies", []):
                if dep not in all_valid_task_ids:
                    issues.append({
                        "invariant": 6,
                        "severity": "ERROR",
                        "task_id": t.get("predicted_task_id"),
                        "dependency": dep,
                        "message": f"Dependency {dep} does not exist in current or predicted task sets",
                    })
                    inv6_failed = True
        if not inv6_failed:
            checks_passed += 1

        # -------------------------------------------------------------
        # Invariant 7: Acyclic task graph (DAG - no cycles)
        # -------------------------------------------------------------
        dep_graph: dict[str, list[str]] = {t.get("predicted_task_id"): t.get("dependencies", []) for t in tasks if t.get("predicted_task_id")}
        visited: dict[str, int] = {}  # 0=unvisited, 1=visiting, 2=visited
        has_cycle = False

        def check_cycle(node: str) -> bool:
            visited[node] = 1
            for neighbor in dep_graph.get(node, []):
                if neighbor in dep_graph:
                    if visited.get(neighbor) == 1:
                        return True
                    if visited.get(neighbor, 0) == 0:
                        if check_cycle(neighbor):
                            return True
            visited[node] = 2
            return False

        for node in dep_graph:
            if visited.get(node, 0) == 0:
                if check_cycle(node):
                    has_cycle = True
                    break

        if has_cycle:
            issues.append({
                "invariant": 7,
                "severity": "ERROR",
                "message": "Cycle detected in predicted task dependency graph",
            })
        else:
            checks_passed += 1

        # -------------------------------------------------------------
        # Invariant 8: Traceable task source
        # -------------------------------------------------------------
        inv8_failed = False
        for t in tasks:
            if not t.get("source_requirement") and not t.get("source_requirements"):
                issues.append({
                    "invariant": 8,
                    "severity": "WARNING",
                    "task_id": t.get("predicted_task_id"),
                    "message": f"Task {t.get('predicted_task_id')} has untraceable requirement source",
                })
                inv8_failed = True
        if not inv8_failed:
            checks_passed += 1

        # -------------------------------------------------------------
        # Invariant 9: Valid task category within taxonomy
        # -------------------------------------------------------------
        inv9_failed = False
        for t in tasks:
            cat = t.get("category", "")
            if cat not in cls.ALLOWED_CATEGORIES:
                issues.append({
                    "invariant": 9,
                    "severity": "ERROR",
                    "task_id": t.get("predicted_task_id"),
                    "category": cat,
                    "message": f"Task category '{cat}' is not in allowed taxonomy: {cls.ALLOWED_CATEGORIES}",
                })
                inv9_failed = True
        if not inv9_failed:
            checks_passed += 1

        # Verdict calculation
        errors = [i for i in issues if i.get("severity") == "ERROR"]
        warnings = [i for i in issues if i.get("severity") == "WARNING"]

        if errors:
            verdict = ConsistencyVerdict.INCONSISTENT.value
        elif warnings:
            verdict = ConsistencyVerdict.PARTIALLY_TRACEABLE.value
        else:
            verdict = ConsistencyVerdict.CONSISTENT.value

        return {
            "verdict": verdict,
            "is_valid": len(errors) == 0,
            "checks_passed": checks_passed,
            "checks_total": checks_total,
            "issues": issues,
            "task_count": len(tasks),
            "file_count": len(file_set),
        }
