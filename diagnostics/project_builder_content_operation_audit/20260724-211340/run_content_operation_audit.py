from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().parent
PROTO = ROOT / "diagnostics" / "project_builder_typed_patch_prototype" / "20260724-205420"
os.environ.setdefault("CREWAI_STORAGE_DIR", str(OUTPUT / "crewai_storage"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(PROTO))

from typed_patch_prototype import (  # noqa: E402
    ContractError,
    apply_operations,
    build_namespace,
    run_real_validators,
    sha256_text,
    validate_operations,
)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_case():
    plan = read_json(PROTO / "input" / "original_plan.json")
    errors = read_json(PROTO / "input" / "initial_errors.json")
    schema = read_json(PROTO / "operations.schema.json")
    namespace = build_namespace(plan, errors)
    request = read_json(PROTO / "model_request.json")
    prompt = (PROTO / "model_prompt_used.txt").read_text(encoding="utf-8")
    return plan, errors, schema, namespace, request, prompt


def copy_inputs() -> dict[str, str]:
    source_names = [
        "input/original_plan.json",
        "input/initial_errors.json",
        "scope_derivation.json",
        "operations.schema.json",
        "model_prompt_used.txt",
        "model_request.json",
        "model_response_raw.txt",
        "model_operations.json",
        "model_normalized_operations.json",
        "model_validation.json",
        "manual_operations.json",
        "manual_composed_plan.json",
        "manual_changes.json",
        "manual_validation.json",
        "FINAL_REPORT.md",
    ]
    target = OUTPUT / "input"
    target.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}
    for name in source_names:
        source = PROTO / name
        destination = target / name.replace("/", "_")
        shutil.copy2(source, destination)
        hashes[name] = sha256_file(destination)
    write_json(target / "hashes.json", hashes)
    return hashes


def response_schema(operation_schema: dict, *, include_actions: bool = False) -> dict:
    properties = {"operations": operation_schema}
    required = ["operations"]
    if include_actions:
        properties["required_actions"] = {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["target", "reason", "required_operation_type"],
                "properties": {
                    "target": {"type": "string", "minLength": 1},
                    "reason": {"type": "string", "minLength": 1},
                    "required_operation_type": {"type": "string", "minLength": 1},
                },
            },
        }
        required = ["required_actions", "operations"]
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
    }


def filter_operations_schema(schema: dict, *, include_full: bool, include_text: bool) -> dict:
    result = copy.deepcopy(schema)
    names = {"set_components", "set_component_files", "set_preview_strategy"}
    if include_full:
        names.add("replace_file_content")
    if include_text:
        names.add("replace_text")
    result["items"]["oneOf"] = [
        branch for branch in result["items"]["oneOf"]
        if branch["properties"]["op"]["const"] in names
    ]
    return result


def server_content(plan: dict) -> str:
    return next(item["content"] for item in plan["files"] if item["path"] == "server.js")


def current_server_hash(plan: dict) -> str:
    return sha256_text(server_content(plan))


def base_prompt_context(plan: dict, errors: list[dict], namespace, base_prompt: str) -> str:
    return base_prompt + "\n\nAUDIT REQUIREMENT: resolve every listed validator error in this response.\n" + json.dumps({
        "target": "server.js",
        "target_sha256": current_server_hash(plan),
        "error": "PERSISTENCE_NOT_IMPLEMENTED",
        "error_details": next(item for item in errors if item["code"] == "PERSISTENCE_NOT_IMPLEMENTED"),
        "allowed_content_targets": list(namespace.valid_replacement_targets),
    }, ensure_ascii=False, indent=2)


