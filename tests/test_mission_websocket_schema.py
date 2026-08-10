import json
import tempfile
import unittest
from pathlib import Path

from websocket_schema import WebSocketPayloadError, normalize_ws_message, validate_client_message
from agents.mission_autonomy import AutonomyCycleResult
from agents.mission_executor import MissionExecutorService
from agents.mission_state import MissionStateStore


class WebSocketCollector:
    def __init__(self):
        self.messages = []

    async def send(self, payload):
        self.messages.append(json.loads(payload))


class MissionWebSocketSchemaTest(unittest.TestCase):
    def test_accepts_all_mission_operations_with_required_payloads(self):
        messages = [
            {"type": "mission_list", "project_id": "task-app"},
            {"type": "mission_create", "project_id": "task-app", "title": "T", "objective": "O"},
            {"type": "mission_get", "project_id": "task-app", "mission_id": "m"},
            {"type": "mission_update", "project_id": "task-app", "mission_id": "m", "expected_version": 1, "changes": {}},
            {"type": "mission_set_status", "project_id": "task-app", "mission_id": "m", "expected_version": 1, "status": "READY"},
            {"type": "work_package_create", "project_id": "task-app", "mission_id": "m", "title": "WP"},
            {"type": "work_package_update", "project_id": "task-app", "mission_id": "m", "work_package_id": "wp", "expected_version": 1, "changes": {}},
            {"type": "work_package_set_status", "project_id": "task-app", "mission_id": "m", "work_package_id": "wp", "expected_version": 1, "status": "IN_PROGRESS"},
            {"type": "work_package_add_dependency", "project_id": "task-app", "mission_id": "m", "work_package_id": "wp", "dependency_id": "dep", "expected_version": 1},
            {"type": "deliverable_create", "project_id": "task-app", "mission_id": "m", "work_package_id": "wp", "name": "D"},
            {"type": "deliverable_update", "project_id": "task-app", "mission_id": "m", "deliverable_id": "d", "expected_version": 1, "changes": {}},
            {"type": "deliverable_set_status", "project_id": "task-app", "mission_id": "m", "deliverable_id": "d", "expected_version": 1, "status": "ACCEPTED"},
            {"type": "evidence_attach", "project_id": "task-app", "mission_id": "m", "work_package_id": "wp", "kind": "FILE", "source_ref": "file:workspace/projects/task-app/a.txt"},
            {"type": "criterion_create", "project_id": "task-app", "mission_id": "m", "owner_type": "WORK_PACKAGE", "owner_id": "wp", "description": "C"},
            {"type": "criterion_set_status", "project_id": "task-app", "mission_id": "m", "criterion_id": "c", "expected_version": 1, "status": "SATISFIED"},
            {"type": "mission_resume_snapshot", "project_id": "task-app", "mission_id": "m"},
            {"type": "mission_execute_work_package", "project_id": "task-app", "mission_id": "m", "work_package_id": "wp", "expected_mission_version": 1, "expected_work_package_version": 1},
            {"type": "mission_apply_execution", "project_id": "task-app", "mission_id": "m", "execution_id": "e", "expected_execution_version": 1, "confirmed": True},
            {"type": "mission_review_execution", "project_id": "task-app", "mission_id": "m", "execution_id": "e", "decision": "ACCEPT", "review_note": "ok", "accepted_evidence_refs": ["ev"], "expected_execution_version": 1},
            {"type": "mission_retry_execution", "project_id": "task-app", "mission_id": "m", "execution_id": "e", "expected_execution_version": 1},
            {"type": "mission_cancel_execution", "project_id": "task-app", "mission_id": "m", "execution_id": "e", "expected_execution_version": 1, "confirmed": True},
            {"type": "mission_release_stale_lock", "project_id": "task-app", "mission_id": "m", "execution_id": "e", "expected_execution_version": 1, "confirmed": True},
            {"type": "mission_autonomy_run", "project_id": "task-app", "mission_id": "m", "expected_mission_version": 1, "max_work_packages": 1, "confirmed": True, "test_mode": False},
        ]
        for message in messages:
            with self.subTest(message["type"]):
                self.assertEqual(validate_client_message(message), message)

    def test_rejects_missing_fields_stale_shape_and_unknown_operation(self):
        with self.assertRaises(WebSocketPayloadError):
            validate_client_message({"type": "mission_create", "project_id": "task-app"})
        with self.assertRaises(WebSocketPayloadError):
            validate_client_message({
                "type": "mission_update", "project_id": "task-app", "mission_id": "m",
                "expected_version": "1", "changes": {},
            })
        with self.assertRaises(WebSocketPayloadError):
            validate_client_message({"type": "execute_mission", "project_id": "task-app"})
        with self.assertRaises(WebSocketPayloadError):
            validate_client_message({
                "type": "mission_cancel_execution", "project_id": "task-app", "mission_id": "m",
                "execution_id": "e", "expected_execution_version": 1, "confirmed": False,
            })
        with self.assertRaises(WebSocketPayloadError):
            validate_client_message({
                "type": "mission_review_execution", "project_id": "task-app", "mission_id": "m",
                "execution_id": "e", "decision": "SKIP", "review_note": "", "accepted_evidence_refs": [],
                "expected_execution_version": 1,
            })
        with self.assertRaises(WebSocketPayloadError):
            validate_client_message({
                "type": "mission_autonomy_run", "project_id": "task-app", "mission_id": "m",
                "expected_mission_version": 1, "confirmed": False,
            })
        with self.assertRaises(WebSocketPayloadError):
            validate_client_message({
                "type": "mission_autonomy_run", "project_id": "task-app", "mission_id": "m",
                "expected_mission_version": 1, "confirmed": True, "max_work_packages": 4,
            })

    def test_normalizes_mission_server_messages(self):
        self.assertEqual(
            normalize_ws_message({"type": "mission_list", "project_id": "task-app", "missions": "bad"}),
            {"type": "mission_list", "project_id": "task-app", "missions": []},
        )
        snapshot = {"mission": {"mission_id": "m"}}
        self.assertEqual(
            normalize_ws_message({"type": "mission_snapshot", "data": snapshot}),
            {"type": "mission_snapshot", "data": snapshot},
        )

    def test_validates_manual_file_save_and_preserves_hash_metadata(self):
        digest = "a" * 64
        payload = {
            "type": "save_project_file",
            "project_id": "task-app",
            "filename": "app.js",
            "content": "",
            "expected_sha256": digest,
        }
        self.assertEqual(validate_client_message(payload), payload)
        with self.assertRaises(WebSocketPayloadError):
            validate_client_message({**payload, "expected_sha256": "invalid"})

        context_message = normalize_ws_message({
            "type": "project_context",
            "context": {"project_id": "task-app"},
            "files": {"app.js": ""},
            "file_hashes": {"app.js": digest},
            "symbols": {},
        })
        self.assertEqual(context_message["file_hashes"], {"app.js": digest})
        self.assertEqual(
            normalize_ws_message({
                "type": "project_file_save_result",
                "ok": True,
                "project_id": "task-app",
                "filename": "app.js",
                "sha256": digest,
                "size_bytes": 0,
            }),
            {
                "type": "project_file_save_result",
                "ok": True,
                "project_id": "task-app",
                "filename": "app.js",
                "sha256": digest,
                "size_bytes": 0,
                "error": "",
            },
        )


