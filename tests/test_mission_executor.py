import asyncio
import json
import tempfile
import unittest
from dataclasses import dataclass, field
from pathlib import Path

from agents.mission_executor import (
    ExecutorUnavailableError,
    MissionExecutionError,
    MissionExecutorService,
)
from agents.mission_state import MissionStateStore, StaleVersionError
from intelligence.coding_session import CodingSession


class FakeCodingService:
    def __init__(self):
        self.created = []
        self.applied = []
        self.next_status = "SUCCEEDED"

    async def create_assisted_session(self, project_id, objective):
        session = CodingSession(
            session_id=(f"{len(self.created) + 1:032x}"),
            project_id=project_id,
            objective=objective,
            project_context_snapshot={"project_id": project_id, "root_path": f"workspace/projects/{project_id}"},
            affected_files=["app.js"],
            proposed_changes=[{
                "file": "app.js",
                "operation": "replace_text",
                "previous_excerpt": "old",
                "proposed_excerpt": "new",
                "unified_diff": "--- a/app.js\n+++ b/app.js\n@@ -1 +1 @@\n-old\n+new",
                "reason": "Teste controlado",
            }],
            change_plan={
                "objective": objective,
                "affected_files": ["app.js"],
                "affected_symbols": ["render"],
                "validations": [{"command": "node --check app.js", "required": True}],
            },
        )
        self.created.append(session)
        return session

    def apply_session(self, project_id, session_id):
        session = next(item for item in self.created if item.session_id == session_id)
        session.status = self.next_status
        session.validation_results = [{
            "command": "node --check app.js",
            "exit_code": 0 if self.next_status == "SUCCEEDED" else 1,
            "stdout": "ok" if self.next_status == "SUCCEEDED" else "",
            "stderr": "" if self.next_status == "SUCCEEDED" else "SyntaxError",
            "duration_seconds": 0.01,
            "required": True,
        }]
        if self.next_status != "SUCCEEDED":
            session.errors = ["Validacao falhou"]
        self.applied.append((project_id, session_id))
        return session


@dataclass
class FakeBuildResult:
    project_name: str = "Built app"
    project_dir: str = ""
    project_rel_dir: str = "workspace/projects/built-app"
    files_created: list[str] = field(default_factory=lambda: ["workspace/projects/built-app/index.html"])
    commands_executed: list[dict] = field(default_factory=lambda: [{"command": "check", "ok": True, "output": "ok"}])
    commands_skipped: list[dict] = field(default_factory=list)
    preview_url: str = "http://127.0.0.1:9000/"
    preview_started: bool = True
    obsidian_used: bool = False
    technical_success: bool = True
    status: str = "SUCCEEDED"
    error_category: str = ""
    validation_errors: list[dict] = field(default_factory=list)


class MissionExecutorTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = self.temp.name
        for project_id in ("fixture", "built-app"):
            project = Path(self.root, "workspace", "projects", project_id)
            project.mkdir(parents=True)
            (project / "app.js").write_text("old\n", encoding="utf-8")
        (Path(self.root, "workspace", "projects", "built-app", "index.html")).write_text(
            "<h1>Built</h1>\n", encoding="utf-8"
        )
        self.store = MissionStateStore(self.root)
        self.coding = FakeCodingService()

        async def builder(_prompt):
            return FakeBuildResult(
                project_dir=str(Path(self.root, "workspace", "projects", "built-app"))
            )

        self.service = MissionExecutorService(
            self.root,
            mission_state=self.store,
            coding_service=self.coding,
            project_builder_runner=builder,
            stale_lock_min_age_seconds=1,
            owner_id="test-owner",
        )

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def mission(snapshot):
        return snapshot["mission"]

    @staticmethod
    def work_package(snapshot, work_package_id):
        return next(item for item in snapshot["work_packages"] if item["work_package_id"] == work_package_id)

    @staticmethod
    def execution(snapshot, execution_id=None):
        items = snapshot["executions"]
        if execution_id:
            return next(item for item in items if item["execution_id"] == execution_id)
        return items[-1]

    def create_active_mission(self, packages):
        snapshot = self.store.create_mission(
            "fixture", "Missao controlada", "Executar manualmente", mission_id="mission"
        )
        for package in packages:
            snapshot = self.store.create_work_package(
                "fixture",
                "mission",
                package["title"],
                description=package.get("description", "Objetivo verificavel"),
                type=package.get("type", "GENERIC"),
                dependencies=package.get("dependencies"),
                executor_kind=package.get("executor_kind", "MANUAL"),
                work_package_id=package["id"],
            )
            if package.get("criterion", True):
                snapshot = self.store.create_criterion(
                    "fixture",
                    "mission",
                    "WORK_PACKAGE",
                    package["id"],
                    "Validacao tecnica aprovada",
                    required_evidence_kinds=["VALIDATION"],
                    criterion_id=f"criterion-{package['id']}",
                )
        snapshot = self.store.set_mission_status(
            "fixture", "mission", "READY", self.mission(snapshot)["version"]
        )
        return self.store.set_mission_status(
            "fixture", "mission", "ACTIVE", self.mission(snapshot)["version"]
        )

    async def execute(self, snapshot, work_package_id, test_mode=False):
        return await self.service.execute_work_package(
            "fixture",
            "mission",
            work_package_id,
            self.mission(snapshot)["version"],
            self.work_package(snapshot, work_package_id)["version"],
            test_mode=test_mode,
        )

    async def test_coding_requires_apply_approval_and_waits_for_review(self):
        snapshot = self.create_active_mission([{"id": "code", "title": "Alterar UI", "type": "CODING"}])
        snapshot = await self.execute(snapshot, "code")
        execution = self.execution(snapshot)
        self.assertEqual(execution["status"], "RUNNING")
        self.assertEqual(execution["output_summary"]["phase"], "AWAITING_APPLY_APPROVAL")
        self.assertEqual(self.coding.applied, [])
        self.assertEqual(self.work_package(snapshot, "code")["status"], "IN_PROGRESS")

        snapshot = self.service.apply_execution(
            "fixture", "mission", execution["execution_id"], execution["version"], True
        )
        execution = self.execution(snapshot)
        self.assertEqual(execution["status"], "WAITING_FOR_REVIEW")
        self.assertEqual(len(execution["evidence_refs"]), 3)
        self.assertEqual(len(self.coding.applied), 1)
        self.assertNotEqual(self.work_package(snapshot, "code")["status"], "COMPLETED")

    async def test_project_builder_waits_for_review_and_accept_completes(self):
        snapshot = self.create_active_mission([{
            "id": "build", "title": "Criar app", "type": "PROJECT_BUILD"
        }])
        snapshot = await self.execute(snapshot, "build")
        execution = self.execution(snapshot)
        self.assertEqual(execution["status"], "WAITING_FOR_REVIEW")
        self.assertIn("project_context:built-app", [item["source_ref"] for item in snapshot["evidence"]])
        snapshot = self.service.review_execution(
            "fixture",
            "mission",
            execution["execution_id"],
            "ACCEPT",
            "Validado manualmente",
            execution["evidence_refs"],
            execution["version"],
        )
        self.assertEqual(self.execution(snapshot)["status"], "COMPLETED")
        self.assertEqual(self.work_package(snapshot, "build")["status"], "COMPLETED")
        self.assertEqual(snapshot["acceptance_criteria"][0]["status"], "SATISFIED")

    async def test_project_builder_controlled_validation_failure_releases_lock(self):
        async def failed_builder(_prompt):
            return FakeBuildResult(
                project_dir=str(Path(self.root, "workspace", "projects", "built-app")),
                commands_executed=[],
                preview_url="",
                preview_started=False,
                technical_success=False,
                status="VALIDATION_FAILED",
                error_category="MISSING_REQUIRED_COMPONENT",
                validation_errors=[{
                    "category": "MISSING_REQUIRED_COMPONENT",
                    "phase": "PRE_VALIDATION",
                    "message": "frontend em falta",
                }],
            )

        self.service.project_builder_runner = failed_builder
        snapshot = self.create_active_mission([{
            "id": "build", "title": "Criar app", "type": "PROJECT_BUILD"
        }])
        snapshot = await self.execute(snapshot, "build")

        execution = self.execution(snapshot)
        self.assertEqual(execution["status"], "VALIDATION_FAILED")
        self.assertIsNone(execution["lock_owner"])
        self.assertEqual(execution["evidence_refs"], [])
        self.assertEqual(snapshot["evidence"], [])
        self.assertEqual(execution["primary_error"]["type"], "MissionExecutionError")
        self.assertNotIn("Traceback (most recent call last)", execution["primary_error"]["traceback"])
        self.assertEqual(self.work_package(snapshot, "build")["status"], "VALIDATION_FAILED")

    async def test_not_ready_non_active_and_unsupported_are_blocked(self):
        snapshot = self.create_active_mission([
            {"id": "first", "title": "Manual", "type": "RESEARCH"},
            {"id": "second", "title": "Code", "type": "CODING", "dependencies": ["first"]},
        ])
        with self.assertRaisesRegex(MissionExecutionError, "READY"):
            await self.execute(snapshot, "second")
        with self.assertRaises(ExecutorUnavailableError):
            await self.execute(snapshot, "first")
        reloaded = self.store.load_mission("fixture", "mission")
        self.assertEqual(self.work_package(reloaded, "first")["status"], "READY")
        self.assertEqual(reloaded["executions"], [])

        draft = self.store.create_mission("fixture", "Draft", "No run", mission_id="draft")
        draft = self.store.create_work_package(
            "fixture", "draft", "Build", description="Create", type="PROJECT_BUILD", work_package_id="build"
        )
        with self.assertRaisesRegex(MissionExecutionError, "ACTIVE"):
            await self.service.execute_work_package(
                "fixture", "draft", "build", draft["mission"]["version"], draft["work_packages"][0]["version"]
            )

    async def test_concurrent_lock_and_optimistic_version(self):
        snapshot = self.create_active_mission([{"id": "code", "title": "Code", "type": "CODING"}])
        with self.assertRaises(StaleVersionError):
            await self.service.execute_work_package(
                "fixture", "mission", "code", 1, self.work_package(snapshot, "code")["version"]
            )
        snapshot = await self.execute(snapshot, "code")
        execution = self.execution(snapshot)
        self.assertIsNotNone(execution["lock_owner"])
        with self.assertRaisesRegex(MissionExecutionError, "READY|ativa"):
            await self.service.execute_work_package(
                "fixture",
                "mission",
                "code",
                self.mission(snapshot)["version"],
                self.work_package(snapshot, "code")["version"],
            )

    async def test_accept_without_criteria_is_blocked(self):
        snapshot = self.create_active_mission([{
            "id": "build", "title": "Build", "type": "PROJECT_BUILD", "criterion": False
        }])
        snapshot = await self.execute(snapshot, "build")
        execution = self.execution(snapshot)
        with self.assertRaisesRegex(MissionExecutionError, "AcceptanceCriterion"):
            self.service.review_execution(
                "fixture", "mission", execution["execution_id"], "ACCEPT", "", execution["evidence_refs"], execution["version"]
            )
        self.assertEqual(
            self.service.load_snapshot("fixture", "mission")["executions"][0]["status"],
            "WAITING_FOR_REVIEW",
        )

    async def test_reject_retry_and_history(self):
        snapshot = self.create_active_mission([{"id": "build", "title": "Build", "type": "PROJECT_BUILD"}])
        snapshot = await self.execute(snapshot, "build")
        first = self.execution(snapshot)
        snapshot = self.service.review_execution(
            "fixture", "mission", first["execution_id"], "REJECT", "Rever resultado", [], first["version"]
        )
        self.assertEqual(self.execution(snapshot, first["execution_id"])["status"], "FAILED")
        self.assertEqual(self.work_package(snapshot, "build")["status"], "READY")

        snapshot = await self.service.retry_execution(
            "fixture", "mission", first["execution_id"], self.execution(snapshot, first["execution_id"])["version"]
        )
        second = self.execution(snapshot)
        self.assertNotEqual(second["execution_id"], first["execution_id"])
        self.assertEqual(second["attempt"], 2)
        self.assertEqual(second["previous_execution_id"], first["execution_id"])
        self.assertEqual(len(snapshot["executions"]), 2)

    async def test_validation_failure_retry_and_cancel(self):
        snapshot = self.create_active_mission([{"id": "code", "title": "Code", "type": "CODING"}])
        snapshot = await self.execute(snapshot, "code")
        execution = self.execution(snapshot)
        self.coding.next_status = "VALIDATION_FAILED"
        snapshot = self.service.apply_execution(
            "fixture", "mission", execution["execution_id"], execution["version"], True
        )
        failed = self.execution(snapshot)
        self.assertEqual(failed["status"], "VALIDATION_FAILED")
        self.coding.next_status = "SUCCEEDED"
        snapshot = await self.service.retry_execution(
            "fixture", "mission", failed["execution_id"], failed["version"]
        )
        retry = self.execution(snapshot)
        snapshot = self.service.cancel_execution(
            "fixture", "mission", retry["execution_id"], retry["version"], True
        )
        self.assertEqual(self.execution(snapshot)["status"], "CANCELLED")
        self.assertEqual(self.work_package(snapshot, "code")["status"], "READY")

    async def test_manual_stale_lock_release_and_restart_resume(self):
        snapshot = self.create_active_mission([{"id": "code", "title": "Code", "type": "CODING"}])
        snapshot = await self.execute(snapshot, "code")
        execution = self.execution(snapshot)
        path = Path(
            self.root,
            "workspace", ".jarvis", "projects", "fixture", "missions", "mission",
            "executions", f"{execution['execution_id']}.json",
        )
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["heartbeat_at"] = "2000-01-01T00:00:00+00:00"
        path.write_text(json.dumps(raw), encoding="utf-8")
        restarted = MissionExecutorService(
            self.root,
            mission_state=MissionStateStore(self.root),
            coding_service=self.coding,
            project_builder_runner=self.service.project_builder_runner,
            stale_lock_min_age_seconds=1,
            owner_id="new-owner",
        )
        resumed = restarted.load_snapshot("fixture", "mission")
        self.assertEqual(self.execution(resumed)["status"], "RUNNING")
        released = restarted.release_stale_lock(
            "fixture", "mission", execution["execution_id"], execution["version"], True
        )
        self.assertEqual(self.execution(released)["status"], "FAILED")
        self.assertIsNone(self.execution(released)["lock_owner"])
        self.assertIn("STALE_LOCK_RELEASED", [item["event_type"] for item in released["recent_events"]])

    async def test_failure_before_executor_is_persisted_without_false_completion(self):
        snapshot = self.create_active_mission([{"id": "code", "title": "Code", "type": "CODING"}])

        async def broken_create(_project_id, _objective):
            raise RuntimeError("planner unavailable")

        self.coding.create_assisted_session = broken_create
        snapshot = await self.execute(snapshot, "code")
        execution = self.execution(snapshot)
        self.assertEqual(execution["status"], "FAILED")
        self.assertEqual(execution["primary_error"]["message"], "planner unavailable")
        self.assertEqual(self.work_package(snapshot, "code")["status"], "READY")
        self.assertNotEqual(self.work_package(snapshot, "code")["status"], "COMPLETED")

    async def test_required_chain_never_runs_next_package_automatically(self):
        snapshot = self.create_active_mission([
            {"id": "wp1", "title": "Create", "type": "PROJECT_BUILD"},
            {"id": "wp2", "title": "Code", "type": "CODING", "dependencies": ["wp1"]},
            {"id": "wp3", "title": "Document", "type": "DOCUMENT", "dependencies": ["wp2"]},
        ])
        self.assertEqual(self.work_package(snapshot, "wp1")["status"], "READY")
        self.assertEqual(self.work_package(snapshot, "wp2")["status"], "PENDING")
        snapshot = await self.execute(snapshot, "wp1")
        first = self.execution(snapshot)
        self.assertEqual(self.work_package(snapshot, "wp2")["status"], "PENDING")
        snapshot = self.service.review_execution(
            "fixture", "mission", first["execution_id"], "ACCEPT", "ok", first["evidence_refs"], first["version"]
        )
        self.assertEqual(self.work_package(snapshot, "wp2")["status"], "READY")
        self.assertEqual(len(snapshot["executions"]), 1)
        with self.assertRaises(ExecutorUnavailableError):
            await self.execute(
                self._complete_code_for_chain(snapshot), "wp3"
            )

    def _complete_code_for_chain(self, snapshot):
        # The unavailable-executor assertion only needs the dependency to be complete;
        # completion is performed directly here because the CODING flow is covered above.
        work_package = self.store._load_work_package("fixture", "mission", "wp2")
        work_package.status = "COMPLETED"
        self.store._touch(work_package)
        self.store._write_entity(
            self.store._entity_path("fixture", "mission", "work_packages", "wp2"), work_package
        )
        mission = self.store._load_mission_entity("fixture", "mission")
        self.store._touch_mission_after_child_change("fixture", mission)
        return self.store.load_mission("fixture", "mission")


if __name__ == "__main__":
    unittest.main()
