import json
import os
import shutil
import unittest
from pathlib import Path

from agents import tools as ag_tools
from agents.orchestrator import project_builder


TEST_ROOT_REL = f"workspace/projects/_project_builder_validation_{os.getpid()}"


class FakeRequester:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.last_response = self.responses[-1]
        self.calls = []

    async def __call__(self, prompt, correction=None):
        self.calls.append((prompt, correction))
        if self.responses:
            self.last_response = self.responses.pop(0)
        return self.last_response


def node_server(extra_line=""):
    return (
        "const http = require('node:http');\n"
        f"{extra_line}\n"
        "function createApp() {\n"
        "  return http.createServer((request, response) => {\n"
        "    if (request.url === '/health') {\n"
        "      response.writeHead(200, {'content-type': 'application/json'});\n"
        "      return response.end(JSON.stringify({status: 'ok'}));\n"
        "    }\n"
        "    response.writeHead(404); response.end('not found');\n"
        "  });\n"
        "}\n"
        "if (require.main === module) {\n"
        "  createApp().listen(Number(process.env.PORT) || 3000, '127.0.0.1');\n"
        "}\n"
        "module.exports = {createApp};\n"
    )


def backend_plan(name, *, files=None, components=None, setup=None, validation=None):
    return {
        "project_name": name,
        "stack": "Node.js backend",
        "components": components or ["backend"],
        "dependencies": [],
        "files": files or [{"path": "server.js", "content": node_server()}],
        "component_files": {"backend": ["server.js"]},
        "setup_commands": setup or [],
        "validation_commands": validation or ["node --check server.js"],
        "entrypoints": ["server.js"],
        "preview_strategy": {"kind": "backend", "healthcheck_path": "/health"},
        "preview_command": "",
        "rationale": "Validate syntax and the real backend health endpoint.",
    }


