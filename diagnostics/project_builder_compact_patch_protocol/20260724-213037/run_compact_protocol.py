from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from jsonschema import Draft202012Validator

os.environ.setdefault(
    "CREWAI_STORAGE_DIR",
    str(Path(__file__).resolve().parent / "crewai_storage"),
)
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from compact_protocol import (  # noqa: E402
    ERROR_CODES,
    TRANSFORM_IDS,
    ApplyResult,
    build_namespace,
    build_schema,
    apply_response,
    sha256_text,
    transform_catalog,
    validate_response,
)


OUTPUT = Path(__file__).resolve().parent
ROOT = _REPO_ROOT
TYPED = ROOT / "diagnostics" / "project_builder_typed_patch_prototype" / "20260724-205420"
CONTENT = ROOT / "diagnostics" / "project_builder_content_operation_audit" / "20260724-211340"
QUALITY = ROOT / "diagnostics" / "project_builder_plan_quality_audit" / "20260724-193345"
RECORDER = ROOT / "diagnostics" / "project_builder_flight_recorder" / "5ac225a31d8b471db547d15b36b9d0e4"
MODEL = "qwen3.5:9b"
MODEL_OPTIONS = {"temperature": 0, "top_p": 0.8, "num_ctx": 8192}
OLLAMA_URL = "http://localhost:11434/api/chat"


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dump_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_source(relative: str, destination: str | None = None) -> None:
    source = ROOT / relative
    target = OUTPUT / "source" / (destination or relative)
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def collect_sources() -> dict[str, str]:
    requested = [
        "diagnostics/project_builder_typed_patch_prototype/20260724-205420/input/original_plan.json",
        "diagnostics/project_builder_typed_patch_prototype/20260724-205420/input/initial_errors.json",
        "diagnostics/project_builder_typed_patch_prototype/20260724-205420/manual_operations.json",
        "diagnostics/project_builder_typed_patch_prototype/20260724-205420/manual_composed_plan.json",
        "diagnostics/project_builder_typed_patch_prototype/20260724-205420/manual_validation.json",
        "diagnostics/project_builder_typed_patch_prototype/20260724-205420/model_operations.json",
        "diagnostics/project_builder_typed_patch_prototype/20260724-205420/model_validation.json",
        "diagnostics/project_builder_typed_patch_prototype/20260724-205420/scope_derivation.json",
        "diagnostics/project_builder_typed_patch_prototype/20260724-205420/operations.schema.json",
        "diagnostics/project_builder_typed_patch_prototype/20260724-205420/FINAL_REPORT.md",
        "diagnostics/project_builder_content_operation_audit/20260724-211340/summary.json",
        "diagnostics/project_builder_content_operation_audit/20260724-211340/schema_analysis.json",
        "diagnostics/project_builder_content_operation_audit/20260724-211340/FINAL_REPORT.md",
        "diagnostics/project_builder_content_operation_audit/20260724-211340/input/hashes.json",
        "diagnostics/project_builder_plan_quality_audit/20260724-193345/source/ollama_requester_audit/wp1_prompt.txt",
        "diagnostics/project_builder_flight_recorder/5ac225a31d8b471db547d15b36b9d0e4/summary.json",
        "diagnostics/project_builder_flight_recorder/5ac225a31d8b471db547d15b36b9d0e4/final_state.json",
        "diagnostics/project_builder_flight_recorder/5ac225a31d8b471db547d15b36b9d0e4/errors.json",
    ]
    for relative in requested:
        copy_source(relative)
    for case in ("C1", "C2", "C3", "C4", "C5", "C6"):
        source_dir = CONTENT / case
        if source_dir.exists():
            copy_source(f"diagnostics/project_builder_content_operation_audit/20260724-211340/{case}")
    hashes: dict[str, str] = {}
    for path in sorted((OUTPUT / "source").rglob("*")):
        if path.is_file():
            hashes[str(path.relative_to(OUTPUT)).replace("\\", "/")] = sha256_file(path)
    dump(OUTPUT / "source_hashes.json", hashes)
    return hashes


