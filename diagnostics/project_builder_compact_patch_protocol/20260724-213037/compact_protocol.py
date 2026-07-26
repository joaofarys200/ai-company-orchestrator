from __future__ import annotations

import copy
import difflib
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

_TYPED_PROTO = Path(__file__).resolve().parents[3] / "diagnostics" / "project_builder_typed_patch_prototype" / "20260724-205420"
if str(_TYPED_PROTO) not in sys.path:
    sys.path.insert(0, str(_TYPED_PROTO))

ERROR_CODES = (
    "MISSING_REQUESTED_COMPONENTS",
    "MISSING_COMPONENT_MAPPING",
    "DECLARED_COMPONENT_WITHOUT_ARTIFACTS",
    "PERSISTENCE_NOT_IMPLEMENTED",
    "MISSING_HEALTH_ROUTE",
)
COMPONENT_IDS = ("frontend", "backend", "persistence", "tests", "preview")
TRANSFORM_IDS = (
    "ADD_JSON_FILE_PERSISTENCE",
    "PRESERVE_HEALTH_ROUTE",
    "EXPORT_SERVER_FOR_TESTS",
    "PRESERVE_HTTP_IMPORT",
)
TRANSFORM_IMPLEMENTATION_VERSION = "compact-transform-v2-trusted-metadata"
TRANSFORM_IMPLEMENTATION_SHA256 = hashlib.sha256(TRANSFORM_IMPLEMENTATION_VERSION.encode("utf-8")).hexdigest()
DEFAULT_STORAGE_FILENAME = "data.json"


class CompactContractError(ValueError):
    def __init__(self, code: str, message: str, **details: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, **self.details}


@dataclass(frozen=True)
class Namespace:
    errors: tuple[str, ...]
    components: tuple[str, ...]
    paths: tuple[str, ...]
    entrypoints: tuple[str, ...]
    transform_targets: tuple[str, ...]

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "VALID_ERROR_CODES": list(self.errors),
            "VALID_COMPONENT_IDS": list(self.components),
            "VALID_FILE_PATHS": list(self.paths),
            "VALID_ENTRYPOINT_PATHS": list(self.entrypoints),
            "VALID_TRANSFORM_TARGETS": list(self.transform_targets),
        }


@dataclass(frozen=True)
class ApplyResult:
    success: bool
    plan: dict[str, Any] | None
    operations_applied: list[dict[str, Any]]
    error_coverage_report: dict[str, Any]
    transform_report: list[dict[str, Any]]
    virtual_diff: list[dict[str, Any]]
    validator_report: dict[str, Any]
    error: dict[str, Any] | None
    rolled_back: bool
    trusted_bindings: list[dict[str, Any]] = field(default_factory=list)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _files(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["path"]: item for item in plan.get("files", [])}


def build_namespace(plan: dict[str, Any], errors: list[dict[str, Any]]) -> Namespace:
    files = _files(plan)
    entrypoints = {
        str(path).replace("\\", "/").removeprefix("./")
        for path in plan.get("entrypoints", [])
        if isinstance(path, str)
    }
    return Namespace(
        errors=tuple(sorted({item["code"] for item in errors})),
        components=tuple(COMPONENT_IDS),
        paths=tuple(sorted(files)),
        entrypoints=tuple(sorted(path for path in entrypoints if path in files)),
        transform_targets=("server.js",) if "server.js" in files else tuple(),
    )


