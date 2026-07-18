import os
import shutil
import unittest
from pathlib import Path

from agents import tools as ag_tools
from agents.orchestrator import project_builder


TEST_PROJECTS_ROOT = f"workspace/projects/_test_project_builder_{os.getpid()}"


def cleanup_test_projects():
    root = Path(ag_tools.resolve_workspace_path(TEST_PROJECTS_ROOT))
    if root.exists():
        shutil.rmtree(root)


class FakeRequester:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    async def __call__(self, prompt, correction=None):
        self.calls.append((prompt, correction))
        if not self.responses:
            return {}
        return self.responses.pop(0)


def correction_response(plan, error_code):
    return {
        "corrected_plan": plan,
        "correction_manifest": [{
            "error_code": error_code,
            "changed_artifacts": [],
            "resolution": "Returned a complete valid plan.",
        }],
    }


class ProjectBuilderUnitTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        cleanup_test_projects()

    def tearDown(self):
        for process in list(project_builder._preview_processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except Exception:
                    process.kill()
                    process.wait(timeout=5)
            project_builder._preview_processes.remove(process)
        cleanup_test_projects()

    def test_detects_clear_project_creation_prompts(self):
        self.assertTrue(project_builder.is_project_creation_request("cria hello.txt"))
        self.assertTrue(project_builder.is_project_creation_request("cria uma pagina simples"))
        self.assertTrue(project_builder.is_project_creation_request("cria uma app de tarefas"))
        self.assertFalse(project_builder.is_project_creation_request("abre o Excel"))
        self.assertFalse(project_builder.is_project_creation_request("cria uma nota no Obsidian"))

    async def test_creates_hello_txt_in_project_folder(self):
        requester = FakeRequester({
            "project_name": "Hello Txt",
            "stack": "text",
            "files": [{"path": "hello.txt", "content": "hello\n"}],
            "validation_commands": ["Get-ChildItem -LiteralPath ."],
            "preview_command": "",
        })

        result = await project_builder.build_project(
            "cria hello.txt",
            plan_requester=requester,
            projects_root_rel=TEST_PROJECTS_ROOT,
            start_preview=False,
        )

        self.assertTrue(result.project_rel_dir.startswith(TEST_PROJECTS_ROOT))
        self.assertEqual(len(result.files_created), 1)
        created = Path(ag_tools.resolve_workspace_path(result.files_created[0]))
        self.assertEqual(created.read_text(encoding="utf-8"), "hello\n")
        self.assertFalse(result.obsidian_used)
        self.assertNotIn("obsidian_vault", result.files_created[0].lower())
        self.assertEqual(len(result.commands_executed), 1)
        self.assertTrue(result.commands_executed[0].ok)
        self.assertEqual(result.commands_executed[0].working_directory, result.project_dir)
        self.assertEqual(result.commands_executed[0].exit_code, 0)

    async def test_creates_simple_page_and_static_preview(self):
        requester = FakeRequester({
            "project_name": "Pagina Simples",
            "stack": "html/css",
            "files": [
                {"path": "index.html", "content": "<!doctype html><main>Ola</main>"},
                {"path": "style.css", "content": "body { font-family: system-ui; }"},
            ],
            "validation_commands": [],
            "preview_command": "static",
        })

        result = await project_builder.build_project(
            "cria uma pagina simples",
            plan_requester=requester,
            projects_root_rel=TEST_PROJECTS_ROOT,
            start_preview=True,
        )

        self.assertTrue(result.preview_started)
        self.assertTrue(result.preview_url.startswith("http://127.0.0.1:"))
        self.assertTrue(Path(result.project_dir, "index.html").exists())

    async def test_creates_task_app_in_own_project_folder(self):
        requester = FakeRequester({
            "project_name": "App de Tarefas",
            "stack": "vanilla js",
            "files": [
                {"path": "index.html", "content": "<!doctype html><main id=\"app\"></main><script src=\"app.js\"></script>"},
                {"path": "app.js", "content": "const tasks = []; localStorage.setItem('tasks', JSON.stringify(tasks));"},
            ],
            "validation_commands": ["npm install"],
            "preview_command": "static",
        })

        result = await project_builder.build_project(
            "cria uma app de tarefas",
            plan_requester=requester,
            projects_root_rel=TEST_PROJECTS_ROOT,
            start_preview=False,
        )

        self.assertIn("app-de-tarefas", result.project_rel_dir)
        self.assertEqual(len(result.files_created), 2)
        blocked = [item for item in result.commands_executed if item.command == "npm install"]
        self.assertEqual(len(blocked), 1)
        self.assertFalse(blocked[0].ok)
        self.assertEqual(blocked[0].status, "BLOCKED")
        self.assertEqual(result.commands_skipped[0].command, "npm install")
        self.assertFalse(result.technical_success)
        self.assertFalse(result.obsidian_used)

    async def test_invalid_json_gets_one_correction(self):
        requester = FakeRequester(
            "not json",
            correction_response({
                "project_name": "Corrigido",
                "stack": "text",
                "files": [{"path": "ok.txt", "content": "ok"}],
                "validation_commands": [],
                "preview_command": "",
            }, "INVALID_JSON"),
        )

        result = await project_builder.build_project(
            "cria ok.txt",
            plan_requester=requester,
            projects_root_rel=TEST_PROJECTS_ROOT,
            start_preview=False,
        )

        self.assertEqual(len(requester.calls), 2)
        self.assertIn("LLM nao devolveu", requester.calls[1][1])
        self.assertTrue(Path(result.project_dir, "ok.txt").exists())

    async def test_invalid_json_twice_fails_clearly(self):
        requester = FakeRequester("not json", "still not json")

        with self.assertRaises(project_builder.ProjectBuilderError) as ctx:
            await project_builder.build_project(
                "cria fail.txt",
                plan_requester=requester,
                projects_root_rel=TEST_PROJECTS_ROOT,
                start_preview=False,
            )

        error = ctx.exception
        self.assertIsInstance(error, project_builder.ProjectBuilderPlanningError)
        self.assertEqual(error.category, "PLAN_JSON_INVALID")
        self.assertEqual(error.diagnostics["attempt_count"], 2)
        self.assertEqual(
            error.diagnostics["final_validation"]["parse_status"],
            "INVALID_JSON",
        )
        self.assertIn("unica correcao", error.sanitized_message)
        self.assertEqual(len(requester.calls), 2)

    async def test_rejects_obsidian_paths(self):
        requester = FakeRequester({
            "project_name": "Bad",
            "stack": "text",
            "files": [{"path": "obsidian_vault/hello.txt", "content": "no"}],
            "validation_commands": [],
            "preview_command": "",
        })

        result = await project_builder.build_project(
            "cria hello.txt",
            plan_requester=requester,
            projects_root_rel=TEST_PROJECTS_ROOT,
            start_preview=False,
        )

        first_errors = result.planning_diagnostics["validation_history"][0]["errors"]
        self.assertIn("UNSAFE_FILE_PATH", {item["code"] for item in first_errors})
        self.assertEqual(result.error_category, "PLAN_CORRECTION_FAILED")
        self.assertEqual(result.files_created, [])
        self.assertFalse(Path(ag_tools.resolve_workspace_path(TEST_PROJECTS_ROOT)).exists())


if __name__ == "__main__":
    unittest.main()