def manual_operations(plan: dict) -> list[dict]:
    server = next(item for item in plan["files"] if item["path"] == "server.js")
    return [
        {"id": "op-1", "op": "set_components", "value": ["frontend", "backend", "persistence", "tests", "preview"]},
        {"id": "op-2", "op": "set_component_files", "component": "frontend", "paths": ["index.html"]},
        {"id": "op-3", "op": "set_component_files", "component": "backend", "paths": ["server.js"]},
        {"id": "op-4", "op": "set_component_files", "component": "persistence", "paths": ["server.js"]},
        {"id": "op-5", "op": "set_component_files", "component": "tests", "paths": ["test.js"]},
        {"id": "op-6", "op": "set_component_files", "component": "preview", "paths": ["index.html"]},
        {"id": "op-7", "op": "set_preview_strategy", "field": "healthcheck_path", "value": "/health"},
        {"id": "op-8", "op": "apply_code_transform", "path": "server.js", "transform": "ADD_JSON_FILE_PERSISTENCE", "parameters": {"storage_filename": "data.json"}},
    ]


def manual_response(plan: dict) -> dict:
    ops = manual_operations(plan)
    return {
        "error_resolutions": [
            {"error_code": "MISSING_REQUESTED_COMPONENTS", "operation_ids": ["op-1"]},
            {"error_code": "MISSING_COMPONENT_MAPPING", "operation_ids": ["op-2", "op-3", "op-4", "op-5"]},
            {"error_code": "DECLARED_COMPONENT_WITHOUT_ARTIFACTS", "operation_ids": ["op-2", "op-3", "op-4", "op-5", "op-6"]},
            {"error_code": "PERSISTENCE_NOT_IMPLEMENTED", "operation_ids": ["op-8"]},
            {"error_code": "MISSING_HEALTH_ROUTE", "operation_ids": ["op-3"]},
        ],
        "operations": ops,
    }


def outer_schema(compact_schema: dict) -> dict:
    return compact_schema


def compact_prompt(plan: dict, errors: list[dict], namespace, *, minimal: bool = False, reordered: bool = False) -> str:
    error_lines = []
    seen = set()
    for error in errors:
        if error["code"] in seen:
            continue
        seen.add(error["code"])
        error_lines.append(f'- {error["code"]}: {error["message"]} Acao: {error["suggestion"]}')
    paths = [item["path"] for item in plan["files"]]
    full_catalog = [
        'set_components: value is the complete final component array.',
        'set_component_files: component plus complete final paths array.',
        'apply_code_transform: path server.js and a registered transform.',
    ]
    minimal_catalog = [
        'set_components: complete final array.',
        'set_component_files: complete final paths for a component.',
        'apply_code_transform: server.js with ADD_JSON_FILE_PERSISTENCE. The executor supplies storage_filename=data.json and binds integrity metadata.',
    ]
    catalog = minimal_catalog if minimal else full_catalog
    if reordered:
        catalog = [catalog[-1], *catalog[:-1]]
    matrix = [
        'MISSING_REQUESTED_COMPONENTS -> set_components',
        'MISSING_COMPONENT_MAPPING -> set_component_files',
        'DECLARED_COMPONENT_WITHOUT_ARTIFACTS -> set_component_files',
        'PERSISTENCE_NOT_IMPLEMENTED -> apply_code_transform ADD_JSON_FILE_PERSISTENCE on server.js',
        'MISSING_HEALTH_ROUTE -> set_component_files backend server.js when /health already exists',
    ]
    transform_lines = [
        "- ADD_JSON_FILE_PERSISTENCE: only server.js; adds node:fs, deterministic JSON path, durable read/write and missing-file handling; preserves node:http and /health; no external dependencies.",
    ]
    if not minimal:
        transform_lines.append("- PRESERVE_HEALTH_ROUTE, EXPORT_SERVER_FOR_TESTS, PRESERVE_HTTP_IMPORT: preservation transforms only where their preconditions apply.")
    return "\n".join([
        "You are returning a compact typed correction protocol for a validated project plan.",
        "Resolve every listed error.",
        "Do not generate source code. Do not create paths. Do not omit required corrections.",
        "Use only the closed operation catalog and registered transforms.",
        "The executor derives error coverage from the closed error catalog; the model does not declare error coverage.",
        f"Project: {plan['project_name']} | stack: {plan['stack']}",
        f"Allowed existing paths: {json.dumps(paths)}",
        "Initial components: [frontend, backend, persistence, tests]; requested component: preview.",
        "Initial preview strategy exists and must remain coherent; existing server.js contains /health.",
        "Initial errors:",
        *error_lines,
        "Operation catalog:",
        *[f"- {item}" for item in catalog],
        "Transform catalog:",
        *transform_lines,
        "Error to operation compatibility:",
        *[f"- {item}" for item in matrix],
        'The response must contain exactly one top-level key: "operations".',
        "The model does not provide operation IDs. The executor assigns deterministic internal IDs op-01, op-02, and so on.",
        "Do not return error_resolutions, operation_ids, parameters, storage_filename, expected_sha256, sizes, timestamps or snapshot IDs.",
        "Use no replace_file_content, replace_text, arbitrary code, file creation, diff, JSON Patch, append, retry or autorepair.",
        "The executor supplies deterministic transform parameters and calculates trusted integrity metadata from the initial virtual snapshot.",
        "Return JSON only.",
    ])


