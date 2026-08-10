import tempfile
import unittest
from pathlib import Path

from agents.agent_profiles import create_default_agent_profile_registry
from agents.mission_executor import MissionExecutorService
from agents.mission_state import MissionStateStore
from backend.model_harness import (
    CallableModelProvider,
    ModelHarness,
    ProviderRegistry,
    ProviderResult,
)
from intelligence.coding_session import CodingSession


class HarnessAwareCodingService:
    def __init__(self):
        self.requester = None
        self.plan = None

    async def create_assisted_session(
        self,
        project_id,
        objective,
        requester=None,
    ):
        self.requester = requester
        self.plan = await requester({
            "objective": objective,
            "project_context": {"project_id": project_id},
            "symbols": {"files": []},
            "files": {"app.js": "function render() {}"},
        }, None)
        return CodingSession(
            session_id="1" * 32,
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
                "unified_diff": "-old\n+new",
                "reason": "Controlled test",
            }],
            change_plan={
                "objective": objective,
                "affected_files": ["app.js"],
                "affected_symbols": ["render"],
                "validations": [{
                    "command": "node --check app.js",
                    "required": True,
                }],
            },
        )


class MissionModelHarnessBridgeTest(unittest.IsolatedAsyncioTestCase):
    async def test_coding_mission_uses_harness_and_persists_trace(self):
        captured = {}

        async def provider_callback(request, route, _progress):
            captured["request"] = request
            captured["route"] = route
            return ProviderResult(
                raw_text=(
                    '{"changes":[{"file":"app.js",'
                    '"operation":"replace_text","old_text":"old",'
                    '"new_code":"new","reason":"fix"}],"risks":[]}'
                )
            )

        harness = ModelHarness(ProviderRegistry([
            CallableModelProvider(
                "test",
                "model-for-test",
                provider_callback,
            )
        ]))
        with tempfile.TemporaryDirectory() as root:
            project = Path(root, "workspace", "projects", "fixture")
            project.mkdir(parents=True)
            (project / "app.js").write_text("old\n", encoding="utf-8")
            store = MissionStateStore(root)
            coding = HarnessAwareCodingService()
            service = MissionExecutorService(
                root,
                mission_state=store,
                coding_service=coding,
                project_builder_runner=lambda _prompt: None,
                model_harness=harness,
                owner_id="bridge-test",
            )
            snapshot = store.create_mission(
                "fixture",
                "Coding mission",
                "Use the production model boundary",
                mission_id="mission",
            )
            snapshot = store.create_work_package(
                "fixture",
                "mission",
                "Fix render",
                description="Apply a controlled change to render.",
                type="CODING",
                metadata={"agent_id": "devon"},
                work_package_id="code",
            )
            snapshot = store.create_criterion(
                "fixture",
                "mission",
                "WORK_PACKAGE",
                "code",
                "Syntax validation passes.",
                required_evidence_kinds=["VALIDATION"],
                criterion_id="criterion-code",
            )
            snapshot = store.set_mission_status(
                "fixture",
                "mission",
                "READY",
                snapshot["mission"]["version"],
            )
            snapshot = store.set_mission_status(
                "fixture",
                "mission",
                "ACTIVE",
                snapshot["mission"]["version"],
            )

            snapshot = await service.execute_work_package(
                "fixture",
                "mission",
                "code",
                snapshot["mission"]["version"],
                snapshot["work_packages"][0]["version"],
            )

        execution = snapshot["executions"][0]
        request = captured["request"]
        self.assertIsNotNone(coding.requester)
        self.assertEqual(request.metadata["mission_id"], "mission")
        self.assertEqual(request.metadata["caller_type"], "agent")
        self.assertEqual(request.metadata["caller_id"], "devon")
        self.assertEqual(request.metadata["executor"], "CODING")
        self.assertIn(
            "menor alteracao de codigo",
            request.system_prompt,
        )
        self.assertEqual(execution["status"], "RUNNING")
        self.assertEqual(
            execution["output_summary"]["phase"],
            "AWAITING_APPLY_APPROVAL",
        )
        self.assertEqual(
            execution["input_snapshot"]["agent_profile"]["id"],
            "devon",
        )
        model_call = execution["output_summary"]["model_calls"][0]
        self.assertEqual(model_call["provider"], "test")
        self.assertEqual(model_call["model"], "model-for-test")
        self.assertEqual(model_call["validation_result"], "PASSED")
        telemetry = harness.telemetry.snapshot()[0]
        self.assertEqual(telemetry["mission_id"], "mission")
        self.assertEqual(telemetry["caller_id"], "devon")
        self.assertEqual(telemetry["executor"], "CODING")

    async def test_validation_failure_is_persisted_after_each_model_call(self):
        async def invalid_provider(_request, _route, _progress):
            return ProviderResult(raw_text='{"changes":[]}')

        harness = ModelHarness(ProviderRegistry([
            CallableModelProvider(
                "test",
                "invalid-model",
                invalid_provider,
            )
        ]))
        with tempfile.TemporaryDirectory() as root:
            project = Path(root, "workspace", "projects", "fixture")
            project.mkdir(parents=True)
            (project / "app.js").write_text("old\n", encoding="utf-8")
            store = MissionStateStore(root)
            service = MissionExecutorService(
                root,
                mission_state=store,
                coding_service=HarnessAwareCodingService(),
                project_builder_runner=lambda _prompt: None,
                model_harness=harness,
                owner_id="bridge-failure-test",
            )
            snapshot = store.create_mission(
                "fixture",
                "Invalid model output",
                "Preserve failed model calls",
                mission_id="mission",
            )
            snapshot = store.create_work_package(
                "fixture",
                "mission",
                "Fix render",
                description="Apply a controlled change to render.",
                type="CODING",
                work_package_id="code",
            )
            snapshot = store.create_criterion(
                "fixture",
                "mission",
                "WORK_PACKAGE",
                "code",
                "Syntax validation passes.",
                required_evidence_kinds=["VALIDATION"],
                criterion_id="criterion-code",
            )
            snapshot = store.set_mission_status(
                "fixture",
                "mission",
                "READY",
                snapshot["mission"]["version"],
            )
            snapshot = store.set_mission_status(
                "fixture",
                "mission",
                "ACTIVE",
                snapshot["mission"]["version"],
            )
            snapshot = await service.execute_work_package(
                "fixture",
                "mission",
                "code",
                snapshot["mission"]["version"],
                snapshot["work_packages"][0]["version"],
            )

        execution = snapshot["executions"][0]
        self.assertEqual(execution["status"], "FAILED")
        self.assertEqual(
            [item["status"] for item in execution["output_summary"]["model_calls"]],
            ["VALIDATION_FAILED"],
        )
        self.assertEqual(
            execution["primary_error"]["type"],
            "CodingSessionError",
        )
        self.assertEqual(
            snapshot["work_packages"][0]["status"],
            "READY",
        )

    def test_agent_profiles_are_configuration_not_model_instances(self):
        registry = create_default_agent_profile_registry()

        self.assertEqual(
            set(registry.describe()),
            {"alex", "clara", "devon", "quinn"},
        )
        devon = registry.resolve("CODING")
        self.assertEqual(devon.id, "devon")
        self.assertIn("STRUCTURED_EXTRACTION", devon.task_profiles)
        self.assertFalse(hasattr(devon, "model"))
        self.assertFalse(hasattr(devon, "provider"))

    def test_mission_coding_path_has_no_provider_specific_transport(self):
        root = Path(__file__).parents[1]
        for relative in (
            "agents/mission_executor.py",
            "agents/executors/coding.py",
            "intelligence/coding_session.py",
        ):
            source = (root / relative).read_text(encoding="utf-8")
            self.assertNotIn("/api/chat", source, relative)
            self.assertNotIn("httpx.AsyncClient", source, relative)
            self.assertNotIn("OLLAMA_MODEL", source, relative)
            self.assertNotIn("11434", source, relative)


if __name__ == "__main__":
    unittest.main()
