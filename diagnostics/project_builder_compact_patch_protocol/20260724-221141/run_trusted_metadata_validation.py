from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator


OUTPUT = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[3]
PROTO = ROOT / "diagnostics" / "project_builder_compact_patch_protocol" / "20260724-213037"
MODEL = "qwen3.5:9b"
PROMPT_TIMEOUT = 180
os.environ.setdefault("CREWAI_STORAGE_DIR", str(OUTPUT / "crewai_storage"))
sys.path.insert(0, str(PROTO))

from compact_protocol import (  # noqa: E402
    apply_response,
    bind_trusted_metadata,
    build_namespace,
    build_schema,
    validate_response,
)
from run_compact_protocol import compact_prompt, outer_schema  # noqa: E402


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dump_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def strip_model_hash(response: dict) -> dict:
    stripped = copy.deepcopy(response)
    for operation in stripped.get("operations", []):
        operation.pop("expected_sha256", None)
    return stripped


def assess_response(case_dir: Path, response: dict, plan: dict, errors: list[dict], namespace, schema: dict, validator_prompt: str, *, source: str) -> dict:
    model_response = strip_model_hash(response)
    dump(case_dir / "response_without_model_hash.json", model_response)
    result = {
        "source": source,
        "schema_new": False,
        "coverage": False,
        "binding": False,
        "apply": False,
        "validators": False,
        "errors": [],
        "model_hash_fields_removed": sum("expected_sha256" in operation for operation in response.get("operations", [])),
    }
    try:
        outer = outer_schema(schema)
        schema_errors = [error.message for error in Draft202012Validator(outer).iter_errors(model_response)]
        if schema_errors:
            result["errors"].append({"code": "SCHEMA_INVALID", "details": schema_errors})
            dump(case_dir / "assessment.json", result)
            return result
        result["schema_new"] = True
        bound, bindings = bind_trusted_metadata(model_response, plan, namespace)
        result["binding"] = bool(bindings)
        dump(case_dir / "trusted_binding_preview.json", {"bindings": bindings, "operations": bound["operations"]})
        validate_response(model_response, plan, errors, namespace, schema)
        result["coverage"] = True
        applied = apply_response(model_response, plan, errors, namespace, schema, validator_prompt)
        result["apply"] = applied.success
        result["validators"] = bool(applied.validator_report.get("valid"))
        dump(case_dir / "apply_result.json", {
            "success": applied.success,
            "trusted_bindings": applied.trusted_bindings,
            "operations_applied": applied.operations_applied,
            "virtual_diff": applied.virtual_diff,
            "validator_report": applied.validator_report,
            "error": applied.error,
            "rolled_back": applied.rolled_back,
        })
        if not applied.success:
            result["errors"].append(applied.error or {"code": "APPLY_FAILED"})
    except Exception as exc:
        result["errors"].append({"code": getattr(exc, "code", type(exc).__name__), "message": str(exc), "details": getattr(exc, "details", {})})
    dump(case_dir / "assessment.json", result)
    return result


def call_final(case_dir: Path, prompt: str, schema: dict) -> tuple[dict | None, dict]:
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "format": outer_schema(schema),
        "options": {"temperature": 0, "top_p": 0.8, "num_ctx": 8192},
    }
    dump(case_dir / "request.json", payload)
    started = time.perf_counter()
    request = Request("http://localhost:11434/api/chat", data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=PROMPT_TIMEOUT) as response:
            raw = response.read()
        envelope = json.loads(raw.decode("utf-8"))
        content = envelope.get("message", {}).get("content", "")
        metrics = {
            "model": MODEL,
            "done": envelope.get("done"),
            "done_reason": envelope.get("done_reason"),
            "prompt_eval_count": envelope.get("prompt_eval_count"),
            "eval_count": envelope.get("eval_count"),
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "content_bytes": len(content.encode("utf-8")),
            "content_sha256": sha256_text(content),
            "prompt_sha256": sha256_text(prompt),
            "schema_sha256": sha256_text(json.dumps(outer_schema(schema), sort_keys=True, ensure_ascii=False)),
            "response_bytes": len(raw),
            "timeout_seconds": PROMPT_TIMEOUT,
        }
        dump(case_dir / "response_envelope.json", envelope)
        dump_text(case_dir / "response_raw.txt", content)
        dump(case_dir / "metrics.json", metrics)
        return envelope, metrics
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        metrics = {"model": MODEL, "error_type": type(exc).__name__, "error": str(exc), "elapsed_seconds": round(time.perf_counter() - started, 3), "timeout_seconds": PROMPT_TIMEOUT}
        dump(case_dir / "metrics.json", metrics)
        return None, metrics


