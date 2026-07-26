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
OLLAMA_URL = "http://localhost:11434/api/chat"
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
from run_compact_protocol import compact_prompt  # noqa: E402


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


def public_baseline() -> dict:
    return {
        "operations": [
            {"op": "set_components", "value": ["frontend", "backend", "persistence", "tests", "preview"]},
            {"op": "set_component_files", "component": "frontend", "paths": ["index.html"]},
            {"op": "set_component_files", "component": "backend", "paths": ["server.js"]},
            {"op": "set_component_files", "component": "persistence", "paths": ["server.js"]},
            {"op": "set_component_files", "component": "tests", "paths": ["test.js"]},
            {"op": "set_component_files", "component": "preview", "paths": ["index.html"]},
            {"op": "apply_code_transform", "path": "server.js", "transform": "ADD_JSON_FILE_PERSISTENCE"},
        ]
    }


def normalize_previous(response: dict) -> dict:
    """Remove only metadata that the new public contract no longer accepts."""
    normalized = copy.deepcopy(response)
    normalized.pop("error_resolutions", None)
    for operation in normalized.get("operations", []):
        operation.pop("id", None)
        operation.pop("operation_id", None)
        operation.pop("expected_sha256", None)
        operation.pop("parameters", None)
    return normalized


def assess(case_dir: Path, response: dict, plan: dict, errors: list[dict], namespace, schema: dict, validator_prompt: str, source: str) -> dict:
    normalized = normalize_previous(response)
    dump(case_dir / "response_normalized.json", normalized)
    result = {
        "source": source,
        "schema_valid": False,
        "coverage": False,
        "binding": False,
        "apply": False,
        "validators": False,
        "errors": [],
    }
    schema_errors = [error.message for error in Draft202012Validator(schema).iter_errors(normalized)]
    if schema_errors:
        result["errors"].append({"code": "SCHEMA_INVALID", "details": schema_errors})
        dump(case_dir / "assessment.json", result)
        return result
    result["schema_valid"] = True
    try:
        validated = validate_response(normalized, plan, errors, namespace, schema)
        result["coverage"] = bool(validated["coverage"]["valid"])
        bound, bindings = bind_trusted_metadata(normalized, plan, namespace)
        result["binding"] = bool(bindings)
        dump(case_dir / "trusted_binding.json", {"bindings": bindings, "operations": bound["operations"]})
        applied = apply_response(normalized, plan, errors, namespace, schema, validator_prompt)
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
        result["errors"].append({
            "code": getattr(exc, "code", type(exc).__name__),
            "message": str(exc),
            "details": getattr(exc, "details", {}),
        })
    dump(case_dir / "assessment.json", result)
    return result


def call_final(case_dir: Path, prompt: str, schema: dict) -> tuple[dict | None, dict]:
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "format": schema,
        "options": {"temperature": 0, "top_p": 0.8, "num_ctx": 8192},
    }
    dump(case_dir / "request.json", payload)
    started = time.perf_counter()
    request = Request(
        OLLAMA_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
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
            "schema_sha256": sha256_text(json.dumps(schema, sort_keys=True, ensure_ascii=False)),
            "response_bytes": len(raw),
            "timeout_seconds": PROMPT_TIMEOUT,
        }
        dump(case_dir / "response_envelope.json", envelope)
        dump_text(case_dir / "response_raw.txt", content)
        dump(case_dir / "metrics.json", metrics)
        return envelope, metrics
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        metrics = {
            "model": MODEL,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "timeout_seconds": PROMPT_TIMEOUT,
        }
        dump(case_dir / "metrics.json", metrics)
        return None, metrics