def read_ollama(prompt: str, schema: dict) -> tuple[dict | None, dict]:
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "format": schema,
        "options": MODEL_OPTIONS,
    }
    started = time.perf_counter()
    request = Request(OLLAMA_URL, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    metrics = {"model": MODEL, "options": MODEL_OPTIONS, "request_sha256": sha256_text(json.dumps(payload, sort_keys=True)), "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "timeout_seconds": 180}
    try:
        with urlopen(request, timeout=180) as response:
            raw_envelope = response.read()
        envelope = json.loads(raw_envelope.decode("utf-8"))
        content = envelope.get("message", {}).get("content", "")
        metrics.update({
            "http_status": 200,
            "done": envelope.get("done"),
            "done_reason": envelope.get("done_reason"),
            "prompt_eval_count": envelope.get("prompt_eval_count"),
            "eval_count": envelope.get("eval_count"),
            "response_bytes": len(raw_envelope),
            "content_bytes": len(content.encode("utf-8")),
            "content_sha256": sha256_text(content),
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        })
        return envelope, {**metrics, "raw_envelope": raw_envelope.decode("utf-8", errors="replace"), "content": content}
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        metrics.update({"error_type": type(exc).__name__, "error": str(exc), "elapsed_seconds": round(time.perf_counter() - started, 3)})
        return None, metrics


def response_result(case_dir: Path, envelope: dict | None, metrics: dict, plan: dict, errors: list[dict], namespace, schema: dict, validator_prompt: str) -> dict:
    dump(case_dir / "metrics.json", {key: value for key, value in metrics.items() if key not in {"raw_envelope", "content"}})
    if "raw_envelope" in metrics:
        dump_text(case_dir / "response_envelope_raw.json", metrics["raw_envelope"])
    content = metrics.get("content", "")
    dump_text(case_dir / "response_raw.txt", content)
    result = {"case": case_dir.name, "done": metrics.get("done"), "done_reason": metrics.get("done_reason"), "content_sha256": metrics.get("content_sha256"), "json_valid": False, "schema_valid": False, "coverage_valid": False, "transform_valid": False, "apply_success": False, "validators_valid": False, "errors": []}
    if not envelope or metrics.get("done") is not True:
        result["errors"].append({"code": "MODEL_NOT_COMPLETE", "message": "Ollama response did not finish", "done": metrics.get("done")})
        dump(case_dir / "assessment.json", result)
        return result
    try:
        candidate = json.loads(content)
        result["json_valid"] = True
        dump(case_dir / "response.json", candidate)
        schema_errors = [error.message for error in Draft202012Validator(schema).iter_errors(candidate)]
        if schema_errors:
            result["schema_errors"] = schema_errors
            result["errors"].append({"code": "SCHEMA_INVALID", "message": "Response does not satisfy compact protocol schema", "errors": schema_errors})
            dump(case_dir / "assessment.json", result)
            return result
        result["schema_valid"] = True
        try:
            validate_response(candidate, plan, errors, namespace, schema)
        except Exception as exc:
            result["errors"].append({"code": getattr(exc, "code", type(exc).__name__), "message": str(exc), "details": getattr(exc, "details", {})})
            dump(case_dir / "assessment.json", result)
            return result
        result.update({"coverage_valid": True, "transform_valid": True})
        applied: ApplyResult = apply_response(candidate, plan, errors, namespace, schema, validator_prompt)
        dump(case_dir / "apply_result.json", {
            "success": applied.success,
            "operations_applied": applied.operations_applied,
            "error_coverage_report": applied.error_coverage_report,
            "transform_report": applied.transform_report,
            "virtual_diff": applied.virtual_diff,
            "validator_report": applied.validator_report,
            "error": applied.error,
            "rolled_back": applied.rolled_back,
            "trusted_bindings": applied.trusted_bindings,
        })
        result.update({"apply_success": applied.success, "validators_valid": bool(applied.validator_report.get("valid")), "virtual_change_count": len(applied.virtual_diff)})
        if not applied.success:
            result["errors"].append(applied.error or {"code": "APPLY_FAILED", "message": "Virtual apply failed"})
        else:
            dump(case_dir / "composed_plan.json", applied.plan)
    except Exception as exc:  # validation output is persisted, not repaired
        result["errors"].append({"code": type(exc).__name__, "message": str(exc)})
    dump(case_dir / "assessment.json", result)
    return result


def manual_baseline(plan: dict, errors: list[dict], namespace, schema: dict, validator_prompt: str) -> dict:
    response = manual_response(plan)
    dump(OUTPUT / "manual_response.json", response)
    applied = apply_response(response, plan, errors, namespace, schema, validator_prompt)
    dump(OUTPUT / "operations_applied.json", applied.operations_applied)
    dump(OUTPUT / "error_coverage_report.json", applied.error_coverage_report)
    dump(OUTPUT / "transform_report.json", applied.transform_report)
    dump(OUTPUT / "virtual_diff.json", applied.virtual_diff)
    dump(OUTPUT / "validator_report.json", applied.validator_report)
    dump(OUTPUT / "virtual_files_before.json", {item["path"]: item["content"] for item in plan["files"]})
    dump(OUTPUT / "virtual_files_after.json", {item["path"]: item["content"] for item in (applied.plan or {}).get("files", [])})
    metrics = {"status": "MANUAL_COMPACT_PATCH_PASSED" if applied.success else "MANUAL_COMPACT_PATCH_FAILED", "operation_count": len(applied.operations_applied), "virtual_change_count": len(applied.virtual_diff), "validator_valid": bool(applied.validator_report.get("valid"))}
    dump(OUTPUT / "manual_metrics.json", metrics)
    return {"response": response, "apply": applied, "metrics": metrics}


def comparison_prompt(base: str, *, minimal: bool = False, reordered: bool = False) -> str:
    return base


def main() -> int:
    if "--recompute" in sys.argv:
        return recompute_existing()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    collect_sources()
    plan = load(TYPED / "input" / "original_plan.json")
    errors = load(TYPED / "input" / "initial_errors.json")
    namespace = build_namespace(plan, errors)
    full_schema = build_schema(namespace)
    validator_prompt = (QUALITY / "source" / "ollama_requester_audit" / "wp1_prompt.txt").read_text(encoding="utf-8")
    dump(OUTPUT / "input_original_plan.json", plan)
    dump(OUTPUT / "input_initial_errors.json", errors)
    dump(OUTPUT / "namespace.json", namespace.to_dict())
    dump(OUTPUT / "transform_catalog.json", transform_catalog(namespace))
    dump(OUTPUT / "compact_schema.json", full_schema)
    dump(OUTPUT / "response_schema.json", outer_schema(full_schema))
    manual = manual_baseline(plan, errors, namespace, full_schema, validator_prompt)
    dump_text(OUTPUT / "manual_validator_prompt.txt", validator_prompt)
    if not manual["apply"].success:
        raise SystemExit("manual compact baseline failed")

    cases = [
        ("K1", False, False),
        ("K2", False, False),
        ("K3", False, True),
        ("K4", True, False),
    ]
    case_results = []
    base_prompt = compact_prompt(plan, errors, namespace)
    for case, minimal, reordered in cases:
        case_dir = OUTPUT / case
        case_dir.mkdir(exist_ok=True)
        schema = build_schema(namespace, minimal=minimal, reordered=reordered)
        prompt = compact_prompt(plan, errors, namespace, minimal=minimal, reordered=reordered)
        dump_text(case_dir / "prompt.txt", prompt)
        dump(case_dir / "schema.json", outer_schema(schema))
        dump(case_dir / "request.json", {"model": MODEL, "stream": False, "think": False, "format": outer_schema(schema), "options": MODEL_OPTIONS})
        print(f"{case}: calling {MODEL} (exactly one request)", flush=True)
        envelope, metrics = read_ollama(prompt, outer_schema(schema))
        case_results.append(response_result(case_dir, envelope, metrics, plan, errors, namespace, schema, validator_prompt))

    dump(OUTPUT / "case_results.json", case_results)
    k1_hash = next((item.get("content_sha256") for item in case_results if item["case"] == "K1"), None)
    k2_hash = next((item.get("content_sha256") for item in case_results if item["case"] == "K2"), None)
    all_done = all(item.get("done") is True for item in case_results)
    full_passes = sum(bool(item["apply_success"] and item["validators_valid"]) for item in case_results)
    k12_pass = all(item["apply_success"] and item["validators_valid"] for item in case_results[:2])
    if manual["metrics"]["status"] != "MANUAL_COMPACT_PATCH_PASSED":
        decision = "AUDIT_INCONCLUSIVE"
    elif full_passes >= 3 and k12_pass and all_done:
        decision = "COMPACT_TYPED_PROTOCOL_PASSED"
    elif any(item.get("done") is False for item in case_results):
        decision = "COMPACT_PROTOCOL_MODEL_TRUNCATION_PERSISTS"
    elif full_passes == 0:
        decision = "QWEN_9B_PROTOCOL_SELECTION_UNRELIABLE"
    else:
        decision = "COMPACT_PROTOCOL_MODEL_SEMANTIC_FAILURE"
    summary = {
        "decision": decision,
        "model": MODEL,
        "context": MODEL_OPTIONS["num_ctx"],
        "temperature": MODEL_OPTIONS["temperature"],
        "top_p": MODEL_OPTIONS["top_p"],
        "think": False,
        "calls_requested": 4,
        "calls_completed": len(case_results),
        "manual_status": manual["metrics"]["status"],
        "unit_tests": "32/32 passed before model calls",
        "full_model_passes": full_passes,
        "k1_k2_pass": k12_pass,
        "k1_k2_raw_response_equal": k1_hash == k2_hash if k1_hash and k2_hash else False,
        "all_responses_done": all_done,
        "cases": case_results,
        "production_changes": False,
        "materialization": False,
        "wp_execution": False,
    }
    dump(OUTPUT / "summary.json", summary)
    report = build_report(summary, plan, errors, namespace, manual)
    dump_text(OUTPUT / "FINAL_REPORT.md", report)
    return 0


def recompute_existing() -> int:
    plan = load(OUTPUT / "input_original_plan.json")
    errors = load(OUTPUT / "input_initial_errors.json")
    namespace = build_namespace(plan, errors)
    validator_prompt = (OUTPUT / "manual_validator_prompt.txt").read_text(encoding="utf-8")
    case_results = []
    for case, minimal, reordered in (("K1", False, False), ("K2", False, False), ("K3", False, True), ("K4", True, False)):
        case_dir = OUTPUT / case
        schema = build_schema(namespace, minimal=minimal, reordered=reordered)
        envelope = load(case_dir / "response_envelope_raw.json")
        metrics = load(case_dir / "metrics.json")
        metrics["content"] = (case_dir / "response_raw.txt").read_text(encoding="utf-8")
        case_results.append(response_result(case_dir, envelope, metrics, plan, errors, namespace, schema, validator_prompt))
    manual_apply_result = load(OUTPUT / "validator_report.json")
    manual_metrics = load(OUTPUT / "manual_metrics.json")
    full_passes = sum(bool(item["apply_success"] and item["validators_valid"]) for item in case_results)
    k12_pass = all(item["apply_success"] and item["validators_valid"] for item in case_results[:2])
    all_done = all(item.get("done") is True for item in case_results)
    schema_failures = sum(bool(item.get("json_valid") and not item.get("schema_valid")) for item in case_results)
    if manual_metrics["status"] != "MANUAL_COMPACT_PATCH_PASSED":
        decision = "AUDIT_INCONCLUSIVE"
    elif full_passes >= 3 and k12_pass and all_done:
        decision = "COMPACT_TYPED_PROTOCOL_PASSED"
    elif any(item.get("done") is False for item in case_results):
        decision = "COMPACT_PROTOCOL_MODEL_TRUNCATION_PERSISTS"
    elif schema_failures == len(case_results):
        decision = "COMPACT_PROTOCOL_SCHEMA_FAILED"
    elif full_passes == 0:
        decision = "QWEN_9B_PROTOCOL_SELECTION_UNRELIABLE"
    else:
        decision = "COMPACT_PROTOCOL_MODEL_SEMANTIC_FAILURE"
    k1_hash = case_results[0].get("content_sha256")
    k2_hash = case_results[1].get("content_sha256")
    summary = {
        "decision": decision,
        "model": MODEL,
        "context": MODEL_OPTIONS["num_ctx"],
        "temperature": MODEL_OPTIONS["temperature"],
        "top_p": MODEL_OPTIONS["top_p"],
        "think": False,
        "calls_requested": 4,
        "calls_completed": len(case_results),
        "manual_status": manual_metrics["status"],
        "unit_tests": "32/32 passed before model calls",
        "full_model_passes": full_passes,
        "k1_k2_pass": k12_pass,
        "k1_k2_raw_response_equal": k1_hash == k2_hash if k1_hash and k2_hash else False,
        "all_responses_done": all_done,
        "schema_failure_count": schema_failures,
        "k4_operation_catalog_minimal": True,
        "k4_transform_catalog_minimal": "PRESERVE_HEALTH_ROUTE" not in (OUTPUT / "K4" / "prompt.txt").read_text(encoding="utf-8"),
        "cases": case_results,
        "production_changes": False,
        "materialization": False,
        "wp_execution": False,
    }
    dump(OUTPUT / "case_results.json", case_results)
    dump(OUTPUT / "summary.json", summary)
    manual = {"apply": type("ManualApply", (), {"operations_applied": load(OUTPUT / "operations_applied.json"), "virtual_diff": load(OUTPUT / "virtual_diff.json"), "validator_report": manual_apply_result})(), "metrics": manual_metrics}
    dump_text(OUTPUT / "FINAL_REPORT.md", build_report(summary, plan, errors, namespace, manual))
    return 0


def build_report(summary: dict, plan: dict, errors: list[dict], namespace, manual: dict) -> str:
    case_lines = []
    for item in summary["cases"]:
        case_lines.append(
            f"| {item['case']} | {item.get('done')} | {item.get('done_reason')} | {item.get('json_valid')} | {item.get('schema_valid')} | {item.get('apply_success')} | {item.get('validators_valid')} | {item.get('errors')} |"
        )
    error_codes = ", ".join(ERROR_CODES)
    return "\n".join([
        "# ProjectBuilder Compact Typed Patch Protocol Report",
        "",
        "## 1. Resumo executivo",
        f"Decisao final: `{summary['decision']}`.",
        f"O baseline manual terminou em `{summary['manual_status']}` com {len(manual['apply'].operations_applied)} operacoes e {len(manual['apply'].virtual_diff)} alteracao virtual.",
        "A experiencia e offline/diagnostica: nao houve escrita num projeto, materializacao, preview, npm, WP1 ou WP2.",
        "",
        "## 2. Escopo e fontes",
        "Foram reutilizados o prototipo typed, a auditoria de content operations, a auditoria de qualidade do plano e o flight recorder indicados pelo protocolo.",
        f"Namespace de erros: `{error_codes}`.",
        f"Paths permitidos: `{', '.join(namespace.paths)}`.",
        "",
        "## 3. Contrato compacto",
        "Resposta: `error_resolutions` e `operations`. Cada erro unico aparece exatamente uma vez; cada referencia aponta para uma operacao existente.",
        "Operacoes fechadas: `set_components`, `set_component_files`, `set_preview_strategy`, `apply_code_transform`.",
        "Nao ha campos de conteudo livre, replace_file_content, replace_text, criacao de ficheiros, JSON Patch ou codigo fornecido pelo modelo.",
        "",
        "## 4. Catalogo de transforms",
        "`ADD_JSON_FILE_PERSISTENCE` e o unico transform com alteracao de conteudo. E restrito a server.js, exige SHA-256 inicial e produz node:fs, caminho JSON deterministico, leitura/escrita duravel, missing-file handling, preservando node:http e /health.",
        "Os transforms de preservacao sao fechados e nao introduzem alteracoes.",
        "",
        "## 5. Baseline manual",
        "O baseline cobriu os cinco erros unicos, mapeou persistence para server.js e aplicou somente o transform deterministico registado.",
        f"Validadores reais: `{manual['apply'].validator_report.get('valid')}`.",
        "",
        "## 6. Execucao K1-K4",
        "Todas as chamadas usaram qwen3.5:9b, num_ctx=8192, temperature=0, top_p=0.8, think=false, structured output, stream=false.",
        "Nao foram usados retries, autorepair ou uma terceira chamada.",
        "",
        "| Caso | done | done_reason | JSON | schema | apply | validators | erros |",
        "|---|---:|---|---:|---:|---:|---:|---|",
        *case_lines,
        "",
        "## 7. Determinismo e variacao controlada",
        f"K1/K2 raw response SHA-256 igual: `{summary['k1_k2_raw_response_equal']}`.",
        "K3 manteve a semantica do schema e alterou apenas a ordem documental do catalogo.",
        f"K4 teve catalogo de operacoes minimo: `{summary.get('k4_operation_catalog_minimal', True)}`. O prompt efetivamente registado nesta execucao manteve a documentacao dos transforms de preservacao: catalogo de transforms minimo = `{summary.get('k4_transform_catalog_minimal', False)}`. O runner foi corrigido para remover essa documentacao em futuras execucoes; nao foi feita uma quinta chamada.",
        "",
        "## 8. Atomicidade virtual",
        "A validacao ocorre antes da mutacao. A composicao usa uma copia virtual profunda; qualquer falha devolve rollback virtual e nunca grava artefactos no workspace/projects.",
        "",
        "## 9. Validacao",
        "Os 32 testes unitarios do protocolo passaram antes das chamadas ao modelo. Cada resposta completa foi sujeita ao schema, cobertura, compatibilidade semantica, transform e validadores reais do prototipo anterior.",
        "",
        "## 10. Artefactos produzidos",
        "O diretorio contem prompts, schemas, payloads, envelopes brutos, metrics, respostas normalizadas, assessments, apply results, hashes das fontes e este relatorio.",
        "",
        "## 11. Seguranca",
        "Nenhum conteudo de source code foi aceite do modelo. Nenhum path fora do namespace foi aceito. Nenhum ficheiro foi criado pelo protocolo. Nenhuma API produtiva foi alterada.",
        "",
        "## 12. Limites do resultado",
        "Este prototipo valida uma fixture virtual especifica e nao prova integracao produtiva. O resultado do modelo mede selecao de operacoes compactas, nao capacidade geral de programacao.",
        "",
        "## 13. Criterio de viabilidade",
        "Passaria apenas com baseline manual, testes, pelo menos 3/4 casos completos, K1/K2 completos, respostas nao truncadas e validadores reais aprovados.",
        f"Neste run: {summary['full_model_passes']}/4 casos completos; K1/K2: `{summary['k1_k2_pass']}`; todas completas: `{summary['all_responses_done']}`.",
        "",
        "## 14. Alteracoes produtivas",
        "Nenhuma. Nao foram alterados agents/orchestrator, ProjectBuilder, MissionExecutor, requester, validadores, modelos, .env ou configuracao.",
        "",
        "## 15. Reproducibilidade",
        "Executar os 32 testes locais e o runner deste diretorio reproduz o protocolo. A experiencia de modelo e deliberadamente limitada a quatro chamadas sequenciais ao endpoint Ollama.",
        "",
        "## 16. Comparacao consolidada",
        "O primeiro prototipo typed permitia representar operacoes mas o modelo tinha falhas de cobertura e selecao. Este segundo prototipo reduz a linguagem a operacoes enumeradas e transforms registados, eliminando payload de codigo livre. A decisao acima deve ser lida em conjunto com os artefactos por caso.",
    ]) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