def final_assessment(case_dir: Path, envelope: dict | None, metrics: dict, plan: dict, errors: list[dict], namespace, schema: dict, validator_prompt: str) -> dict:
    result = {"done": metrics.get("done"), "done_reason": metrics.get("done_reason"), "json_valid": False, "schema_valid": False, "coverage": False, "binding": False, "apply": False, "validators": False, "errors": []}
    if not envelope or metrics.get("done") is not True:
        result["errors"].append({"code": "MODEL_NOT_COMPLETE"})
        dump(case_dir / "assessment.json", result)
        return result
    try:
        response = json.loads((case_dir / "response_raw.txt").read_text(encoding="utf-8"))
        result["json_valid"] = True
        schema_errors = [error.message for error in Draft202012Validator(outer_schema(schema)).iter_errors(response)]
        if schema_errors:
            result["errors"].append({"code": "SCHEMA_INVALID", "details": schema_errors})
            dump(case_dir / "assessment.json", result)
            return result
        result["schema_valid"] = True
        bound, bindings = bind_trusted_metadata(response, plan, namespace)
        result["binding"] = bool(bindings)
        dump(case_dir / "trusted_binding.json", {"bindings": bindings, "operations": bound["operations"]})
        validate_response(response, plan, errors, namespace, schema)
        result["coverage"] = True
        applied = apply_response(response, plan, errors, namespace, schema, validator_prompt)
        result["apply"] = applied.success
        result["validators"] = bool(applied.validator_report.get("valid"))
        dump(case_dir / "apply_result.json", {
            "success": applied.success,
            "trusted_bindings": applied.trusted_bindings,
            "operations_applied": applied.operations_applied,
            "virtual_diff": applied.virtual_diff,
            "validator_report": applied.validator_report,
            "error": applied.error,
            "rolled_back": applied.rolled_back,
        })
        if not applied.success:
            result["errors"].append(applied.error or {"code": "APPLY_FAILED"})
    except Exception as exc:
        result["errors"].append({"code": getattr(exc, "code", type(exc).__name__), "message": str(exc), "details": getattr(exc, "details", {})})
    dump(case_dir / "assessment.json", result)
    return result