class MissionWebSocketDispatchTest(unittest.IsolatedAsyncioTestCase):
    async def test_dispatch_creates_and_returns_persistent_snapshot_without_execution(self):
        import server

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "workspace", "projects", "task-app").mkdir(parents=True)
            previous = server.mission_planner
            server.mission_planner = MissionStateStore(temp_dir)
            websocket = WebSocketCollector()
            try:
                handled = await server.dispatch_mission_operation(websocket, {
                    "type": "mission_create",
                    "project_id": "task-app",
                    "title": "Manual",
                    "objective": "Persistir sem executar",
                    "mission_id": "manual-mission",
                }, "task-app")
            finally:
                server.mission_planner = previous
            self.assertTrue(handled)
            self.assertEqual([item["type"] for item in websocket.messages], ["mission_snapshot", "mission_list"])
            self.assertTrue(websocket.messages[0]["data"]["read_only_execution"])
            self.assertEqual(websocket.messages[0]["data"]["mission"]["status"], "DRAFT")

    async def test_dispatch_executes_only_selected_ready_work_package(self):
        import server

        async def builder(_prompt):
            return {
                "project_name": "Built",
                "project_dir": "workspace/projects/built",
                "project_rel_dir": "workspace/projects/built",
                "files_created": ["workspace/projects/built/index.html"],
                "commands_executed": [{"command": "check", "ok": True, "output": "ok"}],
                "commands_skipped": [],
                "preview_url": "",
                "preview_started": False,
                "obsidian_used": False,
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            for project_id in ("task-app", "built"):
                root = Path(temp_dir, "workspace", "projects", project_id)
                root.mkdir(parents=True)
            Path(temp_dir, "workspace", "projects", "built", "index.html").write_text("ok", encoding="utf-8")
            store = MissionStateStore(temp_dir)
            snapshot = store.create_mission("task-app", "Manual", "One WP", mission_id="m")
            snapshot = store.create_work_package(
                "task-app", "m", "Build", description="Create isolated app",
                type="PROJECT_BUILD", work_package_id="wp",
            )
            snapshot = store.create_criterion(
                "task-app", "m", "WORK_PACKAGE", "wp", "Build passes", ["VALIDATION"], criterion_id="c"
            )
            snapshot = store.set_mission_status("task-app", "m", "READY", snapshot["mission"]["version"])
            snapshot = store.set_mission_status("task-app", "m", "ACTIVE", snapshot["mission"]["version"])
            executor = MissionExecutorService(
                temp_dir, mission_state=store, coding_service=object(), project_builder_runner=builder
            )
            previous_planner = server.mission_planner
            previous_executor = server.mission_executor_service
            server.mission_planner = store
            server.mission_executor_service = executor
            websocket = WebSocketCollector()
            try:
                handled = await server.dispatch_mission_operation(websocket, {
                    "type": "mission_execute_work_package",
                    "project_id": "task-app",
                    "mission_id": "m",
                    "work_package_id": "wp",
                    "expected_mission_version": snapshot["mission"]["version"],
                    "expected_work_package_version": snapshot["work_packages"][0]["version"],
                }, "task-app")
            finally:
                server.mission_planner = previous_planner
                server.mission_executor_service = previous_executor
            self.assertTrue(handled)
            self.assertEqual([item["type"] for item in websocket.messages], ["mission_snapshot", "mission_list"])
            self.assertEqual(websocket.messages[0]["data"]["executions"][0]["status"], "WAITING_FOR_REVIEW")
            self.assertFalse(websocket.messages[0]["data"]["autonomous_execution"])

    async def test_dispatch_runs_only_explicit_confirmed_autonomy_cycle(self):
        import server

        class FakeAutonomyController:
            def __init__(self):
                self.calls = []

            async def run_cycle(self, project_id, mission_id, **kwargs):
                self.calls.append((project_id, mission_id, kwargs))
                return AutonomyCycleResult(
                    project_id=project_id,
                    mission_id=mission_id,
                    status="NO_ELIGIBLE_WORK",
                    stop_reason="eligible_work_packages_is_empty",
                    snapshot_version=3,
                    cycle_id="cycle",
                )

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(
                temp_dir,
                "workspace",
                "projects",
                "task-app",
            ).mkdir(parents=True)
            store = MissionStateStore(temp_dir)
            snapshot = store.create_mission(
                "task-app",
                "Autonomy",
                "No packages",
                mission_id="m",
            )
            snapshot = store.set_mission_status(
                "task-app",
                "m",
                "READY",
                snapshot["mission"]["version"],
            )
            snapshot = store.set_mission_status(
                "task-app",
                "m",
                "ACTIVE",
                snapshot["mission"]["version"],
            )
            executor = MissionExecutorService(
                temp_dir,
                mission_state=store,
                coding_service=object(),
                project_builder_runner=lambda _prompt: None,
            )
            autonomy = FakeAutonomyController()
            previous_planner = server.mission_planner
            previous_executor = server.mission_executor_service
            previous_autonomy = server.mission_autonomy_controller
            server.mission_planner = store
            server.mission_executor_service = executor
            server.mission_autonomy_controller = autonomy
            websocket = WebSocketCollector()
            try:
                handled = await server.dispatch_mission_operation(
                    websocket,
                    {
                        "type": "mission_autonomy_run",
                        "project_id": "task-app",
                        "mission_id": "m",
                        "expected_mission_version": snapshot["mission"]["version"],
                        "max_work_packages": 1,
                        "confirmed": True,
                        "test_mode": True,
                    },
                    "task-app",
                )
            finally:
                server.mission_planner = previous_planner
                server.mission_executor_service = previous_executor
                server.mission_autonomy_controller = previous_autonomy
            self.assertTrue(handled)
            self.assertEqual(
                [item["type"] for item in websocket.messages],
                ["mission_snapshot", "mission_list"],
            )
            data = websocket.messages[0]["data"]
            self.assertTrue(data["autonomous_execution"])
            self.assertEqual(
                data["autonomy_cycle"]["status"],
                "NO_ELIGIBLE_WORK",
            )
            self.assertEqual(
                autonomy.calls[0][2],
                {
                    "expected_mission_version": snapshot["mission"]["version"],
                    "max_work_packages": 1,
                    "test_mode": True,
                },
            )


if __name__ == "__main__":
    unittest.main()