def build_schema(namespace: Namespace, *, minimal: bool = False, reordered: bool = False) -> dict[str, Any]:
    path_enums = list(namespace.paths)
    component_enums = list(namespace.components)
    transform_enums = ["ADD_JSON_FILE_PERSISTENCE"] if minimal else list(TRANSFORM_IDS)
    branches: list[dict[str, Any]] = [
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["op", "value"],
            "properties": {
                "op": {"const": "set_components"},
                "value": {"type": "array", "minItems": 1, "maxItems": 5, "uniqueItems": True, "items": {"enum": component_enums}},
            },
        },
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["op", "component", "paths"],
            "properties": {
                "op": {"const": "set_component_files"},
                "component": {"enum": component_enums},
                "paths": {"type": "array", "minItems": 1, "maxItems": 5, "uniqueItems": True, "items": {"enum": path_enums}},
            },
        },
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["op", "path", "transform"],
            "properties": {
                "op": {"const": "apply_code_transform"},
                "path": {"enum": list(namespace.transform_targets)},
                "transform": {"enum": transform_enums},
            },
        },
    ]
    if reordered:
        branches = [branches[-1], branches[1], branches[0]]
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://local.invalid/project-builder/compact-patch-v2.schema.json",
        "title": "ProjectBuilder Compact Typed Patch Protocol v2",
        "type": "object",
        "additionalProperties": False,
        "required": ["operations"],
        "properties": {
            "operations": {
                "type": "array",
                "minItems": 1,
                "maxItems": 12,
                "items": {"oneOf": branches},
            },
        },
    }


def transform_catalog(namespace: Namespace) -> dict[str, Any]:
    return {
        "ADD_JSON_FILE_PERSISTENCE": {
            "paths": ["server.js"],
            "parameters": {"storage_filename": DEFAULT_STORAGE_FILENAME},
            "resolves": ["PERSISTENCE_NOT_IMPLEMENTED"],
            "requires": {"path": "server.js", "component_mapping": "persistence"},
            "preconditions": ["executor-bound snapshot", "http import", "/health route", "Node server structure", "no existing fs persistence"],
            "postconditions": ["node:fs import", "deterministic storage URL", "durable read", "durable write", "missing-file handling", "health preserved"],
            "implementation_sha256": TRANSFORM_IMPLEMENTATION_SHA256,
        },
        "PRESERVE_HEALTH_ROUTE": {
            "paths": ["server.js"], "parameters": {}, "resolves": [], "requires": {"path": "server.js"},
            "preconditions": ["/health exists"], "postconditions": ["/health unchanged"], "implementation_sha256": TRANSFORM_IMPLEMENTATION_SHA256,
        },
        "EXPORT_SERVER_FOR_TESTS": {
            "paths": ["server.js"], "parameters": {}, "resolves": [], "requires": {"path": "server.js"},
            "preconditions": ["server structure"], "postconditions": ["existing test export preserved"], "implementation_sha256": TRANSFORM_IMPLEMENTATION_SHA256,
        },
        "PRESERVE_HTTP_IMPORT": {
            "paths": ["server.js"], "parameters": {}, "resolves": [], "requires": {"path": "server.js"},
            "preconditions": ["http import exists"], "postconditions": ["http import preserved"], "implementation_sha256": TRANSFORM_IMPLEMENTATION_SHA256,
        },
    }


def _schema_error(response: Any, schema: dict[str, Any]) -> list[str]:
    return [error.message for error in Draft202012Validator(schema).iter_errors(response)]


def _initial_hash(plan: dict[str, Any], path: str) -> str:
    item = _files(plan).get(path)
    return sha256_text(item["content"]) if item else ""


def _raise(code: str, message: str, **details: Any) -> None:
    raise CompactContractError(code, message, **details)


def _normalize_response(response: dict[str, Any]) -> dict[str, Any]:
    internal = {"operations": []}
    for index, model_operation in enumerate(response["operations"], 1):
        operation = copy.deepcopy(model_operation)
        operation["id"] = f"op-{index:02d}"
        if operation["op"] == "apply_code_transform":
            operation["parameters"] = {"storage_filename": DEFAULT_STORAGE_FILENAME}
        internal["operations"].append(operation)
    return internal


def _project_plan(plan: dict[str, Any], operations: list[dict[str, Any]]) -> dict[str, Any]:
    projected = copy.deepcopy(plan)
    for operation in operations:
        if operation["op"] == "set_components":
            projected["components"] = list(operation["value"])
        elif operation["op"] == "set_component_files":
            projected.setdefault("component_files", {})[operation["component"]] = list(operation["paths"])
    return projected


