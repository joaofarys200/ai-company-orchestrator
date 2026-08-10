import shutil
import tempfile
import unittest
from pathlib import Path

from agents.mission_executor import MissionExecutorService
from agents.mission_state import MissionStateError, MissionStateStore
from backend.model_harness import (
    CallableModelProvider,
    ModelHarness,
    ProviderRegistry,
    ProviderResult,
)
from intelligence.coding_session import CodingSessionService
from intelligence.project_context import ProjectContextService


UPDATED_ADD_TASK = """function addTask() {
  const input = document.getElementById('taskInput');
  const list = document.getElementById('taskList');
  const task = input.value.trim();
  if (!task) return;
  const li = document.createElement('li');
  li.textContent = task;
  list.appendChild(li);
  input.value = '';
}"""


class MissionModelHarnessEndToEndTest(
    unittest.IsolatedAsyncioTestCase
):
    async def test_reference_coding_mission_succeeds_twice(self):
        source = (
            Path(__file__).parents[1]
            / "workspace"
            / "projects"
            / "task-app"
        )
        provider_requests = []

        async def provider_callback(request, _route, _progress):
            provider_requests.append(request)
            return ProviderResult(raw_text=(
                '{"changes":[{"file":"app.js",'
                '"operation":"replace_symbol","symbol":"addTask",'
                f'"new_code":{self._json_string(UPDATED_ADD_TASK)},'
                '"reason":"Ignore empty input after trimming."}],'
                '"risks":["Input normalization changes user-visible behavior."]}'
            ))

        harness = ModelHarness(ProviderRegistry([
            CallableModelProvider(
                "test",
                "deterministic-coding-model",
                provider_callback,
            )
        ]))
        with tempfile.TemporaryDirectory() as root:
            for run_number in (1, 2):
                project_id = f"task-app-{run_number}"
                target = (
                    Path(root)
                    / "workspace"
                    / "projects"
                    / project_id
                )
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(source, target)
                projects = ProjectContextService(workspace_root=root)
                projects.index_project(project_id)
                coding = CodingSessionService(projects)
                store = MissionStateStore(root)
                service = MissionExecutorService(
                    root,
                    mission_state=store,
                    coding_service=coding,
                    model_harness=harness,
                    owner_id=f"e2e-{run_number}",
                )
                snapshot = self._create_mission(
                    store,
                    project_id,
                    run_number,
                )
                with self.assertRaisesRegex(
                    MissionStateError,
                    "WorkPackages obrigatorios ainda nao concluidos",
                ):
                    store.set_mission_status(
                        project_id,
                        f"mission-{run_number}",
                        "COMPLETED",
                        snapshot["mission"]["version"],
                    )
                snapshot = await service.execute_work_package(
                    project_id,
                    f"mission-{run_number}",
                    "code",
                    snapshot["mission"]["version"],
                    snapshot["work_packages"][0]["version"],
                    test_mode=True,
                )
                execution = snapshot["executions"][0]

                self.assertEqual(
                    execution["status"],
                    "WAITING_FOR_REVIEW",
                )
                self.assertEqual(
                    execution["output_summary"]["phase"],
                    "TECHNICAL_SUCCESS",
                )
                validation = execution["output_summary"][
                    "validation_results"
                ][0]
                self.assertEqual(validation["exit_code"], 0)
                self.assertIn(
                    "input.value.trim()",
                    (target / "app.js").read_text(encoding="utf-8"),
                )
                snapshot = service.review_execution(
                    project_id,
                    f"mission-{run_number}",
                    execution["execution_id"],
                    "ACCEPT",
                    "Validation evidence confirmed.",
                    execution["evidence_refs"],
                    execution["version"],
                )
                self.assertEqual(
                    snapshot["work_packages"][0]["status"],
                    "COMPLETED",
                )
                self.assertEqual(
                    snapshot["acceptance_criteria"][0]["status"],
                    "SATISFIED",
                )
                self.assertEqual(
                    snapshot["mission"]["status"],
                    "ACTIVE",
                )
                snapshot = store.set_mission_status(
                    project_id,
                    f"mission-{run_number}",
                    "COMPLETED",
                    snapshot["mission"]["version"],
                )
                self.assertEqual(
                    snapshot["mission"]["status"],
                    "COMPLETED",
                )

        self.assertEqual(len(provider_requests), 2)
        self.assertEqual(
            [item.metadata["step"] for item in provider_requests],
            [1, 1],
        )
        self.assertTrue(all(
            item.metadata["caller_id"] == "devon"
            for item in provider_requests
        ))

    @staticmethod
    def _create_mission(store, project_id, run_number):
        mission_id = f"mission-{run_number}"
        snapshot = store.create_mission(
            project_id,
            "Reference coding mission",
            "Inspect addTask, patch it, validate it and report evidence.",
            mission_id=mission_id,
        )
        snapshot = store.create_work_package(
            project_id,
            mission_id,
            "Ignore empty task input",
            description=(
                "Update addTask so whitespace-only input is ignored."
            ),
            type="CODING",
            work_package_id="code",
        )
        snapshot = store.create_criterion(
            project_id,
            mission_id,
            "WORK_PACKAGE",
            "code",
            "The JavaScript syntax validation must pass.",
            required_evidence_kinds=["VALIDATION"],
            criterion_id="syntax-valid",
        )
        snapshot = store.set_mission_status(
            project_id,
            mission_id,
            "READY",
            snapshot["mission"]["version"],
        )
        return store.set_mission_status(
            project_id,
            mission_id,
            "ACTIVE",
            snapshot["mission"]["version"],
        )

    @staticmethod
    def _json_string(value):
        import json

        return json.dumps(value)


if __name__ == "__main__":
    unittest.main()