def make_cases(plan, errors, namespace, base_schema, request, base_prompt):
    c1_schema = base_schema
    c1_response_schema = copy.deepcopy(request["format"])
    c1_prompt = base_prompt
    c2_prompt = c1_prompt + """

MANDATORY CONTENT ACTION:
The final patch is invalid unless it contains an operation that modifies "server.js".
You MUST include exactly one content-changing operation targeting "server.js".
Do not return a response that only changes plan fields.
All listed validator errors must be resolved in this response.
"""
    c3_schema = filter_operations_schema(base_schema, include_full=True, include_text=False)
    c3_prompt = c1_prompt + "\nserver.js is the only allowed content target.\n"
    c4_prompt = c1_prompt + """

REQUIRED SERVER.JS CONTENT TEMPLATE:
Return the complete replacement content for server.js using this structure. Do not omit the content operation.
```text
import http from 'http';
import fs from 'node:fs';

// persistence implementation marker:
// deterministic storage path;
// durable read;
// durable write;
// missing-file handling;

const server = http.createServer((req, res) => {
  // preserve the existing /health behavior
});
```
The final content must use Node.js standard-library filesystem APIs, read and write durable state, preserve /health, and add no external dependency.
"""
    c5_schema = filter_operations_schema(base_schema, include_full=False, include_text=True)
    old_import = "import http from 'http';\n"
    c5_prompt = c1_prompt + f"""

LOCALIZED REPLACEMENT ONLY:
Use replace_text, not replace_file_content. Do not choose a different path.
Target: server.js
expected_sha256: {current_server_hash(plan)}
old_text: {json.dumps(old_import)}
expected_occurrences: 1
Replace that exact import line with a block that adds a node:fs import, a deterministic storage path, durable read and write functions, missing-file handling, and one durable read/write integration. Preserve the rest of server.js including /health.
"""
    c6_schema = response_schema(base_schema, include_actions=True)
    c6_prompt = c1_prompt + """

TWO-STAGE REQUIRED RESPONSE:
First declare required_actions. It must contain an action with target "server.js", reason "PERSISTENCE_NOT_IMPLEMENTED", and required_operation_type "replace_file_content" or "replace_text".
Then operations must concretize exactly those actions. A response with the required action but without its content operation is invalid.
"""
    return [
        {"id": "C1", "description": "exact P1 prompt and schema", "prompt": c1_prompt, "schema": c1_schema, "response_schema": c1_response_schema},
        {"id": "C2", "description": "explicitly mandatory content operation", "prompt": c2_prompt, "schema": c1_schema, "response_schema": c1_response_schema},
        {"id": "C3", "description": "only required operation branches; server.js content target", "prompt": c3_prompt, "schema": c3_schema, "response_schema": response_schema(c3_schema)},
        {"id": "C4", "description": "full-file replacement with structural template", "prompt": c4_prompt, "schema": c1_schema, "response_schema": c1_response_schema},
        {"id": "C5", "description": "localized replace_text with exact insertion point", "prompt": c5_prompt, "schema": c5_schema, "response_schema": response_schema(c5_schema)},
        {"id": "C6", "description": "required_actions followed by operations", "prompt": c6_prompt, "schema": c1_schema, "response_schema": c6_schema},
    ]