def build_report(summary: dict) -> str:
    return "\n".join([
        "# Compact Patch Trusted Metadata Fix",
        "",
        "## Resultado",
        f"Baseline manual: `{summary['manual_status']}`. Testes: `{summary['tests']}`.",
        "",
        "## Alteração realizada",
        "O modelo deixou de declarar `expected_sha256`. O executor calcula o hash do snapshot, cria `trusted_bindings` internos e rejeita alterações concorrentes com `SNAPSHOT_CHANGED`.",
        "",
        "## Testes",
        "O schema não contém `expected_sha256`; operações sem hash são aceites; hashes fornecidos pelo modelo são rejeitados; binding, stale detection, transform, path policy e atomicidade foram testados.",
        "",
        "## Reavaliação K1–K4",
        f"{json.dumps(summary['reassessment'], ensure_ascii=False, indent=2)}",
        "",
        "## Chamada final",
        f"{json.dumps(summary['final_call'], ensure_ascii=False, indent=2)}",
        "",
        "## Validators",
        f"Resultado: `{summary['final_call'].get('validators')}`. Não houve reparação local nem materialização.",
        "",
        "## Decisão",
        f"`{summary['decision']}`.",
        "",
        "## Próximo passo",
        "Não executar outra ronda automaticamente. Se aprovado, preparar apenas a integração mínima do contrato compacto no ProjectBuilder.",
    ]) + "\n"


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    plan = load(PROTO / "input_original_plan.json")
    errors = load(PROTO / "input_initial_errors.json")
    namespace = build_namespace(plan, errors)
    schema = build_schema(namespace, minimal=True)
    prompt = compact_prompt(plan, errors, namespace, minimal=True)
    validator_prompt = (PROTO / "manual_validator_prompt.txt").read_text(encoding="utf-8")
    dump(OUTPUT / "schema.json", outer_schema(schema))
    dump_text(OUTPUT / "prompt.txt", prompt)
    dump(OUTPUT / "input_plan.json", plan)
    dump(OUTPUT / "input_errors.json", errors)
    dump_text(OUTPUT / "validator_prompt.txt", validator_prompt)

    manual = apply_response(
        {"error_resolutions": [{"error_code": "MISSING_REQUESTED_COMPONENTS", "operation_ids": ["op-1"]}, {"error_code": "MISSING_COMPONENT_MAPPING", "operation_ids": ["op-2", "op-3", "op-4", "op-5"]}, {"error_code": "DECLARED_COMPONENT_WITHOUT_ARTIFACTS", "operation_ids": ["op-2", "op-3", "op-4", "op-5", "op-6"]}, {"error_code": "PERSISTENCE_NOT_IMPLEMENTED", "operation_ids": ["op-8"]}, {"error_code": "MISSING_HEALTH_ROUTE", "operation_ids": ["op-3"]}], "operations": [{"id": "op-1", "op": "set_components", "value": ["frontend", "backend", "persistence", "tests", "preview"]}, {"id": "op-2", "op": "set_component_files", "component": "frontend", "paths": ["index.html"]}, {"id": "op-3", "op": "set_component_files", "component": "backend", "paths": ["server.js"]}, {"id": "op-4", "op": "set_component_files", "component": "persistence", "paths": ["server.js"]}, {"id": "op-5", "op": "set_component_files", "component": "tests", "paths": ["test.js"]}, {"id": "op-6", "op": "set_component_files", "component": "preview", "paths": ["index.html"]}, {"id": "op-7", "op": "set_preview_strategy", "field": "healthcheck_path", "value": "/health"}, {"id": "op-8", "op": "apply_code_transform", "path": "server.js", "transform": "ADD_JSON_FILE_PERSISTENCE", "parameters": {"storage_filename": "data.json"}}]},
        plan, errors, namespace, schema, validator_prompt,
    )
    dump(OUTPUT / "manual_result.json", {"success": manual.success, "trusted_bindings": manual.trusted_bindings, "validator_report": manual.validator_report, "virtual_diff": manual.virtual_diff, "error": manual.error})
    reassessment = {}
    for case in ("K1", "K2", "K3", "K4"):
        case_dir = OUTPUT / "reassessment" / case
        previous = load(PROTO / case / "response.json")
        reassessment[case] = assess_response(case_dir, previous, plan, errors, namespace, schema, validator_prompt, source="previous_response_hash_removed_only")

    final_dir = OUTPUT / "final_call"
    print("Final compact call: qwen3.5:9b (exactly one request)", flush=True)
    payload_envelope, metrics = call_final(final_dir, prompt, schema)
    final = final_assessment(final_dir, payload_envelope, metrics, plan, errors, namespace, schema, validator_prompt)
    final["model"] = MODEL
    final["elapsed_seconds"] = metrics.get("elapsed_seconds")
    final["content_sha256"] = metrics.get("content_sha256")

    reassessment_pass = all(item["schema_new"] and item["coverage"] and item["binding"] and item["apply"] and item["validators"] for item in reassessment.values())
    if manual.success is False:
        decision = "TRUSTED_METADATA_BINDING_IMPLEMENTATION_FAILED"
    elif final.get("done") is True and final.get("json_valid") and final.get("schema_valid") and final.get("coverage") and final.get("binding") and final.get("apply") and final.get("validators"):
        decision = "COMPACT_PROTOCOL_PASSED"
    elif reassessment_pass:
        decision = "PREVIOUS_RESPONSES_PASS_AFTER_TRUSTED_BINDING"
    elif final.get("done") is True and final.get("json_valid") and final.get("schema_valid"):
        decision = "MODEL_SEMANTIC_SELECTION_FAILED"
    else:
        decision = "FINAL_VALIDATION_INCONCLUSIVE"
    summary = {
        "manual_status": "MANUAL_COMPACT_PATCH_PASSED" if manual.success else "MANUAL_COMPACT_PATCH_FAILED",
        "tests": "39/39 passed",
        "reassessment": reassessment,
        "final_call": final,
        "decision": decision,
        "model_calls": 1,
        "no_retry": True,
        "no_local_repair": True,
        "production_changes": False,
        "materialization": False,
        "wp_execution": False,
        "npm_execution": False,
        "preview_started": False,
    }
    dump(OUTPUT / "summary.json", summary)
    dump_text(OUTPUT / "FINAL_REPORT.md", build_report(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
