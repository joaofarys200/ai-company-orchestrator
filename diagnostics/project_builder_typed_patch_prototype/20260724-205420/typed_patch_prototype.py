"""Offline typed operational patch prototype for the ProjectBuilder audit case.

This module deliberately has no production integration. It composes an in-memory
plan, validates a closed operation namespace, and applies accepted operations to
that copy only.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator


OPERATION_ORDER = {
    "set_components": 10,
    "set_component_files": 20,
    "set_preview_strategy": 30,
    "replace_file_content": 40,
    "replace_text": 50,
}
ALLOWED_PREVIEW_FIELDS = {"enabled", "method", "healthcheck_path", "command"}
PREVIEW_FIELD_TYPES = {
    "enabled": bool,
    "method": str,
    "healthcheck_path": str,
    "command": str,
}


class ContractError(ValueError):
    def __init__(self, code: str, message: str, **details: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, **self.details}


@dataclass(frozen=True)
class ClosedNamespace:
    valid_plan_fields: tuple[str, ...]
    valid_component_ids: tuple[str, ...]
    valid_file_paths: tuple[str, ...]
    valid_entrypoint_paths: tuple[str, ...]
    valid_replacement_targets: tuple[str, ...]

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "VALID_PLAN_FIELDS": list(self.valid_plan_fields),
            "VALID_COMPONENT_IDS": list(self.valid_component_ids),
            "VALID_FILE_PATHS": list(self.valid_file_paths),
            "VALID_ENTRYPOINT_PATHS": list(self.valid_entrypoint_paths),
            "VALID_REPLACEMENT_TARGETS": list(self.valid_replacement_targets),
        }


@dataclass(frozen=True)
class PatchResult:
    plan: dict[str, Any]
    applied_operations: list[dict[str, Any]]
    rejected_operations: list[dict[str, Any]]
    changes: list[dict[str, Any]]


def sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _normal_path(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        return ""
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        return ""
    return str(path)


def _files_by_path(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        item["path"]: item
        for item in plan.get("files", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }


def build_namespace(plan: dict[str, Any], errors: list[dict[str, Any]]) -> ClosedNamespace:
    files = _files_by_path(plan)
    components = set(str(value) for value in plan.get("components", []) if isinstance(value, str))
    mappings = plan.get("component_files") or {}
    if isinstance(mappings, dict):
        components.update(str(value) for value in mappings if isinstance(value, str))
    for error in errors:
        component = error.get("component")
        if isinstance(component, str) and component:
            components.add(component)
    requested = {"frontend", "backend", "persistence", "tests", "preview"}
    components.update(requested.intersection(components | {"preview"}))
    entrypoint_values = {
        str(path).replace("\\", "/").removeprefix("./")
        for path in plan.get("entrypoints", [])
        if isinstance(path, str)
    }
    entrypoints = tuple(sorted(path for path in entrypoint_values if path in files))

    replacement_targets: set[str] = set()
    for error in errors:
        if error.get("code") != "PERSISTENCE_NOT_IMPLEMENTED":
            continue
        candidates = []
        for path in (mappings.get("backend", []) if isinstance(mappings, dict) else []):
            if path in files and path not in candidates:
                candidates.append(path)
        for path in entrypoints:
            if path in files and path not in candidates and path.endswith((".js", ".mjs", ".cjs", ".ts", ".py")):
                candidates.append(path)
        replacement_targets.update(candidates[:1])

    return ClosedNamespace(
        valid_plan_fields=tuple(sorted(set(plan) | {"components", "component_files", "preview_strategy"})),
        valid_component_ids=tuple(sorted(components)),
        valid_file_paths=tuple(sorted(files)),
        valid_entrypoint_paths=entrypoints,
        valid_replacement_targets=tuple(sorted(replacement_targets)),
    )


def _schema_errors(operations: Any, schema: dict[str, Any]) -> list[dict[str, Any]]:
    validator = Draft202012Validator(schema)
    return [
        {
            "code": "SCHEMA_INVALID",
            "message": error.message,
            "path": list(error.absolute_path),
            "schema_path": list(error.absolute_schema_path),
        }
        for error in sorted(validator.iter_errors(operations), key=lambda item: list(item.absolute_path))
    ]


def _require_path(path: str, namespace: ClosedNamespace, *, replacement: bool = False) -> None:
    allowed = namespace.valid_replacement_targets if replacement else namespace.valid_file_paths
    if path not in allowed:
        raise ContractError(
            "TARGET_NOT_REPLACEABLE" if replacement else "PATH_NOT_IN_NAMESPACE",
            f"Path is outside the closed namespace: {path}",
            path=path,
            allowed=list(allowed),
        )


def _validate_operation_shape(operation: dict[str, Any], namespace: ClosedNamespace, files: dict[str, dict[str, Any]]) -> None:
    op = operation["op"]
    if op == "set_components":
        values = operation["value"]
        unknown = [value for value in values if value not in namespace.valid_component_ids]
        if unknown:
            raise ContractError("INVALID_COMPONENT", f"Unknown component(s): {unknown}", values=unknown)
        if len(values) != len(set(values)):
            raise ContractError("DUPLICATE_OPERATION", "set_components contains duplicate components")
    elif op == "set_component_files":
        component = operation["component"]
        if component not in namespace.valid_component_ids:
            raise ContractError("INVALID_COMPONENT", f"Unknown component: {component}", component=component)
        paths = operation["paths"]
        if len(paths) != len(set(paths)):
            raise ContractError("DUPLICATE_OPERATION", "set_component_files contains duplicate paths", component=component)
        for path in paths:
            _require_path(path, namespace)
            if path not in files:
                raise ContractError("PATH_NOT_IN_NAMESPACE", f"Path does not exist in the plan: {path}", path=path)
    elif op == "set_preview_strategy":
        field = operation["field"]
        value = operation["value"]
        if field not in ALLOWED_PREVIEW_FIELDS:
            raise ContractError("OUT_OF_SCOPE_FIELD", f"Preview field is not allowed: {field}", field=field)
        expected = PREVIEW_FIELD_TYPES[field]
        if not isinstance(value, expected) or (field in {"method", "healthcheck_path"} and not value):
            raise ContractError("INVALID_FIELD_TYPE", f"Invalid value for preview field: {field}", field=field)
        if field == "healthcheck_path" and (not value.startswith("/") or " " in value):
            raise ContractError("INVALID_FIELD_TYPE", "healthcheck_path must be an absolute URL path", field=field)
    elif op in {"replace_file_content", "replace_text"}:
        path = operation["path"]
        _require_path(path, namespace, replacement=True)
        if path not in files:
            raise ContractError("PATH_NOT_IN_NAMESPACE", f"Replacement target does not exist: {path}", path=path)
        actual_hash = sha256_text(files[path]["content"])
        if operation["expected_sha256"] != actual_hash:
            raise ContractError(
                "HASH_MISMATCH",
                f"Expected hash does not match {path}",
                path=path,
                expected=operation["expected_sha256"],
                actual=actual_hash,
            )
        if op == "replace_file_content" and not operation["content"]:
            raise ContractError("EMPTY_REPLACEMENT", f"Replacement is empty: {path}", path=path)
        if op == "replace_text":
            count = files[path]["content"].count(operation["old_text"])
            if count == 0:
                raise ContractError("EXPECTED_TEXT_NOT_FOUND", f"Text not found in {path}", path=path)
            if count != operation["expected_occurrences"]:
                raise ContractError(
                    "EXPECTED_OCCURRENCE_MISMATCH",
                    f"Unexpected occurrence count in {path}",
                    path=path,
                    expected=operation["expected_occurrences"],
                    actual=count,
                )


def validate_operations(
    operations: Any,
    plan: dict[str, Any],
    namespace: ClosedNamespace,
    schema: dict[str, Any],
) -> list[dict[str, Any]]:
    errors = _schema_errors(operations, schema)
    if errors:
        raise ContractError("SCHEMA_INVALID", "Operations do not satisfy the Draft 2020-12 schema", errors=errors)
    files = _files_by_path(plan)
    seen_keys: set[tuple[str, str]] = set()
    component_keys: dict[str, tuple[str, ...]] = {}
    for operation in operations:
        op = operation["op"]
        key_target = operation.get("path") or operation.get("component") or operation.get("field") or "plan"
        if op == "set_component_files":
            component = operation["component"]
            paths = tuple(operation["paths"])
            previous = component_keys.get(component)
            if previous is not None and previous != paths:
                raise ContractError("CONFLICTING_OPERATION", f"Conflicting component mapping: {component}", component=component)
            component_keys[component] = paths
        key = (op, str(key_target))
        if key in seen_keys:
            raise ContractError("DUPLICATE_OPERATION", f"Duplicate operation: {op} {key_target}", operation=operation)
        seen_keys.add(key)
        _validate_operation_shape(operation, namespace, files)
    return sorted((copy.deepcopy(item) for item in operations), key=lambda item: (OPERATION_ORDER[item["op"]], json.dumps(item, sort_keys=True)))


def apply_operations(
    plan: dict[str, Any],
    operations: list[dict[str, Any]],
    namespace: ClosedNamespace,
    schema: dict[str, Any],
) -> PatchResult:
    accepted = validate_operations(operations, plan, namespace, schema)
    working = copy.deepcopy(plan)
    before_files = {path: item["content"] for path, item in _files_by_path(working).items()}
    changes: list[dict[str, Any]] = []
    for operation in accepted:
        op = operation["op"]
        if op == "set_components":
            working["components"] = list(operation["value"])
        elif op == "set_component_files":
            working.setdefault("component_files", {})[operation["component"]] = list(operation["paths"])
        elif op == "set_preview_strategy":
            working.setdefault("preview_strategy", {})[operation["field"]] = operation["value"]
        elif op in {"replace_file_content", "replace_text"}:
            item = _files_by_path(working)[operation["path"]]
            old = item["content"]
            new = operation["content"] if op == "replace_file_content" else old.replace(operation["old_text"], operation["new_text"], operation["expected_occurrences"])
            item["content"] = new
            changes.append({
                "path": operation["path"],
                "before_sha256": sha256_text(old),
                "after_sha256": sha256_text(new),
                "changed": old != new,
            })
    after_files = {path: item["content"] for path, item in _files_by_path(working).items()}
    for path in sorted(set(before_files) | set(after_files)):
        if before_files.get(path) != after_files.get(path) and not any(item["path"] == path for item in changes):
            changes.append({
                "path": path,
                "before_sha256": sha256_text(before_files[path]),
                "after_sha256": sha256_text(after_files[path]),
                "changed": True,
            })
    return PatchResult(working, accepted, [], sorted(changes, key=lambda item: item["path"]))


def derive_scope(plan: dict[str, Any], errors: list[dict[str, Any]], namespace: ClosedNamespace) -> dict[str, Any]:
    files = _files_by_path(plan)
    mappings = plan.get("component_files") or {}
    scope: list[dict[str, Any]] = []
    for error in errors:
        code = error.get("code")
        if code == "MISSING_REQUESTED_COMPONENTS":
            scope.append({
                "error_code": code,
                "authorized_plan_fields": ["components"],
                "candidate_files": [],
                "operation_types": ["set_components"],
                "evidence": {"missing_components": ["preview"]},
                "reason": "The requested preview component is absent; set the complete final component list.",
            })
        elif code in {"MISSING_COMPONENT_MAPPING", "DECLARED_COMPONENT_WITHOUT_ARTIFACTS", "MAPPED_FILE_NOT_FOUND"}:
            candidates: dict[str, list[str]] = {
                "frontend": [path for path in ("index.html",) if path in files],
                "backend": [path for path in ("server.js",) if path in files],
                "persistence": [path for path in ("server.js",) if path in files],
                "tests": [path for path in ("test.js",) if path in files],
                "preview": [path for path in ("index.html",) if path in files],
            }
            component = error.get("component")
            affected = [component] if component in candidates else ["frontend", "backend", "persistence", "tests", "preview"]
            scope.append({
                "error_code": code,
                "authorized_plan_fields": ["component_files"],
                "candidate_files": sorted({path for item in affected for path in candidates[item]}),
                "operation_types": ["set_component_files"],
                "evidence": {"affected_components": affected, "valid_paths": list(namespace.valid_file_paths)},
                "reason": "Map each affected component to existing planned files only.",
            })
        elif code == "MISSING_HEALTH_ROUTE":
            health_path = str((plan.get("preview_strategy") or {}).get("healthcheck_path") or "/health")
            existing = [
                path for path, item in files.items()
                if health_path in item["content"] and path in namespace.valid_entrypoint_paths
            ]
            backend_unmapped = [path for path in existing if path not in (mappings.get("backend", []) if isinstance(mappings, dict) else [])]
            scope.append({
                "error_code": code,
                "authorized_plan_fields": ["component_files", "preview_strategy"],
                "candidate_files": backend_unmapped,
                "operation_types": ["set_component_files", "set_preview_strategy"],
                "evidence": {"healthcheck_path": health_path, "route_files": existing, "unmapped_backend_files": backend_unmapped},
                "reason": (
                    f'The route "{health_path}" already exists in "{backend_unmapped[0]}"; '
                    "map that existing backend file and do not create a route file."
                    if backend_unmapped else "No existing health route was found; no new route path is authorized."
                ),
            })
        elif code == "PERSISTENCE_NOT_IMPLEMENTED":
            backend = [path for path in (mappings.get("backend", []) if isinstance(mappings, dict) else []) if path in files and path.endswith(".js")]
            if not backend:
                backend = [path for path in namespace.valid_entrypoint_paths if path in files and path.endswith(".js")]
            candidate = backend[:1]
            scope.append({
                "error_code": code,
                "authorized_plan_fields": ["component_files"],
                "candidate_files": candidate,
                "operation_types": ["set_component_files", "replace_file_content", "replace_text"],
                "evidence": {"backend_entrypoint": candidate, "durability": "no durable read/write mechanism"},
                "reason": (
                    f'Persistence is absent; modify only existing backend entrypoint "{candidate[0]}" '
                    "using Node.js standard-library durable read/write behavior."
                    if candidate else "No existing executable persistence candidate is available."
                ),
            })
    return {
        "errors": scope,
        "authorized_fields": sorted({field for item in scope for field in item["authorized_plan_fields"]}),
        "authorized_operations": sorted({op for item in scope for op in item["operation_types"]}),
        "replacement_targets": list(namespace.valid_replacement_targets),
    }


def build_typed_prompt(plan: dict[str, Any], scope: dict[str, Any], namespace: ClosedNamespace, schema: dict[str, Any]) -> str:
    current_hashes = {
        path: sha256_text(item["content"])
        for path, item in sorted(_files_by_path(plan).items())
    }
    return "\n".join([
        "Return only one JSON object with this shape: {\"operations\": [...]}.",
        "Do not return a corrected full plan, prose, JSON Patch, or operations outside this schema.",
        "Use final values for fields; no append, add, patch, delta, fuzzy matching, defaults, file creation, rename, delete, or command execution.",
        "Every path must be an exact member of VALID_FILE_PATHS. No new or derived path is allowed.",
        "Replace content only after matching expected_sha256. Preserve unrelated content.",
        "Do not omit a correction required by an actionable error. A field operation must contain its complete final value.",
        "All operations are validated and applied deterministically by the program; an invalid operation fails closed.",
        "CURRENT PLAN:\n" + json.dumps(plan, ensure_ascii=False, indent=2),
        "CURRENT FILE SHA256 VALUES:\n" + json.dumps(current_hashes, ensure_ascii=False, indent=2),
        "ACTIONABLE ERRORS:\n" + json.dumps(scope["errors"], ensure_ascii=False, indent=2),
        "CLOSED NAMESPACE:\n" + json.dumps(namespace.to_dict(), ensure_ascii=False, indent=2),
        "OPERATIONS SCHEMA (Draft 2020-12):\n" + json.dumps(schema, ensure_ascii=False, separators=(",", ":")),
    ])


def run_real_validators(plan: dict[str, Any], prompt: str) -> dict[str, Any]:
    from agents.orchestrator import project_builder

    try:
        processed = project_builder._validated_raw_project_plan(plan, prompt)
    except project_builder._PlanValidationFailure as exc:
        return {
            "valid": False,
            "error_codes": [item.code for item in exc.errors],
            "errors": [item.to_dict() for item in exc.errors],
        }
    return {
        "valid": True,
        "error_codes": [],
        "plan_hash": processed.final_plan_hash,
        "static_analysis": processed.static_analysis,
    }