def _operation_ids(operations: list[dict[str, Any]], predicate) -> list[str]:
    return [operation["id"] for operation in operations if predicate(operation)]


def _derive_coverage(plan: dict[str, Any], errors: list[dict[str, Any]], operations: list[dict[str, Any]]) -> dict[str, Any]:
    projected = _project_plan(plan, operations)
    mappings = projected.get("component_files") or {}
    components = set(projected.get("components", []))
    files = _files(plan)
    required = sorted({item["code"] for item in errors})
    resolved: dict[str, list[str]] = {code: [] for code in required}
    map_ids = _operation_ids(operations, lambda item: item["op"] == "set_component_files")
    map_by_component = {item["component"]: item["id"] for item in operations if item["op"] == "set_component_files"}
    all_components_mapped = bool(components) and all(
        isinstance(mappings.get(component), list)
        and bool(mappings[component])
        and all(path in files for path in mappings[component])
        for component in components
    )
    if "MISSING_REQUESTED_COMPONENTS" in required and "preview" in components:
        resolved["MISSING_REQUESTED_COMPONENTS"] = _operation_ids(operations, lambda item: item["op"] == "set_components")
    if "MISSING_COMPONENT_MAPPING" in required and all_components_mapped:
        resolved["MISSING_COMPONENT_MAPPING"] = map_ids
    if "DECLARED_COMPONENT_WITHOUT_ARTIFACTS" in required and all_components_mapped:
        resolved["DECLARED_COMPONENT_WITHOUT_ARTIFACTS"] = map_ids
    transform_ids = _operation_ids(operations, lambda item: item["op"] == "apply_code_transform" and item["transform"] == "ADD_JSON_FILE_PERSISTENCE" and item["path"] == "server.js")
    if "PERSISTENCE_NOT_IMPLEMENTED" in required and "server.js" in mappings.get("persistence", []) and transform_ids:
        resolved["PERSISTENCE_NOT_IMPLEMENTED"] = [map_by_component.get("persistence", ""), *transform_ids]
        resolved["PERSISTENCE_NOT_IMPLEMENTED"] = [item for item in resolved["PERSISTENCE_NOT_IMPLEMENTED"] if item]
    health_map = map_by_component.get("backend")
    if "MISSING_HEALTH_ROUTE" in required and health_map and "server.js" in mappings.get("backend", []) and "/health" in files.get("server.js", {}).get("content", ""):
        resolved["MISSING_HEALTH_ROUTE"] = [health_map]
    missing = sorted(code for code in required if not resolved.get(code))
    return {"valid": not missing, "required_errors": required, "resolved": resolved, "missing": missing, "catalog": "compact-v2"}


def _validate_transform(operation: dict[str, Any], plan: dict[str, Any], namespace: Namespace) -> None:
    path = operation["path"]
    if path not in namespace.transform_targets:
        _raise("PATH_NOT_IN_NAMESPACE", "Transform target is outside namespace", path=path)
    trusted_hash = operation.get("_trusted_expected_sha256")
    if trusted_hash is not None and trusted_hash != _initial_hash(plan, path):
        _raise("SNAPSHOT_CHANGED", "The transform snapshot no longer matches the trusted binding", path=path, expected=trusted_hash, actual=_initial_hash(plan, path))
    content = _files(plan)[path]["content"]
    if operation["transform"] == "ADD_JSON_FILE_PERSISTENCE":
        if "import http from 'http';" not in content or "/health" not in content or "http.createServer" not in content:
            _raise("TRANSFORM_PRECONDITION_FAILED", "server.js does not match the known fixture structure", path=path)
        if "node:fs" in content or "readFileSync" in content or "writeFileSync" in content:
            _raise("TRANSFORM_PRECONDITION_FAILED", "Persistence already appears to exist", path=path)
        filename = operation.get("parameters", {}).get("storage_filename")
        if filename != DEFAULT_STORAGE_FILENAME:
            _raise("INVALID_TRANSFORM_PARAMETER", "The executor default storage filename is invalid", value=filename)
    elif operation["transform"] == "PRESERVE_HEALTH_ROUTE" and "/health" in content:
        _raise("HEALTH_ROUTE_ALREADY_EXISTS_MAPPING_REQUIRED", "Existing /health requires backend mapping", path=path)


