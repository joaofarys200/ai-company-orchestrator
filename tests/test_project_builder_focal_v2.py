import json
import os
import shutil
import unittest
from copy import deepcopy
from pathlib import Path
from unittest import mock

from agents import tools as ag_tools
from agents.orchestrator import project_builder
from tests.test_project_builder_correction_effectiveness import (
    FakeRequester,
    OBJECTIVE,
    content,
    focal_correction,
    replacement,
    wp1_plan,
)


TEST_ROOT_REL = f"workspace/projects/_focal_v2_{os.getpid()}"


class ProjectBuilderFocalV2Test(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.root = Path(ag_tools.resolve_workspace_path(TEST_ROOT_REL))
        shutil.rmtree(self.root, ignore_errors=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    async def test_04_empty_response_fails_with_no_effect(self):
        first = wp1_plan(real_backend_test=True)
        requester = FakeRequester(first, focal_correction())

        with self.assertRaises(project_builder.ProjectBuilderPlanningError) as captured:
            await project_builder.get_valid_project_plan(OBJECTIVE, requester)

        diagnostics = captured.exception.diagnostics
        codes = {item["code"] for item in diagnostics["final_validation"]["errors"]}
        self.assertIn("CORRECTION_NO_EFFECT", codes)
        self.assertEqual(diagnostics["derived_changed_plan_fields"], [])
        self.assertEqual(diagnostics["derived_changed_files"], [])
        self.assertEqual(
            diagnostics["error_resolution_statuses"],
            {"COMMAND_TARGET_INVALID": "NOT_EVALUATED"},
        )

    async def test_05_components_change_is_derived(self):
        first = wp1_plan(valid_command=True, real_backend_test=True, include_preview=False)
        requester = FakeRequester(first, focal_correction(plan_updates={
            "components": ["frontend", "backend", "persistence", "tests", "preview"],
        }))

        plan = await project_builder.get_valid_project_plan(OBJECTIVE, requester)
        effectiveness = plan.planning_diagnostics["correction_effectiveness"]

        self.assertEqual(effectiveness["derived_changed_plan_fields"], ["components"])
        self.assertEqual(effectiveness["derived_changed_files"], [])
        entry = effectiveness["correction_manifest"][0]
        self.assertEqual(entry["changed_artifacts"], ["components"])
        self.assertEqual(entry["resolution_status"], "RESOLVED")
        self.assertEqual(
            entry["evidence"]["plan_fields"]["components"]["before"],
            ["frontend", "backend", "persistence", "tests"],
        )

    async def test_06_real_replacement_derives_changed_file(self):
        first = wp1_plan(real_backend_test=True)
        fixed = wp1_plan(valid_command=True, real_backend_test=True)
        requester = FakeRequester(first, focal_correction(
            replacements=[replacement(fixed, "package.json")],
        ))

        plan = await project_builder.get_valid_project_plan(OBJECTIVE, requester)
        effectiveness = plan.planning_diagnostics["correction_effectiveness"]

        self.assertEqual(effectiveness["derived_changed_files"], ["package.json"])
        self.assertEqual(effectiveness["unchanged_replacements"], [])

    async def test_07_identical_replacement_is_rejected_and_recorded(self):
        first = wp1_plan(real_backend_test=True)
        requester = FakeRequester(first, focal_correction(
            replacements=[replacement(first, "package.json")],
        ))

        with self.assertRaises(project_builder.ProjectBuilderPlanningError) as captured:
            await project_builder.get_valid_project_plan(OBJECTIVE, requester)

        diagnostics = captured.exception.diagnostics
        self.assertEqual(diagnostics["unchanged_replacements"], ["package.json"])
        self.assertIn(
            "CORRECTION_DECLARED_FILE_UNCHANGED",
            {item["code"] for item in diagnostics["final_validation"]["errors"]},
        )

    async def test_08_internal_manifest_uses_real_hashes_only(self):
        first = wp1_plan(real_backend_test=True)
        fixed = wp1_plan(valid_command=True, real_backend_test=True)
        requester = FakeRequester(first, focal_correction(
            replacements=[replacement(fixed, "package.json")],
        ))

        plan = await project_builder.get_valid_project_plan(OBJECTIVE, requester)
        effectiveness = plan.planning_diagnostics["correction_effectiveness"]
        entry = next(
            item for item in effectiveness["correction_manifest"]
            if item["error_code"] == "COMMAND_TARGET_INVALID"
        )
        hashes = entry["evidence"]["file_hashes"]["package.json"]

        self.assertEqual(hashes["hash_before"], effectiveness["hashes_before"]["package.json"])
        self.assertEqual(hashes["hash_after"], effectiveness["hashes_after"]["package.json"])
        self.assertNotEqual(hashes["hash_before"], hashes["hash_after"])
        self.assertNotIn("resolution", entry)
        self.assertFalse(effectiveness["model_manifest_accepted"])

    async def test_09_manifest_never_declares_unchanged_file(self):
        first = wp1_plan()
        fixed = wp1_plan(valid_command=True)
        requester = FakeRequester(first, focal_correction(
            replacements=[replacement(fixed, "package.json")],
        ))

        with self.assertRaises(project_builder.ProjectBuilderPlanningError) as captured:
            await project_builder.get_valid_project_plan(OBJECTIVE, requester)

        manifest = captured.exception.diagnostics["correction_manifest"]
        declared = {
            artifact
            for entry in manifest
            for artifact in entry["changed_artifacts"]
        }
        self.assertEqual(declared, {"package.json"})
        self.assertNotIn("tests/run-tests.js", declared)
        self.assertNotIn("backend/server.js", declared)

    async def test_10_resolved_error_status_is_derived(self):
        first = wp1_plan(real_backend_test=True)
        fixed = wp1_plan(valid_command=True, real_backend_test=True)
        requester = FakeRequester(first, focal_correction(
            replacements=[replacement(fixed, "package.json")],
        ))

        plan = await project_builder.get_valid_project_plan(OBJECTIVE, requester)

        self.assertEqual(
            plan.planning_diagnostics["error_resolution_statuses"],
            {"COMMAND_TARGET_INVALID": "RESOLVED"},
        )

    async def test_11_partial_correction_derives_resolved_and_unresolved(self):
        first = wp1_plan()
        fixed = wp1_plan(valid_command=True)
        requester = FakeRequester(first, focal_correction(
            replacements=[replacement(fixed, "package.json")],
        ))

        with self.assertRaises(project_builder.ProjectBuilderPlanningError) as captured:
            await project_builder.get_valid_project_plan(OBJECTIVE, requester)

        self.assertEqual(captured.exception.diagnostics["error_resolution_statuses"], {
            "COMMAND_TARGET_INVALID": "RESOLVED",
            "TEST_DOES_NOT_EXERCISE_ENTRYPOINT": "UNRESOLVED",
        })
        self.assertTrue(captured.exception.diagnostics["correction_revalidation_executed"])

    async def test_12_pre_revalidation_failure_is_not_evaluated(self):
        first = wp1_plan(real_backend_test=True)
        correction = focal_correction(replacements=[{
            "path": "frontend/index.html",
            "content": "<!doctype html><main>changed</main>\n",
        }])
        requester = FakeRequester(first, correction)

        with self.assertRaises(project_builder.ProjectBuilderPlanningError) as captured:
            await project_builder.get_valid_project_plan(OBJECTIVE, requester)

        self.assertEqual(
            captured.exception.diagnostics["error_resolution_statuses"],
            {"COMMAND_TARGET_INVALID": "NOT_EVALUATED"},
        )
        self.assertFalse(captured.exception.diagnostics["correction_revalidation_executed"])

    async def test_13_partial_correction_does_not_materialize(self):
        first = wp1_plan()
        fixed = wp1_plan(valid_command=True)

        result = await project_builder.build_project(
            OBJECTIVE,
            plan_requester=FakeRequester(first, focal_correction(
                replacements=[replacement(fixed, "package.json")],
            )),
            projects_root_rel=TEST_ROOT_REL,
            start_preview=False,
        )

        self.assertEqual(result.files_created, [])
        self.assertEqual(result.commands_executed, [])
        self.assertFalse(self.root.exists())

    async def test_14_integral_correction_materializes(self):
        first = wp1_plan(include_preview=False)
        fixed = wp1_plan(valid_command=True, real_backend_test=True, include_preview=True)

        async def confirm_materialized(*args, **kwargs):
            project_dir = self.root / "correction-effectiveness"
            self.assertTrue((project_dir / "package.json").is_file())
            self.assertTrue((project_dir / "tests" / "run-tests.js").is_file())
            return [], [], False, ""

        with mock.patch.object(
            project_builder,
            "_execute_validation_plan",
            side_effect=confirm_materialized,
        ):
            result = await project_builder.build_project(
                OBJECTIVE,
                plan_requester=FakeRequester(first, focal_correction(
                    plan_updates={"components": fixed["components"]},
                    replacements=[
                        replacement(fixed, "package.json"),
                        replacement(fixed, "tests/run-tests.js"),
                    ],
                )),
                projects_root_rel=TEST_ROOT_REL,
                start_preview=False,
            )

        self.assertTrue(result.files_created)
        self.assertTrue((self.root / "correction-effectiveness" / "package.json").is_file())
        self.assertNotEqual(result.error_category, "PLAN_CORRECTION_FAILED")
        diagnostics = result.planning_diagnostics
        self.assertEqual(set(diagnostics["derived_changed_files"]), {
            "package.json", "tests/run-tests.js",
        })

    def test_16_invalid_response_is_not_repaired_automatically(self):
        response = {
            "plan_updates": {},
            "replacements": [],
            "correction_manifest": [],
        }
        original = deepcopy(response)

        plan_updates, replacements, errors = project_builder._strict_focal_correction_envelope(
            response
        )

        self.assertEqual(response, original)
        self.assertEqual(plan_updates, {})
        self.assertEqual(replacements, [])
        self.assertIn("CORRECTION_RESPONSE_SCHEMA_INVALID", {item.code for item in errors})
        self.assertTrue(all(not item.repairable for item in errors))

    def test_17_legacy_journal_with_model_manifest_remains_readable(self):
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / "legacy-journal.json"
        old_manifest = [{
            "error_code": "COMMAND_TARGET_INVALID",
            "changed_artifacts": ["package.json"],
            "resolution": "Legacy model-provided claim.",
        }]
        state = {
            "run_id": "legacy-focal-v1",
            "status": "VALIDATION_FAILED",
            "planning_diagnostics": {
                "focal_correction_protocol": "project_builder_focal_correction_v1",
                "correction_manifest": old_manifest,
            },
        }
        path.write_text(json.dumps(state), encoding="utf-8")

        journal = project_builder.ProjectBuildJournal.from_path(path)
        loaded = journal.snapshot()

        self.assertEqual(loaded["run_id"], "legacy-focal-v1")
        self.assertEqual(loaded["planning_diagnostics"]["correction_manifest"], old_manifest)


if __name__ == "__main__":
    unittest.main()
