from __future__ import annotations

import copy
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROTO = ROOT / "diagnostics" / "project_builder_typed_patch_prototype" / "20260724-205420"
COMPACT_RUN = ROOT / "diagnostics" / "project_builder_compact_patch_protocol" / "20260724-213037"
os.environ.setdefault("CREWAI_STORAGE_DIR", str(Path(__file__).resolve().parent / "crewai_storage"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from compact_protocol import (  # noqa: E402
    CompactContractError,
    DEFAULT_STORAGE_FILENAME,
    TRANSFORM_IMPLEMENTATION_SHA256,
    apply_response,
    bind_trusted_metadata,
    build_namespace,
    build_schema,
    sha256_text,
    transform_catalog,
    validate_response,
)


PLAN = json.loads((PROTO / "input" / "original_plan.json").read_text(encoding="utf-8"))
ERRORS = json.loads((PROTO / "input" / "initial_errors.json").read_text(encoding="utf-8"))
NAMESPACE = build_namespace(PLAN, ERRORS)
SCHEMA = build_schema(NAMESPACE)
PROMPT = (ROOT / "diagnostics" / "project_builder_plan_quality_audit" / "20260724-193345" / "source" / "ollama_requester_audit" / "wp1_prompt.txt").read_text(encoding="utf-8")


def initial_hash() -> str:
    return sha256_text(next(item["content"] for item in PLAN["files"] if item["path"] == "server.js"))


def operations() -> list[dict]:
    return [
        {"op": "set_components", "value": ["frontend", "backend", "persistence", "tests", "preview"]},
        {"op": "set_component_files", "component": "frontend", "paths": ["index.html"]},
        {"op": "set_component_files", "component": "backend", "paths": ["server.js"]},
        {"op": "set_component_files", "component": "persistence", "paths": ["server.js"]},
        {"op": "set_component_files", "component": "tests", "paths": ["test.js"]},
        {"op": "set_component_files", "component": "preview", "paths": ["index.html"]},
        {"op": "apply_code_transform", "path": "server.js", "transform": "ADD_JSON_FILE_PERSISTENCE"},
    ]


def response(*, ops: list[dict] | None = None) -> dict:
    return {"operations": copy.deepcopy(ops if ops is not None else operations())}


def without_legacy_metadata(value: dict) -> dict:
    result = copy.deepcopy(value)
    result.pop("error_resolutions", None)
    for operation in result.get("operations", []):
        operation.pop("id", None)
        operation.pop("expected_sha256", None)
        operation.pop("parameters", None)
    return result


class CompactProtocolTests(unittest.TestCase):
    def validate(self, value: dict) -> dict:
        return validate_response(value, PLAN, ERRORS, NAMESPACE, SCHEMA)

    def assert_contract(self, value: dict, code: str) -> None:
        with self.assertRaises(CompactContractError) as captured:
            self.validate(value)
        self.assertEqual(captured.exception.code, code)

    def apply(self, value: dict | None = None):
        return apply_response(value or response(), PLAN, ERRORS, NAMESPACE, SCHEMA, PROMPT)

    def test_01_accepts_complete_coverage(self):
        result = self.validate(response())
        self.assertTrue(result["valid"])
        self.assertTrue(result["coverage"]["valid"])

    def test_02_executor_assigns_deterministic_internal_ids(self):
        result = self.validate(response())
        self.assertEqual([item["id"] for item in result["operations"]], [f"op-{index:02d}" for index in range(1, 8)])

    def test_03_rejects_model_supplied_operation_id(self):
        ops = operations()
        ops[0]["id"] = "op-01"
        self.assert_contract(response(ops=ops), "SCHEMA_INVALID")

    def test_04_rejects_model_supplied_error_resolutions(self):
        invalid = response()
        invalid["error_resolutions"] = []
        self.assert_contract(invalid, "SCHEMA_INVALID")

    def test_05_rejects_model_supplied_parameters(self):
        ops = operations()
        ops[-1]["parameters"] = {"storage_filename": DEFAULT_STORAGE_FILENAME}
        self.assert_contract(response(ops=ops), "SCHEMA_INVALID")

    def test_06_rejects_model_supplied_hash(self):
        ops = operations()
        ops[-1]["expected_sha256"] = "0" * 64
        self.assert_contract(response(ops=ops), "SCHEMA_INVALID")

    def test_07_rejects_unknown_operation(self):
        ops = operations()
        ops[0] = {"op": "unknown_operation"}
        self.assert_contract(response(ops=ops), "SCHEMA_INVALID")

    def test_08_rejects_unknown_transform(self):
        ops = operations()
        ops[-1]["transform"] = "UNKNOWN_TRANSFORM"
        self.assert_contract(response(ops=ops), "SCHEMA_INVALID")

    def test_09_rejects_transform_path_outside_namespace(self):
        ops = operations()
        ops[-1]["path"] = "index.html"
        self.assert_contract(response(ops=ops), "SCHEMA_INVALID")

    def test_10_rejects_incompatible_preview_mapping(self):
        ops = operations()
        ops[5]["paths"] = ["package.json"]
        self.assert_contract(response(ops=ops), "INCOMPATIBLE_OPERATION")

    def test_11_derives_coverage_from_operation_semantics(self):
        coverage = self.validate(response())["coverage"]
        self.assertEqual(coverage["missing"], [])
        self.assertIn("op-01", coverage["resolved"]["MISSING_REQUESTED_COMPONENTS"])
        self.assertIn("op-07", coverage["resolved"]["PERSISTENCE_NOT_IMPLEMENTED"])

    def test_12_missing_transform_fails_coverage(self):
        self.assert_contract(response(ops=operations()[:-1]), "MISSING_ERROR_COVERAGE")

    def test_13_incomplete_component_mapping_fails_coverage(self):
        ops = operations()
        del ops[5]
        self.assert_contract(response(ops=ops), "MISSING_ERROR_COVERAGE")

    def test_14_persistence_transform_resolves_persistence_error(self):
        coverage = self.validate(response())["coverage"]
        self.assertEqual(coverage["resolved"]["PERSISTENCE_NOT_IMPLEMENTED"], ["op-04", "op-07"])

    def test_15_executor_adds_deterministic_storage_filename(self):
        result = self.apply()
        self.assertEqual(result.operations_applied[-1]["parameters"], {"storage_filename": DEFAULT_STORAGE_FILENAME})

    def test_16_adds_node_fs(self):
        result = self.apply()
        content = next(item["content"] for item in result.plan["files"] if item["path"] == "server.js")
        self.assertIn("node:fs", content)

    def test_17_adds_durable_read(self):
        result = self.apply()
        content = next(item["content"] for item in result.plan["files"] if item["path"] == "server.js")
        self.assertIn("readFileSync", content)

    def test_18_adds_durable_write(self):
        result = self.apply()
        content = next(item["content"] for item in result.plan["files"] if item["path"] == "server.js")
        self.assertIn("writeFileSync", content)

    def test_19_handles_missing_storage_file(self):
        result = self.apply()
        content = next(item["content"] for item in result.plan["files"] if item["path"] == "server.js")
        self.assertIn("existsSync", content)

    def test_20_preserves_health_route(self):
        result = self.apply()
        content = next(item["content"] for item in result.plan["files"] if item["path"] == "server.js")
        self.assertIn("/health", content)

    def test_21_preserves_test_file(self):
        result = self.apply()
        original = next(item["content"] for item in PLAN["files"] if item["path"] == "test.js")
        final = next(item["content"] for item in result.plan["files"] if item["path"] == "test.js")
        self.assertEqual(original, final)

    def test_22_does_not_create_data_file(self):
        result = self.apply()
        self.assertEqual({item["path"] for item in result.plan["files"]}, {item["path"] for item in PLAN["files"]})

    def test_23_applies_one_virtual_file_change(self):
        result = self.apply()
        self.assertTrue(result.success)
        self.assertEqual([item["path"] for item in result.virtual_diff], ["server.js"])

    def test_24_rolls_back_virtual_plan_on_semantic_failure(self):
        ops = operations()
        ops[-1]["transform"] = "PRESERVE_HEALTH_ROUTE"
        result = self.apply(response(ops=ops))
        self.assertFalse(result.success)
        self.assertTrue(result.rolled_back)
        self.assertIsNone(result.plan)
        self.assertEqual(result.error["code"], "HEALTH_ROUTE_ALREADY_EXISTS_MAPPING_REQUIRED")

    def test_25_real_validators_pass(self):
        result = self.apply()
        self.assertTrue(result.validator_report["valid"], result.validator_report)

    def test_26_incomplete_previous_selection_fails_coverage(self):
        ops = operations()[:-1]
        self.assert_contract(response(ops=ops), "MISSING_ERROR_COVERAGE")

    def test_27_legacy_response_is_not_accepted_without_normalization(self):
        legacy = json.loads((COMPACT_RUN / "K1" / "response.json").read_text(encoding="utf-8"))
        with self.assertRaises(CompactContractError) as captured:
            self.validate(legacy)
        self.assertEqual(captured.exception.code, "SCHEMA_INVALID")

    def test_28_schema_has_no_free_content_or_trusted_metadata_fields(self):
        encoded = json.dumps(SCHEMA)
        for field in ("content", "old_text", "new_text", "id", "error_resolutions", "parameters", "storage_filename", "expected_sha256"):
            self.assertNotIn(f'"{field}"', encoded)

    def test_29_transform_catalog_is_hashed_and_closed(self):
        catalog = transform_catalog(NAMESPACE)
        self.assertEqual(catalog["ADD_JSON_FILE_PERSISTENCE"]["implementation_sha256"], TRANSFORM_IMPLEMENTATION_SHA256)
        self.assertEqual(set(catalog), {"ADD_JSON_FILE_PERSISTENCE", "PRESERVE_HEALTH_ROUTE", "EXPORT_SERVER_FOR_TESTS", "PRESERVE_HTTP_IMPORT"})

    def test_30_output_is_deterministic(self):
        first = self.apply()
        second = self.apply()
        self.assertEqual(first.plan, second.plan)
        self.assertEqual(first.virtual_diff, second.virtual_diff)
        self.assertEqual(first.transform_report, second.transform_report)

    def test_31_binds_real_hash_from_initial_snapshot(self):
        model_response = response()
        bound, bindings = bind_trusted_metadata(model_response, PLAN, NAMESPACE)
        self.assertNotIn("_trusted_expected_sha256", model_response["operations"][-1])
        self.assertEqual(bound["operations"][-1]["_trusted_expected_sha256"], initial_hash())
        self.assertEqual(bindings[0]["expected_sha256"], initial_hash())
        self.assertEqual(bindings[0]["source"], "initial_virtual_snapshot")

    def test_32_snapshot_change_is_rejected(self):
        current = copy.deepcopy(PLAN)
        server = next(item for item in current["files"] if item["path"] == "server.js")
        server["content"] += "\n// concurrent mutation\n"
        result = apply_response(response(), PLAN, ERRORS, NAMESPACE, SCHEMA, PROMPT, current_plan=current)
        self.assertFalse(result.success)
        self.assertEqual(result.error["code"], "SNAPSHOT_CHANGED")
        self.assertTrue(result.rolled_back)

    def test_33_model_cannot_disable_integrity_binding(self):
        ops = operations()
        ops[-1]["expected_sha256"] = initial_hash()
        self.assert_contract(response(ops=ops), "SCHEMA_INVALID")

    def test_34_wrong_transform_fails_before_apply(self):
        ops = operations()
        ops[-1]["transform"] = "PRESERVE_HEALTH_ROUTE"
        result = self.apply(response(ops=ops))
        self.assertFalse(result.success)
        self.assertEqual(result.error["code"], "HEALTH_ROUTE_ALREADY_EXISTS_MAPPING_REQUIRED")

    def test_35_previous_k1_advances_past_hash_validation(self):
        previous = json.loads((COMPACT_RUN / "K1" / "response.json").read_text(encoding="utf-8"))
        normalized = without_legacy_metadata(previous)
        try:
            self.validate(normalized)
        except CompactContractError as exc:
            self.assertNotEqual(exc.code, "HASH_MISMATCH")
        else:
            self.fail("K1 unexpectedly passed without its missing operations being changed")

    def test_36_previous_k1_to_k4_are_not_silently_repaired(self):
        for case in ("K1", "K2", "K3", "K4"):
            previous = json.loads((COMPACT_RUN / case / "response.json").read_text(encoding="utf-8"))
            normalized = without_legacy_metadata(previous)
            with self.assertRaises(CompactContractError):
                self.validate(normalized)

    def test_37_model_response_is_not_mutated_by_binding(self):
        model_response = response()
        original = copy.deepcopy(model_response)
        bind_trusted_metadata(model_response, PLAN, NAMESPACE)
        self.assertEqual(model_response, original)

    def test_38_no_physical_file_is_written(self):
        before = {item["path"]: item["content"] for item in PLAN["files"]}
        self.apply()
        after = {item["path"]: item["content"] for item in PLAN["files"]}
        self.assertEqual(before, after)

    def test_39_schema_has_exact_public_shape(self):
        self.assertEqual(SCHEMA["required"], ["operations"])
        self.assertEqual(set(SCHEMA["properties"]), {"operations"})
        self.assertTrue(SCHEMA["additionalProperties"] is False)


if __name__ == "__main__":
    unittest.main()
