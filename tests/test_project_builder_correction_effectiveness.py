import hashlib
import json
import os
import shutil
import unittest
from copy import deepcopy
from pathlib import Path

from agents import tools as ag_tools
from agents.orchestrator import project_builder


TEST_ROOT_REL = f"workspace/projects/_correction_effectiveness_{os.getpid()}"
OBJECTIVE = "Cria uma app full stack com persistencia, testes e preview"


class FakeRequester:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    async def __call__(self, prompt, correction=None):
        self.calls.append((prompt, correction))
        return self.responses.pop(0)


def wp1_plan(*, valid_command=False, real_backend_test=False, include_preview=True):
    check_target = "tests/run-tests.js" if valid_command else "frontend/index.html"
    test_source = (
        "import http from 'node:http';\n"
        "import { spawn } from 'node:child_process';\n"
        "import { once } from 'node:events';\n"
        "const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));\n"
        "const backend = spawn(process.execPath, ['backend/server.js'], { stdio: 'ignore', windowsHide: true });\n"
        "const health = () => new Promise((resolve, reject) => {\n"
        "  const request = http.get('http://127.0.0.1:3001/health', (response) => {\n"
        "    let body = '';\n"
        "    response.on('data', (chunk) => { body += chunk; });\n"
        "    response.on('end', () => resolve({ statusCode: response.statusCode, body }));\n"
        "  });\n"
        "  request.on('error', reject);\n"
        "});\n"
        "try {\n"
        "  let result;\n"
        "  for (let attempt = 0; attempt < 20; attempt += 1) {\n"
        "    try { result = await health(); break; } catch { await delay(50); }\n"
        "  }\n"
        "  if (!result || result.statusCode !== 200 || result.body !== 'ok') process.exitCode = 1;\n"
        "} finally {\n"
        "  backend.kill();\n"
        "  await Promise.race([once(backend, 'exit'), delay(1000)]);\n"
        "}\n"
        if real_backend_test else
        "import http from 'node:http';\n"
        "const alternate = http.createServer();\n"
        "alternate.listen(3001);\n"
        "http.get('http://localhost:3001/health', () => {});\n"
    )
    components = ["frontend", "backend", "persistence", "tests"]
    if include_preview:
        components.append("preview")
    package = {
        "name": "correction-effectiveness",
        "type": "module",
        "scripts": {
            "check": f"node --check backend/server.js && node --check {check_target}",
            "test": "node tests/run-tests.js",
            "build": "node --check backend/server.js",
            "start": "node backend/server.js",
        },
    }
    return {
        "project_name": "correction-effectiveness",
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
        "rationale": "Correction effectiveness fixture.",
        "files": [
            {"path": "package.json", "content": json.dumps(package)},
            {
                "path": "backend/server.js",
                "content": (
                    "import http from 'node:http';\n"
                    "import fs from 'node:fs';\n"
                    "const dataPath = new URL('./persistence/data.json', import.meta.url);\n"
                    "function loadData() { return JSON.parse(fs.readFileSync(dataPath, 'utf8')); }\n"
                    "function saveData(value) { fs.writeFileSync(dataPath, JSON.stringify(value)); }\n"
                    "const server = http.createServer((req, res) => {\n"
                    "  if (req.url === '/health') { res.end('ok'); return; }\n"
                    "  res.end('missing');\n"
                    "});\n"
                    "server.listen(3001);\n"
                ),
            },
            {"path": "backend/persistence/data.json", "content": "{}\n"},
            {"path": "frontend/index.html", "content": "<!doctype html><main>ok</main>\n"},
            {"path": "tests/run-tests.js", "content": test_source},
        ],
    }


def content(plan, path):
    return next(item["content"] for item in plan["files"] if item["path"] == path)


def replacement(plan, path):
    return {"path": path, "content": content(plan, path)}


def focal_correction(*, plan_updates=None, replacements=None):
    return {
        "plan_updates": deepcopy(plan_updates or {}),
        "replacements": deepcopy(replacements or []),
    }


class ProjectBuilderCorrectionEffectivenessTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.root = Path(ag_tools.resolve_workspace_path(TEST_ROOT_REL))
        shutil.rmtree(self.root, ignore_errors=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    async def test_a_valid_single_file_correction(self):
        first = wp1_plan(real_backend_test=True)
        second = wp1_plan(valid_command=True, real_backend_test=True)
        requester = FakeRequester(first, focal_correction(
            replacements=[replacement(second, "package.json")],
        ))

        plan = await project_builder.get_valid_project_plan(OBJECTIVE, requester)

        effectiveness = plan.planning_diagnostics["correction_effectiveness"]
        self.assertTrue(effectiveness["valid"])
        self.assertTrue(effectiveness["manifest_verified"])
        self.assertEqual(effectiveness["replacements_received"], 1)
        self.assertEqual(effectiveness["replacements_applied"], 1)
        self.assertEqual(effectiveness["revalidation"]["semantic"], "PASSED")
        package = json.loads(next(item.content for item in plan.files if item.path == "package.json"))
        self.assertNotIn("frontend/index.html", package["scripts"]["check"])

    async def test_b_valid_multiple_file_correction(self):
        first = wp1_plan()
        second = wp1_plan(valid_command=True, real_backend_test=True)
        backend = next(item for item in second["files"] if item["path"] == "backend/server.js")
        backend["content"] += "// testable backend entrypoint\n"
        requester = FakeRequester(first, focal_correction(
            replacements=[
                replacement(second, "package.json"),
                replacement(second, "tests/run-tests.js"),
                replacement(second, "backend/server.js"),
            ],
        ))

        plan = await project_builder.get_valid_project_plan(OBJECTIVE, requester)

        effectiveness = plan.planning_diagnostics["correction_effectiveness"]
        self.assertEqual(effectiveness["replacements_applied"], 3)
        self.assertEqual(
            set(effectiveness["changed_artifacts"]),
            {"package.json", "tests/run-tests.js", "backend/server.js"},
        )

    async def test_c_valid_plan_updates_only(self):
        first = wp1_plan(valid_command=True, real_backend_test=True, include_preview=False)
        requester = FakeRequester(first, focal_correction(
            plan_updates={
                "components": ["frontend", "backend", "persistence", "tests", "preview"],
            },
        ))

        plan = await project_builder.get_valid_project_plan(OBJECTIVE, requester)

        self.assertIn("preview", plan.components)
        effectiveness = plan.planning_diagnostics["correction_effectiveness"]
        self.assertEqual(effectiveness["plan_update_fields"], ["components"])
        self.assertEqual(effectiveness["replacements_received"], 0)

    async def test_c2_components_delta_only_is_rejected(self):
        first = wp1_plan(valid_command=True, real_backend_test=True, include_preview=False)
        requester = FakeRequester(first, focal_correction(
            plan_updates={"components": ["preview"]},
        ))

        with self.assertRaises(project_builder.ProjectBuilderPlanningError) as captured:
            await project_builder.get_valid_project_plan(OBJECTIVE, requester)

        errors = captured.exception.diagnostics["final_validation"]["errors"]
        self.assertIn("CORRECTION_PLAN_UPDATE_OUT_OF_SCOPE", {item["code"] for item in errors})

    async def test_d_invalid_json_is_rejected(self):
        first = wp1_plan(real_backend_test=True)
        requester = FakeRequester(first, "not-json")

        with self.assertRaises(project_builder.ProjectBuilderPlanningError) as captured:
            await project_builder.get_valid_project_plan(OBJECTIVE, requester)

        self.assertEqual(captured.exception.category, "PLAN_CORRECTION_FAILED")
        self.assertEqual(
            captured.exception.diagnostics["correction_rejection_reason"],
            "CORRECTION_JSON_INVALID",
        )

    async def test_e_declared_file_with_equal_hash_is_rejected(self):
        first = wp1_plan(real_backend_test=True)
        requester = FakeRequester(first, focal_correction(
            replacements=[replacement(first, "package.json")],
        ))

        with self.assertRaises(project_builder.ProjectBuilderPlanningError) as captured:
            await project_builder.get_valid_project_plan(OBJECTIVE, requester)

        codes = {item["code"] for item in captured.exception.diagnostics["final_validation"]["errors"]}
        self.assertIn("CORRECTION_DECLARED_FILE_UNCHANGED", codes)

    async def test_f_model_correction_manifest_is_rejected(self):
        first = wp1_plan(real_backend_test=True)
        second = wp1_plan(valid_command=True, real_backend_test=True)
        correction = focal_correction(
            replacements=[replacement(second, "package.json")],
        )
        correction["correction_manifest"] = [{
            "error_code": "COMMAND_TARGET_INVALID",
            "changed_artifacts": ["package.json"],
            "resolution": "Model claim",
        }]
        requester = FakeRequester(first, correction)

        with self.assertRaises(project_builder.ProjectBuilderPlanningError) as captured:
            await project_builder.get_valid_project_plan(OBJECTIVE, requester)

        codes = {item["code"] for item in captured.exception.diagnostics["final_validation"]["errors"]}
        self.assertIn("CORRECTION_RESPONSE_SCHEMA_INVALID", codes)

    async def test_g_file_outside_allowlist_is_rejected(self):
        first = wp1_plan(real_backend_test=True)
        altered = deepcopy(first)
        frontend = next(item for item in altered["files"] if item["path"] == "frontend/index.html")
        frontend["content"] += "<!-- unrelated -->\n"
        requester = FakeRequester(first, focal_correction(
            replacements=[replacement(altered, "frontend/index.html")],
        ))

        with self.assertRaises(project_builder.ProjectBuilderPlanningError) as captured:
            await project_builder.get_valid_project_plan(OBJECTIVE, requester)

        codes = {item["code"] for item in captured.exception.diagnostics["final_validation"]["errors"]}
        self.assertIn("CORRECTION_REPLACEMENT_OUT_OF_SCOPE", codes)

    async def test_h_duplicate_replacement_path_is_rejected(self):
        first = wp1_plan(real_backend_test=True)
        second = wp1_plan(valid_command=True, real_backend_test=True)
        fixed = replacement(second, "package.json")
        requester = FakeRequester(first, focal_correction(
            replacements=[fixed, deepcopy(fixed)],
        ))

        with self.assertRaises(project_builder.ProjectBuilderPlanningError) as captured:
            await project_builder.get_valid_project_plan(OBJECTIVE, requester)

        codes = {item["code"] for item in captured.exception.diagnostics["final_validation"]["errors"]}
        self.assertIn("CORRECTION_DUPLICATE_PATH", codes)

    async def test_i_complete_plan_response_is_rejected(self):
        first = wp1_plan(real_backend_test=True)
        second = wp1_plan(valid_command=True, real_backend_test=True)
        requester = FakeRequester(first, {
            "corrected_plan": second,
        })

        with self.assertRaises(project_builder.ProjectBuilderPlanningError) as captured:
            await project_builder.get_valid_project_plan(OBJECTIVE, requester)

        codes = {item["code"] for item in captured.exception.diagnostics["final_validation"]["errors"]}
        self.assertIn("CORRECTION_FULL_PLAN_FORBIDDEN", codes)

    async def test_j_fixing_one_error_while_retaining_another_fails_revalidation(self):
        first = wp1_plan()
        second = wp1_plan(valid_command=True)
        stale_test = content(first, "tests/run-tests.js") + "// changed but still synthetic\n"
        requester = FakeRequester(first, focal_correction(
            replacements=[
                replacement(second, "package.json"),
                {"path": "tests/run-tests.js", "content": stale_test},
            ],
        ))

        with self.assertRaises(project_builder.ProjectBuilderPlanningError) as captured:
            await project_builder.get_valid_project_plan(OBJECTIVE, requester)

        self.assertEqual(captured.exception.category, "PLAN_SEMANTIC_INVALID")
        revalidation = captured.exception.diagnostics["correction_revalidation"]
        self.assertEqual(revalidation["semantic"], "FAILED")
        self.assertIn(
            "TEST_DOES_NOT_EXERCISE_ENTRYPOINT",
            {item["code"] for item in revalidation["errors"]},
        )

    async def test_k_new_semantic_error_is_rejected(self):
        first = wp1_plan(real_backend_test=True)
        broken_package = json.loads(content(first, "package.json"))
        broken_package["scripts"]["check"] = "node --check missing.js"
        requester = FakeRequester(first, focal_correction(
            replacements=[{"path": "package.json", "content": json.dumps(broken_package)}],
        ))

        with self.assertRaises(project_builder.ProjectBuilderPlanningError) as captured:
            await project_builder.get_valid_project_plan(OBJECTIVE, requester)

        self.assertEqual(captured.exception.category, "PLAN_SEMANTIC_INVALID")
        revalidation = captured.exception.diagnostics["correction_revalidation"]
        self.assertIn("MISSING_ENTRYPOINT", {item["code"] for item in revalidation["errors"]})

    def test_l_failed_application_preserves_original_plan_and_vfs(self):
        first = wp1_plan(real_backend_test=True)
        try:
            project_builder._validated_raw_project_plan(first, OBJECTIVE)
        except project_builder._PlanValidationFailure as failure:
            first_failure = failure
        else:
            self.fail("The fixture must fail semantic validation")
        original_plan = deepcopy(first_failure.parsed_plan)
        original_hashes = project_builder._safe_correction_source(original_plan).hashes()

        with self.assertRaises(project_builder._PlanValidationFailure):
            project_builder._validated_correction_response(
                focal_correction(
                    replacements=[{
                        "path": "frontend/index.html",
                        "content": "<!doctype html><main>changed</main>\n",
                    }],
                ),
                OBJECTIVE,
                first_failure,
            )

        self.assertEqual(first_failure.parsed_plan, original_plan)
        self.assertEqual(
            project_builder._safe_correction_source(first_failure.parsed_plan).hashes(),
            original_hashes,
        )

    async def test_m_three_required_wp1_errors_are_corrected_focally(self):
        first = wp1_plan(include_preview=False)
        second = wp1_plan(valid_command=True, real_backend_test=True, include_preview=True)
        requester = FakeRequester(first, focal_correction(
            plan_updates={"components": second["components"]},
            replacements=[
                replacement(second, "package.json"),
                replacement(second, "tests/run-tests.js"),
            ],
        ))

        plan = await project_builder.get_valid_project_plan(OBJECTIVE, requester)

        self.assertIn("preview", plan.components)
        self.assertEqual(
            set(plan.planning_diagnostics["correction_effectiveness"]["changed_artifacts"]),
            {"components", "package.json", "tests/run-tests.js"},
        )

    async def test_n_html_rename_to_javascript_is_rejected(self):
        first = wp1_plan(real_backend_test=True)
        requester = FakeRequester(first, focal_correction(
            replacements=[{
                "path": "frontend/index.html.mjs",
                "content": content(first, "frontend/index.html"),
            }],
        ))

        with self.assertRaises(project_builder.ProjectBuilderPlanningError) as captured:
            await project_builder.get_valid_project_plan(OBJECTIVE, requester)

        codes = {item["code"] for item in captured.exception.diagnostics["final_validation"]["errors"]}
        self.assertIn("CORRECTION_REPLACEMENT_OUT_OF_SCOPE", codes)

    async def test_o_synthetic_alternate_server_still_fails(self):
        first = wp1_plan(valid_command=True)
        synthetic = content(first, "tests/run-tests.js") + "// still an alternate server\n"
        requester = FakeRequester(first, focal_correction(
            replacements=[{"path": "tests/run-tests.js", "content": synthetic}],
        ))

        with self.assertRaises(project_builder.ProjectBuilderPlanningError) as captured:
            await project_builder.get_valid_project_plan(OBJECTIVE, requester)

        self.assertEqual(captured.exception.category, "PLAN_SEMANTIC_INVALID")
        self.assertIn(
            "TEST_DOES_NOT_EXERCISE_ENTRYPOINT",
            {item["code"] for item in captured.exception.diagnostics["correction_revalidation"]["errors"]},
        )

    async def test_p_prompt_is_focal_and_contains_only_allowlisted_files(self):
        first = wp1_plan(include_preview=False)
        second = wp1_plan(valid_command=True, real_backend_test=True)
        requester = FakeRequester(first, focal_correction(
            plan_updates={"components": second["components"]},
            replacements=[
                replacement(second, "package.json"),
                replacement(second, "tests/run-tests.js"),
            ],
        ))

        await project_builder.get_valid_project_plan(OBJECTIVE, requester)

        payload = json.loads(requester.calls[1][1])
        self.assertEqual(payload["protocol"], project_builder.FOCAL_CORRECTION_PROTOCOL)
        self.assertNotIn("normalized_previous_plan", payload)
        self.assertNotIn("virtual_file_system", payload)
        self.assertNotIn("corrected_plan", payload["response_schema"])
        self.assertEqual(
            set(payload["response_schema"]),
            {"plan_updates", "replacements"},
        )
        self.assertTrue(payload["model_generated_manifest_forbidden"])
        self.assertEqual(
            set(payload["affected_files"]),
            {"package.json", "tests/run-tests.js", "backend/server.js"},
        )
        self.assertNotIn("frontend/index.html", payload["affected_files"])
        self.assertEqual(
            payload["affected_files"]["package.json"]["content_hash"],
            hashlib.sha256(content(first, "package.json").encode("utf-8")).hexdigest(),
        )
        component_context = payload["plan_update_context"]["components"]
        self.assertEqual(
            component_context["original_complete_value"],
            ["frontend", "backend", "persistence", "tests"],
        )
        self.assertEqual(component_context["missing_requested_components"], ["preview"])
        self.assertEqual(component_context["expected_final_complete_value"], second["components"])
        component_example = payload["plan_update_semantics"]["mandatory_components_example"]
        self.assertEqual(component_example["Inválido"], ["preview"])
        self.assertEqual(component_example["Válido"], second["components"])
        self.assertIn(
            "plan_updates não usa operações append, add, patch ou delta",
            payload["plan_update_semantics"]["mandatory_rule"],
        )
        allowlist_semantics = payload["replacement_allowlist_semantics"]
        self.assertIn("allowlist", allowlist_semantics["mandatory_rule"])
        self.assertIn("not a list of mandatory changes", allowlist_semantics["mandatory_rule"])
        subset_example = allowlist_semantics["mandatory_subset_example"]
        self.assertEqual(
            subset_example["allowed_replacements"],
            ["tests/run-tests.js", "backend/server.js"],
        )
        self.assertEqual(
            [item["path"] for item in subset_example["valid_response_fragment"]["replacements"]],
            ["tests/run-tests.js"],
        )
        self.assertEqual(subset_example["must_be_omitted"], ["backend/server.js"])
        test_contract = payload["test_entrypoint_contracts"][0]
        self.assertEqual(test_contract["test_file"], "tests/run-tests.js")
        self.assertEqual(test_contract["backend_entrypoint"], "backend/server.js")
        self.assertIn(
            "Creating http.createServer inside tests/run-tests.js is forbidden.",
            test_contract["forbidden"],
        )
        silent_checks = payload["silent_verification_before_response"]
        self.assertIn(
            "tests/run-tests.js contains an executable reference to backend/server.js.",
            silent_checks,
        )
        self.assertIn("tests/run-tests.js does not contain http.createServer.", silent_checks)
        self.assertIn("tests/run-tests.js makes a real request to /health.", silent_checks)
        self.assertIn(
            "Every returned file has a content hash different from its original hash.",
            silent_checks,
        )
        self.assertIn(
            "components contains the complete final array, not only newly added components.",
            silent_checks,
        )
        messages = project_builder._ollama_messages(
            "BASE OBJECTIVE MUST NOT BE RESENT",
            requester.calls[1][1],
            compact=True,
        )
        serialized_messages = json.dumps(messages)
        self.assertNotIn("BASE OBJECTIVE MUST NOT BE RESENT", serialized_messages)
        self.assertNotIn("project_name", messages[0]["content"])

    async def test_p2_allowed_unchanged_backend_is_omitted_and_real_test_is_accepted(self):
        first = wp1_plan(valid_command=True)
        second = wp1_plan(valid_command=True, real_backend_test=True)
        requester = FakeRequester(first, focal_correction(
            replacements=[replacement(second, "tests/run-tests.js")],
        ))

        plan = await project_builder.get_valid_project_plan(OBJECTIVE, requester)

        payload = json.loads(requester.calls[1][1])
        self.assertEqual(
            set(payload["allowed_replacements"]),
            {"tests/run-tests.js", "backend/server.js"},
        )
        effectiveness = plan.planning_diagnostics["correction_effectiveness"]
        self.assertEqual(effectiveness["replacements_received"], 1)
        self.assertEqual(effectiveness["replacements_applied"], 1)
        self.assertEqual(effectiveness["changed_artifacts"], ["tests/run-tests.js"])
        self.assertEqual(
            next(item.content for item in plan.files if item.path == "backend/server.js"),
            content(first, "backend/server.js"),
        )

    async def test_q_invalid_correction_never_materializes(self):
        first = wp1_plan(real_backend_test=True)
        result = await project_builder.build_project(
            OBJECTIVE,
            plan_requester=FakeRequester(first, focal_correction(
                replacements=[replacement(first, "package.json")],
            )),
            projects_root_rel=TEST_ROOT_REL,
            start_preview=False,
        )

        self.assertEqual(result.error_category, "PLAN_CORRECTION_FAILED")
        self.assertEqual(result.files_created, [])
        self.assertEqual(result.commands_executed, [])
        self.assertFalse(self.root.exists())

    async def test_r_exactly_two_calls_maximum(self):
        first = wp1_plan(real_backend_test=True)
        requester = FakeRequester(first, "invalid-json")

        with self.assertRaises(project_builder.ProjectBuilderPlanningError):
            await project_builder.get_valid_project_plan(OBJECTIVE, requester)

        self.assertEqual(len(requester.calls), 2)


if __name__ == "__main__":
    unittest.main()
