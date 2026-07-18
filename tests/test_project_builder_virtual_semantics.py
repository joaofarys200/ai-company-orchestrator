import json
import os
import shutil
import unittest
from pathlib import Path

from agents import tools as ag_tools
from agents.orchestrator import project_builder


TEST_ROOT_REL = f"workspace/projects/_project_builder_virtual_{os.getpid()}"


class FakeRequester:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    async def __call__(self, prompt, correction=None):
        self.calls.append((prompt, correction))
        return self.responses.pop(0)


def minimal_plan(*, source="console.log('ok');\n", command="node --check app.js"):
    return {
        "project_name": "virtual-static-plan",
        "stack": "Node.js",
        "components": [],
        "files": [{"path": "app.js", "content": source}],
        "dependencies": [],
        "setup_commands": [],
        "validation_commands": [command],
        "entrypoints": ["app.js"],
        "preview_strategy": {},
        "preview_command": "",
        "constraints": [],
        "component_files": {},
        "rationale": "Virtual semantic validation fixture.",
    }


def wp1_regression_plan(*, valid=False, references_backend=False, include_preview=True):
    backend = (
        "import http from 'node:http';\n" if valid else ""
    ) + (
        "import fs from 'node:fs';\n"
        "const dataPath = new URL('./persistence/data.json', import.meta.url);\n"
        "function loadData() { return JSON.parse(fs.readFileSync(dataPath, 'utf8')); }\n"
        "function saveData(value) { fs.writeFileSync(dataPath, JSON.stringify(value)); }\n"
        "const server = http.createServer((req, res) => {\n"
        "  if (req.url === '/health') { res.end('ok'); return; }\n"
        "  res.end('missing');\n"
        "});\n"
        "server.listen(3001);\n"
    )
    if references_backend:
        test_source = (
            "import http from 'node:http';\n"
            "import '../backend/server.js';\n"
            "http.get('http://localhost:3001/health', () => {});\n"
        )
    else:
        test_source = (
            "import http from 'node:http';\n"
            "const alternate = http.createServer();\n"
            "alternate.listen(3001);\n"
            "http.get('http://localhost:3001/health', () => {});\n"
        )
    check_script = (
        "node --check backend/server.js && node --check tests/run-tests.js"
        if valid else
        "node --check backend/server.js && node --check frontend/index.html"
    )
    components = ["frontend", "backend", "persistence", "tests"]
    if include_preview:
        components.append("preview")
    return {
        "project_name": "full-stack-standalone-regression",
        "stack": "nodejs-standard-library",
        "components": components,
        "dependencies": [],
        "setup_commands": ["node --version"],
        "validation_commands": ["npm run check", "npm test"],
        "entrypoints": ["frontend/index.html", "backend/server.js"],
        "preview_strategy": {"kind": "static", "healthcheck_path": "/health"},
        "preview_command": "static",
        "constraints": ["Nao uses Obsidian"],
        "component_files": {
            "frontend": ["frontend/index.html"],
            "backend": ["backend/server.js"],
            "persistence": ["backend/server.js", "backend/persistence/data.json"],
            "tests": ["tests/run-tests.js"],
            "preview": ["frontend/index.html"],
        },
        "rationale": "Exact WP1 semantic regression fixture.",
        "files": [
            {
                "path": "package.json",
                "content": json.dumps({
                    "name": "fixture",
                    "type": "module",
                    "scripts": {
                        "check": check_script,
                        "test": "node tests/run-tests.js",
                        "build": "node --check backend/server.js",
                        "start": "node backend/server.js",
                    },
                }),
            },
            {"path": "backend/server.js", "content": backend},
            {"path": "backend/persistence/data.json", "content": "{}\n"},
            {"path": "frontend/index.html", "content": "<!doctype html><main>ok</main>\n"},
            {"path": "tests/run-tests.js", "content": test_source},
        ],
    }


def static_analysis(plan, prompt="Cria um projeto"):
    normalized, _ = project_builder.repair_project_plan_mechanically(plan)
    _source, result = project_builder._analyze_normalized_plan_artifacts(normalized, prompt)
    return result