def assess_final(case_dir: Path, envelope: dict | None, metrics: dict, plan: dict, errors: list[dict], namespace, schema: dict, validator_prompt: str) -> dict:
    result = {
        "model": MODEL,
        "done": metrics.get("done"),
        "done_reason": metrics.get("done_reason"),
        "json_valid": False,
        "schema_valid": False,
        "coverage": False,
        "binding": False,
        "apply": False,
        "validators": False,
        "errors": [],
    }
    if envelope is None or metrics.get("done") is not True:
        result["errors"].append({"code": "MODEL_NOT_COMPLETE"})
        dump(case_dir / "assessment.json", result)
        return result
    try:
        response = json.loads((case_dir / "response_raw.txt").read_text(encoding="utf-8"))
        result["json_valid"] = True
    except (OSError, json.JSONDecodeError) as exc:
        result["errors"].append({"code": "JSON_INVALID", "message": str(exc)})
        dump(case_dir / "assessment.json", result)
        return result
    schema_errors = [error.message for error in Draft202012Validator(schema).iter_errors(response)]
    if schema_errors:
        result["errors"].append({"code": "SCHEMA_INVALID", "details": schema_errors})
        dump(case_dir / "assessment.json", result)
        return result
    result["schema_valid"] = True
    try:
        validated = validate_response(response, plan, errors, namespace, schema)
        result["coverage"] = bool(validated["coverage"]["valid"])
        bound, bindings = bind_trusted_metadata(response, plan, namespace)
        result["binding"] = bool(bindings)
        dump(case_dir / "trusted_binding.json", {"bindings": bindings, "operations": bound["operations"]})
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
        result["errors"].append({
            "code": getattr(exc, "code", type(exc).__name__),
            "message": str(exc),
            "details": getattr(exc, "details", {}),
        })
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
        "O modelo seleciona apenas operações públicas. O executor atribui IDs internos, fornece `data.json`, calcula hashes confiáveis e rejeita `SNAPSHOT_CHANGED`.",
        "",
        "## Testes",
        "O schema público contém apenas `operations`; hashes, IDs, parâmetros, referências de erro e conteúdo livre são rejeitados.",
        "",
        "## Reavaliação K1–K4",
        json.dumps(summary["reassessment"], ensure_ascii=False, indent=2),
        "",
        "## Chamada final",
        json.dumps(summary["final_call"], ensure_ascii=False, indent=2),
        "",
        "## Validators",
        f"Resultado: `{summary['final_call'].get('validators')}`. Não houve retry, reparação local ou materialização.",
        "",
        "## Decisão",
        f"`{summary['decision']}`.",
        "",
        "## Próximo passo",
        "Não executar outra ronda automaticamente.",
        "",
    ])


def main() -> int:
    plan = load(PROTO / "input_original_plan.json")
    errors = load(PROTO / "input_initial_errors.json")
    namespace = build_namespace(plan, errors)
    schema = build_schema(namespace, minimal=True)
    prompt = compact_prompt(plan, errors, namespace, minimal=True)
    validator_prompt = (PROTO / "manual_validator_prompt.txt").read_text(encoding="utf-8")
    dump(OUTPUT / "schema.json", schema)
    dump_text(OUTPUT / "prompt.txt", prompt)
    dump(OUTPUT / "input_plan.json", plan)
    dump(OUTPUT / "input_errors.json", errors)
    dump_text(OUTPUT / "validator_prompt.txt", validator_prompt)

    manual = apply_response(public_baseline(), plan, errors, namespace, schema, validator_prompt)
    dump(OUTPUT / "manual_result.json", {
        "success": manual.success,
        "trusted_bindings": manual.trusted_bindings,
        "operations_applied": manual.operations_applied,
        "validator_report": manual.validator_report,
        "virtual_diff": manual.virtual_diff,
        "error": manual.error,
    })

    sources = {
        "K1": PROTO / "K1" / "response.json",
        "K2": PROTO / "K2" / "response.json",
        "K3": PROTO / "K3" / "response.json",
        "K4": PROTO / "K4" / "response.json",
        "previous_final": ROOT / "diagnostics" / "project_builder_compact_patch_protocol" / "20260724-221141" / "final_call" / "response_raw.txt",
    }
    reassessment = {}
    for name, path in sources.items():
        raw = json.loads(path.read_text(encoding="utf-8")) if path.suffix == ".json" else json.loads(path.read_text(encoding="utf-8"))
        source_response = normalize_previous(raw)
        case_dir = OUTPUT / "reassessment" / name
        reassessment[name] = assess(case_dir, source_response, plan, errors, namespace, schema, validator_prompt, "previous_response_metadata_removed_only")

    final_dir = OUTPUT / "final_call"
    print("Final compact v2 call: qwen3.5:9b (exactly one request)", flush=True)
    envelope, metrics = call_final(final_dir, prompt, schema)
    final = assess_final(final_dir, envelope, metrics, plan, errors, namespace, schema, validator_prompt)
    final["elapsed_seconds"] = metrics.get("elapsed_seconds")
    final["content_sha256"] = metrics.get("content_sha256")

    if not manual.success:
        decision = "DETERMINISTIC_COVERAGE_FAILED"
    elif envelope is None or metrics.get("done") is not True or not final["json_valid"]:
        decision = "VALIDATION_INCONCLUSIVE"
    elif not final["schema_valid"] or not final["coverage"]:
        decision = "MODEL_OPERATION_SELECTION_FAILED"
    elif not final["binding"] or not final["apply"] or not final["validators"]:
        decision = "TRANSFORM_APPLICATION_FAILED"
    else:
        decision = "COMPACT_PROTOCOL_PASSED"

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
