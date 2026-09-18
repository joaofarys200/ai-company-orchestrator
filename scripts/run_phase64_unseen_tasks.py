"""
JARVIS OS — Phase 64: Unseen Architecture Tasks Evaluator
Runs and records 12 distinct unseen architectural evolution tasks across
different architectural smells, boundary patterns, and security constraints.
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict, List

# Ensure repository root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.agents.architecture_evolution.bridge import ArchitectureEvolutionBridge
from backend.agents.architecture_evolution.models import (
    ArchitectureSnapshot,
    ProblemCategory,
    ProblemSeverity,
)

TASKS_DEF = [
    {
        "id": "TASK-01",
        "name": "monolithic_coupling",
        "category": ProblemCategory.COUPLING,
        "severity": ProblemSeverity.HIGH,
        "nodes": ["core/monolith.py"] + [f"sub_{i}.py" for i in range(10)],
        "dependencies": [("core/monolith.py", f"sub_{i}.py") for i in range(10)],
        "description": "Monolithic core component with excessive direct fan-out (10 dependencies).",
    },
    {
        "id": "TASK-02",
        "name": "circular_dependency",
        "category": ProblemCategory.SCC,
        "severity": ProblemSeverity.HIGH,
        "nodes": ["service/alpha.py", "service/beta.py", "service/gamma.py"],
        "dependencies": [
            ("service/alpha.py", "service/beta.py"),
            ("service/beta.py", "service/gamma.py"),
            ("service/gamma.py", "service/alpha.py"),
        ],
        "sccs": [["service/alpha.py", "service/beta.py", "service/gamma.py"]],
        "description": "Mutual 3-node cyclic dependency blocking independent container compilation.",
    },
    {
        "id": "TASK-03",
        "name": "service_boundary",
        "category": ProblemCategory.BOUNDARY,
        "severity": ProblemSeverity.CRITICAL,
        "nodes": ["backend/services/payment.py", "frontend/components/checkout.tsx"],
        "dependencies": [("backend/services/payment.py", "frontend/components/checkout.tsx")],
        "description": "Layer inversion: backend service directly importing frontend component.",
    },
    {
        "id": "TASK-04",
        "name": "contract_concentration",
        "category": ProblemCategory.CONTRACT,
        "severity": ProblemSeverity.MEDIUM,
        "nodes": ["contracts/global_api_v1.json"],
        "consumers": {"contracts/global_api_v1.json": [f"consumer_{i}" for i in range(8)]},
        "description": "Over 8 distinct micro-clients tightly coupled to unversioned monolithic payload.",
    },
    {
        "id": "TASK-05",
        "name": "database_coupling",
        "category": ProblemCategory.COUPLING,
        "severity": ProblemSeverity.MEDIUM,
        "nodes": ["db/transactions_table", "services/audit.py", "services/billing.py"],
        "persistence_edges": [
            {"source": "services/audit.py", "table": "transactions_table"},
            {"source": "services/billing.py", "table": "transactions_table"},
        ],
        "description": "Shared raw table mutation causing transaction lock contention.",
    },
    {
        "id": "TASK-06",
        "name": "event_driven_migration",
        "category": ProblemCategory.RELIABILITY,
        "severity": ProblemSeverity.MEDIUM,
        "nodes": ["sync/event_emitter.py", "sync/subscriber_pool.py"],
        "communication_edges": [
            {"source": "ui_sync_emitter", "target": "backend_worker", "type": "tight_sync_rpc"}
        ],
        "description": "Synchronous request-reply cascade vulnerable to network timeouts.",
    },
    {
        "id": "TASK-07",
        "name": "retry_architecture",
        "category": ProblemCategory.COUPLING,
        "severity": ProblemSeverity.MEDIUM,
        "nodes": ["network/http_client.py"] + [f"endpoint_{i}" for i in range(9)],
        "dependencies": [("network/http_client.py", f"endpoint_{i}") for i in range(9)],
        "description": "HTTP client with excessive outward dependencies and unbuffered retries.",
    },
    {
        "id": "TASK-08",
        "name": "browser_backend_coupling",
        "category": ProblemCategory.BOUNDARY,
        "severity": ProblemSeverity.CRITICAL,
        "nodes": ["backend/raw_sql_query.py", "frontend/views/Dashboard.tsx"],
        "dependencies": [("backend/raw_sql_query.py", "frontend/views/Dashboard.tsx")],
        "description": "Browser UI bypassing API gateway and directly bound to raw backend queries.",
    },
    {
        "id": "TASK-09",
        "name": "security_boundary",
        "category": ProblemCategory.SECURITY,
        "severity": ProblemSeverity.HIGH,
        "nodes": ["auth/token_signer.py"],
        "external_boundaries": ["dynamic_reflection_eval_signer"],
        "description": "Dynamic reflection boundary in security token signer.",
    },
    {
        "id": "TASK-10",
        "name": "high_fan_out_symbol",
        "category": ProblemCategory.MAINTAINABILITY,
        "nodes": ["utils/helpers.py"] + [f"caller_{i}" for i in range(14)],
        "dependencies": [(f"caller_{i}", "utils/helpers.py") for i in range(14)],
        "description": "Utility function referenced by 14 distinct callers as a fan-in hub.",
    },
    {
        "id": "TASK-11",
        "name": "dynamic_reflection_boundary",
        "category": ProblemCategory.SECURITY,
        "severity": ProblemSeverity.HIGH,
        "nodes": ["plugins/loader.py"],
        "external_boundaries": ["dynamic_eval_loader"],
        "description": "Dynamic eval invocation of external modules without sandbox boundary.",
    },
    {
        "id": "TASK-12",
        "name": "cross_language_architecture_proposal",
        "category": ProblemCategory.SCC,
        "severity": ProblemSeverity.HIGH,
        "nodes": ["python_backend/worker.py", "typescript_edge/handler.ts", "shared_contract.py"],
        "dependencies": [
            ("python_backend/worker.py", "typescript_edge/handler.ts"),
            ("typescript_edge/handler.ts", "shared_contract.py"),
            ("shared_contract.py", "python_backend/worker.py"),
        ],
        "sccs": [["python_backend/worker.py", "typescript_edge/handler.ts", "shared_contract.py"]],
        "description": "Heterogeneous cross-language cyclic coupling loop.",
    },
]


def run_unseen_tasks() -> Dict[str, Any]:
    print("=" * 75)
    print("EVALUATING 12 UNSEEN ARCHITECTURE EVOLUTION TASKS")
    print("=" * 75)

    ArchitectureEvolutionBridge.reset_instance()
    bridge = ArchitectureEvolutionBridge.get_instance(db_path=":memory:")

    results: List[Dict[str, Any]] = []

    for task in TASKS_DEF:
        t_id = task["id"]
        name = task["name"]
        print(f"\nProcessing {t_id}: {name} ({task['category'].value})...")

        snap = ArchitectureSnapshot(
            snapshot_id=f"snap_{name}",
            files=task["nodes"],
            symbols=[f"{n}::Symbol" for n in task["nodes"]],
            dependencies=task.get("dependencies", []),
            sccs=task.get("sccs", []),
            consumers=task.get("consumers", {}),
            persistence_edges=task.get("persistence_edges", []),
            communication_edges=task.get("communication_edges", []),
            risk_zones=["auth_zone"] if task["category"] == ProblemCategory.SECURITY else [],
            external_boundaries=task.get("external_boundaries", []),
            test_surfaces=[f"tests/test_{name}.py"],
        )
        bridge.register_snapshot(snap)

        problems = bridge.observe_and_detect_problems(f"snap_{name}")
        prob = problems[0] if problems else None

        if prob:
            eval_res = bridge.evaluate_problem(
                problem_id=prob.problem_id,
                snapshot_id=f"snap_{name}",
                policy_name="STANDARD",
            )
            # Pick primary alternative
            alts = eval_res["alternatives"]
            primary_alt = alts[1] if len(alts) > 1 else alts[0]
            primary_alt_id = primary_alt["alternative_id"]
            gov_dec = eval_res["governance_decisions"].get(primary_alt_id, {})

            task_summary = {
                "task_id": t_id,
                "name": name,
                "problem": eval_res["problem"],
                "constraints_count": len(eval_res["constraints"]),
                "alternatives_count": len(eval_res["alternatives"]),
                "primary_alternative": primary_alt,
                "impact": eval_res["impacts"].get(primary_alt_id),
                "contract_status": eval_res["contracts"].get(primary_alt_id, {}).get("status"),
                "behavior_status": eval_res["behaviors"].get(primary_alt_id, {}).get("status"),
                "risk_criticality": eval_res["risks"].get(primary_alt_id, {}).get("criticality"),
                "cost_hours": eval_res["costs"].get(primary_alt_id, {}).get("total_estimated_effort_hours"),
                "migration_steps": len(eval_res["migration_plans"].get(primary_alt_id, {}).get("steps", [])),
                "simulation_status": eval_res["simulations"].get(primary_alt_id, {}).get("status"),
                "verification_requirements": len(eval_res["verification_plans"].get(primary_alt_id, {}).get("required_tests", [])),
                "governance_decision": gov_dec.get("state", "OBSERVATION_ONLY"),
                "reason": gov_dec.get("reason", "Observation logged"),
            }
            results.append(task_summary)
            print(f"  Verdict: {task_summary['governance_decision']} | Simulation: {task_summary['simulation_status']} | Effort: {task_summary['cost_hours']}h")

    out_path = os.path.join("docs", "phase64_unseen_tasks.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 75)
    print(f"UNSEEN TASKS COMPLETED: {len(results)}/12 evaluated and saved to {out_path}")
    print("=" * 75)
    return {"unseen_tasks": results}


if __name__ == "__main__":
    run_unseen_tasks()
