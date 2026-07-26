from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[3]
PROTO = ROOT / "diagnostics" / "project_builder_typed_patch_prototype" / "20260724-205420"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(PROTO))

from typed_patch_prototype import ContractError, validate_operations  # noqa: E402


def coverage_schema(operation_schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["resolved_error_codes", "operations"],
        "properties": {
            "resolved_error_codes": {
                "type": "array",
                "minItems": 1,
                "uniqueItems": True,
                "items": {"type": "string", "minLength": 1},
            },
            "operations": operation_schema,
        },
    }


def _compatibility(code: str, operation: dict[str, Any]) -> bool:
    op = operation.get("op")
    if code == "MISSING_REQUESTED_COMPONENTS":
        return op == "set_components"
    if code in {"MISSING_COMPONENT_MAPPING", "DECLARED_COMPONENT_WITHOUT_ARTIFACTS", "MAPPED_FILE_NOT_FOUND"}:
        return op == "set_component_files"
    if code == "MISSING_HEALTH_ROUTE":
        return op in {"set_component_files", "set_preview_strategy"}
    if code == "PERSISTENCE_NOT_IMPLEMENTED":
        return op in {"replace_file_content", "replace_text"} and operation.get("path") == "server.js"
    return False


def validate_coverage_response(
    response: dict[str, Any],
    plan: dict[str, Any],
    errors: list[dict[str, Any]],
    namespace,
    operation_schema: dict[str, Any],
) -> dict[str, Any]:
    schema = coverage_schema(operation_schema)
    schema_errors = list(Draft202012Validator(schema).iter_errors(response))
    if schema_errors:
        raise ContractError(
            "COVERAGE_SCHEMA_INVALID",
            "Coverage response failed its schema",
            errors=[error.message for error in schema_errors],
        )
    normalized = validate_operations(response["operations"], plan, namespace, operation_schema)
    required = sorted({item["code"] for item in errors})
    claimed = sorted(response["resolved_error_codes"])
    if claimed != required:
        raise ContractError(
            "ERROR_CODES_NOT_COVERED",
            "resolved_error_codes does not exactly cover the initial validator errors",
            required=required,
            claimed=claimed,
        )
    missing: list[str] = []
    for code in required:
        if not any(_compatibility(code, operation) for operation in normalized):
            missing.append(code)
    if missing:
        if "PERSISTENCE_NOT_IMPLEMENTED" in missing:
            raise ContractError(
                "PERSISTENCE_OPERATION_REQUIRED",
                "PERSISTENCE_NOT_IMPLEMENTED requires a server.js content operation before validators run",
                missing=missing,
            )
        raise ContractError(
            "ERROR_OPERATION_NOT_COVERED",
            "At least one compatible operation is required for every resolved error",
            missing=missing,
        )
    return {"valid": True, "resolved_error_codes": claimed, "normalized_operations": normalized}


def main() -> int:
    root = Path(__file__).resolve().parent
    plan = json.loads((PROTO / "input" / "original_plan.json").read_text(encoding="utf-8"))
    errors = json.loads((PROTO / "input" / "initial_errors.json").read_text(encoding="utf-8"))
    schema = json.loads((PROTO / "operations.schema.json").read_text(encoding="utf-8"))
    manual_operations = json.loads((PROTO / "manual_operations.json").read_text(encoding="utf-8"))
    c1_operations = json.loads((PROTO / "model_operations.json").read_text(encoding="utf-8"))
    namespace_module = __import__("typed_patch_prototype")
    namespace = namespace_module.build_namespace(plan, errors)
    codes = sorted({item["code"] for item in errors})
    c1 = {"resolved_error_codes": codes, "operations": c1_operations}
    manual = {"resolved_error_codes": codes, "operations": manual_operations}
    report: dict[str, Any] = {
        "schema": coverage_schema(schema),
        "required_error_codes": codes,
        "c1": {"accepted": False},
        "manual": {"accepted": False},
        "prevalidator_block": False,
    }
    try:
        validate_coverage_response(c1, plan, errors, namespace, schema)
        report["c1"] = {"accepted": True, "unexpected": True}
    except ContractError as exc:
        report["c1"] = {"accepted": False, "error": exc.to_dict()}
        report["prevalidator_block"] = exc.code == "PERSISTENCE_OPERATION_REQUIRED"
    try:
        result = validate_coverage_response(manual, plan, errors, namespace, schema)
        report["manual"] = {"accepted": True, "normalized_operation_count": len(result["normalized_operations"])}
    except ContractError as exc:
        report["manual"] = {"accepted": False, "error": exc.to_dict()}
    (root / "coverage_extension.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["prevalidator_block"] and report["manual"]["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
