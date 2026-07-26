from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator, RefResolver

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


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().parent
AUDIT = ROOT / "diagnostics" / "project_builder_plan_quality_audit" / "20260724-193345"
RECORDER = ROOT / "diagnostics" / "project_builder_flight_recorder" / "5ac225a31d8b471db547d15b36b9d0e4"
JOURNAL_PATH = AUDIT / "source" / "project_build_journal.json"
SCHEMA_PATH = OUTPUT / "operations.schema.json"
RESPONSE_SCHEMA_PATH = OUTPUT / "response.schema.json"
sys.path.insert(0, str(ROOT))
os.environ.setdefault("CREWAI_STORAGE_DIR", str(OUTPUT / "crewai_storage"))


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_case() -> tuple[dict, list[dict], str, dict, dict]:
    journal = read_json(JOURNAL_PATH)
    first = journal["planning_validation_history"][0]
    plan = json.loads(first["response"])
    errors = first["errors"]
    prompt = (AUDIT / "source" / "ollama_requester_audit" / "wp1_prompt.txt").read_text(encoding="utf-8")
    schema = read_json(SCHEMA_PATH)
    namespace = build_namespace(plan, errors)
    return plan, errors, prompt, schema, namespace.to_dict()


def copy_input_evidence() -> dict[str, str]:
    input_dir = OUTPUT / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    journal = read_json(JOURNAL_PATH)
    first = journal["planning_validation_history"][0]
    plan = json.loads(first["response"])
    values = {
        "original_plan.json": plan,
        "initial_errors.json": first["errors"],
        "error_artifact_mappings.json": first["error_artifact_mappings"],
        "ideal_minimal_correction.json": read_json(AUDIT / "offline" / "ideal_minimal_correction.json"),
        "ideal_corrected_plan.json": read_json(AUDIT / "offline" / "ideal_corrected_plan.json"),
        "offline_validation.json": read_json(AUDIT / "offline" / "offline_validation.json"),
        "historical_focal_response.json": json.loads(journal["planning_validation_history"][1]["response"]),
        "current_focal_schema.json": read_json(AUDIT / "source" / "ollama_requester_audit" / "wp1_schema.json"),
        "real_file_paths.json": [item["path"] for item in plan["files"]],
    }
    hashes: dict[str, str] = {}
    for name, value in values.items():
        path = input_dir / name
        write_json(path, value)
        hashes[name] = hash_file(path)
    recorder_dir = input_dir / "flight_recorder"
    for name in ("summary.json", "final_state.json", "errors.json"):
        source = RECORDER / name
        if source.exists():
            target = recorder_dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
            hashes[f"flight_recorder/{name}"] = hash_file(target)
    write_json(input_dir / "artifact_hashes.json", hashes)
    return hashes


def make_manual_operations(plan: dict) -> list[dict]:
    server = next(item for item in plan["files"] if item["path"] == "server.js")
    ideal = read_json(AUDIT / "offline" / "ideal_minimal_correction.json")
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


def model_response_schema(schema: dict) -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["operations"],
        "properties": {"operations": schema},
    }


def call_model(prompt: str, response_schema: dict) -> dict:
    payload = {
        "model": "qwen3.5:9b",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "format": response_schema,
        "options": {"temperature": 0, "top_p": 0.8, "num_ctx": 8192},
    }
    started = time.perf_counter()
    request = Request(
        "http://localhost:11434/api/chat",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=180) as response:
        raw = response.read().decode("utf-8")
    elapsed = time.perf_counter() - started
    envelope = json.loads(raw)
    content = envelope.get("message", {}).get("content", "")
    return {
        "payload": payload,
        "raw_envelope": envelope,
        "content": content,
        "elapsed_seconds": round(elapsed, 3),
        "status": "HTTP_OK",
    }


def validate_model_content(content: str, plan: dict, namespace, schema: dict) -> tuple[list[dict], list[dict]]:
    response = json.loads(content)
    response_schema = model_response_schema(schema)
    errors = list(Draft202012Validator(response_schema).iter_errors(response))
    if errors:
        raise ContractError("MODEL_RESPONSE_SCHEMA_INVALID", "Model response failed response schema", errors=[error.message for error in errors])
    operations = response["operations"]
    normalized = validate_operations(operations, plan, namespace, schema)
    return operations, normalized


