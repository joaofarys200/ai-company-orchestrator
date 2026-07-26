import copy
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
os.environ.setdefault("CREWAI_STORAGE_DIR", str(Path(__file__).resolve().parent / "crewai_storage"))

from typed_patch_prototype import (
    ContractError,
    apply_operations,
    build_namespace,
    build_typed_prompt,
    derive_scope,
    run_real_validators,
    sha256_text,
    validate_operations,
)
import typed_patch_prototype


ROOT = Path(__file__).resolve().parents[3]
AUDIT = ROOT / "diagnostics" / "project_builder_plan_quality_audit" / "20260724-193345"
JOURNAL = json.loads((AUDIT / "source" / "project_build_journal.json").read_text(encoding="utf-8"))
INITIAL_PLAN = json.loads(JOURNAL["planning_validation_history"][0]["response"])
INITIAL_ERRORS = JOURNAL["planning_validation_history"][0]["errors"]
SCHEMA = json.loads((Path(__file__).parent / "operations.schema.json").read_text(encoding="utf-8"))
NAMESPACE = build_namespace(INITIAL_PLAN, INITIAL_ERRORS)
PROMPT = (AUDIT / "source" / "ollama_requester_audit" / "wp1_prompt.txt").read_text(encoding="utf-8")


def manual_operations(plan=INITIAL_PLAN):
    server = next(item for item in plan["files"] if item["path"] == "server.js")
    ideal = json.loads((AUDIT / "offline" / "ideal_minimal_correction.json").read_text(encoding="utf-8"))
    return [
        {"op": "set_components", "value": ["frontend", "backend", "persistence", "tests", "preview"]},
        {"op": "set_component_files", "component": "frontend", "paths": ["index.html"]},
        {"op": "set_component_files", "component": "backend", "paths": ["server.js"]},
        {"op": "set_component_files", "component": "persistence", "paths": ["server.js"]},
        {"op": "set_component_files", "component": "tests", "paths": ["test.js"]},
        {"op": "set_component_files", "component": "preview", "paths": ["index.html"]},
        {"op": "set_preview_strategy", "field": "healthcheck_path", "value": "/health"},
        {
            "op": "replace_file_content",
            "path": "server.js",
            "expected_sha256": sha256_text(server["content"]),
            "content": ideal["replacements"][0]["content"],
        },
    ]


