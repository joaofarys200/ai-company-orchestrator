import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from agents import tools as ag_tools
from agents.orchestrator import project_builder


TEST_ROOT_REL = f"workspace/projects/_project_builder_cwd_{os.getpid()}"


class ProjectBuilderWorkingDirectoryTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_root = Path(ag_tools.resolve_workspace_path(TEST_ROOT_REL))
        shutil.rmtree(self.test_root, ignore_errors=True)
        self.test_root.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.test_root, ignore_errors=True)

    def project(self, name="note-app"):
        path = self.test_root / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    async def test_relative_command_runs_inside_project_directory(self):
        project = self.project()
        (project / "probe.js").write_text(
            "console.log(process.cwd());\n", encoding="utf-8"
        )

        result = await project_builder._run_project_command(
            "node probe.js", str(project), str(project)
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.working_directory, os.path.realpath(project))
        self.assertIn(os.path.realpath(project), result.stdout.strip())
        self.assertFalse(result.timed_out)
        self.assertGreaterEqual(result.duration, 0)

    @unittest.skipUnless(shutil.which("node"), "Node is required for the WP1 regression")
    async def test_node_src_test_uses_project_file_not_jarvis_root(self):
        project = self.project()
        project_src = project / "src"
        project_src.mkdir()
        project_test = project_src / "test.js"
        project_test.write_text("console.log('PROJECT_FILE');\n", encoding="utf-8")

        workspace_root = Path(ag_tools.resolve_workspace_path("."))
        root_test = workspace_root / "src" / "test.js"
        root_existed = root_test.exists()
        root_bytes = root_test.read_bytes() if root_existed else None
        root_test.write_text("console.log('WRONG_ROOT_FILE');\n", encoding="utf-8")
        try:
            result = await project_builder._run_project_command(
                "node src/test.js", str(project), str(project)
            )
        finally:
            if root_existed:
                root_test.write_bytes(root_bytes or b"")
            else:
                root_test.unlink(missing_ok=True)

        self.assertTrue(result.ok)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("PROJECT_FILE", result.stdout)
        self.assertNotIn("WRONG_ROOT_FILE", result.stdout)

    async def test_missing_working_directory_is_blocked(self):
        missing = self.test_root / "missing"
        result = await project_builder._run_project_command(
            "node probe.js", str(missing), str(missing)
        )
        self.assertFalse(result.ok)
        self.assertIsNone(result.exit_code)
        self.assertIn("nao existe", result.stderr)

    async def test_working_directory_outside_projects_is_blocked(self):
        workspace_root = ag_tools.resolve_workspace_path(".")
        result = await project_builder._run_project_command(
            "node probe.js", workspace_root, workspace_root
        )
        self.assertFalse(result.ok)
        self.assertIsNone(result.exit_code)
        self.assertIn("root global", result.stderr)

    async def test_obsidian_working_directory_is_blocked(self):
        obsidian = self.project("obsidian_vault")
        result = await project_builder._run_project_command(
            "node probe.js", str(obsidian), str(obsidian)
        )
        self.assertFalse(result.ok)
        self.assertIsNone(result.exit_code)
        self.assertIn("Obsidian", result.stderr)

    @unittest.skipUnless(shutil.which("node"), "Node is required for command execution tests")
    async def test_path_with_spaces_environment_exit_code_and_streams_are_preserved(self):
        project = self.project("project with spaces")
        (project / "result.js").write_text(
            "console.log(process.env.PB_TEST_VALUE);\n"
            "console.error('EXPECTED_STDERR');\n"
            "process.exit(3);\n",
            encoding="utf-8",
        )
        result = await project_builder._run_project_command(
            "node result.js",
            str(project),
            str(project),
            environment={"PB_TEST_VALUE": "EXPECTED_STDOUT"},
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.exit_code, 3)
        self.assertIn("EXPECTED_STDOUT", result.stdout)
        self.assertIn("EXPECTED_STDERR", result.stderr)
        self.assertEqual(result.working_directory, os.path.realpath(project))

    @unittest.skipUnless(shutil.which("node"), "Node is required for timeout test")
    async def test_timeout_is_reported_without_losing_working_directory(self):
        project = self.project()
        result = await project_builder._run_project_command(
            "node -e \"setTimeout(() => {}, 2000)\"",
            str(project),
            str(project),
            timeout=0.05,
        )
        self.assertFalse(result.ok)
        self.assertTrue(result.timed_out)
        self.assertIsNone(result.exit_code)
        self.assertEqual(result.working_directory, os.path.realpath(project))

    def test_preview_process_receives_project_directory_as_cwd_and_directory(self):
        project = self.project("preview path with spaces")
        (project / "index.html").write_text("<h1>Preview</h1>", encoding="utf-8")
        process = MagicMock()
        with patch.object(project_builder.subprocess, "Popen", return_value=process) as popen:
            started, url = project_builder.start_static_preview(str(project))
        self.assertTrue(started)
        self.assertTrue(url.startswith("http://127.0.0.1:"))
        command = popen.call_args.args[0]
        kwargs = popen.call_args.kwargs
        self.assertEqual(kwargs["cwd"], os.path.realpath(project))
        self.assertEqual(command[command.index("--directory") + 1], os.path.realpath(project))
        project_builder._preview_processes.remove(process)


if __name__ == "__main__":
    unittest.main()
