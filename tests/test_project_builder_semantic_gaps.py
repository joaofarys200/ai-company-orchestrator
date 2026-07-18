import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

from agents import tools as ag_tools
from agents.orchestrator import project_builder


TEST_ROOT_REL = f"workspace/projects/_project_builder_semantic_gaps_{os.getpid()}"
OBJECTIVE = "Cria um backend com persistencia e testes"


class FakeRequester:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    async def __call__(self, prompt, correction=None):
        self.calls.append((prompt, correction))
        return self.responses.pop(0)


def backend_source(*, durable=False):
    persistence = (
        "import { readFile, writeFile } from 'node:fs/promises';\n"
        "const dataUrl = new URL('./data.json', import.meta.url);\n"
        "async function loadData() { return JSON.parse(await readFile(dataUrl, 'utf8')); }\n"
        "async function saveData(value) { await writeFile(dataUrl, JSON.stringify(value)); }\n"
        if durable else
        "const records = [];\nconst cache = new Map();\n"
    )
    return (
        "import http from 'node:http';\n"
        f"{persistence}"
        "const server = http.createServer((request, response) => {\n"
        "  if (request.url === '/health') { response.end('ok'); return; }\n"
        "  response.end(JSON.stringify(records || []));\n"
        "});\n"
        "server.listen(Number(process.env.PORT) || 3001);\n"
    )


def valid_test_source(handler="error => { console.error(error); process.exitCode = 1; }"):
    return (
        "import http from 'node:http';\n"
        "import '../backend/server.js';\n"
        "const runTests = () => new Promise((resolve, reject) => {\n"
        "  http.get('http://127.0.0.1:3001/health', resolve).on('error', reject);\n"
        "});\n"
        f"runTests().catch({handler});\n"
    )


def plan_with_test(test_source):
    return {
        "project_name": "test-propagation",
        "stack": "Node.js",
        "components": ["backend", "tests"],
        "files": [
            {"path": "package.json", "content": json.dumps({
                "name": "test-propagation",
                "type": "module",
                "scripts": {"test": "node tests/run-tests.js", "check": "node --check backend/server.js"},
            })},
            {"path": "backend/server.js", "content": backend_source()},
            {"path": "tests/run-tests.js", "content": test_source},
        ],
        "dependencies": [],
        "setup_commands": [],
        "validation_commands": ["npm test"],
        "entrypoints": ["backend/server.js"],
        "preview_strategy": {"kind": "backend", "healthcheck_path": "/health"},
        "preview_command": "",
        "constraints": [],
        "component_files": {
            "backend": ["backend/server.js"],
            "tests": ["tests/run-tests.js"],
        },
        "rationale": "Exercise the real backend and propagate failures.",
    }


def persistence_plan(*, durable=False, persistence_paths=None, include_tests=False):
    components = ["backend", "persistence"]
    files = [
        {"path": "backend/server.js", "content": backend_source(durable=durable)},
        {"path": "backend/data.json", "content": "[]\n"},
    ]
    mappings = {
        "backend": ["backend/server.js"],
        "persistence": list(
            ["backend/server.js", "backend/data.json"]
            if persistence_paths is None else persistence_paths
        ),
    }
    if include_tests:
        components.append("tests")
        files.append({"path": "tests/run-tests.js", "content": valid_test_source("console.error")})
        mappings["tests"] = ["tests/run-tests.js"]
    return {
        "project_name": "persistence-contract",
        "stack": "Node.js",
        "components": components,
        "files": files,
        "dependencies": [],
        "setup_commands": [],
        "validation_commands": ["node --check backend/server.js"],
        "entrypoints": ["backend/server.js"],
        "preview_strategy": {"kind": "backend", "healthcheck_path": "/health"},
        "preview_command": "",
        "constraints": [],
        "component_files": mappings,
        "rationale": "Persistence must be durable.",
    }


def static_analysis(plan, prompt=OBJECTIVE):
    normalized, _repairs = project_builder.repair_project_plan_mechanically(plan)
    _source, result = project_builder._analyze_normalized_plan_artifacts(normalized, prompt)
    return result


def project_plan(data):
    return project_builder.ProjectPlan(
        project_name=data["project_name"],
        stack=data["stack"],
        files=[project_builder.ProjectFile(**item) for item in data["files"]],
        validation_commands=data["validation_commands"],
        preview_command=data["preview_command"],
        components=data["components"],
        dependencies=data["dependencies"],
        setup_commands=data["setup_commands"],
        entrypoints=data["entrypoints"],
        preview_strategy=data["preview_strategy"],
        component_files=data["component_files"],
        constraints=data["constraints"],
        rationale=data["rationale"],
    )


class ProjectBuilderSemanticGapsTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.root = Path(ag_tools.resolve_workspace_path(TEST_ROOT_REL))
        shutil.rmtree(self.root, ignore_errors=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def propagation_codes(self, source):
        result = static_analysis(plan_with_test(source), "Cria backend com testes")
        return {item.code for item in result.errors}

    def test_01_direct_console_error_catch_is_invalid(self):
        self.assertIn(
            "TEST_FAILURE_NOT_PROPAGATED",
            self.propagation_codes(valid_test_source("console.error")),
        )

    def test_02_console_only_catch_handler_is_invalid(self):
        self.assertIn(
            "TEST_FAILURE_NOT_PROPAGATED",
            self.propagation_codes(valid_test_source("error => { console.error(error); }")),
        )

    def test_03_nonzero_exit_code_is_valid(self):
        self.assertNotIn(
            "TEST_FAILURE_NOT_PROPAGATED",
            self.propagation_codes(valid_test_source()),
        )

    def test_04_nonzero_process_exit_is_valid(self):
        self.assertNotIn(
            "TEST_FAILURE_NOT_PROPAGATED",
            self.propagation_codes(valid_test_source("error => { console.log(error); process.exit(1); }")),
        )

    def test_05_rethrow_is_valid(self):
        self.assertNotIn(
            "TEST_FAILURE_NOT_PROPAGATED",
            self.propagation_codes(valid_test_source("error => { console.error(error); throw error; }")),
        )

    def test_06_declared_persistence_with_empty_mapping_is_invalid(self):
        result = static_analysis(persistence_plan(persistence_paths=[]))
        issue = next(item for item in result.errors if item.code == "DECLARED_COMPONENT_WITHOUT_ARTIFACTS")
        self.assertEqual(issue.component, "persistence")
        self.assertEqual(issue.field_path, "component_files.persistence")
        self.assertEqual(issue.actual, "[]")

    def test_07_declared_component_with_missing_path_is_invalid(self):
        result = static_analysis(persistence_plan(persistence_paths=["backend/missing.js"]))
        self.assertIn("DECLARED_COMPONENT_WITHOUT_ARTIFACTS", {item.code for item in result.errors})

    def test_08_module_state_does_not_implement_persistence(self):
        result = static_analysis(persistence_plan())
        self.assertIn("PERSISTENCE_NOT_IMPLEMENTED", {item.code for item in result.errors})

    def test_09_node_fs_promises_read_write_implements_persistence(self):
        result = static_analysis(persistence_plan(durable=True))
        self.assertNotIn("PERSISTENCE_NOT_IMPLEMENTED", {item.code for item in result.errors})

    def test_09b_read_and_write_can_be_split_across_mapped_artifacts(self):
        plan = persistence_plan()
        plan["files"][0]["content"] = (
            "import http from 'node:http';\n"
            "import { readFile } from 'node:fs/promises';\n"
            "async function loadData() { return readFile(new URL('./data.json', import.meta.url)); }\n"
            "http.createServer((request, response) => {\n"
            "  if (request.url === '/health') response.end('ok'); else response.end('missing');\n"
            "}).listen(3001);\n"
        )
        plan["files"].append({
            "path": "backend/store-writer.js",
            "content": (
                "import { writeFile } from 'node:fs/promises';\n"
                "export async function saveData(value) {\n"
                "  await writeFile(new URL('./data.json', import.meta.url), JSON.stringify(value));\n"
                "}\n"
            ),
        })
        plan["component_files"]["persistence"] = [
            "backend/server.js", "backend/store-writer.js", "backend/data.json",
        ]
        result = static_analysis(plan)
        self.assertNotIn("PERSISTENCE_NOT_IMPLEMENTED", {item.code for item in result.errors})

    def test_10_backend_can_map_to_backend_and_persistence(self):
        plan = persistence_plan(durable=True, persistence_paths=["backend/server.js"])
        result = static_analysis(plan)
        codes = {item.code for item in result.errors}
        self.assertNotIn("DECLARED_COMPONENT_WITHOUT_ARTIFACTS", codes)
        self.assertNotIn("PERSISTENCE_NOT_IMPLEMENTED", codes)
        self.assertIn("backend/server.js", plan["component_files"]["backend"])
        self.assertIn("backend/server.js", plan["component_files"]["persistence"])

    def test_11_focal_scope_maps_test_persistence_and_component_files(self):
        data = persistence_plan(include_tests=True)
        with self.assertRaises(project_builder._PlanValidationFailure) as captured:
            project_builder._validated_raw_project_plan(data, OBJECTIVE)
        failure = captured.exception
        mappings = {item["code"]: item for item in failure.error_artifact_mappings}
        self.assertEqual(
            mappings["TEST_FAILURE_NOT_PROPAGATED"]["affected_artifacts"],
            ["tests/run-tests.js"],
        )
        self.assertIn(
            "backend/server.js",
            mappings["PERSISTENCE_NOT_IMPLEMENTED"]["affected_artifacts"],
        )
        scope, plan_updates, replacements = project_builder._focal_correction_scope(failure)
        self.assertEqual(scope["TEST_FAILURE_NOT_PROPAGATED"]["replacements"], ["tests/run-tests.js"])
        self.assertEqual(scope["PERSISTENCE_NOT_IMPLEMENTED"]["plan_updates"], ["component_files"])
        self.assertIn("component_files", plan_updates)
        self.assertTrue({"backend/server.js", "tests/run-tests.js"}.issubset(replacements))

    async def test_12_semantic_failure_prevents_materialization_and_third_call(self):
        first = persistence_plan(persistence_paths=[])
        requester = FakeRequester(first, {"plan_updates": {}, "replacements": []})
        result = await project_builder.build_project(
            OBJECTIVE,
            plan_requester=requester,
            projects_root_rel=TEST_ROOT_REL,
            start_preview=False,
        )
        self.assertEqual(len(requester.calls), project_builder.PLAN_MAX_ATTEMPTS)
        self.assertEqual(result.files_created, [])
        self.assertEqual(result.commands_executed, [])
        self.assertFalse(self.root.exists())
        self.assertEqual(result.completion_reason, "PLAN_CORRECTION_FAILED")

    @unittest.skipUnless(shutil.which("node"), "Node is required for the real rejection check")
    async def test_13_zero_exit_rejection_never_produces_test_evidence(self):
        self.root.mkdir(parents=True)
        swallowed = self.root / "swallowed.js"
        swallowed.write_text("Promise.reject(new Error('boom')).catch(console.error);\n", encoding="utf-8")
        observed = subprocess.run(
            [shutil.which("node"), str(swallowed)],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(observed.returncode, 0)

        data = plan_with_test(valid_test_source("console.error"))
        project_dir = self.root / "defense-test"
        for item in data["files"]:
            path = project_dir / Path(item["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(item["content"], encoding="utf-8")
        plan = project_plan(data)
        validation = project_builder.ValidationPlan(
            required_components=["backend", "tests"],
            materialized_components=["backend", "tests"],
        )
        validation.validation_commands.append(project_builder._new_check(
            "package-test", "npm test", str(project_dir), "TEST", "test fixture"
        ))
        executed, _skipped, preview, _url = await project_builder._execute_validation_plan(
            validation, plan, str(project_dir), False
        )
        self.assertFalse(preview)
        self.assertEqual([item.command_id for item in executed], ["technical-validation-gate"])
        self.assertFalse(any(item["category"] == "TEST" for item in validation.technical_evidence))
        self.assertIn("technical-validation-gate", validation.failed_checks)

    async def test_14_gate_detects_memory_persistence_if_semantic_validation_is_bypassed(self):
        data = persistence_plan()
        project_dir = self.root / "defense-persistence"
        for item in data["files"]:
            path = project_dir / Path(item["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(item["content"], encoding="utf-8")
        plan = project_plan(data)
        validation = project_builder.ValidationPlan(
            required_components=["backend", "persistence"],
            materialized_components=["backend"],
        )
        validation.validation_commands.append(project_builder._new_check(
            "syntax", "node --check backend/server.js", str(project_dir), "SYNTAX", "test fixture"
        ))
        executed, _skipped, _preview, _url = await project_builder._execute_validation_plan(
            validation, plan, str(project_dir), False
        )
        self.assertEqual(executed[0].command_id, "technical-validation-gate")
        self.assertEqual(executed[0].error_category, "PERSISTENCE_NOT_IMPLEMENTED")
        self.assertIn(
            "PERSISTENCE_NOT_IMPLEMENTED",
            {item["category"] for item in validation.static_errors},
        )


if __name__ == "__main__":
    unittest.main()