def _validate_operation_semantics(response: dict[str, Any], plan: dict[str, Any], namespace: Namespace) -> list[dict[str, Any]]:
    operations = response["operations"]
    ids = [item["id"] for item in operations]
    if ids != [f"op-{index:02d}" for index in range(1, len(ids) + 1)]:
        _raise("NON_DETERMINISTIC_OPERATION_IDS", "Internal operation IDs are not deterministic", operation_ids=ids)
    seen: set[tuple[str, str]] = set()
    for operation in operations:
        target = operation.get("component") or operation.get("path") or "plan"
        key = (operation["op"], str(target))
        if key in seen:
            _raise("DUPLICATE_OPERATION", "The same operation target was selected more than once", operation=operation)
        seen.add(key)
        if operation["op"] == "set_component_files":
            if operation["component"] == "preview" and any(not path.endswith((".html", ".jsx", ".tsx")) for path in operation["paths"]):
                _raise("INCOMPATIBLE_OPERATION", "Preview must map to a frontend artifact", operation=operation)
        elif operation["op"] == "apply_code_transform":
            _validate_transform(operation, plan, namespace)
    return operations


def validate_response(response: Any, plan: dict[str, Any], errors: list[dict[str, Any]], namespace: Namespace, schema: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(response, dict):
        _raise("SCHEMA_INVALID", "Response must be an object")
    schema_errors = _schema_error(response, schema)
    if schema_errors:
        _raise("SCHEMA_INVALID", "Response does not satisfy compact protocol v2 schema", errors=schema_errors)
    internal = _normalize_response(response)
    operations = _validate_operation_semantics(internal, plan, namespace)
    coverage = _derive_coverage(plan, errors, operations)
    if not coverage["valid"]:
        _raise("MISSING_ERROR_COVERAGE", "Operation semantics do not cover every initial error", coverage=coverage)
    return {"valid": True, "operations": operations, "coverage": coverage, "internal_response": internal}


def bind_trusted_metadata(response: dict[str, Any], plan: dict[str, Any], namespace: Namespace) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    internal = _normalize_response(response) if any("id" not in item for item in response.get("operations", [])) else copy.deepcopy(response)
    bindings: list[dict[str, Any]] = []
    for operation in internal.get("operations", []):
        if operation.get("op") != "apply_code_transform":
            continue
        path = operation.get("path")
        if path not in namespace.transform_targets or path not in _files(plan):
            _raise("PATH_NOT_IN_NAMESPACE", "Transform target is outside namespace", path=path)
        expected = _initial_hash(plan, path)
        operation["_trusted_expected_sha256"] = expected
        bindings.append({"operation_id": operation["id"], "path": path, "expected_sha256": expected, "source": "initial_virtual_snapshot"})
    return internal, bindings


def _expand_add_json_persistence(content: str, storage_filename: str) -> str:
    marker = "import http from 'http';\n"
    if marker not in content:
        _raise("TRANSFORM_PRECONDITION_FAILED", "http import marker not found")
    block = (
        "import http from 'node:http';\n"
        "import fs from 'node:fs';\n\n"
        f"const dataPath = new URL('./{storage_filename}', import.meta.url);\n"
        "function readData() {\n"
        "  if (!fs.existsSync(dataPath)) return {};\n"
        "  return JSON.parse(fs.readFileSync(dataPath, 'utf8'));\n"
        "}\n"
        "function writeData(value) {\n"
        "  fs.writeFileSync(dataPath, JSON.stringify(value));\n"
        "}\n"
        "writeData(readData());\n\n"
    )
    return content.replace(marker, block, 1)


def _apply_transform(content: str, operation: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if operation["transform"] == "ADD_JSON_FILE_PERSISTENCE":
        result = _expand_add_json_persistence(content, operation["parameters"]["storage_filename"])
    elif operation["transform"] in {"PRESERVE_HEALTH_ROUTE", "EXPORT_SERVER_FOR_TESTS", "PRESERVE_HTTP_IMPORT"}:
        result = content
    else:
        _raise("UNKNOWN_TRANSFORM", "Transform is not registered", transform=operation["transform"])
    return result, {
        "id": operation["id"], "transform": operation["transform"], "path": operation["path"],
        "implementation_sha256": TRANSFORM_IMPLEMENTATION_SHA256,
        "before_sha256": sha256_text(content), "after_sha256": sha256_text(result), "changed": content != result,
    }


def _virtual_diff(before: dict[str, str], after: dict[str, str]) -> list[dict[str, Any]]:
    result = []
    for path in sorted(before):
        if before[path] == after[path]:
            continue
        result.append({
            "path": path,
            "before_sha256": sha256_text(before[path]),
            "after_sha256": sha256_text(after[path]),
            "unified_diff": "".join(difflib.unified_diff(before[path].splitlines(True), after[path].splitlines(True), fromfile=path, tofile=path)),
        })
    return result


def run_real_validators(plan: dict[str, Any], prompt: str) -> dict[str, Any]:
    from typed_patch_prototype import run_real_validators as validate_virtual_plan
    return validate_virtual_plan(plan, prompt)


def apply_response(response: dict[str, Any], plan: dict[str, Any], errors: list[dict[str, Any]], namespace: Namespace, schema: dict[str, Any], validator_prompt: str, current_plan: dict[str, Any] | None = None) -> ApplyResult:
    before = {path: item["content"] for path, item in _files(plan).items()}
    trusted_bindings: list[dict[str, Any]] = []
    try:
        coverage = validate_response(response, plan, errors, namespace, schema)
        bound, trusted_bindings = bind_trusted_metadata(coverage["internal_response"], plan, namespace)
        for binding in trusted_bindings:
            if current_plan is not None:
                current_hash = _initial_hash(current_plan, binding["path"])
                if current_hash != binding["expected_sha256"]:
                    _raise("SNAPSHOT_CHANGED", "The project changed after the initial snapshot", path=binding["path"], expected=binding["expected_sha256"], actual=current_hash)
        operations = _validate_operation_semantics(bound, plan, namespace)
        working = copy.deepcopy(current_plan if current_plan is not None else plan)
        applied: list[dict[str, Any]] = []
        transforms: list[dict[str, Any]] = []
        for operation in operations:
            if operation["op"] == "set_components":
                working["components"] = list(operation["value"])
            elif operation["op"] == "set_component_files":
                working.setdefault("component_files", {})[operation["component"]] = list(operation["paths"])
            else:
                item = _files(working)[operation["path"]]
                new_content, transform_report = _apply_transform(item["content"], operation)
                item["content"] = new_content
                transforms.append(transform_report)
            applied.append(copy.deepcopy(operation))
        after = {path: item["content"] for path, item in _files(working).items()}
        validator_report = run_real_validators(working, validator_prompt)
        if not validator_report.get("valid"):
            _raise("VALIDATORS_FAILED", "Composed virtual plan failed real validators", validator_report=validator_report)
        return ApplyResult(True, working, applied, coverage["coverage"], transforms, _virtual_diff(before, after), validator_report, None, False, trusted_bindings)
    except CompactContractError as exc:
        details = exc.to_dict()
        return ApplyResult(False, None, [], details.get("coverage", {"valid": False}), [], [], details.get("validator_report", {}), details, True, trusted_bindings)
