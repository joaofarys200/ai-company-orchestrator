import asyncio
import tempfile
import unittest
import uuid
from dataclasses import asdict
from pathlib import Path

from agents.executors import create_default_executor_registry
from agents.mission_autonomy import (
    MissionAutonomyController,
    MissionAutonomyError,
)
from agents.mission_executor import MissionExecution
from agents.mission_executor import MissionExecutorService
from agents.mission_state import MissionStateError, MissionStateStore, utc_now
from intelligence.coding_session import CodingSession


class AssistedCodingService:
    def __init__(self):
        self.created = []
        self.applied = []

    async def create_assisted_session(self, project_id, objective):
        session = CodingSession(
            session_id=uuid.uuid4().hex,
            project_id=project_id,
            objective=objective,
            project_context_snapshot={
                "project_id": project_id,
                "root_path": f"workspace/projects/{project_id}",
            },
            affected_files=["app.js"],
            proposed_changes=[{
                "file": "app.js",
                "operation": "replace_text",
                "previous_excerpt": "old",
                "proposed_excerpt": "new",
                "unified_diff": "--- a/app.js\n+++ b/app.js\n",
                "reason": "Offline fixture",
            }],
            change_plan={
                "objective": objective,
                "affected_files": ["app.js"],
                "affected_symbols": [],
                "validations": [],
            },
        )
        self.created.append(session)
        return session

    def apply_session(self, project_id, session_id):
        self.applied.append((project_id, session_id))
        raise AssertionError("Autonomy must never apply a CodingSession")


class ScriptedMissionExecutorService:
    def __init__(self, store):
        self.mission_state = store
        self.executor_registry = create_default_executor_registry()
        self.behaviors = {}
        self.calls = []
        self.entered = None
        self.release = None

    def load_snapshot(self, project_id, mission_id):
        snapshot = self.mission_state.load_mission(
            project_id,
            mission_id,
        )
        snapshot["executor_registry"] = self.executor_registry.describe()
        snapshot["controlled_execution"] = True
        snapshot["autonomous_execution"] = False
        return snapshot

    async def execute_work_package(
        self,
        project_id,
        mission_id,
        work_package_id,
        expected_mission_version,
        expected_work_package_version,
        test_mode=False,
        autonomous=False,
    ):
        self.calls.append({
            "work_package_id": work_package_id,
            "test_mode": test_mode,
            "autonomous": autonomous,
        })
        if self.entered is not None:
            self.entered.set()
        if self.release is not None:
            await self.release.wait()
        behavior = self.behaviors.get(work_package_id, "COMPLETED")
        if behavior == "NO_PROGRESS":
            return self.load_snapshot(project_id, mission_id)
        if behavior == "RAISE":
            raise RuntimeError("scripted executor failure")
        with self.mission_state._locked_mission(project_id, mission_id):
            mission = self.mission_state._load_mission_entity(
                project_id,
                mission_id,
            )
            self.mission_state._expect_version(
                mission.version,
                expected_mission_version,
            )
            package = self.mission_state._load_work_package(
                project_id,
                mission_id,
                work_package_id,
            )
            self.mission_state._expect_version(
                package.version,
                expected_work_package_version,
            )
            now = utc_now()
            execution_id = uuid.uuid4().hex
            phase = ""
            status = behavior
            if behavior == "AWAITING_APPLY_APPROVAL":
                status = "RUNNING"
                phase = "AWAITING_APPLY_APPROVAL"
            elif behavior == "WAITING_FOR_REVIEW":
                phase = "TECHNICAL_SUCCESS"
            execution = MissionExecution(
                execution_id=execution_id,
                mission_id=mission_id,
                work_package_id=work_package_id,
                executor_kind=self._executor_kind(package),
                status=status,
                started_at=now,
                updated_at=now,
                completed_at=(
                    None
                    if status in {"RUNNING", "WAITING_FOR_REVIEW"}
                    else now
                ),
                input_snapshot={
                    "mission": asdict(mission),
                    "work_package": asdict(package),
                },
                output_summary={"phase": phase or status},
                lock_owner=(
                    f"scripted:{execution_id}"
                    if status in {"RUNNING", "WAITING_FOR_REVIEW"}
                    else None
                ),
                lock_acquired_at=(
                    now
                    if status in {"RUNNING", "WAITING_FOR_REVIEW"}
                    else None
                ),
                heartbeat_at=(
                    now
                    if status in {"RUNNING", "WAITING_FOR_REVIEW"}
                    else None
                ),
            )
            self.mission_state._write_entity(
                self.mission_state._entity_path(
                    project_id,
                    mission_id,
                    "executions",
                    execution_id,
                ),
                execution,
            )
            if status == "COMPLETED":
                package.status = "COMPLETED"
                package.completed_at = now
            elif status == "VALIDATION_FAILED":
                package.status = "VALIDATION_FAILED"
            elif status in {"RUNNING", "WAITING_FOR_REVIEW"}:
                package.status = "IN_PROGRESS"
                package.started_at = package.started_at or now
            else:
                package.status = "READY"
            self.mission_state._touch(package, now)
            self.mission_state._write_entity(
                self.mission_state._entity_path(
                    project_id,
                    mission_id,
                    "work_packages",
                    work_package_id,
                ),
                package,
            )
            self.mission_state._touch_mission_after_child_change(
                project_id,
                mission,
            )
        return self.load_snapshot(project_id, mission_id)

    @staticmethod
    def _executor_kind(package):
        declared = str(package.executor_kind or "").strip().upper()
        if declared and declared != "MANUAL":
            return declared
        return str(package.type or "GENERIC").strip().upper()


class MissionAutonomyControllerTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = self.temp.name
        Path(
            self.root,
            "workspace",
            "projects",
            "fixture",
        ).mkdir(parents=True)
        Path(
            self.root,
            "workspace",
            "projects",
            "fixture",
            "app.js",
        ).write_text("old\n", encoding="utf-8")
        self.store = MissionStateStore(self.root)
        self.service = ScriptedMissionExecutorService(self.store)
        self.controller = MissionAutonomyController(
            self.root,
            mission_state=self.store,
            executor_service=self.service,
            owner_id="autonomy-test",
            stale_lock_min_age_seconds=1,
        )

    def tearDown(self):
        self.temp.cleanup()

    async def test_rejects_missing_mission_without_creating_cycle_lock(self):
        with self.assertRaisesRegex(MissionStateError, "nao existe"):
            await self.controller.run_cycle("fixture", "missing")

        mission_dir = Path(
            self.store._mission_dir("fixture", "missing")
        )
        self.assertFalse(mission_dir.exists())

    def create_mission(
        self,
        packages,
        *,
        mission_id="mission",
        active=True,
    ):
        snapshot = self.store.create_mission(
            "fixture",
            "Controlled mission",
            "Offline autonomy fixture",
            mission_id=mission_id,
        )
        for item in packages:
            snapshot = self.store.create_work_package(
                "fixture",
                mission_id,
                item["title"],
                description=item.get("description", "Deterministic work"),
                type=item.get("type", "CODING"),
                priority=item.get("priority", 0),
                dependencies=item.get("dependencies"),
                executor_kind=item.get("executor_kind", "MANUAL"),
                work_package_id=item["id"],
            )
        if active:
            snapshot = self.store.set_mission_status(
                "fixture",
                mission_id,
                "READY",
                snapshot["mission"]["version"],
            )
            snapshot = self.store.set_mission_status(
                "fixture",
                mission_id,
                "ACTIVE",
                snapshot["mission"]["version"],
            )
        return snapshot

    async def run_cycle(self, snapshot, **kwargs):
        return await self.controller.run_cycle(
            "fixture",
            snapshot["mission"]["mission_id"],
            expected_mission_version=snapshot["mission"]["version"],
            **kwargs,
        )

    def set_created_at(self, mission_id, work_package_id, value):
        package = self.store._load_work_package(
            "fixture",
            mission_id,
            work_package_id,
        )
        package.created_at = value
        self.store._write_entity(
            self.store._entity_path(
                "fixture",
                mission_id,
                "work_packages",
                work_package_id,
            ),
            package,
        )

    def write_active_execution(
        self,
        mission_id,
        work_package_id,
        *,
        phase="AWAITING_APPLY_APPROVAL",
    ):
        now = utc_now()
        execution = MissionExecution(
            execution_id="active-execution",
            mission_id=mission_id,
            work_package_id=work_package_id,
            executor_kind="CODING",
            status="RUNNING",
            started_at=now,
            updated_at=now,
            output_summary={"phase": phase},
            lock_owner="existing-owner",
            lock_acquired_at=now,
            heartbeat_at=now,
        )
        self.store._write_entity(
            self.store._entity_path(
                "fixture",
                mission_id,
                "executions",
                execution.execution_id,
            ),
            execution,
        )

    async def test_rejects_non_active_mission(self):
        snapshot = self.create_mission(
            [{"id": "code", "title": "Code"}],
            active=False,
        )
        result = await self.run_cycle(snapshot)
        self.assertEqual(result.status, "MISSION_NOT_ACTIVE")
        self.assertEqual(self.service.calls, [])

    async def test_returns_no_eligible_work(self):
        snapshot = self.create_mission([])
        result = await self.run_cycle(snapshot)
        self.assertEqual(result.status, "NO_ELIGIBLE_WORK")
        self.assertEqual(result.eligible_count, 0)

    async def test_selects_highest_priority(self):
        snapshot = self.create_mission([
            {"id": "low", "title": "Low", "priority": 1},
            {"id": "high", "title": "High", "priority": 9},
        ])
        result = await self.run_cycle(snapshot)
        self.assertEqual(result.selected_work_packages, ["high"])

    async def test_tiebreaks_by_oldest_created_at(self):
        snapshot = self.create_mission([
            {"id": "newer", "title": "Newer", "priority": 5},
            {"id": "older", "title": "Older", "priority": 5},
        ])
        self.set_created_at("mission", "newer", "2026-01-02T00:00:00+00:00")
        self.set_created_at("mission", "older", "2026-01-01T00:00:00+00:00")
        snapshot = self.store.load_mission("fixture", "mission")
        result = await self.run_cycle(snapshot)
        self.assertEqual(result.selected_work_packages, ["older"])

    async def test_tiebreaks_by_work_package_id(self):
        snapshot = self.create_mission([
            {"id": "zeta", "title": "Zeta", "priority": 5},
            {"id": "alpha", "title": "Alpha", "priority": 5},
        ])
        timestamp = "2026-01-01T00:00:00+00:00"
        self.set_created_at("mission", "zeta", timestamp)
        self.set_created_at("mission", "alpha", timestamp)
        snapshot = self.store.load_mission("fixture", "mission")
        result = await self.run_cycle(snapshot)
        self.assertEqual(result.selected_work_packages, ["alpha"])

    async def test_rejects_unsupported_executor(self):
        snapshot = self.create_mission([
            {"id": "research", "title": "Research", "type": "RESEARCH"},
        ])
        result = await self.run_cycle(snapshot)
        self.assertEqual(result.status, "EXECUTOR_UNAVAILABLE")
        self.assertEqual(
            result.skipped_packages[0]["reason"],
            "executor_not_supported",
        )
        self.assertEqual(self.service.calls, [])

    async def test_rejects_executor_without_autonomy(self):
        snapshot = self.create_mission([
            {
                "id": "build",
                "title": "Build",
                "type": "PROJECT_BUILD",
            },
        ])
        result = await self.run_cycle(snapshot)
        self.assertEqual(result.status, "AUTONOMY_NOT_ALLOWED")
        self.assertEqual(self.service.calls, [])

    async def test_does_not_fall_through_blocked_top_priority(self):
        snapshot = self.create_mission([
            {
                "id": "build",
                "title": "Build",
                "type": "PROJECT_BUILD",
                "priority": 10,
            },
            {
                "id": "code",
                "title": "Code",
                "type": "CODING",
                "priority": 1,
            },
        ])
        result = await self.run_cycle(snapshot)
        self.assertEqual(result.status, "AUTONOMY_NOT_ALLOWED")
        self.assertEqual(result.selected_work_packages, [])
        self.assertEqual(self.service.calls, [])

    async def test_executes_exactly_one_by_default(self):
        snapshot = self.create_mission([
            {"id": "first", "title": "First", "priority": 2},
            {"id": "second", "title": "Second", "priority": 1},
        ])
        result = await self.run_cycle(snapshot)
        self.assertEqual(result.status, "EXECUTED_ONE")
        self.assertEqual(len(self.service.calls), 1)
        self.assertEqual(result.execution_ids.__len__(), 1)

    async def test_respects_max_work_packages(self):
        snapshot = self.create_mission([
            {"id": "first", "title": "First", "priority": 3},
            {"id": "second", "title": "Second", "priority": 2},
            {"id": "third", "title": "Third", "priority": 1},
        ])
        result = await self.run_cycle(snapshot, max_work_packages=2)
        self.assertEqual(result.status, "MAX_STEPS_REACHED")
        self.assertEqual(
            result.selected_work_packages,
            ["first", "second"],
        )
        self.assertEqual(len(self.service.calls), 2)

    async def test_stops_for_apply_approval_without_applying(self):
        snapshot = self.create_mission([
            {"id": "code", "title": "Code"},
        ])
        self.service.behaviors["code"] = "AWAITING_APPLY_APPROVAL"
        result = await self.run_cycle(snapshot, test_mode=True)
        self.assertEqual(result.status, "WAITING_FOR_REVIEW")
        self.assertEqual(result.stop_reason, "apply_approval_required")
        self.assertTrue(self.service.calls[0]["autonomous"])
        self.assertTrue(self.service.calls[0]["test_mode"])

    async def test_real_coding_adapter_prepares_session_without_auto_apply(self):
        snapshot = self.create_mission([
            {"id": "code", "title": "Code", "description": "Change app.js"},
        ])
        snapshot = self.store.create_criterion(
            "fixture",
            "mission",
            "WORK_PACKAGE",
            "code",
            "Session prepared for review",
            required_evidence_kinds=["VALIDATION"],
            criterion_id="criterion-code",
        )
        coding = AssistedCodingService()
        executor = MissionExecutorService(
            self.root,
            mission_state=self.store,
            coding_service=coding,
            project_builder_runner=lambda _prompt: None,
            owner_id="real-executor",
        )
        controller = MissionAutonomyController(
            self.root,
            mission_state=self.store,
            executor_service=executor,
            owner_id="real-controller",
        )
        result = await controller.run_cycle(
            "fixture",
            "mission",
            expected_mission_version=snapshot["mission"]["version"],
            test_mode=True,
        )
        reloaded = executor.load_snapshot("fixture", "mission")
        execution = reloaded["executions"][0]
        self.assertEqual(result.status, "WAITING_FOR_REVIEW")
        self.assertEqual(execution["status"], "RUNNING")
        self.assertEqual(
            execution["output_summary"]["phase"],
            "AWAITING_APPLY_APPROVAL",
        )
        self.assertEqual(len(coding.created), 1)
        self.assertEqual(coding.applied, [])

    async def test_stops_on_execution_failure(self):
        snapshot = self.create_mission([
            {"id": "code", "title": "Code"},
        ])
        self.service.behaviors["code"] = "FAILED"
        result = await self.run_cycle(snapshot)
        self.assertEqual(result.status, "EXECUTION_FAILED")

    async def test_stops_on_validation_failure(self):
        snapshot = self.create_mission([
            {"id": "code", "title": "Code"},
        ])
        self.service.behaviors["code"] = "VALIDATION_FAILED"
        result = await self.run_cycle(snapshot)
        self.assertEqual(result.status, "VALIDATION_FAILED")

    async def test_stops_on_cancelled_execution(self):
        snapshot = self.create_mission([
            {"id": "code", "title": "Code"},
        ])
        self.service.behaviors["code"] = "CANCELLED"
        result = await self.run_cycle(snapshot)
        self.assertEqual(result.status, "CANCELLED")

    async def test_stops_when_active_execution_exists(self):
        snapshot = self.create_mission([
            {"id": "code", "title": "Code"},
        ])
        self.write_active_execution("mission", "code")
        result = await self.run_cycle(snapshot)
        self.assertEqual(result.status, "WAITING_FOR_REVIEW")
        self.assertEqual(self.service.calls, [])

    async def test_stops_blocked_for_non_review_active_execution(self):
        snapshot = self.create_mission([
            {"id": "code", "title": "Code"},
        ])
        self.write_active_execution(
            "mission",
            "code",
            phase="EXECUTING",
        )
        result = await self.run_cycle(snapshot)
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(self.service.calls, [])

    async def test_detects_no_progress(self):
        snapshot = self.create_mission([
            {"id": "code", "title": "Code"},
        ])
        self.service.behaviors["code"] = "NO_PROGRESS"
        result = await self.run_cycle(snapshot)
        self.assertEqual(result.status, "NO_PROGRESS")

    async def test_preserves_execution_lock_and_releases_cycle_lock(self):
        snapshot = self.create_mission([
            {"id": "code", "title": "Code"},
        ])
        self.service.behaviors["code"] = "WAITING_FOR_REVIEW"
        result = await self.run_cycle(snapshot)
        reloaded = self.service.load_snapshot("fixture", "mission")
        execution = next(
            item
            for item in reloaded["executions"]
            if item["execution_id"] == result.execution_ids[0]
        )
        self.assertIsNotNone(execution["lock_owner"])
        self.assertFalse(
            Path(
                self.root,
                "workspace",
                ".jarvis",
                "projects",
                "fixture",
                "missions",
                "mission",
                ".autonomy.lock",
            ).exists()
        )

    async def test_rejects_concurrent_cycle(self):
        snapshot = self.create_mission([
            {"id": "code", "title": "Code"},
        ])
        self.service.entered = asyncio.Event()
        self.service.release = asyncio.Event()
        first = asyncio.create_task(self.run_cycle(snapshot))
        await self.service.entered.wait()
        second_controller = MissionAutonomyController(
            self.root,
            mission_state=self.store,
            executor_service=self.service,
            owner_id="second-controller",
            stale_lock_min_age_seconds=1,
        )
        second = await second_controller.run_cycle(
            "fixture",
            "mission",
            expected_mission_version=snapshot["mission"]["version"],
        )
        self.assertEqual(second.status, "BLOCKED")
        self.assertEqual(
            second.stop_reason,
            "autonomy_cycle_lock_active",
        )
        self.service.release.set()
        first_result = await first
        self.assertEqual(first_result.status, "EXECUTED_ONE")

    async def test_reports_stale_version_without_execution(self):
        snapshot = self.create_mission([
            {"id": "code", "title": "Code"},
        ])
        result = await self.controller.run_cycle(
            "fixture",
            "mission",
            expected_mission_version=snapshot["mission"]["version"] - 1,
        )
        self.assertEqual(result.status, "STALE_VERSION")
        self.assertEqual(self.service.calls, [])

    async def test_records_autonomy_events(self):
        snapshot = self.create_mission([
            {"id": "code", "title": "Code"},
        ])
        result = await self.run_cycle(snapshot)
        event_types = [item["event_type"] for item in result.events]
        self.assertEqual(event_types[0], "AUTONOMY_CYCLE_STARTED")
        self.assertIn("AUTONOMY_WORK_PACKAGE_SELECTED", event_types)
        self.assertIn("AUTONOMY_EXECUTION_STARTED", event_types)
        self.assertIn("AUTONOMY_EXECUTION_FINISHED", event_types)
        self.assertEqual(event_types[-1], "AUTONOMY_CYCLE_STOPPED")
        persisted = self.store.load_mission(
            "fixture",
            "mission",
        )["recent_events"]
        self.assertIn(
            "AUTONOMY_CYCLE_STOPPED",
            [item["event_type"] for item in persisted],
        )

    async def test_does_not_change_unselected_package(self):
        snapshot = self.create_mission([
            {"id": "selected", "title": "Selected", "priority": 2},
            {"id": "untouched", "title": "Untouched", "priority": 1},
        ])
        before = next(
            item
            for item in snapshot["work_packages"]
            if item["work_package_id"] == "untouched"
        )
        await self.run_cycle(snapshot)
        after = next(
            item
            for item in self.store.load_mission(
                "fixture",
                "mission",
            )["work_packages"]
            if item["work_package_id"] == "untouched"
        )
        self.assertEqual(before, after)

    async def test_does_not_force_incomplete_dependency(self):
        snapshot = self.create_mission([
            {"id": "dependency", "title": "Dependency", "priority": 1},
            {
                "id": "dependent",
                "title": "Dependent",
                "priority": 100,
                "dependencies": ["dependency"],
            },
        ])
        self.assertNotIn(
            "dependent",
            snapshot["eligible_work_packages"],
        )
        result = await self.run_cycle(snapshot)
        self.assertEqual(result.selected_work_packages, ["dependency"])

    async def test_selection_result_is_deterministic(self):
        first_snapshot = self.create_mission([
            {"id": "beta", "title": "Beta", "priority": 2},
            {"id": "alpha", "title": "Alpha", "priority": 2},
        ])
        timestamp = "2026-01-01T00:00:00+00:00"
        self.set_created_at("mission", "beta", timestamp)
        self.set_created_at("mission", "alpha", timestamp)
        first_snapshot = self.store.load_mission("fixture", "mission")
        first = await self.run_cycle(first_snapshot)

        second_snapshot = self.create_mission(
            [
                {"id": "beta", "title": "Beta", "priority": 2},
                {"id": "alpha", "title": "Alpha", "priority": 2},
            ],
            mission_id="mission-two",
        )
        self.set_created_at("mission-two", "beta", timestamp)
        self.set_created_at("mission-two", "alpha", timestamp)
        second_snapshot = self.store.load_mission(
            "fixture",
            "mission-two",
        )
        second = await self.run_cycle(second_snapshot)
        self.assertEqual(
            first.selected_work_package_id,
            second.selected_work_package_id,
        )
        self.assertEqual(first.selection_reason, second.selection_reason)

    async def test_rejects_invalid_cycle_limit(self):
        snapshot = self.create_mission([
            {"id": "code", "title": "Code"},
        ])
        with self.assertRaises(MissionAutonomyError):
            await self.run_cycle(snapshot, max_work_packages=4)

    async def test_unknown_executor_kind_fails_closed(self):
        snapshot = self.create_mission([
            {
                "id": "future",
                "title": "Future",
                "executor_kind": "FUTURE",
            },
        ])
        result = await self.run_cycle(snapshot)
        self.assertEqual(result.status, "EXECUTOR_UNAVAILABLE")
        self.assertEqual(
            result.skipped_packages[0]["reason"],
            "executor_unknown",
        )

    async def test_reports_completed_mission_without_execution(self):
        snapshot = self.create_mission([])
        mission = self.store._load_mission_entity("fixture", "mission")
        mission.status = "COMPLETED"
        self.store._touch(mission)
        self.store._write_entity(
            self.store._mission_path("fixture", "mission"),
            mission,
        )
        snapshot = self.store.load_mission("fixture", "mission")
        result = await self.run_cycle(snapshot)
        self.assertEqual(result.status, "MISSION_COMPLETED")
        self.assertEqual(self.service.calls, [])


if __name__ == "__main__":
    unittest.main()