@unittest.skipUnless(shutil.which("node") and shutil.which("npm"), "Node and npm are required")
class ProjectBuilderValidationPlanTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.root = Path(ag_tools.resolve_workspace_path(TEST_ROOT_REL))
        shutil.rmtree(self.root, ignore_errors=True)

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
        shutil.rmtree(self.root, ignore_errors=True)

    async def build(self, prompt, plan, *, preview=False):
        return await project_builder.build_project(
            prompt,
            plan_requester=FakeRequester(plan),
            projects_root_rel=TEST_ROOT_REL,
            start_preview=preview,
        )

    async def test_a_superficial_check_cannot_hide_broken_entrypoint(self):
        plan = backend_plan(
            "surface-check",
            files=[
                {"path": "server.js", "content": node_server("require('./missing-module');")},
                {"path": "smoke.js", "content": "console.log(2 + 3);\n"},
            ],
            validation=["node smoke.js"],
        )

        result = await self.build("cria um backend API", plan)

        self.assertTrue(any(item.command == "node smoke.js" and item.ok for item in result.commands_executed))
        health = [item for item in result.commands_executed if item.category == "HEALTHCHECK"]
        self.assertEqual(len(health), 1)
        self.assertFalse(health[0].ok)
        self.assertFalse(result.technical_success)

    async def test_b_declared_jest_without_install_requires_setup(self):
        package = {
            "name": "jest-missing",
            "scripts": {"test": "jest --runInBand"},
            "devDependencies": {"jest": "^29.0.0"},
        }
        plan = backend_plan(
            "jest-missing",
            components=["backend", "tests"],
            files=[
                {"path": "package.json", "content": json.dumps(package)},
                {"path": "server.js", "content": node_server()},
                {"path": "tests/server.test.js", "content": "require('../server.js');\ntest('health', () => {});\n"},
            ],
            validation=["npm run test"],
        )

        result = await self.build("cria backend API com testes", plan)

        self.assertIn("not_installed:jest", result.validation_plan["missing_dependencies"])
        setup = result.validation_plan["setup_commands"]
        self.assertEqual(len(setup), 1)
        self.assertEqual(setup[0]["status"], "SKIPPED")
        self.assertFalse(result.technical_success)

    async def test_c_imported_express_reports_structured_failure_before_commands(self):
        plan = backend_plan(
            "undeclared-express",
            files=[{
                "path": "server.js",
                "content": "const express = require('express');\nconst app = express();\napp.listen(3000);\n",
            }],
        )
        requester = FakeRequester(plan)

        result = await project_builder.build_project(
            "cria um backend API",
            plan_requester=requester,
            projects_root_rel=TEST_ROOT_REL,
            start_preview=False,
        )

        self.assertFalse(result.technical_success)
        self.assertEqual(result.status, "VALIDATION_FAILED")
        self.assertEqual(result.commands_executed, [])
        self.assertIn(
            "MISSING_DECLARED_DEPENDENCY",
            {item["category"] for item in result.validation_errors},
        )
        self.assertEqual(result.error_category, "PLAN_CORRECTION_FAILED")
        self.assertIn(
            "CORRECTION_FULL_PLAN_FORBIDDEN",
            {item["category"] for item in result.validation_errors},
        )
        self.assertEqual(result.files_created, [])
        self.assertEqual(len(requester.calls), 2)

    async def test_d_blocked_required_setup_is_a_visible_failure(self):
        package = {
            "name": "blocked-setup",
            "scripts": {"test": "node --check server.js"},
            "dependencies": {"express": "^4.0.0"},
        }
        plan = backend_plan(
            "blocked-setup",
            files=[
                {"path": "package.json", "content": json.dumps(package)},
                {
                    "path": "server.js",
                    "content": "const express = require('express');\nconst app = express();\napp.get('/health', (_, r) => r.send('ok'));\napp.listen(process.env.PORT || 3000);\n",
                },
            ],
            setup=["npm install"],
            validation=["node --check server.js"],
        )

        result = await self.build("cria um backend API", plan)

        blocked = [item for item in result.commands_executed if item.command == "npm install"]
        self.assertEqual(len(blocked), 1)
        self.assertEqual(blocked[0].status, "BLOCKED")
        self.assertIn("setup-1", result.blocked_checks)
        self.assertFalse(result.technical_success)

    async def test_e_full_stack_without_real_frontend_reports_missing_component(self):
        plan = backend_plan(
            "missing-frontend",
            components=["frontend", "backend"],
            files=[
                {"path": "server.js", "content": node_server()},
                {"path": "client.js", "content": "console.log('not a browser entrypoint');\n"},
            ],
        )
        plan["component_files"]["frontend"] = ["client.js"]
        plan["entrypoints"].append("client.js")

        result = await self.build("cria uma app full stack", plan, preview=True)

        self.assertIn("frontend", result.missing_components)
        self.assertFalse(result.technical_success)
        self.assertFalse(result.preview_started)
        self.assertEqual(result.status, "VALIDATION_FAILED")
        self.assertEqual(result.error_category, "PLAN_CORRECTION_FAILED")
        self.assertIn(
            "MISSING_REQUIRED_COMPONENT",
            {item["category"] for item in result.validation_errors},
        )
        self.assertEqual(result.commands_executed, [])
        self.assertEqual(result.files_created, [])
        self.assertEqual(result.validation_plan, {})
        self.assertEqual(result.progress_state["current_phase"], "PLANNING")
        self.assertEqual(result.progress_state["completion_reason"], "PLAN_CORRECTION_FAILED")

    async def test_f_frontend_preview_does_not_hide_backend_failure(self):
        plan = backend_plan(
            "split-validation",
            components=["frontend", "backend"],
            files=[
                {"path": "index.html", "content": "<!doctype html><h1>Frontend</h1>"},
                {"path": "server.js", "content": node_server("require('./missing-module');")},
            ],
            validation=["node --check server.js"],
        )
        plan["component_files"]["frontend"] = ["index.html"]
        plan["entrypoints"].append("index.html")

        result = await self.build("cria uma app full stack", plan, preview=True)

        self.assertTrue(any(item.category == "PREVIEW" and item.ok for item in result.commands_executed))
        self.assertTrue(any(item.category == "HEALTHCHECK" and not item.ok for item in result.commands_executed))
        self.assertIn("frontend", result.validation_plan["validated_components"])
        self.assertNotIn("backend", result.validation_plan["validated_components"])
        self.assertFalse(result.technical_success)
        self.assertFalse(result.preview_started)

    async def test_g_official_package_test_failure_overrides_manual_pass(self):
        package = {
            "name": "official-test-fails",
            "scripts": {"test": "node tests/official.test.js"},
        }
        plan = backend_plan(
            "official-test-fails",
            components=["backend", "tests"],
            files=[
                {"path": "package.json", "content": json.dumps(package)},
                {"path": "server.js", "content": node_server()},
                {"path": "tests/manual.test.js", "content": "require('../server.js');\nconsole.log('manual pass');\n"},
                {"path": "tests/official.test.js", "content": "require('../server.js');\nprocess.exit(7);\n"},
            ],
            validation=["node tests/manual.test.js"],
        )

        result = await self.build("cria backend API com testes", plan)

        manual = [item for item in result.commands_executed if item.command == "node tests/manual.test.js"]
        official = [item for item in result.commands_executed if item.command == "npm run test"]
        self.assertEqual(len(manual), 1)
        self.assertTrue(manual[0].ok)
        self.assertEqual(len(official), 1)
        self.assertEqual(official[0].exit_code, 7)
        self.assertFalse(result.technical_success)

    async def test_h_valid_full_stack_project_has_complete_technical_evidence(self):
        package = {
            "name": "valid-full-stack",
            "scripts": {
                "test": "node tests/test.js",
                "check": "node --check server.js",
                "build": "node build.js",
                "start": "node server.js",
            },
        }
        server = (
            "const http = require('node:http');\n"
            "const fs = require('node:fs');\n"
            "const path = require('node:path');\n"
            "function createApp() { return http.createServer((request, response) => {\n"
            "  if (request.url === '/health') { response.writeHead(200); return response.end('ok'); }\n"
            "  if (request.url === '/api/notes') {\n"
            "    const notes = fs.readFileSync(path.join(__dirname, 'data/notes.json'), 'utf8');\n"
            "    response.writeHead(200, {'content-type': 'application/json'}); return response.end(notes);\n"
            "  }\n"
            "  response.writeHead(404); response.end('not found');\n"
            "}); }\n"
            "if (require.main === module) createApp().listen(Number(process.env.PORT) || 3000, '127.0.0.1');\n"
            "module.exports = {createApp};\n"
        )
        test_script = (
            "const http = require('node:http');\n"
            "const {createApp} = require('../server.js');\n"
            "const server = createApp().listen(0, '127.0.0.1', () => {\n"
            "  const port = server.address().port;\n"
            "  http.get(`http://127.0.0.1:${port}/health`, response => {\n"
            "    if (response.statusCode !== 200) process.exitCode = 1;\n"
            "    response.resume(); response.on('end', () => server.close());\n"
            "  }).on('error', error => { console.error(error); process.exitCode = 1; server.close(); });\n"
            "});\n"
        )
        build_script = (
            "const fs = require('node:fs');\n"
            "fs.mkdirSync('dist', {recursive: true});\n"
            "fs.copyFileSync('index.html', 'dist/index.html');\n"
        )
        plan = {
            "project_name": "valid-full-stack",
            "stack": "Node.js full stack",
            "components": ["frontend", "backend", "persistence", "tests", "preview"],
            "dependencies": [],
            "files": [
                {"path": "package.json", "content": json.dumps(package)},
                {"path": "index.html", "content": "<!doctype html><main id='app'></main><script>fetch('/api/notes')</script>"},
                {"path": "server.js", "content": server},
                {"path": "data/notes.json", "content": "[]\n"},
                {"path": "tests/test.js", "content": test_script},
                {"path": "build.js", "content": build_script},
            ],
            "component_files": {
                "frontend": ["index.html"],
                "backend": ["server.js"],
                "persistence": ["data/notes.json"],
                "tests": ["tests/test.js"],
            },
            "setup_commands": ["node --version"],
            "validation_commands": ["npm run test", "npm run check", "npm run build"],
            "entrypoints": ["server.js", "index.html"],
            "preview_strategy": {"kind": "static_and_backend", "healthcheck_path": "/health"},
            "preview_command": "static",
            "rationale": "Exercise the real backend, persistence, frontend preview and package scripts.",
        }

        result = await self.build(
            "cria uma app full stack com persistencia, testes e preview",
            plan,
            preview=True,
        )

        self.assertTrue(result.technical_success, result.validation_plan)
        self.assertTrue(result.preview_started)
        self.assertEqual(result.missing_components, [])
        self.assertTrue(all(item.ok for item in result.commands_executed))
        categories = {item["category"] for item in result.validation_plan["technical_evidence"]}
        self.assertTrue({
            "SETUP", "SYNTAX", "TEST", "BUILD", "HEALTHCHECK", "PREVIEW", "COMPONENT_COVERAGE",
        }.issubset(categories))
        self.assertEqual(
            set(result.validation_plan["validated_components"]),
            {"frontend", "backend", "persistence", "tests", "preview"},
        )

    async def test_i_required_blocked_command_never_disappears(self):
        package = {"name": "visible-block", "dependencies": {"left-pad": "1.3.0"}}
        plan = {
            "project_name": "visible-block",
            "stack": "Node.js",
            "components": [],
            "dependencies": ["left-pad"],
            "files": [
                {"path": "package.json", "content": json.dumps(package)},
                {"path": "app.js", "content": "console.log('app');\n"},
            ],
            "component_files": {},
            "setup_commands": ["npm install"],
            "validation_commands": ["node --check app.js"],
            "entrypoints": ["app.js"],
            "preview_strategy": {},
            "preview_command": "",
            "rationale": "The required setup must remain visible if blocked.",
        }

        result = await self.build("cria app.js", plan)

        planned = [item for item in result.validation_plan["setup_commands"] if item["command"] == "npm install"]
        executed = [item for item in result.commands_executed if item.command == "npm install"]
        self.assertEqual(len(planned), 1)
        self.assertEqual(planned[0]["status"], "BLOCKED")
        self.assertEqual(len(executed), 1)
        self.assertEqual(executed[0].status, "BLOCKED")
        self.assertFalse(result.technical_success)


if __name__ == "__main__":
    unittest.main()
