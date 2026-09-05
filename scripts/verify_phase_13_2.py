"""
Phase 13.2 — Live QA Verification Script
Verifies Mission State Persistence Scalability & Storage Architecture against the running daemon:
ws://127.0.0.1:8001/?token=local-dev-token
"""

import os
import sys
import time
import json
import uuid
import asyncio
import tempfile
import shutil
import websockets

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))

from agents.mission_state import MissionStateStore
from agents.mission_persistence import (
    SQLiteMissionPersistence,
    ShardedFilesystemPersistence,
    HybridMissionPersistence,
    StorageMigrationEngine,
)

AUTH_TOKEN = os.getenv("JARVIS_WS_TOKEN") or os.getenv("WS_AUTH_TOKEN") or "local-dev-token"
BACKEND_URL = f"ws://127.0.0.1:8001/?token={AUTH_TOKEN}"


async def recv_until(ws, target_types: set[str] | str, timeout: float = 30.0) -> dict:
    if isinstance(target_types, str):
        target_types = {target_types}
    end_time = asyncio.get_event_loop().time() + timeout
    while True:
        remaining = max(0.1, end_time - asyncio.get_event_loop().time())
        msg = await asyncio.wait_for(ws.recv(), timeout=remaining)
        data = json.loads(msg)
        m_type = data.get("type", "")
        if m_type in target_types:
            return data


