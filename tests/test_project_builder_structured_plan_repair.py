import json
import os
import shutil
import unittest
from pathlib import Path

from agents import tools as ag_tools
from agents.orchestrator import project_builder


TEST_ROOT_REL = f"workspace/projects/_structured_plan_{os.getpid()}"


class FakeRequester:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    async def __call__(self, prompt, correction=None):
        self.calls.append((prompt, correction))
        return self.responses.pop(0)


def minimal_plan(**overrides):
    plan = {
        "project_name": "Structured plan",
        "stack": "Node.js",
        "components": [],
        "dependencies": [],
        "files": [{"path": "app.js", "content": "console.log('ok');\n"}],
        "component_files": {},
        "setup_commands": [],
        "validation_commands": ["node --check app.js"],
        "entrypoints": ["app.js"],
        "preview_strategy": {},
        "preview_command": "",
        "constraints": [],
        "rationale": "Validate syntax.",
    }
    plan.update(overrides)
    return plan


def conflicting_plan():
    return minimal_plan(files=[
        {"path": "data.json", "content": "[]\n"},
        {"path": "data.json", "content": "{}\n"},
        {"path": "app.js", "content": "console.log('ok');\n"},
    ])


def correction_response(plan, error_code="DUPLICATE_FILE_PATH_CONFLICT"):
    return {
        "corrected_plan": plan,
        "correction_manifest": [{
            "error_code": error_code,
            "changed_artifacts": [],
            "resolution": "Returned a complete plan satisfying the reported schema error.",
        }],
    }


class ProjectBuilderStructuredPlanRepairTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.root = Path(ag_tools.resolve_workspace_path(TEST_ROOT_REL))
        shutil.rmtree(self.root, ignore_errors=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    async def test_a_entrypoints_string_is_repaired_without_second_call(self):
        requester = FakeRequester(minimal_plan(entrypoints="app.js"))

        plan = await project_builder.get_valid_project_plan("Cria app.js", requester)

        self.assertEqual(plan.entrypoints, ["app.js"])
        self.assertEqual(len(requester.calls), 1)
        self.assertTrue(plan.planning_diagnostics["locally_repaired"])
        self.assertIn(
            "SCALAR_TO_ARRAY",
            {item["code"] for item in plan.planning_diagnostics["local_repairs"]},
        )

    async def test_b_identical_duplicate_file_is_removed_locally(self):
        plan_data = minimal_plan(files=[
            {"path": ".\\app.js", "content": "console.log('ok');\n"},
            {"path": "app.js", "content": "console.log('ok');\n"},
        ])
        requester = FakeRequester(plan_data)

        plan = await project_builder.get_valid_project_plan("Cria app.js", requester)

        self.assertEqual([item.path for item in plan.files], ["app.js"])
        self.assertEqual(len(requester.calls), 1)
        repair_codes = {item["code"] for item in plan.planning_diagnostics["local_repairs"]}
        self.assertIn("REMOVE_IDENTICAL_DUPLICATE_FILE", repair_codes)

    async def test_c_conflicting_duplicate_requires_second_attempt(self):
        requester = FakeRequester(conflicting_plan(), correction_response(minimal_plan()))

        plan = await project_builder.get_valid_project_plan("Cria app.js", requester)

        self.assertEqual(len(requester.calls), 2)
        self.assertTrue(plan.planning_diagnostics["corrected_by_model"])
        correction = json.loads(requester.calls[1][1])
        self.assertEqual(correction["errors"][0]["code"], "DUPLICATE_FILE_PATH_CONFLICT")

    async def test_d_second_prompt_contains_exact_structured_feedback(self):
        requester = FakeRequester(conflicting_plan(), correction_response(minimal_plan()))
        await project_builder.get_valid_project_plan("Cria app.js", requester)

        messages = project_builder._ollama_messages(
            requester.calls[1][0], requester.calls[1][1], compact=True
        )
        second_prompt = messages[1]["content"]

        for required_key in ("code", "field_path", "expected_type", "suggestion"):
            self.assertIn(f'"{required_key}"', second_prompt)
        self.assertIn("DUPLICATE_FILE_PATH_CONFLICT", second_prompt)
        self.assertIn("entrypoints must be an array of strings", second_prompt)

    async def test_e_valid_second_response_passes_and_has_final_hash(self):
        requester = FakeRequester(
            minimal_plan(entrypoints={"path": "app.js"}),
            correction_response(minimal_plan(), "INVALID_FIELD_TYPE"),
        )

        plan = await project_builder.get_valid_project_plan("Cria app.js", requester)

        self.assertEqual(len(requester.calls), 2)
        self.assertEqual(plan.entrypoints, ["app.js"])
        self.assertEqual(len(plan.planning_diagnostics["final_plan_hash"]), 64)

    async def test_f_invalid_second_response_stops_after_two_calls(self):
        requester = FakeRequester(conflicting_plan(), correction_response(conflicting_plan()))

        with self.assertRaises(project_builder.ProjectBuilderError) as ctx:
            await project_builder.get_valid_project_plan("Cria app.js", requester)

        self.assertEqual(len(requester.calls), 2)
        self.assertIn("DUPLICATE_FILE_PATH_CONFLICT", requester.calls[1][1])
        self.assertIn("conteudo diferente", str(ctx.exception))

    async def test_g_constraints_remain_in_second_prompt(self):
        requester = FakeRequester(conflicting_plan(), correction_response(minimal_plan()))
        await project_builder.get_valid_project_plan(
            "Cria uma app. Nao uses Obsidian.", requester
        )

        messages = project_builder._ollama_messages(
            requester.calls[1][0], requester.calls[1][1], compact=True
        )
        second_prompt = messages[1]["content"]
        self.assertIn("Nao uses Obsidian", second_prompt)
        self.assertIn('"excluded_targets":["Obsidian"]'.replace(" ", ""), second_prompt.replace(" ", ""))

    def test_h_repairer_does_not_invent_files(self):
        repaired, repairs = project_builder.repair_project_plan_mechanically({
            "project_name": "No files",
            "stack": "text",
            "entrypoints": "main.txt",
        })

        self.assertNotIn("files", repaired)
        self.assertNotIn("REMOVE_IDENTICAL_DUPLICATE_FILE", {item["code"] for item in repairs})

    def test_i_repairer_does_not_choose_between_conflicting_duplicates(self):
        repaired, repairs = project_builder.repair_project_plan_mechanically(conflicting_plan())

        data_files = [item for item in repaired["files"] if item["path"] == "data.json"]
        self.assertEqual(len(data_files), 2)
        self.assertNotIn("REMOVE_IDENTICAL_DUPLICATE_FILE", {item["code"] for item in repairs})
        errors = project_builder._schema_errors(repaired)
        self.assertIn("DUPLICATE_FILE_PATH_CONFLICT", {item.code for item in errors})

    def test_j_prompt_schema_is_generated_from_validator_definition(self):
        expected = json.dumps(
            project_builder.project_plan_schema_document(),
            ensure_ascii=False,
            separators=(",", ":"),
        )

        self.assertEqual(project_builder.project_plan_schema_prompt(), expected)
        messages = project_builder._ollama_messages("Cria app.js", "{}", compact=True)
        self.assertIn(expected, messages[1]["content"])
        invalid, _ = project_builder.repair_project_plan_mechanically(
            minimal_plan(entrypoints={"path": "app.js"})
        )
        error = next(
            item for item in project_builder._schema_errors(invalid)
            if item.field_path == "entrypoints"
        )
        self.assertEqual(
            error.expected_type,
            project_builder.project_plan_schema_document()["properties"]["entrypoints"]["type"],
        )

    def test_k_semantic_error_is_not_classified_as_schema(self):
        plan_data = minimal_plan(
            components=["backend"],
            component_files={"backend": ["app.js"]},
        )

        with self.assertRaises(project_builder._PlanValidationFailure) as ctx:
            project_builder._validated_raw_project_plan(
                plan_data,
                "Cria uma app full stack com frontend e backend",
            )

        self.assertEqual(ctx.exception.category, "PLAN_SEMANTIC_INVALID")
        self.assertEqual(ctx.exception.parse_status, "PARSED")
        self.assertEqual(ctx.exception.errors[0].code, "MISSING_REQUESTED_COMPONENTS")

    async def test_l_no_files_are_written_before_final_valid_plan(self):
        requester = FakeRequester(conflicting_plan(), correction_response(conflicting_plan()))

        with self.assertRaises(project_builder.ProjectBuilderError):
            await project_builder.build_project(
                "Cria app.js",
                plan_requester=requester,
                projects_root_rel=TEST_ROOT_REL,
                start_preview=False,
            )

        self.assertEqual(len(requester.calls), 2)
        self.assertFalse(self.root.exists())


if __name__ == "__main__":
    unittest.main()
