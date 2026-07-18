from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.mission_executor import (  # noqa: E402
    ExecutorUnavailableError,
    MissionExecutionError,
    MissionExecutorService,
)
from agents.mission_state import MissionStateStore  # noqa: E402
from intelligence.coding_session import CodingSession  # noqa: E402


class BenchmarkCodingService:
    def __init__(self):
        self.sessions: list[CodingSession] = []

    async def create_assisted_session(self, project_id: str, objective: str) -> CodingSession:
        session = CodingSession(
            session_id=f"{len(self.sessions) + 1:032x}",
            project_id=project_id,
            objective=objective,
            project_context_snapshot={"project_id": project_id, "stack": ["HTML/JavaScript"]},
            affected_files=["app.js"],
            proposed_changes=[{
                "file": "app.js",
                "operation": "replace_text",
                "previous_excerpt": "old",
                "proposed_excerpt": "new",
                "unified_diff": "--- a/app.js\n+++ b/app.js\n@@ -1 +1 @@\n-old\n+new",
                "reason": "Controlled benchmark change",
            }],
            change_plan={
                "objective": objective,
                "affected_files": ["app.js"],
                "affected_symbols": ["render"],
                "risks": ["UI regression"],
                "validations": [{"command": "node --check app.js", "required": True}],
            },
        )
        self.sessions.append(session)
        return session

    def apply_session(self, project_id: str, session_id: str) -> CodingSession:
        session = next(item for item in self.sessions if item.session_id == session_id)
        session.status = "SUCCEEDED"
        session.validation_results = [{
            "command": "node --check app.js",
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "duration_seconds": 0.01,
            "required": True,
        }]
        return session


@dataclass
class BenchmarkBuildResult:
    project_name: str = "Benchmark app"
    project_dir: str = ""
    project_rel_dir: str = "workspace/projects/benchmark-built"
    files_created: list[str] = field(
        default_factory=lambda: ["workspace/projects/benchmark-built/index.html"]
    )
    commands_executed: list[dict[str, Any]] = field(
        default_factory=lambda: [{"command": "static-check", "ok": True, "output": "ok"}]
    )
    commands_skipped: list[dict[str, Any]] = field(default_factory=list)
    preview_url: str = "http://127.0.0.1:19000/"
    preview_started: bool = True
    obsidian_used: bool = False