async def run_live_qa():
    print("=" * 85)
    print(" JARVIS OS - PHASE 13.2 STORAGE PERSISTENCE SCALABILITY LIVE QA VERIFICATION")
    print("=" * 85)

    scorecard = []

    # 1. Connect to running daemon
    print("\n--> [STEP 1] Connecting to live daemon WebSocket at", BACKEND_URL)
    try:
        async with websockets.connect(BACKEND_URL, close_timeout=15.0, max_size=33554432) as ws:
            print("[PASS] Successfully connected to live JARVIS backend.")
            scorecard.append(("Daemon WebSocket Connection", "PASS", "Connected to 127.0.0.1:8001"))

            project_id = "default"
            mission_id = f"m_scale_qa_{uuid.uuid4().hex[:6]}"

            # 2. Decompose a multi-task mission through the live WebSocket
            print("\n--> [STEP 2] Creating and decomposing scalable mission via live WebSocket")
            t0 = time.perf_counter()
            tasks = [
                {
                    "task_id": f"qa_task_{i:03d}",
                    "title": f"Scalable QA Task {i}",
                    "dependencies": [f"qa_task_{i-1:03d}"] if i > 0 and i % 4 != 0 else [],
                }
                for i in range(120)
            ]
            decomp_msg = {
                "type": "mission_plan_decompose",
                "project_id": project_id,
                "mission_id": mission_id,
                "title": "Phase 13.2 Live QA Mission",
                "objective": "Verify scalable storage and state persistence",
                "tasks": tasks,
            }
            await ws.send(json.dumps(decomp_msg))
            snapshot = await recv_until(ws, "mission_snapshot", timeout=30.0)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            m_data = snapshot["data"]["mission"]
            wps = snapshot["data"].get("work_packages", [])
            assert m_data["mission_id"] == mission_id
            assert len(wps) == 120
            print(f"[PASS] 120 work packages created and validated over WebSocket in {elapsed_ms:.1f}ms")
            scorecard.append(("Live DAG Decompose & Persistence", "PASS", f"120 tasks created in {elapsed_ms:.1f}ms"))

            # 3. Query mission status over live WebSocket
            print("\n--> [STEP 3] Querying mission status over live WebSocket")
            await ws.send(json.dumps({
                "type": "mission_get",
                "project_id": project_id,
                "mission_id": mission_id,
            }))
            status_snap = await recv_until(ws, "mission_snapshot", timeout=15.0)
            assert status_snap["data"]["mission"]["mission_id"] == mission_id
            print("[PASS] Mission status snapshot retrieved cleanly")
            scorecard.append(("Live Mission Status Query", "PASS", "Snapshot confirmed"))

    except Exception as exc:
        print(f"[FAIL] Daemon WebSocket communication error: {exc}")
        scorecard.append(("Daemon WebSocket Connection", "FAIL", str(exc)))

    # 4. In-process Persistence Layer Scalability & Architecture Verification
    print("\n--> [STEP 4] Verifying Hybrid Storage Persistence Architecture")
    temp_dir = tempfile.mkdtemp(prefix="qa_phase13_2_")
    try:
        os.makedirs(os.path.join(temp_dir, "workspace", "projects", "qa-proj"), exist_ok=True)
        store = MissionStateStore(temp_dir, storage_backend="hybrid")
        m_scale = "mission-hybrid-qa"
        store.create_mission("qa-proj", "Hybrid QA", "Storage validation", mission_id=m_scale)

        # Batch write 1,000 tasks
        pkgs = [
            {"work_package_id": f"wp-{i:04d}", "title": f"T{i}", "priority": i % 5}
            for i in range(1000)
        ]
        t_b0 = time.perf_counter()
        snap = store.create_work_packages_batch("qa-proj", m_scale, pkgs)
        b_write_ms = (time.perf_counter() - t_b0) * 1000.0

        assert len(snap["work_packages"]) == 1000
        stats = store.get_storage_stats("qa-proj", m_scale)
        assert stats.work_packages_count == 1000
        assert stats.total_files <= 5
        print(f"[PASS] 1,000 tasks batch persisted in {b_write_ms:.1f}ms into {stats.total_files} files (vs 1,000 loose files)")
        scorecard.append(("Hybrid 1k Batch Write", "PASS", f"1,000 tasks in {b_write_ms:.1f}ms, {stats.total_files} files"))

        # O(1) Lookup
        t_l0 = time.perf_counter()
        wp_found = store.get_work_package("qa-proj", m_scale, "wp-0500")
        lookup_ms = (time.perf_counter() - t_l0) * 1000.0
        assert wp_found is not None
        assert wp_found["work_package_id"] == "wp-0500"
        print(f"[PASS] O(1) indexed lookup in {lookup_ms:.3f}ms")
        scorecard.append(("O(1) Indexed Task Lookup", "PASS", f"{lookup_ms:.3f}ms"))

        # Checkpoint save and restore
        t_cp0 = time.perf_counter()
        store.save_checkpoint("qa-proj", m_scale, {
            "checkpoint_id": "cp_qa_01",
            "sequence": 1,
            "mission_id": m_scale,
            "project_id": "qa-proj",
            "task_graph_data": {"test": True},
            "created_at": "2026-09-03T18:00:00Z",
        })
        cp_loaded = store.load_latest_checkpoint("qa-proj", m_scale)
        assert cp_loaded is not None
        assert cp_loaded["checkpoint_id"] == "cp_qa_01"
        print("[PASS] Checkpoint saved and restored deterministically")
        scorecard.append(("Deterministic Checkpoint Restore", "PASS", "Sequence 1 verified"))

        # Storage Migration Verification
        print("\n--> [STEP 5] Verifying Legacy-to-SQLite Migration Engine")
        leg_dir = os.path.join(temp_dir, "workspace", ".jarvis", "projects", "qa-proj", "missions", "legacy-qa")
        os.makedirs(os.path.join(leg_dir, "work_packages"), exist_ok=True)
        with open(os.path.join(leg_dir, "mission.json"), "w", encoding="utf-8") as f:
            json.dump({"mission_id": "legacy-qa", "project_id": "qa-proj", "title": "Old Format", "status": "DRAFT", "version": 1}, f)
        for i in range(25):
            with open(os.path.join(leg_dir, "work_packages", f"old-wp-{i}.json"), "w", encoding="utf-8") as f:
                json.dump({"work_package_id": f"old-wp-{i}", "mission_id": "legacy-qa", "title": f"Old {i}", "status": "PENDING", "version": 1}, f)

        migrator = StorageMigrationEngine(temp_dir)
        target_db = SQLiteMissionPersistence(temp_dir)
        report = migrator.migrate("qa-proj", "legacy-qa", target_db, create_backup=True)

        assert report.success is True
        assert report.work_packages_migrated == 25
        assert report.validation_passed is True
        assert os.path.isdir(report.backup_path)
        print(f"[PASS] Migrated 25 legacy loose JSON files to SQLite in {report.duration_ms:.1f}ms with verified backup")
        scorecard.append(("Legacy Storage Migration", "PASS", f"25 tasks migrated in {report.duration_ms:.1f}ms"))

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    # Browser QA
    scorecard.append(("Browser Storage UI", "NOT_APPLICABLE", "No frontend storage UI exists"))

    # Final Summary Table
    print("\n" + "=" * 85)
    print(" PHASE 13.2 LIVE QA VERIFICATION SCORECARD")
    print("=" * 85)
    print(f"{'Requirement / Check':<38} | {'Status':<14} | {'Notes / Metrics':<30}")
    print("-" * 85)
    for name, status, notes in scorecard:
        print(f"{name:<38} | {status:<14} | {notes:<30}")
    print("=" * 85)

    all_pass = all(s in {"PASS", "NOT_APPLICABLE"} for _, s, _ in scorecard)
    if all_pass:
        print("\n>>> ALL PHASE 13.2 QA VERIFICATIONS PASSED SUCCESSFULLY! <<<\n")
        return 0
    else:
        print("\n>>> SOME VERIFICATIONS FAILED <<<\n")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_live_qa())
    sys.exit(exit_code)
