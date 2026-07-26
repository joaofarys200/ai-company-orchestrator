from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator


OUTPUT = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[3]
TYPED = ROOT / "diagnostics" / "project_builder_typed_patch_prototype" / "20260724-205420"
COMPACT = ROOT / "diagnostics" / "project_builder_compact_patch_protocol" / "20260724-213037"
MODEL_QWEN = "qwen3.5:9b"
MODEL_QWOPUS = "hf.co/Jackrong/Qwopus3.5-9B-v3-GGUF:Q4_K_M"
MODELS = (MODEL_QWEN, MODEL_QWOPUS)
OLLAMA_URL = "http://localhost:11434/api/chat"
TIMEOUT_SECONDS = 180

os.environ.setdefault("CREWAI_STORAGE_DIR", str(OUTPUT / "crewai_storage"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TYPED) not in sys.path:
    sys.path.insert(0, str(TYPED))
if str(COMPACT) not in sys.path:
    sys.path.insert(0, str(COMPACT))

from compact_protocol import (  # noqa: E402
    apply_response as apply_compact_response,
    build_namespace as build_compact_namespace,
    validate_response as validate_compact_response,
)
from typed_patch_prototype import (  # noqa: E402
    apply_operations,
    build_namespace as build_typed_namespace,
    run_real_validators,
    validate_operations,
)
from run_prototype import model_response_schema  # noqa: E402


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dump_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_command(args: list[str]) -> dict:
    started = time.perf_counter()
    try:
        result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        return {"command": args, "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr, "elapsed_seconds": round(time.perf_counter() - started, 3)}
    except Exception as exc:
        return {"command": args, "exit_code": None, "stdout": "", "stderr": str(exc), "error_type": type(exc).__name__, "elapsed_seconds": round(time.perf_counter() - started, 3)}


def collect_runtime_state() -> dict:
    state = {
        "ollama_list": run_command(["ollama", "list"]),
        "ollama_ps": run_command(["ollama", "ps"]),
        "models": {model: run_command(["ollama", "show", model]) for model in MODELS},
        "hardware": {
            "system": run_command(["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer,Model,TotalPhysicalMemory | ConvertTo-Json -Compress"]),
            "gpu": run_command(["nvidia-smi", "--query-gpu=name,memory.total,memory.used,driver_version", "--format=csv,noheader,nounits"]),
        },
    }
    return state


def copy_input(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def collect_inputs() -> dict[str, str]:
    sources = {
        "typed/model_request.json": TYPED / "model_request.json",
        "typed/model_prompt_used.txt": TYPED / "model_prompt_used.txt",
        "typed/response.schema.json": TYPED / "response.schema.json",
        "typed/operations.schema.json": TYPED / "operations.schema.json",
        "typed/plan.json": TYPED / "input" / "original_plan.json",
        "typed/initial_errors.json": TYPED / "input" / "initial_errors.json",
        "typed/namespace.json": TYPED / "namespace.json",
        "typed/historical_metrics.json": TYPED / "metrics.json",
        "compact/prompt.txt": COMPACT / "K1" / "prompt.txt",
        "compact/request_template.json": COMPACT / "K1" / "request.json",
        "compact/response_schema.json": COMPACT / "K1" / "schema.json",
        "compact/compact_schema.json": COMPACT / "compact_schema.json",
        "compact/plan.json": COMPACT / "input_original_plan.json",
        "compact/initial_errors.json": COMPACT / "input_initial_errors.json",
        "compact/validator_prompt.txt": COMPACT / "manual_validator_prompt.txt",
        "compact/historical_qwen_metrics.json": COMPACT / "K1" / "metrics.json",
        "compact/historical_qwen_response.json": COMPACT / "K1" / "response.json",
    }
    hashes: dict[str, str] = {}
    for relative, source in sources.items():
        target = OUTPUT / "inputs" / relative
        copy_input(source, target)
        hashes[relative] = sha256_file(source)
    dump(OUTPUT / "inputs" / "source_hashes.json", hashes)
    return hashes


def load_p1_case() -> tuple[dict, str, dict, object, dict]:
    template = load(TYPED / "model_request.json")
    plan = load(TYPED / "input" / "original_plan.json")
    errors = load(TYPED / "input" / "initial_errors.json")
    prompt = template["messages"][0]["content"]
    schema = template["format"]["properties"]["operations"]
    response_schema = template["format"]
    namespace = build_typed_namespace(plan, errors)
    return plan, prompt, schema, namespace, response_schema


def load_compact_case() -> tuple[dict, list[dict], str, dict, object, dict]:
    plan = load(COMPACT / "input_original_plan.json")
    errors = load(COMPACT / "input_initial_errors.json")
    prompt = (COMPACT / "K1" / "prompt.txt").read_text(encoding="utf-8")
    outer_schema = load(COMPACT / "K1" / "schema.json")
    compact_schema = load(COMPACT / "compact_schema.json")
    namespace = build_compact_namespace(plan, errors)
    return plan, errors, prompt, compact_schema, namespace, outer_schema


def make_payload(template: dict, model: str, prompt: str | None = None, response_schema: dict | None = None) -> dict:
    payload = copy.deepcopy(template)
    payload["model"] = model
    if prompt is not None:
        payload["messages"] = [{"role": "user", "content": prompt}]
    if response_schema is not None:
        payload["format"] = response_schema
    return payload


def call_once(case_dir: Path, model: str, payload: dict) -> tuple[dict | None, dict]:
    case_dir.mkdir(parents=True, exist_ok=True)
    dump(case_dir / "request.json", payload)
    request_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    started = time.perf_counter()
    request = Request(OLLAMA_URL, data=request_bytes, headers={"Content-Type": "application/json"}, method="POST")
    metrics = {
        "model": model,
        "timeout_seconds": TIMEOUT_SECONDS,
        "request_sha256": sha256_bytes(request_bytes),
        "prompt_sha256": sha256_text(payload["messages"][0]["content"]),
        "schema_sha256": sha256_text(json.dumps(payload["format"], sort_keys=True, ensure_ascii=False)),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw_bytes = response.read()
        envelope = json.loads(raw_bytes.decode("utf-8"))
        content = envelope.get("message", {}).get("content", "")
        metrics.update({
            "http_status": 200,
            "done": envelope.get("done"),
            "done_reason": envelope.get("done_reason"),
            "prompt_eval_count": envelope.get("prompt_eval_count"),
            "eval_count": envelope.get("eval_count"),
            "response_bytes": len(raw_bytes),
            "content_bytes": len(content.encode("utf-8")),
            "content_sha256": sha256_text(content),
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        })
        dump(case_dir / "response_envelope.json", envelope)
        dump_text(case_dir / "response_raw.txt", content)
        dump(case_dir / "metrics.json", metrics)
        dump(case_dir / "ollama_ps_after.json", run_command(["ollama", "ps"]))
        return envelope, metrics
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        metrics.update({"error_type": type(exc).__name__, "error": str(exc), "elapsed_seconds": round(time.perf_counter() - started, 3)})
        dump(case_dir / "metrics.json", metrics)
        dump(case_dir / "ollama_ps_after.json", run_command(["ollama", "ps"]))
        return None, metrics


def operation_paths(operations: list[dict]) -> list[str]:
    result = []
    for operation in operations:
        if isinstance(operation.get("path"), str):
            result.append(operation["path"])
        result.extend(path for path in operation.get("paths", []) if isinstance(path, str))
    return result


def validate_p1(case_dir: Path, envelope: dict | None, metrics: dict, plan: dict, prompt: str, schema: dict, namespace, response_schema: dict) -> dict:
    result = {
        "case": case_dir.name,
        "done": metrics.get("done"),
        "done_reason": metrics.get("done_reason"),
        "json_valid": False,
        "schema_valid": False,
        "operations_valid": False,
        "server_js_operation": False,
        "persistence_operation": False,
        "plan_operations": 0,
        "invented_paths": [],
        "validators_valid": False,
        "errors": [],
    }
    if not envelope or metrics.get("done") is not True:
        result["errors"].append({"code": "MODEL_NOT_COMPLETE", "message": "Response did not finish"})
        dump(case_dir / "assessment.json", result)
        return result
    content = (case_dir / "response_raw.txt").read_text(encoding="utf-8")
    try:
        response = json.loads(content)
        result["json_valid"] = True
    except json.JSONDecodeError as exc:
        result["errors"].append({"code": "JSON_INVALID", "message": str(exc)})
        dump(case_dir / "assessment.json", result)
        return result
    schema_errors = [error.message for error in Draft202012Validator(response_schema).iter_errors(response)]
    if schema_errors:
        result["errors"].append({"code": "SCHEMA_INVALID", "errors": schema_errors})
        dump(case_dir / "assessment.json", result)
        return result
    result["schema_valid"] = True
    operations = response.get("operations", [])
    result["plan_operations"] = sum(operation.get("op") in {"set_components", "set_component_files", "set_preview_strategy"} for operation in operations)
    valid_paths = set(namespace.valid_file_paths)
    result["invented_paths"] = sorted(set(operation_paths(operations)) - valid_paths)
    result["server_js_operation"] = any(operation.get("path") == "server.js" for operation in operations)
    result["persistence_operation"] = any(
        operation.get("path") == "server.js" and operation.get("op") in {"replace_file_content", "replace_text"}
        for operation in operations
    )
    try:
        accepted = validate_operations(operations, plan, namespace, schema)
        result["operations_valid"] = True
        patch = apply_operations(plan, operations, namespace, schema)
        dump(case_dir / "composed_plan.json", patch.plan)
        dump(case_dir / "changes.json", patch.changes)
        validator_report = run_real_validators(patch.plan, prompt)
        dump(case_dir / "validator_report.json", validator_report)
        result["validators_valid"] = bool(validator_report.get("valid"))
        final_server = next((item["content"] for item in patch.plan["files"] if item["path"] == "server.js"), "")
        result["persistence_detected_in_content"] = all(token in final_server for token in ("fs", "readFile", "writeFile"))
        result["accepted_operation_count"] = len(accepted)
        if not result["validators_valid"]:
            result["errors"].extend(validator_report.get("errors", []))
    except Exception as exc:
        result["errors"].append({"code": getattr(exc, "code", type(exc).__name__), "message": str(exc), "details": getattr(exc, "details", {})})
    dump(case_dir / "assessment.json", result)
    return result


def validate_compact(case_dir: Path, envelope: dict | None, metrics: dict, plan: dict, errors: list[dict], prompt: str, schema: dict, namespace, outer_schema: dict) -> dict:
    result = {
        "case": case_dir.name,
        "done": metrics.get("done"),
        "done_reason": metrics.get("done_reason"),
        "json_valid": False,
        "schema_valid": False,
        "operations_valid": False,
        "server_js_operation": False,
        "persistence_operation": False,
        "plan_operations": 0,
        "invented_paths": [],
        "validators_valid": False,
        "errors": [],
    }
    if not envelope or metrics.get("done") is not True:
        result["errors"].append({"code": "MODEL_NOT_COMPLETE", "message": "Response did not finish"})
        dump(case_dir / "assessment.json", result)
        return result
    content = (case_dir / "response_raw.txt").read_text(encoding="utf-8")
    try:
        response = json.loads(content)
        result["json_valid"] = True
    except json.JSONDecodeError as exc:
        result["errors"].append({"code": "JSON_INVALID", "message": str(exc)})
        dump(case_dir / "assessment.json", result)
        return result
    schema_errors = [error.message for error in Draft202012Validator(outer_schema).iter_errors(response)]
    if schema_errors:
        result["errors"].append({"code": "SCHEMA_INVALID", "errors": schema_errors})
        dump(case_dir / "assessment.json", result)
        return result
    result["schema_valid"] = True
    operations = response.get("operations", [])
    result["plan_operations"] = sum(operation.get("op") in {"set_components", "set_component_files", "set_preview_strategy"} for operation in operations)
    valid_paths = set(namespace.paths)
    result["invented_paths"] = sorted(set(operation_paths(operations)) - valid_paths)
    result["server_js_operation"] = any(operation.get("path") == "server.js" for operation in operations)
    result["persistence_operation"] = any(operation.get("path") == "server.js" and operation.get("transform") == "ADD_JSON_FILE_PERSISTENCE" for operation in operations)
    try:
        validate_compact_response(response, plan, errors, namespace, schema)
        result["operations_valid"] = True
        applied = apply_compact_response(response, plan, errors, namespace, schema, prompt)
        dump(case_dir / "apply_result.json", {
            "success": applied.success,
            "operations_applied": applied.operations_applied,
            "error_coverage_report": applied.error_coverage_report,
            "transform_report": applied.transform_report,
            "virtual_diff": applied.virtual_diff,
            "validator_report": applied.validator_report,
            "error": applied.error,
            "rolled_back": applied.rolled_back,
        })
        result["validators_valid"] = bool(applied.validator_report.get("valid"))
        result["accepted_operation_count"] = len(applied.operations_applied)
        if not applied.success:
            result["errors"].append(applied.error or {"code": "APPLY_FAILED", "message": "Compact apply failed"})
    except Exception as exc:
        result["errors"].append({"code": getattr(exc, "code", type(exc).__name__), "message": str(exc), "details": getattr(exc, "details", {})})
    dump(case_dir / "assessment.json", result)
    return result


def payload_difference(left: dict, right: dict) -> list[str]:
    differences: list[str] = []
    keys = sorted(set(left) | set(right))
    for key in keys:
        if key == "model":
            continue
        if left.get(key) != right.get(key):
            differences.append(key)
    return differences


def build_report(summary: dict) -> str:
    p1 = summary["cases"]["p1"]
    compact = summary["cases"]["compact"]
    def line(case: dict) -> str:
        return f"| {case['model']} | {case.get('done')} | {case.get('json_valid')} | {case.get('schema_valid')} | {case.get('server_js_operation')} | {case.get('persistence_operation')} | {case.get('validators_valid')} | {case.get('elapsed_seconds')} |"
    return "\n".join([
        "# Qwen3.5-9B vs Qwopus3.5-9B-v3 ProjectBuilder Benchmark",
        "",
        "## 1. Resumo executivo",
        f"Decisao: `{summary['decision']}`.",
        "Benchmark isolado com dois casos, quatro chamadas totais e sem alteracoes produtivas.",
        "",
        "## 2. Modelos",
        f"Qwen: `{MODEL_QWEN}`; Qwopus: `{MODEL_QWOPUS}`. Ambos permaneceram instalados.",
        "",
        "## 3. Hardware e memória",
        "A evidencia bruta de `ollama list`, `ollama show`, `ollama ps`, sistema e GPU esta em `runtime/`.",
        "Ollama reportou ambos como arquitetura qwen35/Q4_K_M; o Qwopus reportou 8.95B parametros e contexto suportado 262144.",
        "",
        "## 4. Configuração controlada",
        "Foram carregados sem reconstrução: payload, prompt e schema P1 do prototipo typed; prompt e schema K1 do protocolo compacto.",
        "Contexto 8192, temperature 0, top_p 0.8, think false, stream false, timeout 180 s. A unica diferenca intencional entre pares foi `model`.",
        f"Diferencas de payload fora de model: P1 `{summary['equivalence']['p1_non_model_differences']}`, compacto `{summary['equivalence']['compact_non_model_differences']}`.",
        "",
        "## 5. P1 — Qwen",
        f"{json.dumps(p1[MODEL_QWEN], ensure_ascii=False, indent=2)}",
        "",
        "## 6. P1 — Qwopus",
        f"{json.dumps(p1[MODEL_QWOPUS], ensure_ascii=False, indent=2)}",
        "",
        "## 7. Teste compacto — Qwen",
        f"{json.dumps(compact[MODEL_QWEN], ensure_ascii=False, indent=2)}",
        "",
        "## 8. Teste compacto — Qwopus",
        f"{json.dumps(compact[MODEL_QWOPUS], ensure_ascii=False, indent=2)}",
        "",
        "## 9. Comparação",
        "| Modelo/caso | done | JSON | schema | server.js | persistence op | validators | segundos |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        f"| P1 {MODEL_QWEN} | {p1[MODEL_QWEN].get('done')} | {p1[MODEL_QWEN].get('json_valid')} | {p1[MODEL_QWEN].get('schema_valid')} | {p1[MODEL_QWEN].get('server_js_operation')} | {p1[MODEL_QWEN].get('persistence_operation')} | {p1[MODEL_QWEN].get('validators_valid')} | {p1[MODEL_QWEN].get('elapsed_seconds')} |",
        f"| P1 {MODEL_QWOPUS} | {p1[MODEL_QWOPUS].get('done')} | {p1[MODEL_QWOPUS].get('json_valid')} | {p1[MODEL_QWOPUS].get('schema_valid')} | {p1[MODEL_QWOPUS].get('server_js_operation')} | {p1[MODEL_QWOPUS].get('persistence_operation')} | {p1[MODEL_QWOPUS].get('validators_valid')} | {p1[MODEL_QWOPUS].get('elapsed_seconds')} |",
        f"| Compacto {MODEL_QWEN} | {compact[MODEL_QWEN].get('done')} | {compact[MODEL_QWEN].get('json_valid')} | {compact[MODEL_QWEN].get('schema_valid')} | {compact[MODEL_QWEN].get('server_js_operation')} | {compact[MODEL_QWEN].get('persistence_operation')} | {compact[MODEL_QWEN].get('validators_valid')} | {compact[MODEL_QWEN].get('elapsed_seconds')} |",
        f"| Compacto {MODEL_QWOPUS} | {compact[MODEL_QWOPUS].get('done')} | {compact[MODEL_QWOPUS].get('json_valid')} | {compact[MODEL_QWOPUS].get('schema_valid')} | {compact[MODEL_QWOPUS].get('server_js_operation')} | {compact[MODEL_QWOPUS].get('persistence_operation')} | {compact[MODEL_QWOPUS].get('validators_valid')} | {compact[MODEL_QWOPUS].get('elapsed_seconds')} |",
        "",
        "## 10. Validators",
        "Cada resposta foi validada localmente e, quando a composição foi aceite, pelos validators reais reutilizados do prototipo. Nenhuma reparação foi feita.",
        "",
        "## 11. Desempenho",
        "Tempos, tokens, bytes, done_reason e estado de memoria estao nos metrics.json de cada caso e no diretório runtime.",
        "",
        "## 12. Limitações",
        "E um benchmark de uma fixture e de dois prompts fixos. Não mede capacidade geral. O teste não executa WP1/WP2, não materializa ficheiros, não inicia preview e não executa npm.",
        "",
        "## 13. Decisão",
        f"`{summary['decision']}`.",
        "",
        "## 14. Próximo passo",
        "Não alterar o ProjectBuilder com base neste benchmark. Se Qwopus passar, repetir a confirmação apenas num benchmark independente autorizado; se falhar, manter o diagnóstico de protocolo/modelo.",
    ]) + "\n"


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    source_hashes = collect_inputs()
    runtime_before = collect_runtime_state()
    dump(OUTPUT / "runtime" / "before.json", runtime_before)
    p1_plan, p1_prompt, p1_schema, p1_namespace, p1_response_schema = load_p1_case()
    compact_plan, compact_errors, compact_prompt, compact_schema, compact_namespace, compact_response_schema = load_compact_case()
    dump_text(OUTPUT / "inputs" / "p1_prompt_exact.txt", p1_prompt)
    dump_text(OUTPUT / "inputs" / "compact_prompt_exact.txt", compact_prompt)

    p1_template = load(TYPED / "model_request.json")
    compact_template = load(COMPACT / "K1" / "request.json")
    p1_cases: dict[str, dict] = {}
    compact_cases: dict[str, dict] = {}
    payload_equivalence = {}
    for model in MODELS:
        safe_name = "qwen" if model == MODEL_QWEN else "qwopus"
        print(f"P1 {model}: one request", flush=True)
        p1_payload = make_payload(p1_template, model)
        p1_dir = OUTPUT / "P1" / safe_name
        _, p1_metrics = call_once(p1_dir, model, p1_payload)
        p1_assessment = validate_p1(p1_dir, load(p1_dir / "response_envelope.json") if (p1_dir / "response_envelope.json").exists() else None, p1_metrics, p1_plan, p1_prompt, p1_schema, p1_namespace, p1_response_schema)
        p1_assessment["model"] = model
        p1_assessment["elapsed_seconds"] = p1_metrics.get("elapsed_seconds")
        p1_assessment["content_sha256"] = p1_metrics.get("content_sha256")
        p1_cases[model] = p1_assessment
        print(f"Compact {model}: one request", flush=True)
        compact_payload = make_payload(compact_template, model, compact_prompt, compact_response_schema)
        compact_dir = OUTPUT / "compact" / safe_name
        _, compact_metrics = call_once(compact_dir, model, compact_payload)
        compact_assessment = validate_compact(compact_dir, load(compact_dir / "response_envelope.json") if (compact_dir / "response_envelope.json").exists() else None, compact_metrics, compact_plan, compact_errors, compact_prompt, compact_schema, compact_namespace, compact_response_schema)
        compact_assessment["model"] = model
        compact_assessment["elapsed_seconds"] = compact_metrics.get("elapsed_seconds")
        compact_assessment["content_sha256"] = compact_metrics.get("content_sha256")
        compact_cases[model] = compact_assessment

    qwen_p1_payload = load(OUTPUT / "P1" / "qwen" / "request.json")
    qwopus_p1_payload = load(OUTPUT / "P1" / "qwopus" / "request.json")
    qwen_compact_payload = load(OUTPUT / "compact" / "qwen" / "request.json")
    qwopus_compact_payload = load(OUTPUT / "compact" / "qwopus" / "request.json")
    payload_equivalence = {
        "p1_non_model_differences": payload_difference(qwen_p1_payload, qwopus_p1_payload),
        "compact_non_model_differences": payload_difference(qwen_compact_payload, qwopus_compact_payload),
        "p1_prompt_equal": qwen_p1_payload["messages"][0]["content"] == qwopus_p1_payload["messages"][0]["content"],
        "compact_prompt_equal": qwen_compact_payload["messages"][0]["content"] == qwopus_compact_payload["messages"][0]["content"],
        "p1_schema_equal": qwen_p1_payload["format"] == qwopus_p1_payload["format"],
        "compact_schema_equal": qwen_compact_payload["format"] == qwopus_compact_payload["format"],
    }
    runtime_after = collect_runtime_state()
    dump(OUTPUT / "runtime" / "after.json", runtime_after)

    qwen_pass = all(p1_cases[MODEL_QWEN].get(key) and compact_cases[MODEL_QWEN].get(key) for key in ("validators_valid",))
    qwopus_pass = all(p1_cases[MODEL_QWOPUS].get(key) and compact_cases[MODEL_QWOPUS].get(key) for key in ("validators_valid",))
    qwen_complete = all(p1_cases[MODEL_QWEN].get(key) for key in ("done", "json_valid", "schema_valid")) and compact_cases[MODEL_QWEN].get("done") is True and compact_cases[MODEL_QWEN].get("json_valid") and compact_cases[MODEL_QWEN].get("schema_valid")
    qwopus_complete = all(p1_cases[MODEL_QWOPUS].get(key) for key in ("done", "json_valid", "schema_valid")) and compact_cases[MODEL_QWOPUS].get("done") is True and compact_cases[MODEL_QWOPUS].get("json_valid") and compact_cases[MODEL_QWOPUS].get("schema_valid")
    if payload_equivalence["p1_non_model_differences"] or payload_equivalence["compact_non_model_differences"] or not payload_equivalence["p1_prompt_equal"] or not payload_equivalence["compact_prompt_equal"] or not payload_equivalence["p1_schema_equal"] or not payload_equivalence["compact_schema_equal"]:
        decision = "BENCHMARK_INCONCLUSIVE"
    elif qwopus_pass and not qwen_pass:
        decision = "QWOPUS_REPLACES_QWEN_FOR_PROJECTBUILDER"
    elif qwopus_complete and not qwen_complete:
        decision = "QWOPUS_IMPROVES_BUT_NOT_SUFFICIENT"
    elif (
        (p1_cases[MODEL_QWOPUS].get("operations_valid") and not p1_cases[MODEL_QWEN].get("operations_valid"))
        or (compact_cases[MODEL_QWOPUS].get("operations_valid") and not compact_cases[MODEL_QWEN].get("operations_valid"))
    ) and not qwopus_pass:
        decision = "QWOPUS_IMPROVES_BUT_NOT_SUFFICIENT"
    else:
        decision = "QWOPUS_NO_MATERIAL_IMPROVEMENT"
    summary = {
        "decision": decision,
        "model_calls": 4,
        "no_retries": True,
        "no_local_repair": True,
        "production_changes": False,
        "materialization": False,
        "wp_execution": False,
        "npm_execution": False,
        "preview_started": False,
        "source_hashes": source_hashes,
        "equivalence": payload_equivalence,
        "cases": {"p1": p1_cases, "compact": compact_cases},
        "completeness": {"qwen": qwen_complete, "qwopus": qwopus_complete},
        "validator_success": {"qwen": qwen_pass, "qwopus": qwopus_pass},
    }
    dump(OUTPUT / "summary.json", summary)
    dump_text(OUTPUT / "FINAL_REPORT.md", build_report(summary))
    return 0


def recompute_existing() -> int:
    summary = load(OUTPUT / "summary.json")
    p1 = summary["cases"]["p1"]
    compact = summary["cases"]["compact"]
    qwen_pass = bool(p1[MODEL_QWEN].get("validators_valid") and compact[MODEL_QWEN].get("validators_valid"))
    qwopus_pass = bool(p1[MODEL_QWOPUS].get("validators_valid") and compact[MODEL_QWOPUS].get("validators_valid"))
    qwen_complete = all(p1[MODEL_QWEN].get(key) for key in ("done", "json_valid", "schema_valid")) and all(compact[MODEL_QWEN].get(key) for key in ("done", "json_valid", "schema_valid"))
    qwopus_complete = all(p1[MODEL_QWOPUS].get(key) for key in ("done", "json_valid", "schema_valid")) and all(compact[MODEL_QWOPUS].get(key) for key in ("done", "json_valid", "schema_valid"))
    equivalence = summary["equivalence"]
    if equivalence["p1_non_model_differences"] or equivalence["compact_non_model_differences"] or not equivalence["p1_prompt_equal"] or not equivalence["compact_prompt_equal"] or not equivalence["p1_schema_equal"] or not equivalence["compact_schema_equal"]:
        decision = "BENCHMARK_INCONCLUSIVE"
    elif qwopus_pass and not qwen_pass:
        decision = "QWOPUS_REPLACES_QWEN_FOR_PROJECTBUILDER"
    elif qwopus_complete and not qwen_complete:
        decision = "QWOPUS_IMPROVES_BUT_NOT_SUFFICIENT"
    elif ((p1[MODEL_QWOPUS].get("operations_valid") and not p1[MODEL_QWEN].get("operations_valid")) or (compact[MODEL_QWOPUS].get("operations_valid") and not compact[MODEL_QWEN].get("operations_valid"))) and not qwopus_pass:
        decision = "QWOPUS_IMPROVES_BUT_NOT_SUFFICIENT"
    else:
        decision = "QWOPUS_NO_MATERIAL_IMPROVEMENT"
    summary["decision"] = decision
    dump(OUTPUT / "summary.json", summary)
    dump_text(OUTPUT / "FINAL_REPORT.md", build_report(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(recompute_existing() if "--recompute" in sys.argv else main())