def correction_response(original, corrected):
    original_files = {item["path"]: item["content"] for item in original["files"]}
    replacements = [
        {"path": item["path"], "content": item["content"]}
        for item in corrected["files"]
        if original_files.get(item["path"]) != item["content"]
    ]
    plan_updates = {
        field: corrected[field]
        for field in corrected
        if field != "files" and original.get(field) != corrected.get(field)
    }
    return {
        "plan_updates": plan_updates,
        "replacements": replacements,
    }


class ProjectBuilderVirtualSemanticsTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.root = Path(ag_tools.resolve_workspace_path(TEST_ROOT_REL))
        shutil.rmtree(self.root, ignore_errors=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_a_req_url_is_not_an_import(self):
        result = static_analysis(minimal_plan(source="function f(req) { return req.url; }\n"))
        self.assertNotIn("url", {item.symbol for item in result.errors if item.code == "MISSING_IMPORT"})

    def test_b_res_end_is_not_an_import(self):
        result = static_analysis(minimal_plan(source="function f(res) { res.end('ok'); }\n"))
        self.assertNotIn("end", {item.symbol for item in result.errors if item.code == "MISSING_IMPORT"})

    def test_c_console_log_is_not_an_import(self):
        result = static_analysis(minimal_plan())
        self.assertNotIn("log", {item.symbol for item in result.errors if item.code == "MISSING_IMPORT"})

    def test_d_http_namespace_without_import_is_rejected(self):
        result = static_analysis(minimal_plan(source="http.createServer(() => {});\n"))
        error = next(item for item in result.errors if item.code == "MISSING_IMPORT")
        self.assertEqual(error.symbol, "http")
        self.assertEqual(error.file, "app.js")

    def test_e_http_require_introduces_binding(self):
        result = static_analysis(minimal_plan(
            source="const http = require('http');\nhttp.createServer(() => {});\n"
        ))
        self.assertNotIn("MISSING_IMPORT", {item.code for item in result.errors})

    def test_f_http_namespace_import_introduces_binding(self):
        result = static_analysis(minimal_plan(
            source="import * as http from 'http';\nhttp.createServer(() => {});\n"
        ))
        self.assertNotIn("MISSING_IMPORT", {item.code for item in result.errors})

    def test_g_node_check_rejects_html_in_virtual_plan(self):
        plan = minimal_plan(command="node --check frontend/index.html")
        plan["files"].append({"path": "frontend/index.html", "content": "<main>ok</main>"})
        result = static_analysis(plan)
        error = next(item for item in result.errors if item.code == "COMMAND_TARGET_INVALID")
        self.assertEqual(error.field_path, "validation_commands[0]")
        self.assertEqual(error.target, "frontend/index.html")
        self.assertEqual(error.expected, "JavaScript source file")

    def test_h_node_check_accepts_planned_javascript(self):
        result = static_analysis(minimal_plan())
        self.assertNotIn("COMMAND_TARGET_INVALID", {item.code for item in result.errors})

    def test_i_script_target_must_be_planned(self):
        result = static_analysis(minimal_plan(command="node missing.js"))
        self.assertIn("MISSING_ENTRYPOINT", {item.code for item in result.errors})

    async def test_j_all_first_response_errors_reach_correction_prompt(self):
        first = wp1_regression_plan(include_preview=False)
        second = wp1_regression_plan(valid=True, references_backend=True)
        requester = FakeRequester(first, correction_response(first, second))

        await project_builder.get_valid_project_plan(
            "Cria uma app full stack com persistencia, testes e preview", requester
        )

        correction = json.loads(requester.calls[1][1])
        codes = {item["error_code"] for item in correction["errors"]}
        self.assertIn("MISSING_REQUESTED_COMPONENTS", codes)
        self.assertIn("COMMAND_TARGET_INVALID", codes)
        self.assertIn("MISSING_IMPORT", codes)
        self.assertIn("TEST_DOES_NOT_EXERCISE_ENTRYPOINT", codes)
        self.assertNotIn(
            "url",
            {
                evidence.get("symbol")
                for item in correction["errors"]
                if item["error_code"] == "MISSING_IMPORT"
                for evidence in item["evidence"]
            },
        )

    def test_k_semantic_validator_accumulates_three_errors(self):
        plan = wp1_regression_plan(include_preview=False)
        with self.assertRaises(project_builder._PlanValidationFailure) as captured:
            project_builder._validated_raw_project_plan(
                plan, "Cria uma app full stack com persistencia, testes e preview"
            )
        codes = {item.code for item in captured.exception.errors}
        self.assertTrue({
            "MISSING_REQUESTED_COMPONENTS",
            "COMMAND_TARGET_INVALID",
            "MISSING_IMPORT",
        }.issubset(codes))

    async def test_l_invalid_second_response_never_materializes(self):
        plan = wp1_regression_plan()
        requester = FakeRequester(plan, correction_response(plan, plan))
        result = await project_builder.build_project(
            "Cria uma app full stack com persistencia, testes e preview",
            plan_requester=requester,
            projects_root_rel=TEST_ROOT_REL,
            start_preview=False,
        )

        self.assertEqual(len(requester.calls), 2)
        self.assertEqual(result.status, "VALIDATION_FAILED")
        self.assertEqual(result.error_category, "PLAN_CORRECTION_FAILED")
        self.assertEqual(result.completion_reason, "PLAN_CORRECTION_FAILED")
        self.assertEqual(result.files_created, [])
        self.assertEqual(result.commands_executed, [])
        self.assertFalse(self.root.exists())
        self.assertEqual(result.progress_state["materialized_files"], [])

    @unittest.skipUnless(shutil.which("node"), "Node is required for materialization flow")
    async def test_m_valid_plan_still_materializes(self):
        result = await project_builder.build_project(
            "Cria app.js",
            plan_requester=FakeRequester(minimal_plan()),
            projects_root_rel=TEST_ROOT_REL,
            start_preview=False,
        )
        self.assertEqual(result.status, "SUCCEEDED")
        self.assertTrue(result.files_created)
        self.assertTrue(Path(result.project_dir, "app.js").is_file())

    def test_n_virtual_and_materialized_analysis_have_code_parity(self):
        data = wp1_regression_plan()
        virtual = static_analysis(data, "Cria uma app full stack com persistencia, testes e preview")
        project_dir = self.root / "parity"
        for item in data["files"]:
            path = project_dir / Path(*Path(item["path"]).parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(item["content"], encoding="utf-8")
        plan = project_builder.ProjectPlan(
            project_name=data["project_name"], stack=data["stack"],
            files=[project_builder.ProjectFile(**item) for item in data["files"]],
            validation_commands=data["validation_commands"], preview_command=data["preview_command"],
            components=data["components"], dependencies=data["dependencies"],
            setup_commands=data["setup_commands"], entrypoints=data["entrypoints"],
            preview_strategy=data["preview_strategy"], component_files=data["component_files"],
            constraints=data["constraints"], rationale=data["rationale"],
        )
        source = project_builder.PlannedFileSystem.from_materialized_project(str(project_dir), plan)
        materialized = project_builder.analyze_project_artifacts(
            source,
            components=plan.components,
            required_components=plan.components,
            entrypoints=plan.entrypoints,
            component_files=plan.component_files,
            dependencies=plan.dependencies,
            setup_commands=plan.setup_commands,
            validation_commands=plan.validation_commands,
            preview_command=plan.preview_command,
            preview_strategy=plan.preview_strategy,
            phase="PRE_VALIDATION",
        )
        self.assertEqual(
            {item.code for item in virtual.errors},
            {item.code for item in materialized.errors},
        )

    def test_o_alternate_server_does_not_exercise_backend(self):
        result = static_analysis(
            wp1_regression_plan(),
            "Cria uma app full stack com persistencia, testes e preview",
        )
        self.assertIn("TEST_DOES_NOT_EXERCISE_ENTRYPOINT", {item.code for item in result.errors})

    def test_p_explicit_backend_import_is_accepted(self):
        result = static_analysis(
            wp1_regression_plan(valid=True, references_backend=True),
            "Cria uma app full stack com persistencia, testes e preview",
        )
        self.assertNotIn("TEST_DOES_NOT_EXERCISE_ENTRYPOINT", {item.code for item in result.errors})


if __name__ == "__main__":
    unittest.main()
