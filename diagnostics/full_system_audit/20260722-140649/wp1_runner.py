from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.mission_executor import MissionExecutorService  # noqa: E402
from agents.mission_state import MissionStateStore  # noqa: E402


def _project_slug(label: str) -> str:
    clean = "".join(char.lower() if char.isalnum() else "-" for char in label).strip("-")
    return f"health-{clean}-{uuid.uuid4().hex[:10]}"


async def run(label: str, output_path: Path) -> dict:
    project_id = _project_slug(label)
    mission_id = f"wp1-{uuid.uuid4().hex[:16]}"
    prompt = (
        f"Cria um projeto full-stack pequeno chamado {project_id}, com frontend, backend, "
        "persistencia simples, testes executaveis e preview. Usa apenas Node.js standard "
        "library, sem dependencias externas. Nao uses Obsidian."
    )
    project_root = ROOT / "workspace" / "projects" / project_id
    project_root.mkdir(parents=True, exist_ok=False)
    store = MissionStateStore(str(ROOT))
    store.create_mission(
        project_id,
        "Full system health WP1",
        prompt,
        description="Real ProjectBuilder WP1 execution for the full-system health audit.",
        current_phase="WP1",
        mission_id=mission_id,
        metadata={"audit": "full_system_health", "label": label, "attempt": 1},
    )
    snapshot = store.create_work_package(
        project_id,
        mission_id,
        "WP1 ProjectBuilder real execution",
        description=prompt,
        type="PROJECT_BUILD",
        executor_kind="PROJECT_BUILD",
        work_package_id="wp1",
    )
    snapshot = store.set_mission_status(project_id, mission_id, "READY", snapshot["mission"]["version"])
    snapshot = store.set_mission_status(project_id, mission_id, "ACTIVE", snapshot["mission"]["version"])
    work_package = next(item for item in snapshot["work_packages"] if item["work_package_id"] == "wp1")
    started = time.perf_counter()
    result = await MissionExecutorService(
        str(ROOT),
        mission_state=store,
        owner_id=f"full-health-wp1:{os.getpid()}:{label}",
    ).execute_work_package(
        project_id,
        mission_id,
        "wp1",
        snapshot["mission"]["version"],
        work_package["version"],
    )
    elapsed = time.perf_counter() - started
    execution = result["executions"][-1] if result.get("executions") else {}
    report = {
        "label": label,
        "started_at_epoch": time.time() - elapsed,
        "duration_seconds": round(elapsed, 3),
        "project_id": project_id,
        "mission_id": mission_id,
        "work_package_id": "wp1",
        "prompt": prompt,
        "status": execution.get("status"),
        "execution": execution,
        "work_package": next(
            item for item in result["work_packages"] if item["work_package_id"] == "wp1"
        ),
        "mission": result["mission"],
        "project_builder": execution.get("output_summary", {}).get("project_builder"),
        "snapshot": result,
        "python_executable": sys.executable,
        "model": os.getenv("OLLAMA_MODEL", "") or "loaded-by-project-builder",
    }
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "label": label,
        "project_id": project_id,
        "mission_id": mission_id,
        "status": report["status"],
        "duration_seconds": report["duration_seconds"],
        "project_dir": (report["project_builder"] or {}).get("project_dir"),
        "progress_path": (report["project_builder"] or {}).get("progress_path"),
        "output_path": str(output_path),
    }, ensure_ascii=False))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    asyncio.run(run(args.label, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