class Benchmark:
    def __init__(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for project_id in ("mission-fixture", "benchmark-built"):
            project = self.root / "workspace" / "projects" / project_id
            project.mkdir(parents=True)
            (project / "app.js").write_text("old\n", encoding="utf-8")
        (self.root / "workspace" / "projects" / "benchmark-built" / "index.html").write_text(
            "<h1>benchmark</h1>\n", encoding="utf-8"
        )
        self.store = MissionStateStore(str(self.root))
        self.coding = BenchmarkCodingService()

        async def builder(_prompt: str):
            return BenchmarkBuildResult(
                project_dir=str(self.root / "workspace" / "projects" / "benchmark-built")
            )

        self.builder = builder
        self.service = MissionExecutorService(
            str(self.root),
            mission_state=self.store,
            coding_service=self.coding,
            project_builder_runner=builder,
            owner_id="benchmark-owner",
        )
        self.results: dict[str, dict[str, Any]] = {}

    def close(self):
        self.temp.cleanup()

    @staticmethod
    def wp(snapshot, work_package_id):
        return next(item for item in snapshot["work_packages"] if item["work_package_id"] == work_package_id)

    @staticmethod
    def execution(snapshot, execution_id=None):
        if execution_id:
            return next(item for item in snapshot["executions"] if item["execution_id"] == execution_id)
        return snapshot["executions"][-1]

    def record(self, benchmark_id: str, passed: bool, **details):
        self.results[benchmark_id] = {"passed": bool(passed), "details": details}
        print(f"{benchmark_id}: {'PASS' if passed else 'FAIL'} - {json.dumps(details, ensure_ascii=False)}")

    def setup_chain(self):
        snapshot = self.store.create_mission(
            "mission-fixture", "Controlled chain", "Execute one package at a time", mission_id="chain"
        )
        packages = [
            ("wp1", "Create project", "PROJECT_BUILD", []),
            ("wp2", "Implement feature", "CODING", ["wp1"]),
            ("wp3", "Write report", "DOCUMENT", ["wp2"]),
        ]
        for work_package_id, title, kind, dependencies in packages:
            snapshot = self.store.create_work_package(
                "mission-fixture",
                "chain",
                title,
                description=f"Verifiable objective for {title}",
                type=kind,
                dependencies=dependencies,
                work_package_id=work_package_id,
            )
            snapshot = self.store.create_criterion(
                "mission-fixture",
                "chain",
                "WORK_PACKAGE",
                work_package_id,
                f"Technical evidence accepted for {title}",
                ["VALIDATION"],
                criterion_id=f"criterion-{work_package_id}",
            )
        snapshot = self.store.set_mission_status(
            "mission-fixture", "chain", "READY", snapshot["mission"]["version"]
        )
        return self.store.set_mission_status(
            "mission-fixture", "chain", "ACTIVE", snapshot["mission"]["version"]
        )

    async def execute_selected(self, snapshot, work_package_id):
        return await self.service.execute_work_package(
            "mission-fixture",
            "chain",
            work_package_id,
            snapshot["mission"]["version"],
            self.wp(snapshot, work_package_id)["version"],
        )

    async def run(self):
        snapshot = self.setup_chain()

        snapshot = await self.execute_selected(snapshot, "wp1")
        build_execution = self.execution(snapshot)
        self.record(
            "E001",
            len(snapshot["executions"]) == 1 and build_execution["work_package_id"] == "wp1",
            execution_id=build_execution["execution_id"],
            status=build_execution["status"],
        )
        self.record(
            "E002",
            self.wp(snapshot, "wp2")["status"] == "PENDING" and self.wp(snapshot, "wp3")["status"] == "PENDING",
            wp2=self.wp(snapshot, "wp2")["status"],
            wp3=self.wp(snapshot, "wp3")["status"],
        )

        unsupported_snapshot = self.store.create_mission(
            "mission-fixture", "Unsupported", "No fallback", mission_id="unsupported"
        )
        unsupported_snapshot = self.store.create_work_package(
            "mission-fixture", "unsupported", "Research", description="Manual research",
            type="RESEARCH", work_package_id="research"
        )
        unsupported_snapshot = self.store.set_mission_status(
            "mission-fixture", "unsupported", "READY", unsupported_snapshot["mission"]["version"]
        )
        unsupported_snapshot = self.store.set_mission_status(
            "mission-fixture", "unsupported", "ACTIVE", unsupported_snapshot["mission"]["version"]
        )
        unavailable = False
        try:
            await self.service.execute_work_package(
                "mission-fixture", "unsupported", "research",
                unsupported_snapshot["mission"]["version"], unsupported_snapshot["work_packages"][0]["version"]
            )
        except ExecutorUnavailableError:
            unavailable = True
        unchanged = self.store.load_mission("mission-fixture", "unsupported")
        self.record(
            "E003",
            unavailable and unchanged["work_packages"][0]["status"] == "READY" and not unchanged["executions"],
            executor="RESEARCH",
            fallback_used=False,
        )
        self.record(
            "E004",
            build_execution["status"] == "WAITING_FOR_REVIEW"
            and bool(build_execution["artifact_refs"])
            and bool(build_execution["validation_refs"]),
            artifacts=build_execution["artifact_refs"],
            validations=build_execution["validation_refs"],
        )
        self.record(
            "E005",
            self.wp(snapshot, "wp1")["status"] == "IN_PROGRESS"
            and self.wp(snapshot, "wp2")["status"] == "PENDING",
            execution=build_execution["status"],
            work_package=self.wp(snapshot, "wp1")["status"],
        )

        snapshot = self.service.review_execution(
            "mission-fixture", "chain", build_execution["execution_id"], "ACCEPT", "Builder accepted",
            build_execution["evidence_refs"], build_execution["version"]
        )
        snapshot = await self.execute_selected(snapshot, "wp2")
        first_coding = self.execution(snapshot)
        before_apply = first_coding["status"] == "RUNNING" and first_coding["output_summary"].get("phase") == "AWAITING_APPLY_APPROVAL"
        concurrent_blocked = False
        try:
            await self.execute_selected(snapshot, "wp2")
        except MissionExecutionError:
            concurrent_blocked = True
        self.record(
            "E009",
            concurrent_blocked and bool(first_coding["lock_owner"]),
            lock_owner=first_coding["lock_owner"],
        )

        restarted = MissionExecutorService(
            str(self.root),
            mission_state=MissionStateStore(str(self.root)),
            coding_service=self.coding,
            project_builder_runner=self.builder,
            owner_id="benchmark-restarted",
        )
        resumed = restarted.load_snapshot("mission-fixture", "chain")
        resumed_execution = self.execution(resumed, first_coding["execution_id"])
        self.record(
            "E010",
            resumed_execution["status"] == "RUNNING"
            and resumed_execution["output_summary"].get("phase") == "AWAITING_APPLY_APPROVAL",
            status=resumed_execution["status"],
            version=resumed_execution["version"],
        )

        snapshot = self.service.apply_execution(
            "mission-fixture", "chain", first_coding["execution_id"], first_coding["version"], True
        )
        first_coding = self.execution(snapshot, first_coding["execution_id"])
        self.record(
            "E006",
            before_apply and first_coding["status"] == "WAITING_FOR_REVIEW"
            and bool(first_coding["validation_refs"]),
            coding_session=first_coding["executor_ref"],
            status=first_coding["status"],
        )

        snapshot = self.service.review_execution(
            "mission-fixture", "chain", first_coding["execution_id"], "REJECT", "Needs revision", [],
            first_coding["version"]
        )
        rejected = self.execution(snapshot, first_coding["execution_id"])
        self.record(
            "E007",
            rejected["status"] == "FAILED" and self.wp(snapshot, "wp2")["status"] == "READY",
            execution=rejected["status"],
            work_package=self.wp(snapshot, "wp2")["status"],
        )

        snapshot = await self.service.retry_execution(
            "mission-fixture", "chain", rejected["execution_id"], rejected["version"]
        )
        retry = self.execution(snapshot)
        snapshot = self.service.apply_execution(
            "mission-fixture", "chain", retry["execution_id"], retry["version"], True
        )
        retry = self.execution(snapshot, retry["execution_id"])
        self.record(
            "E008",
            retry["attempt"] == 2
            and retry["previous_execution_id"] == rejected["execution_id"]
            and retry["status"] == "WAITING_FOR_REVIEW",
            attempt=retry["attempt"],
            previous_execution_id=retry["previous_execution_id"],
        )

        snapshot = self.service.review_execution(
            "mission-fixture", "chain", retry["execution_id"], "ACCEPT", "Coding accepted",
            retry["evidence_refs"], retry["version"]
        )
        criterion = next(
            item for item in snapshot["acceptance_criteria"] if item["criterion_id"] == "criterion-wp2"
        )
        self.record(
            "E011",
            criterion["status"] == "SATISFIED" and bool(criterion["evidence_refs"])
            and self.wp(snapshot, "wp2")["status"] == "COMPLETED",
            criterion=criterion["status"],
            evidence_refs=criterion["evidence_refs"],
        )

        document_unavailable = False
        try:
            await self.execute_selected(snapshot, "wp3")
        except ExecutorUnavailableError:
            document_unavailable = True
        final_snapshot = self.service.load_snapshot("mission-fixture", "chain")
        self.record(
            "E012",
            self.wp(final_snapshot, "wp1")["status"] == "COMPLETED"
            and self.wp(final_snapshot, "wp2")["status"] == "COMPLETED"
            and self.wp(final_snapshot, "wp3")["status"] == "READY"
            and document_unavailable
            and len(final_snapshot["executions"]) == 3
            and final_snapshot["autonomous_execution"] is False,
            statuses={item["work_package_id"]: item["status"] for item in final_snapshot["work_packages"]},
            executions=len(final_snapshot["executions"]),
            automatic_executions=0,
        )

        passed = sum(1 for item in self.results.values() if item["passed"])
        if passed == 12:
            classification = "STABLE_MISSION_EXECUTOR"
        elif passed >= 9:
            classification = "CONTROLLED_MISSION_EXECUTOR"
        else:
            classification = "PROTO_MISSION_EXECUTOR"
        print(json.dumps({
            "passed": passed,
            "total": 12,
            "classification": classification,
            "results": self.results,
        }, ensure_ascii=False, indent=2))
        return 0 if passed == 12 else 1


async def main() -> int:
    benchmark = Benchmark()
    try:
        return await benchmark.run()
    finally:
        benchmark.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
