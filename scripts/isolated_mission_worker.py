"""
JARVIS OS — Isolated Mission Worker
Helper script for testing real OS-level process restarts and abrupt terminations.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")


repo_root = os.path.realpath(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--mission-id", required=True)
    parser.add_argument("--scenario", required=True)
    args = parser.parse_args()

    # Configure environment
    workspace_root = os.path.abspath(args.workspace)
    os.environ["JARVIS_WORKSPACE"] = workspace_root
    os.environ["JARVIS_PERMISSIONS_DIR"] = os.path.join(workspace_root, "workspace", ".jarvis", "permissions")

    from agents.file_lease_manager import get_file_lease_manager
    from agents.mission_state import MissionStateStore
    from security.permission_gateway.gateway import get_permission_gateway_service
    from security.permission_gateway.project_dependency_manager import ProjectDependencyManager

    store = MissionStateStore(workspace_root=workspace_root)
    proj_dir = os.path.join(workspace_root, "workspace", "projects", args.project_id)
    os.makedirs(proj_dir, exist_ok=True)

    # 1. Base project context
    context_file = os.path.join(workspace_root, "workspace", ".jarvis", "projects", args.project_id, "project_context.json")
    os.makedirs(os.path.dirname(context_file), exist_ok=True)
    with open(context_file, "w", encoding="utf-8") as f:
        json.dump({
            "project_id": args.project_id,
            "project_name": args.project_id,
            "root_path": proj_dir,
            "created_at": time.time(),
        }, f, indent=2)

    # 2. Scenario Execution
    if args.scenario == "clean":
        store.create_mission(
            project_id=args.project_id,
            title="Clean Mission",
            objective="Survive clean restart",
            mission_id=args.mission_id,
        )
        store.create_work_package(
            project_id=args.project_id,
            mission_id=args.mission_id,
            title="Step 1",
            work_package_id="wp_01",
        )
        store.save_checkpoint(
            args.project_id,
            args.mission_id,
            {
                "sequence": 1,
                "checkpoint_id": "cp_0001",
                "mission_id": args.mission_id,
                "project_id": args.project_id,
                "mission_status": "READY",
                "schema_version": 2,
            },
        )
        print("CLEAN_COMPLETED", flush=True)
        sys.exit(0)

    elif args.scenario == "abrupt_kill":
        store.create_mission(
            project_id=args.project_id,
            title="Abrupt Mission",
            objective="Test abrupt process termination",
            mission_id=args.mission_id,
        )
        target_file = os.path.join(proj_dir, "main.py")
        with open(target_file, "w", encoding="utf-8") as f:
            f.write("# In-progress file\ndef run():\n    pass\n")

        # Acquire file lease
        lease_mgr = get_file_lease_manager()
        lease_mgr.acquire_file_lease(target_file, holder_id=f"worker_proc_{os.getpid()}", ttl_seconds=600.0)

        # Create work package in progress
        store.create_work_package(
            project_id=args.project_id,
            mission_id=args.mission_id,
            title="Editing main.py",
            work_package_id="wp_edit_01",
            metadata={"target_file": target_file},
        )
        store.update_work_package_status(args.project_id, args.mission_id, "wp_edit_01", "RUNNING")
        store.save_checkpoint(
            args.project_id,
            args.mission_id,
            {
                "sequence": 1,
                "checkpoint_id": "cp_0001_abrupt",
                "mission_id": args.mission_id,
                "project_id": args.project_id,
                "mission_status": "ACTIVE",
                "running_task_ids": ["wp_edit_01"],
                "schema_version": 2,
            },
        )
        print("READY_FOR_KILL", flush=True)
        # Hang until parent process executes proc.kill()
        while True:
            time.sleep(0.1)

    elif args.scenario == "pending_auth":
        store.create_mission(
            project_id=args.project_id,
            title="Mission With Pending Auth",
            objective="Authorization survives restart",
            mission_id=args.mission_id,
        )
        store.create_work_package(
            project_id=args.project_id,
            mission_id=args.mission_id,
            title="Install colorama",
            work_package_id="wp_auth_01",
        )
        # Prepare authorization request in gateway
        pdm = ProjectDependencyManager(gateway=get_permission_gateway_service())
        req = pdm.prepare_authorization_request(
            project_root=proj_dir,
            package_name="colorama",
            reason="Library needed for terminal colors",
            project_id=args.project_id,
            mission_id=args.mission_id,
        )
        store.set_mission_status(args.project_id, args.mission_id, "BLOCKED")
        store.save_checkpoint(
            args.project_id,
            args.mission_id,
            {
                "sequence": 1,
                "checkpoint_id": "cp_auth_01",
                "mission_id": args.mission_id,
                "project_id": args.project_id,
                "mission_status": "BLOCKED",
                "current_stage": "STAGE_AWAITING_APPROVAL",
                "approval_requests": [req.to_dict()],
                "schema_version": 2,
            },
        )
        print(f"READY_FOR_KILL:{req.request_id}", flush=True)
        while True:
            time.sleep(0.1)


if __name__ == "__main__":
    main()