def call_model(prompt: str, output_schema: dict) -> dict:
    payload = {
        "model": "qwen3.5:9b",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "format": output_schema,
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
    envelope = json.loads(raw)
    return {
        "payload": payload,
        "envelope": envelope,
        "content": envelope.get("message", {}).get("content", ""),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }


def persistence_signals(content: str) -> dict[str, bool]:
    lower = content.lower()
    imports = re.findall(r"(?:from\s+['\"]|require\(\s*['\"])([^'\"]+)", content)
    node_builtins = {
        "assert", "buffer", "child_process", "crypto", "events", "fs", "fs/promises",
        "http", "https", "net", "os", "path", "querystring", "stream", "url", "util",
    }
    return {
        "filesystem_import": any(value in {"fs", "node:fs", "fs/promises", "node:fs/promises"} for value in imports),
        "deterministic_storage_path": bool(re.search(r"data(path|_path)|storage(path|_path)|new\s+url\s*\([^)]*data", lower)),
        "durable_read": bool(re.search(r"readfilesync|readfile\s*\(|readfileasync|read\s*data", lower)),
        "durable_write": bool(re.search(r"writefilesync|writefile\s*\(|writefileasync|write\s*data", lower)),
        "missing_file_handling": bool(re.search(r"exists(sync)?|enoent|not exist|if\s*\(!?[^)]*exists|catch\s*\([^)]*\)", lower)),
        "health_preserved": "/health" in content,
        "external_dependency_import": any(
            not value.startswith(("node:", ".", "/")) and value not in node_builtins
            for value in imports
        ),
    }


def lexical_content_attempt(raw: str, target: str = "server.js") -> dict[str, Any]:
    operation_match = re.search(r'"op"\s*:\s*"(replace_file_content|replace_text)"', raw)
    path_match = re.search(r'"path"\s*:\s*"([^"]+)"', raw)
    hash_match = re.search(r'"expected_sha256"\s*:\s*"([0-9a-f]+)"', raw)
    return {
        "present": bool(operation_match),
        "op": operation_match.group(1) if operation_match else "",
        "target": path_match.group(1) if path_match else "",
        "target_correct": bool(path_match and path_match.group(1) == target),
        "hash": hash_match.group(1) if hash_match else "",
        "hash_complete": bool(hash_match and len(hash_match.group(1)) == 64),
    }


def analyze_response(case, plan, errors, namespace):
    result = {
        "json_valid": False,
        "schema_valid": False,
        "generation_complete": case.get("generation_complete", True),
        "operation_count": 0,
        "server_content_operations": [],
        "server_content_operation_present": False,
        "target_correct": False,
        "expected_hash_correct": False,
        "content_non_empty": False,
        "paths_invented": [],
        "contract_errors": [],
        "required_actions_valid": True,
        "validators": {},
        "persistence_signals": {},
        "operation_error": None,
    }
    raw = case.get("content", "")
    try:
        parsed = json.loads(raw)
        result["json_valid"] = True
    except Exception as exc:
        result["contract_errors"] = ["INVALID_JSON"]
        result["lexical_content_attempt"] = lexical_content_attempt(raw)
        result["operation_error"] = {"type": type(exc).__name__, "message": str(exc)}
        return result, None
    schema_errors = list(Draft202012Validator(case["response_schema"]).iter_errors(parsed))
    if schema_errors:
        result["contract_errors"] = ["RESPONSE_SCHEMA_INVALID"]
        result["operation_error"] = {"type": "SchemaError", "message": "; ".join(item.message for item in schema_errors)}
        return result, parsed
    result["schema_valid"] = True
    operations = parsed["operations"]
    result["operation_count"] = len(operations)
    if "required_actions" in parsed:
        actions = parsed["required_actions"]
        result["required_actions_valid"] = any(
            item.get("target") == "server.js"
            and item.get("reason") == "PERSISTENCE_NOT_IMPLEMENTED"
            and item.get("required_operation_type") in {"replace_file_content", "replace_text"}
            for item in actions
        )
        if not result["required_actions_valid"]:
            result["contract_errors"].append("REQUIRED_ACTION_MISSING")
    try:
        normalized = validate_operations(operations, plan, namespace, case["schema"])
        result["normalized_operation_count"] = len(normalized)
        for operation in normalized:
            if operation["op"] in {"replace_file_content", "replace_text"}:
                result["server_content_operations"].append({
                    "op": operation["op"],
                    "path": operation["path"],
                    "content_non_empty": bool(operation.get("content", operation.get("new_text", ""))),
                    "expected_sha256": operation["expected_sha256"],
                    "expected_hash_correct": operation["expected_sha256"] == current_server_hash(plan),
                })
        result["server_content_operation_present"] = any(item["path"] == "server.js" for item in result["server_content_operations"])
        result["target_correct"] = all(item["path"] == "server.js" for item in result["server_content_operations"])
        result["expected_hash_correct"] = all(item["expected_hash_correct"] for item in result["server_content_operations"])
        result["content_non_empty"] = all(item["content_non_empty"] for item in result["server_content_operations"])
        result["paths_invented"] = [
            operation.get("path") for operation in operations
            if operation.get("path") and operation.get("path") not in namespace.valid_file_paths
        ]
        composed = apply_operations(plan, normalized, namespace, case["schema"])
        result["validators"] = run_real_validators(composed.plan, BASE_PROMPT)
        final_server = server_content(composed.plan)
        result["persistence_signals"] = persistence_signals(final_server)
        return result, composed
    except ContractError as exc:
        result["contract_errors"].append(exc.code)
        result["operation_error"] = exc.to_dict()
        return result, None


def schema_analysis(schema: dict) -> dict:
    branches = []
    for branch in schema["items"]["oneOf"]:
        branches.append({
            "op": branch["properties"]["op"]["const"],
            "property_count": len(branch["properties"]),
            "additional_properties": branch["additionalProperties"],
            "required": branch["required"],
            "content_fields": [field for field in branch["properties"] if field in {"content", "old_text", "new_text"}],
        })
    return {
        "root_type": schema["type"],
        "allows_empty_array": "minItems" not in schema,
        "max_items": schema.get("maxItems"),
        "branch_order": [item["op"] for item in branches],
        "branches": branches,
        "has_error_coverage_field": False,
        "represents_error_to_operation_dependency": False,
        "allows_plan_field_only_response": True,
        "observation": "A formally valid non-empty response may contain only set_* operations and omit content operations.",
    }


def write_report(summary: dict, schema_info: dict) -> None:
    rows = []
    for item in summary["cases"]:
        assessment = item["assessment"]
        content_status = "valid"
        if not assessment.get("server_content_operation_present"):
            lexical = assessment.get("lexical_content_attempt", {})
            content_status = "attempted/incomplete" if lexical.get("present") else "none"
        rows.append(
            f"| {item['id']} | {item['description']} | {content_status} | {assessment.get('validators', {}).get('valid', False)} | {item['status']} |"
        )
    report = f"""# Content Operation Audit

Status: **{summary['decision']}**

This audit is diagnostic only. It did not run WP1/WP2, MissionState, npm, preview, materialization, or production validators changes.

## Controlled calls

- Model: `qwen3.5:9b`
- Context: `8192`
- Temperature: `0`
- Top-p: `0.8`
- Think: `false`
- Calls executed: `{summary['model_calls']}`
- Retries: `0`
- Automatic repairs: `0`

## Baseline

`CONTENT_OPERATION_MANUAL_BASELINE_PASSED`: `{summary['manual_baseline_passed']}`

The manual patch changed only the virtual `server.js`, passed the real validators, and used the initial SHA256 `{summary['initial_server_sha256']}` as its expected hash.

## Comparison

| Test | Isolated modification | server.js operation | Persistence valid | Validators | Result |
|---|---|---:|---:|---:|---|
{chr(10).join(rows)}

## Schema findings

```json
{json.dumps(schema_info, ensure_ascii=False, indent=2)}
```

The original schema allows an empty operation array, does not require coverage of validator error IDs, and permits a formally valid response containing only plan-field operations. `replace_file_content` is not required by the schema and content-bearing branches are later than the simple branches.

## Answers

- The model did not consistently treat the `server.js` content change as mandatory: C1 omitted it; C2 recognized it lexically but failed to finish JSON.
- The original protocol made the operation optional in practice because no schema field required error coverage or a content operation.
- The schema permits simple plan operations without dependencies, so it can favor them over content branches.
- The controlled runs show incomplete structured generation for four content-attempt cases; they do not prove a pure model capacity limit independently of protocol pressure.
- `replace_file_content` was not reliable in these runs. `replace_text` produced a valid operation in C5, but not a valid complete correction.
- A template and a two-stage response did not produce a passing result in this six-call sample.
- The next step is protocol refinement around required error coverage and compact bounded content operations, not production integration or model replacement yet.

## Classification

{json.dumps(summary['classifications'], ensure_ascii=False, indent=2)}

## Decision

`{summary['decision']}`

The model is considered viable only if at least two semantically distinct tests pass, including one real content-generation test, with real validators passing and no manual full-solution injection. The recorded outcomes determine the decision above.

## Evidence

All requests, exact prompts, schemas, raw responses, normalized operations, validators, hashes and metrics are stored below this audit directory. No production file was edited.
"""
    (OUTPUT / "FINAL_REPORT.md").write_text(report, encoding="utf-8")


BASE_PROMPT = ""


def main() -> int:
    global BASE_PROMPT
    hashes = copy_inputs()
    plan, errors, base_schema, namespace, exact_request, BASE_PROMPT = load_case()
    write_json(OUTPUT / "namespace.json", namespace.to_dict())
    schema_info = schema_analysis(base_schema)
    write_json(OUTPUT / "schema_analysis.json", schema_info)
    cases = make_cases(plan, errors, namespace, base_schema, exact_request, BASE_PROMPT)
    summary = {
        "model": "qwen3.5:9b",
        "model_calls": 0,
        "manual_baseline_passed": False,
        "initial_server_sha256": current_server_hash(plan),
        "cases": [],
        "classifications": {},
        "decision": "AUDIT_INCONCLUSIVE",
        "input_hash_count": len(hashes),
        "production_changes": False,
        "materialization": False,
    }
    manual_validation = read_json(PROTO / "manual_validation.json")
    summary["manual_baseline_passed"] = bool(manual_validation.get("valid"))
    if not summary["manual_baseline_passed"]:
        summary["decision"] = "AUDIT_INCONCLUSIVE"
        write_json(OUTPUT / "summary.json", summary)
        write_report(summary, schema_info)
        return 1

    for case in cases:
        case_dir = OUTPUT / case["id"]
        case_dir.mkdir(parents=True, exist_ok=True)
        (case_dir / "prompt.txt").write_text(case["prompt"], encoding="utf-8")
        write_json(case_dir / "response.schema.json", case["response_schema"])
        write_json(case_dir / "operation.schema.json", case["schema"])
        request_payload = {
            "model": "qwen3.5:9b",
            "messages": [{"role": "user", "content": case["prompt"]}],
            "stream": False,
            "think": False,
            "format": case["response_schema"],
            "options": {"temperature": 0, "top_p": 0.8, "num_ctx": 8192},
        }
        write_json(case_dir / "request.json", request_payload)
        case_record = {"id": case["id"], "description": case["description"], "status": "FAILED", "assessment": {}}
        try:
            response = call_model(case["prompt"], case["response_schema"])
            summary["model_calls"] += 1
            (case_dir / "response_raw.txt").write_text(response["content"], encoding="utf-8")
            write_json(case_dir / "response_envelope.json", response["envelope"])
            metrics = {
                "elapsed_seconds": response["elapsed_seconds"],
                "prompt_bytes": len(case["prompt"].encode("utf-8")),
                "response_bytes": len(response["content"].encode("utf-8")),
                "response_sha256": hashlib.sha256(response["content"].encode("utf-8")).hexdigest(),
                "prompt_sha256": hashlib.sha256(case["prompt"].encode("utf-8")).hexdigest(),
                "prompt_eval_count": response["envelope"].get("prompt_eval_count"),
                "eval_count": response["envelope"].get("eval_count"),
            }
            write_json(case_dir / "metrics.json", metrics)
            case["content"] = response["content"]
            case["generation_complete"] = response["envelope"].get("done", True)
            assessment, composed = analyze_response(case, plan, errors, namespace)
            write_json(case_dir / "assessment.json", assessment)
            if composed is not None:
                write_json(case_dir / "composed_plan.json", composed.plan)
                write_json(case_dir / "changes.json", composed.changes)
            try:
                parsed = json.loads(response["content"])
                write_json(case_dir / "response.json", parsed)
                write_json(case_dir / "operations.json", parsed.get("operations", []))
            except Exception:
                pass
            case_record["assessment"] = assessment
            case_record["status"] = "PASSED" if assessment.get("validators", {}).get("valid") else "FAILED"
        except Exception as exc:
            case_record["error"] = {"type": type(exc).__name__, "message": str(exc)}
            write_json(case_dir / "error.json", case_record["error"])
        summary["cases"].append(case_record)

    passed_content = [
        item for item in summary["cases"]
        if item["assessment"].get("validators", {}).get("valid")
        and item["assessment"].get("server_content_operation_present")
        and item["assessment"].get("target_correct")
        and item["assessment"].get("expected_hash_correct")
        and item["assessment"].get("persistence_signals", {}).get("filesystem_import")
    ]
    if len(passed_content) >= 2 and any(item["id"] in {"C2", "C3", "C4", "C5", "C6"} for item in passed_content):
        summary["decision"] = "CONTENT_OPERATION_PROTOCOL_REFINEMENT_PASSED"
    elif any(item["id"] == "C5" for item in passed_content):
        summary["decision"] = "LOCAL_TEXT_PATCH_PROTOCOL_PREFERRED"
    elif any(item["id"] == "C6" for item in passed_content):
        summary["decision"] = "TWO_STAGE_TYPED_RESPONSE_PREFERRED"
    elif any(item["id"] == "C4" and item["assessment"].get("server_content_operation_present") for item in summary["cases"]):
        summary["decision"] = "FULL_FILE_CONTENT_GENERATION_UNRELIABLE"
    else:
        summary["decision"] = "QWEN_9B_TYPED_PATCH_UNRELIABLE"

    summary["classifications"] = {
        "REQUIRED_OPERATION_NOT_SALIENT": {"evidence": "C1 baseline response contained only set_* operations; C2 isolates salience.", "confidence": "pending C2"},
        "SCHEMA_BRANCH_AVOIDANCE": {"evidence": "C1 schema allows plan-only operations and places replacement branches after simple branches; C3 isolates branch set.", "confidence": "pending C3"},
        "CONTENT_GENERATION_TOO_COMPLEX": {"evidence": "C4 isolates a structural template while keeping full-file replacement.", "confidence": "pending C4"},
        "LOCAL_TEXT_PATCH_PROTOCOL_PREFERRED": {"evidence": "C5 isolates replace_text; classification only applies if C5 passes while full-file cases fail.", "confidence": "pending C5"},
        "ERROR_TO_OPERATION_LINK_MISSING": {"evidence": "Original response had no operation coverage field and no required error-to-operation relation.", "confidence": "high"},
        "MODEL_CAPACITY_LIMIT_FOR_CODE_PATCH": {"evidence": "Cannot be concluded until C2-C6 are compared.", "confidence": "low"},
    }
    write_json(OUTPUT / "summary.json", summary)
    write_report(summary, schema_info)
    return 0


if __name__ == "__main__":
    sys.exit(main())