def write_report(data: dict) -> None:
    lines = [
        "# Typed Patch Prototype",
        "",
        f"Status: **{data['status']}**",
        "",
        "This is an offline diagnostic prototype. It does not modify ProjectBuilder, run WP1/WP2, materialize a project, execute npm, or start preview.",
        "",
        "## Scope",
        "",
        "- Input case: real health-boundary-probe WP1 planning failure.",
        "- File namespace: package.json, server.js, index.html, test.js.",
        "- Replacement target: server.js only, derived from PERSISTENCE_NOT_IMPLEMENTED.",
        "- Model calls: " + str(data.get("model_call_count", 0)),
        "",
        "## Baseline",
        "",
        f"- Manual typed patch: **{data['manual_status']}**.",
        f"- Manual validator error codes: `{', '.join(data['manual_validation'].get('error_codes', [])) or 'none'}`.",
        "- The manual baseline is accepted only when the real validator returns valid=true.",
        "",
        "## Model P1",
        "",
        f"- Model: `qwen3.5:9b`; context: `8192`; temperature: `0`; top_p: `0.8`; think: `false`.",
        f"- Result: **{data['model_status']}**.",
        f"- Response time: `{data.get('model_elapsed_seconds', 'n/a')}s`.",
        f"- Contract errors: `{', '.join(data.get('model_contract_errors', [])) or 'none'}`.",
        f"- Model validator errors: `{', '.join(data.get('model_validation', {}).get('error_codes', [])) or 'none'}`.",
        "",
        "## Safety",
        "",
        "- Operations are validated before application.",
        "- No create_file, rename_file, delete_file, arbitrary patch, merge object, or execute command operation exists.",
        "- Hash mismatch, unknown path, duplicate/conflicting operations, and schema violations fail closed.",
        "- Application is pure over a deep copy; no project path is opened or written.",
        "- No local repair or third model call is present.",
        "",
        "## Evidence",
        "",
        f"- Artifact hashes: `{OUTPUT / 'input' / 'artifact_hashes.json'}`.",
        f"- Manual validation: `{OUTPUT / 'manual_validation.json'}`.",
        f"- Model response: `{OUTPUT / 'model_response.json'}`.",
        f"- Metrics: `{OUTPUT / 'metrics.json'}`.",
    ]
    (OUTPUT / "FINAL_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    hashes = copy_input_evidence()
    plan, initial_errors, original_prompt, schema, namespace_data = load_case()
    namespace = build_namespace(plan, initial_errors)
    scope = derive_scope(plan, initial_errors, namespace)
    typed_prompt = build_typed_prompt(plan, scope, namespace, schema)
    write_json(OUTPUT / "namespace.json", namespace.to_dict())
    write_json(OUTPUT / "scope_derivation.json", scope)
    (OUTPUT / "typed_prompt.txt").write_text(typed_prompt, encoding="utf-8")
    write_json(OUTPUT / "response.schema.json", model_response_schema(schema))

    manual_operations = make_manual_operations(plan)
    write_json(OUTPUT / "manual_operations.json", manual_operations)
    manual_status = "FAILED"
    manual_validation: dict = {}
    manual_error = None
    try:
        manual_result = apply_operations(plan, manual_operations, namespace, schema)
        write_json(OUTPUT / "manual_normalized_operations.json", manual_result.applied_operations)
        write_json(OUTPUT / "manual_composed_plan.json", manual_result.plan)
        write_json(OUTPUT / "manual_changes.json", manual_result.changes)
        manual_validation = run_real_validators(manual_result.plan, original_prompt)
        write_json(OUTPUT / "manual_validation.json", manual_validation)
        manual_status = "MANUAL_TYPED_PATCH_PASSED" if manual_validation.get("valid") else "MANUAL_TYPED_PATCH_FAILED"
    except Exception as exc:
        manual_error = {"type": type(exc).__name__, "message": str(exc)}
        write_json(OUTPUT / "manual_error.json", manual_error)

    if manual_status != "MANUAL_TYPED_PATCH_PASSED":
        data = {
            "status": "MANUAL_BASELINE_FAILED",
            "manual_status": manual_status,
            "manual_validation": manual_validation,
            "model_status": "NOT_EXECUTED",
            "model_call_count": 0,
        }
        write_json(OUTPUT / "metrics.json", data)
        write_report(data)
        return 1

    response_schema = model_response_schema(schema)
    model_status = "FAILED"
    model_contract_errors: list[str] = []
    model_validation: dict = {}
    model_elapsed = None
    model_ops = None
    model_error = None
    model_call_count = 1
    try:
        result = call_model(typed_prompt, response_schema)
        model_elapsed = result["elapsed_seconds"]
        write_json(OUTPUT / "model_request.json", result["payload"])
        (OUTPUT / "model_response_raw.txt").write_text(result["content"], encoding="utf-8")
        operations, normalized = validate_model_content(result["content"], plan, namespace, schema)
        model_ops = normalized
        write_json(OUTPUT / "model_operations.json", operations)
        write_json(OUTPUT / "model_normalized_operations.json", normalized)
        composed = apply_operations(plan, normalized, namespace, schema)
        write_json(OUTPUT / "model_composed_plan.json", composed.plan)
        write_json(OUTPUT / "model_changes.json", composed.changes)
        model_validation = run_real_validators(composed.plan, original_prompt)
        write_json(OUTPUT / "model_validation.json", model_validation)
        model_status = "MODEL_TYPED_PATCH_PASSED" if model_validation.get("valid") else "MODEL_TYPED_PATCH_FAILED_VALIDATION"
        write_json(OUTPUT / "model_response.json", {"operations": operations})
    except Exception as exc:
        model_error = {"type": type(exc).__name__, "message": str(exc)}
        model_contract_errors.append(getattr(exc, "code", type(exc).__name__))
        write_json(OUTPUT / "model_error.json", model_error)
    metrics = {
        "status": model_status,
        "manual_status": manual_status,
        "manual_validation": manual_validation,
        "model_status": model_status,
        "model_elapsed_seconds": model_elapsed,
        "model_contract_errors": model_contract_errors,
        "model_validation": model_validation,
        "model_call_count": model_call_count,
        "model_operations_count": len(model_ops or []),
        "input_artifact_count": len(hashes),
        "production_changes_allowed": False,
        "materialization": False,
        "commands_executed": [],
        "third_model_call": False,
        "local_repair": False,
    }
    write_json(OUTPUT / "metrics.json", metrics)
    write_report(metrics)
    return 0 if model_status == "MODEL_TYPED_PATCH_PASSED" else 1


if __name__ == "__main__":
    sys.exit(main())
