import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from agents import tools as ag_tools
from agents.orchestrator import project_builder


TEST_ROOT_REL = f"workspace/projects/_project_builder_prevalidation_{os.getpid()}"


class FakeRequester:
    def __init__(self, response):
        self.response = response

    async def __call__(self, _prompt, _correction=None):
        return self.response


def backend_source(*, health=True, express=False):
    dependency = "const express = require('express');\nconst app = express();\n" if express else ""
    route = "if (request.url === '/health') { response.end('ok'); return; }\n" if health else ""
    return (
        f"{dependency}"
        "const http = require('node:http');\n"
        "const server = http.createServer((request, response) => {\n"
        f"  {route}"
        "  response.statusCode = 404; response.end('missing');\n"
        "});\n"
        "if (require.main === module) server.listen(Number(process.env.PORT) || 3000);\n"
    )


def backend_plan(name, *, source=None, entrypoints=None, commands=None):
    return {
        "project_name": name,
        "stack": "Node.js backend",
        "components": ["backend"],
        "files": [{"path": "server.js", "content": source or backend_source()}],
        "dependencies": [],
        "setup_commands": [],
        "validation_commands": commands or ["node --check server.js"],
        "entrypoints": entrypoints or ["server.js"],
        "preview_strategy": {"kind": "backend", "healthcheck_path": "/health"},
        "preview_command": "",
        "component_files": {"backend": ["server.js"]},
        "rationale": "Contrato focal de pre-validacao.",
    }


class ProjectBuilderPreValidationContractTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.root = Path(ag_tools.resolve_workspace_path(TEST_ROOT_REL))
        shutil.rmtree(self.root, ignore_errors=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    async def build(self, prompt, plan):
        return await project_builder.build_project(
            prompt,
            plan_requester=FakeRequester(plan),
            projects_root_rel=TEST_ROOT_REL,
            start_preview=False,
        )

    def assert_structured_failure(self, result, category):
        self.assertFalse(result.technical_success)
        self.assertEqual(result.status, "VALIDATION_FAILED")
        categories = {item["category"] for item in result.validation_errors}
        self.assertIn(category, categories)
        self.assertIn("CORRECTION_FULL_PLAN_FORBIDDEN", categories)
        self.assertEqual(result.error_category, "PLAN_CORRECTION_FAILED")
        self.assertEqual(result.commands_executed, [])
        self.assertEqual(result.files_created, [])
        self.assertFalse(result.preview_started)
        self.assertFalse(result.pre_validation["valid"])
        self.assertEqual(result.validation_plan, {})
        self.assertEqual(result.progress_state["current_phase"], "PLANNING")
        self.assertEqual(result.progress_state["commands_executed"], [])
        self.assertEqual(result.progress_state["artifacts_created"], [])
        self.assertEqual(result.progress_state["technical_success"], False)
        self.assertEqual(result.progress_state["completion_reason"], "PLAN_CORRECTION_FAILED")

    async def test_a_full_stack_without_frontend_is_structured_failure(self):
        plan = backend_plan("missing-frontend")
        plan["components"] = ["frontend", "backend"]
        plan["files"].append({"path": "client.js", "content": "console.log('client');\n"})
        plan["entrypoints"].append("client.js")
        plan["component_files"]["frontend"] = ["client.js"]

        result = await self.build("cria uma app full stack", plan)

        self.assert_structured_failure(result, "MISSING_REQUIRED_COMPONENT")
        self.assertIn("frontend", result.missing_components)

    async def test_b_missing_backend_entrypoint_is_structured_failure(self):
        result = await self.build(
            "cria um backend API",
            backend_plan("missing-entrypoint", entrypoints=["missing.js"]),
        )

        self.assert_structured_failure(result, "MISSING_ENTRYPOINT")

    async def test_c_incompatible_node_check_target_is_not_executed(self):
        plan = {
            "project_name": "invalid-target",
            "stack": "HTML",
            "components": ["frontend"],
            "files": [{"path": "index.html", "content": "<!doctype html><main>ok</main>"}],
            "dependencies": [],
            "setup_commands": [],
            "validation_commands": ["node --check index.html"],
            "entrypoints": ["index.html"],
            "preview_strategy": {"kind": "static"},
            "preview_command": "static",
            "component_files": {"frontend": ["index.html"]},
            "rationale": "Target deliberadamente incompativel.",
        }

        result = await self.build("cria uma pagina simples", plan)

        self.assert_structured_failure(result, "COMMAND_TARGET_INVALID")
        self.assertEqual(result.progress_state["processes"], [])

    async def test_d_undeclared_dependency_is_structured_failure(self):
        result = await self.build(
            "cria um backend API",
            backend_plan("undeclared-dependency", source=backend_source(express=True)),
        )

        self.assert_structured_failure(result, "MISSING_DECLARED_DEPENDENCY")

    async def test_e_missing_health_route_is_structured_failure(self):
        result = await self.build(
            "cria um backend API",
            backend_plan("missing-health", source=backend_source(health=False)),
        )

        self.assert_structured_failure(result, "MISSING_HEALTH_ROUTE")

    @unittest.skipUnless(shutil.which("node"), "Node is required for valid flow")
    async def test_f_valid_plan_keeps_normal_flow(self):
        result = await self.build("cria um backend API", backend_plan("valid-plan"))

        self.assertTrue(result.technical_success, result.validation_plan)
        self.assertEqual(result.status, "SUCCEEDED")
        self.assertTrue(result.pre_validation["valid"])
        self.assertGreaterEqual(len(result.commands_executed), 2)
        self.assertTrue(all(item.ok for item in result.commands_executed))

    async def test_g_internal_corruption_remains_internal_error(self):
        with patch.object(
            project_builder,
            "_prevalidation_errors_and_metadata",
            side_effect=RuntimeError("corrupt internal state"),
        ):
            with self.assertRaises(project_builder.ProjectBuilderInternalError) as captured:
                await self.build("cria um backend API", backend_plan("internal-error"))

        self.assertEqual(captured.exception.category, "INTERNAL_ERROR")
        self.assertEqual(captured.exception.primary_error["type"], "RuntimeError")
        self.assertIn("corrupt internal state", captured.exception.primary_error["message"])

    async def test_h_persistence_failure_is_not_converted_to_domain_error(self):
        failure = OSError("journal storage unavailable")
        with patch.object(
            project_builder.ProjectBuildJournal,
            "record_prevalidation",
            side_effect=failure,
        ):
            with self.assertRaises(OSError) as captured:
                await self.build("cria um backend API", backend_plan("persistence-error"))

        self.assertIs(captured.exception, failure)

    async def test_i_failed_result_survives_reload(self):
        result = await self.build(
            "cria um backend API",
            backend_plan("reload-failure", entrypoints=["missing.js"]),
        )

        journal = project_builder.ProjectBuildJournal.from_path(result.progress_path)
        reloaded = journal.snapshot()
        self.assertEqual(reloaded["status"], "VALIDATION_FAILED")
        self.assertEqual(reloaded["current_phase"], "PLANNING")
        self.assertEqual(reloaded["normalized_plan_hash"], "")
        self.assertEqual(reloaded["artifacts_created"], [])
        self.assertIn(
            "MISSING_ENTRYPOINT",
            {item["category"] for item in reloaded["validation_errors"]},
        )
        self.assertEqual(reloaded["commands_executed"], [])
        self.assertFalse(reloaded["static_analysis_results"]["valid"])
        self.assertIsNone(reloaded["pre_validation"])
        self.assertIsNone(reloaded["validation_plan"])
        self.assertEqual(len(reloaded["planning_validation_history"]), 2)
        self.assertTrue(reloaded["virtual_files"])
        self.assertTrue(all(item["content_hash"] for item in reloaded["virtual_files"]))
        self.assertTrue(reloaded["updated_at"])


if __name__ == "__main__":
    unittest.main()
