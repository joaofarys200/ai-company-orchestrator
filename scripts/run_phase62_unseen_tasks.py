"""
JARVIS OS — Phase 62: Continuous Verification & Autonomous Regression Governance
Unseen Tasks Evaluation Script (10 Diverse Production Scenarios)
Outputs canonical docs/phase62_unseen_tasks.json.
"""

import json
import os
import sys
import time
from typing import Any, Dict, List

sys.path.insert(0, os.getcwd())

from backend.agents.continuous_verification.bridge import ContinuousVerificationBridge
from backend.agents.continuous_verification.models import (
    ChangeItem,
    ChangeSet,
    ChangeSource,
    ChangeType,
    VerificationPolicyName,
)
from backend.agents.continuous_verification.policy import VerificationPolicyEngine


def run_unseen_tasks() -> Dict[str, Any]:
    print("Running 10 Unseen Production Tasks for Phase 62...")
    bridge = ContinuousVerificationBridge.get_instance(db_path=":memory:")

    tasks_definitions = [
        {
            "task_id": "task_01_python_backend",
            "category": "Python backend",
            "description": "Refactor async task queue worker in Python backend",
            "changes": [
                ChangeItem(
                    file_path="backend/services/queue_worker.py",
                    symbol_id="func:process_next_job",
                    change_type=ChangeType.SYMBOL_CHANGED,
                    before_hash="hash_q1",
                    after_hash="hash_q2",
                    diff_metadata={"lines_added": 12, "lines_removed": 4},
                    source=ChangeSource.WORKSPACE_MODIFICATION,
                )
            ],
            "tests": [
                {"test_id": "test_process_next_job_basic", "target_file": "backend/services/queue_worker.py", "target_symbol": "func:process_next_job"},
                {"test_id": "test_process_next_job_timeout", "target_file": "backend/services/queue_worker.py", "target_symbol": "func:process_next_job"},
            ],
            "policy": "STANDARD",
        },
        {
            "task_id": "task_02_typescript_frontend",
            "category": "TypeScript frontend",
            "description": "Update mission progress bar component in React/TypeScript",
            "changes": [
                ChangeItem(
                    file_path="frontend/src/features/missions/ProgressBar.tsx",
                    change_type=ChangeType.MODIFIED,
                    before_hash="hash_ts1",
                    after_hash="hash_ts2",
                    diff_metadata={"lines_added": 8, "lines_removed": 2},
                    source=ChangeSource.WORKSPACE_MODIFICATION,
                )
            ],
            "tests": [
                {"test_id": "test_progress_bar_render", "target_file": "frontend/src/features/missions/ProgressBar.tsx", "framework": "playwright"}
            ],
            "policy": "STANDARD",
        },
        {
            "task_id": "task_03_contract_change",
            "category": "contract change",
            "description": "Add optional metadata field to UserProfileDTO schema contract",
            "changes": [
                ChangeItem(
                    file_path="contracts/schemas/user_profile.py",
                    symbol_id="class:UserProfileDTO",
                    change_type=ChangeType.CONTRACT_CHANGED,
                    before_hash="hash_c1",
                    after_hash="hash_c2",
                    diff_metadata={"lines_added": 5, "lines_removed": 0},
                    source=ChangeSource.WORKSPACE_MODIFICATION,
                )
            ],
            "tests": [
                {"test_id": "test_user_profile_dto_contract", "target_file": "contracts/schemas/user_profile.py"}
            ],
            "policy": "STRICT",
        },
        {
            "task_id": "task_04_behavioral_change",
            "category": "behavioral change",
            "description": "Reorder pipeline stages from sequential to buffered streaming",
            "changes": [
                ChangeItem(
                    file_path="backend/agents/workflows/pipeline_flow.py",
                    symbol_id="func:execute_pipeline_stages",
                    change_type=ChangeType.SYMBOL_CHANGED,
                    before_hash="hash_b1",
                    after_hash="hash_b2",
                    diff_metadata={"lines_added": 20, "lines_removed": 15},
                    source=ChangeSource.WORKSPACE_MODIFICATION,
                )
            ],
            "tests": [
                {"test_id": "test_pipeline_behavioral_order", "target_file": "backend/agents/workflows/pipeline_flow.py"}
            ],
            "policy": "STANDARD",
        },
        {
            "task_id": "task_05_browser_change",
            "category": "browser change",
            "description": "Modify interactive dropdown modal behavior in navigation bar",
            "changes": [
                ChangeItem(
                    file_path="frontend/src/components/NavigationDropdown.tsx",
                    change_type=ChangeType.MODIFIED,
                    before_hash="hash_br1",
                    after_hash="hash_br2",
                    diff_metadata={"lines_added": 14, "lines_removed": 6},
                    source=ChangeSource.WORKSPACE_MODIFICATION,
                )
            ],
            "tests": [
                {"test_id": "test_browser_dropdown_interaction", "target_file": "frontend/src/components/NavigationDropdown.tsx", "framework": "playwright"}
            ],
            "policy": "STANDARD",
        },
        {
            "task_id": "task_06_dynamic_dispatch",
            "category": "dynamic dispatch",
            "description": "Dynamic plugin routing with runtime string resolution and reflection",
            "changes": [
                ChangeItem(
                    file_path="backend/agents/dispatch/plugin_router.py",
                    change_type=ChangeType.MODIFIED,
                    before_hash="hash_dyn1",
                    after_hash="hash_dyn2",
                    diff_metadata={"lines_added": 10, "lines_removed": 2},
                    source=ChangeSource.WORKSPACE_MODIFICATION,
                )
            ],
            "files": {
                "backend/agents/dispatch/plugin_router.py": "plugin = getattr(importlib.import_module(p_name), 'Handler')\nres = plugin.run()"
            },
            "tests": [],
            "policy": "STANDARD",
        },
        {
            "task_id": "task_07_test_regression",
            "category": "test regression",
            "description": "Regression in calculation logic causing assertion failure",
            "changes": [
                ChangeItem(
                    file_path="backend/services/pricing.py",
                    symbol_id="func:calculate_discount",
                    change_type=ChangeType.SYMBOL_CHANGED,
                    before_hash="hash_p1",
                    after_hash="hash_p2",
                    diff_metadata={"lines_added": 3, "lines_removed": 1},
                    source=ChangeSource.WORKSPACE_MODIFICATION,
                )
            ],
            "tests": [
                {"test_id": "test_pricing_regression_boundary", "target_file": "backend/services/pricing.py", "target_symbol": "func:calculate_discount"}
            ],
            "policy": "STANDARD",
        },
        {
            "task_id": "task_08_deleted_symbol",
            "category": "deleted symbol",
            "description": "Removal of deprecated legacy helper function",
            "changes": [
                ChangeItem(
                    file_path="backend/legacy/v1_compat.py",
                    symbol_id="func:legacy_parse_token",
                    change_type=ChangeType.SYMBOL_REMOVED,
                    before_hash="hash_leg1",
                    after_hash="",
                    diff_metadata={"lines_added": 0, "lines_removed": 15},
                    source=ChangeSource.WORKSPACE_MODIFICATION,
                )
            ],
            "tests": [],
            "policy": "STANDARD",
        },
        {
            "task_id": "task_09_cross_service_consumer",
            "category": "cross-service consumer",
            "description": "Shared connection pool parameter update affecting downstream telemetry consumers",
            "changes": [
                ChangeItem(
                    file_path="backend/shared/db_pool.py",
                    symbol_id="func:acquire_db_conn",
                    change_type=ChangeType.SYMBOL_CHANGED,
                    before_hash="hash_db1",
                    after_hash="hash_db2",
                    diff_metadata={"lines_added": 7, "lines_removed": 3},
                    source=ChangeSource.WORKSPACE_MODIFICATION,
                )
            ],
            "tests": [
                {"test_id": "test_db_pool_acquire", "target_file": "backend/shared/db_pool.py", "target_symbol": "func:acquire_db_conn"},
                {"test_id": "test_telemetry_consumer_db", "target_file": "backend/services/telemetry.py"}
            ],
            "policy": "STANDARD",
        },
        {
            "task_id": "task_10_high_risk_change",
            "category": "high-risk change",
            "description": "Security-critical authentication token validation update",
            "changes": [
                ChangeItem(
                    file_path="backend/security/auth/token_validator.py",
                    symbol_id="func:validate_jwt_token",
                    change_type=ChangeType.SYMBOL_CHANGED,
                    before_hash="hash_auth1",
                    after_hash="hash_auth2",
                    diff_metadata={"lines_added": 18, "lines_removed": 5},
                    source=ChangeSource.WORKSPACE_MODIFICATION,
                )
            ],
            "tests": [
                {"test_id": "test_security_jwt_token_validation", "target_file": "backend/security/auth/token_validator.py", "target_symbol": "func:validate_jwt_token"}
            ],
            "policy": "CRITICAL",
        },
    ]

    results: List[Dict[str, Any]] = []

    for item in tasks_definitions:
        ContinuousVerificationBridge.reset_instance()
        bridge = ContinuousVerificationBridge.get_instance(db_path=":memory:")

        t_id = item["task_id"]
        cs = ChangeSet(id=f"cs_{t_id}", changes=item["changes"], source="unseen_task")
        ws_files = item.get("files")
        avail_tests = item.get("tests", [])
        policy_name = item.get("policy", "STANDARD")

        t0 = time.perf_counter()
        decision = bridge.verify_change(
            change_set=cs,
            workspace_files=ws_files,
            policy=policy_name,
            available_tests=avail_tests,
            domain="unseen_tasks",
        )
        duration_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        record = {
            "task_id": t_id,
            "category": item["category"],
            "description": item["description"],
            "policy_applied": policy_name,
            "verification_surface": decision.scope,
            "tests_selected": decision.tests_run,
            "tests_generated": decision.tests_missing,
            "execution_result": {
                "outcome": decision.outcome.value if hasattr(decision.outcome, "value") else str(decision.outcome),
                "confidence": decision.confidence,
                "duration_ms": duration_ms,
            },
            "evidence": decision.evidence,
            "final_verification_decision": decision.to_dict(),
        }
        results.append(record)
        print(f"Task '{t_id}' ({item['category']}): {decision.outcome.value if hasattr(decision.outcome, 'value') else decision.outcome} ({duration_ms}ms)")

    out_path = os.path.join(os.getcwd(), "docs", "phase62_unseen_tasks.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"total_tasks": len(results), "tasks": results}, f, indent=2)

    print(f"\nSaved unseen task evaluation to {out_path}")
    return {"total_tasks": len(results), "tasks": results}


if __name__ == "__main__":
    run_unseen_tasks()