class TypedPatchPrototypeTests(unittest.TestCase):
    def assert_code(self, operation, code):
        with self.assertRaises(ContractError) as captured:
            validate_operations([operation], INITIAL_PLAN, NAMESPACE, SCHEMA)
        self.assertEqual(captured.exception.code, code)

    def test_01_accepts_valid_set_components(self):
        operation = {"op": "set_components", "value": ["frontend", "backend", "persistence", "tests", "preview"]}
        self.assertEqual(validate_operations([operation], INITIAL_PLAN, NAMESPACE, SCHEMA), [operation])

    def test_02_rejects_unknown_component(self):
        self.assert_code({"op": "set_components", "value": ["unknown"]}, "INVALID_COMPONENT")

    def test_03_accepts_mapping_to_existing_path(self):
        operation = {"op": "set_component_files", "component": "backend", "paths": ["server.js"]}
        self.assertEqual(validate_operations([operation], INITIAL_PLAN, NAMESPACE, SCHEMA), [operation])

    def test_04_rejects_nonexistent_path(self):
        self.assert_code({"op": "set_component_files", "component": "backend", "paths": ["routes/health.js"]}, "PATH_NOT_IN_NAMESPACE")

    def test_05_accepts_server_replacement(self):
        operation = manual_operations()[-1]
        self.assertEqual(validate_operations([operation], INITIAL_PLAN, NAMESPACE, SCHEMA), [operation])

    def test_06_rejects_replacement_target_outside_scope(self):
        operation = manual_operations()[-1] | {"path": "package.json"}
        self.assert_code(operation, "TARGET_NOT_REPLACEABLE")

    def test_07_rejects_wrong_hash(self):
        operation = manual_operations()[-1] | {"expected_sha256": "0" * 64}
        self.assert_code(operation, "HASH_MISMATCH")

    def test_08_rejects_duplicate_operation(self):
        operation = manual_operations()[0]
        self.assert_code({"op": "set_components", "value": operation["value"]} | {"extra": True}, "SCHEMA_INVALID")
        with self.assertRaises(ContractError) as captured:
            validate_operations([operation, operation], INITIAL_PLAN, NAMESPACE, SCHEMA)
        self.assertEqual(captured.exception.code, "DUPLICATE_OPERATION")

    def test_09_rejects_conflicting_operation(self):
        operations = [
            {"op": "set_component_files", "component": "backend", "paths": ["server.js"]},
            {"op": "set_component_files", "component": "backend", "paths": ["package.json"]},
        ]
        with self.assertRaises(ContractError) as captured:
            validate_operations(operations, INITIAL_PLAN, NAMESPACE, SCHEMA)
        self.assertEqual(captured.exception.code, "CONFLICTING_OPERATION")

    def test_10_applies_in_deterministic_order(self):
        operations = list(reversed(manual_operations()))
        result = apply_operations(INITIAL_PLAN, operations, NAMESPACE, SCHEMA)
        self.assertEqual(result.plan["components"][-1], "preview")
        self.assertEqual(result.plan["component_files"]["persistence"], ["server.js"])
        self.assertTrue(result.plan["files"][1]["content"].count("node:fs"))
        self.assertEqual([item["op"] for item in result.applied_operations[:2]], ["set_components", "set_component_files"])

    def test_11_does_not_create_files(self):
        result = apply_operations(INITIAL_PLAN, manual_operations(), NAMESPACE, SCHEMA)
        self.assertEqual({item["path"] for item in result.plan["files"]}, {item["path"] for item in INITIAL_PLAN["files"]})

    def test_12_does_not_change_unreferenced_files(self):
        result = apply_operations(INITIAL_PLAN, manual_operations(), NAMESPACE, SCHEMA)
        before = {item["path"]: item["content"] for item in INITIAL_PLAN["files"]}
        after = {item["path"]: item["content"] for item in result.plan["files"]}
        for path in {"package.json", "index.html", "test.js"}:
            self.assertEqual(after[path], before[path])

    def test_13_failed_operation_preserves_original(self):
        original = copy.deepcopy(INITIAL_PLAN)
        with self.assertRaises(ContractError):
            apply_operations(INITIAL_PLAN, manual_operations() + [{"op": "set_component_files", "component": "backend", "paths": ["routes/health.js"]}], NAMESPACE, SCHEMA)
        self.assertEqual(INITIAL_PLAN, original)

    def test_14_manual_ideal_passes_real_validators(self):
        result = apply_operations(INITIAL_PLAN, manual_operations(), NAMESPACE, SCHEMA)
        validation = run_real_validators(result.plan, PROMPT)
        self.assertTrue(validation["valid"], validation)

    def test_15_mapping_without_content_does_not_fix_persistence(self):
        operations = [
            {"op": "set_components", "value": ["frontend", "backend", "persistence", "tests", "preview"]},
            {"op": "set_component_files", "component": "frontend", "paths": ["index.html"]},
            {"op": "set_component_files", "component": "backend", "paths": ["server.js"]},
            {"op": "set_component_files", "component": "persistence", "paths": ["server.js"]},
            {"op": "set_component_files", "component": "tests", "paths": ["test.js"]},
            {"op": "set_component_files", "component": "preview", "paths": ["index.html"]},
            {"op": "set_preview_strategy", "field": "healthcheck_path", "value": "/health"},
        ]
        result = apply_operations(INITIAL_PLAN, operations, NAMESPACE, SCHEMA)
        validation = run_real_validators(result.plan, PROMPT)
        self.assertIn("PERSISTENCE_NOT_IMPLEMENTED", validation["error_codes"])

    def test_16_scope_exposes_incomplete_mapping(self):
        scope = derive_scope(INITIAL_PLAN, INITIAL_ERRORS, NAMESPACE)
        self.assertIn("component_files", scope["authorized_fields"])
        self.assertIn("set_component_files", scope["authorized_operations"])

    def test_17_routes_health_path_is_not_authorized(self):
        self.assert_code({"op": "set_component_files", "component": "backend", "paths": ["routes/health.js"]}, "PATH_NOT_IN_NAMESPACE")

    def test_18_database_path_is_not_authorized(self):
        self.assert_code({"op": "set_component_files", "component": "persistence", "paths": ["db/storage.json"]}, "PATH_NOT_IN_NAMESPACE")

    def test_19_src_html_path_is_not_authorized(self):
        self.assert_code({"op": "set_component_files", "component": "frontend", "paths": ["src/index.html"]}, "PATH_NOT_IN_NAMESPACE")

    def test_20_package_json_is_not_persistence_replacement_target(self):
        operation = manual_operations()[-1] | {"path": "package.json"}
        self.assert_code(operation, "TARGET_NOT_REPLACEABLE")

    def test_21_scope_uses_actionable_health_evidence(self):
        scope = derive_scope(INITIAL_PLAN, INITIAL_ERRORS, NAMESPACE)
        health = next(item for item in scope["errors"] if item["error_code"] == "MISSING_HEALTH_ROUTE")
        self.assertEqual(health["evidence"]["route_files"], ["server.js"])
        self.assertIn("already exists", health["reason"])

    def test_22_no_model_or_repair_is_part_of_applicator(self):
        source = Path(typed_patch_prototype.__file__).read_text(encoding="utf-8")
        self.assertNotIn("ollama", source.lower())
        self.assertNotIn("create_file", source)

    def test_23_prompt_contains_current_hashes_and_closed_paths(self):
        prompt = build_typed_prompt(INITIAL_PLAN, derive_scope(INITIAL_PLAN, INITIAL_ERRORS, NAMESPACE), NAMESPACE, SCHEMA)
        self.assertIn("CURRENT FILE SHA256 VALUES", prompt)
        self.assertIn(sha256_text(next(item for item in INITIAL_PLAN["files"] if item["path"] == "server.js")["content"]), prompt)
        for path in ("package.json", "server.js", "index.html", "test.js"):
            self.assertIn(path, prompt)


if __name__ == "__main__":
    unittest.main()
